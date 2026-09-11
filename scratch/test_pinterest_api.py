import httpx
import json
import urllib.parse

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*, q=0.01",
    "Referer": "https://www.pinterest.com/",
}

query = "Abiy Ahmed Ethiopia"
data_param = {
    "options": {
        "query": query,
        "scope": "pins",
        "page_size": 10
    },
    "context": {}
}

url = f"https://www.pinterest.com/resource/BaseSearchResource/get/?source_url=%2Fsearch%2Fpins%2F%3Fq%3D{urllib.parse.quote(query)}&data={urllib.parse.quote(json.dumps(data_param))}"

try:
    res = httpx.get(url, headers=headers, timeout=10.0)
    print("Pinterest API status:", res.status_code)
    if res.status_code == 200:
        data = res.json()
        results = data.get("resource_response", {}).get("data", {}).get("results", [])
        print("Pinterest pins returned:", len(results))
        for p in results[:5]:
            images = p.get("images", {})
            orig = images.get("orig", {}).get("url") or images.get("736x", {}).get("url")
            desc = p.get("grid_title") or p.get("description") or "Pinterest Photo"
            print("  Pin:", desc[:50], "->", orig)
except Exception as e:
    print("Pinterest API error:", e)
