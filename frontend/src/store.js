import { computed, reactive, ref } from 'vue'

/* ============ 身份 ============ */
const USER_KEY = 'psy.user'

export const ROLES = [
  { key: 'elder', label: '长者', icon: 'heart', hint: '想找人说说话', placeholder: '比如：王奶奶' },
  { key: 'child', label: '孩子', icon: 'spark', hint: '有心事想说', placeholder: '比如：朵朵' },
  { key: 'family', label: '家属', icon: 'user', hint: '关心家人的状态', placeholder: '比如：王女士' }
]

export function roleOf(key) {
  return ROLES.find(r => r.key === key) || ROLES[0]
}

function loadUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    if (raw) return JSON.parse(raw)
  } catch (e) { /* 隐私模式下忽略 */ }
  return null
}

/** 当前使用者（保存在本机，刷新后仍在） */
export const currentUser = ref(loadUser())

/**
 * 稳定身份 id：FNV-1a(role:name)。
 * 同一称呼 + 同一角色重新登录时得到同一个 id，后端的长期记忆才能接上。
 * （同名同角色的两个人会共享记忆——演示场景可接受，生产需换成账号体系。）
 */
function stableId(role, name) {
  let h = 2166136261
  const s = `${role}:${name}`
  for (let i = 0; i < s.length; i += 1) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return `${role}-${(h >>> 0).toString(36)}`
}

export function signIn({ name, role }) {
  const user = {
    id: stableId(role, String(name || '').trim()),
    name: String(name || '').trim(),
    role,
    since: Date.now()
  }
  currentUser.value = user
  try { localStorage.setItem(USER_KEY, JSON.stringify(user)) } catch (e) { /* 忽略 */ }
  clearCare()
  resetTtsPrefsForRole(role)
  return user
}

export function signOut() {
  currentUser.value = null
  try { localStorage.removeItem(USER_KEY) } catch (e) { /* 忽略 */ }
  clearCare()
}

/* ============ 风险等级语义 ============ */
export const RISK_META = {
  0: { label: '无风险', tone: 'safe' },
  1: { label: '低风险', tone: 'safe' },
  2: { label: '需关注', tone: 'warn' },
  3: { label: '高风险', tone: 'danger' }
}

export function riskMeta(level) {
  if (level === null || level === undefined) return { label: '未评估', tone: 'mute' }
  return RISK_META[level] || { label: `等级 ${level}`, tone: 'mute' }
}

/* ============ 紧急求助（全站只在这里展示号码） ============ */
export const HOTLINE = { name: '心理援助热线 12356', tel: '12356', note: '全国 · 24 小时接听' }

/* ============ 本次会话的风险留痕（按使用者归属） ============ */
export const sessionRecords = reactive([])

export function addRiskRecord({ level, reason, message, source }) {
  if (level === null || level === undefined || level < 2) return
  const userId = currentUser.value ? currentUser.value.id : 'anonymous'
  if (sessionRecords.some(r => r.userId === userId && r.message === message && r.level === level)) return
  sessionRecords.unshift({
    id: `${Date.now()}-${sessionRecords.length}`,
    userId,
    userName: currentUser.value ? currentUser.value.name : '未登录',
    time: new Date().toLocaleString('zh-CN', { hour12: false }),
    level,
    reason: reason || '',
    message: message || '',
    source: source || '文字对话'
  })
}

/** 只显示当前使用者自己的记录 */
export const myRecords = computed(() => {
  const id = currentUser.value ? currentUser.value.id : null
  return id ? sessionRecords.filter(r => r.userId === id) : []
})

export function formatClock(date = new Date()) {
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

/* ============ 语音偏好（TTS） ============ */
export const TTS_DEFAULTS = {
  elder: { voice: 'zh-CN-XiaoxiaoNeural', rate: 0.9 },
  child: { voice: 'zh-CN-XiaoyiNeural', rate: 1.05 },
  family: { voice: 'zh-CN-YunxiNeural', rate: 1.0 }
}

const TTS_KEY = 'psy.tts'

function loadTtsPrefs() {
  try {
    const raw = localStorage.getItem(TTS_KEY)
    if (raw) return JSON.parse(raw)
  } catch (e) { /* 忽略 */ }
  const d = TTS_DEFAULTS.elder
  return { engine: 'backend', voice: d.voice, rate: d.rate }
}

/** 当前语音偏好：engine 云端(backend edge-tts) / 系统(system speechSynthesis)，voice/rate 按角色默认 */
export const ttsPrefs = ref(loadTtsPrefs())

/** 切换使用者时把语音偏好切回该角色的默认音色 */
export function resetTtsPrefsForRole(role) {
  const d = TTS_DEFAULTS[role] || TTS_DEFAULTS.elder
  ttsPrefs.value = { engine: 'backend', voice: d.voice, rate: d.rate }
  try { localStorage.setItem(TTS_KEY, JSON.stringify(ttsPrefs.value)) } catch (e) { /* 忽略 */ }
}

export function saveTtsPrefs() {
  try { localStorage.setItem(TTS_KEY, JSON.stringify(ttsPrefs.value)) } catch (e) { /* 忽略 */ }
}

/* ============ 主动关怀（全局，切换 tab 不丢） ============ */
/** 未读关怀队列（已经过本机去重） */
export const unreadCare = ref([])

/** 呼吸练习请求：CareToast 发起，App 监听后切页并自动开始 */
export const breathAction = ref(null)

export function requestBreath(pattern) {
  breathAction.value = { pattern: pattern || '4-4-6', seq: Date.now() }
}

export function dismissCare(id) {
  unreadCare.value = unreadCare.value.filter(c => c.id !== id)
}

/** 本机已见过的关怀 id（sessionStorage，防止刷新/重轮询后重复弹出） */
function seenIds() {
  const key = `psy.seenCare.${currentUser.value ? currentUser.value.id : 'anon'}`
  try {
    const raw = sessionStorage.getItem(key)
    return raw ? JSON.parse(raw) : []
  } catch (e) { return [] }
}

function rememberSeen(ids) {
  const key = `psy.seenCare.${currentUser.value ? currentUser.value.id : 'anon'}`
  try {
    const all = seenIds().concat(ids).slice(-100)
    sessionStorage.setItem(key, JSON.stringify(all))
  } catch (e) { /* 忽略 */ }
}

/**
 * 轮询未读关怀：新消息入队 + 记入本机已见 + 通知服务端已送达。
 * 用动态 import 避免 store <-> api 的循环依赖。
 */
export async function pollCare() {
  if (!currentUser.value) return
  let list = []
  try {
    const { pendingCare, ackCare } = await import('./api')
    list = await pendingCare()
    const seen = seenIds()
    const fresh = (list || []).filter(c => c && c.id && !seen.includes(c.id))
    if (fresh.length) {
      const dupes = new Set(unreadCare.value.map(c => c.id))
      const novel = fresh.filter(c => !dupes.has(c.id))
      if (novel.length) {
        unreadCare.value = unreadCare.value.concat(novel)
        // 新关怀到达时顺手把上次没完成的呼吸请求清掉
        breathAction.value = null
      }
      rememberSeen(fresh.map(c => c.id))
      ackCare(fresh.map(c => c.id)).catch(() => { /* 确认失败无害，下轮重试 */ })
    }
  } catch (e) { /* 主动关怀失败不影响正常对话 */ }
}

function clearCare() {
  unreadCare.value = []
  breathAction.value = null
}

/* ============ 呼吸练习统计（按使用者分账） ============ */
export function breathStatsKey() {
  return currentUser.value ? `psy.breath.stats.${currentUser.value.id}` : 'psy.breath.stats'
}
