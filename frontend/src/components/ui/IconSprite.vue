<template>
  <!-- 全站图标符号表：只渲染一次，其它地方用 <Icon name="..."/> 引用 -->
  <svg class="sprite" aria-hidden="true" focusable="false">
    <symbol id="ic-mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 12.4h3.4l2-5.2 3.1 10 2.3-6.2 1.6 3.4H21" />
    </symbol>
    <symbol id="ic-chat" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3.2" y="4.2" width="17.6" height="13.6" rx="3.2" />
      <path d="M8.6 20.4l3.1-2.6" />
    </symbol>
    <symbol id="ic-video" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <rect x="2.8" y="6.4" width="12.4" height="11.2" rx="2.6" />
      <path d="M15.2 10.6l5.6-3.2v9.2l-5.6-3.2z" />
    </symbol>
    <symbol id="ic-breath" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round">
      <circle cx="12" cy="12" r="8.2" />
      <circle cx="12" cy="12" r="3.1" />
    </symbol>
    <symbol id="ic-shield" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 3.2l7.2 2.8v6.1c0 4.5-3 7.7-7.2 9.1-4.2-1.4-7.2-4.6-7.2-9.1V6z" />
      <path d="M9.2 12.1l2 2 3.6-3.9" />
    </symbol>
    <symbol id="ic-set" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round">
      <path d="M4 8h16M4 16h16" />
      <circle cx="15.2" cy="8" r="2.4" fill="var(--surface)" />
      <circle cx="8.8" cy="16" r="2.4" fill="var(--surface)" />
    </symbol>
    <symbol id="ic-spark" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 3.4l1.9 5.3 5.3 1.9-5.3 1.9-1.9 5.3-1.9-5.3L4.8 10.6l5.3-1.9z" />
      <path d="M18.6 15.4l.9 2.2 2.2.9-2.2.9-.9 2.2-.9-2.2-2.2-.9 2.2-.9z" opacity=".55" />
    </symbol>
    <symbol id="ic-doc" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <path d="M6.4 3.4h7l4.8 4.8v12.4H6.4z" />
      <path d="M13.4 3.4v4.8h4.8" />
    </symbol>
    <symbol id="ic-mic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.6 11.6a6.4 6.4 0 0 0 12.8 0M12 18v3" />
    </symbol>
    <symbol id="ic-img" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3.2" y="4.4" width="17.6" height="15.2" rx="3" />
      <circle cx="8.6" cy="9.6" r="1.7" />
      <path d="M4.4 17.4l4.9-4.3 3.9 3.4 2.9-2.4 4.3 3.7" />
    </symbol>
    <symbol id="ic-send" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M4.4 12.2l15.2-7.4-6.6 15-2.3-6.2z" />
    </symbol>
    <symbol id="ic-copy" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <rect x="9.2" y="9.2" width="11" height="11" rx="2.6" />
      <path d="M15.2 6.6A2.8 2.8 0 0 0 12.4 4H6.8A2.8 2.8 0 0 0 4 6.8v5.6a2.8 2.8 0 0 0 2.6 2.8" />
    </symbol>
    <symbol id="ic-redo" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <path d="M20.2 12a8.2 8.2 0 1 1-2.5-5.9" />
      <path d="M20.4 3.8v5.3h-5.3" />
    </symbol>
    <symbol id="ic-up" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <path d="M7 20.2v-9.6l4.1-7.2 1.5 1a3.1 3.1 0 0 1 1 3.3l-.6 1.9h5a2.1 2.1 0 0 1 2 2.4l-1 6.1a2.1 2.1 0 0 1-2 1.7z" />
      <path d="M7 10.6H4v9.6h3" />
    </symbol>
    <symbol id="ic-alert" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 3.8l8.8 15.2H3.2z" />
      <path d="M12 9.4v4.5M12 16.9h.01" />
    </symbol>
    <symbol id="ic-warn" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="8.4" />
      <path d="M12 7.8v4.8M12 15.9h.01" />
    </symbol>
    <symbol id="ic-phone" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M6.4 3.6h3l1.5 4-2 1.4a10.6 10.6 0 0 0 5.9 5.9l1.4-2 4 1.5v3a1.9 1.9 0 0 1-2.1 1.9A16.2 16.2 0 0 1 4.5 5.7a1.9 1.9 0 0 1 1.9-2.1z" />
    </symbol>
    <symbol id="ic-pause" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round">
      <path d="M9.4 5.2v13.6M14.6 5.2v13.6" />
    </symbol>
    <symbol id="ic-play" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round">
      <path d="M8.4 5.6l10 6.4-10 6.4z" />
    </symbol>
    <symbol id="ic-stop" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round">
      <rect x="6.6" y="6.6" width="10.8" height="10.8" rx="2.4" />
    </symbol>
    <symbol id="ic-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M9.6 6.4l5.6 5.6-5.6 5.6" />
    </symbol>
    <symbol id="ic-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </symbol>
    <symbol id="ic-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
      <path d="M6.4 6.4l11.2 11.2M17.6 6.4L6.4 17.6" />
    </symbol>
    <symbol id="ic-user" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="8.2" r="3.6" />
      <path d="M4.8 20.2a7.2 7.2 0 0 1 14.4 0" />
    </symbol>
    <symbol id="ic-heart" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 20.2s-7.4-4.6-7.4-9.8A4.3 4.3 0 0 1 12 7.4a4.3 4.3 0 0 1 7.4 3c0 5.2-7.4 9.8-7.4 9.8z" />
    </symbol>
    <symbol id="ic-logout" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M9.4 5H6.6A1.6 1.6 0 0 0 5 6.6v10.8A1.6 1.6 0 0 0 6.6 19h2.8" />
      <path d="M15.2 8.6L18.6 12l-3.4 3.4M18.6 12H10" />
    </symbol>
    <symbol id="ic-volume" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M4.6 9.6h3l4.4-3.4v11.6l-4.4-3.4h-3z" />
      <path d="M16 9.4a3.6 3.6 0 0 1 0 5.2M18.6 6.8a7.2 7.2 0 0 1 0 10.4" />
    </symbol>
    <symbol id="ic-bell" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M6.4 10a5.6 5.6 0 0 1 11.2 0c0 4.6 1.8 5.8 2.6 6.4H3.8c.8-.6 2.6-1.8 2.6-6.4z" />
      <path d="M10 19.6a2.2 2.2 0 0 0 4 0" />
    </symbol>
  </svg>
</template>

<style scoped>
.sprite { position: absolute; width: 0; height: 0; overflow: hidden; }
</style>
