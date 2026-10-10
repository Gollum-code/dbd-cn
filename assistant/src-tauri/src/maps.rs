use crate::db::{MapEntry, Realm};
use serde::Serialize;

/// Maps / hook / totem helper.
///
/// The wiki datatable stores map sizes + release history in `variations`
/// (JSON).  Hooks and totem spots are not exposed by the current datatables,
/// so they are surfaced as user landmarks here and kept extensible.

#[derive(Debug, Serialize, Clone)]
pub struct MapView {
    pub id: String,
    pub name_en: String,
    pub name_zh: String,
    pub realm: String,
    pub variations: Vec<MapVariation>,
    pub hooks: Option<i64>,
    pub totems: Option<i64>,
}

#[derive(Debug, Serialize, Clone)]
pub struct MapVariation {
    pub size: i64,
    pub release: String,
}

pub fn maps_with_realms(maps: &[MapEntry], realms: &[Realm]) -> Vec<MapView> {
    let realm_by_id: std::collections::HashMap<Option<i64>, String> = realms
        .iter()
        .map(|r| (Some(r.id), r.name_zh.clone()))
        .collect();

    maps.iter()
        .map(|m| {
            let variations: Vec<MapVariation> =
                serde_json::from_str::<Vec<serde_json::Value>>(&m.variations)
                    .unwrap_or_default()
                    .into_iter()
                    .map(|v| MapVariation {
                        size: v.get("size").and_then(|s| s.as_i64()).unwrap_or(0),
                        release: v
                            .get("release")
                            .and_then(|r| r.as_str())
                            .unwrap_or("")
                            .to_string(),
                    })
                    .collect();
            MapView {
                id: m.id.clone(),
                name_en: m.name_en.clone(),
                name_zh: m.name_zh.clone(),
                realm: realm_by_id.get(&m.realm_id).cloned().unwrap_or_default(),
                variations,
                hooks: m.hooks,
                totems: m.totems,
            }
        })
        .collect()
}