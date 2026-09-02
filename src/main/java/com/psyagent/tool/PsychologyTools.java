package com.psyagent.tool;

import com.psyagent.config.RagProperties;
import com.psyagent.dto.SourceItem;
import com.psyagent.service.RiskEvaluator;
import com.psyagent.service.ToolCallContext;
import org.springframework.ai.document.Document;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 第二步：Agent 工具（Function Calling）。
 *  - search_psychology_kb：检索心理学知识库
 *  - evaluate_risk_level：风险判定（委托 RiskEvaluator，规则+LLM 混合）
 */
@Component
public class PsychologyTools {

    private final VectorStore vectorStore;
    private final RiskEvaluator riskEvaluator;
    private final ToolCallContext context;
    private final int topK;

    public PsychologyTools(VectorStore vectorStore, RiskEvaluator riskEvaluator,
                           ToolCallContext context, RagProperties props) {
        this.vectorStore = vectorStore;
        this.riskEvaluator = riskEvaluator;
        this.context = context;
        this.topK = props.topK();
    }

    @Tool(description = "在心理学知识库中检索与用户问题相关的知识片段。当你需要基于心理学专业知识（如 CBT、情绪调节、放松技巧等）回答用户问题时调用，参数 query 为检索关键词或用户原话。")
    public String search_psychology_kb(String query) {
        List<Document> hits = vectorStore.similaritySearch(
                SearchRequest.builder().query(query).topK(topK).build());

        StringBuilder sb = new StringBuilder();
        int i = 1;
        for (Document d : hits) {
            String source = String.valueOf(d.getMetadata().getOrDefault("source", "unknown"));
            context.addSource(new SourceItem(source, truncate(d.getText(), 120),
                    d.getScore() == null ? 0.0 : d.getScore()));
            sb.append("【片段").append(i++).append("｜来源：").append(source).append("】\n")
                    .append(d.getText()).append("\n\n");
        }
        return hits.isEmpty() ? "知识库中没有检索到相关内容。" : sb.toString();
    }

    @Tool(description = "评估用户消息的心理风险等级，返回 0-3 级：0=无明显风险，1=轻度情绪困扰，2=中高风险，3=极高风险（有自伤/自杀倾向）。当用户表达强烈负面情绪、绝望，或任何自伤/自杀相关话语时，必须调用此工具。可选参数 emotionContext 为多模态情绪特征（语速/停顿/表情等 JSON 字符串），若有请务必传入以综合研判。")
    public String evaluate_risk_level(String userMessage, String emotionContext) {
        RiskEvaluator.RiskResult result = riskEvaluator.evaluate(userMessage, emotionContext);
        context.setRisk(result.level(), result.reason());
        return "风险等级：" + result.level() + "（0-3级）\n判定依据：" + result.reason();
    }

    private static String truncate(String s, int max) {
        if (s == null || s.length() <= max) return s;
        return s.substring(0, max) + "…";
    }
}
