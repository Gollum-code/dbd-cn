<template>
  <div>
    <h1>地图查询</h1>
    <input v-model="kw" type="search" placeholder="搜索地图 / 领域..." class="filter" />
    <div class="realm-list">
      <div v-for="[realm, items] in grouped" :key="realm" class="realm">
        <h2>{{ realm || '未知领域' }} <small>{{ items.length }} 张地图</small></h2>
        <table>
          <thead><tr><th>地图</th><th>英文</th><th>钩点</th><th>图腾点</th><th>版本</th></tr></thead>
          <tbody>
            <tr v-for="m in items" :key="m.id">
              <td>{{ m.name_zh || m.name_en }}</td>
              <td class="en">{{ m.name_en }}</td>
              <td>{{ m.hooks ?? '—' }}</td>
              <td>{{ m.totems ?? '—' }}</td>
              <td>
                <span v-for="(v, i) in m.variations" :key="i" class="var">
                  {{ v.size }}<em>{{ v.release }}</em>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import api from "../api.js";

const maps = ref([]);
const kw = ref("");

onMounted(async () => {
  maps.value = await api.invoke("get_maps");
});

const grouped = computed(() => {
  const q = kw.value.trim().toLowerCase();
  const filtered = q
    ? maps.value.filter(
        (m) =>
          (m.name_zh || "").toLowerCase().includes(q) ||
          (m.name_en || "").toLowerCase().includes(q) ||
          (m.realm || "").toLowerCase().includes(q)
      )
    : maps.value;
  const out = {};
  for (const m of filtered) {
    const key = m.realm || "未知领域";
    (out[key] = out[key] || []).push(m);
  }
  return Object.entries(out);
});
</script>

<style scoped>
.filter {
  padding: 0.5rem 0.7rem; border-radius: 8px; border: 1px solid var(--border);
  background: #101116; color: var(--text); width: 240px; margin-bottom: 1rem;
}
.realm { margin-bottom: 1.6rem; }
.realm h2 { font-size: 1.05rem; margin: 0 0 0.5rem; }
.realm h2 small { color: var(--muted); font-weight: 400; font-size: 0.8rem; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 0.45rem 0.5rem; border-bottom: 1px solid var(--border); }
thead th { color: var(--muted); font-weight: 600; }
td.en { color: var(--muted); font-size: 0.8rem; }
.var { margin-right: 0.5rem; font-size: 0.8rem; }
.var em { color: var(--muted); font-style: normal; margin-left: 0.2rem; }
</style>