package com.psyagent.dto;

import java.util.List;

/** 前端确认收到主动关怀：POST /api/care/ack */
public record AckRequest(List<String> ids) {
}
