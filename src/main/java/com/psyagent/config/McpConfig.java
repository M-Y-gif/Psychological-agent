package com.psyagent.config;

import com.psyagent.tool.WarningTools;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * MCP 服务端工具注册：把外部能力（邮件、Excel）封装为 MCP 工具。
 * Spring AI 自动把该 ToolCallbackProvider 转换为 MCP SyncToolSpecification，
 * 并通过 WebMVC 传输在 /mcp 端点对外提供服务（type=SYNC）。
 */
@Configuration
public class McpConfig {

    @Bean
    public ToolCallbackProvider psyWarningToolsProvider(WarningTools warningTools) {
        return MethodToolCallbackProvider.builder().toolObjects(warningTools).build();
    }
}
