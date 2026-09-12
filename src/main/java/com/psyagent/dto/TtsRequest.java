package com.psyagent.dto;

/**
 * 语音合成请求：POST /api/tts。
 * voice / rate 可空，缺省时按 X-User-Role 取人格默认音色。
 */
public record TtsRequest(String text, String voice, String rate) {
}
