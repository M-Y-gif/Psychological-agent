<template>
  <section class="view">
    <div class="pane">
      <header class="topbar">
        <div>
          <h2 class="topbar-title">放松小游戏 · 呼吸练习</h2>
          <div class="topbar-meta">{{ patternLabel }} 节奏 · 第 {{ round }} / {{ ROUNDS }} 轮</div>
        </div>
        <div class="grow"></div>
        <span class="chip"><Icon name="breath" size="s" />已进行 {{ elapsedText }}</span>
      </header>

      <div class="breath-wrap">
        <div v-if="finished" class="done">
          <div class="done-mark"><Icon name="check" size="l" /></div>
          <h3>完成 {{ ROUNDS }} 轮练习</h3>
          <p class="muted">这次用了 {{ elapsedText }}。留意一下现在的身体感觉，和开始前有什么不同。</p>
          <button class="btn btn-p" type="button" @click="start">再来一轮</button>
        </div>

        <template v-else>
          <div class="orb" :style="orbStyle">
            <svg class="ring" viewBox="0 0 200 200" aria-hidden="true">
              <circle cx="100" cy="100" r="88" fill="none" stroke="var(--line)" stroke-width="3" />
              <circle cx="100" cy="100" r="88" fill="none" stroke="var(--primary)" stroke-width="3.4"
                      stroke-linecap="round" :stroke-dasharray="CIRC" :stroke-dashoffset="dashOffset"
                      transform="rotate(-90 100 100)" />
            </svg>
            <div class="glow" :class="`ph-${phase}`">
              <div class="glow-inner">
                <div class="ph" aria-live="polite">{{ phaseText }}</div>
                <div class="cd">{{ countdown }}</div>
              </div>
            </div>
          </div>

          <div class="dots" aria-hidden="true">
            <i v-for="i in ROUNDS" :key="i" :class="{ on: i === round, done: i < round }"></i>
          </div>
          <p class="rounds muted">
            吸气 {{ DURATION.inhale }} 秒 → 屏住 {{ DURATION.hold }} 秒 → 呼气 {{ DURATION.exhale }} 秒
          </p>

          <div class="controls">
            <button v-if="!running" class="btn btn-p" type="button" @click="primary">
              <Icon name="play" size="s" />{{ paused ? '继续' : '开始练习' }}
            </button>
            <button v-else class="btn btn-p" type="button" @click="pause">
              <Icon name="pause" size="s" />暂停
            </button>
            <button v-if="running || paused" class="btn btn-g" type="button" @click="stop">结束</button>
          </div>
        </template>
      </div>
    </div>

    <aside class="side">
      <div class="side-block">
        <div class="side-head"><h3>节奏设置</h3></div>
        <div class="card knobs">
          <div class="knob">
            <span class="knob-k">呼吸节奏</span>
            <div class="seg">
              <button v-for="p in PATTERNS" :key="p.label" type="button"
                      :class="{ on: p.label === patternLabel }"
                      :disabled="running"
                      @click="setPattern(p)">{{ p.label }}</button>
            </div>
          </div>
          <div class="knob">
            <span class="knob-k">提示音</span>
            <button type="button" class="sw" :class="{ off: !sound }" role="switch" :aria-checked="sound ? 'true' : 'false'"
                    :aria-label="sound ? '关闭提示音' : '开启提示音'" @click="toggleSound">
              <span class="sr-only">提示音</span>
            </button>
          </div>
          <div class="knob">
            <span class="knob-k">减少动效</span>
            <button type="button" class="sw" :class="{ off: !reduced }" role="switch" :aria-checked="reduced ? 'true' : 'false'"
                    :aria-label="reduced ? '关闭减少动效' : '开启减少动效'" @click="toggleReduced">
              <span class="sr-only">减少动效</span>
            </button>
          </div>
        </div>
      </div>

      <div class="side-block">
        <div class="side-head"><h3>练习记录</h3><span class="side-sub">本机保存</span></div>
        <div class="stats">
          <div class="card stat"><div class="n">{{ stats.sessions }}</div><div class="l">完成次数</div></div>
          <div class="card stat"><div class="n">{{ Math.round(stats.seconds / 60) }}</div><div class="l">累计分钟</div></div>
        </div>
      </div>

      <div class="side-block">
        <div class="side-head"><h3>为什么这样呼吸</h3></div>
        <div class="card prose">
          呼气长于吸气会轻度激活<b>副交感神经</b>，让心率和呼吸频率一起慢下来。<br>
          屏息的那几秒是给注意力一个落脚点——如果走神了，把注意力带回圆圈就好，
          这本身就是练习的一部分。
        </div>
      </div>
    </aside>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Icon from './ui/Icon.vue'
import { breathStatsKey } from '../store'

const props = defineProps({
  /** 主动关怀带来的呼吸练习请求：命中后自动开始 */
  autoStartPattern: { type: String, default: '' }
})
const emit = defineEmits(['consumed'])

const ROUNDS = 3
const CIRC = 2 * Math.PI * 88
const PATTERNS = [
  { label: '4-4-6', inhale: 4, hold: 4, exhale: 6, hint: '放松入门' },
  { label: '4-7-8', inhale: 4, hold: 7, exhale: 8, hint: '助眠' }
]

const running = ref(false)
const paused = ref(false)
const finished = ref(false)
const phase = ref('inhale')
const progress = ref(0)
const round = ref(1)
const pattern = ref(PATTERNS[0])
const sound = ref(false)
const reduced = ref(false)
const elapsedSec = ref(0)
const stats = ref(loadStats())

let rafId = null
let phaseStart = 0
let elapsedInPhase = 0
let tickStart = 0

const DURATION = computed(() => ({
  inhale: pattern.value.inhale,
  hold: pattern.value.hold,
  exhale: pattern.value.exhale
}))
const patternLabel = computed(() => pattern.value.label)
const phaseText = computed(() => ({ inhale: '吸气', hold: '屏住', exhale: '呼气' }[phase.value]))
const countdown = computed(() => {
  const dur = DURATION.value[phase.value]
  return Math.max(0, Math.ceil(dur - elapsedInPhase / 1000))
})
const dashOffset = computed(() => CIRC * (1 - progress.value))
const orbStyle = computed(() => {
  if (reduced.value) return {}
  let scale = 1
  if (phase.value === 'inhale') scale = 0.72 + 0.28 * progress.value
  else if (phase.value === 'exhale') scale = 1 - 0.28 * progress.value
  return { transform: `scale(${scale.toFixed(3)})` }
})
const elapsedText = computed(() => {
  const s = Math.floor(elapsedSec.value)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
})

if (typeof window !== 'undefined' && window.matchMedia) {
  reduced.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function loadStats() {
  try {
    const raw = localStorage.getItem(breathStatsKey())
    if (raw) return JSON.parse(raw)
    // 旧版本不分使用者：迁移一次历史数据
    const legacy = localStorage.getItem('psy.breath.stats')
    if (legacy) {
      const parsed = JSON.parse(legacy)
      localStorage.removeItem('psy.breath.stats')
      return parsed
    }
  } catch (e) { /* 忽略隐私模式下的存储异常 */ }
  return { sessions: 0, seconds: 0 }
}
function saveStats() {
  try { localStorage.setItem(breathStatsKey(), JSON.stringify(stats.value)) } catch (e) { /* 忽略 */ }
}

function setPattern(p) {
  pattern.value = p
}
function toggleSound() {
  sound.value = !sound.value
}
function toggleReduced() {
  reduced.value = !reduced.value
}

/** 相位切换时给一声轻提示（默认关闭） */
function beep(freq) {
  if (!sound.value) return
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.frequency.value = freq
    osc.type = 'sine'
    gain.gain.setValueAtTime(0.0001, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.06, ctx.currentTime + 0.05)
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5)
    osc.connect(gain).connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.55)
    osc.onended = () => ctx.close()
  } catch (e) { /* 音频不可用时静默忽略 */ }
}

function start() {
  finished.value = false
  running.value = true
  paused.value = false
  round.value = 1
  elapsedSec.value = 0
  tickStart = 0
  enterPhase('inhale')
}

function enterPhase(p) {
  phase.value = p
  progress.value = 0
  elapsedInPhase = 0
  phaseStart = 0
  beep(p === 'inhale' ? 528 : p === 'hold' ? 396 : 352)
  loop()
}

function loop() {
  cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(tick)
}

function tick(now) {
  if (!running.value || paused.value) return
  if (!phaseStart) phaseStart = now
  if (!tickStart) tickStart = now
  elapsedInPhase = now - phaseStart
  elapsedSec.value += (now - (tick.last || now)) / 1000
  tick.last = now

  const dur = DURATION.value[phase.value] * 1000
  progress.value = Math.min(1, elapsedInPhase / dur)

  if (elapsedInPhase >= dur) {
    advance()
    return
  }
  rafId = requestAnimationFrame(tick)
}

function advance() {
  if (phase.value === 'inhale') return enterPhase('hold')
  if (phase.value === 'hold') return enterPhase('exhale')
  if (round.value >= ROUNDS) return complete()
  round.value += 1
  return enterPhase('inhale')
}

function complete() {
  cancelAnimationFrame(rafId)
  running.value = false
  paused.value = false
  finished.value = true
  phase.value = 'inhale'
  progress.value = 0
  stats.value = {
    sessions: stats.value.sessions + 1,
    seconds: stats.value.seconds + Math.round(elapsedSec.value)
  }
  saveStats()
}

function pause() {
  paused.value = true
  running.value = false
  cancelAnimationFrame(rafId)
  tick.last = 0
}

function resume() {
  running.value = true
  paused.value = false
  phaseStart = performance.now() - elapsedInPhase
  tick.last = 0
  loop()
}

function stop() {
  cancelAnimationFrame(rafId)
  running.value = false
  paused.value = false
  finished.value = false
  phase.value = 'inhale'
  progress.value = 0
  elapsedInPhase = 0
  round.value = 1
  elapsedSec.value = 0
  tick.last = 0
}

onBeforeUnmount(() => cancelAnimationFrame(rafId))

onMounted(() => {
  // 主动关怀发起：命中指定呼吸模式并自动开始，然后通知 App 已消费
  if (props.autoStartPattern) {
    const p = PATTERNS.find(x => x.label === props.autoStartPattern) || PATTERNS[0]
    setPattern(p)
    start()
    emit('consumed')
  }
})

/** 主按钮：未开始时 start，暂停后 resume */
function primary() {
  if (paused.value && elapsedInPhase > 0) resume()
  else start()
}
</script>

<style scoped>
.breath-wrap {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 20px; padding: 28px 20px;
}

.orb {
  position: relative; width: 238px; height: 238px;
  display: grid; place-items: center;
  transition: transform .12s linear;
}
.ring { position: absolute; inset: 0; width: 100%; height: 100%; }
.glow {
  width: 168px; height: 168px; border-radius: 50%;
  display: grid; place-items: center; color: #fff;
  background: radial-gradient(circle at 38% 32%, #6FBCAB 0%, #3E8E7D 46%, #24685C 100%);
  box-shadow: 0 18px 44px rgba(36, 104, 92, .34), inset 0 2px 12px rgba(255, 255, 255, .28);
  transition: background .4s ease;
}
.glow.ph-hold {
  background: radial-gradient(circle at 38% 32%, #7CC3D4 0%, #46889B 46%, #2A5F70 100%);
  box-shadow: 0 18px 44px rgba(42, 95, 112, .34), inset 0 2px 12px rgba(255, 255, 255, .28);
}
.glow.ph-exhale {
  background: radial-gradient(circle at 38% 32%, #8FC0A9 0%, #4E8F70 46%, #2F6349 100%);
  box-shadow: 0 18px 44px rgba(47, 99, 73, .32), inset 0 2px 12px rgba(255, 255, 255, .26);
}
.glow-inner { text-align: center; }
.ph { font-size: 21px; font-weight: 600; letter-spacing: .06em; }
.cd { font-size: 34px; font-weight: 300; line-height: 1.15; font-variant-numeric: tabular-nums; }

.dots { display: flex; gap: 7px; align-items: center; }
.dots i { width: 6px; height: 6px; border-radius: 50%; background: #CDD3D1; }
.dots i.on { background: var(--primary); width: 18px; border-radius: 99px; }
.dots i.done { background: var(--primary); opacity: .45; }

.rounds { font-size: 12.5px; }
.controls { display: flex; gap: 10px; }

.done { text-align: center; display: flex; flex-direction: column; align-items: center; gap: 10px; }
.done-mark {
  width: 48px; height: 48px; border-radius: 14px; display: grid; place-items: center;
  background: var(--primary-soft); color: var(--primary-ink);
}
.done h3 { font-size: 16px; font-weight: 650; }
.done .btn { margin-top: 6px; }

/* 右侧设置 */
.knobs { padding: 4px 12px; }
.knob { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 0; }
.knob + .knob { border-top: 1px solid var(--line); }
.knob-k { font-size: 12.5px; color: var(--ink-2); }

.seg { display: flex; gap: 2px; padding: 3px; background: var(--surface-3); border-radius: 9px; }
.seg button {
  padding: 4px 9px; border-radius: 7px; font-size: 11.5px; color: var(--ink-2);
  font-variant-numeric: tabular-nums;
}
.seg button.on { background: var(--surface); color: var(--ink); font-weight: 600; box-shadow: var(--sh-1); }
.seg button:disabled { opacity: .55; cursor: not-allowed; }

.sw {
  width: 36px; height: 21px; border-radius: var(--r-full); background: var(--primary);
  position: relative; flex: none; transition: background .18s ease;
}
.sw::after {
  content: ''; position: absolute; top: 2.5px; right: 2.5px;
  width: 16px; height: 16px; border-radius: 50%; background: #fff;
  transition: transform .18s ease, right .18s ease;
}
.sw.off { background: #D4D8D7; }
.sw.off::after { right: calc(100% - 18.5px); }

.stats { display: flex; gap: 10px; }
.stat { flex: 1; padding: 11px; }
.stat .n { font-size: 19px; font-weight: 600; font-variant-numeric: tabular-nums; }
.stat .l { font-size: 10.5px; color: var(--ink-3); }

.prose { padding: 12px; font-size: 12.5px; line-height: 1.85; color: var(--ink-2); }
.prose b { color: var(--ink); font-weight: 600; }

@media (max-width: 720px) {
  .orb { width: 200px; height: 200px; }
  .glow { width: 142px; height: 142px; }
  .cd { font-size: 30px; }
}
</style>
