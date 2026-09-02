<template>
  <div class="game">
    <h2 class="title">🌬️ 放松小游戏：呼吸练习</h2>
    <p class="sub">跟随圆圈的节奏呼吸：吸气 4 秒 → 屏住 4 秒 → 呼气 6 秒，重复 3 轮。</p>

    <div class="circle-wrap">
      <div class="circle" :class="phase" :style="circleStyle">
        <span class="phase-text">{{ phaseText }}</span>
      </div>
    </div>

    <div class="controls">
      <button v-if="!running" @click="start">开始练习</button>
      <button v-else class="secondary" @click="stop">停止</button>
    </div>
    <p class="round">第 {{ round }} / 3 轮 · {{ countdown }}</p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const running = ref(false)
const phase = ref('inhale')   // inhale | hold | exhale
const countdown = ref(4)
const round = ref(1)
let timer = null

const DURATION = { inhale: 4, hold: 4, exhale: 6 }

const phaseText = computed(() => ({
  inhale: '吸气',
  hold: '屏住',
  exhale: '呼气'
}[phase.value]))

const circleStyle = computed(() => {
  const scale = phase.value === 'inhale' ? 1.6 : phase.value === 'hold' ? 1.6 : 1.0
  return { transform: `scale(${scale})` }
})

function start() {
  running.value = true
  round.value = 1
  runPhase('inhale')
}

function stop() {
  running.value = false
  clearInterval(timer)
  phase.value = 'inhale'
  countdown.value = 4
}

function runPhase(p) {
  phase.value = p
  countdown.value = DURATION[p]
  clearInterval(timer)
  timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      const next = p === 'inhale' ? 'hold' : p === 'hold' ? 'exhale' : 'inhale'
      if (p === 'exhale') {
        if (round.value >= 3) { stop(); return }
        round.value++
      }
      runPhase(next)
    }
  }, 1000)
}
</script>

<style scoped>
.title { font-size: 18px; }
.sub { color: #6b7280; font-size: 12px; margin: 6px 0 18px; }
.circle-wrap { display: flex; justify-content: center; padding: 30px 0; }
.circle {
  width: 140px; height: 140px; border-radius: 50%;
  background: radial-gradient(circle, #a5b4fc 0%, #6366f1 100%);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 20px; font-weight: 600;
  transition: transform 1s ease-in-out; box-shadow: 0 10px 30px rgba(99,102,241,.35);
}
.controls { text-align: center; }
.round { text-align: center; color: #6b7280; font-size: 13px; margin-top: 12px; }
</style>
