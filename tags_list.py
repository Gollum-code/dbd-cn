import json
import sqlite3
from collections import Counter

conn = sqlite3.connect('data/dbd_cn.db')
for tbl in ['addons', 'perks']:
    tags = Counter()
    for (raw,) in conn.execute(f"SELECT tags FROM {tbl} WHERE tags IS NOT NULL AND tags!=''"):
        try:
            for t in json.loads(raw):
                tags[t] += 1
        except Exception:
            pass
    print(f'=== {tbl} tags（{len(tags)} 种，共 {sum(tags.values())} 次）===')
    for t, n in tags.most_common(50):
        print(f'  {t:28s} {n}')
    print()
