<template>
  <div v-if="riskLevel !== null && riskLevel !== undefined" class="risk-wrap">
    <!-- 高风险（≥2 级）：最高优先级展示，不依赖颜色区分，附可执行动作 -->
    <div v-if="isHigh" class="alert" role="alert">
      <div class="alert-icon"><Icon name="alert" /></div>
      <div class="alert-main">
        <div class="alert-title">风险评估：等级 {{ riskLevel }} / 3 · {{ meta.label }}</div>
        <p v-if="reason" class="alert-reason">{{ reason }}</p>
        <p class="alert-advice">
          建议今天就与信任的人或专业人士聊一聊，不必等到更严重。
        </p>
        <div class="alert-actions">
          <a class="btn btn-sm btn-call" :href="`tel:${HOTLINE.tel}`">
            <Icon name="phone" size="s" />立即拨打求助热线
          </a>
          <button class="btn btn-sm btn-line" type="button" @click="copyScript">
            <Icon name="copy" size="s" />{{ copied ? '已复制' : '复制求助话术' }}
          </button>
        </div>
        <p class="alert-foot">本次研判依据与建议已写入「风险记录」，可随时查看。</p>
      </div>
    </div>

    <!-- 低风险：轻量提示，不抢视线 -->
    <div v-else class="risk-lite" :class="`tone-${meta.tone}`">
      <Icon name="warn" size="s" />
      <span>风险等级 {{ riskLevel }} / 3 · {{ meta.label }}<template v-if="reason">（{{ reason }}）</template></span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import Icon from './ui/Icon.vue'
import { HOTLINE, riskMeta } from '../store'

const props = defineProps({
  riskLevel: { type: Number, default: null },
  reason: { type: String, default: '' }
})

const isHigh = computed(() => props.riskLevel >= 2)
const meta = computed(() => riskMeta(props.riskLevel))
const copied = ref(false)

const SCRIPT = '我现在状态不太好，可能不太安全，能陪我待一会儿吗？如果联系不上我，请帮我联系心理援助热线 12356。'

async function copyScript() {
  try {
    await navigator.clipboard.writeText(SCRIPT)
  } catch (e) {
    const ta = document.createElement('textarea')
    ta.value = SCRIPT
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}
</script>

<style scoped>
.risk-wrap { margin-top: 12px; }

.alert {
  display: flex; gap: 12px;
  background: var(--danger-bg); border: 1px solid var(--danger-line);
  border-radius: var(--r-m); padding: 14px 15px;
}
.alert-icon {
  width: 30px; height: 30px; border-radius: 9px; flex: none;
  background: #F7DCD8; color: var(--danger-fg); display: grid; place-items: center;
}
.alert-main { min-width: 0; }
.alert-title { font-size: 13.5px; font-weight: 650; color: var(--danger-fg); }
.alert-reason { font-size: 12.5px; color: #7C3B34; margin-top: 4px; line-height: 1.7; }
.alert-advice { font-size: 12.5px; color: #7C3B34; margin-top: 4px; line-height: 1.7; }
.alert-actions { display: flex; gap: 8px; margin-top: 11px; flex-wrap: wrap; }
.btn-call { background: var(--danger-fg); color: #fff; text-decoration: none; }
.btn-call:hover { background: #8C1C14; }
.btn-line {
  border-color: #E0B4AE; color: var(--danger-fg);
  background: rgba(255, 255, 255, .6); text-decoration: none;
}
.btn-line:hover { background: #fff; }
.alert-foot { font-size: 11px; color: #93605A; margin-top: 9px; }

.risk-lite {
  display: flex; align-items: center; gap: 8px;
  border-radius: var(--r-m); padding: 9px 12px; font-size: 12.5px;
}
.risk-lite.tone-safe { background: var(--safe-bg); color: var(--safe-fg); border: 1px solid var(--safe-line); }
.risk-lite.tone-warn { background: var(--warn-bg); color: var(--warn-fg); border: 1px solid var(--warn-line); }
.risk-lite.tone-mute { background: var(--surface-3); color: var(--ink-2); border: 1px solid var(--line); }
</style>
