import { createApp } from "vue";
import { createRouter, createWebHashHistory } from "vue-router";
import App from "./App.vue";
import Build from "./views/Build.vue";
import Builds from "./views/Builds.vue";
import Addons from "./views/Addons.vue";
import Perks from "./views/Perks.vue";
import Roster from "./views/Roster.vue";
import Maps from "./views/Maps.vue";
import Changelog from "./views/Changelog.vue";
import About from "./views/About.vue";

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/roster" },
    { path: "/roster", component: Roster },
    { path: "/perks", component: Perks },
    { path: "/addons", component: Addons },
    { path: "/builds", component: Build },
    { path: "/my-builds", component: Builds },
    { path: "/maps", component: Maps },
    { path: "/changelog", component: Changelog },
    { path: "/about", component: About },
  ],
});

createApp(App).use(router).mount("#app");