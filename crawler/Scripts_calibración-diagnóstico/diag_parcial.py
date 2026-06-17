# diag_parcial.py v2 — corre desde crawler/ (importa crawler.py y su .env)
import json, re
from urllib.parse import urlsplit
import httpx
from crawler import detectar_paywall_jsonld, MARCADORES_PAYWALL, limpiar_contenido, HEADERS

URLS = [
    "https://www.elespectador.com/bogota/al-parecer-no-violo-a-ninguno-de-sus-hijos-presidente-petro-por-supuesto-caso-de-abuso-sexual-en-bogota/",
    "https://www.elespectador.com/bogota/denuncia-abuso-sexual-usaquen-menores-ya-fueron-dados-de-alta-y-estan-bajo-proteccion-del-icbf/",
    "https://www.elespectador.com/judicial/soldado-del-ejercito-murio-tras-recibir-descarga-electrica-durante-operacion-en-magdalena/",
]

def nodos_jsonld(html):
    out = []
    for bloque in re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.I | re.S):
        try:
            data = json.loads(bloque.strip())
        except Exception:
            continue
        pila = [data]
        while pila:
            o = pila.pop(0)
            if isinstance(o, dict):
                if isinstance(o.get("@graph"), list):
                    pila.extend(o["@graph"])
                out.append(o)
            elif isinstance(o, list):
                pila.extend(o)
    return out

def url_de_nodo(n):
    # mainEntityOfPage (str o {"@id":...}), url, o @id — lo que haya
    for k in ("mainEntityOfPage", "url", "@id"):
        v = n.get(k)
        if isinstance(v, dict):
            v = v.get("@id")
        if isinstance(v, str) and v.startswith("http"):
            return v
    return None

def path_norm(u):
    return urlsplit(u).path.rstrip("/").lower() if u else None

with httpx.Client(headers=HEADERS, follow_redirects=True) as c:
    for url in URLS:
        print("\n" + "=" * 75)
        print(url[:73])
        try:
            html = c.get(url, timeout=30).text
        except Exception as e:
            print("  no se pudo descargar:", e); continue

        objetivo = path_norm(url)
        nodos = [n for n in nodos_jsonld(html)
                 if isinstance(n, dict) and "isAccessibleForFree" in n]

        principal = None
        for n in nodos:
            es_ppal = path_norm(url_de_nodo(n)) == objetivo
            head = str(n.get("headline", ""))[:45]
            free = n.get("isAccessibleForFree")
            body = bool(str(n.get("articleBody", "")).strip())
            marca = "  <<< NODO PRINCIPAL" if es_ppal else ""
            print(f"   free={str(free):6} body={str(body):5} @type={str(n.get('@type','')):18} "
                  f"'{head}'{marca}")
            if es_ppal:
                principal = free

        # patrón de Jota: enlaces incrustados
        leamas = [m for m in ("lea más", "lea también", "le puede interesar", "puede leer")
                  if m in html.lower()]

        regex = detectar_paywall_jsonld(html)           # lo que ve el crawler hoy
        print(f"\n   regex global (crawler)  -> parcial={regex}")
        print(f"   nodo PRINCIPAL declara  -> isAccessibleForFree={principal}")
        print(f"   enlaces 'lea más' en HTML -> {leamas or 'ninguno'}")
        if principal is True and regex is True:
            print("   >>> CASO A: falso positivo CONFIRMADO (regex agarró un nodo ajeno)")
        elif principal is False:
            print("   >>> CASO B: el medio SÍ declara la nota de pago — el flag es correcto")
        elif principal is None:
            print("   >>> el nodo principal no expone isAccessibleForFree — revisar a mano")