# 黎明杀机（DBD）中文 Wiki + 助手 · 项目计划

> 目标：一个**真正可用的中文 DBD 资料站** + 一个**独立桌面助手软件**
> 定位：免费、开源、兴趣项目（不做商业化）
> 数据源：官方 wiki.gg API（已验证可抓取，结构化模板）

---

## 一、为什么做（机会验证）

| 现状 | 事实 |
|---|---|
| 官方 wiki.gg | 完整但**无中文**（只有德/法/西/意/波） |
| BWIKI 中文站 | **半废弃**：首页还是"施工中"占位符、角色页大量重复占位图、仅5名编辑 |
| Fandom 中文 | 内容量小、靠翻译 |
| **中文区结论** | **没有完整、活跃、权威的中文 wiki** ← 真实缺口 |

**数据源已验证**：wiki.gg 的 MediaWiki API 可抓到**结构化模板**（`#Invoke:Loadout` / `#Invoke:Killers`），角色/技能/数值全在里面，比纯文本好解析。

---

## 二、整体架构

```
┌─────────────────────────────────────┐
│   数据管道（自动，每周同步）          │
│   爬 wiki.gg API → 解析 Lua 模板      │
│   → 中文 SQLite 数据库（单一数据源）   │
└──────────┬──────────────────────────┘
           │
   ┌───────┴────────┐
   │   中文 Wiki     │      │  DBD 助手软件        │
   │   （静态网页）   │      │  （Tauri 桌面应用）   │
   │  读同一数据库    │      │  读同一数据库        │
   └────────────────┘      └──────────────────────┘
```

**关键优势**：你**不需要手动写 wiki 内容**。爬虫把官方数据自动变成中文库，wiki 和助手软件共用一份数据。工作量集中在「翻译 + 界面 + 助手逻辑」。

---

## 三、项目结构（单仓库）

```
dbd-cn/
├── crawler/                  # 数据管道
│   ├── fetch_wiki.py         # 抓 wiki.gg API（角色/技能/附加品/地图）
│   ├── parse_templates.py    # 解析 #Invoke Lua 模板 → 结构化字段
│   ├── translate.py          # 中文翻译（词典 + 人工校对）
│   ├── build_db.py           # 生成 SQLite
│   └── sync.py               # 每周增量同步
├── wiki/                     # 中文 Wiki（静态站）
│   ├── src/                  # 页面生成（角色/技能/附加品/地图/构筑）
│   ├── templates/            # 页面模板
│   └── generate.py           # 从数据库生成 HTML 页面
├── assistant/                # DBD 助手软件（Tauri 桌面应用）
│   ├── src-tauri/            # Rust 后端
│   │   ├── recommender.rs    # 构筑推荐引擎
│   │   ├── search.rs         # 技能/角色检索
│   │   ├── maps.rs           # 地图/捆钩点
│   │   └── db.rs             # SQLite 读取
│   └── src/                  # 前端（Vue/React）
│       ├── views/Build.vue   # 构筑推荐
│       ├── views/Perks.vue   # 技能图鉴
│       ├── views/Roster.vue  # 角色图鉴
│       └── views/Maps.vue    # 地图查询
├── data/                     # SQLite + 缓存
├── tests/
├── README.md
└── pyproject.toml
```

---

## 四、数据库设计（核心数据模型）

```sql
-- 角色（杀手/逃生者）
CREATE TABLE characters (
    id TEXT PRIMARY KEY,        -- 'K01_TheTrapper' / 'S01_DwightFairfield'
    name_en TEXT,               -- 'The Trapper'
    name_zh TEXT,               -- '设陷者'
    role TEXT,                  -- 'killer' / 'survivor'
    difficulty TEXT,
    lore TEXT,                  -- 背景故事（中文）
    power TEXT,                 -- 能力/力量（中文）
    icon TEXT                   -- 图标路径
);

-- 技能
CREATE TABLE perks (
    id TEXT PRIMARY KEY,        -- 'barbecueAndChilli'
    name_en TEXT,
    name_zh TEXT,
    owner TEXT,                 -- 所属角色
    role TEXT,                  -- killer/survivor/通用
    tiers TEXT,                 -- 三档数值（JSON）
    description TEXT,           -- 中文描述
    icon TEXT
);

-- 附加品
CREATE TABLE addons (
    id TEXT PRIMARY KEY,
    name_en TEXT, name_zh TEXT,
    owner TEXT,
    rarity TEXT,                -- 常见/罕见/稀有/...
    effect TEXT,                -- 效果（中文）
    icon TEXT
);

-- 地图/领域
CREATE TABLE maps (
    id TEXT PRIMARY KEY,
    name_en TEXT, name_zh TEXT,
    realm TEXT,
    hooks TEXT,                 -- 捆钩点（JSON）
    totems TEXT                 -- 图腾点（JSON）
);

-- 构筑（社区/推荐）
CREATE TABLE builds (
    id INTEGER PRIMARY KEY,
    character TEXT,
    role TEXT,
    perks TEXT,                 -- 4技能 JSON
    addons TEXT,                -- 附加品 JSON
    playstyle TEXT,             -- 玩法（中文）
    rating REAL                 -- 社区评分
);

-- 翻译词表（增量）
CREATE TABLE translations (
    term TEXT PRIMARY KEY,
    zh TEXT
);
```

---

## 五、功能规划

### A. 中文 Wiki（网页）
| 页面 | 内容 |
|---|---|
| 首页 | 最新版本、更新日志、角色导航 |
| 角色页 | 44杀手 + 44逃生者：背景/能力/技能/附加品 |
| 技能页 | 全部技能：中文描述/三档数值/所属 |
| 附加品页 | 中文效果/稀有度 |
| 地图页 | 领域/地图/捆钩点/图腾点 |
| 构筑页 | 社区构筑推荐（中文） |
| 更新日志 | 版本变更（从 wiki History tab） |

### B. DBD 助手软件（Tauri 桌面应用）
| 界面 | 功能 |
|---|---|
| **构筑推荐** | ★ 输入角色/玩法 → 推荐技能组合（杀手/逃生者分类） |
| **技能图鉴** | 中文搜索技能（效果/三档数值/所属角色） |
| **角色图鉴** | 杀手 + 逃生者：背景/能力/附加品 |
| **附加品** | 中文效果/稀有度/所属 |
| **地图查询** | 领域/地图/捆钩点/图腾点 |
| **版本更新** | 版本变更速览（联机检查） |

**软件形态**：Tauri 桌面应用（Rust + Vue），Windows/macOS/macOS，单exe 分发，离线可用（本地 SQLite），数据随 wiki 同步更新。

---

## 六、里程碑

| 阶段 | 周期 | 交付 |
|---|---|---|
| **M1 数据管道** | 1-2周 | 爬虫抓全部角色/技能/附加品 → SQLite；翻译框架 |
| **M2 中文 Wiki** | 2周 | 静态站生成：角色/技能/附加品/地图页 |
| **M3 DBD 助手软件** | 2-3周 | Tauri 桌面应用：构筑推荐/技能图鉴/角色图鉴 |
| **M4 打磨** | 持续 | 地图查询、版本更新、同步脚本、SEO、发布 |

---

## 七、技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| 爬虫 | Python + requests + lxml | wiki.gg API 是标准 MediaWiki |
| 解析 | 正则 + 模板语法分析 | `#Invoke:` 模板是半结构化 |
| 存储 | SQLite | 单文件，够用 |
| Wiki 站 | 静态生成（Jinja2 模板 → HTML） | 免服务器，GitHub Pages 托管 |
| **助手软件** | **Tauri（Rust + Vue/React）** | 单exe、体积小、跨平台、你熟 |
| 翻译 | 词典 + 人工校对 | AI 辅助翻译 + 人工审校 |

---

## 八、风险与对策

| 风险 | 对策 |
|---|---|
| wiki.gg 改版/模板变化 | 解析层做容错，weekly sync 试跑 |
| 翻译工作量大 | AI 批量翻译 + 词典 + 只翻译核心字段 |
| 维护成本（每周更新） | 全自动化管道，个人可扛 |
| 版权/商标 | 非官方站 + 注明数据来源 wiki.gg |
| 中文社区冷启动 | B站/贴吧发布，SEO 中文关键词（黎明杀机 wiki） |

---

## 九、最终形态

```
GitHub: dbd-cn（开源）
├── 中文 Wiki 线上站（GitHub Pages 免费托管）
├── DBD 助手桌面软件（Tauri，单exe，离线可用）
└── 数据管道（每周自动更新）
```

**一句话**：不手动写 wiki，用爬虫把官方数据变成中文库，wiki 和桌面助手软件共用一份数据——个人完全扛得住，填补中文 DBD 资料真空。

---

需要我调整哪部分？（比如：先做助手还是先做wiki？构筑推荐的具体逻辑？软件界面风格？）
