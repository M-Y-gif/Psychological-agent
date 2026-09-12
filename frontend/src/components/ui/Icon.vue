<template>
  <svg class="ic" :class="sizeClass" aria-hidden="true" focusable="false">
    <use :href="'#ic-' + name" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: String, default: '' }   // '' | 's' | 'l'
})

const sizeClass = computed(() => (props.size ? `ic-${props.size}` : ''))
</script>
