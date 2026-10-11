import os, re, sqlite3

print('=== A. CI 是否跑测试（质量门）===')
wf = open('.github/workflows/weekly-sync.yml', encoding='utf-8').read()
for kw in ['pytest', 'cargo test', 'npm run build', 'npm ci', 'lint']:
    print('  {:14s}: {}'.format(kw, 'YES' if kw in wf else 'NO'))

print()
print('=== B. Tauri 写库路径是否只读（macOS/Program Files）===')
db = open('assistant/src-tauri/src/db.rs', encoding='utf-8').read()
print('  Db::open 优先 resource_dir:', 'resourceDir' in db or 'resource_dir' in db)
print('  -> 打包后资源目录在 macOS /Applications 与 Windows Program Files 下只读，')
print('     save_build/delete_build 会失败')

print()
print('=== C. 助手搜索性能：每次调用全量读库 ===')
s = open('assistant/src-tauri/src/lib.rs', encoding='utf-8').read()
m = re.search(r'fn search_all.*?\{(.*?)\n\}', s, re.S)
body = m.group(1) if m else ''
calls = len(re.findall(r'\.list_\w+\(\)', body))
print('  search_all 每次请求的 list_* 调用数:', calls, '(每次全量加载 98+336+981+46+21 行)')

print()
print('=== D. 搜索索引正文截断导致漏搜 ===')
gen = open('wiki/generate.py', encoding='utf-8').read()
m = re.search(r'def _body\(.*?cap: int = (\d+)', gen, re.S)
print('  _body 截断上限:', m.group(1) if m else '?')
idx = open('site/static/search-index.json', encoding='utf-8').read()
print('  索引总长 KB:', round(len(idx.encode())/1024))

print()
print('=== E. README 与实际数据是否一致 ===')
rd = open('README.md', encoding='utf-8').read()
conn = sqlite3.connect('data/dbd_cn.db')
sur = conn.execute("SELECT COUNT(*) FROM characters WHERE role='survivor'").fetchone()[0]
print('  实际逃生者数:', sur, '| README 提及 44 逃生者:', '44 逃生者' in rd)

print()
print('=== F. 站点缺 404 页 / 助手缺关于页 ===')
print('  site/404.html:', os.path.exists('site/404.html'))
print('  助手 views:', sorted(os.listdir('assistant/src/views')))

print()
print('=== G. 密钥落盘 ===')
print('  .env 存在:', os.path.exists('.env'), '| gitignore 覆盖:',
      '.env' in open('.gitignore', encoding='utf-8').read())
tracked = os.popen('cd D:/project/DBDwiki && git ls-files | findstr ".env"').read().strip()
print('  git 已跟踪的 .env*:', tracked or '(仅 .env.example)')

print()
print('=== H. 附加品无详情页（wiki）===')
print('  site/addon/ 目录:', os.path.isdir('site/addon'))