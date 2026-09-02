package com.psyagent.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 第四步：多模态感知引擎配置（前缀 psy.multimodal）。
 */
@ConfigurationProperties(prefix = "psy.multimodal")
public record MultimodalProperties(String baseUrl, boolean enabled) {
}
