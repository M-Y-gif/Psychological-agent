package com.psyagent.service;

import com.psyagent.config.WarningProperties;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.ss.usermodel.WorkbookFactory;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * 风险记录 Excel 服务：追加写入风险留痕（时间、等级、依据、消息）。
 * 采用「临时文件 + 原子替换」，避免写入中断导致文件损坏；文件损坏时自动重建。
 */
@Service
public class RiskRecordExcelService {

    private static final Logger log = LoggerFactory.getLogger(RiskRecordExcelService.class);
    private static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final String SHEET = "风险记录";

    private final WarningProperties props;

    public RiskRecordExcelService(WarningProperties props) {
        this.props = props;
    }

    public synchronized String appendRiskRecord(int riskLevel, String reason, String userMessage) {
        Path file = Path.of(props.excelPath());
        try {
            Path parent = file.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            Workbook wb = openWorkbook(file);
            Sheet sheet = wb.getSheet(SHEET);
            if (sheet == null) {
                sheet = wb.createSheet(SHEET);
                writeHeader(sheet);
            }

            int rowNum = sheet.getLastRowNum() + 1;
            Row row = sheet.createRow(rowNum);
            row.createCell(0).setCellValue(LocalDateTime.now().format(FMT));
            row.createCell(1).setCellValue(riskLevel);
            row.createCell(2).setCellValue(reason == null ? "" : reason);
            row.createCell(3).setCellValue(truncate(userMessage, 200));

            // 先写临时文件，成功后原子替换，防止中断留下 0 字节损坏文件
            Path tmp = file.resolveSibling(file.getFileName() + ".tmp");
            try (OutputStream out = Files.newOutputStream(tmp)) {
                wb.write(out);
            }
            wb.close();
            Files.move(tmp, file, StandardCopyOption.REPLACE_EXISTING);
            log.info("风险记录已写入 {}", file.toAbsolutePath());
            return "风险记录已写入 Excel: " + file.toAbsolutePath();
        } catch (Exception e) {
            log.error("写入风险记录 Excel 失败", e);
            return "写入风险记录失败：" + e.getMessage();
        }
    }

    private Workbook openWorkbook(Path file) throws IOException {
        if (Files.exists(file) && Files.size(file) > 0) {
            try {
                return WorkbookFactory.create(file.toFile());
            } catch (Exception e) {
                log.warn("风险记录文件损坏（{}），自动重建：{}", file.getFileName(), e.getMessage());
                return new XSSFWorkbook();
            }
        }
        return new XSSFWorkbook();
    }

    private static void writeHeader(Sheet sheet) {
        Row header = sheet.createRow(0);
        header.createCell(0).setCellValue("时间");
        header.createCell(1).setCellValue("风险等级");
        header.createCell(2).setCellValue("判定依据");
        header.createCell(3).setCellValue("用户消息");
        sheet.setColumnWidth(0, 22 * 256);
        sheet.setColumnWidth(1, 10 * 256);
        sheet.setColumnWidth(2, 60 * 256);
        sheet.setColumnWidth(3, 60 * 256);
    }

    private static String truncate(String s, int max) {
        if (s == null) return "";
        return s.length() <= max ? s : s.substring(0, max) + "…";
    }
}
