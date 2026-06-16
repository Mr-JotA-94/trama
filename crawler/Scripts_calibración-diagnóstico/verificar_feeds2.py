# verificar_feeds.py — diligencia de cola, NO es Fase 2. Solo lee, no escribe nada.
import httpx
from xml.etree import ElementTree as ET

CANDIDATOS = {
    "lasillavacia": [
        "https://www.lasillavacia.com/feed/",
        "https://www.lasillavacia.com/rss/",
    ],
    "rtvcnoticias": [
        "https://www.rtvcnoticias.com/feed",
        "https://www.rtvcnoticias.com/feed/",
        "https://www.rtvcnoticias.com/rss.xml",
        "https://www.rtvcnoticias.com/rss",
    ],
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}

with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20) as c:
    for medio, urls in CANDIDATOS.items():
        print(f"\n=== {medio} ===")
        for u in urls:
            try:
                r = c.get(u)
                ct = r.headers.get("content-type", "")
                # ¿Es XML/RSS parseable y trae <item>?
                try:
                    raiz = ET.fromstring(r.text.encode("utf-8"))
                    n_items = len(list(raiz.iter("item")))
                except ET.ParseError:
                    n_items = -1  # no es XML
                marca = "OK" if n_items > 0 else ("vacío/no-rss" if n_items == 0 else "NO-XML")
                print(f"  [{r.status_code}] items={n_items:>3} {marca:<12} {u}  ({ct[:30]})")
            except Exception as e:
                print(f"  ERROR {type(e).__name__}: {str(e)[:50]}  {u}")