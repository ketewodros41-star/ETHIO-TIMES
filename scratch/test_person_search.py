import sys
sys.path.insert(0, '.')
import httpx
import urllib.parse
from app.schemas.social_post import PhotoCandidate

def search_person_photos(person_name: str) -> list[PhotoCandidate]:
    headers = {"User-Agent": "ETHIOTIMESBot/1.0 (editorial-studio@ethiotimes.org; contact: info@ethiotimes.com)"}
    candidates = []
    seen = set()

    # 1. Wikimedia Commons direct search for person
    c_url = (
        f"https://commons.wikimedia.org/w/api.php?action=query&generator=search"
        f"&gsrsearch={urllib.parse.quote(person_name + ' filetype:bitmap')}"
        f"&gsrnamespace=6&gsrlimit=12&prop=imageinfo&iiprop=url&iiurlwidth=1000&format=json"
    )
    try:
        with httpx.Client(timeout=8.0) as client:
            res = client.get(c_url, headers=headers)
            if res.status_code == 200:
                pages = res.json().get("query", {}).get("pages", {})
                for pid, p in pages.items():
                    ii = p.get("imageinfo", [{}])[0]
                    thumb = ii.get("thumburl") or ii.get("url")
                    orig = ii.get("url") or thumb
                    title = p.get("title", "").replace("File:", "").replace("_", " ")
                    if not thumb or thumb in seen:
                        continue
                    if any(x in thumb.lower() for x in [".svg", ".pdf", ".gif"]):
                        continue
                    seen.add(thumb)
                    candidates.append(PhotoCandidate(
                        id=f"commons-person-{pid}",
                        title=f"{person_name}: {title[:60]}",
                        thumb_url=thumb,
                        image_url=orig,
                        source="wikimedia",
                        photographer="Wikimedia Commons",
                        description=f"Press photo of {person_name}",
                    ))
    except Exception as e:
        print("Commons person search error:", e)

    # 2. Wikipedia pageimages for person
    w_url = (
        f"https://en.wikipedia.org/w/api.php?action=query&generator=search"
        f"&gsrsearch={urllib.parse.quote(person_name)}"
        f"&gsrlimit=8&prop=pageimages|extracts&pithumbsize=1000&exintro=1&explaintext=1&format=json"
    )
    try:
        with httpx.Client(timeout=8.0) as client:
            res = client.get(w_url, headers=headers)
            if res.status_code == 200:
                pages = res.json().get("query", {}).get("pages", {})
                for pid, p in pages.items():
                    thumb = p.get("thumbnail", {}).get("source")
                    title = p.get("title", "")
                    if not thumb or thumb in seen:
                        continue
                    if any(x in thumb.lower() for x in [".svg", ".pdf", ".gif", "emblem", "flag"]):
                        continue
                    # Ensure title is relevant to person
                    if any(w.lower() in title.lower() for w in person_name.split()):
                        seen.add(thumb)
                        candidates.append(PhotoCandidate(
                            id=f"wiki-person-{pid}",
                            title=f"{title}",
                            thumb_url=thumb,
                            image_url=thumb,
                            source="wikimedia",
                            photographer="Wikipedia Editorial",
                            description=f"Official photo from {title}",
                        ))
    except Exception as e:
        print("Wiki person search error:", e)

    return candidates

# Test with Abiy Ahmed
res = search_person_photos("Abiy Ahmed")
print(f"Total photos found for Abiy Ahmed: {len(res)}")
for i, c in enumerate(res[:8]):
    print(f"[{i}] {c.title} -> {c.image_url}")
