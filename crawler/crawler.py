"""
TRAMA — Crawler v1 (Fase 1, Paso 2)
Archivo: crawler/crawler.py

Qué hace, en orden:
  1. Lee los 5 medios y sus fuentes (jsonb) desde Supabase
  2. Por cada fuente (rss o sitemap) obtiene los URLs de artículos recientes
  3. Por cada URL: descarga, extrae SOLO el contenido visible (trafilatura),
     clasifica el tipo por heurísticas de URL, calcula SHA-256
  4. Inserta en Supabase. La restricción unique(url, hash) hace la
     deduplicación: re-captura idéntica = rechazada; contenido cambiado
     = fila nueva (historial). Nunca se hace UPDATE.
  5. Registra cada inserción en audit_log.

Uso local (primera vez, antes de automatizar):
  pip install -r requirements.txt
  copia .env.example a .env y llena las dos claves
  python crawler.py

Componente LOAD-BEARING: si tocas este archivo, cada fuente debe seguir
fallando de forma aislada (un medio caído no detiene a los demás).
"""

import hashlib
import html as html_lib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from xml.etree import ElementTree

import httpx
import trafilatura
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]  # service_role: SOLO en .env y GitHub Secrets

# Límite por fuente por corrida: mantiene las corridas cortas y predecibles.
MAX_ARTICULOS_POR_FUENTE = 25

# Pausa entre descargas de artículos (segundos). Sé un buen ciudadano:
# esto es un archivo histórico, no una aspiradora.
PAUSA_ENTRE_ARTICULOS = 2.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "es-CO,es;q=0.9",
}

# ---------------------------------------------------------------------
# Clasificador de tipo por URL (heurístico, calibrar con muestreo manual)
# ---------------------------------------------------------------------
PATRONES_TIPO = [
    (r"/opinion/|/columnistas?/|/blogs?/", "opinion"),
    (r"/editorial/", "editorial"),
    (r"/analisis/", "analisis"),
    (r"(afp|efe|reuters|europa-press)", "agencia"),
]

def extraer_seccion(url: str, regla: dict) -> str | None:
    """Extrae la sección según la regla configurada por medio."""
    metodo = (regla or {}).get("metodo", "primer_segmento")
    if metodo == "fijo":
        return regla.get("valor")
    if metodo == "ninguno":
        return None
    if metodo == "primer_segmento":
        # https://medio.com/seccion/sub/titulo → 'seccion'
        try:
            path = url.split("//", 1)[1].split("/", 1)[1]  # quita dominio
            primer = path.split("/", 1)[0].strip().lower()
            # Un slug largo con guiones es título, no sección (caso Las2orillas
            # si alguna vez cae aquí). Sección real: corta, sin muchos guiones.
            if primer and len(primer) <= 20 and primer.count("-") <= 1:
                return primer
        except (IndexError, AttributeError):
            pass
    return None

def clasificar_tipo(url: str) -> str:
    u = url.lower()
    for patron, tipo in PATRONES_TIPO:
        if re.search(patron, u):
            return tipo
    # Si no coincide ningún patrón de sección especial, es noticia.
    # 'desconocido' queda reservado para casos que un humano deba revisar.
    return "noticia"


# ---------------------------------------------------------------------
# Obtención de URLs desde las fuentes
# ---------------------------------------------------------------------
def urls_desde_rss(xml_texto: str) -> list[dict]:
    """Extrae url, título y fecha de un feed RSS. Devuelve [] si falla."""
    items = []
    try:
        raiz = ElementTree.fromstring(xml_texto.encode("utf-8"))
        for item in raiz.iter("item"):
            link = item.findtext("link", "").strip()
            titulo = (item.findtext("title") or "").strip()
            fecha = (item.findtext("pubDate") or "").strip()
            if link:
                items.append({"url": link, "titulo_feed": titulo, "fecha_feed": fecha})
    except ElementTree.ParseError as e:
        print(f"    XML inválido: {e}")
    return items


def urls_desde_sitemap(xml_texto: str) -> list[dict]:
    """Extrae URLs de un sitemap (news o estándar), ordenadas por fecha
    de publicación descendente cuando el sitemap la declara."""
    items = []
    try:
        # Quitar namespaces: primero las declaraciones, luego los prefijos
        # de las etiquetas (<news:name> → <name>). Solo leemos <url>, <loc>
        # y <publication_date>, así que aplanar no pierde nada que usemos.
        limpio = re.sub(r'xmlns(:\w+)?="[^"]+"', "", xml_texto)
        limpio = re.sub(r"<(/?)\w+:", r"<\1", limpio)
        raiz = ElementTree.fromstring(limpio.encode("utf-8"))
        for url_el in raiz.iter("url"):
            loc = (url_el.findtext("loc") or "").strip()
            # Tras aplanar prefijos, <news:publication_date> queda como
            # <publication_date> anidado; .//  lo busca a cualquier nivel.
            fecha = (url_el.findtext(".//publication_date") or "").strip()
            if loc:
                items.append({"url": loc, "titulo_feed": "", "fecha_feed": fecha})
        # ISO 8601 ordena correctamente como texto; vacíos al final.
        items.sort(key=lambda x: x["fecha_feed"], reverse=True)
    except ElementTree.ParseError as e:
        print(f"    Sitemap inválido: {e}")
    return items


def obtener_urls_de_fuente(cliente: httpx.Client, fuente: dict) -> list[dict]:
    """Una fuente que falla devuelve [] — jamás levanta excepción hacia arriba."""
    try:
        r = cliente.get(fuente["url"], timeout=25)
        if r.status_code != 200:
            print(f"    [{r.status_code}] {fuente['url']}")
            return []
        if fuente["tipo"] == "rss":
            return urls_desde_rss(r.text)
        if fuente["tipo"] == "sitemap":
            return urls_desde_sitemap(r.text)
        print(f"    Tipo de fuente desconocido: {fuente['tipo']}")
        return []
    except Exception as e:
        print(f"    ERROR fuente {fuente['url']}: {type(e).__name__}: {str(e)[:80]}")
        return []


# ---------------------------------------------------------------------
# Extracción de artículo
# ---------------------------------------------------------------------

def extraer_articlebody(html: str) -> str | None:
    """Cuerpo declarado por el medio en el JSON-LD. Recorre todos los bloques
    ld+json, aplana @graph/arrays, devuelve el primer articleBody no vacío.
    None si ninguno lo trae (p. ej. notas-video). Nunca levanta."""
    bloques = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.I | re.S,
    )
    for bloque in bloques:
        try:
            data = json.loads(bloque.strip())
        except Exception:
            continue
        nodos: list = []

        def recoger(obj):
            if isinstance(obj, dict):
                if isinstance(obj.get("@graph"), list):
                    for n in obj["@graph"]:
                        recoger(n)
                nodos.append(obj)
            elif isinstance(obj, list):
                for n in obj:
                    recoger(n)

        recoger(data)
        for nodo in nodos:
            if isinstance(nodo, dict):
                cuerpo = nodo.get("articleBody")
                if isinstance(cuerpo, str) and cuerpo.strip():
                    return html_lib.unescape(cuerpo).strip()
    return None

def detectar_paywall_jsonld(html: str) -> bool:
    """Lee isAccessibleForFree del JSON-LD. El medio declara aquí si la nota
    es de pago — señal limpia, no depende de longitud ni de overlays JS."""
    # Tolerante a espacios/comillas: "isAccessibleForFree" : "false"  o  false
    m = re.search(r'"isAccessibleForFree"\s*:\s*"?(false|true)"?', html, re.I)
    if m:
        return m.group(1).lower() == "false"  # false = de pago = parcial
    return False

def meta_content(html: str, name: str) -> str | None:
    """Extrae el content de un <meta name=... > o property=... del HTML."""
    for attr in ("name", "property"):
        m = re.search(
            rf'<meta[^>]*{attr}=["\']{re.escape(name)}["\'][^>]*content=["\']([^"\']*)["\']',
            html, re.I,
        )
        if not m:
            m = re.search(
                rf'<meta[^>]*content=["\']([^"\']*)["\'][^>]*{attr}=["\']{re.escape(name)}["\']',
                html, re.I,
            )
        if m:
            return m.group(1).strip() or None
    return None


def extraer_articulo(cliente: httpx.Client, url: str, metodo: str = "articlebody") -> dict | None:
    """Descarga y extrae SOLO el contenido visible públicamente."""
    try:
        r = cliente.get(url, timeout=30)
        if r.status_code != 200:
            return None
        extraido = trafilatura.bare_extraction(
            r.text, url=url, with_metadata=True, include_comments=False,
        )
        if not extraido:
            return None

        # trafilatura 1.x devuelve dict; 2.x devuelve objeto. Soportamos ambos.
        if isinstance(extraido, dict):
            campo = extraido.get
        else:
            campo = lambda k, d=None: getattr(extraido, k, d)

        contenido_traf = (campo("text") or "").strip()

        # Elección del cuerpo según bucket. articleBody primario, trafilatura
        # piso. Un articleBody < 100 chars se trata como ausente (cae a traf).
        if metodo == "articlebody":
            ab = extraer_articlebody(r.text)
            contenido = ab if (ab and len(ab) >= 100) else contenido_traf
        else:
            contenido = contenido_traf
        titulo = (campo("title") or "").strip()

        # Subtítulo: trafilatura usa og:description. Algunos medios (El
        # Colombiano hoy) ahí ponen el primer párrafo en vez de la bajada.
        # Detectamos el síntoma —no el medio— y caemos a twitter:description.
        subtitulo = (campo("description") or "").strip() or None
        if subtitulo and contenido.startswith(subtitulo[:60]):
            # og duplica el cuerpo: no es bajada real. Probar respaldo.
            respaldo = meta_content(r.text, "twitter:description")
            if respaldo and not contenido.startswith(respaldo[:60]):
                subtitulo = respaldo   # el respaldo SÍ es una bajada distinta
            else:
                subtitulo = None        # ningún meta sirve: mejor sin subtítulo

        if not titulo or len(contenido) < 100:
            # Sin título o casi sin texto visible: no vale como snapshot
            return None
        return {
            "titulo": titulo,
            "subtitulo": subtitulo,
            "autor": (campo("author") or "").strip() or None,
            "fecha_publicacion": campo("date"),  # ISO o None
            "contenido_visible": contenido,
            "paywall_jsonld": detectar_paywall_jsonld(r.text),
        }
    except Exception as e:
        print(f"    ERROR artículo {url[:60]}: {type(e).__name__}: {str(e)[:60]}")
        return None
    

def calcular_hash(titulo: str, subtitulo: str | None, contenido: str) -> str:
    base = f"{titulo}|{subtitulo or ''}|{contenido}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


MARCADORES_PAYWALL = [
    "contenido exclusivo para suscriptores",
    "regístrese para seguir leyendo",
    "regístrate para seguir leyendo",
    "suscríbase para continuar",
    "este contenido es exclusivo",
    "ya tienes una cuenta",
]


def detectar_parcial(contenido: str, nivel_paywall: str) -> bool:
    if nivel_paywall == "abierto":
        return False
    texto = contenido.lower()
    return any(m in texto for m in MARCADORES_PAYWALL)

# Líneas de boilerplate conocidas por medio. Si una línea del contenido
# contiene alguno de estos marcadores, se descarta. Calibrar con muestreo.
BOILERPLATE = [
    "cookies propias y de terceros",
    "inicia sesión",
    "iniciar sesión",
    "límite diario de",
    "plan de suscripción",
    "chatbot",
    "chat bot",
    "términos y condiciones del chat",
    "procesando tu pregunta",
    "error 505",
    "registrándote en nuestro portal",
    "peticiones mensuales",
    "políticas de la ia",
    "suscríbete e inicia la conversación",
    "uso de cookies no esenciales",
    "escucha este artículo",
    "audio generado con ia",
]


COLA_PROMOCIONAL = [
    "boletines el tiempo",
    "el tiempo google news",
    "el tiempo app",
    "suscríbete al digital",
    "sigue toda la información de",
    "ya se enteró de las últimas noticias",
    "alianza estratégica con the new york times",
    "regístrese en nuestros boletines",
    "regístrate en nuestros boletines",
    "regístrate en nuestros boletines",
    # RTVC: promo de sitio (línea "síguenos" + tweet de ratings de Señal
    # Colombia). Cortar desde el inicio del bloque evita inyectar "elecciones
    # presidenciales 2026" en cada nota. Validado read-only sobre 30 notas del
    # news-sitemap: DUROS=0. Emoji primero (corte limpio), sin-emoji de respaldo.
    "📢 entérate de lo que pasa en colombia",
    "entérate de lo que pasa en colombia",
]

# Teasers de "notas relacionadas": línea-widget que apunta a OTRA nota,
# no al cuerpo de ESTA. Filtro por PREFIJO de línea (no substring: "te puede
# interesar" puede aparecer legítimo dentro de una frase) y drop-line (no
# corte-a-fin: un teaser puede quedar intercalado entre párrafos). Exclusivo
# de RTVC hoy (medido: 0 en los otros 6 medios), pero seguro como global.
TEASERS = (
    "lee además:", "lee también:", "te puede interesar:",
    "no te lo pierdas:", "también puedes leer:",
)

def limpiar_contenido(texto: str, titulo: str = "") -> str:
    # 1) Corte de cabecera: todo lo anterior al título es chrome del sitio.
    if titulo:
        idx = texto.find(titulo)
        if idx > 0:
            texto = texto[idx:]

    # 2) Corte de cola: desde el primer marcador promocional, nada sirve.
    texto_low = texto.lower()
    cortes = [texto_low.find(m) for m in COLA_PROMOCIONAL]
    cortes = [c for c in cortes if c > 0]
    if cortes:
        texto = texto[: min(cortes)]

    # 3) Filtro línea a línea para residuos sueltos.
    lineas = []
    for l in texto.split("\n"):
        ls = l.strip()
        if ls.lower() in ("noticia", "aquí", "publicidad"):
            continue
        if ls and len(ls) <= 8 and all(c in "0123456789:/ " for c in ls):
            continue
        if any(m in ls.lower() for m in BOILERPLATE):
            continue
        if ls.lower().startswith(TEASERS):
            continue
        lineas.append(l)
    return "\n".join(lineas).strip()

# ---------------------------------------------------------------------
# Corrida principal
# ---------------------------------------------------------------------
def main():
    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    medios = sb.table("outlets").select("id, slug, nivel_paywall, fuentes, regla_seccion, extraccion").execute().data
    if not medios:
        sys.exit("No hay medios en la tabla outlets. ¿Corriste las migraciones?")

    total_nuevos, total_duplicados, total_errores = 0, 0, 0

    with httpx.Client(headers=HEADERS, follow_redirects=True) as cliente:
        for medio in medios:
            fuentes = medio.get("fuentes") or []
            if not fuentes:
                print(f"\n== {medio['slug']}: sin fuentes configuradas, salto")
                continue
            print(f"\n== {medio['slug']} ({len(fuentes)} fuente(s))")

            urls_vistas: set[str] = set()
            for fuente in fuentes:
                entradas = obtener_urls_de_fuente(cliente, fuente)
                print(f"   {fuente['tipo']}: {len(entradas)} urls | {fuente['url'][:70]}")

                for entrada in entradas[:MAX_ARTICULOS_POR_FUENTE]:
                    url = entrada["url"]
                    if url in urls_vistas:
                        continue
                    urls_vistas.add(url)
                    if medio["slug"] == "el-tiempo" and entrada.get("titulo_feed", "").strip().lower().startswith("video |"):
                        continue  # nota-video de El Tiempo: sin cuerpo de texto archivable
                    if "/caricaturista" in url or "/caricaturas" in url:
                        continue  # contenido visual, no archivable como texto

                    art = extraer_articulo(cliente, url, medio.get("extraccion") or "articlebody")
                    time.sleep(PAUSA_ENTRE_ARTICULOS)
                    if art is None:
                        total_errores += 1
                        continue

                    contenido_limpio = limpiar_contenido(art["contenido_visible"], art["titulo"])
                    if len(contenido_limpio) < 100:
                        total_errores += 1
                        continue

                    seccion = extraer_seccion(url, medio.get("regla_seccion"))
                    fila = {
                        "outlet_id": medio["id"],
                        "url": url,
                        "titulo": art["titulo"],
                        "subtitulo": art["subtitulo"],
                        "autor": art["autor"],
                        "fecha_publicacion": art["fecha_publicacion"],
                        "contenido_visible": contenido_limpio,
                        "es_parcial": art["paywall_jsonld"] or detectar_parcial(contenido_limpio, medio["nivel_paywall"]),
                        "tipo": clasificar_tipo(url),
                        "seccion": seccion,
                        "hash_sha256": calcular_hash(art["titulo"], art["subtitulo"], contenido_limpio),
                    }

                    try:
                        res = sb.table("articles").insert(fila).execute()
                        articulo_id = res.data[0]["id"]
                        sb.table("audit_log").insert(
                            {"article_id": articulo_id, "hash_sha256": fila["hash_sha256"]}
                        ).execute()
                        total_nuevos += 1
                        print(f"      + [{fila['tipo']}] {art['titulo'][:65]}")
                    except Exception as e:
                        # Violación de unique(url, hash) = ya lo tenemos idéntico. Correcto.
                        if "duplicate" in str(e).lower() or "23505" in str(e):
                            total_duplicados += 1
                        else:
                            total_errores += 1
                            print(f"      ERROR insert: {str(e)[:100]}")

    ahora = datetime.now(timezone.utc).isoformat()
    print("\n" + "=" * 60)
    print(f"Corrida {ahora}")
    print(f"Nuevos: {total_nuevos} | Ya existentes (idénticos): {total_duplicados} | Errores: {total_errores}")


if __name__ == "__main__":
    main()
