<template>
  <section class="view records-view">
    <div class="pane">
      <header class="topbar">
        <div>
          <h2 class="topbar-title">风险记录</h2>
          <div class="topbar-meta">对话中触发的预警留痕 · 后端同时写入 data/risk_records.xlsx</div>
        </div>
        <div class="grow"></div>
        <span v-if="myRecords.length" class="chip">{{ currentUser.name }} · {{ myRecords.length }} 条</span>
      </header>

      <div class="records-body">
        <div v-if="!myRecords.length" class="empty">
          <div class="empty-icon"><Icon name="shield" size="l" /></div>
          <div class="empty-title">暂无预警记录</div>
          <p class="muted">
            当对话中评估出 2 级及以上风险时，会自动在这里留痕，<br>
            并同步触发邮件预警与 Excel 记录。
          </p>
        </div>

        <ul v-else class="list">
          <li v-for="r in myRecords" :key="r.id" class="record card">
            <div class="record-head">
              <span class="pill" :class="`pill-${riskMeta(r.level).tone}`">
                <Icon name="warn" size="s" />等级 {{ r.level }} / 3 · {{ riskMeta(r.level).label }}
              </span>
              <span class="record-time">{{ r.time }} · {{ r.source }}</span>
            </div>
            <p v-if="r.reason" class="record-reason">{{ r.reason }}</p>
            <p v-if="r.message" class="record-msg">「{{ r.message }}」</p>
          </li>
        </ul>
      </div>
    </div>

    <aside class="side">
      <div class="side-head"><h3>说明</h3></div>
      <div class="card prose">
        这里只显示<b>当前使用者</b>的预警留痕，切换身份后互不可见。刷新页面即清空。<br>
        完整的持久化记录在服务端 <b>data/risk_records.xlsx</b>，由
        <b>write_risk_record_excel</b> 工具写入。
      </div>
    </aside>
  </section>
</template>

<script setup>
import Icon from './ui/Icon.vue'
import { currentUser, myRecords, riskMeta } from '../store'
</script>

<style scoped>
.records-view { grid-template-columns: minmax(0, 1fr) 296px; }
.records-body { padding: 20px; }

.empty { text-align: center; padding: 56px 20px; }
.empty-icon {
  width: 52px; height: 52px; border-radius: 14px; margin: 0 auto 14px;
  display: grid; place-items: center;
  background: var(--primary-soft); color: var(--primary-ink);
}
.empty-title { font-size: 14px; font-weight: 600; margin-bottom: 6px; }

.list { display: flex; flex-direction: column; gap: 12px; }
.record { padding: 14px 16px; }
.record-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.record-time { font-size: 11.5px; color: var(--ink-3); margin-left: auto; font-variant-numeric: tabular-nums; }
.record-reason { font-size: 12.5px; color: var(--ink-2); line-height: 1.75; margin-top: 8px; }
.record-msg { font-size: 13px; color: var(--ink); line-height: 1.75; margin-top: 6px; }

.prose { padding: 12px; font-size: 12.5px; line-height: 1.8; color: var(--ink-2); }
.prose b { color: var(--ink); font-weight: 600; }
</style>
