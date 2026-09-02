package com.psyagent.util;

import java.util.ArrayList;
import java.util.List;

/**
 * 简易中文分块器：按空行划分段落，再按字符上限合并成块，块与块之间保留重叠。
 * 起步够用；后续可替换为语义分块或标题感知分块。
 */
public final class TextChunker {

    private TextChunker() {
    }

    public static List<String> chunk(String text, int maxChars, int overlap) {
        if (text == null || text.isBlank()) {
            return List.of();
        }
        if (maxChars <= 0) {
            throw new IllegalArgumentException("maxChars 必须大于 0");
        }

        String normalized = text.replace("\r\n", "\n").trim();
        String[] paragraphs = normalized.split("\n\\s*\n");

        List<String> result = new ArrayList<>();
        StringBuilder current = new StringBuilder();

        for (String para : paragraphs) {
            String p = para.trim();
            if (p.isEmpty()) {
                continue;
            }
            // 单个超长段落：先清空当前块，再硬切
            if (p.length() > maxChars) {
                flush(current, result);
                result.addAll(hardSplit(p, maxChars, overlap));
                continue;
            }
            // 放不下：先收走当前块，并带上尾部重叠
            if (current.length() > 0 && current.length() + p.length() + 2 > maxChars) {
                String tail = overlapTail(current.toString(), overlap);
                flush(current, result);
                if (!tail.isEmpty()) {
                    current.append(tail).append("\n\n");
                }
            } else if (current.length() > 0) {
                current.append("\n\n");
            }
            current.append(p);
        }
        flush(current, result);
        return result;
    }

    private static void flush(StringBuilder sb, List<String> out) {
        if (!sb.isEmpty()) {
            out.add(sb.toString());
            sb.setLength(0);
        }
    }

    private static String overlapTail(String chunk, int overlap) {
        if (overlap <= 0 || chunk.length() <= overlap) {
            return "";
        }
        return chunk.substring(chunk.length() - overlap);
    }

    private static List<String> hardSplit(String text, int maxChars, int overlap) {
        List<String> pieces = new ArrayList<>();
        int start = 0;
        while (start < text.length()) {
            int end = Math.min(start + maxChars, text.length());
            pieces.add(text.substring(start, end));
            if (end == text.length()) {
                break;
            }
            start = Math.max(end - overlap, start + 1);
        }
        return pieces;
    }
}
