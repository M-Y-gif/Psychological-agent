package com.psyagent.dto;

/**
 * question: 用户文本；emotionContext: 多模态情绪特征（JSON 对象或 JSON 字符串均可）
 */
public record ChatRequest(String question, Object emotionContext) {
}
