package com.psyagent.dto;

/**
 * 当前使用者：由前端在请求头里带过来（X-User-Id / X-User-Name / X-User-Role）。
 * 这一版只做透传归属，不做鉴权。
 */
public record Caller(String id, String name, String role) {

    public static Caller anonymous() {
        return new Caller("anonymous", "访客", "elder");
    }

    /** 从请求头还原（姓名经过 URL 编码，这里解一下） */
    public static Caller from(String id, String name, String role) {
        if (id == null || id.isBlank()) {
            return anonymous();
        }
        return new Caller(id, decode(name), role == null || role.isBlank() ? "elder" : role);
    }

    private static String decode(String v) {
        if (v == null || v.isBlank()) return "访客";
        try {
            return java.net.URLDecoder.decode(v, java.nio.charset.StandardCharsets.UTF_8);
        } catch (Exception e) {
            return v;
        }
    }

    public String roleLabel() {
        return switch (role) {
            case "child" -> "孩子";
            case "family" -> "家属";
            default -> "长者";
        };
    }
}
