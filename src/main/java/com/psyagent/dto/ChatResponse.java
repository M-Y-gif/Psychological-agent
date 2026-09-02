package com.psyagent.dto;

import java.util.List;

public record ChatResponse(String answer,
                           List<SourceItem> sources,
                           Integer riskLevel,
                           String riskReason) {
}
