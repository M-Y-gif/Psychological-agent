<template>
  <div>
    <h2 class="title">💬 文字对话</h2>
    <p class="sub">Agent 会自主检索知识库、评估风险；高风险自动触发邮件预警 + Excel 留痕。</p>

    <textarea v-model="question" class="input" rows="3"
      placeholder="例如：什么是认知歪曲？&#10;或者：我最近很焦虑，有什么放松的方法？"
      @keydown.ctrl.enter="send" @keydown.meta.enter="send"></textarea>
    <button :disabled="loading" @click="send">{{ loading ? '思考中…' : '发送提问' }}</button>

    <div class="block">
      <div class="label">回答</div>
      <div class="answer">{{ answer || '等待提问…' }}</div>
    </div>

    <RiskBanner :risk-level="riskLevel" :reason="riskReason" />

    <div class="block">
      <div class="label">命中的知识片段</div>
      <div v-if="sources.length" class="sources">
        <div v-for="(s, i) in sources" :key="i" class="source">
          📄 {{ s.source }} · 相似度 {{ s.score.toFixed(4) }}<br>{{ s.snippet }}
        </div>
      </div>
      <div v-else class="muted">未命中知识库片段</div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { chat } from '../api'
import RiskBanner from './RiskBanner.vue'

const question = ref('')
const answer = ref('')
const sources = ref([])
const riskLevel = ref(null)
const riskReason = ref('')
const loading = ref(false)
const error = ref('')

async function send() {
  const q = question.value.trim()
  if (!q || loading.value) return
  loading.value = true
  error.value = ''
  answer.value = '正在检索知识库、评估风险并生成回答…'
  sources.value = []
  riskLevel.value = null
  try {
    const data = await chat(q)
    answer.value = data.answer || '（无回答）'
    sources.value = data.sources || []
    riskLevel.value = data.riskLevel
    riskReason.value = data.riskReason || ''
  } catch (e) {
    error.value = e.message
    answer.value = ''
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.title { font-size: 18px; }
.sub { color: #6b7280; font-size: 12px; margin: 6px 0 14px; }
.input { width: 100%; border: 1px solid #d1d5db; border-radius: 10px; padding: 12px; font-size: 14px; font-family: inherit; resize: vertical; }
.input:focus { outline: 2px solid #6366f1; border-color: transparent; }
button { width: 100%; margin-top: 10px; }
.block { margin-top: 18px; }
.label { font-size: 13px; color: #6b7280; margin-bottom: 8px; }
.answer { background: #f9fafb; border-radius: 10px; padding: 14px; font-size: 14px; line-height: 1.7; white-space: pre-wrap; min-height: 40px; }
.source { background: #eef2ff; border-radius: 8px; padding: 10px 12px; margin-top: 8px; font-size: 12px; color: #4338ca; word-break: break-all; }
.muted { color: #9ca3af; font-size: 13px; }
.error { background: #fef2f2; color: #b91c1c; border-radius: 10px; padding: 12px; font-size: 13px; margin-top: 12px; }
</style>
