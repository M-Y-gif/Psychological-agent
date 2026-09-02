<template>
  <div v-if="riskLevel != null" :class="['risk', riskLevel >= 2 ? 'high' : 'low']">
    <template v-if="riskLevel >= 2">
      ⚠️ <b>检测到高风险信号（等级 {{ riskLevel }}/3）</b><br>
      {{ reason }}<br>
      建议立即联系心理援助热线 <b>12356</b> 或寻求线下专业帮助。
    </template>
    <template v-else>
      风险等级 {{ riskLevel }}/3（{{ reason }}）
    </template>
  </div>
</template>

<script setup>
defineProps({
  riskLevel: { type: Number, default: null },
  reason: { type: String, default: '' }
})
</script>

<style scoped>
.risk { border-radius: 10px; padding: 12px 14px; font-size: 13px; line-height: 1.7; margin-top: 12px; }
.high { background: #fff1f2; border: 1px solid #fecdd3; color: #be123c; }
.high b { font-size: 15px; }
.low { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
</style>
