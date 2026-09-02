package com.psyagent.dto;

import java.util.List;

/**
 * 会话心理分析结果。
 * overallMood: negative(负面) / positive(正面) / neutral(中性)
 * feedback: 负面情绪 -> 鼓励与安慰；正面情绪 -> 同乐与鼓励。
 */
public record SessionAnalysisResponse(
        String emotionTrend,
        List<String> mainIssues,
        String overallMood,
        int riskLevel,
        String riskReason,
        String feedback,
        List<String> suggestions) {
}
