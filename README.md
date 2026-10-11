# dbd-cn · 黎明杀机（DBD）中文 Wiki + 助手

> 免费 · 开源 · 兴趣项目 · 非官方
> 一个真正可用的中文 DBD 资料站 + 一个独立桌面助手软件。

**核心理念**：不手动写 wiki。用爬虫把官方 wiki.gg 的结构化数据自动变成中文 SQLite 数据库，中文 Wiki（静态站）和桌面助手（Tauri 应用）共用同一份数据。

---

## 架构

```
┌─────────────────────────────────────┐
│   数据管道（自动，每周同步）           │
│   爬 wiki.gg Module:Datatable        │
│   → 解析 Lua 数据表 → 中文 SQLite      │
└──────────┬──────────────────────────┘
           │
   ┌───────┴────────┐
   │   中文 Wiki     │      │  DBD 助手软件        │
   │  （静态网页）    │      │  （Tauri 桌面应用）  │
   │  读同一数据库    │      │  读同一数据库        │
   └────────────────┘      └──────────────────────┘
```

数据源已验证：wiki.gg 把角色/技能/附加品/地图的数据以结构化 Lua 数据表存在
`Module:Datatable` 与 `Module:Datatable/Loadout` 中，数值比纯文本好解析得多。

## 项目结构

```
dbd-cn/
├── crawler/                  # 数据管道（Python）
│   ├── api.py                # wiki.gg MediaWiki API 客户端（User-Agent / 限流 / 重试 / 重定向）
│   ├── lua_parser.py         # Lua 数据表解析器（半结构化 #Invoke 数据）
│   ├── html_extract.py       # 渲染页内容抽取（技能描述 / 背景故事 / 附加品效果 / 补丁说明）
│   ├── enrich.py             # 长文内容补全（描述 / 背景 / 效果 / 补丁 notes）
│   ├── translate.py          # 中文词典 + 结构化词表
│   ├── review_queue.py       # 翻译校对队列（词典 + 人工校对）
│   ├── db.py                 # SQLite schema + 迁移
│   ├── pipeline.py           # 抓取 → 解析 → 归一化 → 写入
│   ├── dictionaries/         # 词典 JSON（perks / addons / maps / landmarks…）
│   ├── cli.py                # dbd-crawl 入口（--full 补全内容）
│   └── sync.py               # 每周增量同步入口
├── wiki/                     # 中文 Wiki（静态站生成，Python + Jinja2）
│   ├── generate.py           # 从数据库生成 HTML + sitemap + robots（含 SEO meta）
│   ├── templates/            # 页面模板
│   └── static/               # CSS
├── assistant/                # DBD 助手（Tauri 桌面应用）
│   ├── src/                  # 前端（Vue 3 + Vite）
│   │   ├── views/            # Build / Perks / Roster / Maps / Changelog
│   │   └── App.vue
│   └── src-tauri/            # Rust 后端
│       ├── src/
│       │   ├── db.rs         # SQLite 读取
│       │   ├── search.rs     # 中英文检索
│       │   ├── recommender.rs# 构筑推荐引擎
│       │   ├── maps.rs       # 地图/领域查询
│       │   └── lib.rs        # Tauri 命令入口
│       ├── Cargo.toml
│       └── tauri.conf.json
├── data/                     # SQLite + 缓存
├── tests/                    # Python 单元测试
├── scripts/                  # 辅助脚本（每周同步任务等）
├── .github/workflows/        # GitHub Actions：每周自动同步 + 部署 Pages
├── LICENSE
├── pyproject.toml
└── README.md
```

## 数据库设计（SQLite，单一数据源）

| 表 | 内容 |
|---|---|
| `characters` | 杀手/逃生者：中英文名、难度、移速、恐惧范围、**背景故事、能力**、领域… |
| `perks` | 技能：中英文名、所属角色、三档数值、单位、标签、**中文描述** |
| `addons` | 附加品：中英文名、所属、稀有度、标签、**中文效果** |
| `maps` / `realms` | 地图与领域：钩点/图腾点、版本变化、领域归属 |
| `patches` | 版本补丁：补丁号、日期、PTB 标记、**变更说明** |
| `builds` | 社区/推荐构筑：技能组合、玩法、评分、来源 |
| `translations` | 翻译词表（增量，人工校对标记） |
| `sync_meta` | 同步元信息（最近同步时间、数据源） |

## 快速开始

### 1. 数据管道（生成中文数据库）

```bash
pip install -e .
# 抓取全部角色/技能/附加品/地图 → data/dbd_cn.db
python -m crawler.cli --db data/dbd_cn.db
# 追加抓取长文内容（技能描述/背景故事/附加品效果/补丁说明）→ 需几分钟
python -m crawler.cli --full --db data/dbd_cn.db
# 或：每周同步入口（只更新数值数据）
python -m crawler.sync --db data/dbd_cn.db
```

产出（本项目实测）：
- 数值数据：`98 角色 / 336 技能 / 981 附加品 / 46 地图 / 21 领域 / 398 补丁`
- 长文内容：`336 技能描述 / 98 背景故事 / 44 杀手能力 / 981 附加品效果 / 307 补丁说明`（均已翻译为中文；307 为 wiki.gg 上有补丁页的数量，其余 91 条早期补丁无对应页面）
- 图标：`98 角色立绘 / 335 技能图标 / 963 附加品图标`（约 1400 张，存于 `data/icons/`）

### 2. LLM 长文本翻译（技能描述 / 背景故事 / 附加品效果）

`--full` 抓回的长文本是英文；用 LLM 批量翻译成中文：

```bash
# 1) 配置 API（写入 .env，已被 gitignore，绝不入库）
cp .env.example .env   # 或手动创建 .env

# 2) 翻译 + 检查断点续传（已翻译行自动跳过）
python -m crawler.cli --translate --db data/dbd_cn.db
```

`.env` 字段：

```
LLM_BASE_URL=https://api.inferaiapi.com/v1
LLM_API_KEY=sk-xxxxxxxx
LLM_MODEL=deepseek-v4-pro
```

实现要点（`crawler/llm.py`）：
- 术语记忆词表在 System Prompt 中（设陷者/幽灵/逃生者等），保证术语一致
- 批量翻译接口（多条文本一次请求）+ 并发 + 429/5xx 指数退避重试 + 多轮自动续跑
- 检查点：逐条落库，中断后重跑只补剩余

### 3. 抓取图标（角色立绘 / 技能 / 附加品）

```bash
python -m crawler.cli --icons --db data/dbd_cn.db
# 或单独补抓/补漏
python -c "from crawler.icons import fetch_icons; print(fetch_icons())"
```

策略：按命名规则批量生成候选文件名（`IconPerks_*` / `IconAddon_*` /
`T_UI_iconAddon_*` / `K01_TheTrapper_Portrait.png` 等），用 MediaWiki
imageinfo 批量校验存在性并获取真实下载 URL，未命中者从渲染页面提取兜底。
部分未实装/已下架条目（如 Overconfidence）在官方 wiki 上即无图标，暂无匹配。

> ⚠️ 图标版权：角色立绘与图标素材来自《Dead by Daylight》游戏本体或其发行商
> 所有的关联网站，版权归发行商与开发者所有。本项目为非商业粉丝项目，站点
> 页脚与助手界面均保留该版权标注，不建议将素材用于任何商业用途。

### 4. 翻译校对队列（词典 + 人工校对）

```bash
# 导出仍为英文的词条，用表格工具填中文
python -m crawler.review_queue --db data/dbd_cn.db --dump data/review_queue.tsv
# 填好后合并回数据库
python -m crawler.review_queue --db data/dbd_cn.db --import data/review_queue.tsv
# 重新构建即生效
python -m crawler.cli --db data/dbd_cn.db
```

词典文件位于 `crawler/dictionaries/*_zh.json`（`perks` / `addons` / `maps`），
增补条目后重新构建即可。

### 5. 生成静态中文 Wiki

```bash
python -m wiki.generate --db data/dbd_cn.db --out site
# 附带 SEO（每页 meta 描述/keywords、sitemap.xml、robots.txt）
python -m wiki.generate --db data/dbd_cn.db --out site --sitemap
# 产出 site/，可部署到 GitHub Pages / 任意静态托管
```

产出：`1438 个 HTML 页面`（首页、杀手/逃生者图鉴【角色立绘】、角色详情【中文背景/能力】、技能【中文描述+图标】、技能详情、附加品【中文效果+图标】、附加品详情、地图【钩点/图腾点】、更新日志【补丁说明】、构筑、站内搜索）+ sitemap + robots，页脚含版权标注。

### 6. 构建桌面助手（Tauri）

```bash
cd assistant
npm install
# 开发模式
npm run tauri dev
# 打包（单 exe）
npm run tauri build
```

助手功能：构筑推荐（角色 + 玩法 → 技能组合，自动补齐通用技能）、我的构筑（保存/删除）、技能图鉴（中文搜索/效果类型筛选/中文描述/三档数值/图标）、角色图鉴（立绘/中文背景/能力）、附加品、地图查询（钩点/图腾点）、版本更新速览（离线检查本地库）。图标随应用打包，离线可用。

## 自动同步与部署

`.github/workflows/weekly-sync.yml` 每周一自动执行：

1. 抓取 wiki.gg 数据 → 更新 `data/dbd_cn.db`
2. 补抓图标（仅补缺失）
3. LLM 翻译长文本（需在仓库 Secrets 配置 `LLM_API_KEY`，可选）
4. 生成静态站 `site/`（含 sitemap + robots）
5. 提交数据变更
6. 用 `peaceiris/actions-gh-pages` 部署到 `gh-pages` 分支

首次使用需在 GitHub 仓库启用 **Settings → Pages → Deploy from branch: gh-pages**。

如需自动翻译，在仓库配置：
- **Secrets**：`LLM_API_KEY`（LLM 翻译密钥，不配置则跳过翻译步骤）
- **Variables**（可选）：`LLM_BASE_URL`、`LLM_MODEL`（有默认值）

> ⚠️ `.env` 含密钥，已被 `.gitignore` 忽略；仓库只提交 `.env.example` 模板。

## 测试

```bash
# Python 爬虫 / 解析 / 翻译 / 校对队列 / HTML 抽取 测试（31 项）
python -m pytest tests -q

# Rust 构筑推荐引擎测试（4 项）
cd assistant/src-tauri && cargo test
```

## 里程碑

| 阶段 | 状态 | 交付 |
|---|---|---|
| **M1 数据管道** | ✅ | 爬虫抓全部角色/技能/附加品/地图/补丁 → SQLite；翻译词典 + 校对队列 |
| **M2 中文 Wiki** | ✅ | 静态站：角色【背景/能力】/技能【描述】/附加品【效果】/地图【钩点图腾】/更新日志/构筑，SEO 完备 |
| **M3 DBD 助手** | ✅ | Tauri 桌面应用：构筑推荐/技能图鉴/角色图鉴/地图/版本更新（含描述/背景/效果展示） |
| **M4 打磨** | ✅ | 钩点图腾点、版本更新、长文内容补全、SEO、LICENSE、GitHub Actions 每周自动同步+部署 |

## 版权与免责

- 本项目为**非官方**粉丝兴趣项目，与 Behaviour Interactive / BHVR 无任何关联。
- 游戏数据来源于公开的 [deadbydaylight.wiki.gg](https://deadbydaylight.wiki.gg)，
  版权归原作者所有；本站仅做中文整理与工具化呈现，并注明来源。
- 《Dead by Daylight》为 Behaviour Interactive 的商标。

## 许可

MIT（代码部分，见 LICENSE）。游戏数据版权归原作者。