// 后端 API 封装：统一错误处理，支持 AbortSignal 以便中途取消
import { currentUser } from './store'

const BASE = '/api'

/**
 * 带上当前使用者标识。姓名是中文，HTTP 头只能放 ASCII，所以做了 URL 编码。
 * 说明：这一版后端只做透传记录，尚未校验身份。
 */
function userHeaders(extra = {}) {
  const u = currentUser.value
  if (!u) return { ...extra }
  return {
    ...extra,
    'X-User-Id': u.id,
    'X-User-Name': encodeURIComponent(u.name),
    'X-User-Role': u.role
  }
}

async function toJson(res) {
  let data = null
  try {
    data = await res.json()
  } catch (e) {
    data = null
  }
  if (!res.ok) {
    throw new Error((data && data.error) || `请求失败（HTTP ${res.status}）`)
  }
  return data
}

/**
 * 对话：question 本次提问；emotionContext 多模态情绪特征；history 历史轮次 [{role, content}]
 */
export async function chat(question, emotionContext, history, signal) {
  const body = { question }
  if (emotionContext) body.emotionContext = emotionContext
  if (history && history.length) body.history = history
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: userHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
    signal
  })
  return toJson(res)
}

/** 会话结束后的心理分析报告 */
export async function analysisSession(turns, preRiskLevel, preRiskReason, signal) {
  const res = await fetch(`${BASE}/analysis/session`, {
    method: 'POST',
    headers: userHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ turns, preRiskLevel, preRiskReason }),
    signal
  })
  return toJson(res)
}

/** 多模态感知：音频 -> 转写 + 韵律；图片 -> 表情特征 */
export async function multimodalAnalyze(audioFile, imageFile, signal) {
  const fd = new FormData()
  if (audioFile) fd.append('audio', audioFile)
  if (imageFile) fd.append('image', imageFile)
  const res = await fetch(`${BASE}/multimodal/analyze`, { method: 'POST', headers: userHeaders(), body: fd, signal })
  return toJson(res)
}

/**
 * 流式对话（SSE）：逐段回调增量文本 onToken，流结束时回调 onMeta（检索来源 + 风险等级）。
 * 用 fetch + ReadableStream 手工解析，因为需要 POST（EventSource 只支持 GET）。
 */
export async function streamChat({ question, emotionContext, history, signal, onToken, onMeta }) {
  const body = { question }
  if (emotionContext) body.emotionContext = emotionContext
  if (history && history.length) body.history = history

  const res = await fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: userHeaders({ 'Content-Type': 'application/json', Accept: 'text/event-stream' }),
    body: JSON.stringify(body),
    signal
  })
  if (!res.ok || !res.body) {
    throw new Error(`流式请求失败（HTTP ${res.status}）`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let eventName = 'message'
  let dataLines = []
  let failure = null

  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let idx = buffer.indexOf('\n')
    while (idx >= 0) {
      const line = buffer.slice(0, idx).replace(/\r$/, '')
      buffer = buffer.slice(idx + 1)

      if (line === '') {
        if (dataLines.length) {
          let payload = null
          try { payload = JSON.parse(dataLines.join('\n')) } catch (e) { payload = null }
          if (eventName === 'token' && payload && onToken) onToken(payload.t || '')
          else if (eventName === 'meta' && payload && onMeta) onMeta(payload)
          else if (eventName === 'error') failure = new Error((payload && payload.message) || '生成失败')
        }
        eventName = 'message'
        dataLines = []
      } else if (line.startsWith('event:')) {
        eventName = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).replace(/^ /, ''))
      }

      idx = buffer.indexOf('\n')
    }
  }

  if (failure) throw failure
}

/** 取尚未展示的主动关怀（只读；展示确认走 ackCare） */
export async function pendingCare(signal) {
  const res = await fetch(`${BASE}/care/pending`, { headers: userHeaders(), signal })
  return toJson(res)
}

/** 确认已展示的关怀 id，服务端标记送达（幂等） */
export async function ackCare(ids) {
  const res = await fetch(`${BASE}/care/ack`, {
    method: 'POST',
    headers: userHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ ids: ids || [] })
  })
  return toJson(res)
}

/** 演示用：立刻触发一条主动关怀（type：message / breath / story） */
export async function triggerCare(type) {
  const url = `${BASE}/care/trigger${type ? `?type=${encodeURIComponent(type)}` : ''}`
  const res = await fetch(url, { method: 'POST', headers: userHeaders() })
  return toJson(res)
}

/** 查看"它记得我什么" */
export async function fetchMemory() {
  const res = await fetch(`${BASE}/memory`, { headers: userHeaders() })
  return toJson(res)
}

/** 保存心情日记：text 正文；mood 1-5 心情（可空）。返回 {diary, riskLevel, riskReason} */
export async function addDiary(text, mood, signal) {
  const res = await fetch(`${BASE}/diary`, {
    method: 'POST',
    headers: userHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ text, mood: mood || null }),
    signal
  })
  return toJson(res)
}

/** 语音合成：返回 mp3 Blob（失败抛异常，由调用方降级到浏览器语音） */
export async function tts(text, { voice, rate, signal } = {}) {
  const body = { text }
  if (voice) body.voice = voice
  if (rate) body.rate = rate
  const res = await fetch(`${BASE}/tts`, {
    method: 'POST',
    headers: userHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
    signal
  })
  if (!res.ok) {
    let msg = `语音合成失败（HTTP ${res.status}）`
    try {
      const data = await res.json()
      if (data && data.error) msg = data.error
    } catch (e) { /* 忽略 */ }
    throw new Error(msg)
  }
  return res.blob()
}

/** 情感陪伴质量评测（演示/论文用，运行约 2-4 分钟） */
export async function evalCompanion() {
  const res = await fetch(`${BASE}/eval/companion`, { method: 'POST', headers: userHeaders() })
  return toJson(res)
}
