package com.psyagent.dto;

import java.util.List;

/**
 * 会话心理分析请求：turns 为完整对话（含每轮情绪标签），可选带入对话过程中的风险信息。
 */
public record SessionAnalysisRequest(List<SessionTurn> turns, Integer preRiskLevel, String preRiskReason) {

    public record SessionTurn(String role, String content, String emotion) {
    }
}
