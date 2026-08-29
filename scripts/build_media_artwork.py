import json
import os
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT = 'entertainment_catalog.json'
OUTPUT = 'media_artwork.json'
USER_AGENT = 'ShadowGardenArtworkIndexer/1.0 (local project)'


def normalize(value):
    value = str(value or '').lower().replace('&', ' and ')
    value = re.sub(r'[^a-z0-9]+', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def tokens(value):
    return set(normalize(value).split())


def score_match(wanted, candidate):
    wanted_tokens = tokens(wanted)
    candidate_tokens = tokens(candidate)
    if not wanted_tokens:
        return 0
    return len(wanted_tokens & candidate_tokens) / len(wanted_tokens)


def drive_thumbnail(url):
    patterns = [r'/file/d/([^/]+)', r'/file/u/\d+/d/([^/]+)', r'[?&]id=([^&]+)']
    for pattern in patterns:
        match = re.search(pattern, url or '', re.I)
        if match:
            return f'https://drive.google.com/thumbnail?id={urllib.parse.quote(match.group(1))}&sz=w300-h450'
    return ''


def request_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))


def wikipedia_candidate(item):
    title = item['title'].strip()
    kind = item.get('type', '')
    terms = [title]
    if kind == 'Movies': terms = [f'{title} film', title]
    elif kind == 'TV Shows': terms = [f'{title} television series', f'{title} TV series', title]
    elif kind == 'Music': terms = [f'{title} album', f'{title} song', title]
    elif kind == 'Manga': terms = [f'{title} manga', f'{title} anime', title]

    for term in terms:
        query = urllib.parse.urlencode({'action': 'query', 'list': 'search', 'srsearch': term, 'srlimit': '5', 'srnamespace': '0', 'format': 'json', 'utf8': '1'})
        try:
            hits = request_json('https://en.wikipedia.org/w/api.php?' + query).get('query', {}).get('search', [])
        except Exception:
            continue
        for hit in hits:
            page_title = hit.get('title', '')
            score = score_match(title, page_title)
            if score < 0.9:
                continue
            try:
                summary = request_json('https://en.wikipedia.org/api/rest_v1/page/summary/' + urllib.parse.quote(page_title.replace(' ', '_')))
            except Exception:
                continue
            thumb = (summary.get('thumbnail') or {}).get('source', '')
            if thumb:
                return {'image': thumb, 'source': 'Wikimedia', 'matchedTitle': summary.get('title', page_title), 'confidence': round(score, 2)}
    return None


def deezer_candidate(item):
    if item.get('type') != 'Music':
        return None
    term = item['title'] + ((' ' + item.get('artist', '')) if item.get('artist') else '')
    query = urllib.parse.urlencode({'q': term, 'limit': '8'})
    try:
        results = request_json('https://api.deezer.com/search/album?' + query).get('data', [])
    except Exception:
        return None
    for result in results:
        candidate = result.get('title', '')
        score = score_match(item['title'], candidate)
        if score >= 0.9:
            image = result.get('cover_big') or result.get('cover_medium') or result.get('cover')
            if image:
                return {'image': image, 'source': 'Deezer artwork', 'matchedTitle': candidate, 'confidence': round(score, 2)}
    return None


def itunes_candidate(item, entity):
    term = item['title'] + ((' ' + item.get('artist', '')) if item.get('artist') else '')
    query = urllib.parse.urlencode({'term': term, 'entity': entity, 'limit': '8'})
    try:
        results = request_json('https://itunes.apple.com/search?' + query).get('results', [])
    except Exception:
        return None
    title = item['title']
    for result in results:
        candidates = [result.get('trackName', ''), result.get('collectionName', ''), result.get('artistName', '')]
        score = max((score_match(title, candidate) for candidate in candidates if candidate), default=0)
        if score >= 0.9:
            image = result.get('artworkUrl100', '').replace('100x100', '600x600')
            if image:
                matched = result.get('trackName') or result.get('collectionName') or result.get('artistName')
                return {'image': image, 'source': 'Apple artwork', 'matchedTitle': matched, 'confidence': round(score, 2)}
    return None


def tvmaze_candidate(item):
    query = urllib.parse.urlencode({'q': item['title']})
    try:
        results = request_json('https://api.tvmaze.com/search/shows?' + query)
    except Exception:
        return None
    for result in results[:8]:
        show = result.get('show') or {}
        score = score_match(item['title'], show.get('name', ''))
        image = (show.get('image') or {}).get('original') or (show.get('image') or {}).get('medium')
        if score >= 0.9 and image:
            return {'image': image, 'source': 'TVMaze', 'matchedTitle': show.get('name', ''), 'confidence': round(score, 2)}
    return None


def anilist_candidate(item):
    query = '''query($search:String!){Media(search:$search,type:ANIME){title{romaji english native} coverImage{extraLarge large medium}}}'''
    payload = json.dumps({'query': query, 'variables': {'search': item['title']}}).encode('utf-8')
    request = urllib.request.Request('https://graphql.anilist.co', data=payload, headers={'User-Agent': USER_AGENT, 'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            media = json.loads(response.read().decode('utf-8')).get('data', {}).get('Media') or {}
    except Exception:
        return None
    names = media.get('title') or {}
    score = max(score_match(item['title'], names.get(key, '')) for key in ('romaji', 'english', 'native'))
    image = (media.get('coverImage') or {}).get('extraLarge') or (media.get('coverImage') or {}).get('large') or (media.get('coverImage') or {}).get('medium')
    if score >= 0.9 and image:
        return {'image': image, 'source': 'AniList', 'matchedTitle': names.get('english') or names.get('romaji') or item['title'], 'confidence': round(score, 2)}
    return None


def openverse_candidate(item):
    # Only accept near-exact title matches with an explicit license.
    query = urllib.parse.urlencode({'q': item['title'], 'page_size': '10'})
    try:
        results = request_json('https://api.openverse.org/v1/images/?' + query).get('results', [])
    except Exception:
        return None
    for result in results:
        candidate = result.get('title') or ''
        score = score_match(item['title'], candidate)
        image = result.get('thumbnail') or result.get('url') or ''
        if score >= 1.0 and image and result.get('license'):
            return {'image': image, 'source': 'Openverse', 'matchedTitle': candidate, 'confidence': round(score, 2), 'license': result['license']}
    return None


def find_artwork(item):
    kind = item.get('type', '')
    # Prefer the actual Drive file thumbnail; it is the exact associated file.
    direct = drive_thumbnail(item.get('url', ''))
    if direct:
        return {'image': direct, 'source': 'Google Drive', 'matchedTitle': item['title'], 'confidence': 1.0}
    if kind == 'Music':
        found = deezer_candidate(item) or itunes_candidate(item, 'album') or wikipedia_candidate(item)
    elif kind == 'Movies':
        found = itunes_candidate(item, 'movie') or wikipedia_candidate(item)
    elif kind == 'TV Shows':
        found = tvmaze_candidate(item) or wikipedia_candidate(item)
    elif kind == 'Manga':
        found = anilist_candidate(item) or wikipedia_candidate(item)
    else:
        found = wikipedia_candidate(item) or openverse_candidate(item)
    return found


def main():
    if not os.path.isfile(INPUT):
        print(f'ERROR: missing {INPUT}'); sys.exit(1)
    sections = json.load(open(INPUT, encoding='utf-8'))
    jobs = []
    for section in sections:
        for item in section.get('items', []):
            job = dict(item)
            job['type'] = section.get('type', '')
            job['section'] = section.get('name', '')
            jobs.append(job)

    artwork = {}
    stats = {'drive': 0, 'wikimedia': 0, 'apple': 0, 'deezer': 0, 'tvmaze': 0, 'anilist': 0, 'openverse': 0, 'unmatched': 0, 'total': len(jobs)}

    def one(item):
        key = f"{item['type']}|{item['section']}|{item['title']}"
        return key, find_artwork(item)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(one, item) for item in jobs]
        for index, future in enumerate(as_completed(futures), 1):
            try:
                key, found = future.result()
                if found:
                    artwork[key] = found
                    source = found['source']
                    if source == 'Google Drive': stats['drive'] += 1
                    elif source == 'Wikimedia': stats['wikimedia'] += 1
                    elif source == 'Apple artwork': stats['apple'] += 1
                    elif source == 'Deezer artwork': stats['deezer'] += 1
                    elif source == 'TVMaze': stats['tvmaze'] += 1
                    elif source == 'AniList': stats['anilist'] += 1
                    else: stats['openverse'] += 1
                else:
                    stats['unmatched'] += 1
            except Exception:
                stats['unmatched'] += 1
            if index % 50 == 0: print(f'processed {index}/{len(futures)}')

    with open(OUTPUT, 'w', encoding='utf-8') as file:
        json.dump({'version': 4, 'generatedFrom': INPUT, 'stats': stats, 'items': artwork}, file, ensure_ascii=False, indent=1)
    print('saved', OUTPUT)
    print(json.dumps(stats))

if __name__ == '__main__':
    main()
