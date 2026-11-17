<template>
  <section class="view diary-view">
    <div class="pane">
      <div class="paper">
        <header class="paper-head">
          <h1 class="paper-date">{{ todayText }}</h1>
        </header>

        <!-- 今日心情打卡 -->
        <div class="mood-block">
          <div class="mood-label">今天心情</div>
          <div class="mood-row">
            <button v-for="m in MOODS" :key="m.value" type="button"
                    class="mood-btn" :class="{ on: mood === m.value }"
                    :aria-label="m.label" :aria-pressed="mood === m.value"
                    @click="pick(m.value)">
              <span class="mood-emoji" aria-hidden="true">{{ m.emoji }}</span>
            </button>
          </div>
        </div>

        <!-- 写日记 -->
        <textarea v-model="draft" rows="6" maxlength="2000"
                  placeholder="写点什么…"
                  aria-label="日记正文"></textarea>
        <div class="paper-acts">
          <button type="button" class="btn btn-p" :disabled="busy || !draft.trim()" @click="save">
            {{ busy ? '它正在读…' : '保存' }}
          </button>
        </div>
        <div v-if="error" class="error-box" role="alert">
          <Icon name="warn" size="s" /><span>{{ error }}</span>
        </div>

        <!-- 历史：默认只露心情与首行，点开才看全文 -->
        <div class="history">
          <div v-if="!entries.length" class="empty">
            <span class="empty-emoji" aria-hidden="true">📖</span>
            <p class="muted">还没有日记，写下第一篇吧。</p>
          </div>
          <ul v-else class="entry-list">
            <li v-for="(d, i) in entries" :key="(d.at || '') + i"
                class="entry" :class="{ open: openAt === d.at }">
              <button type="button" class="entry-row"
                      :aria-expanded="openAt === d.at"
                      @click="toggle(d)">
                <span class="entry-emoji" aria-hidden="true">{{ emojiOf(d.mood) }}</span>
                <span class="entry-date">{{ shortDate(d.at) }}</span>
                <span class="entry-preview">{{ d.text }}</span>
              </button>
              <div v-if="openAt === d.at" class="entry-detail">
                <p class="entry-text">{{ d.text }}</p>
                <div v-if="d.reply" class="entry-reply">
                  <Icon name="mark" size="s" />
                  <p>{{ d.reply }}</p>
                </div>
                <div v-if="latestAt === d.at && riskLevel !== null" class="entry-risk">
                  <RiskBanner :risk-level="riskLevel" :reason="riskReason" />
                </div>
                <div v-if="d.reply" class="entry-acts">
                  <button type="button" class="btn btn-g btn-sm" @click="toggleRead(d)">
                    <Icon name="volume" size="s" />{{ readingAt === d.at ? '停止朗读' : '读给我听' }}
                  </button>
                  <button type="button" class="btn btn-sm" @click="copyReply(d)">
                    <Icon name="copy" size="s" />{{ copiedAt === d.at ? '已复制' : '复制' }}
                  </button>
                </div>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { addDiary, fetchMemory } from '../api'
import { addRiskRecord, ttsPrefs } from '../store'
import { speakOnce } from '../utils/tts'
import { plainText } from '../utils/text'
import Icon from './ui/Icon.vue'
import RiskBanner from './RiskBanner.vue'

const MOODS = [
  { value: 1, emoji: '😞', label: '很糟' },
  { value: 2, emoji: '😕', label: '不太好' },
  { value: 3, emoji: '😐', label: '一般' },
  { value: 4, emoji: '🙂', label: '不错' },
  { value: 5, emoji: '😄', label: '很好' }
]

const mood = ref(null)
const draft = ref('')
const busy = ref(false)
const error = ref('')
const entries = ref([])
const openAt = ref(null)          // 展开的日记 at；默认全折叠
const readingAt = ref('')         // 正在朗读的日记 at
const copiedAt = ref('')
const latestAt = ref(null)        // 最近一次保存的日记（风险横幅只挂在它身上）
const riskLevel = ref(null)
const riskReason = ref('')
let readHandle = null

const todayText = computed(() => {
  const d = new Date()
  const w = '日一二三四五六'[d.getDay()]
  return `${d.getMonth() + 1}月${d.getDate()}日 · 星期${w}`
})

onMounted(loadEntries)
onBeforeUnmount(() => { if (readHandle) readHandle.stop() })

async function loadEntries() {
  try {
    const m = await fetchMemory()
    entries.value = m.diary || []
    // 今天已打过卡：把当天最近一篇的心情回填到打卡器
    const today = new Date().toISOString().slice(0, 10)
    const todays = entries.value.filter(d => (d.at || '').startsWith(today) && d.mood != null)
    if (todays.length) mood.value = todays[0].mood
  } catch (e) {
    /* 历史加载失败不阻塞写日记 */
  }
}

function emojiOf(v) {
  return (MOODS.find(m => m.value === v) || {}).emoji || '📝'
}

function shortDate(at) {
  if (!at) return ''
  const [y, m, d] = String(at).slice(0, 10).split('-')
  return `${Number(m)}/${Number(d)}`
}

function pick(v) {
  mood.value = mood.value === v ? null : v
}

function toggle(d) {
  if (openAt.value === d.at) {
    openAt.value = null
  } else {
    if (readHandle) readHandle.stop()
    readingAt.value = ''
    openAt.value = d.at
  }
}

async function save() {
  const text = draft.value.trim()
  if (!text || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const data = await addDiary(text, mood.value)
    entries.value = [data.diary, ...entries.value].slice(0, 50)
    openAt.value = data.diary.at          // 自动展开刚保存的这篇，让回信可见
    latestAt.value = data.diary.at
    riskLevel.value = data.riskLevel === undefined || data.riskLevel === null ? null : data.riskLevel
    riskReason.value = data.riskReason || ''
    addRiskRecord({ level: riskLevel.value, reason: riskReason.value, message: text, source: '心情日记' })
    draft.value = ''
    mood.value = null
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    busy.value = false
  }
}

function toggleRead(d) {
  if (readingAt.value === d.at) {
    if (readHandle) readHandle.stop()
    readingAt.value = ''
    return
  }
  if (!d.reply) return
  readHandle = speakOnce(plainText(d.reply), {
    ...ttsPrefs.value,
    onEnd: () => { readingAt.value = '' }
  })
  readingAt.value = d.at
}

async function copyReply(d) {
  if (!d.reply) return
  try {
    await navigator.clipboard.writeText(d.reply)
  } catch (e) {
    const ta = document.createElement('textarea')
    ta.value = d.reply
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  copiedAt.value = d.at
  setTimeout(() => { if (copiedAt.value === d.at) copiedAt.value = '' }, 2000)
}
</script>

<style scoped>
/* 极简纸页：单栏、无侧栏、大留白 */
.diary-view { grid-template-columns: minmax(0, 1fr); }
.diary-view .pane { align-items: flex-start; overflow-y: auto; padding: 28px 20px 48px; }

.paper {
  width: 100%; max-width: 560px; margin: 0 auto;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-l); padding: 36px 40px 32px;
  box-shadow: var(--sh-1);
}

.paper-head { margin-bottom: 24px; }
.paper-date { font-size: 15px; font-weight: 650; color: var(--ink); margin: 0; }

.mood-block { margin-bottom: 22px; }
.mood-label { font-size: 12px; color: var(--ink-3); margin-bottom: 10px; }
.mood-row { display: flex; gap: 8px; }
.mood-btn {
  flex: 1; display: grid; place-items: center;
  background: var(--surface-2); border: 1px solid var(--line); border-radius: var(--r-m);
  padding: 10px 0; cursor: pointer; transition: border-color .15s, background .15s;
}
.mood-btn:hover { border-color: var(--primary-2); }
.mood-btn.on { background: var(--primary-soft); border-color: var(--primary); }
.mood-emoji { font-size: 24px; line-height: 1; }

textarea {
  width: 100%; border: 1px solid var(--line); border-radius: var(--r-m);
  padding: 12px 14px; font-size: 14px; line-height: 1.8; font-family: inherit;
  resize: vertical; background: var(--surface); color: var(--ink); min-height: 130px;
}
textarea:focus { outline: 2px solid var(--primary-2); border-color: transparent; }
.paper-acts { display: flex; justify-content: flex-end; margin-top: 12px; }

.history { margin-top: 30px; }
.entry-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.entry { border-top: 1px dashed var(--line-2); }
.entry.open { background: var(--surface-2); margin: 0 -14px; padding: 0 14px; border-radius: var(--r-s); border-top-color: transparent; }
.entry-row {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 12px 0; background: none; border: none; cursor: pointer; text-align: left;
}
.entry-row:hover .entry-preview { color: var(--primary-ink); }
.entry-emoji { font-size: 17px; line-height: 1; flex: none; }
.entry-date { font-size: 11.5px; color: var(--ink-3); flex: none; }
.entry-preview {
  font-size: 13.5px; color: var(--ink-2); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0;
}
.entry-detail { padding: 2px 0 14px; }
.entry-text { font-size: 14px; line-height: 1.9; color: var(--ink); white-space: pre-wrap; margin: 0; }
.entry-reply {
  display: flex; gap: 8px; margin-top: 10px; padding: 10px 12px;
  background: var(--surface); border-radius: var(--r-s); color: var(--ink-2);
}
.entry-reply p { font-size: 13px; line-height: 1.8; margin: 0; }
.entry-risk { margin-top: 10px; }
.entry-acts { display: flex; gap: 8px; margin-top: 12px; }

.empty { text-align: center; padding: 26px 0 6px; }
.empty-emoji { font-size: 26px; display: block; margin-bottom: 8px; }
.empty p { font-size: 12.5px; margin: 0; }
</style>
