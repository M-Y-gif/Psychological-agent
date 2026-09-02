package com.psyagent.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 第一步 RAG 链路相关配置（前缀 psy.rag）。
 */
@ConfigurationProperties(prefix = "psy.rag")
public record RagProperties(
        String docsPath,
        boolean ingestOnStartup,
        int topK,
        int chunkSize,
        int chunkOverlap,
        String systemPrompt) {
}
