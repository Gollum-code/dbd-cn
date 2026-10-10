<template>
  <div>
    <h1>附加品</h1>
    <p class="sub">共 {{ addons.length }} 个 · 中文效果与稀有度</p>

    <div class="filters">
      <input v-model="kw" type="search" placeholder="搜索名称 / 效果关键词..." class="filter" />
      <select v-model="rarityFilter" class="filter">
        <option value="">全部稀有度</option>
        <option v-for="r in rarities" :key="r" :value="r">{{ rarityZh(r) }}</option>
      </select>
      <select v-model="ownerFilter" class="filter">
        <option value="">全部归属</option>
        <option value="none">道具类（无归属）</option>
        <option v-for="c in owners" :key="c.id" :value="c.id">{{ c.name_zh || c.name_en }}</option>
      </select>
    </div>

    <div class="grid">
      <div
        v-for="a in paged"
        :key="a.id"
        class="addon-card"
        :class="{ flash: a.id === focusId }"
      >
        <div class="head">
          <img v-if="ic(a)" class="ic" :src="ic(a)" :alt="a.name_en" loading="lazy" />
          <div class="head-txt">
            <strong>{{ a.name_zh || a.name_en }}</strong>
            <em>{{ a.name_en }}</em>
          </div>
          <span class="rarity r{{ (a.rarity_en || '').toLowerCase().replace(' ', '') }}">{{ a.rarity || a.rarity_en }}</span>
        </div>
        <p v-if="a.effect" class="effect">{{ a.effect }}</p>
        <div class="foot">
          <span v-if="ownerName(a.owner)" class="owner">{{ ownerName(a.owner) }}</span>
        </div>
      </div>
    </div>

    <nav v-if="pages > 1" class="pager">
      <button :disabled="page <= 1" @click="page--">← 上一页</button>
      <span>{{ page }} / {{ pages }}</span>
      <button :disabled="page >= pages" @click="page++">下一页 →</button>
    </nav>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive, watch, nextTick } from "vue";
import { useRoute } from "vue-router";
import api from "../api.js";

const PER_PAGE = 60;

const addons = ref([]);
const chars = ref([]);
const kw = ref("");
const rarityFilter = ref("");
const ownerFilter = ref("");
const page = ref(1);
const icons = reactive({});
const focusId = ref("");

const route = useRoute();

onMounted(async () => {
  addons.value = await api.invoke("get_addons");
  chars.value = await api.invoke("get_characters");
  for (const a of addons.value) {
    if (a.icon) icons[a.id] = await api.iconUrl(a.icon);
  }
  await applyFocus();
});

watch(() => route.query.focus, applyFocus);
watch([kw, rarityFilter, ownerFilter], () => (page.value = 1));

async function applyFocus() {
  const f = route.query.focus;
  if (!f) return;
  // jump to the page containing the focused add-on
  const idx = filtered.value.findIndex((a) => a.id === f);
  if (idx >= 0) page.value = Math.floor(idx / PER_PAGE) + 1;
  focusId.value = f;
  await nextTick();
  setTimeout(() => (focusId.value = ""), 1600);
}

const owners = computed(() => chars.value.filter((c) => c.role === "killer"));
const rarities = computed(() => {
  const s = new Set();
  for (const a of addons.value) if (a.rarity_en) s.add(a.rarity_en);
  const order = ["Common", "Uncommon", "Rare", "Very Rare", "Ultra Rare", "Event"];
  return Array.from(s).sort((a, b) => order.indexOf(a) - order.indexOf(b));
});

const filtered = computed(() => {
  const q = kw.value.trim().toLowerCase();
  let list = addons.value;
  if (q) {
    list = list.filter(
      (a) =>
        (a.name_zh || "").toLowerCase().includes(q) ||
        (a.name_en || "").toLowerCase().includes(q) ||
        (a.effect || "").toLowerCase().includes(q)
    );
  }
  if (rarityFilter.value) list = list.filter((a) => a.rarity_en === rarityFilter.value);
  if (ownerFilter.value === "none") {
    list = list.filter((a) => !a.owner);
  } else if (ownerFilter.value) {
    list = list.filter((a) => a.owner === ownerFilter.value);
  }
  return list;
});

const pages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PER_PAGE)));
const paged = computed(() => {
  const start = (page.value - 1) * PER_PAGE;
  return filtered.value.slice(start, start + PER_PAGE);
});

function ic(a) {
  return icons[a.id] || "";
}
function rarityZh(r) {
  const m = {
    Common: "常见", Uncommon: "罕见", Rare: "稀有",
    "Very Rare": "精贵", "Ultra Rare": "传说", Event: "活动",
  };
  return m[r] || r;
}
function ownerName(id) {
  if (!id) return "";
  const c = chars.value.find((c) => c.id === id);
  return c ? c.name_zh || c.name_en : "";
}
</script>

<style scoped>
.filters { display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 1rem; }
.filter {
  padding: 0.5rem 0.7rem; border-radius: 8px; border: 1px solid var(--border);
  background: #101116; color: var(--text);
}
.filters input.filter { width: 250px; }
.filters select.filter { min-width: 140px; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 0.7rem; }
.addon-card {
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.7rem;
}
.addon-card.flash {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(199, 54, 47, 0.35);
}
.head { display: flex; align-items: center; gap: 0.5rem; }
.head-txt { min-width: 0; flex: 1; }
.head-txt strong { display: block; }
.head-txt em { color: var(--muted); font-style: normal; font-size: 0.75rem; }
.ic { width: 40px; height: 40px; border-radius: 7px; flex-shrink: 0; }
.rarity { border-radius: 999px; padding: 0.05rem 0.5rem; font-size: 0.72rem; flex-shrink: 0; }
.rarity.rcommon { background: #2b2f3a; color: #c9cedb; }
.rarity.runcommon { background: #1f3d2f; color: #7ecba1; }
.rarity.rrare { background: #1f3345; color: #6cb6e8; }
.rarity.rveryrare { background: #3a2540; color: #c99be8; }
.rarity.rultrarare { background: #44301d; color: #e8b26c; }
.rarity.revent { background: #2d2340; color: #b79ce8; }
.effect {
  color: var(--muted); font-size: 0.8rem; line-height: 1.5; margin: 0.45rem 0 0;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.foot { margin-top: 0.35rem; }
.owner { color: var(--accent2); font-size: 0.76rem; }
.pager {
  display: flex; align-items: center; justify-content: center; gap: 0.8rem; margin-top: 1.2rem;
}
.pager button {
  padding: 0.4rem 0.9rem; border-radius: 8px; border: 1px solid var(--border);
  background: #101116; color: var(--text); cursor: pointer;
}
.pager button:disabled { opacity: 0.4; cursor: default; }
</style>