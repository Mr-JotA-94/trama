"""
TRAMA — Verificador de feeds RSS
Fase 1, Paso 1

Córrelo en TU máquina (no en el datacenter — los medios bloquean IPs de servidor).

  pip install httpx
  python verificar_feeds.py

Objetivo: confirmar qué URL de RSS funciona para cada medio.
Anota los que digan OK y mételos en la columna rss_url de Supabase.
Si alguno falla con 403 incluso desde tu casa, ese medio necesitará
crawling de su sitemap en vez de RSS (lo resolvemos en el Paso 2).
"""

import httpx

# Candidatos por medio. El script prueba todos y reporta cuál sirve.
CANDIDATOS = {
    "voragine": [
        "https://voragine.co/feed/",
        "https://voragine.co/rss",
    ],
    "las2orillas": [
        "https://www.las2orillas.co/feed/",
    ],
    "el-espectador": [
        "https://www.elespectador.com/arc/outboundfeeds/rss/?outputType=xml",
        "https://www.elespectador.com/arc/outboundfeeds/rss/category/politica/?outputType=xml",
    ],
    "el-tiempo": [
        "https://www.eltiempo.com/rss/colombia.xml",
        "https://www.eltiempo.com/rss/politica.xml",
        "https://www.eltiempo.com/rss/justicia.xml",
    ],
    "el-colombiano": [
        "https://www.elcolombiano.com/rss/colombia.xml",
        "https://www.elcolombiano.com/rss/politica.xml",
    ],
}

# Header de navegador real. Importante: identifícate con honestidad pero
# usa un UA estándar para que el servidor no te bloquee por defecto.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def es_feed_valido(texto: str) -> bool:
    cabeza = texto.strip()[:500].lower()
    return ("<rss" in cabeza) or ("<feed" in cabeza) or ("<?xml" in cabeza and "<channel" in texto.lower())


def contar_items(texto: str) -> int:
    return texto.count("<item>") + texto.count("<item ") + texto.count("<entry>")


def main():
    print("Verificando feeds RSS de los 5 medios de Fase 1...\n")
    confirmados = {}

    for slug, urls in CANDIDATOS.items():
        print(f"=== {slug} ===")
        mejor = None
        for url in urls:
            try:
                r = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
                valido = es_feed_valido(r.text)
                items = contar_items(r.text)
                estado = "OK " if (r.status_code == 200 and valido and items > 0) else "no "
                print(f"  [{estado}] {r.status_code} | items={items:<3} | {url}")
                if estado == "OK " and mejor is None:
                    mejor = url
            except Exception as e:
                print(f"  [ERR] {type(e).__name__}: {str(e)[:50]} | {url}")
        if mejor:
            confirmados[slug] = mejor
        else:
            print(f"  >> SIN FEED CONFIRMADO para {slug} (irá por sitemap en Paso 2)")
        print()

    print("=" * 60)
    print("RESUMEN — pega estos rss_url en Supabase:\n")
    if not confirmados:
        print("  Ningún feed confirmado. Avísame y vamos por sitemaps.")
    for slug, url in confirmados.items():
        print(f"  update outlets set rss_url = '{url}' where slug = '{slug}';")
    faltantes = set(CANDIDATOS) - set(confirmados)
    if faltantes:
        print(f"\n  Faltan (sin RSS): {', '.join(sorted(faltantes))}")


if __name__ == "__main__":
    main()
