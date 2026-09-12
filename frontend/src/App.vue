<template>
  <IconSprite />

  <!-- 未选择身份时先进入欢迎页 -->
  <EntryView v-if="!currentUser" />

  <div v-else class="app">
    <aside class="rail">
      <div class="brand">
        <div class="brand-mark"><Icon name="mark" size="l" /></div>
        <div>
          <div class="brand-name">心理 Agent</div>
          <div class="brand-sub">预警与咨询</div>
        </div>
      </div>

      <nav class="nav" aria-label="主导航">
        <div class="nav-label">工作区</div>
        <button v-for="item in workTabs" :key="item.key" type="button"
                class="nav-item" :class="{ on: current === item.key }"
                :aria-current="current === item.key ? 'page' : undefined"
                @click="current = item.key">
          <Icon :name="item.icon" />
          <span class="nav-text">{{ item.label }}</span>
          <span v-if="item.key === 'text' && unreadCare.length" class="nav-badge">{{ unreadCare.length }}</span>
        </button>

        <div class="nav-label nav-label-gap">记录</div>
        <button type="button" class="nav-item" :class="{ on: current === 'records' }"
                :aria-current="current === 'records' ? 'page' : undefined"
                @click="current = 'records'">
          <Icon name="shield" />
          <span class="nav-text">风险记录</span>
          <span v-if="myRecords.length" class="nav-badge">{{ myRecords.length }}</span>
        </button>
      </nav>

      <div class="rail-foot">
        <div class="me">
          <div class="me-avatar" aria-hidden="true">{{ initial }}</div>
          <div class="me-main">
            <div class="me-name">{{ currentUser.name }}</div>
            <div class="me-role">{{ roleLabel }}</div>
          </div>
          <button class="icon-btn" type="button" title="切换身份" aria-label="切换身份" @click="signOut">
            <Icon name="logout" size="s" />
          </button>
        </div>

        <div class="status">
          <span class="dot" aria-hidden="true"></span>
          <span>DeepSeek · 已连接</span>
        </div>

        <div class="hotline">
          <div class="hotline-name">{{ HOTLINE.name }}</div>
          <div class="hotline-note">{{ HOTLINE.note }}</div>
          <a class="hotline-btn" :href="`tel:${HOTLINE.tel}`">立即拨打</a>
        </div>
      </div>
    </aside>

    <div class="stage">
      <TextChat v-if="current === 'text'" />
      <VideoChat v-else-if="current === 'video'" />
      <BreathingGame v-else-if="current === 'breath'"
                     :key="breathSeq"
                     :auto-start-pattern="breathAction ? breathAction.pattern : ''"
                     @consumed="consumeBreath" />
      <RiskRecords v-else />
    </div>

    <!-- 主动关怀弹窗：全局挂载，任何 tab 下都能收到 -->
    <CareToast />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Icon from './components/ui/Icon.vue'
import IconSprite from './components/ui/IconSprite.vue'
import EntryView from './components/EntryView.vue'
import TextChat from './components/TextChat.vue'
import VideoChat from './components/VideoChat.vue'
import BreathingGame from './components/BreathingGame.vue'
import RiskRecords from './components/RiskRecords.vue'
import CareToast from './components/CareToast.vue'
import {
  HOTLINE, currentUser, myRecords, roleOf, signOut,
  pollCare, unreadCare, breathAction
} from './store'

const workTabs = [
  { key: 'text', label: '文字对话', icon: 'chat' },
  { key: 'video', label: '视频感知', icon: 'video' },
  { key: 'breath', label: '呼吸练习', icon: 'breath' }
]

const current = ref('text')

// 主动关怀：全局 60 秒轮询一次（切换 tab 不中断）
let careTimer = null
onMounted(() => {
  pollCare()
  careTimer = setInterval(pollCare, 60000)
})
onBeforeUnmount(() => {
  if (careTimer) clearInterval(careTimer)
})

// 关怀里的呼吸练习请求：切到呼吸页并自动开始。
// breathSeq 只在请求到来时 +1，让 BreathingGame 重挂载执行 auto-start；
// 清空 breathAction 不改变 key，避免重复触发。
const breathSeq = ref(0)
watch(breathAction, v => {
  if (v) {
    breathSeq.value += 1
    current.value = 'breath'
  }
})
function consumeBreath() {
  breathAction.value = null
}

const initial = computed(() => {
  const n = currentUser.value ? currentUser.value.name : ''
  return n ? n.trim().slice(0, 1) : '·'
})
const roleLabel = computed(() => roleOf(currentUser.value && currentUser.value.role).label)
</script>

<style scoped>
.rail {
  display: flex; flex-direction: column; gap: 20px;
  padding: 18px 14px; background: var(--surface-2);
  border-right: 1px solid var(--line); overflow-y: auto;
  height: 100vh;
}

.brand { display: flex; align-items: center; gap: 10px; padding: 0 6px; }
.brand-mark {
  width: 34px; height: 34px; border-radius: 10px; flex: none;
  background: linear-gradient(150deg, #3A8E7E, #225F54);
  display: grid; place-items: center; color: #fff;
  box-shadow: 0 3px 8px rgba(36, 104, 92, .28);
}
.brand-name { font-size: 15px; font-weight: 650; letter-spacing: -.01em; }
.brand-sub { font-size: 11px; color: var(--ink-3); letter-spacing: .04em; }

.nav { display: flex; flex-direction: column; gap: 2px; }
.nav-label {
  font-size: 11px; font-weight: 600; letter-spacing: .1em;
  color: var(--ink-3); padding: 0 8px 8px;
}
.nav-label-gap { margin-top: 14px; }
.nav-item {
  display: flex; align-items: center; gap: 11px;
  padding: 9px 10px; border-radius: 9px;
  font-size: 13.5px; color: var(--ink-2); text-align: left;
  transition: background .15s ease, color .15s ease;
}
.nav-item:hover { background: var(--surface-3); }
.nav-item.on { background: var(--primary-soft); color: var(--primary-ink); font-weight: 600; }
.nav-text { flex: 1; }
.nav-badge {
  font-size: 10.5px; font-weight: 700; padding: 1px 7px;
  border-radius: var(--r-full); background: var(--danger-bg); color: var(--danger-fg);
}

.rail-foot { margin-top: auto; display: flex; flex-direction: column; gap: 10px; }

.me {
  display: flex; align-items: center; gap: 9px;
  padding: 9px 10px; border: 1px solid var(--line);
  border-radius: var(--r-m); background: var(--surface);
}
.me-avatar {
  width: 28px; height: 28px; border-radius: 9px; flex: none;
  display: grid; place-items: center; font-size: 13px; font-weight: 600;
  background: var(--primary-soft); color: var(--primary-ink);
}
.me-main { flex: 1; min-width: 0; }
.me-name {
  font-size: 12.5px; font-weight: 600;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.me-role { font-size: 10.5px; color: var(--ink-3); }
.me .icon-btn { width: 28px; height: 28px; }

.status {
  display: flex; align-items: center; gap: 8px; padding: 9px 11px;
  border: 1px solid var(--line); border-radius: 10px;
  background: var(--surface); font-size: 12px; color: var(--ink-2);
}
.dot {
  width: 7px; height: 7px; border-radius: 50%; flex: none;
  background: #37A06E; box-shadow: 0 0 0 3px rgba(55, 160, 110, .16);
}
.hotline { padding: 12px; border-radius: var(--r-m); background: #1C2B29; }
.hotline-name { font-size: 12px; font-weight: 600; color: #fff; }
.hotline-note { font-size: 11px; color: #93A8A3; margin-top: 1px; }
.hotline-btn {
  display: block; margin-top: 9px; padding: 7px; border-radius: 8px;
  background: rgba(255, 255, 255, .11); border: 1px solid rgba(255, 255, 255, .14);
  color: #fff; font-size: 12px; text-align: center; text-decoration: none;
}
.hotline-btn:hover { background: rgba(255, 255, 255, .18); }

@media (max-width: 900px) {
  .rail {
    height: auto; flex-direction: row; align-items: center; gap: 12px;
    border-right: 0; border-bottom: 1px solid var(--line);
    overflow-x: auto; padding: 12px 14px;
  }
  .brand-sub, .nav-label, .rail-foot { display: none; }
  .nav { flex-direction: row; gap: 6px; margin-left: auto; }
  .nav-item { white-space: nowrap; padding: 8px 12px; }
}
</style>
