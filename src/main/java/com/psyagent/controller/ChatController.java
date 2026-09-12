package com.psyagent.controller;

import com.psyagent.dto.ChatRequest;
import com.psyagent.dto.ChatResponse;
import com.psyagent.dto.Caller;
import com.psyagent.dto.SourceItem;
import com.psyagent.service.RagService;
import com.psyagent.service.MemoryService;
import com.psyagent.service.ToolCallContext;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import reactor.core.publisher.Flux;

@RestController
@RequestMapping("/api")
public class ChatController {

    private final RagService ragService;
    private final MemoryService memoryService;

    public ChatController(RagService ragService, MemoryService memoryService) {
        this.ragService = ragService;
        this.memoryService = memoryService;
    }

    /** 用户提问 -> Agent 自主决策（检索/风险评估/预警）-> 大模型生成回答；支持多轮历史与多模态情绪特征 */
    @PostMapping("/chat")
    public ChatResponse chat(@RequestBody ChatRequest request,
                             @RequestHeader(value = "X-User-Id", required = false) String userId,
                             @RequestHeader(value = "X-User-Name", required = false) String userName,
                             @RequestHeader(value = "X-User-Role", required = false) String userRole) {
        Caller caller = Caller.from(userId, userName, userRole);
        memoryService.recordTurn(caller, "user", request.question(), null);
        ChatResponse response = ragService.answer(request.question(), request.emotionContext(),
                request.history(), caller);
        memoryService.recordTurn(caller, "assistant", response.answer(), response.riskLevel());
        memoryService.recordMood(caller, request.question(), response.riskLevel());
        memoryService.maybeExtractFacts(caller);
        return response;
    }

    /**
     * 流式对话（SSE）：边生成边推送。
     * 事件序列：token（增量文本，可多次）-> meta（本次检索来源与风险等级）-> done。
     */
    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<Object>> chatStream(@RequestBody ChatRequest request,
                             @RequestHeader(value = "X-User-Id", required = false) String userId,
                             @RequestHeader(value = "X-User-Name", required = false) String userName,
                             @RequestHeader(value = "X-User-Role", required = false) String userRole) {
        Caller caller = Caller.from(userId, userName, userRole);
        ToolCallContext ctx = new ToolCallContext();
        StringBuilder full = new StringBuilder();
        memoryService.recordTurn(caller, "user", request.question(), null);
        return ragService
                .streamAnswer(request.question(), request.emotionContext(), request.history(), ctx, caller)
                .map(token -> {
                    full.append(token);
                    return ServerSentEvent.<Object>builder(Map.of("t", token)).event("token").build();
                })
                .doOnComplete(() -> {
                    memoryService.recordTurn(caller, "assistant", full.toString(), ctx.getRiskLevel());
                    memoryService.recordMood(caller, request.question(), ctx.getRiskLevel());
                    memoryService.maybeExtractFacts(caller);
                })
                .concatWith(Flux.defer(() -> {
                    Map<String, Object> meta = new LinkedHashMap<>();
                    meta.put("sources", ctx.getSources());
                    meta.put("riskLevel", ctx.getRiskLevel());
                    meta.put("riskReason", ctx.getRiskReason());
                    return Flux.just(
                            ServerSentEvent.<Object>builder(meta).event("meta").build(),
                            ServerSentEvent.<Object>builder(Map.of("ok", true)).event("done").build());
                }))
                .onErrorResume(e -> Flux.just(ServerSentEvent.<Object>builder(
                                Map.of("message", e.getMessage() == null ? "生成失败" : e.getMessage()))
                        .event("error").build()));
    }

    /** 仅检索，返回命中的知识片段（调试/评测用） */
    @GetMapping("/rag/retrieve")
    public List<SourceItem> retrieve(@RequestParam String question) {
        return ragService.retrieve(question);
    }
}
