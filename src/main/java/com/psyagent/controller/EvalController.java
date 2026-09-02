package com.psyagent.controller;

import com.psyagent.eval.RiskEvalService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 评测接口：POST /api/eval/risk
 * 用测试集评估风险识别效果（需要几分钟，期间会调用大模型）。
 */
@RestController
@RequestMapping("/api/eval")
public class EvalController {

    private final RiskEvalService evalService;

    public EvalController(RiskEvalService evalService) {
        this.evalService = evalService;
    }

    @PostMapping("/risk")
    public Map<String, Object> runRiskEval() throws Exception {
        return evalService.runEvaluation();
    }
}
