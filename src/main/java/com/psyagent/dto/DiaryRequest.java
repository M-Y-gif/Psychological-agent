package com.psyagent.dto;

/** 心情日记请求：text 正文；mood 1-5 心情打卡（可为空） */
public record DiaryRequest(String text, Integer mood) {
}
