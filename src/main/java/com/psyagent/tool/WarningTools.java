package com.psyagent.tool;

import com.psyagent.service.RiskRecordExcelService;
import com.psyagent.service.WarningEmailService;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.stereotype.Component;

/**
 * 第三步：外部能力工具（通过 MCP 暴露给 Agent）。
 * 当 evaluate_risk_level 判定出高风险（2-3 级）时，Agent 自动调用这两个工具完成预警与留痕。
 */
@Component
public class WarningTools {

    private final WarningEmailService emailService;
    private final RiskRecordExcelService excelService;

    public WarningTools(WarningEmailService emailService, RiskRecordExcelService excelService) {
        this.emailService = emailService;
        this.excelService = excelService;
    }

    @Tool(description = "发送心理危机预警邮件给咨询师/辅导员。当评估出高风险（2-3 级）时调用，参数 subject 为邮件主题，content 为邮件正文。")
    public String send_warning_email(String subject, String content) {
        return emailService.sendWarning(subject, content);
    }

    @Tool(description = "将心理风险记录写入 Excel 留痕文件。当评估出风险（>=1 级）时调用，参数 riskLevel 为 0-3 级风险等级，reason 为判定依据，userMessage 为用户消息。")
    public String write_risk_record_excel(int riskLevel, String reason, String userMessage) {
        return excelService.appendRiskRecord(riskLevel, reason, userMessage);
    }
}
