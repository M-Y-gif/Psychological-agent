package com.psyagent.util;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class TextChunkerTest {

    @Test
    void blankTextReturnsEmpty() {
        assertThat(TextChunker.chunk("", 100, 20)).isEmpty();
        assertThat(TextChunker.chunk("   \n\n  ", 100, 20)).isEmpty();
    }

    @Test
    void shortTextStaysInOneChunk() {
        String text = "第一段。\n\n第二段。";
        List<String> chunks = TextChunker.chunk(text, 1000, 50);
        assertThat(chunks).hasSize(1);
        assertThat(chunks.get(0)).contains("第一段").contains("第二段");
    }

    @Test
    void mergesParagraphsUntilLimit() {
        String text = "段落A：一二三四五六七八九十。\n\n段落B：一二三四五六七八九十。\n\n段落C：一二三四五六七八九十。";
        List<String> chunks = TextChunker.chunk(text, 30, 0);
        assertThat(chunks.size()).isGreaterThan(1);
        for (String c : chunks) {
            assertThat(c.length()).isLessThanOrEqualTo(40); // 允许略超
        }
    }

    @Test
    void longParagraphIsHardSplitWithOverlap() {
        String text = "x".repeat(1000);
        List<String> chunks = TextChunker.chunk(text, 300, 50);
        assertThat(chunks.size()).isGreaterThanOrEqualTo(4);
        assertThat(chunks.get(0)).endsWith("x".repeat(50));
        assertThat(chunks.get(1)).startsWith("x".repeat(50));
    }

    @Test
    void overlapCarriesTailBetweenParagraphMerges() {
        String para1 = "一".repeat(100);
        String para2 = "二".repeat(100);
        String text = para1 + "\n\n" + para2;
        List<String> chunks = TextChunker.chunk(text, 120, 20);
        assertThat(chunks.size()).isGreaterThan(1);
        String first = chunks.get(0);
        assertThat(chunks.get(1)).startsWith(first.substring(first.length() - 20));
    }
}
