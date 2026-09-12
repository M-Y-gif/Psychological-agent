package com.psyagent.dto;

import java.util.Map;

/**
 * 一条主动关怀消息（返回给前端）。
 * type：message 纯消息 | breath 呼吸练习邀请 | story 睡前故事。
 * payload：breath={"pattern":"4-4-6"}；story={"title":…,"content":…}；message=null。
 */
public record CareItem(String id, String text, String reason, String at,
                       String type, Map<String, Object> payload) {
}
