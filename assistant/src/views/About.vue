<template>
  <div>
    <h1>关于</h1>
    <div class="panel">
      <div class="brand">DBD 助手<span>中文</span></div>
      <p class="desc">
        黎明杀机（Dead by Daylight）中文资料助手 · 非官方粉丝项目。
        数据每周自动同步自 <a href="https://deadbydaylight.wiki.gg" target="_blank" rel="noopener">deadbydaylight.wiki.gg</a>。
      </p>
      <dl>
        <dt>数据源</dt><dd>{{ info.source || '—' }}</dd>
        <dt>最近同步</dt><dd>{{ info.last_sync || '—' }}</dd>
        <dt>最新补丁</dt><dd>{{ info.latest_patch || '—' }}</dd>
      </dl>
      <p class="legal">
        本项目为非商业粉丝项目，与 Behaviour Interactive 无任何关联。
        游戏角色、名称与图标等素材版权归其发行商与开发者所有，本应用仅作中文整理与工具化呈现。
      </p>
    </div>

    <div class="panel">
      <h2>内容统计</h2>
      <div class="stats">
        <div class="stat"><span>{{ chars.length }}</span>角色</div>
        <div class="stat"><span>{{ perks.length }}</span>技能</div>
        <div class="stat"><span>{{ addons.length }}</span>附加品</div>
        <div class="stat"><span>{{ maps.length }}</span>地图</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import api from "../api.js";

const info = ref({});
const chars = ref([]);
const perks = ref([]);
const addons = ref([]);
const maps = ref([]);

onMounted(async () => {
  info.value = (await api.invoke("get_sync_info")) || {};
  chars.value = await api.invoke("get_characters");
  perks.value = await api.invoke("get_perks");
  addons.value = await api.invoke("get_addons");
  maps.value = await api.invoke("get_maps");
});
</script>

<style scoped>
.panel {
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 10px; padding: 1rem; margin-bottom: 1rem; max-width: 640px;
}
.brand { font-weight: 800; font-size: 1.15rem; margin-bottom: 0.5rem; }
.brand span { color: var(--accent); }
.desc { color: var(--muted); font-size: 0.9rem; }
.desc a { color: var(--accent2); }
dl { display: grid; grid-template-columns: 80px 1fr; gap: 0.25rem 0.6rem; margin: 0.8rem 0; }
dt { color: var(--muted); }
dd { margin: 0; font-size: 0.88rem; }
.legal { color: #7a8192; font-size: 0.78rem; line-height: 1.6; margin-top: 0.8rem; }
.stats { display: flex; gap: 1.6rem; flex-wrap: wrap; }
.stat { color: var(--muted); font-size: 0.88rem; }
.stat span { display: block; color: var(--text); font-size: 1.5rem; font-weight: 700; }
</style>