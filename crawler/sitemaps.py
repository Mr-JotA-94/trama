# Diagnóstico: ¿qué devuelve el news-sitemap y lo entiende nuestro parser?
import re
import httpx
from xml.etree import ElementTree

URL = "https://www.elespectador.com/arc/outboundfeeds/news-sitemap/?outputType=xml"
H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "es-CO,es;q=0.9",
}

r = httpx.get(URL, headers=H, timeout=25, follow_redirects=True)
print("status:", r.status_code)
print("primeros 500 chars del XML:\n", r.text[:500], "\n")

# Replicar exactamente lo que hace urls_desde_sitemap en crawler.py
limpio = re.sub(r'xmlns(:\w+)?="[^"]+"', "", r.text)
limpio = re.sub(r"<(/?)\w+:", r"<\1", limpio)
raiz = ElementTree.fromstring(limpio.encode("utf-8"))
urls = [(u.findtext("loc") or "").strip() for u in raiz.iter("url")]
print(f"URLs que el parser extrae: {len(urls)}")
for u in urls[:5]:
    print("  ", u)