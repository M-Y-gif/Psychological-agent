<template>
  <section class="view memory-view">
    <div class="pane">
      <header class="topbar">
        <div class="topbar-title">它眼里的你</div>
        <div class="topbar-meta">
          {{ loading ? '正在打开它的记忆…' : `${mem.name || '你'} · 从 ${sinceText} 开始陪伴` }}
        </div>
      </header>

      <div class="memory-body">
        <div v-if="error" class="error-box" role="alert">
          <Icon name="warn" size="s" /><span>{{ error }}</span>
          <button type="button" class="btn btn-sm" @click="load">重试</button>
        </div>

        <template v-if="!loading && !error">
          <!-- 档案 -->
          <div class="card profile-card">
            <div class="kv">
              <div class="kv-item"><span class="kv-k">整体情绪</span><span class="kv-v">{{ overallText }}</span></div>
              <div class="kv-item"><span class="kv-k">最近活跃</span><span class="kv-v">{{ mem.lastActive || '—' }}</span></div>
              <div class="kv-item"><span class="kv-k">最近风险</span><span class="kv-v">
                <span v-if="lastRisk" class="pill" :class="`pill-${lastRisk.tone}`">{{ lastRisk.label }}</span>
                <span v-else class="muted">暂无</span>
              </span></div>
              <div class="kv-item"><span class="kv-k">陪伴对话</span><span class="kv-v">{{ mem.turnCount || 0 }} 轮</span></div>
            </div>
            <p v-if="mem.emotionTrend" class="trend-quote">最近一次会话分析的印象：{{ mem.emotionTrend }}</p>
          </div>

          <!-- 情绪轨迹 -->
          <div class="card chart-card">
            <div class="side-head">
              <h3>情绪轨迹</h3>
              <span class="chip">最近 {{ points.length }} 次记录</span>
            </div>
            <svg class="chart" viewBox="0 0 260 56" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <linearGradient id="moodFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#2E7D6F" stop-opacity=".22" />
                  <stop offset="100%" stop-color="#2E7D6F" stop-opacity="0" />
                </linearGradient>
              </defs>
              <path d="M4,28 L256,28" stroke="#B9C6C3" stroke-width="1" stroke-dasharray="3 3" />
              <path v-if="areaPath" :d="areaPath" fill="url(#moodFill)" />
              <path v-if="linePath" :d="linePath" fill="none" stroke="#2E7D6F" stroke-width="2"
                    stroke-linecap="round" stroke-linejoin="round" />
              <circle v-if="points.length === 1" cx="4" :cy="yOf(points[0].score)" r="2" fill="#2E7D6F" />
            </svg>
            <div class="chart-axis"><span>较早</span><span>最近</span></div>
            <p v-if="!points.length" class="muted chart-empty">还没有情绪记录，聊几句或写篇日记就有了。</p>
            <div v-else class="chart-legend">
              <span v-if="sourceCount.chat" class="legend-item"><i class="dot dot-chat" />聊天 {{ sourceCount.chat }}</span>
              <span v-if="sourceCount.diary" class="legend-item"><i class="dot dot-diary" />日记打卡 {{ sourceCount.diary }}</span>
              <span v-if="sourceCount.session" class="legend-item"><i class="dot dot-session" />会话分析 {{ sourceCount.session }}</span>
            </div>
          </div>

          <!-- 记住的事 -->
          <div class="card facts-card">
            <div class="side-head"><h3>它记得的事</h3><span class="muted">{{ mem.facts.length }} 条</span></div>
            <div v-if="!mem.facts.length" class="muted">还没有沉淀下来的事实，多聊聊就有了。</div>
            <ul v-else class="fact-list">
              <li v-for="(f, i) in mem.facts" :key="i" class="fact">
                <Icon name="heart" size="s" /><span>{{ f }}</span>
              </li>
            </ul>
          </div>

          <!-- 最近的日记 -->
          <div class="card diary-card">
            <div class="side-head"><h3>最近的日记</h3></div>
            <div v-if="!mem.diary.length" class="muted">还没有日记，去「心情日记」写下第一篇吧。</div>
            <div v-else class="entry-list">
              <article v-for="(d, i) in mem.diary.slice(0, 5)" :key="(d.at || '') + i" class="entry">
                <div class="entry-head">
                  <span class="entry-mood" aria-hidden="true">{{ emojiOf(d.mood) }}</span>
                  <span class="entry-date">{{ d.at }}</span>
                </div>
                <p class="entry-text">{{ d.text }}</p>
                <div v-if="d.reply" class="entry-reply">
                  <Icon name="mark" size="s" />
                  <p>{{ d.reply }}</p>
                </div>
              </article>
            </div>
          </div>
        </template>
      </div>
    </div>

    <aside class="side">
      <div class="side-block">
        <div class="side-head"><h3>关怀记录</h3></div>
        <div v-if="!careList.length" class="muted">还没有主动关怀，它会在合适的时候来找你。</div>
        <ul v-else class="care-list">
          <li v-for="c in careList" :key="c.at + c.text" class="care-item">
            <div class="care-head">
              <Icon :name="careIcon(c.type)" size="s" />
              <span class="care-reason">{{ c.reason }}</span>
              <span class="care-time">{{ c.at }}</span>
            </div>
            <p class="care-text">{{ c.text }}</p>
          </li>
        </ul>
      </div>
      <div class="side-block prose">
        <p>这里的所有内容都来自你们真实的对话与日记，只存在你自己的设备数据目录里。</p>
        <p>它用这些记忆让每次聊天都接得上话；如果哪天想清空，删掉对应记忆文件即可。</p>
      </div>
    </aside>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchMemory } from '../api'
import { riskMeta } from '../store'
import Icon from './ui/Icon.vue'

const MOODS = {
  1: '😞', 2: '😕', 3: '😐', 4: '🙂', 5: '😄'
}

const mem = ref({
  name: '', since: '', facts: [], diary: [], care: [], moodScores: [],
  overallMood: '', emotionTrend: '', lastActive: '', lastRiskLevel: '', turnCount: 0
})
const loading = ref(true)
const error = ref('')

onMounted(load)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const m = await fetchMemory()
    // 与旧版接口缺字段时兜底，避免模板访问 undefined
    mem.value = { ...mem.value, ...m }
  } catch (e) {
    error.value = e.message || '记忆加载失败'
  } finally {
    loading.value = false
  }
}

const sinceText = computed(() => (mem.value.since || '').slice(0, 10) || '…')
const overallText = computed(() => ({
  negative: '偏低', positive: '不错', neutral: '平稳'
}[mem.value.overallMood] || '暂无'))
const lastRisk = computed(() => {
  const lv = parseInt(mem.value.lastRiskLevel, 10)
  return Number.isNaN(lv) ? null : riskMeta(lv)
})

const points = computed(() => (mem.value.moodScores || []).slice(-24))
const sourceCount = computed(() => {
  const c = { chat: 0, diary: 0, session: 0 }
  for (const s of mem.value.moodScores || []) {
    const k = s.source || 'chat'
    if (c[k] !== undefined) c[k]++
  }
  return c
})
function yOf(score) {
  const s = Math.max(-3, Math.min(3, Number(score) || 0))
  return (28 - s * 7.5).toFixed(1)
}
const linePath = computed(() => {
  const n = points.value.length
  if (!n) return ''
  const step = n > 1 ? 252 / (n - 1) : 0
  return points.value.map((p, i) =>
    `${i === 0 ? 'M' : 'L'}${(4 + i * step).toFixed(1)},${yOf(p.score)}`).join(' ')
})
const areaPath = computed(() => {
  const n = points.value.length
  if (n < 2) return ''
  const lastX = (4 + 252).toFixed(1)
  return `${linePath.value} L${lastX},56 L4,56 Z`
})

const careList = computed(() => [...(mem.value.care || [])].reverse())
function careIcon(type) {
  return type === 'breath' ? 'breath' : type === 'story' ? 'spark' : 'chat'
}
function emojiOf(v) {
  return MOODS[v] || '📝'
}
</script>

<style scoped>
.memory-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; max-width: 760px; }

.side-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.side-head h3 { font-size: 14px; font-weight: 650; color: var(--ink); margin: 0 0 12px; }

.kv { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px 20px; }
.kv-item { display: flex; flex-direction: column; gap: 4px; }
.kv-k { font-size: 11.5px; color: var(--ink-3); }
.kv-v { font-size: 13.5px; color: var(--ink); font-weight: 550; }
.trend-quote {
  margin: 14px 0 0; padding: 10px 12px; font-size: 12.5px; line-height: 1.8;
  color: var(--ink-2); background: var(--surface-2); border-radius: var(--r-s);
  border-left: 3px solid var(--primary-2);
}

.chart { width: 100%; height: 56px; display: block; }
.chart-axis { display: flex; justify-content: space-between; font-size: 10.5px; color: var(--ink-3); margin-top: 4px; }
.chart-empty { font-size: 12px; margin: 8px 0 0; text-align: center; }
.chart-legend { display: flex; gap: 14px; margin-top: 8px; flex-wrap: wrap; }
.legend-item { display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; color: var(--ink-2); }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-chat { background: var(--primary-2); }
.dot-diary { background: #C9A227; }
.dot-session { background: #7C8DB5; }

.fact-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.fact {
  display: flex; align-items: center; gap: 8px; font-size: 13.5px; color: var(--ink);
  background: var(--surface-2); border-radius: var(--r-s); padding: 10px 12px;
}
.fact :deep(.ic) { color: var(--primary); flex: none; }

.entry-list { display: flex; flex-direction: column; gap: 12px; }
.entry { border: 1px solid var(--line); border-radius: var(--r-s); padding: 12px 14px; }
.entry-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.entry-mood { font-size: 18px; line-height: 1; }
.entry-date { font-size: 11.5px; color: var(--ink-3); }
.entry-text { font-size: 13.5px; line-height: 1.8; color: var(--ink); white-space: pre-wrap; margin: 0; }
.entry-reply { display: flex; gap: 8px; margin-top: 8px; padding: 8px 10px; background: var(--surface-2); border-radius: var(--r-s); color: var(--ink-2); }
.entry-reply p { font-size: 12.5px; line-height: 1.8; margin: 0; }

.care-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.care-item { border-bottom: 1px dashed var(--line-2); padding-bottom: 12px; }
.care-item:last-child { border-bottom: none; padding-bottom: 0; }
.care-head { display: flex; align-items: center; gap: 6px; }
.care-head :deep(.ic) { color: var(--primary); flex: none; }
.care-reason { font-size: 11px; color: var(--ink-3); flex: 1; }
.care-time { font-size: 11px; color: var(--ink-3); }
.care-text { font-size: 12.5px; line-height: 1.8; color: var(--ink); margin: 6px 0 0; white-space: pre-wrap; }

.prose p { font-size: 12.5px; color: var(--ink-2); line-height: 1.8; margin: 0 0 8px; }
</style>
