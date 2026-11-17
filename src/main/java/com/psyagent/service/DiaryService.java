package com.psyagent.service;

import com.psyagent.config.PersonaProperties;
import com.psyagent.dto.Caller;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 心情日记：保存日记 + 情绪打卡，然后由 Agent 写一段温柔回信。
 *
 * 安全设计：回信用工具版 ChatClient（同 RagService 的 bean）——
 * 日记内容若被判定为高风险，evaluate_risk_level 会触发预警邮件 + Excel 留痕，
 * 与文字对话同一套预警链路。
 */
@Service
public class DiaryService {

    private static final Logger log = LoggerFactory.getLogger(DiaryService.class);

    private final MemoryService memory;
    private final PersonaProperties personas;
    private final ChatClient chatClient;   // 工具版：evaluate_risk_level + 预警双工具

    public DiaryService(MemoryService memory, PersonaProperties personas, ChatClient chatClient) {
        this.memory = memory;
        this.personas = personas;
        this.chatClient = chatClient;
    }

    /** 1-5 心情 → -3..+3 打卡分（负面加权，3=中性记 0） */
    static int mapMood(Integer mood) {
        return switch (mood == null ? 3 : mood) {
            case 1 -> -3;
            case 2 -> -2;
            case 3 -> 0;
            case 4 -> 1;
            case 5 -> 2;
            default -> 0;
        };
    }

    /**
     * 顺序：先落盘日记 + 情绪打卡（LLM 失败也不丢），再用工具版客户端生成回信，
     * 最后后台抽取事实/安排。返回 {diary, riskLevel, riskReason}。
     */
    public Map<String, Object> saveAndReply(Caller caller, String text, Integer mood) {
        String cleaned = text == null ? "" : text.trim();
        if (cleaned.isEmpty()) {
            throw new IllegalArgumentException("日记内容不能为空");
        }
        Integer m = (mood != null && mood >= 1 && mood <= 5) ? mood : null;
        MemoryService.Diary diary = memory.addDiary(caller, cleaned, m, m == null ? null : mapMood(m));

        Integer riskLevel = null;
        String riskReason = null;
        MemoryService.Diary saved = diary;
        try {
            ToolCallContext ctx = new ToolCallContext();   // 与 RagService.answer 同款模式
            String out = chatClient.prompt()
                    .system(diarySystem(caller, cleaned))
                    .user("对方今天写下的日记（心情 " + (m == null ? "未选择" : m + " / 5") + "）：\n" + cleaned)
                    .toolContext(Map.of(ToolCallContext.KEY, ctx))
                    .call().content();
            if (out != null && !out.isBlank()) {
                saved = memory.attachDiaryReply(caller, diary.at, out.trim(), ctx.getRiskLevel());
            }
            riskLevel = ctx.getRiskLevel();               // evaluate_risk_level 写回
            riskReason = ctx.getRiskReason();
        } catch (Exception e) {
            log.warn("日记回信生成失败：{}", e.getMessage());   // 日记已保存，前端仍可用
        }
        memory.extractFromDiaryAsync(caller, cleaned);    // 后台抽取，不拖慢响应

        Map<String, Object> res = new LinkedHashMap<>();
        res.put("diary", diaryMap(saved == null ? diary : saved));
        res.put("riskLevel", riskLevel);
        res.put("riskReason", riskReason == null ? "" : riskReason);
        return res;
    }

    private String diarySystem(Caller caller, String diaryText) {
        String sys = "对方刚写下了一篇心情日记，你现在要给他写一段温柔的回信。要求：\n"
                + "- 先接住日记里的情绪（复述他具体说了什么），再轻轻回应，2-4 句话，总长 80-200 字；\n"
                + "- 不说教、不评判、不展开成小作文；纯口语，禁止 markdown 标记与 emoji；\n"
                + "- 自然地用上你对他的了解；日记里提到具体事件（复查、考试、家人）可以轻轻回应；\n"
                + "- 结尾留一个轻轻的、容易回答的口子。\n\n"
                + "【安全】如果日记出现强烈负面情绪、绝望或自伤/自杀相关内容，必须先调用 evaluate_risk_level 评估风险；"
                + "评估为 2-3 级时，必须立即调用 send_warning_email 和 write_risk_record_excel，二者都要调用，"
                + "并在回复中直接建议对方立即拨打心理援助热线 12356 或寻求线下专业帮助。安全永远优先于回信风格。\n\n"
                + "只输出回信正文，不要输出任何解释或标题。";
        PersonaProperties.Persona persona = personas.personaFor(caller.role());
        if (persona != null && persona.system() != null && !persona.system().isBlank()) {
            sys = persona.system() + "\n\n" + sys;
        }
        String remembered = memory.promptContext(caller, diaryText);   // 日记内容作为检索查询词
        if (remembered != null) {
            sys += "\n\n【关于这位来访者，你记得的事】\n" + remembered;
        }
        String tone = memory.toneDirective(caller);
        if (tone != null) {
            sys += "\n\n" + tone;
        }
        return sys;
    }

    private static Map<String, Object> diaryMap(MemoryService.Diary d) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("text", d.text);
        e.put("at", d.at);
        e.put("mood", d.mood);
        e.put("reply", d.reply);
        e.put("repliedAt", d.repliedAt);
        return e;
    }
}
