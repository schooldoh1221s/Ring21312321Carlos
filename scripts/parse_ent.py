import re, json, html, os, sys

# Resolve input path: use first CLI arg or search common temp locations
candidates = [
    sys.argv[1] if len(sys.argv) > 1 else None,
    '/tmp/aft-ent.html',
    os.path.join(os.environ.get('TEMP', ''), 'aft-ent.html'),
    os.path.join(os.environ.get('TMP', ''), 'aft-ent.html'),
]
src_path = next((p for p in candidates if p and os.path.isfile(p)), None)
if not src_path:
    print('ERROR: aft-ent.html not found; pass path as argv[1]')
    sys.exit(1)

src = open(src_path, encoding='utf-8', errors='ignore').read()
src = html.unescape(src)

start = src.find('[{"type":"TV Shows"')
if start < 0:
    start = src.find('[{"type":"Movies"')
if start < 0:
    start = src.find('[{"type":"Music"')
print('start:', start)

if start < 0:
    print('No media JSON found in source')
    sys.exit(1)

# Walk backwards to find the true array start (the found '[' may be nested)
# Google Sites wraps the blob inside a larger JS string; the real array begins
# at the first '[' that is preceded by ':' or ',' or whitespace outside strings.
# Simpler heuristic: find the LAST occurrence of '[{"type"' before start and use that.
all_starts = [m.start() for m in re.finditer(re.escape('[{"type":"'), src)]
if all_starts:
    # use the earliest start that is <= current start
    earlier = [s for s in all_starts if s <= start]
    if earlier:
        start = earlier[0]
        print('adjusted start:', start)

depth = 0
end = None
in_str = False
esc = False
BS = chr(92)
limit = min(start + 3_000_000, len(src))
for i in range(start, limit):
    c = src[i]
    if in_str:
        if esc:
            esc = False
        elif c == BS:
            esc = True
        elif c == '"':
            in_str = False
    else:
        if c == '"':
            in_str = True
        elif c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break

print('end:', end)
if end is None:
    print('ERROR: unbalanced JSON, no end found')
    sys.exit(1)

blob = src[start:end]
print('blob length:', len(blob))

try:
    data = json.loads(blob)
except Exception as ex:
    print('parse failed:', ex)
    print(repr(blob[:200]))
    sys.exit(1)

print('parsed sections:', len(data))
for e in data:
    print(' ', e.get('type'), '|', e.get('name'), '| items:', len(e.get('movies', [])))

out_path = os.path.join(os.path.dirname(src_path), 'aft-ent.json')
open(out_path, 'w', encoding='utf-8').write(json.dumps(data, indent=1))
print('saved', out_path)
