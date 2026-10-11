// Tauri invoke wrapper with graceful fallback so the UI can also run in a
// plain browser (dev) without the Rust backend.
const IS_TAURI = typeof window !== "undefined" && window.__TAURI_INTERNALS__;

async function invoke(cmd, args = {}) {
  if (IS_TAURI) {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke(cmd, args);
  }
  return demoFallback(cmd, args);
}

/** Resolve a DB icon path (icons/.../x.png) to a renderable URL. */
async function iconUrl(path) {
  if (!path) return "";
  if (IS_TAURI) {
    const { convertFileSrc } = await import("@tauri-apps/api/core");
    const { resourceDir, appDataDir, join } = await import("@tauri-apps/api/path");
    // Icons ship with the bundle (read-only is fine for reading).
    const base = await resourceDir();
    const file = await join(base, "data", "icons", path.replace("icons/", ""));
    return convertFileSrc(file.replace(/\\/g, "/"));
  }
  // browser fallback: try serving from /icons/<path> on the dev server
  return "/icons/" + path.replace("icons/", "");
}

// ---- demo data (used only when running outside Tauri) ----
const DEMO_CHARS = [
  { id: "K01", name_en: "Trapper", name_zh: "设陷者", role: "killer", difficulty: "1", speed: "4.6", terror_radius: "32.0", speed_forms: [{ label: "", value: "4.6" }], terror_forms: [{ label: "", value: "32" }], gender: "男性", origin: "美国人", actor: null, power: "捕兽夹", lore: null, icon: null },
  { id: "K02", name_en: "Wraith", name_zh: "幽灵", role: "killer", difficulty: "1", speed: "[4.6, \"Uncloaked\"]", terror_radius: "32.0", speed_forms: [{ label: "Uncloaked", value: "4.6" }], terror_forms: [{ label: "", value: "32" }], gender: "男性", origin: "尼日利亚人", actor: null, power: "哀嚎钟", lore: null, icon: null },
  { id: "S01", name_en: "Dwight Fairfield", name_zh: "德怀特·费尔菲尔德", role: "survivor", difficulty: null, speed: null, terror_radius: null, speed_forms: [], terror_forms: [], gender: "男性", origin: "美国人", actor: null, power: null, lore: null, icon: null },
];
const DEMO_PERKS = [
  { id: "agitation", name_en: "Agitation", name_zh: "焦躁不安", owner: "K01", role: "killer", tiers: '{"1":14,"2":16,"3":18}', units: '{"1":"metres"}', tags: '["Carrying","MovementSpeed","TerrorRadius"]', patch: "10.2.0", description: "携带逃生者时，恐惧范围扩大。", icon: null },
  { id: "brutalStrength", name_en: "Brutal Strength", name_zh: "残暴之力", owner: "K01", role: "killer", tiers: '{"1":40,"2":50,"3":60}', units: null, tags: '["BasicAttack","SurvivorCarry"]', patch: null, description: null, icon: null },
  { id: "ironGrasp", name_en: "Iron Grasp", name_zh: "铁掌", owner: "K01", role: "killer", tiers: '{"1":15,"2":20,"3":25}', units: null, tags: '["Hook","Carry"]', patch: null, description: null, icon: null },
];
const DEMO_MAPS = [
  { id: "1", name_en: "Coal Tower", name_zh: "煤塔", realm: "麦克米伦庄园", variations: [{ size: 132, release: "1.0.0" }], hooks: 10, totems: 5 },
];
const DEMO_PLAYSTYLES = ["控场压制", "追逐击倒", "信息/侦查", "守尸/防御", "机动游击"];
const DEMO_BUILDS = [
  { id: 1, character: "K01", role: "killer", perks: '["agitation","brutalStrength","ironGrasp"]', addons: "[]", playstyle: "控场压制", rating: 0, source: "default" },
];
const DEMO_ADDONS = [
  { id: "rustedJaws", name_en: "Rusted Jaws", name_zh: "生锈钳口", owner: "K01", rarity: "罕见", rarity_en: "Uncommon", tags: '["DeepWound"]', effect: "被捕兽夹夹伤的逃生者会陷入深度伤口状态，持续 70 秒。", icon: null },
  { id: "tarBottle", name_en: "Tar Bottle", name_zh: "焦油瓶", owner: "K01", rarity: "稀有", rarity_en: "Rare", tags: '["TrapDisguise"]', effect: "一种黑色、哑光且有黏性的物质，涂抹在捕兽夹上能使其不那么显眼。", icon: null },
];

function demoFallback(cmd, args) {
  switch (cmd) {
    case "get_characters": return Promise.resolve(DEMO_CHARS);
    case "get_perks": return Promise.resolve(DEMO_PERKS);
    case "get_addons": return Promise.resolve(DEMO_ADDONS);
    case "get_maps": return Promise.resolve(DEMO_MAPS);
    case "get_patches": return Promise.resolve([]);
    case "get_sync_info": return Promise.resolve({ last_sync: null, source: null, latest_patch: null });
    case "get_playstyles": return Promise.resolve(DEMO_PLAYSTYLES);
    case "get_builds": return Promise.resolve(DEMO_BUILDS);
    case "delete_build": return Promise.resolve(false);
    case "search_all": {
      const q = (args.query || "").toLowerCase();
      return Promise.resolve(
        DEMO_CHARS.filter((c) => c.name_en.toLowerCase().includes(q)).slice(0, 20)
      );
    }
    case "recommend_build": return Promise.resolve([]);
    case "save_build": return Promise.resolve(1);
    default: return Promise.resolve(null);
  }
}

export default { invoke, iconUrl, IS_TAURI };