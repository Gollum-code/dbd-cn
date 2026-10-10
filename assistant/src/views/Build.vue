<template>
  <div>
    <h1>构筑推荐</h1>
    <p class="sub">选择角色与玩法流派，自动推荐技能组合</p>

    <div class="controls">
      <label>
        角色
        <select v-model="charId">
          <option v-for="c in chars" :key="c.id" :value="c.id">
            {{ c.name_zh || c.name_en }}（{{ c.role === 'killer' ? '杀手' : '逃生者' }}）
          </option>
        </select>
      </label>
      <label>
        玩法
        <select v-model="playstyle">
          <option v-for="p in playstyles" :key="p" :value="p">{{ p }}</option>
        </select>
      </label>
      <button :disabled="loading" @click="recommend">生成推荐</button>
    </div>

    <div v-if="loading" class="hint">计算中...</div>

    <div class="build-out">
      <h2>{{ current?.name_zh || current?.name_en || '推荐技能' }}</h2>
      <div v-if="recs.length" class="rec-list">
        <div v-for="(r, i) in recs" :key="i" class="rec">
          <span class="rank">{{ i + 1 }}</span>
          <div>
            <div class="rec-name">{{ r.name_zh || r.name_en }} <em>{{ r.name_en }}</em></div>
            <div class="rec-reason">{{ r.reason }}</div>
          </div>
          <span class="score">{{ r.score.toFixed(1) }}</span>
        </div>
        <button class="save" @click="save">保存此构筑</button>
      </div>
      <div v-else class="hint">暂无匹配（该角色技能可能尚未收录）。</div>
    </div>

    <div v-if="savedMsg" class="toast">{{ savedMsg }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from "vue";
import api from "../api.js";

const chars = ref([]);
const playstyles = ref([]);
const charId = ref("");
const playstyle = ref("控场压制");
const recs = ref([]);
const loading = ref(false);
const savedMsg = ref("");

const current = computed(() => chars.value.find((c) => c.id === charId.value));

onMounted(async () => {
  chars.value = await api.invoke("get_characters");
  playstyles.value = await api.invoke("get_playstyles");
  if (chars.value.length) charId.value = chars.value[0].id;
});

async function recommend() {
  loading.value = true;
  recs.value = [];
  try {
    recs.value = await api.invoke("recommend_build", {
      character_id: charId.value,
      playstyle: playstyle.value || "控场压制",
    });
  } finally {
    loading.value = false;
  }
}

async function save() {
  await api.invoke("save_build", {
    character: charId.value,
    role: current.value?.role || "",
    perks_json: JSON.stringify(recs.value.map((r) => r.perk_id)),
    addons_json: "[]",
    playstyle: playstyle.value,
    rating: 0,
  });
  savedMsg.value = "构筑已保存";
  setTimeout(() => (savedMsg.value = ""), 2000);
}
</script>

<style scoped>
.controls { display: flex; gap: 1rem; align-items: flex-end; flex-wrap: wrap; }
label { display: flex; flex-direction: column; gap: 0.3rem; color: var(--muted); font-size: 0.85rem; }
select, button {
  padding: 0.45rem 0.7rem; border-radius: 8px; border: 1px solid var(--border);
  background: #101116; color: var(--text);
}
button { background: var(--accent); border-color: var(--accent); cursor: pointer; }
button:disabled { opacity: 0.5; cursor: default; }
.build-out { margin-top: 1.4rem; }
.rec-list { display: grid; gap: 0.6rem; max-width: 560px; }
.rec {
  display: flex; align-items: center; gap: 0.8rem;
  background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 0.7rem 0.9rem;
}
.rank {
  width: 26px; height: 26px; border-radius: 50%; background: var(--accent);
  display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0;
}
.rec-name { font-weight: 600; }
.rec-name em { color: var(--muted); font-style: normal; font-size: 0.8rem; }
.rec-reason { color: var(--muted); font-size: 0.82rem; }
.score { margin-left: auto; color: var(--good); font-weight: 700; }
.hint { color: var(--muted); margin-top: 1rem; }
.save { margin-top: 0.8rem; }
.toast {
  position: fixed; bottom: 20px; right: 20px; background: var(--good); color: #06140c;
  padding: 0.6rem 1rem; border-radius: 8px; font-weight: 600;
}
</style>