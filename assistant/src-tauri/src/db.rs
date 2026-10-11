use rusqlite::{Connection, params};
use serde::Serialize;
use std::path::PathBuf;

#[derive(Debug, Serialize, Clone)]
pub struct Character {
    pub id: String,
    pub name_en: String,
    pub name_zh: String,
    pub role: String,
    pub difficulty: Option<String>,
    /// raw stat strings as stored (may be plain numbers or JSON)
    pub speed: Option<String>,
    pub terror_radius: Option<String>,
    /// parsed forms for display (multi-form killers have several entries)
    pub speed_forms: Vec<StatForm>,
    pub terror_forms: Vec<StatForm>,
    pub gender: Option<String>,
    pub origin: Option<String>,
    pub actor: Option<String>,
    pub power: Option<String>,
    pub lore: Option<String>,
    pub icon: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
pub struct Perk {
    pub id: String,
    pub name_en: String,
    pub name_zh: String,
    pub owner: String,
    pub role: String,
    pub tiers: String,
    pub units: String,
    pub tags: String,
    pub patch: Option<String>,
    pub description: Option<String>,
    pub icon: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
pub struct Addon {
    pub id: String,
    pub name_en: String,
    pub name_zh: String,
    pub owner: String,
    pub rarity: String,
    pub rarity_en: String,
    pub tags: String,
    pub effect: Option<String>,
    pub icon: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
pub struct MapEntry {
    pub id: String,
    pub name_en: String,
    pub name_zh: String,
    pub realm_id: Option<i64>,
    pub variations: String,
    pub hooks: Option<i64>,
    pub totems: Option<i64>,
}

#[derive(Debug, Serialize, Clone)]
pub struct Realm {
    pub id: i64,
    pub name_en: String,
    pub name_zh: String,
    pub abbr: String,
    pub location: String,
    pub color: String,
}

#[derive(Debug, Serialize, Clone)]
pub struct Build {
    pub id: i64,
    pub character: String,
    pub role: String,
    pub perks: String,
    pub addons: String,
    pub playstyle: String,
    pub rating: f64,
    pub source: String,
}

#[derive(Debug, Serialize, Clone)]
pub struct Patch {
    pub id: i64,
    pub patch: String,
    pub rdate: String,
    pub ptb: bool,
    pub notes: String,
}

#[derive(Debug, Serialize, Clone)]
pub struct SyncInfo {
    pub last_sync: Option<String>,
    pub source: Option<String>,
    pub latest_patch: Option<String>,
}

/// One labelled stat form (e.g. Stalker Mode = 32 m).
#[derive(Debug, Serialize, Clone)]
pub struct StatForm {
    pub label: String,
    pub value: String,
}

/// Parse a killer stat that may be a plain number or a JSON list of
/// [value, label] pairs (some killers change speed / terror radius by form).
pub fn parse_stat_forms(raw: &str) -> Vec<StatForm> {
    let text = raw.trim();
    if text.is_empty() {
        return Vec::new();
    }
    // plain number (possibly stored as text)
    if let Ok(v) = text.parse::<f64>() {
        return vec![StatForm { label: String::new(), value: fmt_num(v) }];
    }
    let value: serde_json::Value = match serde_json::from_str(text) {
        Ok(v) => v,
        Err(_) => return Vec::new(),
    };
    let arr = match value.as_array() {
        Some(a) => a,
        None => return Vec::new(),
    };
    // shape [4.6, "Uncloaked"] -> single labelled form
    if arr.len() == 2 && arr[0].is_number() && arr[1].is_string() {
        return vec![StatForm {
            label: arr[1].as_str().unwrap_or("").to_string(),
            value: fmt_num(arr[0].as_f64().unwrap_or(0.0)),
        }];
    }
    // shape [[32, "Stalker Mode"], [16, "Pursuer Mode"], ...]
    let mut out = Vec::new();
    for item in arr {
        if let Some(pair) = item.as_array() {
            if pair.len() == 2 && pair[0].is_number() {
                out.push(StatForm {
                    label: pair[1].as_str().unwrap_or("").to_string(),
                    value: fmt_num(pair[0].as_f64().unwrap_or(0.0)),
                });
            }
        } else if let Some(n) = item.as_f64() {
            out.push(StatForm { label: String::new(), value: fmt_num(n) });
        }
    }
    out
}

fn fmt_num(v: f64) -> String {
    if v.fract() == 0.0 {
        format!("{}", v as i64)
    } else {
        format!("{}", v)
    }
}

pub struct Db {
    conn: Connection,
}

impl Db {
    /// Open the database, preferring a writable copy.
    ///
    /// In a packaged build the bundled database lives inside the app bundle,
    /// which is read-only on macOS (/Applications) and Windows (Program
    /// Files).  We therefore copy it once into the user-data directory and
    /// always work on that copy, so saving builds keeps working.
    pub fn open(resource_dir: Option<PathBuf>) -> Result<Self, String> {
        let path = Self::db_path(resource_dir)?;
        let conn = Connection::open(&path).map_err(|e| format!("无法打开数据库: {e}"))?;
        Ok(Self { conn })
    }

    /// Locate a *writable* database.
    ///
    /// Order: user-data copy (created from the bundled one on first run) →
    /// dev-time ./data/dbd_cn.db → user-data path even if it does not exist yet.
    fn db_path(resource_dir: Option<PathBuf>) -> Result<PathBuf, String> {
        let dev_copy = PathBuf::from("./data/dbd_cn.db");

        if let Some(user_dir) = dirs_data() {
            if !user_dir.exists() {
                let _ = std::fs::create_dir_all(&user_dir);
            }
            let user_db = user_dir.join("dbd_cn.db");
            // seed the user copy from the bundled/dev database once
            let source = resource_dir
                .as_ref()
                .map(|d| d.join("dbd_cn.db"))
                .filter(|p| p.exists())
                .or_else(|| dev_copy.exists().then(|| dev_copy.clone()));
            if let Some(src) = source {
                if !user_db.exists() {
                    if let Some(parent) = user_db.parent() {
                        let _ = std::fs::create_dir_all(parent);
                    }
                    if std::fs::copy(&src, &user_db).is_err() {
                        // fall back to opening the source directly (read-only)
                        return Ok(src);
                    }
                }
            }
            if user_db.exists() {
                return Ok(user_db);
            }
        }

        // dev fallback: use the repo copy (writable)
        if dev_copy.exists() {
            return Ok(dev_copy);
        }
        // last resort: bundled resource (may be read-only)
        if let Some(d) = resource_dir {
            let p = d.join("dbd_cn.db");
            if p.exists() {
                return Ok(p);
            }
        }
        Ok(dev_copy)
    }

    pub fn list_characters(&self) -> Result<Vec<Character>, String> {
        let mut stmt = self
            .conn
            .prepare(
                "SELECT id, name_en, name_zh, role, difficulty,
                        CAST(speed AS TEXT), CAST(terror_radius AS TEXT),
                        gender, origin, actor, power, lore, icon
                 FROM characters ORDER BY role, id",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |r| {
                let speed: Option<String> = r.get(5)?;
                let radius: Option<String> = r.get(6)?;
                Ok(Character {
                    id: r.get(0)?,
                    name_en: r.get(1)?,
                    name_zh: r.get(2)?,
                    role: r.get(3)?,
                    difficulty: r.get(4)?,
                    speed_forms: speed
                        .as_deref()
                        .map(parse_stat_forms)
                        .unwrap_or_default(),
                    terror_forms: radius
                        .as_deref()
                        .map(parse_stat_forms)
                        .unwrap_or_default(),
                    speed,
                    terror_radius: radius,
                    gender: r.get(7)?,
                    origin: r.get(8)?,
                    actor: r.get(9)?,
                    power: r.get(10)?,
                    lore: r.get(11)?,
                    icon: r.get(12)?,
                })
            })
            .map_err(|e| e.to_string())?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?;
        Ok(rows)
    }

    pub fn list_perks(&self) -> Result<Vec<Perk>, String> {
        let mut stmt = self
            .conn
            .prepare(
                "SELECT id, name_en, name_zh, owner, role, tiers, units, tags, patch, description, icon
                 FROM perks ORDER BY name_en",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |r| {
                Ok(Perk {
                    id: r.get(0)?,
                    name_en: r.get(1)?,
                    name_zh: r.get(2)?,
                    owner: r.get(3)?,
                    role: r.get(4)?,
                    tiers: r.get(5)?,
                    units: r.get(6)?,
                    tags: r.get(7)?,
                    patch: r.get(8)?,
                    description: r.get(9)?,
                    icon: r.get(10)?,
                })
            })
            .map_err(|e| e.to_string())?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?;
        Ok(rows)
    }

    pub fn list_addons(&self) -> Result<Vec<Addon>, String> {
        let mut stmt = self
            .conn
            .prepare(
                "SELECT id, name_en, name_zh, owner, rarity, rarity_en, tags, effect, icon
                 FROM addons ORDER BY name_en",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |r| {
                Ok(Addon {
                    id: r.get(0)?,
                    name_en: r.get(1)?,
                    name_zh: r.get(2)?,
                    owner: r.get(3)?,
                    rarity: r.get(4)?,
                    rarity_en: r.get(5)?,
                    tags: r.get(6)?,
                    effect: r.get(7)?,
                    icon: r.get(8)?,
                })
            })
            .map_err(|e| e.to_string())?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?;
        Ok(rows)
    }

    pub fn list_maps(&self) -> Result<Vec<MapEntry>, String> {
        let mut stmt = self
            .conn
            .prepare("SELECT id, name_en, name_zh, realm_id, variations, hooks, totems FROM maps ORDER BY name_en")
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |r| {
                Ok(MapEntry {
                    id: r.get(0)?,
                    name_en: r.get(1)?,
                    name_zh: r.get(2)?,
                    realm_id: r.get(3)?,
                    variations: r.get(4)?,
                    hooks: r.get(5)?,
                    totems: r.get(6)?,
                })
            })
            .map_err(|e| e.to_string())?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?;
        Ok(rows)
    }

    pub fn list_patches(&self, limit: i64) -> Result<Vec<Patch>, String> {
        let mut stmt = self
            .conn
            .prepare(
                "SELECT id, patch, rdate, ptb, notes FROM patches ORDER BY id DESC LIMIT ?",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([limit], |r| {
                Ok(Patch {
                    id: r.get(0)?,
                    patch: r.get(1)?,
                    rdate: r.get(2)?,
                    ptb: r.get(3)?,
                    notes: r.get(4)?,
                })
            })
            .map_err(|e| e.to_string())?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?;
        Ok(rows)
    }

    pub fn sync_info(&self) -> Result<SyncInfo, String> {
        let mut last_sync: Option<String> = None;
        let mut source: Option<String> = None;
        let mut rows = self
            .conn
            .prepare("SELECT key, value FROM sync_meta")
            .map_err(|e| e.to_string())?;
        let iter = rows
            .query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)))
            .map_err(|e| e.to_string())?;
        for row in iter {
            let (k, v) = row.map_err(|e| e.to_string())?;
            if k == "last_sync" {
                last_sync = Some(v);
            } else if k == "source" {
                source = Some(v);
            }
        }
        let latest_patch: Option<String> = self
            .conn
            .query_row("SELECT patch FROM patches ORDER BY id DESC LIMIT 1", [], |r| {
                r.get(0)
            })
            .ok();
        Ok(SyncInfo {
            last_sync,
            source,
            latest_patch,
        })
    }

    pub fn list_realms(&self) -> Result<Vec<Realm>, String> {
        let mut stmt = self
            .conn
            .prepare(
                "SELECT id, name_en, name_zh, abbr, location, color
                 FROM realms ORDER BY id",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |r| {
                Ok(Realm {
                    id: r.get(0)?,
                    name_en: r.get(1)?,
                    name_zh: r.get(2)?,
                    abbr: r.get(3)?,
                    location: r.get(4)?,
                    color: r.get(5)?,
                })
            })
            .map_err(|e| e.to_string())?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?;
        Ok(rows)
    }

    pub fn add_build(
        &self,
        character: &str,
        role: &str,
        perks_json: &str,
        addons_json: &str,
        playstyle: &str,
        rating: f64,
    ) -> Result<i64, String> {
        self.conn
            .execute(
                "INSERT INTO builds (character, role, perks, addons, playstyle, rating)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                params![character, role, perks_json, addons_json, playstyle, rating],
            )
            .map_err(|e| e.to_string())?;
        Ok(self.conn.last_insert_rowid())
    }

    pub fn list_builds(&self, only_user: bool) -> Result<Vec<Build>, String> {
        let (sql, params): (&str, Vec<&dyn rusqlite::ToSql>) = if only_user {
            (
                "SELECT id, character, role, perks, addons, playstyle, rating, source
                 FROM builds WHERE source != 'default' ORDER BY id DESC",
                vec![],
            )
        } else {
            (
                "SELECT id, character, role, perks, addons, playstyle, rating, source
                 FROM builds ORDER BY id DESC",
                vec![],
            )
        };
        let mut stmt = self.conn.prepare(sql).map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(rusqlite::params_from_iter(params), |r| {
                Ok(Build {
                    id: r.get(0)?,
                    character: r.get(1)?,
                    role: r.get(2)?,
                    perks: r.get(3)?,
                    addons: r.get(4)?,
                    playstyle: r.get(5)?,
                    rating: r.get(6).unwrap_or(0.0),
                    source: r.get::<_, Option<String>>(7)?.unwrap_or_else(|| "user".into()),
                })
            })
            .map_err(|e| e.to_string())?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?;
        Ok(rows)
    }

    pub fn delete_build(&self, id: i64) -> Result<bool, String> {
        let n = self
            .conn
            .execute("DELETE FROM builds WHERE id = ?1 AND source != 'default'", [id])
            .map_err(|e| e.to_string())?;
        Ok(n > 0)
    }

    /// Seed a couple of starter builds if the table is empty (offline demo).
    pub fn seed_builds(&self) -> Result<(), String> {
        let count: i64 = self
            .conn
            .query_row("SELECT COUNT(*) FROM builds", [], |r| r.get(0))
            .map_err(|e| e.to_string())?;
        if count > 0 {
            return Ok(());
        }
        self.conn
            .execute_batch(
                r#"
                INSERT INTO builds (character, role, perks, addons, playstyle, rating, source)
                VALUES ('K01', 'killer', '["brutalStrength","agitation","ironGrasp","monstrousShrine"]',
                        '["stichedBag","rustedJaws"]', '控场流：熊夹封锁必经路线，配合高恐惧范围压制逃生者。', 4.6, 'default');
                INSERT INTO builds (character, role, perks, addons, playstyle, rating, source)
                VALUES ('S01', 'survivor', '["bond","proveThyself","weWillMakeIt","leader"]',
                        '[]', '团队辅助流：报点+加速修机+快速治疗，适合车队开黑。', 4.2, 'default');
                INSERT INTO builds (character, role, perks, addons, playstyle, rating, source)
                VALUES ('K02', 'killer', '["hexRuin","hexUndying","hexRetribution","hexDevourHope"]',
                        '["boneClapper","coxscomb"]', '图腾流：图腾叠 buff，利用咒术体系压制修机节奏。', 4.5, 'default');
                INSERT INTO builds (character, role, perks, addons, playstyle, rating, source)
                VALUES ('S04', 'survivor', '["ironWill","sprintBurst","deadHard","decisiveStrike"]',
                        '[]', '硬核遛鬼流：位移+反制，配合打击技能拖延杀手。', 4.4, 'default');
                "#,
            )
            .map_err(|e| e.to_string())
    }
}

/// Resolve the OS user-data directory.
fn dirs_data() -> Option<PathBuf> {
    #[cfg(windows)]
    {
        std::env::var_os("APPDATA").map(PathBuf::from)
    }
    #[cfg(target_os = "macos")]
    {
        std::env::var_os("HOME")
            .map(|h| PathBuf::from(h).join("Library/Application Support"))
    }
    #[cfg(not(any(windows, target_os = "macos")))]
    {
        std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".config"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plain_number() {
        let f = parse_stat_forms("4.6");
        assert_eq!(f.len(), 1);
        assert_eq!(f[0].label, "");
        assert_eq!(f[0].value, "4.6");
    }

    #[test]
    fn integer_is_trimmed() {
        let f = parse_stat_forms("32.0");
        assert_eq!(f[0].value, "32");
    }

    #[test]
    fn single_labelled_form() {
        let f = parse_stat_forms(r#"[4.6, "Uncloaked"]"#);
        assert_eq!(f.len(), 1);
        assert_eq!(f[0].label, "Uncloaked");
        assert_eq!(f[0].value, "4.6");
    }

    #[test]
    fn multiple_forms() {
        let f = parse_stat_forms(r#"[[32, "Stalker Mode"], [16, "Pursuer Mode"]]"#);
        assert_eq!(f.len(), 2);
        assert_eq!(f[0].value, "32");
        assert_eq!(f[1].label, "Pursuer Mode");
    }

    #[test]
    fn empty_and_garbage() {
        assert!(parse_stat_forms("").is_empty());
        assert!(parse_stat_forms("nonsense").is_empty());
    }
}