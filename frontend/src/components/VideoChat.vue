<template>
  <section class="view">
    <div class="pane">
      <header class="topbar">
        <div>
          <h2 class="topbar-title">实时对话</h2>
          <div class="topbar-meta">持续聆听 · 说完自动接话 · 可随时打断</div>
        </div>
        <div class="grow"></div>
        <span class="chip">
          <span class="dot" :class="{ live: streamOn }" aria-hidden="true"></span>
          {{ statusText }}
        </span>
      </header>

      <!-- 画面 -->
      <div class="frame">
        <video ref="videoEl" autoplay playsinline muted class="video"></video>

        <div v-if="!streamOn" class="frame-empty">
          <div class="frame-empty-icon"><Icon name="video" size="l" /></div>
          <div class="frame-empty-title">开始一段面对面的聊天</div>
          <p class="frame-empty-sub">
            开启后我会一直听着，你停下来我就接话，也可以随时打断我
          </p>
          <button class="btn btn-p" type="button" @click="startSession">
            <Icon name="play" size="s" />开始对话
          </button>
          <p class="frame-empty-tip">建议戴耳机，避免我的声音被麦克风收进去</p>
        </div>

        <template v-else>
          <div class="rec" :class="phase">
            <i aria-hidden="true"></i>{{ phaseLabel }}
          </div>

          <div v-if="liveText" class="live-caption">{{ liveText }}</div>

          <div class="tags">
            <span v-if="lastMetrics.emotionLabel" class="tag">表情 · {{ lastMetrics.emotionLabel }}</span>
            <span v-if="lastMetrics.speechRate" class="tag">语速 · {{ speechRateText }}</span>
            <span v-if="lastMetrics.pauseCount !== null" class="tag">停顿 · {{ lastMetrics.pauseCount }} 次</span>
          </div>

          <div class="wave" aria-hidden="true">
            <i v-for="(h, i) in levelBars" :key="i" :style="{ height: `${h}%` }"></i>
          </div>
        </template>
      </div>

      <!-- 实时控制条 -->
      <div v-if="streamOn" class="live-bar">
        <div class="live-state">
          <span class="live-dot" :class="phase" aria-hidden="true"></span>
          <span class="live-text">{{ hintText }}</span>
        </div>
        <button type="button" class="toggle" :class="{ off: !listening }" @click="listening = !listening">
          <Icon :name="listening ? 'mic' : 'close'" size="s" />{{ listening ? '正在聆听' : '已暂停聆听' }}
        </button>
        <button type="button" class="toggle" :class="{ off: !ttsOn }" @click="toggleTts">
          <Icon name="volume" size="s" />{{ ttsOn ? '语音朗读' : '仅文字' }}
        </button>
        <template v-if="ttsOn">
          <button type="button" class="toggle" :class="{ off: ttsPrefs.engine !== 'backend' }"
                  title="云端音色更自然，需要后端语音服务" @click="toggleEngine">
            <Icon name="volume" size="s" />{{ ttsPrefs.engine === 'backend' ? '云端音色' : '系统音色' }}
          </button>
          <select v-if="ttsPrefs.engine !== 'backend'" v-model="pickedVoice" class="voice-select" aria-label="选择朗读音色">
            <option v-for="v in voices" :key="v.name" :value="v.name">
              {{ v.name }}（{{ v.lang }}）
            </option>
            <option v-if="!voices.length" value="">系统默认</option>
          </select>
          <button type="button" class="toggle" @click="previewVoice">
            <Icon name="play" size="s" />试听
          </button>
        </template>
      </div>

      <!-- 对话记录 -->
      <div class="turns">
        <div v-if="!turns.length" class="turns-empty muted">
          {{ streamOn ? '说点什么吧，你说完我会接话' : '对话记录会显示在这里' }}
        </div>
        <div v-for="(t, i) in turns" :key="i" class="turn" :class="t.role === 'user' ? 'me' : 'ag'">
          <div class="turn-main">
            <div class="turn-who">
              {{ t.role === 'user' ? '你' : 'Agent' }}
              <span v-if="t.emotion" class="who-tag">{{ t.emotion }}</span>
              <span v-if="t.meta" class="who-meta">{{ t.meta }}</span>
            </div>
            <div class="turn-text">
              {{ t.content }}<span v-if="t.streaming" class="caret" aria-hidden="true"></span>
            </div>
          </div>
        </div>
        <div v-if="phase === 'thinking' && !streamingNow" class="turn ag">
          <div class="turn-main">
            <div class="turn-who">Agent</div>
            <div class="turn-text processing">
              <span class="spinner" aria-hidden="true"></span>正在理解你刚才说的话…
            </div>
          </div>
        </div>
      </div>

      <div class="controls">
        <template v-if="streamOn">
          <button class="btn btn-g" type="button" :disabled="busy || !turns.length" @click="endSession">
            <Icon name="doc" size="s" />结束并生成心理分析
          </button>
          <button class="btn btn-q" type="button" @click="stopSession">结束对话</button>
        </template>
      </div>

      <!-- 心理分析报告 -->
      <div v-if="report" class="report card">
        <div class="report-head">
          <h3>心理分析报告</h3>
          <span class="mood" :class="report.overallMood">{{ moodText(report.overallMood) }}</span>
        </div>
        <div class="report-row"><span class="report-k">情绪变化</span><span class="report-v">{{ report.emotionTrend }}</span></div>
        <div class="report-row">
          <span class="report-k">主要议题</span>
          <span class="report-v">{{ (report.mainIssues || []).join('、') || '—' }}</span>
        </div>
        <RiskBanner :risk-level="report.riskLevel" :reason="report.riskReason" />
        <p class="report-feedback">{{ report.feedback }}</p>
        <div v-if="report.suggestions && report.suggestions.length" class="report-sug">
          <div class="report-k">可以试试</div>
          <ul>
            <li v-for="(sg, i) in report.suggestions" :key="i"><Icon name="check" size="s" />{{ sg }}</li>
          </ul>
        </div>
      </div>

      <div v-if="error" class="error-wrap">
        <div class="error-box" role="alert"><Icon name="warn" size="s" /><span>{{ error }}</span></div>
      </div>
    </div>

    <aside class="side">
      <div class="side-block">
        <div class="side-head"><h3>实时研判</h3><span class="side-sub">{{ userTurns }} 轮发言</span></div>
        <div class="card kv-card">
          <div class="kv">
            <span class="kv-k">当前风险</span>
            <span v-if="sessionRisk !== null" class="pill" :class="`pill-${riskMeta(sessionRisk).tone}`">
              <Icon name="warn" size="s" />{{ sessionRisk }} / 3 {{ riskMeta(sessionRisk).label }}
            </span>
            <span v-else class="kv-v muted">待评估</span>
          </div>
          <div class="kv">
            <span class="kv-k">情绪倾向</span>
            <span class="kv-v">{{ lastMetrics.emotionLabel || '—' }}</span>
          </div>
          <div class="kv">
            <span class="kv-k">人脸检测</span>
            <span class="kv-v">{{ lastMetrics.faceChecked ? (lastMetrics.faceDetected ? '已捕获' : '未检测到') : '—' }}</span>
          </div>
        </div>
      </div>

      <div class="side-block">
        <div class="side-head"><h3>情绪曲线</h3><span class="side-sub">微笑程度</span></div>
        <div class="card chart-card">
          <svg class="chart" viewBox="0 0 260 56" preserveAspectRatio="none" aria-hidden="true">
            <defs>
              <linearGradient id="emoFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#2E7D6F" stop-opacity=".22" />
                <stop offset="100%" stop-color="#2E7D6F" stop-opacity="0" />
              </linearGradient>
            </defs>
            <path :d="areaPath" fill="url(#emoFill)" />
            <path :d="linePath" fill="none" stroke="#2E7D6F" stroke-width="2"
                  stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <div class="chart-axis">
            <span>{{ emotionSeries.length ? '较早' : '开始对话后显示' }}</span>
            <span v-if="emotionSeries.length">当前</span>
          </div>
        </div>
      </div>

      <div class="side-block">
        <div class="side-head"><h3>语音特征</h3></div>
        <div class="metrics">
          <div class="card metric"><div class="metric-n">{{ speechRateText || '—' }}</div><div class="metric-l">语速</div></div>
          <div class="card metric"><div class="metric-n">{{ lastMetrics.pauseCount === null ? '—' : lastMetrics.pauseCount }}</div><div class="metric-l">停顿次数</div></div>
          <div class="card metric"><div class="metric-n">{{ lastMetrics.duration === null ? '—' : `${lastMetrics.duration}s` }}</div><div class="metric-l">本次时长</div></div>
          <div class="card metric"><div class="metric-n">{{ lastMetrics.tilt === null ? '—' : `${lastMetrics.tilt}°` }}</div><div class="metric-l">头部倾斜</div></div>
        </div>
      </div>

      <div class="side-block">
        <div class="side-head"><h3>这一刻可以做的</h3></div>
        <div class="card prose">
          <template v-if="sessionRisk !== null && sessionRisk >= 2">
            已经出现需要关注的信号。<b>不必独自扛着</b>——左下角的热线可以直接拨打，
            也请联系一位你信任的人陪你待一会儿。
          </template>
          <template v-else-if="turns.length">
            目前未达预警阈值，我会继续陪你聊。想停下来的时候，直接说「等一下」我就会停。
          </template>
          <template v-else>
            开启后我会一直听着。你随时可以点「已暂停聆听」，我一声都不会听。
          </template>
        </div>
      </div>
    </aside>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import Icon from './ui/Icon.vue'
import RiskBanner from './RiskBanner.vue'
import { multimodalAnalyze, analysisSession, streamChat } from '../api'
import { blobToWav } from '../utils/wav'
import { plainText } from '../utils/text'
import { speakOnce } from '../utils/tts'
import { addRiskRecord, riskMeta, saveTtsPrefs, ttsPrefs } from '../store'

/* ============ 可调参数 ============ */
const SPEECH_RMS = 0.055        // 判定「有人在说话」的音量阈值
const SILENCE_MS = 900          // 停顿多久算一句话说完
const MIN_SPEECH_MS = 350       // 短于这个时长视为噪音
const BARGE_IN_RMS = 0.055      // 打断我的音量阈值：正常说话即可，不用喊
const BARGE_IN_GUARD_MS = 700   // 一轮结束后短暂忽略，避免尾音立刻打断自己
const EMOTION_EVERY_MS = 2500   // 表情采样间隔

const paneEl = ref(null)
const videoEl = ref(null)
const streamOn = ref(false)
const listening = ref(true)
const ttsOn = ref(true)
const phase = ref('idle')       // idle | listening | thinking | speaking
const liveText = ref('')
const turns = ref([])
const report = ref(null)
const error = ref('')
const levelBars = ref(new Array(10).fill(6))
const micLevel = ref(0)
const emotionSeries = ref([])
const lastMetrics = reactive({
  emotionLabel: '', speechRate: null, pauseCount: null,
  duration: null, tilt: null, faceChecked: false, faceDetected: false
})

let mediaStream = null
let audioCtx = null
let analyser = null
let levelData = null
let vadRaf = null
let barsTimer = null
let emotionTimer = null
let recorder = null
let chunks = []
let latestFrame = null
let latestFrameAt = 0
let controller = null
let sessionRisk = null
let sessionRiskReason = ''
let speaking = false
let speechStartedAt = 0
let lastVoiceAt = 0
let utteranceStartedAt = 0
let streamingNow = ref(false)
let lastUtteranceEndAt = 0
let ttsPending = 0          // 未播完的句子数
let speechEpoch = 0         // 每次打断自增，旧的朗读回调自动作废
let turnSeq = 0             // 轮次令牌：打断后，上一轮的处理结果全部作废

/** 语音列表（Chrome 首次为空，需等 voiceschanged） */
const voices = ref([])
const pickedVoice = ref('')

/** macOS 自带的趣味音效，中文场景下听起来很怪，直接排除 */
const NOVELTY = /^(Eddy|Flo|Grandma|Grandpa|Reed|Rocko|Sandy|Shelley|Junior|Ralph|Fred|Bahh|Bells|Boing|Bubble|Bubbles|Cellos|Jester|Organ|Superstar|Trinoids|Whisper|Wobble|Zarvox|Albert|Bad News|Good News|Deranged|Hysterical|Pipe Organ)/i

function loadVoices() {
  if (!window.speechSynthesis) return
  const all = window.speechSynthesis.getVoices() || []
  const zh = all.filter(v => v.lang && v.lang.toLowerCase().startsWith('zh'))
  const score = v => {
    const name = v.name || ''
    let sc = 0
    if (/Tingting|婷婷|Ting-Ting/i.test(name)) sc += 100   // macOS 上最自然的中文音色
    if (/zh[-_]CN/i.test(v.lang)) sc += 30
    else if (/zh[-_]TW/i.test(v.lang)) sc += 10
    else if (/zh[-_]HK/i.test(v.lang)) sc += 5
    if (v.localService) sc += 6
    if (NOVELTY.test(name)) sc -= 90
    return sc
  }
  const sorted = zh.slice().sort((a, b) => score(b) - score(a))
  voices.value = sorted
  if (!pickedVoice.value && sorted.length) pickedVoice.value = sorted[0].name
}

/* ============ 派生状态 ============ */
const busy = computed(() => phase.value === 'thinking')
const userTurns = computed(() => turns.value.filter(t => t.role === 'user').length)
const statusText = computed(() => {
  if (!streamOn.value) return '未开启'
  return { idle: '待命', listening: '聆听中', thinking: '思考中', speaking: '说话中' }[phase.value] || '待命'
})
const phaseLabel = computed(() => statusText.value)
const hintText = computed(() => {
  if (!listening.value) return '已暂停聆听，我不会听你说话'
  return {
    idle: '我在听',
    listening: '我在听，说完停一下就好',
    thinking: '让我想一下…',
    speaking: '正在说话，你可以随时打断我'
  }[phase.value] || '我在听'
})
const speechRateText = computed(() => {
  const r = lastMetrics.speechRate
  return r ? `${Math.round(r * 60)} 字/分` : ''
})
const linePath = computed(() => {
  const n = emotionSeries.value.length
  if (!n) return ''
  const step = n > 1 ? 256 / (n - 1) : 0
  return emotionSeries.value
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${(4 + i * step).toFixed(1)},${(50 - p.v * 42).toFixed(1)}`)
    .join(' ')
})
const areaPath = computed(() => {
  const d = linePath.value
  if (!d) return ''
  const n = emotionSeries.value.length
  const step = n > 1 ? 256 / (n - 1) : 0
  const lastX = (4 + (n - 1) * step).toFixed(1)
  return `${d} L${lastX},56 L4,56 Z`
})

/* ============ 开启 / 关闭 ============ */
async function startSession() {
  error.value = ''
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 } },
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    })
    streamOn.value = true
    loadVoices()
    turns.value = []
    report.value = null
    sessionRisk = null
    sessionRiskReason = ''
    emotionSeries.value = []
    await nextTick()
    if (videoEl.value) videoEl.value.srcObject = mediaStream
    setupAudio()
    startVad()
    phase.value = 'listening'
    startEmotionSampling()
  } catch (e) {
    error.value = `无法打开摄像头或麦克风：${e.message}`
  }
}

function setupAudio() {
  const Ctx = window.AudioContext || window.webkitAudioContext
  if (!Ctx) return
  audioCtx = new Ctx()
  const source = audioCtx.createMediaStreamSource(mediaStream)
  analyser = audioCtx.createAnalyser()
  analyser.fftSize = 1024
  source.connect(analyser)
  levelData = new Uint8Array(analyser.fftSize)
  barsTimer = setInterval(updateBars, 90)
}

function readLevel() {
  if (!analyser || !levelData) return 0
  analyser.getByteTimeDomainData(levelData)
  let sum = 0
  for (let i = 0; i < levelData.length; i += 1) {
    const v = (levelData[i] - 128) / 128
    sum += v * v
  }
  return Math.sqrt(sum / levelData.length)
}

function updateBars() {
  const level = Math.min(1, micLevel.value * 3.4)
  levelBars.value = levelBars.value.map((h, i) => {
    const jitter = 0.55 + Math.abs(Math.sin(Date.now() / 240 + i)) * 0.45
    const target = 6 + level * 92 * jitter
    return Math.max(6, Math.min(100, h * 0.55 + target * 0.45))
  })
}

/* ============ VAD：自动断句 & 打断 ============ */
function startVad() {
  const loop = () => {
    vadRaf = requestAnimationFrame(loop)
    const level = readLevel()
    micLevel.value = level
    if (!listening.value) return

    const now = performance.now()
    // 「我在忙」包括：正在想、正在说、还有句子没播完
    const busyNow = phase.value === 'thinking' || phase.value === 'speaking' || ttsPending > 0
    const threshold = busyNow ? Math.max(SPEECH_RMS, BARGE_IN_RMS) : SPEECH_RMS

    if (level > threshold) {
      if (busyNow && !speaking && now - lastUtteranceEndAt > BARGE_IN_GUARD_MS) {
        bargeIn()
      }
      if (!speaking) {
        speaking = true
        speechStartedAt = now
        onSpeechStart()
      }
      lastVoiceAt = now
    } else if (speaking && now - lastVoiceAt > SILENCE_MS) {
      speaking = false
      lastUtteranceEndAt = now
      const duration = now - speechStartedAt
      if (duration >= MIN_SPEECH_MS) onSpeechEnd(duration)
      else abortUtterance()
    }
  }
  vadRaf = requestAnimationFrame(loop)
}

function onSpeechStart() {
  liveText.value = ''
  startRecorder()
}

function onSpeechEnd() {
  stopRecorder().then(blob => {
    if (!blob || !blob.size) {
      if (phase.value === 'listening') phase.value = 'listening'
      return
    }
    handleUtterance(blob)
  })
}

function abortUtterance() {
  try { if (recorder && recorder.state !== 'inactive') recorder.stop() } catch (e) { /* 忽略 */ }
  recorder = null
  chunks = []
}

/* ============ 录音（每句话一段） ============ */
function pickMime() {
  const list = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
  for (const m of list) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported(m)) return m
  }
  return ''
}

function startRecorder() {
  if (!mediaStream || (recorder && recorder.state === 'recording')) return
  chunks = []
  utteranceStartedAt = performance.now()
  try {
    const audioOnly = new MediaStream(mediaStream.getAudioTracks())
    const mime = pickMime()
    recorder = mime ? new MediaRecorder(audioOnly, { mimeType: mime }) : new MediaRecorder(audioOnly)
    recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data) }
    recorder.start()
  } catch (e) {
    recorder = null
  }
}

function stopRecorder() {
  return new Promise(resolve => {
    const rec = recorder
    if (!rec || rec.state === 'inactive') { resolve(null); return }
    rec.onstop = () => {
      const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' })
      recorder = null
      chunks = []
      resolve(blob)
    }
    try { rec.stop() } catch (e) { resolve(null) }
  })
}

/* ============ 一轮完整交互 ============ */
async function handleUtterance(audioBlob) {
  const myTurn = ++turnSeq
  phase.value = 'thinking'
  liveText.value = '正在识别…'
  error.value = ''
  try {
    captureFrame()
    if (latestFrame && performance.now() - latestFrameAt > 400) {
      await new Promise(r => setTimeout(r, 200))
    }
    const wav = await blobToWav(audioBlob)
    const mm = await multimodalAnalyze(wav, latestFrame)
    if (myTurn !== turnSeq) return          // 这几秒里用户已经开口，本轮作废
    const text = (mm.text || '').trim()
    liveText.value = ''
    if (!text) {
      if (streamOn.value) phase.value = 'listening'
      return
    }

    applyMetrics(mm)
    const emotionLabel = mm.emotion_label || ''
    turns.value.push({
      role: 'user',
      content: text,
      emotion: emotionLabel,
      meta: speechMeta(mm)
    })
    const history = turns.value.slice(0, -1).map(t => ({ role: t.role, content: t.content }))
    let emotionContext = null
    try { emotionContext = mm.features_json ? JSON.parse(mm.features_json) : null } catch (e) { emotionContext = null }

    const turn = { role: 'assistant', content: '', streaming: true }
    turns.value.push(turn)
    scrollToEnd()
    streamingNow.value = true
    phase.value = 'speaking'
    const epoch = ++speechEpoch   // 本轮朗读凭证；被打断后此凭证作废

    controller = new AbortController()
    let acc = ''
    let spoken = 0
    await streamChat({
      question: text,
      emotionContext,
      history,
      signal: controller.signal,
      onToken: (piece) => {
        if (myTurn !== turnSeq) return       // 已被打断，忽略残留的增量
        acc += piece
        turn.content = plainText(acc)
        scrollToEnd()
        // 按句朗读：凑满一个完整句子、且够长时才读，避免碎句听起来一顿一顿
        const tail = acc.slice(spoken)
        const cut = Math.max(tail.lastIndexOf('。'), tail.lastIndexOf('！'), tail.lastIndexOf('？'))
        // 至少凑够 24 字再读，避免一顿一顿的机械感
        if (cut >= 24 || tail.length >= 70) {
          const end = cut >= 24 ? cut + 1 : tail.length
          const sentence = tail.slice(0, end)
          spoken += end
          speak(plainText(sentence), epoch)
        }
      },
      onMeta: (meta) => {
        if (myTurn !== turnSeq) return
        turn.sources = meta.sources || []
        if (meta.riskLevel !== null && meta.riskLevel !== undefined) {
          sessionRisk = meta.riskLevel
          sessionRiskReason = meta.riskReason || ''
          addRiskRecord({ level: sessionRisk, reason: sessionRiskReason, message: text, source: '实时对话' })
        }
      }
    })
    const rest = acc.slice(spoken)
    if (rest.trim()) speak(plainText(rest), epoch)
    turn.streaming = false
    turn.content = plainText(acc)
    if (!turn.content) turn.content = '（没有生成回答）'
  } catch (e) {
    if (e.name === 'AbortError') {
      const t = turns.value[turns.value.length - 1]
      if (t && t.role === 'assistant') t.streaming = false
    } else {
      error.value = `处理失败：${e.message}`
      const t = turns.value[turns.value.length - 1]
      if (t && t.role === 'assistant' && !t.content) turns.value.pop()
    }
  } finally {
    if (myTurn === turnSeq) {
      streamingNow.value = false
      controller = null
      liveText.value = ''
      // 文字流结束不代表"说完了"，语音可能还在播；由 finishTurnIfIdle 决定何时回到聆听
      finishTurnIfIdle()
    }
  }
}

/** 打断：停朗读 + 中断生成 + 切回聆听 */
function bargeIn() {
  turnSeq += 1                         // 旧轮次的后续处理全部作废
  stopSpeaking()                       // 内部会自增 speechEpoch，本轮后续朗读全部作废
  if (controller) {
    controller.abort()
    controller = null
  }
  const t = turns.value[turns.value.length - 1]
  if (t && t.role === 'assistant') t.streaming = false
  streamingNow.value = false
  phase.value = 'listening'
  liveText.value = ''
}

/** 流结束且朗读也播完后，才回到聆听状态 */
function finishTurnIfIdle() {
  if (streamingNow.value || ttsPending > 0) return
  if (window.speechSynthesis && window.speechSynthesis.speaking) return
  if (streamOn.value && phase.value === 'speaking') phase.value = 'listening'
}

/* ============ 语音朗读 ============ */
/**
 * 朗读：顺序队列 + pump（云端 Audio 元素不串行，必须排队保证逐句顺序）。
 * epoch 用于打断：一旦被打断（speechEpoch 自增），队列里旧轮次的句子全部作废。
 */
const ttsQueue = []
let ttsPlaying = false
let ttsCurrent = null

function speak(text, epoch) {
  if (!ttsOn.value || !text) return
  if (epoch !== undefined && epoch !== speechEpoch) return
  ttsQueue.push({ text, epoch })
  pumpTts()
}

function pumpTts() {
  if (ttsPlaying) return
  const next = ttsQueue.shift()
  if (!next) {
    finishTurnIfIdle()
    return
  }
  if (next.epoch !== speechEpoch) {
    pumpTts()
    return
  }
  ttsPlaying = true
  ttsPending += 1
  const systemVoice = voices.value.find(x => x.name === pickedVoice.value)
  ttsCurrent = speakOnce(next.text, {
    ...ttsPrefs.value,
    // 系统音色时沿用本页手动选的音色（云端音色忽略该字段）
    ...(ttsPrefs.value.engine !== 'backend' && systemVoice ? { voice: systemVoice.name } : {}),
    onEnd: () => {
      ttsPlaying = false
      ttsPending = Math.max(0, ttsPending - 1)
      ttsCurrent = null
      pumpTts()
    }
  })
}

function stopSpeaking() {
  speechEpoch += 1
  ttsQueue.length = 0
  ttsPlaying = false
  ttsPending = 0
  if (ttsCurrent) {
    ttsCurrent.stop()
    ttsCurrent = null
  }
  try { window.speechSynthesis.cancel() } catch (e) { /* 忽略 */ }
}

/** 试听当前音色 */
function previewVoice() {
  stopSpeaking()
  const epoch = speechEpoch
  speak('你好，我是你的陪伴助手。今天感觉怎么样？', epoch)
}

function toggleTts() {
  ttsOn.value = !ttsOn.value
  if (!ttsOn.value) stopSpeaking()
}

/** 云端音色 <-> 系统音色切换 */
function toggleEngine() {
  ttsPrefs.value = {
    ...ttsPrefs.value,
    engine: ttsPrefs.value.engine === 'backend' ? 'system' : 'backend'
  }
  saveTtsPrefs()
  stopSpeaking()
}

/* ============ 表情采样 ============ */
function startEmotionSampling() {
  emotionTimer = setInterval(async () => {
    if (!streamOn.value || phase.value === 'thinking') return
    captureFrame()
    if (!latestFrame) return
    try {
      const mm = await multimodalAnalyze(null, latestFrame)
      applyMetrics(mm)
      if (typeof mm.smile_score === 'number') {
        emotionSeries.value = [...emotionSeries.value, { v: mm.smile_score }].slice(-24)
      }
    } catch (e) { /* 采样失败忽略 */ }
  }, EMOTION_EVERY_MS)
}

function captureFrame() {
  const video = videoEl.value
  if (!video || !video.videoWidth) return
  const canvas = document.createElement('canvas')
  const scale = Math.min(1, 480 / video.videoWidth)
  canvas.width = Math.round(video.videoWidth * scale)
  canvas.height = Math.round(video.videoHeight * scale)
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
  canvas.toBlob(b => { latestFrame = b; latestFrameAt = performance.now() }, 'image/jpeg', 0.82)
}

function applyMetrics(mm) {
  lastMetrics.emotionLabel = mm.emotion_label || lastMetrics.emotionLabel
  if (mm.speech_rate_chars_per_sec !== undefined) lastMetrics.speechRate = mm.speech_rate_chars_per_sec
  if (mm.pause_count !== undefined) lastMetrics.pauseCount = mm.pause_count
  if (mm.duration_sec !== undefined) lastMetrics.duration = mm.duration_sec
  if (mm.head_tilt_deg !== undefined) lastMetrics.tilt = mm.head_tilt_deg
  if (mm.face_detected !== undefined) {
    lastMetrics.faceChecked = true
    lastMetrics.faceDetected = mm.face_detected === true
  }
}

function speechMeta(mm) {
  const parts = []
  if (mm.duration_sec) parts.push(`${mm.duration_sec}s`)
  if (mm.speech_rate_chars_per_sec) parts.push(`${Math.round(mm.speech_rate_chars_per_sec * 60)} 字/分`)
  if (mm.pause_count) parts.push(`停顿 ${mm.pause_count} 次`)
  return parts.join(' · ')
}

function moodText(m) {
  if (m === 'negative') return '整体情绪偏负面'
  if (m === 'positive') return '整体情绪积极'
  return '情绪中性'
}

async function scrollToEnd() {
  await nextTick()
  const el = paneEl.value
  if (el) el.scrollTop = el.scrollHeight
}

/* ============ 结束 ============ */
async function endSession() {
  if (phase.value === 'thinking' || !turns.value.length) return
  phase.value = 'thinking'
  error.value = ''
  try {
    const payload = turns.value.map(t => ({ role: t.role, content: t.content, emotion: t.emotion || '' }))
    const r = await analysisSession(payload, sessionRisk, sessionRiskReason)
    report.value = {
      ...r,
      emotionTrend: plainText(r.emotionTrend),
      feedback: plainText(r.feedback),
      riskReason: plainText(r.riskReason),
      mainIssues: (r.mainIssues || []).map(plainText),
      suggestions: (r.suggestions || []).map(plainText)
    }
  } catch (e) {
    error.value = `生成心理分析失败：${e.message}`
  } finally {
    if (streamOn.value) phase.value = 'listening'
  }
}

function stopSession() {
  stopSpeaking()
  if (controller) controller.abort()
  streamOn.value = false
  phase.value = 'idle'
  clearTimers()
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop())
    mediaStream = null
  }
  if (audioCtx) { audioCtx.close(); audioCtx = null }
  analyser = null
}

function clearTimers() {
  if (vadRaf) { cancelAnimationFrame(vadRaf); vadRaf = null }
  if (barsTimer) { clearInterval(barsTimer); barsTimer = null }
  if (emotionTimer) { clearInterval(emotionTimer); emotionTimer = null }
  speaking = false
  levelBars.value = new Array(10).fill(6)
}

function onVoicesChanged() {
  loadVoices()
}

onMounted(() => {
  loadVoices()
  if (window.speechSynthesis) {
    window.speechSynthesis.addEventListener('voiceschanged', onVoicesChanged)
    // 有些浏览器不会主动触发，补一次延迟加载
    setTimeout(loadVoices, 600)
  }
})

onBeforeUnmount(() => {
  if (window.speechSynthesis) {
    window.speechSynthesis.removeEventListener('voiceschanged', onVoicesChanged)
  }
  stopSession()
})
</script>

<style scoped>
.frame {
  position: relative; margin: 16px 20px 0; border-radius: 13px; overflow: hidden;
  background: #12171A; aspect-ratio: 16 / 10; flex: none;
}
.video { width: 100%; height: 100%; object-fit: cover; display: block; }
.frame-empty {
  position: absolute; inset: 0; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 6px; text-align: center; padding: 20px;
}
.frame-empty-icon {
  width: 44px; height: 44px; border-radius: 13px; display: grid; place-items: center;
  background: rgba(255, 255, 255, .08); color: #9FB3B0; margin-bottom: 6px;
}
.frame-empty-title { color: #E8EDEC; font-size: 14px; font-weight: 600; }
.frame-empty-sub { color: #8A9A97; font-size: 12px; margin-bottom: 12px; max-width: 320px; line-height: 1.7; }
.frame-empty-tip { color: #6F7F7C; font-size: 11px; margin-top: 10px; }

.rec {
  position: absolute; top: 12px; left: 12px; display: flex; align-items: center; gap: 7px;
  background: rgba(10, 14, 16, .62); border: 1px solid rgba(255, 255, 255, .14);
  color: #fff; padding: 5px 10px; border-radius: var(--r-full); font-size: 11px;
  backdrop-filter: blur(6px);
}
.rec i { width: 7px; height: 7px; border-radius: 50%; background: #7C8B88; }
.rec.listening i { background: #3ED598; animation: recblink 1.4s infinite; }
.rec.thinking i { background: #F0B429; animation: recblink 1s infinite; }
.rec.speaking i { background: #6FD3B6; animation: recblink .8s infinite; }
@keyframes recblink { 50% { opacity: .25; } }

.live-caption {
  position: absolute; left: 50%; bottom: 14px; transform: translateX(-50%);
  max-width: 86%; padding: 8px 14px; border-radius: 10px;
  background: rgba(10, 14, 16, .7); backdrop-filter: blur(6px);
  color: #EAF2F0; font-size: 13px; line-height: 1.6;
}

.tags { position: absolute; left: 12px; top: 52px; display: flex; gap: 7px; flex-wrap: wrap; max-width: 70%; }
.tag {
  background: rgba(10, 14, 16, .62); border: 1px solid rgba(255, 255, 255, .14);
  color: #E8EDEC; padding: 4px 9px; border-radius: var(--r-full); font-size: 11px;
  backdrop-filter: blur(6px);
}
.wave { position: absolute; right: 12px; bottom: 12px; display: flex; align-items: flex-end; gap: 2.5px; height: 24px; }
.wave i { width: 3px; border-radius: 99px; background: #6FD3B6; display: block; transition: height .09s linear; }

.live-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin: 14px 20px 0; padding: 10px 12px;
  border: 1px solid var(--line); border-radius: var(--r-m); background: var(--surface-2);
}
.live-state { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 150px; }
.live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--ink-3); flex: none; }
.live-dot.listening { background: #37A06E; box-shadow: 0 0 0 3px rgba(55, 160, 110, .16); }
.live-dot.thinking { background: #D9A21B; box-shadow: 0 0 0 3px rgba(217, 162, 27, .16); }
.live-dot.speaking { background: var(--primary); box-shadow: 0 0 0 3px rgba(46, 125, 111, .16); }
.live-text { font-size: 12.5px; color: var(--ink-2); }
.toggle {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 11px; border-radius: var(--r-full); border: 1px solid var(--line-2);
  font-size: 12px; color: var(--ink-2); background: var(--surface);
}
.toggle:hover { background: var(--surface-3); }
.toggle.off { color: var(--ink-3); border-style: dashed; }
.voice-select {
  max-width: 190px; padding: 6px 8px; font-size: 12px; color: var(--ink-2);
  border: 1px solid var(--line-2); border-radius: var(--r-full); background: var(--surface);
  outline: 0;
}
.voice-select:focus { border-color: var(--primary); }

.turns { padding: 16px 20px 4px; display: flex; flex-direction: column; gap: 12px; }
.turns-empty { text-align: center; padding: 18px 0; }
.turn { display: flex; gap: 10px; }
.turn.me .turn-main { margin-left: auto; }
.turn-main { max-width: min(560px, 88%); min-width: 0; }
.turn-who { display: flex; align-items: center; gap: 7px; font-size: 11.5px; color: var(--ink-3); margin-bottom: 4px; }
.turn.me .turn-who { justify-content: flex-end; }
.who-tag { background: var(--surface-3); border-radius: 5px; padding: 0 6px; font-size: 11px; color: var(--ink-2); }
.who-meta { font-variant-numeric: tabular-nums; }
.turn-text {
  font-size: 13.5px; line-height: 1.75; padding: 10px 13px; border-radius: 10px;
  white-space: pre-wrap; word-break: break-word;
}
.turn.me .turn-text { background: var(--primary-soft); color: var(--primary-ink); border-radius: 10px 4px 10px 10px; }
.turn.ag .turn-text { background: var(--surface); border: 1px solid var(--line); border-radius: 4px 10px 10px 10px; }
.caret {
  display: inline-block; width: 6px; height: 14px; margin-left: 2px;
  background: var(--primary); vertical-align: -2px; animation: blink 1s steps(2) infinite;
}
@keyframes blink { 50% { opacity: 0; } }
.processing { display: flex; align-items: center; gap: 9px; color: var(--ink-2); }
.spinner {
  width: 13px; height: 13px; border-radius: 50%; flex: none;
  border: 1.8px solid var(--line-2); border-top-color: var(--primary);
  animation: spin .8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.controls { display: flex; gap: 10px; padding: 14px 20px 18px; flex-wrap: wrap; margin-top: auto; }
.controls .btn { flex: 1; min-width: 130px; }

.report { margin: 0 20px 20px; padding: 16px; }
.report-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.report-head h3 { font-size: 15px; font-weight: 650; }
.mood { padding: 3px 11px; border-radius: var(--r-full); font-size: 12px; font-weight: 600; }
.mood.negative { background: var(--danger-bg); color: var(--danger-fg); }
.mood.positive { background: var(--safe-bg); color: var(--safe-fg); }
.mood.neutral { background: var(--surface-3); color: var(--ink-2); }
.report-row { display: flex; gap: 10px; padding: 7px 0; font-size: 13px; }
.report-row + .report-row { border-top: 1px dashed var(--line); }
.report-k { width: 62px; flex: none; color: var(--ink-3); font-size: 12px; }
.report-v { color: var(--ink); line-height: 1.7; }
.report-feedback {
  margin-top: 12px; padding: 12px 13px; border-radius: var(--r-m);
  background: var(--primary-soft); color: var(--primary-ink); font-size: 13.5px; line-height: 1.8;
}
.report-sug { margin-top: 12px; }
.report-sug ul { margin-top: 6px; display: flex; flex-direction: column; gap: 6px; }
.report-sug li { display: flex; align-items: flex-start; gap: 8px; font-size: 13px; color: var(--ink-2); line-height: 1.7; }
.report-sug li .ic { margin-top: 4px; color: var(--primary); }

.error-wrap { padding: 0 20px 20px; }
.kv-card { padding: 4px 12px; }
.chart-card { padding: 10px 12px 8px; }
.chart { width: 100%; height: 56px; display: block; }
.chart-axis { display: flex; justify-content: space-between; font-size: 10.5px; color: var(--ink-3); margin-top: 2px; }
.metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.metric { padding: 11px; }
.metric-n { font-size: 16px; font-weight: 600; font-variant-numeric: tabular-nums; }
.metric-l { font-size: 10.5px; color: var(--ink-3); }
.prose { padding: 12px; font-size: 12.5px; line-height: 1.85; color: var(--ink-2); }
.prose b { color: var(--ink); font-weight: 600; }

@media (max-width: 720px) {
  .frame { margin: 14px 14px 0; }
  .live-bar { margin: 12px 14px 0; }
  .turns { padding: 12px 14px 4px; }
  .controls { padding: 12px 14px 16px; }
  .report { margin: 0 14px 16px; }
  .error-wrap { padding: 0 14px 16px; }
  .tags { max-width: 100%; top: 46px; }
}
</style>
