package com.psyagent.controller;

import com.psyagent.service.MultimodalClient;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

/**
 * 多模态分析接口：POST /api/multimodal/analyze
 * 可传 audio（语音文件）和/或 image（人脸图片），返回转写文本、韵律与表情特征。
 */
@RestController
@RequestMapping("/api/multimodal")
public class MultimodalController {

    private final MultimodalClient multimodalClient;

    public MultimodalController(MultimodalClient multimodalClient) {
        this.multimodalClient = multimodalClient;
    }

    @PostMapping(value = "/analyze", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> analyze(
            @RequestParam(value = "audio", required = false) MultipartFile audio,
            @RequestParam(value = "image", required = false) MultipartFile image) {
        return multimodalClient.analyze(audio, image);
    }
}
