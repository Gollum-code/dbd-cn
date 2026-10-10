import { createApp } from "vue";
import { createRouter, createWebHashHistory } from "vue-router";
import App from "./App.vue";
import Build from "./views/Build.vue";
import Builds from "./views/Builds.vue";
import Perks from "./views/Perks.vue";
import Roster from "./views/Roster.vue";
import Maps from "./views/Maps.vue";
import Changelog from "./views/Changelog.vue";

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/roster" },
    { path: "/roster", component: Roster },
    { path: "/perks", component: Perks },
    { path: "/builds", component: Build },
    { path: "/my-builds", component: Builds },
    { path: "/maps", component: Maps },
    { path: "/changelog", component: Changelog },
  ],
});

createApp(App).use(router).mount("#app");