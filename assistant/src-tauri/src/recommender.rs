use crate::db::{Character, Perk};
use serde::Serialize;
use std::collections::HashMap;

/// Playstyle archetypes (in Chinese, shown in the UI).
pub const PLAYSTYLES: &[&str] = &[
    "控场压制", // area control / pressure
    "追逐击倒", // chase & down
    "信息/侦查", // info / aura reading
    "守尸/防御", // camping / defense
    "机动游击", // mobility / hit-and-run
];

/// Rules-based perk recommender.
///
/// Scores every perk available to the selected character against the chosen
/// playstyle using a small tag->weight table, then returns the top 4 with a
/// per-perk reason (Chinese).
pub struct Recommender;

impl Recommender {
    pub fn recommend(
        character: &Character,
        perks: &[Perk],
        playstyle: &str,
    ) -> Vec<Recommendation> {
        let weights = weights_for(playstyle);
        let owned: Vec<&Perk> = perks
            .iter()
            .filter(|p| p.owner == character.id)
            .collect();

        let mut scored: Vec<(f64, &Perk)> = owned
            .iter()
            .filter_map(|p| {
                let tags = parse_tags(&p.tags);
                let score = score_tags(&tags, &weights);
                if score <= 0.0 {
                    return None;
                }
                Some((score, *p))
            })
            .collect();

        scored.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));

        let mut out: Vec<Recommendation> = scored
            .into_iter()
            .take(4)
            .map(|(score, p)| Recommendation {
                perk_id: p.id.clone(),
                name_en: p.name_en.clone(),
                name_zh: p.name_zh.clone(),
                score,
                reason: reason_for(playstyle, &p.tags),
            })
            .collect();

        // Fill remaining slots from universal/teachable perks when the
        // character has fewer than 4 matching ones.
        if out.len() < 4 {
            let used: std::collections::HashSet<&str> =
                out.iter().map(|r| r.perk_id.as_str()).collect();
            let mut pool: Vec<&Perk> = perks
                .iter()
                .filter(|p| p.owner != character.id && !used.contains(p.id.as_str()))
                .collect();
            pool.sort_by(|a, b| {
                let sa = score_tags(&parse_tags(&a.tags), &weights);
                let sb = score_tags(&parse_tags(&b.tags), &weights);
                sb.partial_cmp(&sa).unwrap_or(std::cmp::Ordering::Equal)
            });
            for p in pool.into_iter().take(4 - out.len()) {
                let score = score_tags(&parse_tags(&p.tags), &weights);
                out.push(Recommendation {
                    perk_id: p.id.clone(),
                    name_en: p.name_en.clone(),
                    name_zh: p.name_zh.clone(),
                    score,
                    reason: format!("补充位（{}）", reason_for(playstyle, &p.tags)),
                });
            }
        }
        out
    }
}

#[derive(Debug, Serialize, Clone)]
pub struct Recommendation {
    pub perk_id: String,
    pub name_en: String,
    pub name_zh: String,
    pub score: f64,
    pub reason: String,
}

type TagWeights = HashMap<&'static str, f64>;

fn weights_for(playstyle: &str) -> TagWeights {
    let mut w = TagWeights::new();
    match playstyle {
        "控场压制" => {
            for t in ["AreaControl", "Slowing", "TerrorRadius", "Traps", "Totems", "Haste"] {
                w.insert(t, 2.0);
            }
        }
        "追逐击倒" => {
            for t in ["Chase", "Exposed", "MovementSpeed", "Speed", "BasicAttack", "Lacerations"] {
                w.insert(t, 2.0);
            }
        }
        "信息/侦查" => {
            for t in ["Auras", "SurvivorLocation", "Tracking", "KillerLocation", "Stealth"] {
                w.insert(t, 2.0);
            }
        }
        "守尸/防御" => {
            for t in ["HookSabotage", "Carrying", "Deviousness", "Regression", "Generator"] {
                w.insert(t, 2.0);
            }
        }
        "机动游击" => {
            for t in ["Teleportation", "Mobility", "MovementSpeed", "Haste", "Invisibility"] {
                w.insert(t, 2.0);
            }
        }
        _ => {
            for t in ["General", "Utility", "Survivor", "Killer"] {
                w.insert(t, 1.0);
            }
        }
    }
    w.insert("General", 0.5);
    w
}

fn parse_tags(raw: &str) -> Vec<String> {
    serde_json::from_str::<Vec<String>>(raw).unwrap_or_default()
}

fn score_tags(tags: &[String], weights: &TagWeights) -> f64 {
    tags.iter().fold(0.0, |acc, t| {
        let base = weights.get(t.as_str()).copied().unwrap_or(0.0);
        // substring match for compound tags, e.g. "MovementSpeed" -> "Speed"
        let low = t.to_ascii_lowercase();
        let sub = weights
            .iter()
            .filter(|(k, _)| low.contains(&k.to_ascii_lowercase()))
            .map(|(_, v)| *v)
            .fold(0.0, f64::max);
        acc + base + sub
    })
}

fn reason_for(playstyle: &str, raw_tags: &str) -> String {
    let tags = parse_tags(raw_tags);
    let zh = match playstyle {
        "控场压制" => "强化领域控制/减速，符合控场思路",
        "追逐击倒" => "增强追猎与击倒能力",
        "信息/侦查" => "提供关键信息与侦察，便于决策",
        "守尸/防御" => "配合钩子防守与发电机回归",
        "机动游击" => "提升机动性，打带跑",
        _ => "通用增益，适用多数场景",
    };
    let tags_en: Vec<String> = tags.iter().take(3).cloned().collect();
    format!("{zh}（{}）", tags_en.join("/"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::Perk;

    fn perk(id: &str, owner: &str, tags: &str) -> Perk {
        Perk {
            id: id.into(),
            name_en: id.into(),
            name_zh: id.into(),
            owner: owner.into(),
            role: "killer".into(),
            tiers: "{}".into(),
            units: "{}".into(),
            tags: tags.into(),
            patch: None,
            description: None,
            icon: None,
        }
    }

    fn trapper() -> Character {
        Character {
            id: "K01".into(),
            name_en: "Trapper".into(),
            name_zh: "设陷者".into(),
            role: "killer".into(),
            difficulty: None,
            speed: None,
            terror_radius: None,
            speed_forms: Vec::new(),
            terror_forms: Vec::new(),
            gender: None,
            origin: None,
            actor: None,
            power: None,
            lore: None,
            icon: None,
        }
    }

    #[test]
    fn returns_top_four_owned_perks() {
        let perks = vec![
            perk("a", "K01", r#"["AreaControl","Slowing"]"#),
            perk("b", "K01", r#"["TerrorRadius"]"#),
            perk("c", "K01", r#"["Traps"]"#),
            perk("d", "K01", r#"["Haste"]"#),
            perk("e", "K01", r#"["General"]"#),
            perk("other", "K02", r#"["AreaControl"]"#),
        ];
        let recs = Recommender::recommend(&trapper(), &perks, "控场压制");
        assert_eq!(recs.len(), 4);
        assert!(recs.iter().all(|r| r.perk_id != "other"));
        for w in recs.windows(2) {
            assert!(w[0].score >= w[1].score);
        }
    }

    #[test]
    fn fills_with_universal_when_no_matching() {
        let perks = vec![
            perk("a", "K01", r#"["Nonexistent"]"#),
            perk("u1", "S00", r#"["General"]"#),
            perk("u2", "S00", r#"["General"]"#),
        ];
        let recs = Recommender::recommend(&trapper(), &perks, "信息/侦查");
        // no owned match, so filled from universal perks
        assert_eq!(recs.len(), 2);
        assert!(recs.iter().all(|r| r.perk_id.starts_with('u')));
    }

    #[test]
    fn completely_empty_input_returns_nothing() {
        let perks = vec![perk("a", "K01", r#"["Nonexistent"]"#)];
        let recs = Recommender::recommend(&trapper(), &perks, "信息/侦查");
        assert!(recs.is_empty());
    }

    #[test]
    fn highest_weighted_tag_wins() {
        let perks = vec![
            perk("info", "K01", r#"["Auras"]"#),
            perk("speed", "K01", r#"["MovementSpeed"]"#),
        ];
        let recs = Recommender::recommend(&trapper(), &perks, "追逐击倒");
        assert_eq!(recs[0].perk_id, "speed");
    }
}