<template>
  <div class="entry">
    <div class="entry-card">
      <header class="brand">
        <div class="brand-mark"><Icon name="mark" size="l" /></div>
        <h1 class="brand-name">心理 Agent</h1>
        <p class="brand-sub">一个会记得你的陪伴者</p>
      </header>

      <div class="field">
        <div class="field-label">我是</div>
        <div class="roles" role="group" aria-label="选择身份">
          <button v-for="r in ROLES" :key="r.key" type="button"
                  class="role" :class="{ on: role === r.key }"
                  :aria-pressed="role === r.key ? 'true' : 'false'"
                  @click="selectRole(r.key)">
            <Icon :name="r.icon" />
            <span class="role-label">{{ r.label }}</span>
            <span class="role-hint">{{ r.hint }}</span>
          </button>
        </div>
      </div>

      <div class="field">
        <label class="field-label" for="entry-name">怎么称呼你</label>
        <input id="entry-name" ref="nameEl" v-model="name" class="name-input" type="text"
               :placeholder="currentRole.placeholder" maxlength="12" autocomplete="off"
               @keydown.enter="enter" />
      </div>

      <button class="btn btn-p enter-btn" type="button" :disabled="!canEnter" @click="enter">
        进入
      </button>

      <button class="demo" type="button" @click="demo">先用演示账号看看</button>

      <p class="foot"><Icon name="shield" size="s" />称呼会随对话一起发送给助手，用于记住你；仅保存在你的个人档案里</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import Icon from './ui/Icon.vue'
import { ROLES, roleOf, signIn } from '../store'

const role = ref('elder')
const name = ref('')
const nameEl = ref(null)

const currentRole = computed(() => roleOf(role.value))
const canEnter = computed(() => name.value.trim().length > 0)

function selectRole(key) {
  role.value = key
  if (nameEl.value) nameEl.value.focus()
}

function enter() {
  if (!canEnter.value) return
  signIn({ name: name.value, role: role.value })
}

function demo() {
  signIn({ name: '演示账号', role: 'elder' })
}

onMounted(() => {
  if (nameEl.value) nameEl.value.focus()
})
</script>

<style scoped>
.entry {
  min-height: 100vh; display: grid; place-items: center; padding: 24px 16px;
  background:
    radial-gradient(120% 80% at 50% -10%, rgba(46, 125, 111, .10), transparent 60%),
    var(--bg);
}

.entry-card {
  width: 100%; max-width: 440px; background: var(--surface);
  border: 1px solid var(--line); border-radius: 20px;
  padding: 36px 32px 24px; box-shadow: var(--sh-2);
}

.brand { text-align: center; margin-bottom: 28px; }
.brand-mark {
  width: 46px; height: 46px; border-radius: 14px; margin: 0 auto 14px;
  display: grid; place-items: center; color: #fff;
  background: linear-gradient(150deg, #3A8E7E, #225F54);
  box-shadow: 0 6px 16px rgba(36, 104, 92, .26);
}
.brand-name { font-size: 21px; font-weight: 650; letter-spacing: -.01em; }
.brand-sub { font-size: 13px; color: var(--ink-3); margin-top: 4px; }

.field + .field { margin-top: 22px; }
.field-label { font-size: 12.5px; color: var(--ink-2); margin-bottom: 9px; }

.roles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.role {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 14px 6px 12px; border: 1px solid var(--line); border-radius: var(--r-m);
  background: var(--surface); color: var(--ink-2);
  transition: border-color .15s ease, background .15s ease, color .15s ease;
}
.role:hover { border-color: var(--line-2); background: var(--surface-2); }
.role .ic { color: var(--ink-3); transition: color .15s ease; }
.role-label { font-size: 14px; font-weight: 600; color: var(--ink); }
.role-hint { font-size: 10.5px; color: var(--ink-3); line-height: 1.4; text-align: center; }
.role.on {
  border-color: var(--primary); background: var(--primary-soft);
  box-shadow: 0 0 0 3px rgba(46, 125, 111, .10);
}
.role.on .ic { color: var(--primary-ink); }
.role.on .role-label { color: var(--primary-ink); }
.role.on .role-hint { color: var(--primary-ink); opacity: .8; }

.name-input {
  width: 100%; padding: 12px 14px; font-size: 15px;
  border: 1px solid var(--line-2); border-radius: var(--r-m);
  background: var(--surface); outline: 0;
  transition: border-color .15s ease, box-shadow .15s ease;
}
.name-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(46, 125, 111, .13); }
.name-input::placeholder { color: var(--ink-3); }

.enter-btn { width: 100%; margin-top: 24px; padding: 12px; font-size: 15px; }

.demo {
  display: block; width: 100%; margin-top: 10px; padding: 8px;
  font-size: 12.5px; color: var(--ink-3);
  transition: color .15s ease;
}
.demo:hover { color: var(--primary-ink); }

.foot {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--line);
  font-size: 11.5px; color: var(--ink-3);
}
.foot .ic { color: var(--ink-3); }

@media (max-width: 420px) {
  .entry-card { padding: 28px 20px 18px; }
  .role { padding: 12px 4px 10px; }
  .role-hint { display: none; }
}
</style>
