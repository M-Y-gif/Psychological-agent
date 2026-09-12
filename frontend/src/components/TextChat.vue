<template>
  <section class="view">
    <div class="pane" ref="paneEl">
      <header class="topbar">
        <div>
          <h2 class="topbar-title">文字对话</h2>
          <div class="topbar-meta">Agent 自主检索知识库并评估风险 · 高风险自动触发预警与留痕</div>
        </div>
        <div class="grow"></div>
        <span class="chip"><Icon name="doc" size="s" />psychology_kb</span>
        <button class="btn btn-g btn-sm" type="button" :disabled="busy || !turns.length" @click="reset">
          新建对话
        </button>
      </header>

      <div class="thread" :class="{ empty: !turns.length }">
        <!-- 空状态 -->
        <div v-if="!turns.length" class="welcome">
          <div class="welcome-mark"><Icon name="spark" size="l" /></div>
          <h3>今天想聊点什么？</h3>
          <p class="muted">
            我会先检索心理学知识库，再评估风险等级，然后回答你。<br>
            这里的对话只用于本次会话，不会用于其他用途。
          </p>
          <div class="samples">
            <button v-for="s in samples" :key="s" type="button" class="sample" @click="send(s)">
              {{ s }}
            </button>
          </div>
        </div>

        <template v-else>
          <div v-for="t in turns" :key="t.id" class="msg" :class="t.role === 'user' ? 'me' : 'agent'">
            <div v-if="t.role === 'assistant'" class="avatar"><Icon name="spark" size="s" /></div>

            <div class="bubble">
              <div class="who">
                <template v-if="t.role === 'user'">
                  <span>你</span>
                  <span v-if="t.emotionLabel" class="who-tag">{{ t.emotionLabel }}</span>
                </template>
                <template v-else>Agent</template>
                <span v-if="t.proactive" class="who-tag">主动关心</span>
                <span class="who-time">{{ t.time }}</span>
              </div>

              <!-- 等待中：展示 Agent 的真实处理步骤 -->
              <div v-if="t.state === 'pending'" class="body thinking">
                <div class="steps">
                  <span v-for="(s, i) in STEPS" :key="s" class="step" :class="{ done: i < t.stepIndex, now: i === t.stepIndex }">
                    <span class="step-dot">
                      <Icon v-if="i < t.stepIndex" name="check" size="s" />
                    </span>{{ s }}
                  </span>
                </div>
              </div>

              <!-- 回答（逐字呈现，可中途停止） -->
              <div v-else class="body">
                <span class="sr-only" aria-live="polite">{{ t.state === 'revealing' ? '回答生成中' : '回答已生成' }}</span>
                <span class="text">{{ t.content }}</span>
                <span v-if="t.state === 'revealing'" class="caret" aria-hidden="true"></span>
                <span v-if="t.state === 'stopped'" class="stopped">（已停止）</span>
              </div>

              <!-- 引用来源 -->
              <div v-if="t.sources && t.sources.length" class="cite">
                <button type="button" class="cite-head" :aria-expanded="expanded[t.id] ? 'true' : 'false'"
                        @click="toggle(t.id)">
                  <Icon name="doc" size="s" />
                  <span class="grow">引用 {{ t.sources.length }} 条知识库来源</span>
                  <Icon name="chev" size="s" class="cite-chev" :class="{ open: expanded[t.id] }" />
                </button>
                <ul v-show="expanded[t.id]" class="cite-list">
                  <li v-for="(s, i) in t.sources" :key="i">
                    <Icon name="doc" size="s" />
                    <div class="cite-main">
                      <div class="cite-name">{{ s.source }}</div>
                      <div class="cite-snippet">{{ s.snippet }}</div>
                    </div>
                    <span class="cite-score">
                      <span class="meter"><i :style="{ width: scorePct(s.score) }"></i></span>
                      {{ Number(s.score).toFixed(2) }}
                    </span>
                  </li>
                </ul>
              </div>

              <RiskBanner v-if="t.role === 'assistant'" :risk-level="t.riskLevel" :reason="t.riskReason" />

              <div v-if="t.role === 'assistant' && (t.state === 'done' || t.state === 'stopped')" class="acts">
                <button type="button" @click="copy(t)"><Icon name="copy" size="s" />{{ t.copied ? '已复制' : '复制' }}</button>
                <button type="button" :class="{ active: readingId === t.id }" @click="toggleRead(t)">
                  <Icon name="volume" size="s" />{{ readingId === t.id ? '停止朗读' : '朗读' }}
                </button>
                <button type="button" :class="{ active: t.helpful }" @click="t.helpful = !t.helpful">
                  <Icon name="up" size="s" />{{ t.helpful ? '已标记' : '有帮助' }}
                </button>
                <button type="button" :disabled="busy" @click="regenerate(t)"><Icon name="redo" size="s" />重新生成</button>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div class="composer">
        <div v-if="attachment" class="attach">
          <img :src="attachment.url" alt="上传的图片" />
          <div class="attach-main">
            <div class="attach-name">已附加图片</div>
            <div class="attach-meta">
              <template v-if="attachment.detected">
                表情特征：{{ attachment.label || '中性' }}
                <template v-if="attachment.features">· {{ featureSummary(attachment.features) }}</template>
              </template>
              <template v-else>未检测到人脸，本次不附加表情特征</template>
            </div>
          </div>
          <button class="icon-btn" type="button" aria-label="移除图片" @click="removeAttachment">
            <Icon name="close" size="s" />
          </button>
        </div>

        <div class="input" :class="{ focus: inputFocus }">
          <textarea ref="taEl" v-model="draft" rows="1" :disabled="busy"
                    placeholder="说说你现在的心情，或输入一个心理学问题…"
                    aria-label="输入你的问题"
                    @input="autoGrow" @focus="inputFocus = true" @blur="inputFocus = false"
                    @keydown.enter.exact.prevent="send()"></textarea>
          <div class="input-row">
            <label class="icon-btn" :class="{ disabled: attaching || busy }" title="附加一张照片，检测表情特征">
              <input type="file" accept="image/*" class="file" :disabled="attaching || busy" @change="onPickImage" />
              <Icon name="img" size="s" />
              <span class="sr-only">附加图片</span>
            </label>
            <span v-if="attaching" class="attach-loading">正在分析表情…</span>
            <div class="grow"></div>
            <span class="hint">Enter 发送 · Shift + Enter 换行</span>
            <button v-if="busy" class="btn btn-g btn-sm" type="button" @click="stop">
              <Icon name="stop" size="s" />停止
            </button>
            <button v-else class="send" type="button" :disabled="!draft.trim()" aria-label="发送" @click="send()">
              <Icon name="send" size="s" />
            </button>
          </div>
        </div>

        <div v-if="error" class="error-box" role="alert">
          <Icon name="warn" size="s" />
          <span class="grow">{{ error }}</span>
          <button class="btn btn-sm btn-g" type="button" @click="retry">重试</button>
        </div>
      </div>
    </div>

    <aside class="side">
      <div class="side-head">
        <h3>本回合</h3>
        <span class="side-sub">{{ latest ? latest.time : '尚未开始' }}</span>
      </div>
      <div class="card kv-card">
        <div class="kv">
          <span class="kv-k">风险等级</span>
          <span v-if="latest && latest.riskLevel !== null" class="pill" :class="`pill-${riskMeta(latest.riskLevel).tone}`">
            <Icon name="warn" size="s" />{{ latest.riskLevel }} / 3 {{ riskMeta(latest.riskLevel).label }}
          </span>
          <span v-else class="kv-v muted">待评估</span>
        </div>
        <div class="kv">
          <span class="kv-k">检索片段</span>
          <span class="kv-v">{{ latest ? `${latest.sources.length} 条` : '—' }}</span>
        </div>
        <div class="kv">
          <span class="kv-k">对话轮次</span>
          <span class="kv-v">{{ userCount }} 轮</span>
        </div>
      </div>

      <div class="side-block">
        <div class="side-head">
          <h3>我记得的事</h3>
          <button class="btn btn-q btn-sm" type="button" :disabled="busy" @click="triggerCare"
                  title="演示：立刻让 Agent 主动关心一次">主动关心</button>
        </div>
        <div v-if="facts.length" class="card fact-card">
          <div v-for="(f, i) in facts" :key="i" class="fact">
            <Icon name="heart" size="s" /><span>{{ f }}</span>
          </div>
        </div>
        <div v-else class="card empty-card muted">聊过之后，我会慢慢记住你在意的事</div>
      </div>

      <div class="side-block">
        <div class="side-head"><h3>知识来源</h3><span class="side-sub">psychology_kb</span></div>
        <div v-if="latest && latest.sources.length" class="card src-card">
          <div v-for="(s, i) in latest.sources" :key="i" class="src">
            <div class="src-name">{{ s.source }}</div>
            <div class="src-meta">
              <span class="meter"><i :style="{ width: scorePct(s.score) }"></i></span>
              <span>{{ Number(s.score).toFixed(2) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="card empty-card muted">提问后显示命中的知识片段</div>
      </div>

    </aside>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import Icon from './ui/Icon.vue'
import RiskBanner from './RiskBanner.vue'
import { chat, fetchMemory, multimodalAnalyze, streamChat, triggerCare as triggerCareApi } from '../api'
import { plainText } from '../utils/text'
import { speakOnce } from '../utils/tts'
import { addRiskRecord, formatClock, pollCare, riskMeta, ttsPrefs } from '../store'

const STEPS = ['检索知识库', '评估风险等级', '生成回答']
const samples = [
  '什么是认知歪曲？常见的认知歪曲有哪些？',
  '我最近总是失眠，有什么放松的方法？',
  '怎么记录和检验自己的自动思维？'
]

const paneEl = ref(null)
const taEl = ref(null)
const draft = ref('')
const turns = ref([])
const error = ref('')
const busy = ref(false)
const attaching = ref(false)
const attachment = ref(null)
const inputFocus = ref(false)
const expanded = reactive({})

const facts = ref([])
const readingId = ref('')
let readHandle = null
let seq = 0
let controller = null
let stepTimer = null
let lastQuestion = ''

const latest = computed(() => {
  for (let i = turns.value.length - 1; i >= 0; i -= 1) {
    const t = turns.value[i]
    if (t.role === 'assistant') return t
  }
  return null
})
const userCount = computed(() => turns.value.filter(t => t.role === 'user').length)

/** 演示按钮：立刻触发一条主动关怀，结果经全局轮询出现在关怀弹窗 */
async function triggerCare() {
  try {
    await triggerCareApi()
    await pollCare()
  } catch (e) {
    error.value = `主动关心触发失败：${e.message}`
  }
}

/** 朗读本条回复（云端音色优先，自动降级系统语音） */
function toggleRead(t) {
  if (readingId.value === t.id) {
    if (readHandle) { readHandle.stop(); readHandle = null }
    readingId.value = ''
    return
  }
  if (readHandle) readHandle.stop()
  readingId.value = t.id
  readHandle = speakOnce(plainText(t.content), { ...ttsPrefs.value, onEnd: () => { readingId.value = '' } })
}

async function loadMemory() {
  try {
    const m = await fetchMemory()
    facts.value = (m && m.facts) || []
  } catch (e) { /* 忽略 */ }
}

onMounted(() => {
  loadMemory()
})

onBeforeUnmount(() => {
  if (readHandle) readHandle.stop()
})

function scorePct(score) {
  const n = Number(score) || 0
  return `${Math.max(4, Math.min(100, n * 100))}%`
}

function featureSummary(features) {
  return Object.entries(features)
    .slice(0, 2)
    .map(([k, v]) => `${k} ${v}`)
    .join(' · ')
}

function safeParse(json) {
  if (!json) return null
  try { return JSON.parse(json) } catch (e) { return null }
}

async function scrollToEnd(force = false) {
  await nextTick()
  const el = paneEl.value
  if (!el) return
  const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 160
  if (force || nearBottom) el.scrollTop = el.scrollHeight
}

function autoGrow() {
  const el = taEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

function toggle(id) {
  expanded[id] = !expanded[id]
}

async function send(textOverride) {
  const question = (textOverride !== undefined ? textOverride : draft.value).trim()
  if (!question || busy.value) return

  error.value = ''
  lastQuestion = question
  // 历史轮次：用户发言全部保留，助手发言只取已完成的（避免把报错/进行中的内容带进上下文）
  const history = turns.value
    .filter(t => t.content && (t.role === 'user' || t.state === 'done' || t.state === 'stopped'))
    .map(t => ({ role: t.role, content: t.content }))

  const emotionLabel = attachment.value && attachment.value.detected ? attachment.value.label : ''
  turns.value.push({ id: `u${seq += 1}`, role: 'user', content: question, time: formatClock(), emotionLabel })
  const emotionContext = attachment.value && attachment.value.detected ? attachment.value.features : null

  draft.value = ''
  if (taEl.value) taEl.value.style.height = 'auto'
  turns.value.push({
    id: `a${seq += 1}`, role: 'assistant', content: '', time: formatClock(),
    sources: [], riskLevel: null, riskReason: '', state: 'pending', stepIndex: 0,
    copied: false, helpful: false
  })
  const turn = turns.value[turns.value.length - 1]

  busy.value = true
  scrollToEnd(true)
  stepTimer = setInterval(() => {
    if (turn.stepIndex < STEPS.length - 1) turn.stepIndex += 1
  }, 1400)

  controller = new AbortController()
  let streamed = ''
  try {
    await streamChat({
      question,
      emotionContext,
      history,
      signal: controller.signal,
      onToken: (piece) => {
        if (turn.state === 'pending') {
          // 收到第一段文字：把「思考中」换成真正的回答
          clearInterval(stepTimer)
          attachment.value = null
          turn.state = 'revealing'
        }
        streamed += piece
        turn.content = plainText(streamed)
        scrollToEnd()
      },
      onMeta: (meta) => {
        turn.sources = meta.sources || []
        turn.riskLevel = meta.riskLevel === undefined ? null : meta.riskLevel
        turn.riskReason = meta.riskReason || ''
        addRiskRecord({ level: turn.riskLevel, reason: turn.riskReason, message: question, source: '文字对话' })
      }
    })
    clearInterval(stepTimer)
    if (!turn.content) turn.content = '（没有生成回答，请换一种问法再试一次）'
    turn.state = 'done'
    loadMemory()
  } catch (e) {
    clearInterval(stepTimer)
    if (e.name === 'AbortError') {
      turn.state = 'stopped'
      if (!turn.content) turn.content = '（已停止，未生成回答）'
    } else {
      await fallback(question, emotionContext, history, turn)
    }
  } finally {
    busy.value = false
    controller = null
    scrollToEnd()
  }
}

/** 流式不可用时退回普通接口，保证功能仍然可用 */
async function fallback(question, emotionContext, history, turn) {
  try {
    const data = await chat(question, emotionContext, history)
    turn.sources = data.sources || []
    turn.riskLevel = data.riskLevel === undefined ? null : data.riskLevel
    turn.riskReason = data.riskReason || ''
    addRiskRecord({ level: turn.riskLevel, reason: turn.riskReason, message: question, source: '文字对话' })
    turn.content = plainText(data.answer) || '（没有生成回答，请换一种问法再试一次）'
    turn.state = 'done'
  } catch (e) {
    turn.state = 'error'
    turn.content = ''
    error.value = e.message || '请求失败'
  }
}

function stop() {
  if (controller) {
    controller.abort()
    controller = null
  }
  const t = latest.value
  if (t && (t.state === 'pending' || t.state === 'revealing')) {
    t.state = 'stopped'
    if (!t.content) t.content = '（已停止，未生成回答）'
  }
  busy.value = false
}

async function copy(turn) {
  try {
    await navigator.clipboard.writeText(turn.content)
  } catch (e) {
    const ta = document.createElement('textarea')
    ta.value = turn.content
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  turn.copied = true
  setTimeout(() => { turn.copied = false }, 2000)
}

function regenerate(turn) {
  if (busy.value) return
  const idx = turns.value.findIndex(t => t.id === turn.id)
  if (idx < 0) return
  const userTurn = turns.value.slice(0, idx).reverse().find(t => t.role === 'user')
  if (!userTurn) return
  const question = userTurn.content
  turns.value.splice(idx - 1, 2)
  send(question)
}

function retry() {
  if (lastQuestion) {
    const idx = turns.value.length - 1
    const t = turns.value[idx]
    if (t && t.role === 'assistant' && t.state === 'error') {
      turns.value.splice(idx - 1, 2)
      send(lastQuestion)
    }
  }
}

function reset() {
  if (busy.value) return
  turns.value = []
  error.value = ''
  attachment.value = null
}

async function onPickImage(event) {
  const file = event.target.files && event.target.files[0]
  event.target.value = ''
  if (!file) return
  attaching.value = true
  error.value = ''
  try {
    const data = await multimodalAnalyze(null, file)
    attachment.value = {
      url: URL.createObjectURL(file),
      label: data.emotion_label || '',
      detected: data.face_detected !== false,
      features: safeParse(data.features_json)
    }
  } catch (e) {
    error.value = `图片分析失败：${e.message}`
  } finally {
    attaching.value = false
  }
}

function removeAttachment() {
  attachment.value = null
}
</script>

<style scoped>
.thread { flex: 1; padding: 20px 24px 8px; display: flex; flex-direction: column; gap: 18px; }
.thread.empty { justify-content: center; }

/* 空状态 */
.welcome { text-align: center; padding: 24px 0 36px; }
.welcome-mark {
  width: 46px; height: 46px; border-radius: 13px; margin: 0 auto 14px;
  display: grid; place-items: center; background: var(--primary-soft); color: var(--primary-ink);
}
.welcome h3 { font-size: 16px; font-weight: 650; margin-bottom: 6px; }
.samples { display: flex; flex-direction: column; gap: 8px; align-items: center; margin-top: 18px; }
.sample {
  width: 100%; max-width: 420px; text-align: left;
  padding: 11px 14px; border: 1px solid var(--line); border-radius: var(--r-m);
  background: var(--surface); color: var(--ink-2); font-size: 13px;
  transition: border-color .15s ease, color .15s ease, box-shadow .15s ease;
}
.sample:hover { border-color: var(--primary); color: var(--primary-ink); box-shadow: var(--sh-1); }

/* 消息 */
.msg { display: flex; gap: 11px; }
.msg.me { justify-content: flex-end; }
.avatar {
  width: 30px; height: 30px; border-radius: 9px; flex: none;
  display: grid; place-items: center; background: var(--primary-soft); color: var(--primary-ink);
}
.bubble { max-width: min(600px, 86%); min-width: 0; }
.who { display: flex; align-items: center; gap: 7px; font-size: 11.5px; color: var(--ink-3); margin-bottom: 5px; }
.msg.me .who { justify-content: flex-end; }
.who-tag { background: var(--surface-3); border-radius: 5px; padding: 0 6px; font-size: 11px; color: var(--ink-2); }
.who-time { font-variant-numeric: tabular-nums; }

.body {
  background: var(--surface); border: 1px solid var(--line); border-radius: 4px 12px 12px 12px;
  padding: 12px 15px; font-size: 13.5px; line-height: 1.78; box-shadow: var(--sh-1);
  white-space: pre-wrap; word-break: break-word;
}
.msg.me .body {
  background: var(--primary); border-color: var(--primary); color: #fff;
  border-radius: 12px 4px 12px 12px;
}
.text { white-space: pre-wrap; }
.caret {
  display: inline-block; width: 7px; height: 15px; margin-left: 2px;
  background: var(--primary); vertical-align: -2px; animation: blink 1s steps(2) infinite;
}
@keyframes blink { 50% { opacity: 0; } }
.stopped { color: var(--ink-3); font-size: 12px; margin-left: 4px; }

/* 处理步骤 */
.thinking { padding: 11px 15px; }
.steps { display: flex; flex-direction: column; gap: 6px; }
.step { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--ink-3); }
.step.now { color: var(--ink); }
.step.done { color: var(--ink-2); }
.step-dot {
  width: 14px; height: 14px; border-radius: 50%; flex: none;
  border: 1.5px solid var(--line-2); display: grid; place-items: center;
}
.step.done .step-dot { background: var(--primary); border-color: var(--primary); color: #fff; }
.step.done .step-dot .ic { width: 10px; height: 10px; }
.step.now .step-dot { border-color: var(--primary); animation: pulse 1.4s ease-in-out infinite; }
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(46, 125, 111, .35); }
  50% { box-shadow: 0 0 0 4px rgba(46, 125, 111, 0); }
}

/* 引用来源 */
.cite { margin-top: 10px; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: var(--surface-2); }
.cite-head {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 9px 12px; font-size: 12px; color: var(--ink-2); text-align: left;
}
.cite-head:hover { background: var(--surface-3); }
.cite-chev { transition: transform .18s ease; }
.cite-chev.open { transform: rotate(90deg); }
.cite-list { border-top: 1px solid var(--line); }
.cite-list li { display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; }
.cite-list li + li { border-top: 1px solid var(--line); }
.cite-main { flex: 1; min-width: 0; }
.cite-name { font-size: 12px; color: var(--ink); }
.cite-snippet {
  font-size: 11.5px; color: var(--ink-3); line-height: 1.65; margin-top: 2px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.cite-score { display: flex; align-items: center; gap: 7px; flex: none; font-size: 11px; color: var(--ink-3); font-variant-numeric: tabular-nums; }

/* 消息操作 */
.acts { display: flex; gap: 4px; margin-top: 7px; flex-wrap: wrap; }
.acts button {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 8px; border-radius: 7px; font-size: 11.5px; color: var(--ink-3);
}
.acts button:hover:not(:disabled) { background: var(--surface-3); color: var(--ink-2); }
.acts button.active { color: var(--primary-ink); background: var(--primary-soft); }
.acts button:disabled { opacity: .5; }

/* 输入区 */
.composer { padding: 12px 24px 18px; display: flex; flex-direction: column; gap: 10px; }
.attach {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px;
  border: 1px solid var(--line); border-radius: var(--r-m); background: var(--surface-2);
}
.attach img { width: 40px; height: 40px; border-radius: 8px; object-fit: cover; flex: none; }
.attach-main { min-width: 0; flex: 1; }
.attach-name { font-size: 12.5px; font-weight: 550; }
.attach-meta { font-size: 11.5px; color: var(--ink-3); }
.attach-loading { font-size: 11.5px; color: var(--ink-3); }

.input {
  border: 1px solid var(--line-2); border-radius: 14px; background: var(--surface);
  padding: 11px 12px 9px; box-shadow: var(--sh-1);
  transition: border-color .15s ease, box-shadow .15s ease;
}
.input.focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(46, 125, 111, .13); }
.input textarea {
  width: 100%; border: 0; outline: 0; resize: none; background: transparent;
  font-size: 13.5px; line-height: 1.7; min-height: 26px; max-height: 160px;
}
.input textarea::placeholder { color: var(--ink-3); }
.input-row { display: flex; align-items: center; gap: 4px; margin-top: 6px; }
.hint { font-size: 11px; color: var(--ink-3); margin-right: 4px; }
.file { display: none; }
.icon-btn.disabled { opacity: .45; pointer-events: none; }
.send {
  width: 32px; height: 32px; border-radius: 9px; display: grid; place-items: center;
  background: var(--primary); color: #fff; box-shadow: 0 2px 6px rgba(36, 104, 92, .3);
  transition: background .15s ease;
}
.send:hover:not(:disabled) { background: var(--primary-2); }
.send:disabled { background: #C3D6D1; box-shadow: none; }

/* 右侧栏 */
.kv-card { padding: 4px 12px; }
.src-card { padding: 2px 12px; }
.src { padding: 9px 0; }
.src + .src { border-top: 1px solid var(--line); }
.src-name {
  font-size: 12px; color: var(--ink);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.src-meta { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--ink-3); margin-top: 4px; font-variant-numeric: tabular-nums; }
.empty-card { padding: 14px 12px; font-size: 12px; text-align: center; }
.fact-card { padding: 4px 12px; }
.fact {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 9px 0; font-size: 12.5px; color: var(--ink-2); line-height: 1.65;
}
.fact + .fact { border-top: 1px solid var(--line); }
.fact .ic { margin-top: 4px; color: var(--primary); }

@media (max-width: 720px) {
  .thread { padding: 16px 14px 8px; }
  .composer { padding: 10px 14px 16px; }
  .bubble { max-width: 92%; }
  .hint { display: none; }
}
</style>
