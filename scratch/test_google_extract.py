import httpx
import re
import bs4

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Test standard Google image search
res = httpx.get("https://www.google.com/search?q=Abiy+Ahmed&tbm=isch", headers=headers, follow_redirects=True)
print("Google Images raw status:", res.status_code, "length:", len(res.text))

# Let's search for encrypted-tbn0.gstatic.com thumbnails which Google always embeds directly in HTML!
tbn_imgs = re.findall(r'https://encrypted-tbn0\.gstatic\.com/images\?q=tbn:[^\"\'\s]+', res.text)
print("Found gstatic thumbnails:", len(tbn_imgs))
for u in tbn_imgs[:5]:
    print("  Gstatic ->", u)

# Also let's check high-res URLs in the JSON blobs inside google html
# Google embeds: [["https://...jpg", height, width], ...]
high_res = re.findall(r'\[\"(https://[^\"]+?\.(?:jpg|jpeg|png))\",\s*\d+,\s*\d+\]', res.text)
print("Found high-res image pairs in Google HTML:", len(high_res))
for u in high_res[:5]:
    print("  High-res ->", u)
