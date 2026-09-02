package com.psyagent.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 第三步：预警工具配置（前缀 psy.warning）。
 */
@ConfigurationProperties(prefix = "psy.warning")
public record WarningProperties(
        boolean mailEnabled,
        String mailTo,
        String mailOutboxDir,
        String excelPath) {
}
