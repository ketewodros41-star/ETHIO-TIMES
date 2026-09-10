import httpx
import re
import bs4
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# 1. Test Pinterest
try:
    r_pin = httpx.get("https://www.pinterest.com/search/pins/?q=Abiy%20Ahmed%20Ethiopia", headers=headers, timeout=10.0)
    print("Pinterest status:", r_pin.status_code)
    # Pinterest embeds pin images in json or html
    pin_images = list(set(re.findall(r'https://i\.pinimg\.com/[0-9a-zA-Z_/-]+\.jpg', r_pin.text)))
    print("Pinterest images found:", len(pin_images))
    for u in pin_images[:4]:
        print("  Pinterest ->", u)
except Exception as e:
    print("Pinterest failed:", e)

# 2. Test Google Images with tbm=isch
try:
    r_goog = httpx.get("https://www.google.com/search?q=Abiy+Ahmed+Prime+Minister+Ethiopia&tbm=isch&asearch=ichunk&async=_id:rg_s,_pms:s", headers=headers, timeout=10.0)
    print("Google status:", r_goog.status_code)
    # Check for image urls in google response
    g_images = list(set(re.findall(r'https://[^\"]+?\.(?:jpg|jpeg|png)', r_goog.text)))
    # filter google domains
    real_g_images = [u for u in g_images if "gstatic.com" in u or ("google.com" not in u and "google" not in u)]
    print("Google images found:", len(real_g_images))
    for u in real_g_images[:4]:
        print("  Google ->", u)
except Exception as e:
    print("Google failed:", e)

# 3. Test Google News Topic Images / Media
try:
    r_news = httpx.get("https://news.google.com/rss/search?q=Abiy+Ahmed&hl=en-US&gl=US&ceid=US:en", headers=headers, timeout=10.0)
    print("Google News RSS status:", r_news.status_code)
    import feedparser
    feed = feedparser.parse(r_news.text)
    print("Google news entries:", len(feed.entries))
    for entry in feed.entries[:3]:
        print("  Entry:", entry.title)
        # Check links
        print("  Link:", entry.link)
except Exception as e:
    print("Google News failed:", e)
