<template>
  <div>
    <div class="head">
      <h1>版本更新</h1>
      <button class="refresh" @click="refresh">检查更新</button>
    </div>
    <div v-if="info" class="sync-bar">
      <span>最新版本：<strong>{{ info.latest_patch || '—' }}</strong></span>
      <span>数据源：{{ info.source || '—' }}</span>
      <span>最近同步：{{ info.last_sync || '—' }}</span>
    </div>

    <div class="patch-list">
      <div v-for="p in patches" :key="p.id" class="patch">
        <div class="patch-head">
          <span class="patch-no">{{ p.patch }}</span>
          <span v-if="p.ptb" class="ptb">PTB</span>
          <span class="date">{{ p.rdate }}</span>
        </div>
        <p v-if="p.notes" class="notes">{{ p.notes }}</p>
      </div>
      <p v-if="!patches.length" class="hint">暂无补丁数据。</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api.js";

const patches = ref([]);
const info = ref(null);

async function refresh() {
  patches.value = await api.invoke("get_patches");
  info.value = await api.invoke("get_sync_info");
}

onMounted(refresh);
</script>

<style scoped>
.head { display: flex; align-items: center; gap: 1rem; }
.refresh {
  padding: 0.4rem 0.9rem; border-radius: 8px; border: 1px solid var(--border);
  background: #101116; color: var(--text); cursor: pointer;
}
.refresh:hover { border-color: var(--accent); }
.sync-bar {
  display: flex; gap: 1.2rem; flex-wrap: wrap;
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.7rem 0.9rem; margin: 1rem 0;
  color: var(--muted); font-size: 0.88rem;
}
.sync-bar strong { color: var(--text); }
.patch-list { display: grid; gap: 0.55rem; max-width: 560px; }
.patch {
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.7rem 0.9rem;
}
.patch-head { display: flex; align-items: center; gap: 0.6rem; }
.patch-no { font-weight: 800; color: #6cb6e8; }
.ptb { background: #3a2d1d; color: #e8b26c; border-radius: 999px; padding: 0.05rem 0.5rem; font-size: 0.7rem; font-weight: 700; }
.date { margin-left: auto; color: var(--muted); font-size: 0.8rem; }
.notes { color: var(--muted); font-size: 0.85rem; margin: 0.3rem 0 0; }
.hint { color: var(--muted); }
</style>