package com.psyagent.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.psyagent.dto.Caller;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Stream;

/**
 * 长期记忆：每个使用者一个 JSON 文件（data/users/&lt;id&gt;.json），记录
 *  - facts：从对话中沉淀下来的、关于这个人的事实（家人、健康、习惯、喜欢的东西）
 *  - turns：历史对话轮次（跨会话，用于"接得上上次的话"）
 *  - care：主动关怀记录（避免重复打扰）
 *
 * 为什么不用数据库：毕设演示场景下 JSON 文件足够，且零部署成本；
 * 量级上来后换成 SQLite / PostgreSQL，接口不用改。
 */
@Service
public class MemoryService {

    private static final Logger log = LoggerFactory.getLogger(MemoryService.class);
    private static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final int MAX_TURNS = 200;
    private static final int MAX_FACTS = 30;
    private static final int MEMORY_TURNS_IN_PROMPT = 8;
    private static final int MAX_EVENTS = 20;
    private static final int MAX_MOOD = 20;

    /** 情绪评分的正/负关键词（规则层，零模型成本） */
    private static final Set<String> POS_KW = Set.of(
            "开心", "高兴", "好多了", "放松", "轻松", "感谢", "谢谢", "进步", "舒服",
            "愉快", "棒", "不错", "好玩", "喜欢", "期待");
    private static final Set<String> NEG_KW = Set.of(
            "难过", "痛苦", "绝望", "焦虑", "崩溃", "压抑", "想哭", "孤独",
            "累", "失眠", "无助", "害怕", "烦", "委屈", "生气", "失败");

    private static final String TONE_DIRECTIVE = "【语气调整】对方最近几轮对话里情绪持续偏低。请调整语气：\n"
            + "- 句子更短，语气更柔和；少讲道理，多听。\n"
            + "- 最多给 1 个建议，或者干脆不给建议，只做情绪承接。\n"
            + "- 结尾的问题要更轻、更容易回答，比如「现在想不想再多说一点？」\n"
            + "- 如果合适，可以自然地提议：「要不要和我一起做一次小呼吸练习？吸气 4 秒、屏住 4 秒、慢慢呼气 6 秒。」但不要命令对方。\n"
            + "- 不要直接说「我注意到你情绪低落」，用行动表现关心。";

    private final ObjectMapper mapper;
    private final ChatModel chatModel;
    private final Path root;
    /** 抽取事实会多花一次模型调用，放到后台线程，不拖慢回答 */
    private final ExecutorService extractor = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "memory-extractor");
        t.setDaemon(true);
        return t;
    });

    public MemoryService(ObjectMapper mapper, ChatModel chatModel) {
        this.mapper = mapper;
        this.chatModel = chatModel;
        this.root = Path.of("data", "users");
    }

    /** 一个使用者的记忆档案 */
    public static class Memory {
        public String id;
        public String name;
        public String role;
        public String firstSeen;
        public String lastActive;
        public String lastGreetingDate;
        public String lastRiskLevel;
        public String lastExtractAtTurn;
        public List<Fact> facts = new ArrayList<>();
        public List<Turn> turns = new ArrayList<>();
        public List<Care> care = new ArrayList<>();
        public List<Event> events = new ArrayList<>();
        public List<MoodScore> moodScores = new ArrayList<>();
        public String lastMoodCareAt;
        public String lastReconnectDate;
        public String lastStoryDate;
        public String overallMood;
        public String emotionTrend;
    }

    public static class Fact {
        public String text;
        public String at;

        public Fact() { }

        public Fact(String text, String at) {
            this.text = text;
            this.at = at;
        }
    }

    /** 用户提过的、未来会发生的具体事情（考试、复查、比赛、生日等） */
    public static class Event {
        public String text;
        public String date;      // yyyy-MM-dd
        public boolean reminded;
        public String at;

        public Event() { }

        public Event(String text, String date, String at) {
            this.text = text;
            this.date = date;
            this.at = at;
        }
    }

    /** 每轮对话的情绪分数：-3(很低落) ~ +3(很积极) */
    public static class MoodScore {
        public int score;
        public String at;

        public MoodScore() { }

        public MoodScore(int score, String at) {
            this.score = score;
            this.at = at;
        }
    }

    public static class Turn {
        public String speaker;   // user | assistant
        public String content;
        public String at;

        public Turn() { }

        public Turn(String speaker, String content, String at) {
            this.speaker = speaker;
            this.content = content;
            this.at = at;
        }
    }

    public static class Care {
        public String id;
        public String text;
        public String at;
        public String reason;
        public boolean delivered;
        public String type;                  // message | breath | story（旧数据 null = message）
        public Map<String, Object> payload;  // breath: {"pattern":…}；story: {"title":…,"content":…}

        public Care() { }

        public Care(String text, String reason, String at) {
            this.text = text;
            this.reason = reason;
            this.at = at;
        }
    }

    // ---------- 读写 ----------

    public synchronized Memory load(Caller caller) {
        Path file = fileOf(caller.id());
        Memory m = null;
        if (Files.exists(file)) {
            try {
                m = mapper.readValue(file.toFile(), Memory.class);
            } catch (Exception e) {
                log.warn("记忆文件损坏，重建：{}", file, e);
            }
        }
        if (m == null) {
            m = new Memory();
            m.id = caller.id();
            m.firstSeen = now();
        }
        if (caller.name() != null && !caller.name().isBlank()) {
            m.name = caller.name();
        }
        m.role = caller.role();
        return m;
    }

    public synchronized void save(Memory m) {
        try {
            Files.createDirectories(root);
            Path file = fileOf(m.id);
            Path tmp = file.resolveSibling(file.getFileName() + ".tmp");
            mapper.writerWithDefaultPrettyPrinter().writeValue(tmp.toFile(), m);
            Files.move(tmp, file, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException e) {
            log.error("写入记忆失败：{}", m.id, e);
        }
    }

    private Path fileOf(String id) {
        String safe = id == null ? "anonymous" : id.replaceAll("[^a-zA-Z0-9_-]", "_");
        return root.resolve(safe + ".json");
    }

    private static String now() {
        return LocalDateTime.now().format(FMT);
    }

    // ---------- 写入 ----------

    /** 记录一轮对话；顺带更新活跃时间与最近风险 */
    public synchronized void recordTurn(Caller caller, String speaker, String content, Integer riskLevel) {
        Memory m = load(caller);
        m.turns.add(new Turn(speaker, content, now()));
        if (m.turns.size() > MAX_TURNS) {
            m.turns = new ArrayList<>(m.turns.subList(m.turns.size() - MAX_TURNS, m.turns.size()));
        }
        m.lastActive = now();
        if (riskLevel != null) {
            m.lastRiskLevel = String.valueOf(riskLevel);
        }
        save(m);
    }

    public synchronized void addFact(Caller caller, String text) {
        if (text == null || text.isBlank()) return;
        Memory m = load(caller);
        String t = text.trim();
        boolean dup = m.facts.stream().anyMatch(f -> f.text.equals(t));
        if (dup) return;
        m.facts.add(new Fact(t, now()));
        if (m.facts.size() > MAX_FACTS) {
            m.facts = new ArrayList<>(m.facts.subList(m.facts.size() - MAX_FACTS, m.facts.size()));
        }
        save(m);
    }

    /** 记录一个未来事件（按 text+date 去重，最多保留 MAX_EVENTS 条） */
    public synchronized void addEvent(Caller caller, String text, String date) {
        if (text == null || text.isBlank()) return;
        Memory m = load(caller);
        boolean dup = m.events.stream()
                .anyMatch(e -> e.text.equals(text.trim()) && Objects.equals(e.date, date));
        if (dup) return;
        m.events.add(new Event(text.trim(), date, now()));
        if (m.events.size() > MAX_EVENTS) {
            m.events = new ArrayList<>(m.events.subList(m.events.size() - MAX_EVENTS, m.events.size()));
        }
        save(m);
    }

    /** 事件回访已发送，标记不再提醒 */
    public synchronized void markEventReminded(Caller caller, String text, String date) {
        Memory m = load(caller);
        boolean changed = false;
        for (Event e : m.events) {
            if (e.text.equals(text) && Objects.equals(e.date, date) && !e.reminded) {
                e.reminded = true;
                changed = true;
            }
        }
        if (changed) save(m);
    }

    public synchronized Care addCare(Caller caller, String text, String reason) {
        return addCare(caller, text, reason, "message", null);
    }

    public synchronized Care addCare(Caller caller, String text, String reason,
                                     String type, Map<String, Object> payload) {
        Memory m = load(caller);
        Care c = new Care(text, reason, now());
        c.id = UUID.randomUUID().toString();
        c.type = type == null ? "message" : type;
        c.payload = payload;
        m.care.add(c);
        save(m);
        return c;
    }

    public synchronized void markGreeted(Caller caller) {
        Memory m = load(caller);
        m.lastGreetingDate = LocalDate.now().toString();
        save(m);
    }

    /** 每轮对话结束后记录情绪分数（规则层，零模型成本） */
    public synchronized void recordMood(Caller caller, String userText, Integer riskLevel) {
        if (userText == null || userText.isBlank()) return;
        int pos = POS_KW.stream().anyMatch(userText::contains) ? 1 : 0;
        int neg = NEG_KW.stream().anyMatch(userText::contains) ? 1 : 0;
        int risk = riskLevel == null ? 0 : riskLevel;
        int score = Math.max(-3, Math.min(3, pos - neg - risk));
        Memory m = load(caller);
        m.moodScores.add(new MoodScore(score, now()));
        if (m.moodScores.size() > MAX_MOOD) {
            m.moodScores = new ArrayList<>(m.moodScores.subList(m.moodScores.size() - MAX_MOOD, m.moodScores.size()));
        }
        save(m);
    }

    /** 会话分析结束后回写情绪结论（negative→-2 / neutral→0 / positive→+1） */
    public synchronized void recordSessionAnalysis(Caller caller, String overallMood, String emotionTrend) {
        Memory m = load(caller);
        if (overallMood != null && !overallMood.isBlank()) {
            m.overallMood = overallMood;
            int score = switch (overallMood) {
                case "negative" -> -2;
                case "positive" -> 1;
                default -> 0;
            };
            m.moodScores.add(new MoodScore(score, now()));
            if (m.moodScores.size() > MAX_MOOD) {
                m.moodScores = new ArrayList<>(m.moodScores.subList(m.moodScores.size() - MAX_MOOD, m.moodScores.size()));
            }
        }
        if (emotionTrend != null && !emotionTrend.isBlank()) {
            m.emotionTrend = emotionTrend;
        }
        save(m);
    }

    // ---------- 主动关怀守卫（防重复打扰） ----------

    public synchronized void touchLastMoodCareAt(Caller caller) {
        Memory m = load(caller);
        m.lastMoodCareAt = now();
        save(m);
    }

    public synchronized void touchLastReconnectDate(Caller caller) {
        Memory m = load(caller);
        m.lastReconnectDate = LocalDate.now().toString();
        save(m);
    }

    public synchronized void touchLastStoryDate(Caller caller) {
        Memory m = load(caller);
        m.lastStoryDate = LocalDate.now().toString();
        save(m);
    }

    /** 删除某用户的记忆档案（评测清理用） */
    public synchronized void deleteUser(String id) {
        try {
            Files.deleteIfExists(fileOf(id));
        } catch (IOException e) {
            log.warn("删除用户记忆失败：{}", id, e);
        }
    }

    /**
     * 列出未送达的主动关怀（只读，不标记；送达确认走 ackCare）。
     * 旧数据没有 id：读取时合成，保证前端可以去重。
     */
    public synchronized List<Care> pendingCare(Caller caller) {
        Memory m = load(caller);
        List<Care> pending = m.care.stream().filter(c -> !c.delivered).toList();
        if (pending.isEmpty()) return List.of();
        boolean changed = false;
        for (int i = 0; i < pending.size(); i++) {
            Care c = pending.get(i);
            if (c.id == null || c.id.isBlank()) {
                c.id = "legacy-" + i + "-" + (c.at == null ? "0" : c.at);
                changed = true;
            }
        }
        if (changed) save(m);
        return pending;
    }

    /** 前端确认收到后标记送达（幂等） */
    public synchronized void ackCare(Caller caller, List<String> ids) {
        if (ids == null || ids.isEmpty()) return;
        Memory m = load(caller);
        Set<String> wanted = Set.copyOf(ids);
        boolean changed = false;
        for (Care c : m.care) {
            if (!c.delivered && c.id != null && wanted.contains(c.id)) {
                c.delivered = true;
                changed = true;
            }
        }
        if (changed) save(m);
    }

    // ---------- 读取 ----------

    /**
     * 每积累几轮对话就抽取一次"值得长期记住的事实"。
     * 只有当用户发言数达到 3 的倍数、且这一批还没抽过时才触发。
     */
    public void maybeExtractFacts(Caller caller) {
        Memory m = load(caller);
        long userTurns = m.turns == null ? 0 : m.turns.stream()
                .filter(t -> "user".equals(t.speaker)).count();
        if (userTurns == 0 || userTurns % 3 != 0) return;
        String marker = String.valueOf(userTurns);
        if (marker.equals(m.lastExtractAtTurn)) return;
        m.lastExtractAtTurn = marker;
        save(m);
        extractor.submit(() -> extractFacts(caller));
    }

    private void extractFacts(Caller caller) {
        try {
            Memory m = load(caller);
            List<Turn> recent = m.turns.stream().skip(Math.max(0, m.turns.size() - 6)).toList();
            if (recent.isEmpty()) return;

            StringBuilder dialog = new StringBuilder();
            recent.forEach(t -> dialog.append("user".equals(t.speaker) ? "用户：" : "助手：")
                    .append(abbreviate(t.content, 120)).append('\n'));

            String knownFacts = m.facts == null || m.facts.isEmpty() ? "（暂无）"
                    : m.facts.stream().map(f -> "- " + f.text).reduce((a, b) -> a + "\n" + b).orElse("（暂无）");
            String knownEvents = m.events == null || m.events.isEmpty() ? "（暂无）"
                    : m.events.stream().map(e -> "- " + e.text + (e.date == null ? "" : "（" + e.date + "）"))
                    .reduce((a, b) -> a + "\n" + b).orElse("（暂无）");

            LocalDate today = LocalDate.now();
            String weekday = String.valueOf("一二三四五六日".charAt(today.getDayOfWeek().getValue() - 1));

            String system = "你是信息抽取器。从对话里抽取两类信息，只输出一个 JSON 对象，不要输出任何其他内容：\n"
                    + "{\"facts\": [\"事实1\", \"事实2\"], \"events\": [{\"text\": \"事情\", \"date\": \"yyyy-MM-dd\"}]}\n\n"
                    + "今天是 " + today + "（星期" + weekday + "）。\n\n"
                    + "facts：值得长期记住的、关于这位来访者的事实（家人与称呼、健康状况、生活习惯、在意的事）。"
                    + "最多 2 条，每条不超过 20 个字，只写事实，不写评价，不与已有事实重复。没有就输出空数组。\n\n"
                    + "events：对话里提到的、未来会发生的具体事情（考试、复查、比赛、生日、旅行、家人来访、预约等）。"
                    + "text 用简短中文（不超过 20 字）；date 必须换算成 yyyy-MM-dd 格式的具体日期（今天是 " + today + "）。"
                    + "只有给出了明确日期或明确时间关系（如\"下周五\"\"9月20号\"）的才抽取；\"以后\"\"有空时\"\"哪天\"这类模糊说法不要抽。"
                    + "没有就输出空数组。";
            String user = "已有事实：\n" + knownFacts + "\n已有安排：\n" + knownEvents + "\n\n最近的对话：\n" + dialog;

            String out = chatModel.call(new Prompt(List.of(
                    new SystemMessage(system), new UserMessage(user)))).getResult().getOutput().getText();
            if (out == null || out.isBlank()) return;

            if (!parseJsonExtraction(caller, out, today)) {
                // JSON 解析失败：回退到原来的行式事实解析（只抽 facts，不抽 events），保证不崩溃
                fallbackLineFacts(caller, out);
            }
            log.info("已为 {} 抽取记忆事实与安排", caller.name());
        } catch (Exception e) {
            log.warn("抽取记忆事实失败：{}", e.getMessage());
        }
    }

    /** 解析 JSON 抽取结果；解析成功返回 true */
    private boolean parseJsonExtraction(Caller caller, String out, LocalDate today) {
        try {
            String json = out.trim()
                    .replaceFirst("^```(?:json)?\\s*", "")
                    .replaceFirst("\\s*```$", "");
            int start = json.indexOf('{');
            int end = json.lastIndexOf('}');
            if (start < 0 || end <= start) return false;
            JsonNode root = mapper.readTree(json.substring(start, end + 1));
            if (root == null || !root.isObject()) return false;

            JsonNode facts = root.get("facts");
            if (facts != null && facts.isArray()) {
                for (JsonNode f : facts) {
                    String fact = cleanFactLine(f.asText());
                    if (fact != null) addFact(caller, fact);
                }
            }
            JsonNode events = root.get("events");
            if (events != null && events.isArray()) {
                for (JsonNode ev : events) {
                    String text = cleanShortText(ev.get("text"));
                    if (text == null) continue;
                    JsonNode dateNode = ev.get("date");
                    if (dateNode == null || dateNode.isNull()) continue;
                    String date = dateNode.asText();
                    if (date == null || date.isBlank()) continue;
                    try {
                        LocalDate d = LocalDate.parse(date.trim());
                        if (d.isBefore(today.minusDays(1)) || d.isAfter(today.plusDays(365))) continue;
                        addEvent(caller, text, d.toString());
                    } catch (Exception ignored) {
                        // 日期非法（如 LLM 输出"下周五"）：跳过，不存储
                    }
                }
            }
            return true;
        } catch (Exception e) {
            log.warn("JSON 抽取结果解析失败，回退行式解析：{}", e.getMessage());
            return false;
        }
    }

    /** 行式兜底：把输出按行清洗为事实 */
    private void fallbackLineFacts(Caller caller, String out) {
        for (String line : out.split("\n")) {
            String fact = cleanFactLine(line);
            if (fact != null) addFact(caller, fact);
        }
    }

    /** 行清洗：去掉编号/符号，过滤空行与占位词 */
    private static String cleanFactLine(String raw) {
        if (raw == null) return null;
        String fact = raw.replaceAll("^[-*\\d.、)\\s]+", "").trim();
        if (fact.isEmpty() || "无".equals(fact) || fact.length() > 40) return null;
        return fact;
    }

    /** 事件文本清洗：去空白 + 20 字截断 */
    private static String cleanShortText(JsonNode node) {
        if (node == null || node.isNull()) return null;
        String t = node.asText().replaceAll("\\s+", " ").trim();
        if (t.isEmpty() || "无".equals(t)) return null;
        return t.length() <= 20 ? t : t.substring(0, 20) + "…";
    }

    /** 给提示词用的记忆片段：关于这个人的事实 + 近期安排 + 最近说过的话 */
    public String promptContext(Caller caller) {
        Memory m = load(caller);
        StringBuilder sb = new StringBuilder();
        if (m.facts != null && !m.facts.isEmpty()) {
            sb.append("你记得关于这位来访者的事：\n");
            m.facts.stream().skip(Math.max(0, m.facts.size() - 10))
                    .forEach(f -> sb.append("- ").append(f.text).append('\n'));
        }
        if (m.events != null && !m.events.isEmpty()) {
            List<Event> upcoming = m.events.stream()
                    .filter(e -> e.date != null && !e.reminded
                            && e.date.compareTo(LocalDate.now().toString()) >= 0)
                    .sorted(Comparator.comparing((Event e) -> e.date))
                    .limit(5)
                    .toList();
            if (!upcoming.isEmpty()) {
                sb.append("他提过的近期安排：\n");
                upcoming.forEach(e -> sb.append("- ").append(prettyDate(e.date)).append(" ").append(e.text).append('\n'));
            }
        }
        List<Turn> userTurns = m.turns == null ? List.of()
                : m.turns.stream().filter(t -> "user".equals(t.speaker)).toList();
        if (!userTurns.isEmpty()) {
            sb.append("他之前说过的话（最近的）：\n");
            userTurns.stream().skip(Math.max(0, userTurns.size() - MEMORY_TURNS_IN_PROMPT))
                    .forEach(t -> sb.append("- ").append(abbreviate(t.content, 60)).append('\n'));
        }
        if (sb.isEmpty()) return null;
        return sb.append("（自然地用上这些记忆，不要生硬复述，也不要声称「我记得一切」；"
                + "如果对方提到的事已经过去很久，先关心近况。）").toString();
    }

    /**
     * 语气指令：最近 3 轮情绪均值 <= -1 且最新记录在 3 天内时返回；
     * 由 RagService 拼进系统提示词，让本轮回答更软更暖。
     */
    public String toneDirective(Caller caller) {
        Memory m = load(caller);
        if (m.moodScores == null || m.moodScores.size() < 3) return null;
        List<MoodScore> last3 = m.moodScores.subList(m.moodScores.size() - 3, m.moodScores.size());
        double avg = last3.stream().mapToInt(s -> s.score).average().orElse(0);
        if (avg > -1.0) return null;
        try {
            LocalDateTime t = LocalDateTime.parse(last3.get(last3.size() - 1).at, FMT);
            if (Duration.between(t, LocalDateTime.now()).toDays() > 3) return null;
        } catch (Exception e) {
            return null;
        }
        return TONE_DIRECTIVE;
    }

    private static String prettyDate(String iso) {
        try {
            LocalDate d = LocalDate.parse(iso);
            return d.getMonthValue() + "月" + d.getDayOfMonth() + "日";
        } catch (Exception e) {
            return iso;
        }
    }

    public List<String> allUserIds() {
        if (!Files.exists(root)) return List.of();
        try (Stream<Path> s = Files.list(root)) {
            return s.filter(p -> p.getFileName().toString().endsWith(".json"))
                    .map(p -> p.getFileName().toString().replace(".json", ""))
                    .toList();
        } catch (IOException e) {
            return List.of();
        }
    }

    /** 把磁盘上的 id 还原成可用的 Caller */
    public Caller callerById(String id) {
        Memory m = load(new Caller(id, null, null));
        return new Caller(id, m.name == null ? "你" : m.name, m.role == null ? "elder" : m.role);
    }

    public Map<String, Object> summary(Caller caller) {
        Memory m = load(caller);
        List<Map<String, Object>> events = new ArrayList<>();
        if (m.events != null) {
            m.events.stream()
                    .sorted(Comparator.comparing((Event e) -> e.date == null ? "9999" : e.date))
                    .forEach(e -> {
                        Map<String, Object> item = new java.util.LinkedHashMap<>();
                        item.put("text", e.text == null ? "" : e.text);
                        item.put("date", e.date == null ? "" : e.date);
                        item.put("reminded", e.reminded);
                        events.add(item);
                    });
        }
        List<Integer> mood = m.moodScores == null || m.moodScores.isEmpty() ? List.of()
                : m.moodScores.stream().skip(Math.max(0, m.moodScores.size() - 3))
                        .map(s -> s.score).toList();
        return Map.of(
                "name", m.name == null ? "" : m.name,
                "since", m.firstSeen == null ? "" : m.firstSeen,
                "facts", m.facts == null ? List.of() : m.facts.stream()
                        .sorted(Comparator.comparing((Fact f) -> f.at).reversed())
                        .limit(10).map(f -> f.text).toList(),
                "events", events,
                "mood", mood,
                "turnCount", m.turns == null ? 0 : m.turns.size());
    }

    private static String abbreviate(String s, int max) {
        if (s == null) return "";
        String one = s.replaceAll("\\s+", " ").trim();
        return one.length() <= max ? one : one.substring(0, max) + "…";
    }
}
