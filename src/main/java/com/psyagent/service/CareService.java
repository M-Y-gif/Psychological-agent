package com.psyagent.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.psyagent.config.PersonaProperties;
import com.psyagent.dto.Caller;
import com.psyagent.dto.CareItem;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

/**
 * 主动关怀。
 *
 * 设计原则：宁可少说，不要说错。
 *  - 只在明确的节律点开口（早间问候、日程回访、情绪关怀、睡前故事、久未联系），不做随机打扰；
 *  - 每个分支都有"守卫"：守卫只在消息成功生成后才提交，避免 LLM 失败导致事件被跳过或每小时重复；
 *  - 开口必须"具体"——用记忆里的事实说话，而不是"您好，今天感觉怎么样"。
 *
 * 注意：careChatClient 必须是无工具的裸 ChatClient（自带工具会让关怀消息触发预警邮件/留痕）。
 */
@Service
public class CareService {

    private static final Logger log = LoggerFactory.getLogger(CareService.class);
    private static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final int MORNING_FROM = 7;
    private static final int MORNING_TO = 10;
    private static final long QUIET_HOURS = 20;
    private static final int MAX_USERS_PER_TICK = 20;

    private final MemoryService memory;
    private final PersonaProperties personas;
    private final ObjectMapper mapper;
    /** 无工具关怀客户端（生成关怀消息用，绝不能带预警工具） */
    private final ChatClient careChatClient;

    public CareService(MemoryService memory, ChatModel chatModel,
                       PersonaProperties personas, ObjectMapper mapper) {
        this.memory = memory;
        this.personas = personas;
        this.mapper = mapper;
        this.careChatClient = ChatClient.builder(chatModel).build();
    }

    /** 每 30 分钟巡检一次（启动后 1 分钟开始） */
    @Scheduled(fixedDelay = 30 * 60 * 1000L, initialDelay = 60 * 1000L)
    public void tick() {
        try {
            List<String> ids = memory.allUserIds();
            if (ids.size() > MAX_USERS_PER_TICK) {
                log.warn("用户数 {} 超过每轮上限 {}，本轮只巡检前 {} 人",
                        ids.size(), MAX_USERS_PER_TICK, MAX_USERS_PER_TICK);
                ids = ids.subList(0, MAX_USERS_PER_TICK);
            }
            for (String id : ids) {
                Caller caller = memory.callerById(id);
                MemoryService.Memory m = memory.load(caller);
                Decision d = decide(caller, m);
                if (d != null) {
                    memory.addCare(caller, d.text(), d.reason(), d.type(), d.payload());
                    d.commit().run();
                    log.info("为 {} 生成主动关怀（{}）：{}", caller.name(), d.type(), d.text());
                }
            }
        } catch (Exception e) {
            log.warn("主动关怀巡检失败", e);
        }
    }

    /** 一次开口的完整决定：内容 + 类型 + 来源 + 成功后要提交的守卫 */
    private record Decision(String type, String text, Map<String, Object> payload, String reason, Runnable commit) {
    }

    /** 返回本轮该不该开口（null 表示不打扰）；每用户每轮最多一条，分支按顺序取首个命中 */
    private Decision decide(Caller caller, MemoryService.Memory m) {
        String today = LocalDate.now().toString();
        int hour = LocalTime.now().getHour();

        // 1. 早间问候（模板，每日一次）
        boolean morningWindow = hour >= MORNING_FROM && hour < MORNING_TO;
        if (morningWindow && !today.equals(m.lastGreetingDate)) {
            return new Decision("message", morningGreeting(m), null, "定时巡检",
                    () -> memory.markGreeted(caller));
        }
        // 2. 到期事件回访（LLM 生成，失败走模板兜底；排在久未联系之前，避免被通用问候淹没）
        MemoryService.Event due = firstDueEvent(m, today);
        if (due != null && hour >= 8) {
            String text = generateCare(caller, m, eventFollowUpPrompt(caller, m, due, today));
            if (text == null) text = eventFallback(m, due);
            String date = due.date;
            return new Decision("message", text, null, "定时巡检-日程回访",
                    () -> memory.markEventReminded(caller, due.text, date));
        }
        // 3. 低情绪关怀（LLM 生成，最多每 6 小时一次）
        if (hour >= 8 && lowMoodStreak(m) && staleOrNull(m.lastMoodCareAt, 6)) {
            String text = generateCare(caller, m, lowMoodPrompt(caller, m, today));
            if (text != null) {
                return new Decision("breath", text, Map.of("pattern", "4-4-6"), "定时巡检-情绪关怀",
                        () -> memory.touchLastMoodCareAt(caller));
            }
        }
        // 4. 孩子睡前故事（LLM 生成，每日一次，19-21 点）
        if ("child".equals(m.role) && hour >= 19 && hour < 21 && !today.equals(m.lastStoryDate)) {
            String[] story = generateStory(caller, m, today);
            if (story != null) {
                return new Decision("story", story[0] + "\n\n" + story[1],
                        Map.of("title", story[0], "content", story[1]), "定时巡检-睡前故事",
                        () -> memory.touchLastStoryDate(caller));
            }
        }
        // 5. 久未联系（模板，每日最多一次——修掉原来每 30 分钟重复打扰的问题）
        if (m.lastActive != null && idleHours(m.lastActive) >= QUIET_HOURS
                && !today.equals(m.lastReconnectDate)) {
            return new Decision("message", reconnectGreeting(m), null, "定时巡检",
                    () -> memory.touchLastReconnectDate(caller));
        }
        return null;
    }

    /**
     * 演示 / 测试用：立刻触发一条主动关怀（type：message / breath / story）。
     * 注意不假设"很久没联系"，只基于记得的事开口。
     */
    public CareItem triggerNow(Caller caller, String type) {
        String t = type == null || type.isBlank() ? "message" : type;
        MemoryService.Memory m = memory.load(caller);
        String today = LocalDate.now().toString();
        MemoryService.Care c;
        switch (t) {
            case "breath" -> {
                String text = generateCare(caller, m, lowMoodPrompt(caller, m, today));
                if (text == null) {
                    text = "最近心情怎么样？要不要和我一起做一次呼吸练习？吸气 4 秒、屏住 4 秒、慢慢呼气 6 秒。";
                }
                c = memory.addCare(caller, text, "手动触发", "breath", Map.of("pattern", "4-4-6"));
            }
            case "story" -> {
                String[] story = generateStory(caller, m, today);
                if (story != null) {
                    c = memory.addCare(caller, story[0] + "\n\n" + story[1], "手动触发", "story",
                            Map.of("title", story[0], "content", story[1]));
                } else {
                    c = memory.addCare(caller, "今天想听个什么故事呀？我脑子里装了好多故事。", "手动触发", "message", null);
                }
            }
            default -> c = memory.addCare(caller, rememberGreeting(m), "手动触发", "message", null);
        }
        return toItem(c);
    }

    public List<CareItem> pending(Caller caller) {
        return memory.pendingCare(caller).stream().map(CareService::toItem).toList();
    }

    // ---------- 守卫判断 ----------

    private MemoryService.Event firstDueEvent(MemoryService.Memory m, String today) {
        if (m.events == null || m.events.isEmpty()) return null;
        return m.events.stream()
                .filter(e -> e.date != null && !e.reminded && e.date.compareTo(today) <= 0)
                .min(Comparator.comparing((MemoryService.Event e) -> e.date))
                .orElse(null);
    }

    /** 最近 3 轮情绪均值 <= -1 且最新一条在 3 天内 */
    private boolean lowMoodStreak(MemoryService.Memory m) {
        if (m.moodScores == null || m.moodScores.size() < 3) return false;
        List<MemoryService.MoodScore> last3 =
                m.moodScores.subList(m.moodScores.size() - 3, m.moodScores.size());
        double avg = last3.stream().mapToInt(s -> s.score).average().orElse(0);
        if (avg > -1.0) return false;
        try {
            LocalDateTime newest = LocalDateTime.parse(last3.get(last3.size() - 1).at, FMT);
            return Duration.between(newest, LocalDateTime.now()).toDays() <= 3;
        } catch (Exception e) {
            return false;
        }
    }

    private boolean staleOrNull(String ts, int hours) {
        if (ts == null || ts.isBlank()) return true;
        try {
            return Duration.between(LocalDateTime.parse(ts, FMT), LocalDateTime.now()).toHours() >= hours;
        } catch (Exception e) {
            return true;
        }
    }

    // ---------- LLM 生成 ----------

    /** 通用关怀生成：人格设定 + 输出约束；失败返回 null 由调用方兜底 */
    private String generateCare(Caller caller, MemoryService.Memory m, String userPrompt) {
        PersonaProperties.Persona persona = personas.personaFor(caller.role());
        try {
            String system = "你是一个主动关怀助手。下面是你的身份设定，请严格遵循：\n"
                    + (persona == null || persona.system() == null ? "" : persona.system()) + "\n\n"
                    + "你的任务是主动给对方发一条简短消息（不是回复任何问题）。直接输出要发送的消息正文，"
                    + "不要输出任何解释、标题或引号。要求：\n"
                    + "- 2-4 句话，总长 60-120 字，纯口语，禁止 markdown 标记与 emoji。\n"
                    + "- 结合你对用户的了解（记忆事实）说话，不要空泛问候。\n"
                    + "- 不承诺结果，不催促对方，语气按你的身份设定。";
            return careChatClient.prompt().system(system).user(userPrompt).call().content();
        } catch (Exception e) {
            log.warn("关怀生成失败，走模板兜底：{}", e.getMessage());
            return null;
        }
    }

    private String factsText(MemoryService.Memory m) {
        if (m.facts == null || m.facts.isEmpty()) return "（暂无）";
        return m.facts.stream().map(f -> "- " + f.text).reduce((a, b) -> a + "\n" + b).orElse("（暂无）");
    }

    private String userName(MemoryService.Memory m) {
        return m.name == null || m.name.isBlank() ? "对方" : m.name;
    }

    private String eventFollowUpPrompt(Caller caller, MemoryService.Memory m,
                                       MemoryService.Event due, String today) {
        return "今天是 " + today + "。用户：" + userName(m) + "。\n"
                + "你记得的事：\n" + factsText(m) + "\n"
                + "他之前提过的安排里，今天到期或已经过了日期的是：" + due.text + "（" + due.date + "）。\n"
                + "请以你的身份主动发一条消息，自然地提起今天是这件事的日子，关心结果或进展，并给他说话的机会。";
    }

    private String lowMoodPrompt(Caller caller, MemoryService.Memory m, String today) {
        return "今天是 " + today + "。用户：" + userName(m) + "。\n"
                + "最近几轮对话显示他情绪持续偏低。\n"
                + "你记得的事：\n" + factsText(m) + "\n"
                + "请主动发一条消息：\n"
                + "- 先轻轻接住情绪（不说教、不分析），让他知道你在。\n"
                + "- 邀请他做一次简短的呼吸放松：「吸气 4 秒、屏住 4 秒、慢慢呼气 6 秒，做 3 轮」。把邀请说得像提议而不是任务。\n"
                + "- 3-5 句话，总长 80-150 字，纯口语，禁止 markdown 与 emoji。";
    }

    /** 睡前故事：严格 JSON 输出；失败返回 null（不提交守卫，下轮再试） */
    private String[] generateStory(Caller caller, MemoryService.Memory m, String today) {
        try {
            String out = careChatClient.prompt()
                    .system("你是「小暖」，正在给一个孩子讲睡前故事。只输出 JSON，不要输出其他内容："
                            + "{\"title\":\"故事标题（12字以内）\",\"content\":\"故事正文\"}")
                    .user("今天是 " + today + "。你记得这个孩子的事：\n" + factsText(m) + "\n"
                            + "请讲一个 3 分钟能讲完的原创小故事。要求：\n"
                            + "- 温暖、有趣、带一点小冒险；如果能自然用到你记得的事（如孩子喜欢的动物、游戏、家人），就轻轻用上。\n"
                            + "- 语言口语化、适合朗读，句子短。\n"
                            + "- 结尾给孩子一个轻轻的问题（比如「如果是你，你会怎么做呀？」），并把故事收在安心、平静的感觉上——这是睡前故事。\n"
                            + "- 正文 250-400 字。")
                    .call().content();
            if (out == null || out.isBlank()) return null;
            String json = out.trim()
                    .replaceFirst("^```(?:json)?\\s*", "")
                    .replaceFirst("\\s*```$", "");
            int start = json.indexOf('{');
            int end = json.lastIndexOf('}');
            if (start < 0 || end <= start) return null;
            JsonNode root = mapper.readTree(json.substring(start, end + 1));
            String title = root.path("title").asText("").trim();
            String content = root.path("content").asText("").trim();
            if (title.isBlank() || content.isBlank()) return null;
            return new String[]{title, content};
        } catch (Exception e) {
            log.warn("睡前故事生成失败：{}", e.getMessage());
            return null;
        }
    }

    private static CareItem toItem(MemoryService.Care c) {
        return new CareItem(
                c.id, c.text,
                c.reason == null ? "" : c.reason,
                c.at == null ? "" : c.at,
                c.type == null ? "message" : c.type,
                c.payload);
    }

    // ---------- 话术 ----------

    /** 早间问候：优先带上记忆里的具体信息 */
    private String morningGreeting(MemoryService.Memory m) {
        String name = m.name == null || m.name.isBlank() ? "" : m.name;
        String who = name.isEmpty() ? "" : "，" + name;
        String fact = latestFact(m);
        if (fact != null) {
            return "早上好" + who + "。上次你提到" + fact + "，今天好些了吗？";
        }
        return "早上好" + who + "。今天醒得早不早？昨晚睡得还踏实吗？";
    }

    /** 久未联系：先说明"有些日子没聊了"，再留一个轻的口子 */
    private String reconnectGreeting(MemoryService.Memory m) {
        String name = m.name == null || m.name.isBlank() ? "" : m.name;
        String who = name.isEmpty() ? "" : "，" + name;
        String fact = latestFact(m);
        if (fact != null) {
            return "有几天没聊了" + who + "。我还记着你说的" + fact + "，最近怎么样？";
        }
        return "有几天没听到你的消息了" + who + "。最近还顺利吗？想说话的时候我都在。";
    }

    /** 事件回访模板兜底：LLM 失败时保证"还记得"这件事至少说出口 */
    private String eventFallback(MemoryService.Memory m, MemoryService.Event due) {
        String who = m.name == null || m.name.isBlank() ? "" : m.name + "，";
        return who + "今天是" + due.text + "的日子吧？我一直记着呢。结果怎么样，想跟我聊聊吗？";
    }

    /** 基于记忆的关心：不涉及时间假设，随时都能自然地说出口 */
    private String rememberGreeting(MemoryService.Memory m) {
        String name = m.name == null || m.name.isBlank() ? "" : m.name;
        String who = name.isEmpty() ? "" : name + "，";
        String fact = latestFact(m);
        if (fact != null) {
            return who + "我刚想起你提过" + fact + "，今天好些了吗？";
        }
        return who + "今天过得怎么样？有没有什么想说的？";
    }

    private String latestFact(MemoryService.Memory m) {
        if (m.facts == null || m.facts.isEmpty()) return null;
        MemoryService.Fact f = m.facts.get(m.facts.size() - 1);
        return f.text == null || f.text.isBlank() ? null : f.text;
    }

    private long idleHours(String lastActive) {
        try {
            return Duration.between(LocalDateTime.parse(lastActive, FMT), LocalDateTime.now()).toHours();
        } catch (Exception e) {
            return 0;
        }
    }
}
