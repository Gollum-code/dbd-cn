<template>
  <div>
    <h1>我的构筑</h1>
    <p class="sub">在「构筑推荐」页保存的构筑会显示在这里，可删除。</p>
    <div class="tabs">
      <button :class="{ active: !onlyUser }" @click="onlyUser = false">全部</button>
      <button :class="{ active: onlyUser }" @click="onlyUser = true">仅我保存的</button>
    </div>
    <div v-if="!builds.length" class="hint">暂无构筑，去「构筑推荐」生成并保存吧。</div>
    <div class="list">
      <div v-for="b in builds" :key="b.id" class="build">
        <div class="head">
          <span class="role-badge" :class="b.role">{{ b.role === 'killer' ? '杀手' : '逃生者' }}</span>
          <strong>{{ charName(b.character) }}</strong>
          <span class="src">{{ b.source === 'default' ? '内置' : '我的' }}</span>
          <span v-if="b.rating" class="rating">★ {{ b.rating }}</span>
          <button v-if="b.source !== 'default'" class="del" @click="remove(b.id)">删除</button>
        </div>
        <div class="perks">
          <span v-for="(pid, i) in perkIds(b.perks)" :key="i" class="perk-chip">{{ perkName(pid) }}</span>
        </div>
        <p v-if="b.playstyle" class="play">{{ b.playstyle }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import api from "../api.js";

const builds = ref([]);
const chars = ref([]);
const perks = ref([]);
const onlyUser = ref(false);

async function load() {
  builds.value = await api.invoke("get_builds", { onlyUser: onlyUser.value });
}
onMounted(async () => {
  chars.value = await api.invoke("get_characters");
  perks.value = await api.invoke("get_perks");
  await load();
});
watch(onlyUser, load);

function charName(id) {
  const c = chars.value.find((c) => c.id === id);
  return c ? c.name_zh || c.name_en : id;
}
function perkIds(raw) {
  try { return JSON.parse(raw || "[]"); } catch { return []; }
}
function perkName(pid) {
  const p = perks.value.find((p) => p.id === pid);
  return p ? p.name_zh || p.name_en : pid;
}
async function remove(id) {
  await api.invoke("delete_build", { id });
  await load();
}
</script>

<style scoped>
.tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.tabs button {
  padding: 0.4rem 0.9rem; border-radius: 999px; border: 1px solid var(--border);
  background: #101116; color: var(--muted); cursor: pointer;
}
.tabs button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.hint { color: var(--muted); }
.list { display: grid; gap: 0.7rem; max-width: 620px; }
.build { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 0.7rem 0.9rem; }
.head { display: flex; align-items: center; gap: 0.6rem; }
.role-badge { border-radius: 999px; padding: 0.05rem 0.6rem; font-size: 0.75rem; }
.role-badge.killer { background: #3a1d1d; color: #e88a6c; }
.role-badge.survivor { background: #1d2c3a; color: #6cb6e8; }
.src { background: #232735; color: var(--muted); border-radius: 999px; padding: 0.05rem 0.55rem; font-size: 0.72rem; }
.rating { color: #e8b26c; margin-left: auto; }
.del { margin-left: 0.5rem; padding: 0.15rem 0.55rem; border-radius: 6px; border: 1px solid #4a2a2a; background: #2a1818; color: #e88a6c; cursor: pointer; font-size: 0.75rem; }
.perks { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem; }
.perk-chip { background: #232735; border-radius: 999px; padding: 0.1rem 0.6rem; font-size: 0.78rem; }
.play { color: var(--muted); font-size: 0.85rem; margin: 0.4rem 0 0; }
</style>