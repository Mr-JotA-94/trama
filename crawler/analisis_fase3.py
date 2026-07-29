# crawler/analisis_fase3.py — Tier 2, load-bearing.
# Fase 3 v1: comparación inter-medio (por par) + resumen por clúster (corroboración +
# síntesis), vía LLM (DeepInfra). El análisis es caché derivado: idempotente, keyed por
# hash de contenido — se puede borrar `comparaciones`/`resumenes` y reconstruir sin
# perder nada (el archivo fuente en `articles` es la verdad).
#
# El verificador verbatim es el gate de publicación: ningún span que el LLM devuelva se
# guarda si no es subcadena literal (normalizada) del texto del medio que lo declara.
# Esto es lo que impide que una alucinación del modelo se publique como cita.
#
# Este módulo SOLO define funciones de análisis + un main() de prueba manual sobre UN
# story_id. NO hace backfill masivo ni se engancha al cron: eso es otra unidad.
#
# Entorno: Python 3.14 local tiene un bug conocido que cuelga sockets SSL de httpx/
# requests cuando se usa streaming (el timeout no se respeta). Por eso acá se usa
# requests.post con stream=False y un timeout total explícito. Producción real corre en
# GitHub Actions, no en la máquina local, pero el código defensivo se escribe igual.

import os
import re
import json
import time
import hashlib
import argparse
import unicodedata

import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
DEEPINFRA_API_KEY = os.environ["DEEPINFRA_API_KEY"]
DEEPINFRA_BASE_URL = os.environ.get("DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai")

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# --- Config del modelo (fija, no parametrizable por ahora) ---
MODELO = "zai-org/GLM-5.2"
TEMPERATURA = 0.15
MAX_TOKENS = 6000
PROMPT_VERSION = "v1"

TIMEOUT_TOTAL = 120       # segundos, timeout total de la llamada (no por-socket)
MAX_REINTENTOS = 4
BACKOFF_BASE = 2          # segundos: 2, 4, 8, 16...

MIN_PALABRAS_SPAN = 6     # piso de longitud para que un span cuente como cita real,
                           # no una coincidencia trivial de 2-3 palabras comunes.

# ---------------------------------------------------------------------
# Prompts (system) — HARDCODEADOS a propósito (auditar el prompt exacto que produjo
# cada fila es parte del contrato de Fase 3). Validados en diagnóstico:
# SYS_COMPARACION viene de diag_v1_solospans.py (105 spans / 0 fabricación).
# SYS_CORROBORA y SYS_SINTESIS vienen de diag_bakeoff2.py (bakeoff que ganó GLM).
# ---------------------------------------------------------------------

SYS_COMPARACION = """Eres un analista forense de medios. Recibes DOS versiones de un hecho, de dos medios colombianos distintos. Tu trabajo NO es redactar ni explicar: es SEÑALAR, copiando fragmentos LITERALES, en qué difieren las dos coberturas. Un sistema posterior verifica que cada fragmento sea copia exacta del texto; si no lo es, se descarta. Por eso NO parafrasees, NO resumas, NO redactes glosas: solo copiá fragmentos tal cual aparecen.

PASO 0 — ¿MISMO HECHO? (compuerta)
Mismo hecho = las dos notas reportan el MISMO suceso concreto. NO lo son: dos columnas de opinión sobre un tema parecido, o dos notas que solo comparten personajes/tema pero cuentan sucesos distintos. Si no es el mismo suceso: es_mismo_hecho=false, divergencia_relevante=false, todos los arrays vacíos.

PASO 1 — RÉPLICA
Si es el mismo hecho pero dicen esencialmente lo mismo: divergencia_relevante=false, arrays vacíos. El vacío es correcto; se penaliza inventar, no callar.

PASO 2 — DESFASE TEMPORAL
Tenés la fecha de cada versión. Si una diferencia se explica porque una nota es POSTERIOR (conoce hechos que la otra no podía saber), va SOLO en "desfase_temporal", NO en las diferencias.

PASO 3 — SEÑALAR DIFERENCIAS (solo si mismo hecho, no réplica, no temporal)
Cada ítem es un FRAGMENTO LITERAL de UN medio + su categoría. Categorías:
- "enfoque": el fragmento del TITULAR o primer párrafo que muestra qué pone ese medio al frente (cuando el otro pone algo distinto).
- "agrega": un fragmento con un hecho/dato concreto que ese medio incluye y el otro NO menciona.
- "salvedad": un fragmento donde ese medio marca un hecho como NO confirmado, y el otro lo afirma de plano. El fragmento DEBE contener un marcador de duda literal ("presunto", "habría", "al parecer", "en verificación", "sin confirmar", "preliminar", "según fuentes", "se presume", "supuesto"). Si no podés copiar un marcador literal, no es salvedad.

REGLAS DURAS:
- "span" = subcadena EXACTA del titular o cuerpo de ESE medio (mínimo 6 palabras seguidas), copiada carácter por carácter. Sin parafrasear, sin completar, sin unir fragmentos separados, sin mezclar los dos textos. Si dudás de que esté literal, no lo incluyas.
- No inventes un span "representativo": si el medio no tiene una frase literal que muestre la diferencia, no reportes esa diferencia.
- "medio" = el slug exacto dado.
- Ante la duda de si una diferencia es real o trivial, descartala.

FORMATO — responde ÚNICAMENTE este JSON, sin markdown ni texto extra:
{
  "es_mismo_hecho": true,
  "divergencia_relevante": true,
  "desfase_temporal": "",
  "diferencias": [
    {"medio": "slug", "categoria": "enfoque|agrega|salvedad", "span": "fragmento LITERAL copiado del texto de ese medio"}
  ]
}"""

SYS_CORROBORA = """Eres un analista forense de medios. Recibes VARIAS versiones del mismo hecho, publicadas por medios colombianos distintos. Tu trabajo NO es redactar ni explicar: es SEÑALAR, copiando fragmentos LITERALES, qué reportan en común y qué reporta uno solo.

Un sistema posterior verifica que cada fragmento sea copia exacta del texto de ese medio. Si no lo es, se descarta. Por eso NO parafrasees, NO resumas, NO completes: copiá fragmentos tal cual aparecen.

Devuelve dos listas:

1. "hechos_corroborados": cada elemento es UN hecho que reportan DOS O MÁS medios. Para ese hecho, incluí un fragmento literal de CADA medio que lo reporta. Los fragmentos de un mismo hecho deben decir lo MISMO (aunque con otras palabras); si no dicen lo mismo, no es un hecho corroborado.

2. "solo_un_medio": hechos concretos que aparecen en UN SOLO medio y en ninguno de los demás. Un fragmento literal por elemento.

REGLAS DURAS:
- "span" = subcadena EXACTA del titular o cuerpo de ESE medio (mínimo 6 palabras seguidas), copiada carácter por carácter. Sin parafrasear, sin unir fragmentos separados, sin mezclar textos de medios distintos.
- "medio" = el slug exacto dado.
- Priorizá los hechos NUCLEARES (qué pasó, dónde, a quién, cuántos). Máximo 5 hechos corroborados y 4 de un solo medio.
- No incluyas enlaces de navegación ni promociones ("Lea también", "En contexto", "Le puede interesar", "Siga leyendo"): NO son hechos.
- Si dudás de que un fragmento esté literal, no lo incluyas.

FORMATO — responde ÚNICAMENTE este JSON, sin markdown ni texto extra:
{
  "hechos_corroborados": [
    {"spans": [{"medio":"slug","span":"fragmento literal"}, {"medio":"slug","span":"fragmento literal"}]}
  ],
  "solo_un_medio": [
    {"medio":"slug","span":"fragmento literal"}
  ]
}"""

SYS_SINTESIS = """Eres un redactor de una hemeroteca. Recibes una lista de HECHOS YA VERIFICADOS: fragmentos textuales que varios medios colombianos reportaron sobre el mismo suceso. NO tenés acceso a los artículos originales; solo a estos fragmentos.

Escribí una síntesis de MÁXIMO 2 FRASES (unas 40 palabras) que le permita a un lector entender en segundos de qué se trata la noticia.

REGLAS DURAS:
- Usá ÚNICAMENTE información contenida en los fragmentos. Si un dato no está en los fragmentos, NO existe: no lo agregues, no lo deduzcas, no lo completes con lo que sepas del tema.
- NO inventes ni ajustes cifras, fechas, lugares ni nombres. Copiá las cifras tal como aparecen (si dice "al menos 5", no escribas "5").
- NO uses adjetivos de valoración ni califiques a nadie ("polémico", "grave", "escandaloso"). Tono factual y sobrio.
- NO atribuyas a medios ni digas "según los medios": redactá el hecho.
- NO opines, no contextualices con información externa, no especules sobre consecuencias.
- Si los fragmentos son insuficientes para una síntesis clara, escribí una sola frase con lo que sí está.

FORMATO — responde ÚNICAMENTE este JSON, sin markdown ni texto extra:
{"sintesis": "máximo 2 frases"}"""


# =======================================================================
# Verificador verbatim (gate de publicación)
# =======================================================================

def normalizar(s):
    """NFKC + comillas tipográficas→rectas + colapsar espacios + lower.
    Es la base de comparación para TODO el verificador: un span solo cuenta como
    literal si sobrevive esta normalización en ambos lados (span y texto fuente)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = (s.replace("“", '"').replace("”", '"')
          .replace("‘", "'").replace("’", "'"))
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def span_valido(span, texto_fuente):
    """True si `span` es subcadena literal (normalizada) de `texto_fuente` y tiene
    al menos MIN_PALABRAS_SPAN palabras. Cualquier span que falle esto se descarta
    ANTES de guardar — nunca se persiste una cita no-literal."""
    span_norm = normalizar(span)
    if len(span_norm.split()) < MIN_PALABRAS_SPAN:
        return False
    return span_norm in normalizar(texto_fuente)


_RE_NUMERO = re.compile(r"\d+")
_RE_PROPIO = re.compile(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b")


def _verificar_sintesis_parcial(sintesis, hechos_validos):
    """Verificador PARCIAL de la síntesis: a diferencia del de comparación/
    corroboración, NO bloquea. La síntesis es prosa generada (no una cita), así que
    exigirle subcadena literal completa sería demasiado estricto. Pero un número o
    nombre propio que aparece en la síntesis y en NINGÚN span verificado es la señal
    más barata de alucinación — se registra como advertencia para revisión manual."""
    if not sintesis:
        return
    texto_spans = normalizar(" ".join(
        s.get("span", "") for h in hechos_validos for s in h.get("spans", [])
    ))
    for numero in _RE_NUMERO.findall(sintesis):
        if numero not in texto_spans:
            print(f"[fase3] ADVERTENCIA: número '{numero}' en síntesis sin span que lo respalde")
    for propio in _RE_PROPIO.findall(sintesis):
        if normalizar(propio) not in texto_spans:
            print(f"[fase3] ADVERTENCIA: nombre propio '{propio}' en síntesis sin span que lo respalde")


# =======================================================================
# Cliente LLM (DeepInfra, OpenAI-compatible) — POST no-streaming, con reintentos
# =======================================================================

class ErrorLLM(Exception):
    pass


class ErrorParseoJSON(ErrorLLM):
    """El JSON no parseó ni siquiera tras el reintento de llamar_llm_json. `crudo`
    guarda el texto de la respuesta que falló (la del reintento), para que main()
    pueda imprimirlo y diagnosticar por qué salió malformado."""
    def __init__(self, mensaje, crudo):
        super().__init__(mensaje)
        self.crudo = crudo


def parsear_json_llm(texto):
    """Parseo tolerante: quita <think>...</think> y cercas ```json, y extrae el
    objeto entre la primera '{' y la última '}'. Los modelos de razonamiento a veces
    devuelven traza de pensamiento o markdown alrededor del JSON pedido."""
    t = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)
    t = re.sub(r"```(?:json)?", "", t)
    inicio, fin = t.find("{"), t.rfind("}")
    if inicio == -1 or fin == -1 or fin < inicio:
        raise ErrorLLM(f"No se encontró objeto JSON en la respuesta del LLM: {texto[:300]!r}")
    return json.loads(t[inicio:fin + 1])


def _llamar_llm_mensajes(mensajes):
    """POST no-streaming a DeepInfra con una lista de mensajes ya armada (permite el
    reintento multi-turno de llamar_llm_json). Reintenta con backoff exponencial en
    errores de red y HTTP 429 (transitorios). NO reintenta otros 4xx: un 400/401/422
    es un error del payload o las credenciales, y reintentarlo solo quema cupo sin
    arreglar nada."""
    url = f"{DEEPINFRA_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPINFRA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODELO,
        "temperature": TEMPERATURA,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "messages": mensajes,
    }

    ultimo_error = None
    for intento in range(MAX_REINTENTOS):
        try:
            resp = requests.post(url, headers=headers, json=payload,
                                  timeout=TIMEOUT_TOTAL, stream=False)
        except requests.exceptions.RequestException as e:
            ultimo_error = e
            time.sleep(BACKOFF_BASE ** intento)
            continue

        if resp.status_code == 429:
            ultimo_error = ErrorLLM(f"HTTP 429: {resp.text[:300]}")
            time.sleep(BACKOFF_BASE ** intento)
            continue
        if 400 <= resp.status_code < 500:
            raise ErrorLLM(f"HTTP {resp.status_code} (no reintentable): {resp.text[:500]}")
        if resp.status_code >= 500:
            ultimo_error = ErrorLLM(f"HTTP {resp.status_code}: {resp.text[:300]}")
            time.sleep(BACKOFF_BASE ** intento)
            continue

        data = resp.json()
        return data["choices"][0]["message"]["content"]

    raise ErrorLLM(f"Agotados {MAX_REINTENTOS} reintentos. Último error: {ultimo_error}")


def llamar_llm_json(system_prompt, user_prompt):
    """Llama al LLM y parsea la respuesta como JSON. Si el parseo falla (el modelo no
    devolvió JSON limpio), reintenta UNA vez en el mismo hilo de conversación
    pidiéndole explícitamente que corrija y devuelva solo el JSON — mismo patrón que
    los diag. Si el reintento también falla, propaga la excepción (la captura el
    llamador: analizar_par/analizar_cluster, o el try/except de main())."""
    mensajes = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    crudo = _llamar_llm_mensajes(mensajes)
    try:
        return parsear_json_llm(crudo)
    except (ErrorLLM, json.JSONDecodeError):
        mensajes.append({"role": "assistant", "content": crudo})
        mensajes.append({"role": "user", "content":
                          "Tu respuesta anterior no era JSON válido. Responde "
                          "ÚNICAMENTE el JSON pedido, sin markdown ni texto extra."})
        crudo_reintento = _llamar_llm_mensajes(mensajes)
        try:
            return parsear_json_llm(crudo_reintento)
        except (ErrorLLM, json.JSONDecodeError) as e:
            raise ErrorParseoJSON(str(e), crudo_reintento) from e


# =======================================================================
# Caché por hash (el corazón: evita re-analizar lo ya analizado)
# =======================================================================

def par_ya_existe(hash_a, hash_b):
    fila = (sb.table("comparaciones").select("id")
            .eq("hash_a", hash_a).eq("hash_b", hash_b).limit(1).execute().data)
    return bool(fila)


def cluster_key_de(hashes):
    """sha256 del set ordenado de hash_sha256 de los miembros del clúster. Determinista:
    mismo conjunto de artículos -> misma clave, sin importar el orden de entrada."""
    ordenados = sorted(set(hashes))
    return hashlib.sha256("|".join(ordenados).encode("utf-8")).hexdigest()


def cluster_ya_existe(cluster_key):
    fila = (sb.table("resumenes").select("id")
            .eq("cluster_key", cluster_key).limit(1).execute().data)
    return bool(fila)


# =======================================================================
# Filtro de rol
# =======================================================================

def filtrar_comparables(articulos):
    """Solo 'noticia' entra al análisis Fase 3. Opinión/editorial/análisis es reacción
    al hecho, no cobertura primaria del hecho — comparar esas contra 'noticia' mezclaría
    dos cosas distintas (mismo filtro de rol que usa clustering_fase2 para el núcleo)."""
    return [a for a in articulos if a["tipo"] == "noticia"]


# =======================================================================
# Construcción de prompts de usuario
# ---------------------------------------------------------------------
# "medio" en las respuestas del LLM es el slug del outlet (contrato de los tres
# prompts): por eso comparación/corroboración le pasan el slug de cada artículo,
# no su id/hash, y la verificación de spans matchea por slug.
#
# La síntesis es el caso especial: el LLM NO ve los artículos originales, solo los
# hechos_corroborados YA VERIFICADOS (formato exacto abajo) — así se garantiza que
# no pueda "recordar" nada que no haya sobrevivido el verificador de la pasada 1.
# =======================================================================

def _fecha_de(a):
    return a.get("fecha_publicacion") or a.get("fecha_captura") or ""


def _bloque_medio(a):
    return (f"MEDIO: {a['medio_slug']}\n"
            f"FECHA: {_fecha_de(a)}\n"
            f"TITULAR: {a['titulo']}\n\n"
            f"TEXTO:\n{a['contenido_visible'] or ''}")


def _prompt_usuario_comparacion(a, b):
    return _bloque_medio(a) + "\n\n---\n\n" + _bloque_medio(b)


def _prompt_usuario_corrobora(comparables):
    return "\n\n===\n\n".join(_bloque_medio(a) for a in comparables)


def _un_articulo_por_medio(articulos):
    """Colapsa a un artículo representativo por outlet (el más reciente, mismo
    criterio que colapsar_por_url en fase2). Los tres prompts asumen 'un medio, una
    versión' (comparación INTER-medio); la transitividad del clustering puede meter
    2+ artículos del mismo outlet en un clúster sin que se hayan comparado nunca
    entre sí. Sin este colapso, por_slug pisaría uno de los dos en silencio y el LLM
    vería dos bloques etiquetados con el mismo slug, sin forma de distinguirlos."""
    por_medio = {}
    for a in articulos:
        slug = a["medio_slug"]
        actual = por_medio.get(slug)
        if actual is None or _fecha_de(a) > _fecha_de(actual):
            por_medio[slug] = a
    return list(por_medio.values())


def _prompt_usuario_sintesis(hechos_validos):
    lineas = ["Fragmentos verificados sobre un mismo suceso. Escribí la síntesis. Responde SOLO el JSON.", ""]
    for i, hecho in enumerate(hechos_validos, start=1):
        medios = ", ".join(dict.fromkeys(s["medio"] for s in hecho["spans"]))
        lineas.append(f"HECHO {i} (reportado por {medios}):")
        for s in hecho["spans"]:
            lineas.append(f"   - «{s['span']}»")
    return "\n".join(lineas)


# =======================================================================
# Análisis
# =======================================================================

def analizar_par(article_a, article_b):
    """Compara dos artículos (mismo clúster, medios distintos). Cachea por par de
    hash ordenado (hash_a < hash_b). Devuelve dict listo para insertar en
    `comparaciones`, o None si el par ya está en caché o son el mismo hash."""
    if article_a["hash_sha256"] == article_b["hash_sha256"]:
        return None
    if article_a["medio_slug"] == article_b["medio_slug"]:
        return None  # comparación INTER-medio: mismo outlet no es un par válido
    a, b = ((article_a, article_b) if article_a["hash_sha256"] < article_b["hash_sha256"]
            else (article_b, article_a))
    hash_a, hash_b = a["hash_sha256"], b["hash_sha256"]

    if par_ya_existe(hash_a, hash_b):
        return None

    por_slug = {a["medio_slug"]: a, b["medio_slug"]: b}
    resultado = llamar_llm_json(SYS_COMPARACION, _prompt_usuario_comparacion(a, b))

    diferencias_validas = []
    for dif in resultado.get("diferencias", []):
        fuente = por_slug.get(dif.get("medio"))
        if fuente and span_valido(dif.get("span", ""), fuente["contenido_visible"] or ""):
            diferencias_validas.append(dif)

    return {
        "hash_a": hash_a,
        "hash_b": hash_b,
        "article_a": a["id"],
        "article_b": b["id"],
        "diferencias": diferencias_validas,
        "es_mismo_hecho": bool(resultado.get("es_mismo_hecho")),
        "divergencia_relevante": bool(resultado.get("divergencia_relevante")),
        "desfase_temporal": resultado.get("desfase_temporal"),
        "modelo": MODELO,
        "prompt_version": PROMPT_VERSION,
    }


def analizar_cluster(story_id, articulos):
    """Corre las dos pasadas de clúster (corroboración de hechos, luego síntesis)
    sobre los artículos 'noticia' de una story. Cachea por cluster_key (hash del set
    de hash_sha256 de los miembros). Devuelve dict listo para insertar en
    `resumenes`, o None si el clúster ya está en caché o tiene <2 comparables."""
    comparables = filtrar_comparables(articulos)
    if len(comparables) < 2:
        return None

    hashes = [a["hash_sha256"] for a in comparables]
    cluster_key = cluster_key_de(hashes)
    if cluster_ya_existe(cluster_key):
        return None

    representantes = _un_articulo_por_medio(comparables)
    if len(representantes) < 2:
        return None
    por_slug = {a["medio_slug"]: a for a in representantes}

    # Pasada 1: corroboración — ¿qué hechos confirman 2+ medios distintos?
    resultado_corrobora = llamar_llm_json(SYS_CORROBORA, _prompt_usuario_corrobora(representantes))

    hechos_validos = []
    for hecho in resultado_corrobora.get("hechos_corroborados", []):
        spans_validos = []
        medios_vistos = set()
        for s in hecho.get("spans", []):
            fuente = por_slug.get(s.get("medio"))
            if fuente is None:
                continue
            if span_valido(s.get("span", ""), fuente["contenido_visible"] or ""):
                spans_validos.append(s)
                medios_vistos.add(s["medio"])
        # Un hecho corroborado es válido solo si sobreviven spans de >=2 medios
        # distintos DESPUÉS del filtro verbatim (no antes: un solo medio con dos
        # spans no es corroboración cruzada).
        if len(medios_vistos) >= 2:
            hechos_validos.append({"spans": spans_validos})

    # "solo_un_medio" son igual de citables que los corroborados: mismo gate verbatim,
    # sin la exigencia de 2+ medios (por definición, es de uno solo).
    solo_un_medio_validos = []
    for item in resultado_corrobora.get("solo_un_medio", []):
        fuente = por_slug.get(item.get("medio"))
        if fuente and span_valido(item.get("span", ""), fuente["contenido_visible"] or ""):
            solo_un_medio_validos.append(item)

    # Pasada 2: síntesis — el LLM ve SOLO los spans ya verificados, nunca los artículos.
    resultado_sintesis = llamar_llm_json(SYS_SINTESIS, _prompt_usuario_sintesis(hechos_validos))
    sintesis_texto = resultado_sintesis.get("sintesis")

    _verificar_sintesis_parcial(sintesis_texto, hechos_validos)

    return {
        "cluster_key": cluster_key,
        "story_id": story_id,
        "article_ids": [a["id"] for a in comparables],
        "member_hashes": hashes,
        "hechos_corroborados": hechos_validos,
        "solo_un_medio": solo_un_medio_validos,
        "sintesis": sintesis_texto,
        "modelo": MODELO,
        "prompt_version": PROMPT_VERSION,
    }


# =======================================================================
# Escritura a Supabase
# =======================================================================

def guardar_comparacion(fila):
    try:
        sb.table("comparaciones").insert(fila).execute()
    except Exception as e:
        print(f"[fase3] ERROR guardando comparación {fila['hash_a'][:8]}/{fila['hash_b'][:8]}: {e}")


def guardar_resumen(fila):
    try:
        sb.table("resumenes").insert(fila).execute()
    except Exception as e:
        print(f"[fase3] ERROR guardando resumen de story {fila['story_id']}: {e}")


# =======================================================================
# Prueba manual sobre UN story_id (NO backfill, NO cron)
# =======================================================================

def cargar_story_y_articulos(story_id):
    story = sb.table("stories").select("id").eq("id", story_id).limit(1).execute().data
    if not story:
        raise SystemExit(f"No existe story_id={story_id}")
    filas = (sb.table("story_articles")
             .select("articles(id, url, titulo, contenido_visible, tipo, hash_sha256, "
                      "fecha_publicacion, fecha_captura, outlets(slug))")
             .eq("story_id", story_id).execute().data)
    articulos = []
    for f in filas:
        a = f.get("articles")
        if not a:
            continue
        a["medio_slug"] = (a.pop("outlets", None) or {}).get("slug")
        articulos.append(a)
    return articulos


def main():
    parser = argparse.ArgumentParser(
        description="Fase 3: análisis de comparación/resumen sobre UN story_id (prueba manual).")
    parser.add_argument("story_id", help="UUID de la story a analizar")
    args = parser.parse_args()

    articulos = cargar_story_y_articulos(args.story_id)
    comparables = filtrar_comparables(articulos)
    print(f"Story {args.story_id}: {len(articulos)} artículos, {len(comparables)} comparables (tipo=noticia)")

    guardados = saltados = fallidos = 0

    # Un ítem malo (JSON irrecuperable, red caída a mitad de corrida, lo que sea) no
    # puede tumbar el resto del análisis: se registra el fallo y se sigue con el
    # próximo par/clúster. El backfill real correrá sobre miles de pares; un solo
    # crash no puede volver a correr todo desde cero.
    for i in range(len(comparables)):
        for j in range(i + 1, len(comparables)):
            try:
                resultado = analizar_par(comparables[i], comparables[j])
            except Exception as e:
                fallidos += 1
                print(f"  par [{i},{j}] — FALLO: {e}")
                if isinstance(e, ErrorParseoJSON):
                    print(f"    crudo: {e.crudo[:300]!r}")
                continue
            if resultado is None:
                saltados += 1
                print(f"  par [{i},{j}] — skip (caché, mismo hash o mismo medio)")
                continue
            guardar_comparacion(resultado)
            guardados += 1
            print(f"  par [{i},{j}] — guardado")

    try:
        resumen = analizar_cluster(args.story_id, articulos)
    except Exception as e:
        fallidos += 1
        print(f"  resumen — FALLO: {e}")
        if isinstance(e, ErrorParseoJSON):
            print(f"    crudo: {e.crudo[:300]!r}")
    else:
        if resumen is None:
            saltados += 1
            print("resumen — skip (caché o <2 comparables)")
        else:
            guardar_resumen(resumen)
            guardados += 1
            print("resumen — guardado")

    print(f"\n{'='*40}\nGuardados: {guardados} | Skip: {saltados} | Fallidos: {fallidos}\n{'='*40}")


if __name__ == "__main__":
    main()
