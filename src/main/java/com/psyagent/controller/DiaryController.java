package com.psyagent.controller;

import com.psyagent.dto.Caller;
import com.psyagent.dto.DiaryRequest;
import com.psyagent.service.DiaryService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** 心情日记接口：使用者由请求头识别（同 CareController，演示版不做鉴权） */
@RestController
@RequestMapping("/api")
public class DiaryController {

    private final DiaryService diaryService;

    public DiaryController(DiaryService diaryService) {
        this.diaryService = diaryService;
    }

    /** 保存心情日记 + 生成温柔回信；高风险日记自动触发预警与留痕 */
    @PostMapping("/diary")
    public Map<String, Object> save(@RequestBody DiaryRequest body,
                                    @RequestHeader(value = "X-User-Id", required = false) String id,
                                    @RequestHeader(value = "X-User-Name", required = false) String name,
                                    @RequestHeader(value = "X-User-Role", required = false) String role) {
        return diaryService.saveAndReply(Caller.from(id, name, role), body.text(), body.mood());
    }
}
