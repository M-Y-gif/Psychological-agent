package com.psyagent.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.psyagent.dto.Caller;
import com.psyagent.dto.SessionAnalysisRequest;
import com.psyagent.dto.SessionAnalysisResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/**
 * 会话心理分析：对话结束后，基于完整对话记录（含每轮情绪特征）生成心理分析报告。
 * - 负面情绪 -> 鼓励与安慰
 * - 正面情绪 -> 同乐与鼓励
 * 若整体风险较高，自动触发预警留痕（Excel / 邮件）。
 */
@Service
public class SessionAnalysisService {

    private static final Logger log = LoggerFactory.getLogger(SessionAnalysisService.class);

    private static final Set<String> NEGATIVE_KEYWORDS = Set.of(
            "难过", "痛苦", "绝望", "焦虑", "崩溃", "压抑", "想哭", "孤独", "累", "失眠", "无助");
    private static final Set<String> POSITIVE_KEYWORDS = Set.of(
            "开心", "高兴", "好多了", "放松", "轻松", "感谢", "谢谢", "进步", "舒服", "愉快", "棒", "不错");

    private final ChatClient analysisChatClient;
    private final ObjectMapper objectMapper;
    private final RiskRecordExcelService excelService;
    private final WarningEmailService emailService;
    private final MemoryService memoryService;

    public SessionAnalysisService(ChatModel chatModel, ObjectMapper objectMapper,
                                  RiskRecordExcelService excelService, WarningEmailService emailService,
                                  MemoryService memoryService) {
        this.analysisChatClient = ChatClient.builder(chatModel).build();
        this.objectMapper = objectMapper;
        this.excelService = excelService;
        this.emailService = emailService;
        this.memoryService = memoryService;
    }

    public SessionAnalysisResponse analyze(SessionAnalysisRequest request) {
        return analyze(request, Caller.anonymous());
    }

    /** 带使用者身份的分析：情绪结论回写长期记忆（供语气调整与主动关怀使用） */
    public SessionAnalysisResponse analyze(SessionAnalysisRequest request, Caller caller) {
        String transcript = buildTranscript(request);
        String prompt = """
                你是资深心理咨询师，请对以下"用户与心理助手"的完整对话进行心理分析，只输出 JSON，不要输出其他内容：
                {
                  "emotionTrend": "用户情绪的变化轨迹，一句话概括",
                  "mainIssues": ["主要议题1", "主要议题2"],
                  "overallMood": "negative 或 positive 或 neutral",
                  "riskLevel": 0到3的整数,
                  "riskReason": "风险判定依据",
                  "feedback": "给用户的反馈话。若整体情绪负面：真诚地鼓励与安慰，表达理解和陪伴；若正面：同乐并鼓励继续保持",
                  "suggestions": ["实用建议1", "实用建议2"]
                }
                对话记录（角色：内容（情绪标签））：
                %s
                """.formatted(transcript);

        String json;
        try {
            json = analysisChatClient.prompt()
                    .system("你是资深心理咨询师，只输出 JSON，不要输出其他内容。")
                    .user(prompt)
                    .call()
                    .content();
        } catch (Exception e) {
            log.warn("会话分析调用失败，使用规则兜底：{}", e.getMessage());
            json = null;
        }

        SessionAnalysisResponse response = parse(json, request);
        // 情绪结论回写长期记忆（失败不影响报告返回）
        try {
            memoryService.recordSessionAnalysis(caller, response.overallMood(), response.emotionTrend());
        } catch (Exception e) {
            log.warn("回写情绪结论到记忆失败：{}", e.getMessage());
        }
        // 高风险自动预警留痕
        if (response.riskLevel() >= 2) {
            excelService.appendRiskRecord(response.riskLevel(),
                    "会话分析：" + response.riskReason() + "；情绪趋势：" + response.emotionTrend(),
                    transcript.length() > 200 ? transcript.substring(0, 200) + "…" : transcript);
            emailService.sendWarning("心理危机预警：视频会话用户整体风险 " + response.riskLevel() + " 级",
                    "用户在一次视频会话后整体评估风险等级为 " + response.riskLevel()
                            + " 级（" + response.riskReason() + "）。请尽快关注并联系该用户。\n\n情绪趋势：" + response.emotionTrend());
        } else if (response.riskLevel() >= 1) {
            excelService.appendRiskRecord(response.riskLevel(), "会话分析：" + response.riskReason(), transcript);
        }
        return response;
    }

    private String buildTranscript(SessionAnalysisRequest request) {
        StringBuilder sb = new StringBuilder();
        List<SessionAnalysisRequest.SessionTurn> turns = request.turns();
        if (turns != null) {
            for (SessionAnalysisRequest.SessionTurn t : turns) {
                String role = "user".equalsIgnoreCase(t.role()) ? "用户" : "助手";
                sb.append(role).append("：").append(t.content() == null ? "" : t.content());
                if (t.emotion() != null && !t.emotion().isBlank()) {
                    sb.append("（情绪：").append(t.emotion()).append("）");
                }
                sb.append("\n");
            }
        }
        return sb.toString();
    }

    private SessionAnalysisResponse parse(String json, SessionAnalysisRequest request) {
        JsonNode node = null;
        if (json != null && !json.isBlank()) {
            try {
                String cleaned = json.replaceAll("```json|```", "").trim();
                int start = cleaned.indexOf('{');
                int end = cleaned.lastIndexOf('}');
                if (start >= 0 && end > start) {
                    cleaned = cleaned.substring(start, end + 1);
                }
                node = objectMapper.readTree(cleaned);
            } catch (Exception e) {
                log.warn("解析会话分析 JSON 失败：{}", e.getMessage());
            }
        }
        if (node != null) {
            String mood = node.path("overallMood").asText("neutral");
            if (!Set.of("negative", "positive", "neutral").contains(mood)) {
                mood = "neutral";
            }
            int risk = Math.max(0, Math.min(3, node.path("riskLevel").asInt(0)));
            return new SessionAnalysisResponse(
                    node.path("emotionTrend").asText(""),
                    toStringList(node.path("mainIssues")),
                    mood,
                    risk,
                    node.path("riskReason").asText(""),
                    node.path("feedback").asText(fallbackFeedback(mood)),
                    toStringList(node.path("suggestions")));
        }
        // 规则兜底
        String mood = ruleMood(request);
        int risk = request.preRiskLevel() == null ? 0 : request.preRiskLevel();
        String trend = "对话中用户情绪整体表现为" + mood;
        return new SessionAnalysisResponse(trend, List.of(), mood, risk,
                request.preRiskReason() == null ? "规则兜底判定" : request.preRiskReason(),
                fallbackFeedback(mood), List.of());
    }

    private String ruleMood(SessionAnalysisRequest request) {
        if (request.turns() == null || request.turns().isEmpty()) {
            return "neutral";
        }
        int neg = 0;
        int pos = 0;
        for (SessionAnalysisRequest.SessionTurn t : request.turns()) {
            String text = t.content() == null ? "" : t.content();
            for (String kw : NEGATIVE_KEYWORDS) {
                if (text.contains(kw)) {
                    neg++;
                    break;
                }
            }
            for (String kw : POSITIVE_KEYWORDS) {
                if (text.contains(kw)) {
                    pos++;
                    break;
                }
            }
        }
        return neg > pos ? "negative" : (pos > neg ? "positive" : "neutral");
    }

    private String fallbackFeedback(String mood) {
        return switch (mood) {
            case "negative" -> "我看到了你今天的不容易，谢谢你愿意把这些说出来。你的感受是真实且重要的，请给自己一点温柔和耐心，你并不孤单。如果需要，随时可以继续来找我，也可以拨打心理援助热线 12356 寻求专业支持。";
            case "positive" -> "真为你高兴！看到你状态不错，我也跟着开心起来。请记得把这份积极的感觉收藏起来，继续好好照顾自己，我一直在你身边。";
            default -> "感谢你今天愿意和我聊这些，希望这次对话对你有帮助。记得照顾好自己的身心，随时欢迎再来。";
        };
    }

    private List<String> toStringList(JsonNode arr) {
        List<String> list = new ArrayList<>();
        if (arr != null && arr.isArray()) {
            arr.forEach(n -> {
                String v = n.asText("");
                if (!v.isBlank()) {
                    list.add(v);
                }
            });
        }
        return list;
    }
}
