package com.psyagent.service;

import com.psyagent.dto.SourceItem;
import org.springframework.context.annotation.Scope;
import org.springframework.context.annotation.ScopedProxyMode;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * 请求级上下文：收集本次问答中工具调用产生的检索片段与风险评估结果，
 * 供接口返回给前端展示（回答溯源 + 风险提示）。
 */
@Component
@Scope(value = "request", proxyMode = ScopedProxyMode.TARGET_CLASS)
public class ToolCallContext {

    private final List<SourceItem> sources = new ArrayList<>();
    private Integer riskLevel;
    private String riskReason;

    public void clear() {
        sources.clear();
        riskLevel = null;
        riskReason = null;
    }

    public void addSource(SourceItem item) {
        sources.add(item);
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
