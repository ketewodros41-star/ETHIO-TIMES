import httpx
import re
import json
import urllib.parse

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

q = "Abiy Ahmed Ethiopia Prime Minister"
url = f"https://yandex.com/images/search?text={urllib.parse.quote(q)}"
res = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
print("Yandex status:", res.status_code, "length:", len(res.text))

# Yandex embeds images in data-bem attributes: {"serp-item":{"thumb":{"url":"..."},"preview":[{"url":"..."}]}}
matches = re.findall(r'data-bem=\'({[^\']+?serp-item[^\']+?})\'', res.text)
print("Yandex matches:", len(matches))
found = 0
for m in matches:
    try:
        data = json.loads(m)
        serp = data.get("serp-item", {})
        dups = serp.get("dups", [])
        thumb = serp.get("thumb", {}).get("url")
        orig = dups[0].get("url") if dups else thumb
        title = serp.get("snippet", {}).get("title", "")
        if orig:
            found += 1
            if found <= 5:
                print(f"  [{found}] {title[:40]} -> {orig[:80]}")
    except Exception as e:
        pass
print("Total Yandex found:", found)
