package com.psyagent.service;

import com.psyagent.dto.SourceItem;

import java.util.ArrayList;
import java.util.List;

/**
 * 单次问答的上下文：收集本轮工具调用产生的检索片段与风险评估结果，供接口返回给前端展示。
 *
 * 说明：这里不用 request scope。流式（SSE）场景下工具会在 Reactor 的线程上执行，
 * 请求作用域拿不到，所以改为显式对象，通过 Spring AI 的 ToolContext 传入工具。
 */
public class ToolCallContext {

    /** 在 ToolContext 里使用的键 */
    public static final String KEY = "psyToolContext";

    private final List<SourceItem> sources = new ArrayList<>();
    private Integer riskLevel;
    private String riskReason;

    /** 去重：知识库可能因重复导入存在同一片段，避免前端出现多条一样的来源 */
    public void addSource(SourceItem item) {
        boolean exists = sources.stream().anyMatch(
                s -> s.source().equals(item.source()) && s.snippet().equals(item.snippet()));
        if (!exists) {
            sources.add(item);
        }
    }

    public void setRisk(Integer level, String reason) {
        this.riskLevel = level;
        this.riskReason = reason;
    }

    public List<SourceItem> getSources() {
        return sources;
    }

    public Integer getRiskLevel() {
        return riskLevel;
    }

    public String getRiskReason() {
        return riskReason;
    }
}
