<template>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">DBD 助手<span>中文</span></div>
      <nav>
        <RouterLink to="/roster">角色图鉴</RouterLink>
        <RouterLink to="/perks">技能图鉴</RouterLink>
        <RouterLink to="/builds">构筑推荐</RouterLink>
        <RouterLink to="/my-builds">我的构筑</RouterLink>
        <RouterLink to="/maps">地图查询</RouterLink>
        <RouterLink to="/changelog">版本更新</RouterLink>
      </nav>
      <div class="search">
        <input
          v-model="q"
          type="search"
          placeholder="搜索角色 / 技能 / 附加品..."
          @input="onSearch"
          @keyup.enter="focusFirst"
        />
        <ul v-if="results.length" class="results">
          <li v-for="hit in results" :key="hit.kind + hit.id" @click="go(hit)">
            <div class="row">
              <span class="kind">{{ hit.kind }}</span> {{ hit.name_zh || hit.name_en }}
              <em>{{ hit.name_en }}</em>
            </div>
            <div v-if="hit.snippet" class="snippet">{{ hit.snippet }}</div>
          </li>
        </ul>
      </div>
    </aside>
    <main class="content">
      <RouterView @save-build="onSaveBuild" @char-selected="selected = $event" />
    </main>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import api from "./api.js";

const router = useRouter();
const q = ref("");
const results = ref([]);

async function onSearch() {
  if (!q.value.trim()) {
    results.value = [];
    return;
  }
  results.value = await api.invoke("search_all", { query: q.value.trim() });
}

function focusFirst() {
  if (results.value.length) go(results.value[0]);
}

// Jump to the matching view and pass a "focus" id that the target view picks up.
function go(hit) {
  const target =
    hit.kind === "技能" ? "/perks" :
    hit.kind === "地图" || hit.kind === "领域" ? "/maps" :
    "/roster";
  router.push({ path: target, query: { focus: hit.id } });
  results.value = [];
}

async function onSaveBuild(payload) {
  await api.invoke("save_build", payload);
}
</script>

<style>
:root {
  --bg: #0e0f13;
  --panel: #17181f;
  --border: #262a36;
  --text: #e8e8f0;
  --muted: #9aa0b0;
  --accent: #c7362f;
  --accent2: #3f6fd8;
  --good: #3fb96f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "PingFang SC", "Microsoft YaHei", "Segoe UI", system-ui, sans-serif;
  background: var(--bg); color: var(--text);
}
a { color: inherit; text-decoration: none; }

.app { display: grid; grid-template-columns: 230px 1fr; min-height: 100vh; }
.sidebar {
  background: var(--panel); border-right: 1px solid var(--border);
  padding: 1rem; display: flex; flex-direction: column; gap: 1rem;
}
.brand { font-weight: 800; font-size: 1.2rem; }
.brand span { color: var(--accent); }
.sidebar nav { display: flex; flex-direction: column; gap: 0.3rem; }
.sidebar nav a {
  padding: 0.5rem 0.7rem; border-radius: 8px; color: var(--muted);
}
.sidebar nav a:hover, .sidebar nav a.router-link-active {
  background: #232735; color: var(--text);
}
.search input {
  width: 100%; padding: 0.5rem 0.6rem; border-radius: 8px;
  border: 1px solid var(--border); background: #101116; color: var(--text);
}
.results {
  list-style: none; margin: 0.4rem 0 0; padding: 0; max-height: 320px; overflow: auto;
}
.results li {
  padding: 0.4rem 0.5rem; border-bottom: 1px solid var(--border); font-size: 0.85rem;
  cursor: pointer;
}
.results li:hover { background: #232735; color: var(--text); }
.results .snippet { color: var(--muted); font-size: 0.75rem; margin-top: 0.15rem; }
.results .kind { color: var(--accent2); margin-right: 0.3rem; }
.results em { color: var(--muted); font-style: normal; font-size: 0.75rem; }

.content { padding: 1.4rem; overflow-y: auto; }
</style>