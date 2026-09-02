<template>
  <div class="app">
    <header class="header">
      <h1>🧠 心理 Agent</h1>
      <p>多模态 Agentic RAG · 心理预警与咨询</p>
    </header>

    <nav class="tabs">
      <button v-for="t in tabs" :key="t.key" :class="['tab', { active: current === t.key }]"
              @click="current = t.key">
        {{ t.icon }} {{ t.label }}
      </button>
    </nav>

    <main class="main">
      <TextChat v-if="current === 'text'" />
      <VideoChat v-else-if="current === 'video'" />
      <BreathingGame v-else-if="current === 'game'" />
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import TextChat from './components/TextChat.vue'
import VideoChat from './components/VideoChat.vue'
import BreathingGame from './components/BreathingGame.vue'

const tabs = [
  { key: 'text', label: '文字对话', icon: '💬' },
  { key: 'video', label: '视频对话', icon: '🎥' },
  { key: 'game', label: '放松小游戏', icon: '🌬️' }
]
const current = ref('text')
</script>

<style scoped>
.app { max-width: 760px; margin: 0 auto; padding: 24px 16px 60px; }
.header { text-align: center; margin-bottom: 20px; }
.header h1 { font-size: 26px; color: #1f2937; }
.header p { color: #6b7280; font-size: 13px; margin-top: 4px; }
.tabs { display: flex; gap: 10px; justify-content: center; margin-bottom: 20px; }
.tab { background: #fff; color: #374151; box-shadow: 0 2px 8px rgba(0,0,0,.05); }
.tab.active { background: #6366f1; color: #fff; }
.main { background: #fff; border-radius: 16px; box-shadow: 0 8px 30px rgba(0,0,0,.08); padding: 24px; }
</style>
