package com.psyagent.controller;

import com.psyagent.dto.ChatRequest;
import com.psyagent.dto.ChatResponse;
import com.psyagent.dto.SourceItem;
import com.psyagent.service.RagService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api")
public class ChatController {

    private final RagService ragService;

    public ChatController(RagService ragService) {
        this.ragService = ragService;
    }

    /** 用户提问 -> Agent 自主决策（检索/风险评估/预警）-> 大模型生成回答；emotionContext 可选传入多模态情绪特征 */
    @PostMapping("/chat")
    public ChatResponse chat(@RequestBody ChatRequest request) {
        return ragService.answer(request.question(), request.emotionContext());
    }

    /** 仅检索，返回命中的知识片段（调试/评测用） */
    @GetMapping("/rag/retrieve")
    public List<SourceItem> retrieve(@RequestParam String question) {
        return ragService.retrieve(question);
    }
}
