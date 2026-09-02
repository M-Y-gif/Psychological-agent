package com.psyagent.runner;

import com.psyagent.config.RagProperties;
import com.psyagent.service.DocIngestionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

/**
 * 启动时自动把 docs 目录下的文献导入 Chroma。
 * 导入失败只记录警告，不阻塞应用启动，方便先调试其他功能。
 */
@Component
public class StartupIngestRunner implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(StartupIngestRunner.class);

    private final DocIngestionService ingestionService;
    private final RagProperties props;

    public StartupIngestRunner(DocIngestionService ingestionService, RagProperties props) {
        this.ingestionService = ingestionService;
        this.props = props;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (!props.ingestOnStartup()) {
            log.info("已跳过启动时文档导入（psy.rag.ingest-on-startup=false）");
            return;
        }
        try {
            int count = ingestionService.ingest(props.docsPath());
            log.info("启动时文档导入完成，共 {} 个片段", count);
        } catch (Exception e) {
            log.warn("启动时文档导入失败（请确认 Chroma 已启动、目录路径正确）：{}", e.getMessage());
        }
    }
}
