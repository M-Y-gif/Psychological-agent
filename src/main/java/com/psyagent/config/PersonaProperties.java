package com.psyagent.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.Map;

/**
 * 人格设定（前缀 psy.persona）。按 X-User-Role 选择人格：
 *  - elder：晚晴（晚辈式，陪伴长辈）
 *  - child：小暖（玩伴式，陪伴孩子）
 *  - family：晚晴（客观温和，服务家属）
 */
@ConfigurationProperties(prefix = "psy.persona")
public record PersonaProperties(Map<String, Persona> personas) {

    public record Persona(String name, String ttsVoice, String ttsRate, String system) {
    }

    /** 按角色取人格，未知角色回退 elder */
    public Persona personaFor(String role) {
        if (personas == null) return null;
        Persona p = personas.get(role);
        return p != null ? p : personas.get("elder");
    }
}
