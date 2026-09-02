package com.psyagent.service;

import com.psyagent.config.WarningProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * 预警邮件服务：配置了 SMTP 则真实发送，否则演示模式写入本地文件。
 */
@Service
public class WarningEmailService {

    private static final Logger log = LoggerFactory.getLogger(WarningEmailService.class);
    private static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss");

    private final JavaMailSender mailSender;
    private final WarningProperties props;

    public WarningEmailService(ObjectProvider<JavaMailSender> mailSenderProvider, WarningProperties props) {
        this.mailSender = mailSenderProvider.getIfAvailable();
        this.props = props;
    }

    public String sendWarning(String subject, String content) {
        if (props.mailEnabled() && mailSender != null && StringUtils.hasText(props.mailTo())) {
            try {
                SimpleMailMessage msg = new SimpleMailMessage();
                msg.setTo(props.mailTo());
                msg.setSubject(subject);
                msg.setText(content);
                mailSender.send(msg);
                log.info("预警邮件已发送至 {}", props.mailTo());
                return "预警邮件已发送至 " + props.mailTo();
            } catch (Exception e) {
                log.error("邮件发送失败，降级为演示模式：{}", e.getMessage());
            }
        }
        // 演示模式：写入本地文件
        try {
            Path dir = Path.of(props.mailOutboxDir());
            Files.createDirectories(dir);
            Path file = dir.resolve("warning_" + LocalDateTime.now().format(FMT) + ".txt");
            String body = "收件人: " + props.mailTo() + "\n主题: " + subject + "\n\n" + content;
            Files.writeString(file, body, StandardCharsets.UTF_8);
            log.info("演示模式：预警邮件已写入 {}", file.toAbsolutePath());
            return "【演示模式】预警邮件已写入文件: " + file.toAbsolutePath();
        } catch (IOException e) {
            log.error("写入预警邮件文件失败", e);
            return "邮件发送失败（演示模式也失败）：" + e.getMessage();
        }
    }
}
