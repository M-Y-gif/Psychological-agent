package com.psyagent.controller;

import com.psyagent.dto.AckRequest;
import com.psyagent.dto.Caller;
import com.psyagent.dto.CareItem;
import com.psyagent.service.CareService;
import com.psyagent.service.MemoryService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 记忆与主动关怀接口。
 * 使用者由请求头识别：X-User-Id / X-User-Name / X-User-Role（这一版不做鉴权）。
 */
@RestController
@RequestMapping("/api")
public class CareController {

    private final CareService careService;
    private final MemoryService memoryService;

    public CareController(CareService careService, MemoryService memoryService) {
        this.careService = careService;
        this.memoryService = memoryService;
    }

    /** 前端轮询：取尚未展示的主动关怀（只读；展示确认走 /care/ack） */
    @GetMapping("/care/pending")
    public List<CareItem> pending(
            @RequestHeader(value = "X-User-Id", required = false) String id,
            @RequestHeader(value = "X-User-Name", required = false) String name,
            @RequestHeader(value = "X-User-Role", required = false) String role) {
        return careService.pending(Caller.from(id, name, role));
    }

    /** 前端确认已展示，标记送达（幂等） */
    @PostMapping("/care/ack")
    public Map<String, Object> ack(
            @RequestHeader(value = "X-User-Id", required = false) String id,
            @RequestHeader(value = "X-User-Name", required = false) String name,
            @RequestHeader(value = "X-User-Role", required = false) String role,
            @RequestBody(required = false) AckRequest body) {
        memoryService.ackCare(Caller.from(id, name, role),
                body == null ? List.of() : body.ids());
        return Map.of("ok", true);
    }

    /** 演示用：立刻触发一条主动关怀，不用等到定时任务（type：message / breath / story） */
    @PostMapping("/care/trigger")
    public CareItem trigger(
            @RequestHeader(value = "X-User-Id", required = false) String id,
            @RequestHeader(value = "X-User-Name", required = false) String name,
            @RequestHeader(value = "X-User-Role", required = false) String role,
            @RequestParam(defaultValue = "message") String type) {
        return careService.triggerNow(Caller.from(id, name, role), type);
    }

    /** 查看"它记得我什么"，用于演示与排查 */
    @GetMapping("/memory")
    public Map<String, Object> memory(
            @RequestHeader(value = "X-User-Id", required = false) String id,
            @RequestHeader(value = "X-User-Name", required = false) String name,
            @RequestHeader(value = "X-User-Role", required = false) String role) {
        return memoryService.summary(Caller.from(id, name, role));
    }
}
