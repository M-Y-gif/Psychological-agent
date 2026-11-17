package com.psyagent.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.psyagent.config.PersonaProperties;
import com.psyagent.config.RagProperties;
import com.psyagent.dto.Caller;
import com.psyagent.dto.ChatRequest;
import com.psyagent.dto.ChatResponse;
import com.psyagent.dto.SourceItem;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

import reactor.core.publisher.Flux;

/**
 * 第二步：Agentic 问答闭环。
 * 用户提问 -> Agent 自主决策（调用 search_psychology_kb / evaluate_risk_level）-> 大模型生成回答。
 */
@Service
public class RagService {

    private final ChatClient chatClient;
    private final VectorStore vectorStore;
    private final RagProperties props;
    private final ObjectMapper objectMapper;
    private final MemoryService memory;
    private final PersonaProperties personas;

    public RagService(ChatClient chatClient, VectorStore vectorStore, RagProperties props,
                      ObjectMapper objectMapper, MemoryService memory, PersonaProperties personas) {
        this.chatClient = chatClient;
        this.vectorStore = vectorStore;
        this.props = props;
        this.objectMapper = objectMapper;
        this.memory = memory;
        this.personas = personas;
    }

    public ChatResponse answer(String question, Object emotionContext) {
        return answer(question, emotionContext, null, Caller.anonymous());
    }

    public ChatResponse answer(String question, Object emotionContext,
                               List<ChatRequest.ChatTurn> history, Caller caller) {
        ToolCallContext context = new ToolCallContext();
        String answer = buildPrompt(question, emotionContext, history, context, caller).call().content();
        return new ChatResponse(answer, context.getSources(), context.getRiskLevel(), context.getRiskReason());
    }

    /**
     * 流式回答：逐段吐出模型生成的文本。
     * 工具调用同样会执行（Spring AI 在流式路径下也会跑 ToolCallingManager），
     * 检索结果与风险等级会写进传入的 context，调用方在流结束后读取即可。
     */
    public Flux<String> streamAnswer(String question, Object emotionContext,
                                     List<ChatRequest.ChatTurn> history, ToolCallContext context, Caller caller) {
        return buildPrompt(question, emotionContext, history, context, caller).stream().content();
    }

    /**
     * 组装提示词：基础系统提示 -> 人格块（按角色）-> 长期记忆 -> 语气指令 -> 多模态情绪线索 -> 历史轮次 -> 本轮上下文。
     * 安全要求（高风险例外）放在基础提示词里、位置靠前，人格块不得与之冲突。
     */
    private ChatClient.ChatClientRequestSpec buildPrompt(String question, Object emotionContext,
                                              List<ChatRequest.ChatTurn> history, ToolCallContext context,
                                              Caller caller) {
        String systemPrompt = props.systemPrompt();
        // 人格：按使用者角色切换口吻（晚晴/小暖/家属）
        PersonaProperties.Persona persona = personas.personaFor(caller.role());
        if (persona != null && persona.system() != null && !persona.system().isBlank()) {
            systemPrompt += "\n\n" + persona.system();
        }
        // 长期记忆：让这次回答能接上"上次说过的话"（按当前问题检索式选择）
        String remembered = memory.promptContext(caller, question);
        if (remembered != null) {
            systemPrompt += "\n\n【关于这位来访者，你记得的事】\n" + remembered;
        }
        // 语气指令：情绪持续偏低时，本轮回答更软更暖
        String tone = memory.toneDirective(caller);
        if (tone != null) {
            systemPrompt += "\n\n" + tone;
        }
        String emotionCtx = normalizeEmotionContext(emotionContext);
        if (emotionCtx != null) {
            systemPrompt += "\n\n【多模态情绪线索】" + emotionCtx
                    + "\n（请结合文本内容与情绪线索进行综合研判，但不要被情绪线索误导，以用户安全为先。）";
        }
        ChatClient.ChatClientRequestSpec prompt = chatClient.prompt().system(systemPrompt);
        if (history != null && !history.isEmpty()) {
            List<Message> messages = history.stream()
                    .map(t -> "user".equals(t.role())
                            ? (Message) new UserMessage(t.content())
                            : new AssistantMessage(t.content()))
                    .toList();
            prompt = prompt.messages(messages);
        }
        return prompt.user(question).toolContext(Map.of(ToolCallContext.KEY, context));
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
