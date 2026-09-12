package com.psyagent.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.psyagent.config.MultimodalProperties;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 多模态感知引擎客户端：调用 Python 微服务（Whisper 语音 + 表情分析）。
 * 使用 HttpURLConnection 发送原始文件字节流，兼容性最稳妥。
 */
@Service
public class MultimodalClient {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    private final MultimodalProperties props;
    private final ObjectMapper objectMapper;

    public MultimodalClient(MultimodalProperties props, ObjectMapper objectMapper) {
        this.props = props;
        this.objectMapper = objectMapper;
    }

    /**
     * 综合分析：音频 -> 语音转写+韵律；图片 -> 表情特征。二者可单独或同时传入。
     */
    public Map<String, Object> analyze(MultipartFile audio, MultipartFile image) {
        Map<String, Object> result = new LinkedHashMap<>();
        if (audio != null && !audio.isEmpty()) {
            result.putAll(postBinary("/api/stt", audio));
        }
        if (image != null && !image.isEmpty()) {
            result.putAll(postBinary("/api/emotion", image));
        }
        return result;
    }

    private Map<String, Object> postBinary(String path, MultipartFile file) {
        try {
            byte[] bytes = file.getBytes();
            String base = props.baseUrl().replaceAll("/+$", "");
            HttpURLConnection conn = (HttpURLConnection) URI.create(base + path).toURL().openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/octet-stream");
            conn.setDoOutput(true);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(120000);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(bytes);
            }
            int code = conn.getResponseCode();
            InputStream stream = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
            String json = new String(stream == null ? new byte[0] : stream.readAllBytes(), StandardCharsets.UTF_8);
            if (code >= 400) {
                throw new RuntimeException(path + " 返回 " + code + ": " + json);
            }
            return objectMapper.readValue(json, MAP_TYPE);
        } catch (Exception e) {
            throw new RuntimeException("多模态感知调用失败(" + path + "): " + e.getMessage(), e);
        }
    }

    /**
     * 语音合成：POST /api/tts（JSON 请求体），返回 mp3 原始字节。
     * 失败抛异常，由上层（TtsController -> 前端）降级到浏览器 speechSynthesis。
     */
    public byte[] tts(String text, String voice, String rate) {
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("text", text);
            body.put("voice", voice);
            body.put("rate", rate);
            String base = props.baseUrl().replaceAll("/+$", "");
            HttpURLConnection conn = (HttpURLConnection) URI.create(base + "/api/tts").toURL().openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(120000);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(objectMapper.writeValueAsBytes(body));
            }
            int code = conn.getResponseCode();
            InputStream stream = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
            byte[] bytes = stream == null ? new byte[0] : stream.readAllBytes();
            if (code >= 400) {
                throw new RuntimeException("/api/tts 返回 " + code + ": "
                        + new String(bytes, StandardCharsets.UTF_8));
            }
            return bytes;
        } catch (Exception e) {
            throw new RuntimeException("语音合成调用失败: " + e.getMessage(), e);
        }
    }
}
