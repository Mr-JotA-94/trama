# crawler/probar_espectador.py
import httpx
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
r = httpx.get("https://www.elespectador.com/robots.txt", headers=H, timeout=20)
print(r.status_code)
for linea in r.text.splitlines():
    if "sitemap" in linea.lower():
        print(linea)