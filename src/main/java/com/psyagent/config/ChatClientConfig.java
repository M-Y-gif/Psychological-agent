package com.psyagent.config;

import com.psyagent.tool.PsychologyTools;
import com.psyagent.tool.WarningTools;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ChatClientConfig {

    @Bean
    public ChatClient chatClient(ChatModel chatModel, PsychologyTools psychologyTools, WarningTools warningTools) {
        // 注册全部 Agent 工具：
        //  - psychologyTools：检索知识库、风险评估（第二步）
        //  - warningTools：发预警邮件、写 Excel 留痕（第三步，同时通过 MCP 暴露）
        return ChatClient.builder(chatModel)
                .defaultTools(psychologyTools)
                .defaultTools(warningTools)
                .build();
    }
}
