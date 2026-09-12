package com.psyagent.controller;

import com.psyagent.eval.CompanionEvalService;
import com.psyagent.eval.RiskEvalService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 评测接口（均需要几分钟，期间会调用大模型）：
 *  - POST /api/eval/risk：风险识别效果评测
 *  - POST /api/eval/companion：情感陪伴质量评测（四维 LLM-as-judge，需 Chroma 运行）
 */
@RestController
@RequestMapping("/api/eval")
public class EvalController {

    private final RiskEvalService evalService;
    private final CompanionEvalService companionEvalService;

    public EvalController(RiskEvalService evalService, CompanionEvalService companionEvalService) {
        this.evalService = evalService;
        this.companionEvalService = companionEvalService;
    }

    @PostMapping("/risk")
    public Map<String, Object> runRiskEval() throws Exception {
        return evalService.runEvaluation();
    }

    @PostMapping("/companion")
    public Map<String, Object> runCompanionEval() throws Exception {
        return companionEvalService.runEvaluation();
    }
}
