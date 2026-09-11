import httpx
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}
res = httpx.get("https://www.google.com/search?q=Abiy+Ahmed&tbm=isch", headers=headers, follow_redirects=True)
with open("scratch/google_dump.html", "w", encoding="utf-8") as f:
    f.write(res.text)

# Find all occurrences of tbn: or gstatic or http in the dump
print("Occurrences of gstatic:", res.text.count("gstatic"))
print("Occurrences of tbn:", res.text.count("tbn"))
print("Occurrences of img src:", res.text.count("<img"))

import bs4
soup = bs4.BeautifulSoup(res.text, "html.parser")
imgs = soup.find_all("img")
print("Total img tags:", len(imgs))
for img in imgs[:10]:
    print("  img:", img.get("src")[:80] if img.get("src") else "no-src")
