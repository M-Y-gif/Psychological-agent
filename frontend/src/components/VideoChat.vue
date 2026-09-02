<template>
  <div>
    <h2 class="title">🎥 视频对话</h2>
    <p class="sub">开启摄像头，跟 Agent 说说话：每句话都会被语音转写 + 表情分析，Agent 会记住上下文回应你。
      结束后生成心理分析——情绪低落会得到安慰与鼓励，心情不错会得到同乐与肯定。</p>

    <div class="layout">
      <div class="video-box">
        <video ref="videoEl" autoplay playsinline muted class="video"></video>
        <div v-if="!streamOn" class="placeholder">摄像头未开启</div>
      </div>

      <div class="chat-panel">
        <div v-if="!turns.length" class="muted">对话记录会显示在这里<br>点击下方「开始对话」即可开始</div>
        <div v-for="(t, i) in turns" :key="i" :class="['bubble', t.role]">
          <div v-if="t.role === 'user'" class="who">你<span v-if="t.emotion" class="emo">{{ t.emotion }}</span></div>
          <div v-else class="who">🤖 Agent</div>
          <div class="content">{{ t.content }}</div>
        </div>
      </div>
    </div>

    <div class="controls">
      <button v-if="!streamOn" @click="startSession">▶️ 开始对话</button>
      <template v-else>
        <button v-if="!recording" @click="startTurn" :disabled="processing">🎙️ 按住说话（点击开始）</button>
        <button v-if="recording" class="danger" @click="stopTurn">⏹ 说完（点击结束）</button>
        <button class="secondary" :disabled="processing || turns.length === 0" @click="endSession">📋 结束并生成心理分析</button>
      </template>
    </div>

    <div v-if="recording" class="rec-tip">🔴 录音中… 说完点击「说完」</div>
    <div v-if="processing" class="rec-tip">⏳ 正在语音转写 + 情绪分析 + Agent 回应…</div>

    <div v-if="report" class="report">
      <h3>📋 心理分析报告</h3>
      <div class="mood-badge" :class="report.overallMood">
        {{ moodText(report.overallMood) }}
      </div>
      <div class="report-row"><b>情绪变化：</b>{{ report.emotionTrend }}</div>
      <div class="report-row"><b>主要议题：</b>{{ (report.mainIssues || []).join('、') }}</div>
      <RiskBanner :risk-level="report.riskLevel" :reason="report.riskReason" />
      <div class="feedback">{{ report.feedback }}</div>
      <div class="report-row" v-if="report.suggestions && report.suggestions.length">
        <b>建议：</b>
        <ul><li v-for="(sg, i) in report.suggestions" :key="i">{{ sg }}</li></ul>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { chat, multimodalAnalyze, analysisSession } from '../api'
import { blobToWav } from '../utils/wav'
import RiskBanner from './RiskBanner.vue'

const videoEl = ref(null)
const streamOn = ref(false)
const recording = ref(false)
const processing = ref(false)
const turns = ref([])
const report = ref(null)
const error = ref('')

let mediaStream = null
let recorder = null
let chunks = []
let latestFrame = null
let frameTimer = null
let sessionRisk = null
let sessionRiskReason = ''

function moodText(m) {
  return m === 'negative' ? '😔 整体情绪偏负面' : m === 'positive' ? '😄 整体情绪积极' : '😐 情绪中性'
}

async function startSession() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
    streamOn.value = true
    await new Promise(r => setTimeout(r, 100))
    videoEl.value.srcObject = mediaStream
    turns.value = []
    report.value = null
    error.value = ''
  } catch (e) {
    error.value = '无法打开摄像头/麦克风：' + e.message
  }
}

function startTurn() {
  if (!mediaStream || processing.value) return
  chunks = []
  latestFrame = null
  const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')
    ? 'video/webm;codecs=vp9,opus' : 'video/webm'
  recorder = new MediaRecorder(mediaStream, { mimeType: mime })
  recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data) }
  recorder.start(1000)
  recording.value = true
  frameTimer = setInterval(captureFrame, 3000)
}

function captureFrame() {
  const video = videoEl.value
  if (!video || !video.videoWidth) return
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0)
  canvas.toBlob(b => { latestFrame = b }, 'image/jpeg', 0.9)
}

async function stopTurn() {
  if (!recorder) return
  recording.value = false
  if (frameTimer) { clearInterval(frameTimer); frameTimer = null }
  await new Promise(resolve => { recorder.onstop = resolve; recorder.stop() })
  const videoBlob = new Blob(chunks, { type: 'video/webm' })
  if (!videoBlob.size) { error.value = '没录到声音，请重试'; return }
  processing.value = true
  error.value = ''
  try {
    // 1. 语音转写 + 表情分析
    const wavBlob = await blobToWav(videoBlob)
    captureFrame()
    const mm = await multimodalAnalyze(wavBlob, latestFrame)
    const text = mm.text || ''
    const emotion = mm.emotion_label || (mm.features_json ? JSON.parse(mm.features_json).表情 : '')
    if (!text) { error.value = '没有识别到语音，请靠近麦克风再试'; return }
    turns.value.push({ role: 'user', content: text, emotion })

    // 2. 带着多轮历史发给 Agent
    const history = turns.value
      .filter(t => t.role === 'user' || t.role === 'assistant')
      .slice(0, -1)
      .map(t => ({ role: t.role, content: t.content }))
    let emotionContext = null
    try { emotionContext = mm.features_json ? JSON.parse(mm.features_json) : null } catch (e) { emotionContext = null }
    const data = await chat(text, emotionContext, history)
    turns.value.push({ role: 'assistant', content: data.answer || '（无回答）' })
    if (data.riskLevel != null) {
      sessionRisk = data.riskLevel
      sessionRiskReason = data.riskReason || ''
    }
  } catch (e) {
    error.value = '处理失败：' + e.message
    turns.value = turns.value.filter(t => t.role !== 'assistant')
    if (turns.value.length && turns.value[turns.value.length - 1].role === 'user') {
      turns.value.pop()
    }
  } finally {
    processing.value = false
  }
}

async function endSession() {
  if (processing.value || !turns.value.length) return
  processing.value = true
  error.value = ''
  try {
    const turnsPayload = turns.value.map(t => ({ role: t.role, content: t.content, emotion: t.emotion || '' }))
    report.value = await analysisSession(turnsPayload, sessionRisk, sessionRiskReason)
  } catch (e) {
    error.value = '生成心理分析失败：' + e.message
  } finally {
    processing.value = false
  }
}
</script>

<style scoped>
.title { font-size: 18px; }
.sub { color: #6b7280; font-size: 12px; margin: 6px 0 14px; line-height: 1.6; }
.layout { display: flex; gap: 14px; flex-wrap: wrap; }
.video-box { flex: 1; min-width: 240px; background: #111827; border-radius: 12px; min-height: 180px; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.video { width: 100%; max-height: 280px; }
.placeholder { color: #6b7280; font-size: 13px; padding: 50px 0; }
.chat-panel { flex: 1.2; min-width: 260px; max-height: 300px; overflow-y: auto; background: #f9fafb; border-radius: 12px; padding: 10px; }
.muted { color: #9ca3af; font-size: 13px; text-align: center; padding: 40px 0; }
.bubble { margin-bottom: 8px; max-width: 95%; }
.bubble.user { margin-left: auto; text-align: right; }
.bubble.assistant { margin-right: auto; text-align: left; }
.who { font-size: 11px; color: #6b7280; margin-bottom: 2px; }
.emo { background: #fef3c7; color: #92400e; border-radius: 6px; padding: 0 5px; margin-left: 4px; font-size: 10px; }
.content { display: inline-block; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 8px 10px; font-size: 13px; line-height: 1.6; text-align: left; white-space: pre-wrap; word-break: break-word; }
.bubble.user .content { background: #6366f1; color: #fff; border: none; }
.controls { display: flex; gap: 10px; margin-top: 12px; }
.controls button { flex: 1; }
button.danger { background: #dc2626; }
.rec-tip { color: #dc2626; font-size: 13px; margin-top: 10px; animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: .3; } }
.report { margin-top: 18px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 16px; }
.report h3 { font-size: 16px; margin-bottom: 10px; }
.mood-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-bottom: 10px; }
.mood-badge.negative { background: #fff1f2; color: #be123c; }
.mood-badge.positive { background: #ecfdf5; color: #047857; }
.mood-badge.neutral { background: #f3f4f6; color: #374151; }
.report-row { font-size: 13px; color: #374151; line-height: 1.7; margin-top: 6px; }
.report-row ul { margin: 4px 0 0 18px; }
.feedback { margin-top: 10px; background: #fff; border-radius: 10px; padding: 12px; font-size: 14px; line-height: 1.8; color: #1f2937; }
.error { background: #fef2f2; color: #b91c1c; border-radius: 10px; padding: 12px; font-size: 13px; margin-top: 12px; }
</style>
