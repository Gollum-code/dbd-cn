mod db;
mod maps;
mod recommender;
mod search;

use db::{Addon, Build, Character, Db, MapEntry, Patch, Perk, Realm, SyncInfo};
use maps::{maps_with_realms, MapView};
use recommender::{Recommender, PLAYSTYLES, Recommendation};
use search::{search, SearchHit};
use std::sync::Mutex;
use tauri::{Manager, State};

struct AppState {
    db: Mutex<Db>,
}

#[tauri::command]
fn get_characters(state: State<AppState>) -> Result<Vec<Character>, String> {
    state.db.lock().map_err(|e| e.to_string())?.list_characters()
}

#[tauri::command]
fn get_perks(state: State<AppState>) -> Result<Vec<Perk>, String> {
    state.db.lock().map_err(|e| e.to_string())?.list_perks()
}

#[tauri::command]
fn get_addons(state: State<AppState>) -> Result<Vec<Addon>, String> {
    state.db.lock().map_err(|e| e.to_string())?.list_addons()
}

#[tauri::command]
fn get_maps(state: State<AppState>) -> Result<Vec<MapView>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let maps: Vec<MapEntry> = db.list_maps()?;
    let realms: Vec<Realm> = db.list_realms()?;
    Ok(maps_with_realms(&maps, &realms))
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
    let db = state.db.lock().map_err(|e| e.to_string())?;
    Ok(search(
        &db.list_characters()?,
        &db.list_perks()?,
        &db.list_addons()?,
        &db.list_maps()?,
        &db.list_realms()?,
        &query,
    ))
}

#[tauri::command]
fn recommend_build(
    state: State<AppState>,
    character_id: String,
    playstyle: String,
) -> Result<Vec<Recommendation>, String> {
    let db = state.db.lock().map_err(|e| e.to_string())?;
    let chars = db.list_characters()?;
    let perks = db.list_perks()?;
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
            app.manage(AppState { db: Mutex::new(db) });
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