mod db;
mod maps;
mod recommender;
mod search;

use db::{Addon, Build, Character, Db, MapEntry, Patch, Perk, Realm, SyncInfo};
use maps::{maps_with_realms, MapView};
use recommender::{Recommender, PLAYSTYLES, Recommendation};
use search::{search, SearchHit};
use std::sync::{Arc, Mutex};
use tauri::{Manager, State};

/// Read-only reference data loaded once from SQLite and kept in memory.
///
/// Only `builds` are written by the app, so every other table is immutable for
/// the lifetime of the process.  Caching avoids re-reading ~1.5k rows on every
/// keystroke in the search box, and returning `Arc<Vec<_>>` avoids cloning the
/// (often very long) description/lore text on each call.
#[derive(Default)]
struct Cache {
    chars: Option<Arc<Vec<Character>>>,
    perks: Option<Arc<Vec<Perk>>>,
    addons: Option<Arc<Vec<Addon>>>,
    maps: Option<Arc<Vec<MapEntry>>>,
    realms: Option<Arc<Vec<Realm>>>,
}

struct AppState {
    db: Mutex<Db>,
    cache: Mutex<Cache>,
}

impl AppState {
    fn characters(&self) -> Result<Arc<Vec<Character>>, String> {
        if let Some(c) = self.cache.lock().map_err(|e| e.to_string())?.chars.clone() {
            return Ok(c);
        }
        let v = self.db.lock().map_err(|e| e.to_string())?.list_characters()?;
        let arc = Arc::new(v);
        self.cache.lock().map_err(|e| e.to_string())?.chars = Some(arc.clone());
        Ok(arc)
    }
    fn perks(&self) -> Result<Arc<Vec<Perk>>, String> {
        if let Some(c) = self.cache.lock().map_err(|e| e.to_string())?.perks.clone() {
            return Ok(c);
        }
        let v = self.db.lock().map_err(|e| e.to_string())?.list_perks()?;
        let arc = Arc::new(v);
        self.cache.lock().map_err(|e| e.to_string())?.perks = Some(arc.clone());
        Ok(arc)
    }
    fn addons(&self) -> Result<Arc<Vec<Addon>>, String> {
        if let Some(c) = self.cache.lock().map_err(|e| e.to_string())?.addons.clone() {
            return Ok(c);
        }
        let v = self.db.lock().map_err(|e| e.to_string())?.list_addons()?;
        let arc = Arc::new(v);
        self.cache.lock().map_err(|e| e.to_string())?.addons = Some(arc.clone());
        Ok(arc)
    }
    fn maps(&self) -> Result<Arc<Vec<MapEntry>>, String> {
        if let Some(c) = self.cache.lock().map_err(|e| e.to_string())?.maps.clone() {
            return Ok(c);
        }
        let v = self.db.lock().map_err(|e| e.to_string())?.list_maps()?;
        let arc = Arc::new(v);
        self.cache.lock().map_err(|e| e.to_string())?.maps = Some(arc.clone());
        Ok(arc)
    }
    fn realms(&self) -> Result<Arc<Vec<Realm>>, String> {
        if let Some(c) = self.cache.lock().map_err(|e| e.to_string())?.realms.clone() {
            return Ok(c);
        }
        let v = self.db.lock().map_err(|e| e.to_string())?.list_realms()?;
        let arc = Arc::new(v);
        self.cache.lock().map_err(|e| e.to_string())?.realms = Some(arc.clone());
        Ok(arc)
    }
}

#[tauri::command]
fn get_characters(state: State<AppState>) -> Result<Vec<Character>, String> {
    Ok(state.characters()?.as_ref().clone())
}

#[tauri::command]
fn get_perks(state: State<AppState>) -> Result<Vec<Perk>, String> {
    Ok(state.perks()?.as_ref().clone())
}

#[tauri::command]
fn get_addons(state: State<AppState>) -> Result<Vec<Addon>, String> {
    Ok(state.addons()?.as_ref().clone())
}

#[tauri::command]
fn get_maps(state: State<AppState>) -> Result<Vec<MapView>, String> {
    Ok(maps_with_realms(&state.maps()?, &state.realms()?))
}

#[tauri::command]
fn get_patches(state: State<AppState>) -> Result<Vec<Patch>, String> {
    state.db.lock().map_err(|e| e.to_string())?.list_patches(50)
}

#[tauri::command]
fn get_sync_info(state: State<AppState>) -> Result<SyncInfo, String> {
    state.db.lock().map_err(|e| e.to_string())?.sync_info()
}

#[tauri::command]
fn search_all(
    state: State<AppState>,
    query: String,
) -> Result<Vec<SearchHit>, String> {
    Ok(search(
        &state.characters()?,
        &state.perks()?,
        &state.addons()?,
        &state.maps()?,
        &state.realms()?,
        &query,
    ))
}

#[tauri::command]
fn recommend_build(
    state: State<AppState>,
    character_id: String,
    playstyle: String,
) -> Result<Vec<Recommendation>, String> {
    let chars = state.characters()?;
    let perks = state.perks()?;
    let ch = chars
        .iter()
        .find(|c| c.id == character_id)
        .ok_or_else(|| format!("找不到角色 {character_id}"))?;
    Ok(Recommender::recommend(ch, &perks, &playstyle))
}

#[tauri::command]
fn get_playstyles() -> Vec<String> {
    PLAYSTYLES.iter().map(|s| s.to_string()).collect()
}

#[tauri::command]
fn save_build(
    state: State<AppState>,
    character: String,
    role: String,
    perks_json: String,
    addons_json: String,
    playstyle: String,
    rating: f64,
) -> Result<i64, String> {
    state.db.lock().map_err(|e| e.to_string())?.add_build(
        &character,
        &role,
        &perks_json,
        &addons_json,
        &playstyle,
        rating,
    )
}

#[tauri::command]
fn get_builds(state: State<AppState>, only_user: bool) -> Result<Vec<Build>, String> {
    state.db.lock().map_err(|e| e.to_string())?.list_builds(only_user)
}

#[tauri::command]
fn delete_build(state: State<AppState>, id: i64) -> Result<bool, String> {
    state.db.lock().map_err(|e| e.to_string())?.delete_build(id)
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let resource_dir = app.path().resource_dir().ok().map(|p| p.to_path_buf());
            let db = Db::open(resource_dir).expect("无法初始化数据库");
            db.seed_builds().ok();
            app.manage(AppState {
                db: Mutex::new(db),
                cache: Mutex::new(Cache::default()),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_characters,
            get_perks,
            get_addons,
            get_maps,
            get_patches,
            get_sync_info,
            search_all,
            recommend_build,
            get_playstyles,
            save_build,
            get_builds,
            delete_build,
        ])
        .run(tauri::generate_context!())
        .expect("error while running dbd assistant");
}