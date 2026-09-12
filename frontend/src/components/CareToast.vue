<template>
  <div v-if="unreadCare.length" class="care-toast" role="status" aria-live="polite">
    <div class="ct-head">
      <span class="ct-head-left"><Icon name="bell" size="s" />晚晴的主动关心</span>
      <button class="ct-close" type="button" aria-label="全部关闭" @click="dismissAll">
        <Icon name="close" size="s" />
      </button>
    </div>
    <div class="ct-body">
      <div v-for="c in unreadCare" :key="c.id" class="ct-item">
        <span class="ct-tag" :class="`tag-${c.type || 'message'}`">{{ typeLabel(c.type) }}</span>
        <p class="ct-text">{{ plainText(c.text || '') }}</p>

        <!-- 睡前故事：可展开阅读 / 朗读 -->
        <div v-if="c.type === 'story' && c.payload && c.payload.title" class="ct-story">
          <button class="btn btn-sm btn-line" type="button" @click="toggleStory(c.id)">
            {{ storyOpen === c.id ? '收起故事' : '看看故事' }}
          </button>
          <template v-if="storyOpen === c.id">
            <p class="ct-story-title">{{ c.payload.title }}</p>
            <p class="ct-story-content">{{ c.payload.content }}</p>
          </template>
        </div>

        <div class="ct-actions">
          <template v-if="c.type === 'breath'">
            <button class="btn btn-sm" type="button" @click="startBreath(c)">
              <Icon name="breath" size="s" />开始呼吸练习
            </button>
          </template>
          <template v-else-if="c.type === 'story' && c.payload && c.payload.content">
            <button class="btn btn-sm btn-line" type="button" @click="readStory(c)">
              <Icon name="volume" size="s" />{{ reading === c.id ? '停止朗读' : '读给我听' }}
            </button>
          </template>
          <button class="btn btn-sm btn-line" type="button" @click="dismissCare(c.id)">好的</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import Icon from './ui/Icon.vue'
import { plainText } from '../utils/text'
import { speakOnce } from '../utils/tts'
import { unreadCare, dismissCare, requestBreath, ttsPrefs } from '../store'

const storyOpen = ref('')
const reading = ref('')
let readHandle = null

function typeLabel(type) {
  if (type === 'breath') return '呼吸练习'
  if (type === 'story') return '睡前故事'
  return '主动关心'
}

function toggleStory(id) {
  storyOpen.value = storyOpen.value === id ? '' : id
}

function startBreath(c) {
  requestBreath(c.payload && c.payload.pattern)
  dismissCare(c.id)
}

function readStory(c) {
  if (reading.value === c.id) {
    if (readHandle) { readHandle.stop(); readHandle = null }
    reading.value = ''
    return
  }
  if (readHandle) readHandle.stop()
  reading.value = c.id
  const text = `${c.payload.title}。${c.payload.content}`
  readHandle = speakOnce(text, { ...ttsPrefs.value, onEnd: () => { reading.value = '' } })
}

function dismissAll() {
  unreadCare.value.forEach(c => dismissCare(c.id))
}

onBeforeUnmount(() => {
  if (readHandle) readHandle.stop()
})
</script>

<style scoped>
.care-toast {
  position: fixed; right: 20px; bottom: 20px; z-index: 60;
  width: 320px; max-width: calc(100vw - 40px); max-height: 60vh;
  display: flex; flex-direction: column;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-m); box-shadow: var(--sh-2); overflow: hidden;
}
.ct-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; background: var(--primary-soft);
  font-size: 12.5px; font-weight: 650; color: var(--primary);
}
.ct-head-left { display: flex; align-items: center; gap: 6px; }
.ct-close {
  border: 0; background: none; color: var(--ink-2); cursor: pointer;
  display: grid; place-items: center; padding: 2px; border-radius: 6px;
}
.ct-close:hover { color: var(--ink); background: rgba(0, 0, 0, .05); }
.ct-body { overflow-y: auto; padding: 8px 12px 12px; display: flex; flex-direction: column; gap: 10px; }
.ct-item {
  padding: 10px 12px; border: 1px solid var(--line); border-radius: var(--r-s);
  background: var(--surface-2, #FBFDFC);
}
.ct-tag {
  display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 99px; margin-bottom: 6px;
}
.ct-tag.tag-message { background: var(--primary-soft); color: var(--primary); }
.ct-tag.tag-breath { background: var(--safe-bg); color: var(--safe-fg); }
.ct-tag.tag-story { background: var(--warn-bg); color: var(--warn-fg); }
.ct-text { font-size: 13px; line-height: 1.75; color: var(--ink); white-space: pre-wrap; margin: 0; }
.ct-story { margin-top: 8px; }
.ct-story-title { font-size: 13px; font-weight: 650; color: var(--ink); margin: 8px 0 4px; }
.ct-story-content {
  font-size: 12.5px; line-height: 1.8; color: var(--ink-2);
  max-height: 180px; overflow-y: auto; white-space: pre-wrap; margin: 0;
  border-left: 2px solid var(--line); padding-left: 8px;
}
.ct-actions { display: flex; gap: 8px; margin-top: 9px; flex-wrap: wrap; }
</style>
