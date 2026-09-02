<template>
  <div>
    <h2 class="title">🎥 视频对话</h2>
    <p class="sub">录制一段你想说的话（语音+表情），系统提取转写文本与情绪特征后交给 Agent 综合研判。</p>

    <div class="video-box">
      <video ref="videoEl" autoplay playsinline muted class="video"></video>
      <div v-if="!streamOn" class="placeholder">摄像头未开启</div>
    </div>

    <div class="controls">
      <button v-if="!streamOn" class="secondary" @click="openCamera">📷 打开摄像头</button>
      <template v-else>
        <button v-if="!recording" class="secondary" @click="startRecord">⏺ 开始录制</button>
        <button v-if="recording" @click="stopAndAnalyze">⏹ 停止并分析</button>
        <button class="secondary" @click="closeCamera">关闭摄像头</button>
      </template>
    </div>

    <div v-if="recording" class="rec-tip">🔴 录制中…（表情帧与语音将一并分析）</div>

    <div v-if="analysis" class="block">
      <div class="label">🗣️ 转写文本</div>
      <div class="answer">{{ analysis.text || '（未识别到语音）' }}</div>
      <div class="label" style="margin-top:12px;">📊 情绪特征</div>
      <div class="answer small">{{ analysis.features_json || '（无）' }}</div>
      <div v-if="analysis.emotion_label" class="answer small">
        😊 表情：{{ analysis.emotion_label }}（微笑 {{ analysis.smile_score }}）<br>
        ⏱️ 语速 {{ analysis.speech_rate_chars_per_sec }} 字/秒 · 停顿 {{ analysis.pause_count }} 次
      </div>
      <button class="secondary" style="margin-top:12px;" :disabled="analyzing"
              @click="sendToAgent">{{ analyzing ? '综合研判中…' : '发送给 Agent 综合研判' }}</button>
    </div>

    <div v-if="agentResult" class="block">
      <div class="label">🤖 Agent 回答</div>
      <div class="answer">{{ agentResult }}</div>
      <RiskBanner :risk-level="riskLevel" :reason="riskReason" />
    </div>

    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { chat, multimodalAnalyze } from '../api'
import { blobToWav } from '../utils/wav'
import RiskBanner from './RiskBanner.vue'

const videoEl = ref(null)
const streamOn = ref(false)
const recording = ref(false)
const analysis = ref(null)
const agentResult = ref('')
const riskLevel = ref(null)
const riskReason = ref('')
const analyzing = ref(false)
const error = ref('')

let mediaStream = null
let recorder = null
let chunks = []
let latestFrame = null
let frameTimer = null

async function openCamera() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
    streamOn.value = true
    await nextTick()
    videoEl.value.srcObject = mediaStream
  } catch (e) {
    error.value = '无法打开摄像头/麦克风：' + e.message
  }
}

function closeCamera() {
  stopRecordingInternal()
  if (mediaStream) mediaStream.getTracks().forEach(t => t.stop())
  mediaStream = null
  streamOn.value = false
  analysis.value = null
  agentResult.value = ''
  riskLevel.value = null
}

function startRecord() {
  if (!mediaStream) return
  chunks = []
  latestFrame = null
  const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus')
    ? 'video/webm;codecs=vp9,opus'
    : 'video/webm'
  recorder = new MediaRecorder(mediaStream, { mimeType: mime })
  recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data) }
  recorder.start(1000)
  recording.value = true
  // 每 3 秒抓一帧，保留最新表情帧
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

async function stopAndAnalyze() {
  if (!recorder) return
  await new Promise(resolve => {
    recorder.onstop = resolve
    recorder.stop()
  })
  stopRecordingInternal()
  captureFrame()
  const videoBlob = new Blob(chunks, { type: 'video/webm' })
  if (!videoBlob.size) { error.value = '没有录到内容，请重试'; return }

  error.value = ''
  analysis.value = null
  try {
    // 提取音频 -> WAV，供 Whisper 转写
    const wavBlob = await blobToWav(videoBlob)
    const result = await multimodalAnalyze(wavBlob, latestFrame)
    analysis.value = result
  } catch (e) {
    error.value = '多模态分析失败：' + e.message
  }
}

function stopRecordingInternal() {
  if (frameTimer) { clearInterval(frameTimer); frameTimer = null }
  recording.value = false
  recorder = null
}

async function sendToAgent() {
  if (!analysis.value || analyzing.value) return
  analyzing.value = true
  error.value = ''
  agentResult.value = ''
  riskLevel.value = null
  try {
    let emotionContext = null
    try { emotionContext = JSON.parse(analysis.value.features_json) } catch (e) { emotionContext = null }
    const data = await chat(analysis.value.text || '（无语音内容）', emotionContext)
    agentResult.value = data.answer || '（无回答）'
    riskLevel.value = data.riskLevel
    riskReason.value = data.riskReason || ''
  } catch (e) {
    error.value = '对话失败：' + e.message
  } finally {
    analyzing.value = false
  }
}

</script>

<style scoped>
.title { font-size: 18px; }
.sub { color: #6b7280; font-size: 12px; margin: 6px 0 14px; }
.video-box { position: relative; background: #111827; border-radius: 12px; min-height: 200px; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.video { width: 100%; max-height: 320px; }
.placeholder { color: #6b7280; font-size: 14px; padding: 60px 0; }
.controls { display: flex; gap: 10px; margin-top: 12px; }
.controls button { flex: 1; }
.rec-tip { color: #dc2626; font-size: 13px; margin-top: 10px; animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: .3; } }
.block { margin-top: 18px; }
.label { font-size: 13px; color: #6b7280; margin-bottom: 8px; }
.answer { background: #f9fafb; border-radius: 10px; padding: 12px; font-size: 14px; line-height: 1.7; white-space: pre-wrap; }
.answer.small { font-size: 13px; margin-top: 8px; }
.error { background: #fef2f2; color: #b91c1c; border-radius: 10px; padding: 12px; font-size: 13px; margin-top: 12px; }
</style>
