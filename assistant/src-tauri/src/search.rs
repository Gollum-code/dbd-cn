use crate::db::{Addon, Character, MapEntry, Perk, Realm};
use serde::Serialize;

/// Search across characters, perks, addons, maps and realms.
///
/// Name matches are ranked first; then we fall back to full-text over the
/// Chinese/English description/effect/lore and the structured perk tags, so
/// players can search by *effect* keywords ("治疗", "加速", "钩子", "Auras").
#[derive(Debug, Serialize, Clone)]
pub struct SearchHit {
    pub kind: String, // 杀手 | 逃生者 | 技能 | 附加品 | 地图 | 领域
    pub id: String,
    pub name_en: String,
    pub name_zh: String,
    pub extra: String,
    pub snippet: String, // matched text excerpt (empty for name hits)
}

/// Shorten a body string around the first match for display.
fn snippet(body: &str, q: &str, width: usize) -> String {
    let lower = body.to_lowercase();
    let pos = match lower.find(q) {
        Some(p) => p,
        None => return body.chars().take(width).collect(),
    };
    // walk back to a char boundary near the match
    let start = lower[..pos].char_indices().rev().nth(width / 2).map(|(i, _)| i).unwrap_or(0);
    let mut out: String = body[start..].chars().take(width).collect();
    if start > 0 {
        out.insert(0, '…');
    }
    if body.len() > start + out.len() {
        out.push('…');
    }
    out
}

pub fn search(
    chars: &[Character],
    perks: &[Perk],
    addons: &[Addon],
    maps: &[MapEntry],
    realms: &[Realm],
    query: &str,
) -> Vec<SearchHit> {
    let q = query.trim().to_lowercase();
    if q.is_empty() {
        return Vec::new();
    }
    let mut hits: Vec<SearchHit> = Vec::new();

    // ---- pass 1: name / id matches (highest priority) ----
    for c in chars {
        if name_hit(&q, &c.id, &c.name_en, &c.name_zh) {
            hits.push(SearchHit {
                kind: if c.role == "killer" { "杀手" } else { "逃生者" }.into(),
                id: c.id.clone(),
                name_en: c.name_en.clone(),
                name_zh: c.name_zh.clone(),
                extra: c.role.clone(),
                snippet: String::new(),
            });
        }
    }
    for p in perks {
        if name_hit(&q, &p.id, &p.name_en, &p.name_zh) {
            hits.push(SearchHit {
                kind: "技能".into(),
                id: p.id.clone(),
                name_en: p.name_en.clone(),
                name_zh: p.name_zh.clone(),
                extra: if p.role == "killer" { "杀手技能" } else { "逃生者技能" }.into(),
                snippet: String::new(),
            });
        }
    }
    for a in addons {
        if name_hit(&q, &a.id, &a.name_en, &a.name_zh) {
            hits.push(SearchHit {
                kind: "附加品".into(),
                id: a.id.clone(),
                name_en: a.name_en.clone(),
                name_zh: a.name_zh.clone(),
                extra: a.rarity.clone(),
                snippet: String::new(),
            });
        }
    }
    for m in maps {
        if name_hit(&q, &m.id, &m.name_en, &m.name_zh) {
            hits.push(SearchHit {
                kind: "地图".into(),
                id: m.id.clone(),
                name_en: m.name_en.clone(),
                name_zh: m.name_zh.clone(),
                extra: String::new(),
                snippet: String::new(),
            });
        }
    }
    for r in realms {
        if name_hit(&q, &r.id.to_string(), &r.name_en, &r.name_zh) {
            hits.push(SearchHit {
                kind: "领域".into(),
                id: r.id.to_string(),
                name_en: r.name_en.clone(),
                name_zh: r.name_zh.clone(),
                extra: r.location.clone(),
                snippet: String::new(),
            });
        }
    }

    // ---- pass 2: body / tag matches ----
    if hits.len() < 40 {
        for p in perks {
            if hits.len() >= 40 { break; }
            if already_present(&hits, &p.id) { continue; }
            let desc = p.description.as_deref().unwrap_or("");
            let tags = p.tags.as_str();
            if body_hit(&q, desc) || body_hit(&q, tags) {
                let src = if body_hit(&q, desc) { desc } else { tags };
                hits.push(SearchHit {
                    kind: "技能".into(),
                    id: p.id.clone(),
                    name_en: p.name_en.clone(),
                    name_zh: p.name_zh.clone(),
                    extra: if body_hit(&q, desc) {
                        if p.role == "killer" { "杀手技能" } else { "逃生者技能" }.into()
                    } else {
                        "效果标签".into()
                    },
                    snippet: snippet(src, &q, 70),
                });
            }
        }
        for a in addons {
            if hits.len() >= 40 { break; }
            if already_present(&hits, &a.id) { continue; }
            let eff = a.effect.as_deref().unwrap_or("");
            if body_hit(&q, eff) || body_hit(&q, a.tags.as_str()) {
                hits.push(SearchHit {
                    kind: "附加品".into(),
                    id: a.id.clone(),
                    name_en: a.name_en.clone(),
                    name_zh: a.name_zh.clone(),
                    extra: a.rarity.clone(),
                    snippet: snippet(eff, &q, 70),
                });
            }
        }
        for c in chars {
            if hits.len() >= 40 { break; }
            if already_present(&hits, &c.id) { continue; }
            let lore = c.lore.as_deref().unwrap_or("");
            let power = c.power.as_deref().unwrap_or("");
            if body_hit(&q, lore) || body_hit(&q, power) {
                let src = if body_hit(&q, power) { power } else { lore };
                hits.push(SearchHit {
                    kind: if c.role == "killer" { "杀手" } else { "逃生者" }.into(),
                    id: c.id.clone(),
                    name_en: c.name_en.clone(),
                    name_zh: c.name_zh.clone(),
                    extra: "背景".into(),
                    snippet: snippet(src, &q, 70),
                });
            }
        }
    }

    hits.truncate(40);
    hits
}

fn already_present(hits: &[SearchHit], id: &str) -> bool {
    hits.iter().any(|h| h.id == id)
}

fn name_hit(q: &str, id: &str, name_en: &str, name_zh: &str) -> bool {
    id.to_lowercase() == q
        || name_en.to_lowercase().contains(q)
        || name_zh.to_lowercase().contains(q)
}

fn body_hit(q: &str, body: &str) -> bool {
    !body.is_empty() && body.to_lowercase().contains(q)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn perk(id: &str, desc: &str, tags: &str) -> Perk {
        Perk {
            id: id.into(),
            name_en: id.into(),
            name_zh: id.into(),
            owner: "S01".into(),
            role: "survivor".into(),
            tiers: "{}".into(),
            units: "{}".into(),
            tags: tags.into(),
            patch: None,
            description: Some(desc.into()),
            icon: None,
        }
    }

    #[test]
    fn matches_name_first() {
        let p = perk("adrenaline", "当你处于逃脱边缘", "[]");
        let hits = search(&[], &[p], &[], &[], &[], "adrenaline");
        assert_eq!(hits.len(), 1);
        assert!(hits[0].snippet.is_empty());
    }

    #[test]
    fn matches_chinese_description() {
        let p = perk("p1", "受到伤害后可以加速逃跑", "[]");
        let hits = search(&[], &[p], &[], &[], &[], "加速");
        assert_eq!(hits.len(), 1);
        assert!(hits[0].snippet.contains("加速"));
    }

    #[test]
    fn matches_english_tag() {
        let p = perk("p2", "", "[\"Auras\",\"Haste\"]");
        let hits = search(&[], &[p], &[], &[], &[], "auras");
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].extra, "效果标签");
    }

    #[test]
    fn no_duplicate_for_same_id() {
        let p = perk("p3", "治疗效果很强", "[]");
        let hits = search(&[], &[p], &[], &[], &[], "p3");
        assert_eq!(hits.len(), 1);
    }

    #[test]
    fn empty_query_returns_nothing() {
        let p = perk("p4", "x", "[]");
        assert!(search(&[], &[p], &[], &[], &[], "  ").is_empty());
    }
}