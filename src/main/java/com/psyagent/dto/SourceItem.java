package com.psyagent.dto;

/**
 * 检索命中的知识片段，用于回答溯源与调试。
 */
public record SourceItem(String source, String snippet, double score) {
}
