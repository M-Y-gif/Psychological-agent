package com.psyagent.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.psyagent.config.RagProperties;
import com.psyagent.dto.ChatResponse;
import com.psyagent.dto.SourceItem;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 第二步：Agentic 问答闭环。
 * 用户提问 -> Agent 自主决策（调用 search_psychology_kb / evaluate_risk_level）-> 大模型生成回答。
 */
@Service
public class RagService {

    private final ChatClient chatClient;
    private final VectorStore vectorStore;
    private final RagProperties props;
    private final ToolCallContext context;
    private final ObjectMapper objectMapper;

    public RagService(ChatClient chatClient, VectorStore vectorStore, RagProperties props,
                      ToolCallContext context, ObjectMapper objectMapper) {
        this.chatClient = chatClient;
        this.vectorStore = vectorStore;
        this.props = props;
        this.context = context;
        this.objectMapper = objectMapper;
    }

    public ChatResponse answer(String question, Object emotionContext) {
        context.clear();
        String systemPrompt = props.systemPrompt();
        String emotionCtx = normalizeEmotionContext(emotionContext);
        if (emotionCtx != null) {
            systemPrompt += "\n\n【多模态情绪线索】" + emotionCtx
                    + "\n（请结合文本内容与情绪线索进行综合研判，但不要被情绪线索误导，以用户安全为先。）";
        }
        String answer = chatClient.prompt()
                .system(systemPrompt)
                .user(question)
                .call()
                .content();
        return new ChatResponse(answer, context.getSources(), context.getRiskLevel(), context.getRiskReason());
    }

    /** 把多模态情绪特征规范化为字符串（兼容 JSON 对象 / JSON 字符串 / null） */
    private String normalizeEmotionContext(Object emotionContext) {
        if (emotionContext == null) {
            return null;
        }
        if (emotionContext instanceof String s) {
            return s.isBlank() ? null : s;
        }
        try {
            return objectMapper.writeValueAsString(emotionContext);
        } catch (Exception e) {
            return emotionContext.toString();
        }
    }

    /** 只做检索，不生成回答（调试/评测用，不走 Agent） */
    public List<SourceItem> retrieve(String question) {
        return vectorStore.similaritySearch(
                        SearchRequest.builder().query(question).topK(props.topK()).build())
                .stream()
                .map(d -> new SourceItem(
                        String.valueOf(d.getMetadata().getOrDefault("source", "unknown")),
                        truncate(d.getText(), 120),
                        d.getScore() == null ? 0.0 : d.getScore()))
                .toList();
    }

    private static String truncate(String s, int max) {
        if (s == null || s.length() <= max) return s;
        return s.substring(0, max) + "…";
    }
}
