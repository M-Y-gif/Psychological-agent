// 语音朗读：云端 edge-tts 优先，失败自动退回浏览器 speechSynthesis。
// 统一返回句柄 { stop() }，由调用方管理生命周期（保证打断逻辑不串）。
import { tts as ttsApi } from '../api'

/** rate 为数值倍率（0.9 / 1.05），转成 edge-tts 的百分比格式（"-10%" / "+5%"） */
function rateToPct(rate) {
  const n = Number(rate) || 1
  const pct = Math.round((n - 1) * 100)
  return `${pct >= 0 ? '+' : ''}${pct}%`
}

/**
 * 朗读一段文本。
 * opts：{ voice, rate, engine('backend'|'system'), onEnd, onError }
 */
export function speakOnce(text, opts = {}) {
  const { voice, rate = 1, engine = 'backend' } = opts
  const onEnd = opts.onEnd || (() => {})
  const onError = opts.onError || (() => {})
  if (!text || engine !== 'backend') {
    return systemSpeak(text, { rate, onEnd, onError })
  }

  const ac = new AbortController()
  let audio = null
  let done = false
  const finish = (err) => {
    if (done) return
    done = true
    if (err) onError(err)
    else onEnd()
  }

  ttsApi(text, { voice, rate: rateToPct(rate), signal: ac.signal })
    .then(blob => {
      if (done) return
      audio = new Audio(URL.createObjectURL(blob))
      audio.onended = () => { audio = null; finish() }
      audio.onerror = () => { audio = null; finish() } // 播放失败静默结束
      audio.play().catch(() => { audio = null; finish() })
    })
    .catch(() => {
      // 云端失败：退回系统语音
      systemSpeak(text, { rate, onEnd: finish, onError: () => finish() })
    })

  return {
    stop() {
      finish()
      ac.abort()
      if (audio) { audio.pause(); audio.src = ''; audio = null }
    }
  }
}

function systemSpeak(text, { rate = 1, onEnd, onError }) {
  if (!window.speechSynthesis) {
    if (onEnd) onEnd()
    return { stop() {} }
  }
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'zh-CN'
  u.rate = rate
  u.pitch = 1
  u.volume = 1
  u.onend = () => onEnd && onEnd()
  u.onerror = () => onEnd && onEnd() // 系统语音出错也算结束，避免卡住流程
  window.speechSynthesis.speak(u)
  return {
    stop() {
      try { window.speechSynthesis.cancel() } catch (e) { /* 忽略 */ }
      if (onEnd) onEnd()
    }
  }
}
