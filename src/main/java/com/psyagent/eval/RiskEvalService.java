package com.psyagent.eval;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.psyagent.service.RiskEvaluator;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVPrinter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.Reader;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 风险识别效果评测：用与线上一致的风险判定器跑测试集，
 * 对比「纯规则 / 纯LLM / 规则+LLM混合」三组指标，输出报告。
 *
 * 指标口径：高风险 = 等级 >= 2。
 *  - Recall(高风险) 最关键：高风险用户绝不能漏报
 *  - Precision：减少误报（避免给正常用户发预警）
 */
@Service
public class RiskEvalService {

    private static final Logger log = LoggerFactory.getLogger(RiskEvalService.class);
    private static final String TEST_SET = "evaluation/data/test_set.csv";
    private static final String REPORT_DIR = "evaluation/reports";

    private final RiskEvaluator riskEvaluator;

    public RiskEvalService(RiskEvaluator riskEvaluator) {
        this.riskEvaluator = riskEvaluator;
    }

    /** 单条评测结果 */
    public record EvalCase(int id, String text, int gold,
                           int rulePred, int llmPred, int combinedPred, String combinedReason) {
    }

    /** 二分类指标（高风险 vs 非高风险） */
    public record Metrics(int tp, int fp, int fn, int tn,
                          double accuracy, double precision, double recall, double f1) {
        public static Metrics of(int tp, int fp, int fn, int tn) {
            double acc = (double) (tp + tn) / Math.max(1, tp + fp + fn + tn);
            double precision = tp + fp == 0 ? 0 : (double) tp / (tp + fp);
            double recall = tp + fn == 0 ? 0 : (double) tp / (tp + fn);
            double f1 = precision + recall == 0 ? 0 : 2 * precision * recall / (precision + recall);
            return new Metrics(tp, fp, fn, tn, acc, precision, recall, f1);
        }
    }

    public Map<String, Object> runEvaluation() throws IOException {
        List<EvalCase> cases = new ArrayList<>();
        try (Reader reader = Files.newBufferedReader(Path.of(TEST_SET), StandardCharsets.UTF_8);
             CSVParser parser = CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build().parse(reader)) {
            parser.forEach(rec -> {
                int id = Integer.parseInt(rec.get("id"));
                String text = rec.get("text");
                int gold = Integer.parseInt(rec.get("gold_level"));
                RiskEvaluator.RiskResult r = riskEvaluator.evaluate(text);
                cases.add(new EvalCase(id, text, gold, r.ruleLevel(), r.llmLevel(), r.level(), r.reason()));
            });
        }

        Metrics ruleM = computeMetrics(cases, true, false);
        Metrics llmM = computeMetrics(cases, false, true);
        Metrics combinedM = computeMetrics(cases, false, false);

        int exactHits = (int) cases.stream().filter(c -> c.combinedPred() == c.gold()).count();
        int nearHits = (int) cases.stream().filter(c -> Math.abs(c.combinedPred() - c.gold()) <= 1).count();
        int n = cases.size();

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("total", n);
        result.put("exactAccuracy", round(exactHits * 100.0 / n));
        result.put("nearAccuracy_offByOne", round(nearHits * 100.0 / n));
        result.put("ruleOnly", metricsMap(ruleM));
        result.put("llmOnly", metricsMap(llmM));
        result.put("combined", metricsMap(combinedM));

        writeReports(cases, ruleM, llmM, combinedM, result);
        log.info("评测完成：{} 条，混合法高风险召回率 {}%，误报 {} 条",
                n, Math.round(combinedM.recall() * 100), combinedM.fp());
        return result;
    }

    private Metrics computeMetrics(List<EvalCase> cases, boolean useRule, boolean useLlm) {
        int tp = 0, fp = 0, fn = 0, tn = 0;
        for (EvalCase c : cases) {
            int pred = useRule ? c.rulePred() : (useLlm ? c.llmPred() : c.combinedPred());
            boolean goldPos = c.gold() >= 2;
            boolean predPos = pred >= 2;
            if (goldPos && predPos) tp++;
            else if (!goldPos && predPos) fp++;
            else if (goldPos && !predPos) fn++;
            else tn++;
        }
        return Metrics.of(tp, fp, fn, tn);
    }

    private Map<String, Object> metricsMap(Metrics m) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("tp", m.tp()); map.put("fp", m.fp()); map.put("fn", m.fn()); map.put("tn", m.tn());
        map.put("accuracy", round(m.accuracy() * 100));
        map.put("precision", round(m.precision() * 100));
        map.put("recall", round(m.recall() * 100));
        map.put("f1", round(m.f1() * 100));
        return map;
    }

    private void writeReports(List<EvalCase> cases, Metrics ruleM, Metrics llmM, Metrics combinedM,
                              Map<String, Object> result) throws IOException {
        Files.createDirectories(Path.of(REPORT_DIR));
        Path csvPath = Path.of(REPORT_DIR, "risk_eval_cases.csv");
        try (Writer w = Files.newBufferedWriter(csvPath, StandardCharsets.UTF_8);
             CSVPrinter p = CSVFormat.DEFAULT.builder().setHeader(
                     "id", "gold", "rule", "llm", "combined", "combined_correct", "category_hint", "text").build().print(w)) {
            for (EvalCase c : cases) {
                p.printRecord(c.id(), c.gold(), c.rulePred(), c.llmPred(), c.combinedPred(),
                        c.combinedPred() == c.gold() ? 1 : 0, "", c.text());
            }
        }

        Path mdPath = Path.of(REPORT_DIR, "risk_eval_summary.md");
        String md = """
                # 风险识别效果评测报告

                - 测试集：%d 条（高风险正样本 %d 条，常规负样本 %d 条）
                - 指标口径：高风险 = 等级 >= 2
                - 精确等级准确率：%.1f%%，误差<=1级：%.1f%%

                | 方法 | 准确率 | 精确率 | 召回率(高风险) | F1 | 误报FP | 漏报FN |
                | --- | --- | --- | --- | --- | --- | --- |
                | 纯规则 | %.1f%% | %.1f%% | %.1f%% | %.1f%% | %d | %d |
                | 纯LLM | %.1f%% | %.1f%% | %.1f%% | %.1f%% | %d | %d |
                | 规则+LLM混合 | %.1f%% | %.1f%% | %.1f%% | %.1f%% | %d | %d |

                > 说明：召回率（高风险用户被识别出的比例）是本系统最重要的指标——漏报意味着高风险用户未被预警。
                > 数据来源：PsyCrisis-Bench（CC BY-NC 4.0，学术研究使用）+ 自建常规负样本。
                """.formatted(
                cases.size(),
                (int) cases.stream().filter(c -> c.gold() >= 2).count(),
                (int) cases.stream().filter(c -> c.gold() < 2).count(),
                (double) result.get("exactAccuracy"), (double) result.get("nearAccuracy_offByOne"),
                ruleM.accuracy() * 100, ruleM.precision() * 100, ruleM.recall() * 100, ruleM.f1() * 100, ruleM.fp(), ruleM.fn(),
                llmM.accuracy() * 100, llmM.precision() * 100, llmM.recall() * 100, llmM.f1() * 100, llmM.fp(), llmM.fn(),
                combinedM.accuracy() * 100, combinedM.precision() * 100, combinedM.recall() * 100, combinedM.f1() * 100, combinedM.fp(), combinedM.fn());
        Files.writeString(mdPath, md, StandardCharsets.UTF_8);
    }

    private static double round(double v) {
        return Math.round(v * 100.0) / 100.0;
    }
}
