package com.psyagent.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.stereotype.Service;

import java.util.Set;

/**
 * 心理风险判定器：规则层 + 语义层（LLM）混合，最终取两者较大值。
 * 被 Agent 工具 evaluate_risk_level 与评测模块共用，保证线上行为与评测一致。
 */
@Service
public class RiskEvaluator {

    private static final Logger log = LoggerFactory.getLogger(RiskEvaluator.class);

    /** 高风险关键词（自伤/自杀倾向） */
    public static final Set<String> HIGH_RISK_KEYWORDS = Set.of(
            "自杀", "自伤", "想死", "不想活", "活不下去", "结束生命", "结束自己",
            "伤害自己", "割腕", "跳楼", "安眠药", "遗书", "告别", "活着没意思",
            "消失", "解脱", "自我了断", "不想醒来", "没意义了");

    /** 中风险关键词（强烈负面情绪） */
    public static final Set<String> MODERATE_RISK_KEYWORDS = Set.of(
            "绝望", "崩溃", "撑不下去", "撑不住", "受不了", "毫无希望", "没有希望",
            "无意义", "空虚", "无助", "痛苦");

    /** 评测结果 */
    public record RiskResult(int level, String reason, int ruleLevel, int llmLevel, String llmReason) {
    }

    private final ChatClient riskChatClient;
    private final ObjectMapper objectMapper;

    public RiskEvaluator(ChatModel chatModel, ObjectMapper objectMapper) {
        // 独立 ChatClient（不带工具，避免递归调用）
        this.riskChatClient = ChatClient.builder(chatModel).build();
        this.objectMapper = objectMapper;
    }

    public RiskResult evaluate(String message) {
        return evaluate(message, null);
    }

    /**
     * 综合研判：文本 + 可选的多模态情绪特征（语速、停顿、表情等）。
     */
    public RiskResult evaluate(String message, String emotionContext) {
        String text = message == null ? "" : message;
        int ruleLevel = ruleScore(text);
        String llmJson = llmScore(text, emotionContext);
        int llmLevel = parseRiskLevel(llmJson);
        int finalLevel = Math.max(ruleLevel, llmLevel);
        String reason = buildReason(ruleLevel, llmJson);
        return new RiskResult(finalLevel, reason, ruleLevel, llmLevel, extractReason(llmJson));
    }

    /** 仅规则层（评测对照组用） */
    public RiskResult evaluateRuleOnly(String message) {
        int ruleLevel = ruleScore(message == null ? "" : message);
        return new RiskResult(ruleLevel, "规则：" + ruleText(ruleLevel), ruleLevel, 0, "");
    }

    private int ruleScore(String text) {
        int high = countMatches(text, HIGH_RISK_KEYWORDS);
        int moderate = countMatches(text, MODERATE_RISK_KEYWORDS);
        if (high >= 2) return 3;
        if (high == 1) return 2;
        if (moderate >= 2) return 2;
        if (moderate == 1) return 1;
        return 0;
    }

    private static int countMatches(String text, Set<String> keywords) {
        int count = 0;
        for (String kw : keywords) {
            if (text.contains(kw)) {
                count++;
            }
        }
        return count;
    }

    private String llmScore(String userMessage, String emotionContext) {
        String emotionHint = (emotionContext != null && !emotionContext.isBlank())
                ? "\n额外多模态情绪线索：" + emotionContext
                + "（语速快/停顿多可能提示焦虑，表情消极/皱眉可能提示情绪低落，请作为辅助信号参考）"
                : "";
        String prompt = """
                请评估下面用户消息的自伤/自杀风险等级，只输出 JSON：{"riskLevel": 0-3, "reasons": "简短中文理由"}。
                0=无明显风险；1=轻度情绪困扰；2=中高风险；3=极高风险（有明确自伤/自杀意图或计划）。
                用户消息：%s%s
                """.formatted(userMessage, emotionHint);
        try {
            return riskChatClient.prompt()
                    .system("你是心理风险筛查助手，只输出 JSON，不要输出其他内容。")
                    .user(prompt)
                    .call()
                    .content();
        } catch (Exception e) {
            log.warn("LLM 风险判定失败，使用规则判定：{}", e.getMessage());
            return "";
        }
    }

    private int parseRiskLevel(String json) {
        JsonNode node = parseJson(json);
        if (node == null) return 0;
        int level = node.path("riskLevel").asInt(0);
        return Math.max(0, Math.min(3, level));
    }

    private String extractReason(String json) {
        JsonNode node = parseJson(json);
        return (node != null && node.hasNonNull("reasons")) ? node.path("reasons").asText() : "";
    }

    private String buildReason(int ruleLevel, String llmJson) {
        String llmReason = extractReason(llmJson);
        return "规则：" + ruleText(ruleLevel) + "；语义分析：" + (llmReason.isEmpty() ? "未获得" : llmReason);
    }

    private static String ruleText(int ruleLevel) {
        return switch (ruleLevel) {
            case 3 -> "命中多项自伤/自杀类关键词";
            case 2 -> "命中高危或多项负面情绪关键词";
            case 1 -> "命中轻度负面情绪关键词";
            default -> "未命中风险关键词";
        };
    }

    /** 解析大模型返回的 JSON（兼容 ```json 代码块包裹） */
    private JsonNode parseJson(String json) {
        if (json == null || json.isBlank()) return null;
        try {
            String cleaned = json.replaceAll("```json|```", "").trim();
            int start = cleaned.indexOf('{');
            int end = cleaned.lastIndexOf('}');
            if (start >= 0 && end > start) {
                cleaned = cleaned.substring(start, end + 1);
            }
            return objectMapper.readTree(cleaned);
        } catch (Exception e) {
            log.warn("解析风险判定 JSON 失败：{}", e.getMessage());
            return null;
        }
    }
}
