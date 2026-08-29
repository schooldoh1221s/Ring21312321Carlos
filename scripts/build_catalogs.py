import re, json, html, os, sys

"""Build clean catalogs from Afterspace HTML pages.
Outputs (project root):
  - afterspace_games_catalog.json  : [{name, category, url}, ...] deduped
  - entertainment_catalog.json     : [{type, name, items:[{title,url,artist}]}, ...]
"""

def find_src(name):
    cands = [name, os.path.join('/tmp', name), os.path.join(os.environ.get('TEMP',''), name), os.path.join(os.environ.get('TMP',''), name)]
    for p in cands:
        if p and os.path.isfile(p):
            return p
    return None

def balanced_json(src, start):
    depth = 0; in_str = False; esc = False; BS = chr(92)
    for i in range(start, min(start + 5_000_000, len(src))):
        c = src[i]
        if in_str:
            if esc: esc = False
            elif c == BS: esc = True
            elif c == '"': in_str = False
        else:
            if c == '"': in_str = True
            elif c == '[': depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0: return i + 1
    return -1

# ---------- GAMES ----------
games_src_path = find_src('aft-games.html')
if not games_src_path:
    print('ERROR: aft-games.html not found'); sys.exit(1)
gsrc = html.unescape(open(games_src_path, encoding='utf-8', errors='ignore').read())

# Each game entry: "name":"X","category":"Y",...,"url":"https://afterspace-cadear.web.app/titles/....html"
pat = re.compile(r'"name":"([^"]+)","category":"([^"]+)"[^{}]*?"url":"(https://afterspace-cadear\.web\.app/titles/[^"]+)"')
raw = pat.findall(gsrc)
print(f'raw game matches: {len(raw)}')

def norm(t):
    return re.sub(r'[^\w]+', '', str(t).lower(), flags=re.UNICODE)

seen = set()
games = []
for name, cat, url in raw:
    key = norm(name)
    if not key or key in seen:
        continue
    seen.add(key)
    games.append({'name': name, 'category': cat, 'url': url})
print(f'unique games: {len(games)}')

with open('afterspace_games_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(games, f, ensure_ascii=False, indent=1)
print('saved afterspace_games_catalog.json')

# ---------- ENTERTAINMENT ----------
ent_src_path = find_src('aft-ent.html')
if not ent_src_path:
    print('ERROR: aft-ent.html not found'); sys.exit(1)
esrc = html.unescape(open(ent_src_path, encoding='utf-8', errors='ignore').read())

start = esrc.find('[{"type":"TV Shows"')
if start < 0: start = esrc.find('[{"type":"Movies"')
if start < 0: start = esrc.find('[{"type":"Music"')
if start < 0:
    print('ERROR: entertainment JSON not found'); sys.exit(1)

end = balanced_json(esrc, start)
blob = esrc[start:end]
data = json.loads(blob)

out = []
ent_seen = set()
total = 0
for section in data:
    stype = section.get('type', '')
    sname = section.get('name', '')
    items = []
    for item in section.get('movies', []):
        title = (item.get('title') or '').strip()
        url = item.get('url') or ''
        if not title or not url: continue
        key = norm(title) + '|' + url
        if key in ent_seen: continue
        ent_seen.add(key)
        entry = {'title': title, 'url': url}
        if item.get('artist'): entry['artist'] = item['artist']
        items.append(entry)
    if items:
        out.append({'type': stype, 'name': sname, 'items': items})
        total += len(items)

print(f'entertainment sections: {len(out)}, items: {total}')
with open('entertainment_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print('saved entertainment_catalog.json')

# ---------- SUMMARY ----------
cats = {}
for g in games:
    cats[g['category']] = cats.get(g['category'], 0) + 1
print('\nGame categories:')
for c, n in sorted(cats.items(), key=lambda x: -x[1]):
    print(f'  {c}: {n}')
