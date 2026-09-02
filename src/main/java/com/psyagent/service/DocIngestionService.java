package com.psyagent.service;

import com.psyagent.config.RagProperties;
import com.psyagent.util.TextChunker;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

/**
 * 读取 docs 目录下的心理学文献，分块后向量化存入 Chroma。
 */
@Service
public class DocIngestionService {

    private static final Logger log = LoggerFactory.getLogger(DocIngestionService.class);

    private final VectorStore vectorStore;
    private final int chunkSize;
    private final int chunkOverlap;

    public DocIngestionService(VectorStore vectorStore, RagProperties props) {
        this.vectorStore = vectorStore;
        this.chunkSize = props.chunkSize();
        this.chunkOverlap = props.chunkOverlap();
    }

    /**
     * @return 导入的知识片段总数
     */
    public int ingest(String docsPath) throws IOException {
        Path root = Path.of(docsPath);
        if (!Files.isDirectory(root)) {
            throw new IOException("文档目录不存在: " + root.toAbsolutePath());
        }

        List<Document> docs = new ArrayList<>();
        int fileCount = 0;
        try (Stream<Path> paths = Files.walk(root)) {
            List<Path> files = paths.filter(Files::isRegularFile)
                    .filter(p -> p.toString().endsWith(".md") || p.toString().endsWith(".txt"))
                    .sorted()
                    .toList();

            for (Path file : files) {
                String text = Files.readString(file, StandardCharsets.UTF_8);
                List<String> chunks = TextChunker.chunk(text, chunkSize, chunkOverlap);
                for (String chunk : chunks) {
                    docs.add(new Document(chunk, Map.of("source", file.getFileName().toString())));
                }
                fileCount++;
            }
        }

        if (!docs.isEmpty()) {
            vectorStore.add(docs);
        }
        log.info("文档导入完成：{} 个文件 -> {} 个片段", fileCount, docs.size());
        return docs.size();
    }
}
