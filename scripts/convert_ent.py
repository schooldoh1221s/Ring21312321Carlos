import json, os, sys

# Convert Afterspace entertainment JSON into a clean catalog for Shadow Garden
src = sys.argv[1] if len(sys.argv) > 1 else '/tmp/aft-ent.json'
if not os.path.isfile(src):
    src = os.path.join(os.environ.get('TEMP', os.environ.get('TMP', '')), 'aft-ent.json')
if not os.path.isfile(src):
    print('ERROR: aft-ent.json not found')
    sys.exit(1)

data = json.load(open(src, encoding='utf-8'))

out = {"sections": []}
for section in data:
    stype = section.get('type', '')
    sname = section.get('name', '')
    slug = section.get('slug', '')
    items = []
    for item in section.get('movies', []):
        entry = {
            "title": item.get('title', ''),
            "artist": item.get('artist', ''),
            "url": item.get('url', ''),
            "fileId": item.get('fileId'),
            "folderId": item.get('folderId'),
        }
        items.append(entry)
    out["sections"].append({
        "type": stype,
        "name": sname,
        "slug": slug,
        "items": items,
    })

total = sum(len(s['items']) for s in out['sections'])
print(f"sections: {len(out['sections'])}, total items: {total}")

out_path = os.path.join(os.path.dirname(src), 'entertainment_catalog.json')
open(out_path, 'w', encoding='utf-8').write(json.dumps(out, indent=1, ensure_ascii=False))
print('saved', out_path)
