<template>
  <div>
    <h1>技能图鉴</h1>
    <p class="sub">共 {{ perks.length }} 个技能 · 中文搜索</p>
    <div class="filters">
      <input v-model="kw" type="search" placeholder="输入关键词过滤..." class="filter" />
      <select v-model="tagFilter" class="filter">
        <option value="">全部效果类型</option>
        <option v-for="t in allTags" :key="t" :value="t">{{ t }}</option>
      </select>
      <select v-model="roleFilter" class="filter">
        <option value="">全部角色</option>
        <option value="killer">杀手</option>
        <option value="survivor">逃生者</option>
      </select>
    </div>
    <div class="grid" ref="grid">
      <div
        v-for="p in filtered"
        :key="p.id"
        class="perk-card"
        :ref="(el) => setCardRef(p.id, el)"
        :class="{ flash: p.id === focusId }"
      >
        <div class="head">
          <img v-if="ic(p)" class="perk-ic" :src="ic(p)" :alt="p.name_en" loading="lazy" />
          <div class="head-txt">
            <strong>{{ p.name_zh || p.name_en }}</strong>
            <em>{{ p.name_en }}</em>
          </div>
        </div>
        <div class="meta">
          <span class="role-badge" :class="p.role">{{ p.role === 'killer' ? '杀手' : '逃生者' }}</span>
          <span class="owner" v-if="ownerOf(p)">{{ ownerOf(p) }}</span>
        </div>
        <div v-if="tiers(p)" class="tiers">
          <span v-for="(v, i) in tiers(p)" :key="i">
            <b>档 {{ i + 1 }}</b> {{ v }}
          </span>
        </div>
        <p v-if="p.description" class="desc">{{ p.description }}</p>
        <div v-if="p.tags" class="tags">
          <span v-for="t in tags(p)" :key="t" class="tag">{{ t }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, reactive, watch, nextTick } from "vue";
import { useRoute } from "vue-router";
import api from "../api.js";

const perks = ref([]);
const chars = ref([]);
const kw = ref("");
const tagFilter = ref("");
const roleFilter = ref("");
const icons = reactive({});
const focusId = ref("");
const cardEls = reactive({});

const route = useRoute();

onMounted(async () => {
  perks.value = await api.invoke("get_perks");
  chars.value = await api.invoke("get_characters");
  for (const p of perks.value) {
    if (p.icon) icons[p.id] = await api.iconUrl(p.icon);
  }
  await applyFocus();
});

watch(() => route.query.focus, async () => {
  await applyFocus();
});

function setCardRef(id, el) {
  if (el) cardEls[id] = el;
}

async function applyFocus() {
  const f = route.query.focus;
  if (!f) return;
  focusId.value = f;
  // ensure the focused card is visible (clear filters that would hide it)
  if (!filtered.value.some((p) => p.id === f)) {
    kw.value = "";
    tagFilter.value = "";
    roleFilter.value = "";
  }
  await nextTick();
  const el = cardEls[f];
  if (el && el.scrollIntoView) el.scrollIntoView({ behavior: "smooth", block: "center" });
  setTimeout(() => (focusId.value = ""), 1600);
}

function ic(p) {
  return icons[p.id] || "";
}

const allTags = computed(() => {
  const set = new Set();
  for (const p of perks.value) {
    for (const t of tags(p)) set.add(t);
  }
  return Array.from(set).sort();
});

const filtered = computed(() => {
  let list = perks.value;
  const q = kw.value.trim().toLowerCase();
  if (q) {
    list = list.filter(
      (p) =>
        (p.name_zh || "").toLowerCase().includes(q) ||
        (p.name_en || "").toLowerCase().includes(q)
    );
  }
  if (tagFilter.value) {
    list = list.filter((p) => tags(p).includes(tagFilter.value));
  }
  if (roleFilter.value) {
    list = list.filter((p) => p.role === roleFilter.value);
  }
  return list;
});

function tags(p) {
  try { return JSON.parse(p.tags || "[]"); } catch { return []; }
}
function tiers(p) {
  try {
    const t = JSON.parse(p.tiers);
    return Object.values(t);
  } catch { return []; }
}
function ownerOf(p) {
  const c = chars.value.find((c) => c.id === p.owner);
  return c ? c.name_zh || c.name_en : "";
}
</script>

<style scoped>
.filter {
  padding: 0.5rem 0.7rem; border-radius: 8px; border: 1px solid var(--border);
  background: #101116; color: var(--text); width: 260px; margin-bottom: 1rem;
}
.filters { display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 1rem; }
.filters .filter { margin-bottom: 0; }
.filters select.filter { width: auto; min-width: 130px; }
.perk-card.flash {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(199, 54, 47, 0.35);
  transition: box-shadow 0.2s;
}
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 0.8rem; }
.perk-card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 0.8rem;
}
.head { display: flex; justify-content: space-between; gap: 0.4rem; }
.perk-ic { width: 44px; height: 44px; border-radius: 8px; flex-shrink: 0; }
.head-txt { min-width: 0; }
.head em { color: var(--muted); font-style: normal; font-size: 0.75rem; }
.meta { display: flex; gap: 0.5rem; align-items: center; margin: 0.4rem 0; }
.role-badge { border-radius: 999px; padding: 0.05rem 0.55rem; font-size: 0.75rem; }
.role-badge.killer { background: #3a1d1d; color: #e88a6c; }
.role-badge.survivor { background: #1d2c3a; color: #6cb6e8; }
.owner { color: var(--muted); font-size: 0.8rem; }
.tiers { display: flex; gap: 0.4rem; margin-bottom: 0.4rem; }
.tiers span { background: #232735; border-radius: 6px; padding: 0.15rem 0.5rem; font-size: 0.8rem; }
.tiers b { color: var(--muted); font-weight: 500; }
.desc {
  color: var(--muted); font-size: 0.82rem; line-height: 1.5;
  margin: 0.3rem 0; display: -webkit-box; -webkit-line-clamp: 3;
  -webkit-box-orient: vertical; overflow: hidden;
}
.tags { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.tag { background: #101116; border: 1px solid var(--border); border-radius: 999px; padding: 0.05rem 0.5rem; font-size: 0.72rem; color: var(--muted); }
</style>