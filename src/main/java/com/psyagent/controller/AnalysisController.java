package com.psyagent.controller;

import com.psyagent.dto.SessionAnalysisRequest;
import com.psyagent.dto.SessionAnalysisResponse;
import com.psyagent.service.SessionAnalysisService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 会话心理分析：POST /api/analysis/session
 * 对话结束后，基于完整对话记录生成心理分析报告（负面->安慰鼓励，正面->同乐鼓励）。
 */
@RestController
@RequestMapping("/api/analysis")
public class AnalysisController {

    private final SessionAnalysisService analysisService;

    public AnalysisController(SessionAnalysisService analysisService) {
        this.analysisService = analysisService;
    }

    @PostMapping("/session")
    public SessionAnalysisResponse analyze(@RequestBody SessionAnalysisRequest request) {
        return analysisService.analyze(request);
    }
}
