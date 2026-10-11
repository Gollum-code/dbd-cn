<template>
  <div>
    <h1>角色图鉴</h1>
    <div class="tabs">
      <button :class="{ active: tab === 'killer' }" @click="tab = 'killer'">杀手</button>
      <button :class="{ active: tab === 'survivor' }" @click="tab = 'survivor'">逃生者</button>
    </div>
    <div class="grid">
      <div
        v-for="c in shown"
        :key="c.id"
        class="char-card"
        :ref="(el) => setCardRef(c.id, el)"
        :class="{ flash: c.id === focusId }"
      >
        <div class="char-portrait" v-if="icons[c.id]">
          <img :src="icons[c.id]" :alt="c.name_en" loading="lazy" />
        </div>
        <div class="char-head">
          <strong>{{ c.name_zh || c.name_en }}</strong>
          <em>{{ c.name_en }}</em>
        </div>
        <div class="char-meta">
          <div v-if="c.difficulty"><span class="k">难度</span> {{ c.difficulty }}</div>
          <div v-if="c.speed_forms && c.speed_forms.length">
            <span class="k">移速</span>
            <span v-for="(f, i) in c.speed_forms" :key="i" class="form">
              {{ f.value }}<em v-if="f.label">{{ f.label }}</em>
            </span>
          </div>
          <div v-if="c.terror_forms && c.terror_forms.length">
            <span class="k">恐惧范围</span>
            <span v-for="(f, i) in c.terror_forms" :key="i" class="form">
              {{ f.value }} 米<em v-if="f.label">{{ f.label }}</em>
            </span>
          </div>
          <div v-if="c.power"><span class="k">能力</span> {{ c.power }}</div>
          <div v-if="c.gender"><span class="k">性别</span> {{ c.gender }}</div>
          <div v-if="c.origin"><span class="k">出身</span> {{ c.origin }}</div>
        </div>
        <p v-if="c.lore" class="lore">{{ c.lore }}</p>
        <div v-if="ownedPerks(c.id).length" class="mini-perks">
          <span v-for="p in ownedPerks(c.id).slice(0, 3)" :key="p.id" class="tag">{{ p.name_zh || p.name_en }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive, watch, nextTick } from "vue";
import { useRoute } from "vue-router";
import api from "../api.js";

const chars = ref([]);
const perks = ref([]);
const tab = ref("killer");
const icons = reactive({});
const focusId = ref("");
const cardEls = reactive({});

const route = useRoute();

onMounted(async () => {
  chars.value = await api.invoke("get_characters");
  perks.value = await api.invoke("get_perks");
  for (const c of chars.value) {
    if (c.icon) icons[c.id] = await api.iconUrl(c.icon);
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
  const c = chars.value.find((x) => x.id === f);
  if (c) tab.value = c.role; // switch to the right tab so the card is visible
  focusId.value = f;
  await nextTick();
  const el = cardEls[f];
  if (el && el.scrollIntoView) el.scrollIntoView({ behavior: "smooth", block: "center" });
  setTimeout(() => (focusId.value = ""), 1600);
}

const shown = computed(() => chars.value.filter((c) => c.role === tab.value));

function ownedPerks(charId) {
  const c = chars.value.find((x) => x.id === charId);
  const universal = c ? (c.role === "killer" ? "K00" : "S00") : "";
  return perks.value.filter((p) => p.owner === charId || p.owner === universal);
}
</script>

<style scoped>
.tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.tabs button {
  padding: 0.45rem 1.1rem; border-radius: 999px; border: 1px solid var(--border);
  background: #101116; color: var(--muted); cursor: pointer;
}
.tabs button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.8rem; }
.char-card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 0.8rem;
}
.char-card.flash {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(199, 54, 47, 0.35);
  transition: box-shadow 0.2s;
}
.char-portrait {
  aspect-ratio: 3/4; border-radius: 8px; overflow: hidden;
  background: linear-gradient(145deg, #1d202b, #12141c); margin-bottom: 0.5rem;
}
.char-portrait img { width: 100%; height: 100%; object-fit: cover; display: block; }
.char-head { display: flex; justify-content: space-between; gap: 0.4rem; }
.char-head em { color: var(--muted); font-style: normal; font-size: 0.75rem; }
.char-meta { margin: 0.4rem 0; font-size: 0.85rem; color: var(--text); }
.char-meta .k { color: var(--muted); }
.char-meta .form {
  display: inline-block; margin-right: 0.35rem;
  background: #232735; border-radius: 5px; padding: 0.02rem 0.4rem; font-size: 0.8rem;
}
.char-meta .form em { color: var(--muted); font-style: normal; margin-left: 0.25rem; font-size: 0.72rem; }
.lore {
  color: var(--muted); font-size: 0.8rem; line-height: 1.5;
  margin: 0.3rem 0; display: -webkit-box; -webkit-line-clamp: 4;
  -webkit-box-orient: vertical; overflow: hidden;
}
.mini-perks { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.tag { background: #232735; border-radius: 999px; padding: 0.05rem 0.5rem; font-size: 0.72rem; color: var(--muted); }
</style>