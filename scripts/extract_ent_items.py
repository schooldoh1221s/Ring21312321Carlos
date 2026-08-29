import re, json, html, os, sys

src_path = '/tmp/aft-ent.html'
if not os.path.isfile(src_path):
    src_path = os.path.join(os.environ.get('TEMP', os.environ.get('TMP','')), 'aft-ent.html')
if not os.path.isfile(src_path):
    print('ERROR: source file not found')
    sys.exit(1)

src = open(src_path, encoding='utf-8', errors='ignore').read()
src = html.unescape(src)

# Extract all title+url pairs from the entertainment page
pattern = r'"title":"([^"]+)"[^}]*?"url":"(https://drive\.google\.com/[^"]+)"'
matches = re.findall(pattern, src)

items = []
for title, url in matches:
    title = title.strip()
    if title and url:
        items.append({'title': title, 'url': url})

print(f'Extracted {len(items)} items')
for item in items[:10]:
    print(f'  {item["title"]} -> {item["url"]}')

out = os.path.join(os.path.dirname(src_path), 'aft_items.json')
open(out, 'w', encoding='utf-8').write(json.dumps(items, indent=1))
print('saved', out)
