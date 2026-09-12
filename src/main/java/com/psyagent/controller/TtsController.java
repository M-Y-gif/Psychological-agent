package com.psyagent.controller;

import com.psyagent.config.PersonaProperties;
import com.psyagent.dto.TtsRequest;
import com.psyagent.service.MultimodalClient;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 语音合成代理：前端发文本 -> Java 转发到 Python edge-tts 服务 -> 返回 mp3 字节。
 * 音色/语速缺省时按使用者角色取人格默认（elder 晓晓 -20% / child 晓伊 +10% / family 云希）。
 */
@RestController
@RequestMapping("/api")
public class TtsController {

    private final MultimodalClient multimodalClient;
    private final PersonaProperties personas;

    public TtsController(MultimodalClient multimodalClient, PersonaProperties personas) {
        this.multimodalClient = multimodalClient;
        this.personas = personas;
    }

    @PostMapping(value = "/tts", produces = MediaType.APPLICATION_OCTET_STREAM_VALUE)
    public ResponseEntity<byte[]> tts(@RequestBody TtsRequest request,
                                      @RequestHeader(value = "X-User-Role", required = false) String role) {
        String text = request.text() == null ? "" : request.text().trim();
        if (text.isBlank()) {
            return ResponseEntity.badRequest().build();
        }
        // 控制成本与延迟：500 字上限
        if (text.length() > 500) {
            text = text.substring(0, 500);
        }
        PersonaProperties.Persona p = personas.personaFor(role == null || role.isBlank() ? "elder" : role);
        String voice = request.voice() == null || request.voice().isBlank() ? p.ttsVoice() : request.voice();
        String rate = request.rate() == null || request.rate().isBlank() ? p.ttsRate() : request.rate();
        byte[] audio = multimodalClient.tts(text, voice, rate);
        return ResponseEntity.ok()
                .header("Cache-Control", "private, max-age=86400")
                .body(audio);
    }
}
