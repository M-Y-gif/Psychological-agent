package com.psyagent.dto;

import java.util.List;

/**
 * question: 用户文本；emotionContext: 多模态情绪特征（JSON 对象或字符串）；
 * history: 可选的历史对话（多轮对话记忆），role 为 user/assistant。
 */
public record ChatRequest(String question, Object emotionContext, List<ChatTurn> history) {

    public record ChatTurn(String role, String content) {
    }
}
