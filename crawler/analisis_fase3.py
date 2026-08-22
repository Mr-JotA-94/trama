# crawler/analisis_fase3.py — Tier 2, load-bearing.
# Fase 3 v1: comparación inter-medio (por par) + corroboración/síntesis por día
# (ventana-día, resumenes_dia), vía LLM (DeepInfra). El análisis es caché derivado:
# idempotente, keyed por hash de contenido — se puede borrar `comparaciones`/
# `resumenes_dia` y reconstruir sin perder nada (el archivo fuente en `articles` es la verdad).
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
from collections import defaultdict
from datetime import datetime, timezone, date, timedelta
from itertools import combinations
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(override=True)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
# Proveedor LLM vía OpenRouter (capa de acceso a GLM-5.2 con routing multi-proveedor).
# En Actions, OPENROUTER_API_KEY viene de Secrets; en local, del .env.
LLM_API_KEY = os.environ["OPENROUTER_API_KEY"]
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# --- Config del modelo ---
MODELO = "z-ai/glm-5.2"   # slug de OpenRouter (NO "zai-org/GLM-5.2", que es el de DeepInfra directo)
# Routing forense: DeepInfra (proveedor del bake-off original) preferido; Cloudflare y Baidu
# como failover validados (2026-08-11, forense-equivalentes). allow_fallbacks=False: si estos
# tres caen, falla limpio en vez de rutear a un backend no validado (varianza forense no controlada).
LLM_PROVIDER = {"order": ["deepinfra", "cloudflare", "baidu"], "allow_fallbacks": False}
TEMPERATURA = 0.15
MAX_TOKENS = 16000
PROMPT_VERSION = "v2"   # v2: SYS_CORROBORA pasa de "máximo 5" (cuota) a techo-con-prioridad
                        # (hasta 6/4, ordenado por fuerza de corroboración, sin relleno).

TIMEOUT_TOTAL = 300       # segundos, timeout total. 300 (subido de 120): la corroboración de días densos (4+ medios sobre evento masivo) rebasa 120s de generación — medido en 6678516b día 2026-07-20.
MAX_REINTENTOS = 4
BACKOFF_BASE = 2          # segundos: 2, 4, 8, 16...

MIN_PALABRAS_SPAN = 6     # piso de longitud para que un span cuente como cita real,
                           # no una coincidencia trivial de 2-3 palabras comunes.

BOGOTA = ZoneInfo("America/Bogota")  # ventana temporal = día calendario en hora local

# ---------------------------------------------------------------------
# Prompts (system) — HARDCODEADOS a propósito (auditar el prompt exacto que produjo
# cada fila es parte del contrato de Fase 3). Validados en diagnóstico:
# SYS_COMPARACION viene de diag_v1_solospans.py (105 spans / 0 fabricación).
# SYS_CORROBORA viene de diag_bakeoff2.py (bakeoff que ganó GLM).
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
- Ordená los hechos de MAYOR a MENOR corroboración: primero los que confirman más medios, luego los que confirman menos. Incluí solo los hechos NUCLEARES que estructuran la noticia (qué pasó, dónde, a quién, cuántos), del más central al menos central.
- Techo, NO cuota: HASTA 6 hechos corroborados y HASTA 4 de un solo medio. Si el día tiene menos hechos centrales, devolvé menos: tres bien corroborados valen más que seis forzados. NO rellenes para llegar al tope.
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
    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODELO,
        "temperature": TEMPERATURA,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "reasoning": {"enabled": False},   # GLM-5.2 es de razonamiento; sin esto, content viene vacío
        "provider": LLM_PROVIDER,           # routing forense DeepInfra→Cloudflare→Baidu
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
    llamador: analizar_par/_corroborar_dia, o el try/except de main())."""
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
# "medio" en las respuestas del LLM es el slug del outlet (contrato de los prompts):
# por eso comparación/corroboración le pasan el slug de cada artículo, no su id/hash,
# y la verificación de spans matchea por slug.
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


def _un_articulo_por_medio(articulos):
    """Colapsa a un artículo representativo por outlet (el más reciente, mismo
    criterio que colapsar_por_url en fase2). Los prompts asumen 'un medio, una
    versión' (comparación INTER-medio); la transitividad del clustering puede meter
    2+ artículos del mismo outlet en un clúster sin que se hayan comparado nunca
    entre sí. Sin este colapso, por_slug pisaría uno de los dos en silencio y el LLM
    vería dos bloques etiquetados con el mismo slug, sin forma de distinguirlos."""
    por_medio = {}
    for a in articulos:
        slug = a["medio_slug"]
        actual = por_medio.get(slug)
        # Desempate TOTAL por hash: cuando dos capturas del mismo medio en la misma
        # ventana comparten _fecha_de exacta (recaptura sin cambio de fecha_publicacion),
        # el '>' estricto dejaba el ganador al orden de entrada -> conjunto de pares no
        # determinista -> el caché reanudable no reconoce el trabajo previo. Con la tupla
        # (fecha, hash) el orden es total e independiente del input; cuando las fechas
        # difieren, la fecha domina y el comportamiento es idéntico al anterior.
        if actual is None or (_fecha_de(a), a["hash_sha256"]) > (_fecha_de(actual), actual["hash_sha256"]):
            por_medio[slug] = a
    return list(por_medio.values())


# =======================================================================
# Selección de pares (ventana temporal + colapso 1-por-medio-por-ventana)
# ---------------------------------------------------------------------
# La comparación exhaustiva C(n,2) sobre todo el clúster es INVIABLE a escala
# (costo cuadrático: un clúster de 249 artículos = 30.876 pares) Y produce
# divergencias falsas: comparar una nota temprana contra una tardía del mismo
# hilo confunde "la historia se movió" con "los medios divergen" (confound
# temporal, patrón 3, guardarraíl obligatorio de v1).
#
# Dos defensas, con roles distintos (no confundir):
#   - La VENTANA (día calendario Bogotá) ataca el confound temporal: solo se
#     comparan versiones contemporáneas.
#   - El COLAPSO 1-por-medio-por-ventana ataca el costo: techo duro C(medios,2)
#     por ventana = C(7,2)=21 pares como máximo, por aritmética, no por umbral.
#
# Medido sobre el corpus real (diag_ventanas, 2026-07-29): exhaustivo 35.174
# pares (~322h LLM) -> este esquema 973 pares (~9h). Corte de medianoche = 0
# pares perdidos en el corpus actual (ciclo de publicación diurno); re-medir a
# escala antes de asumir que sigue en 0.
# =======================================================================

def _dia_bogota(a):
    """Día calendario (date) en America/Bogota del artículo, clave de ventana.
    Mismo criterio de fecha que el resto del módulo (_fecha_de: publicación, con
    captura como fallback) y mismo parseo que clustering_fase2.cuando(). Supabase
    devuelve timestamptz con zona; si por lo que sea llega un naive, se asume UTC
    (lo que Supabase almacena) para no depender de la hora local de la máquina —
    en CI eso sería UTC, en local la de Jota, y las ventanas divergirían."""
    iso = _fecha_de(a)
    if not iso:
        # Sin ninguna fecha (0% del corpus medido). No se pierde: cae en una
        # ventana sentinela común, donde se compara exhaustivamente con los otros
        # sin fecha. Caso degenerado y raro; se avisa para que no pase inadvertido.
        print(f"[fase3] ADVERTENCIA: artículo {a.get('id')} sin fecha; ventana sentinela")
        return date.min
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # MEDIDO 2026-08-22: fecha_publicacion llega SIEMPRE como fecha SIN HORA,
    # normalizada a medianoche UTC (15.064/15.064, 100% en los 7 medios).
    # Convertir de zona una fecha que no tiene hora es un error de categoría:
    # le resta el offset de Bogotá (-5h) y la corre al día ANTERIOR. Si no trae
    # hora, la fecha ya ES el día declarado por el medio: se toma tal cual.
    # El fallback a fecha_captura sí trae hora real y sigue convirtiéndose normal.
    # Residual aceptado: una nota publicada exactamente a las 00:00:00.000000 UTC
    # quedaría un día adelante. Frecuencia ~0; la alternativa fallaba el 100%.
    en_utc = dt.astimezone(timezone.utc)
    if (en_utc.hour, en_utc.minute, en_utc.second, en_utc.microsecond) == (0, 0, 0, 0):
        return en_utc.date()
    return dt.astimezone(BOGOTA).date()


def pares_por_ventana(comparables):
    """Genera los pares (a, b) a comparar bajo el esquema ventana-día + colapso.
    Agrupa por día-Bogotá; dentro de cada día colapsa a un artículo por medio (el
    más reciente, vía _un_articulo_por_medio) y emite C(medios,2) de esa ventana.

    Rinde pares crudos: analizar_par sigue siendo el dueño del descarte mismo-medio/
    mismo-hash y del caché por (hash_a,hash_b). Aquí NO se filtra ni se cachea — esta
    función solo decide QUÉ pares existen; la unicidad y la idempotencia viven abajo.
    Función pura y determinista: el backfill/cron futuro la reutiliza tal cual."""
    ventanas = defaultdict(list)
    for a in comparables:
        ventanas[_dia_bogota(a)].append(a)
    for dia in sorted(ventanas):
        representantes = _un_articulo_por_medio(ventanas[dia])
        for x, y in combinations(representantes, 2):
            yield x, y


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


# =======================================================================
# Síntesis por día (digest por ventana-día con atribución de medios)
# ---------------------------------------------------------------------
# Reemplaza la corroboración+síntesis por clúster (función retirada, tabla `resumenes`:
# sobre hilos largos daba timeout y corroboraba mal). Cada día del clúster
# recibe su propio digest breve, con los CUERPOS COMPLETOS de ese día (todas las voces,
# colapsadas por URL). Validado en diag_sintesis_por_dia (2026-07-31): cero F5 intra-día
# sobre el caso Popayán, sin structural collapse hasta 234k chars/día (Louvain NO es
# prerequisito), longitud variable según densidad del día (aceptada por diseño).
# Idempotente por dia_key: se salta los días ya analizados.
# =======================================================================

SYS_SINTESIS_DIA = """Eres un redactor de una hemeroteca forense. Recibes los ARTÍCULOS COMPLETOS que varios medios colombianos publicaron EN UN MISMO DÍA sobre una misma historia en desarrollo. Escribí una síntesis BREVE de lo que se movió ESE día.

EXTENSIÓN: máximo 2-3 frases (unas 50 palabras). Si el día tuvo poco, una sola frase.

LÍMITES (de veracidad, no de estilo):
- Usá ÚNICAMENTE información de los textos provistos. Nada de fuera.
- No inventes ni ajustes cifras, fechas, lugares ni nombres. Copiá las cifras tal como aparecen.
- Si afirmás que algo CAUSÓ o llevó a otra cosa, esa relación debe estar afirmada en los textos de ESTE día. Si no explican el porqué, decí qué pasó SIN causa. No rellenes causas.
- Es la foto de UN día: NO anticipes lo que pasará después, NO expliques antecedentes que no estén en estos textos. Solo lo que se reportó hoy.
- Sin adjetivos de valoración; tono factual y sobrio.

FORMATO — responde ÚNICAMENTE este JSON, sin markdown ni texto extra:
{"sintesis": "máximo 2-3 frases"}"""


def _dia_key(member_hashes):
    """Idempotencia del día: sha256 del set ordenado de hash_sha256 de los artículos del día.
    Mismo día, mismos artículos -> misma clave -> no se re-analiza."""
    ordenados = sorted(set(member_hashes))
    return hashlib.sha256("|".join(ordenados).encode("utf-8")).hexdigest()


def dia_ya_existe(dia_key):
    fila = (sb.table("resumenes_dia").select("id, story_id")
            .eq("dia_key", dia_key).limit(1).execute().data)
    return fila[0] if fila else None


def _colapsar_por_url_dia(articulos):
    """Colapsa capturas a artículos únicos DENTRO del día (una nota editada = varias capturas,
    mismo url, hash distinto; representante = última captura). El átomo es la url, igual que
    clustering_fase2.colapsar_por_url."""
    por_url = {}
    for a in articulos:
        u = a["url"]
        clave = a.get("fecha_captura") or _fecha_de(a)
        if u not in por_url or clave > (por_url[u].get("fecha_captura") or _fecha_de(por_url[u])):
            por_url[u] = a
    return list(por_url.values())


def _prompt_sintesis_dia(arts_dia):
    bloques = "\n\n===\n\n".join(_bloque_medio(a) for a in arts_dia)
    return ("Artículos completos publicados el MISMO día sobre una historia en desarrollo. "
            "Escribí la síntesis breve de ese día. Responde SOLO el JSON.\n\n" + bloques)


def _prompt_corrobora_dia(por_medio):
    """Un bloque por MEDIO. Si el medio publicó varias notas ese día, se unen en su bloque:
    el corroborador sigue viendo 'un medio, una voz' (premisa de SYS_CORROBORA) SIN perder
    los sub-hechos de las notas secundarias."""
    bloques = []
    for slug, arts in por_medio.items():
        partes = [f"TITULAR: {a['titulo']}\n\nTEXTO:\n{a['contenido_visible'] or ''}" for a in arts]
        cuerpo = "\n\n--- (otra nota del mismo medio, mismo día) ---\n\n".join(partes)
        bloques.append(f"MEDIO: {slug}\nFECHA: {_fecha_de(arts[0])}\n\n{cuerpo}")
    return "\n\n===\n\n".join(bloques)


def _corroborar_dia(por_medio):
    """por_medio: {slug: [notas del medio ese día]}. Corrobora entre medios DISTINTOS. El gate
    valida cada span contra el texto UNIDO de todas las notas de su medio ese día (así un hecho
    que aparece en una nota secundaria del medio también cuenta). Un hecho corroborado sobrevive
    solo con spans verbatim de >=2 medios."""
    texto_por_medio = {slug: " ".join((a["contenido_visible"] or "") for a in arts)
                       for slug, arts in por_medio.items()}
    resultado = llamar_llm_json(SYS_CORROBORA, _prompt_corrobora_dia(por_medio))

    hechos_validos = []
    for hecho in resultado.get("hechos_corroborados", []):
        spans_validos, medios_vistos = [], set()
        for s in hecho.get("spans", []):
            fuente = texto_por_medio.get(s.get("medio"))
            if fuente and span_valido(s.get("span", ""), fuente):
                spans_validos.append(s)
                medios_vistos.add(s["medio"])
        if len(medios_vistos) >= 2:
            hechos_validos.append({"spans": spans_validos})

    solo = []
    for item in resultado.get("solo_un_medio", []):
        fuente = texto_por_medio.get(item.get("medio"))
        if fuente and span_valido(item.get("span", ""), fuente):
            solo.append(item)
    return hechos_validos, solo


def procesar_dia(story_id, articulos):
    """Por cada ventana-día del clúster: (1) síntesis destrabada (cuerpos completos del día) y
    (2) corroboración por día (spans verbatim de 2+ medios). Una fila completa por día en
    resumenes_dia, idempotente por dia_key: salta los días ya guardados. Reemplaza a la
    corroboración-por-clúster monolítica (resumenes), que sobre hilos largos daba timeout y
    corroboraba mal (un representante por medio de semanas). Devuelve (guardados, saltados,
    adoptados, fallidos): un día que agota los reintentos del LLM se registra como fallo y el
    bucle sigue con el resto de los días."""
    comparables = filtrar_comparables(articulos)
    por_dia = defaultdict(list)
    for a in comparables:
        por_dia[_dia_bogota(a)].append(a)

    guardados = saltados = adoptados = fallidos = 0
    for dia in sorted(por_dia):
        arts = _colapsar_por_url_dia(por_dia[dia])
        if not arts:
            continue
        hashes = sorted(a["hash_sha256"] for a in arts)
        clave = _dia_key(hashes)

        pasada = "?"
        try:
            fila = dia_ya_existe(clave)
            if fila:
                if fila["story_id"] == story_id:
                    saltados += 1
                    continue
                sb.table("resumenes_dia").update({"story_id": story_id}).eq("id", fila["id"]).execute()
                adoptados += 1
                print(f"    día {dia.isoformat()} — adoptado (sid previo obsoleto)")
                continue
            # Pasada 1: síntesis (todos los cuerpos del día; modo "redactar").
            pasada = "sintesis"
            r_sint = llamar_llm_json(SYS_SINTESIS_DIA, _prompt_sintesis_dia(arts))
            sintesis = (r_sint or {}).get("sintesis")

            # Pasada 2: corroboración (agrupada por medio; modo "copiar literal", gate verbatim).
            # Separada de la síntesis a propósito: redactar y citar son modos opuestos, mezclarlos
            # en un prompt reintroduce fabricación. Requiere 2+ medios para tener con qué corroborar.
            pasada = "corroboracion"
            por_medio = defaultdict(list)
            for a in arts:
                por_medio[a["medio_slug"]].append(a)
            hechos_validos, solo_un_medio = [], []
            if len(por_medio) >= 2:
                hechos_validos, solo_un_medio = _corroborar_dia(por_medio)

            guardar_resumen_dia({
                "story_id": story_id,
                "dia": dia.isoformat(),
                "dia_key": clave,
                "sintesis": sintesis,
                "hechos_corroborados": hechos_validos,
                "solo_un_medio": solo_un_medio,
                "article_ids": [a["id"] for a in arts],
                "member_hashes": hashes,
                "medios": sorted(por_medio.keys()),
                "modelo": MODELO,
                "prompt_version": PROMPT_VERSION,
            })
            guardados += 1
        except Exception as e:
            fallidos += 1
            print(f"    día {dia.isoformat()} pasada={pasada} — FALLO: {e}")
            continue
    return guardados, saltados, adoptados, fallidos


# =======================================================================
# Escritura a Supabase
# =======================================================================

def guardar_comparacion(fila):
    try:
        sb.table("comparaciones").insert(fila).execute()
    except Exception as e:
        print(f"[fase3] ERROR guardando comparación {fila['hash_a'][:8]}/{fila['hash_b'][:8]}: {e}")


def guardar_resumen_dia(fila):
    """Un día, un análisis vigente: al cambiar la composición del día (dia_key nuevo)
    la versión anterior se retira. resumenes_dia es análisis derivado y regenerable,
    NO archivo inmutable (esa regla aplica a articles). El DELETE va DESPUÉS del insert
    exitoso: si el insert falla, la versión previa sobrevive en vez de perderse el día."""
    nueva_id = None
    try:
        res = sb.table("resumenes_dia").insert(fila).execute()
        nueva_id = (res.data or [{}])[0].get("id")
    except Exception as e:
        print(f"[fase3] ERROR guardando resumen_dia {fila['story_id']} {fila['dia']}: {e}")
        return
    try:
        q = (sb.table("resumenes_dia").delete()
             .eq("story_id", fila["story_id"]).eq("dia", fila["dia"]))
        if nueva_id:
            q = q.neq("id", nueva_id)
        q.execute()
    except Exception as e:
        print(f"[fase3] AVISO: no se pudo retirar versión previa de {fila['dia']}: {e}")


# =======================================================================
# Análisis de una historia completa (pares + días) — compartido por main()
# (sid único) y backfill_activas (muchas historias).
# =======================================================================

def analizar_story(story_id, articulos, verbose=True):
    """Cuerpo de análisis de UNA historia: comparación por par (ventana-día) +
    síntesis/corroboración por día. Devuelve contadores en vez de imprimir el banner
    final: el llamador (main() o backfill_activas) decide cómo reportar. Con
    verbose=False se silencian los prints por-par y por-día (backfill corre sobre
    decenas de historias y no puede inundar el log con el detalle de cada una);
    con verbose=True (sid único) el output es idéntico al de antes del refactor."""
    comparables = filtrar_comparables(articulos)
    if verbose:
        print(f"Story {story_id}: {len(articulos)} artículos, {len(comparables)} comparables (tipo=noticia)")

    pares_guardados = pares_skip = fallidos = 0

    # Un ítem malo (JSON irrecuperable, red caída a mitad de corrida, lo que sea) no
    # puede tumbar el resto del análisis: se registra el fallo y se sigue con el
    # próximo par/clúster.
    pares = list(pares_por_ventana(comparables))
    if verbose:
        print(f"Pares a evaluar (ventana-día + colapso): {len(pares)} "
              f"(exhaustivo habría sido {len(comparables)*(len(comparables)-1)//2})")

    for x, y in pares:
        etq = f"{x['medio_slug']}×{y['medio_slug']} {x['hash_sha256'][:6]}/{y['hash_sha256'][:6]}"
        try:
            resultado = analizar_par(x, y)
        except Exception as e:
            fallidos += 1
            if verbose:
                print(f"  par {etq} — FALLO: {e}")
                if isinstance(e, ErrorParseoJSON):
                    print(f"    crudo: {e.crudo[:300]!r}")
            continue
        if resultado is None:
            pares_skip += 1
            if verbose:
                print(f"  par {etq} — skip (caché, mismo hash o mismo medio)")
            continue
        guardar_comparacion(resultado)
        pares_guardados += 1
        if verbose:
            print(f"  par {etq} — guardado")

    # Síntesis + corroboración por día (digest cronológico + hechos corroborados por
    # ventana). Idempotente por dia_key: re-correr salta los días ya hechos.
    dia_guardados = dia_skip = dia_adopt = 0
    try:
        g_dia, s_dia, a_dia, f_dia = procesar_dia(story_id, articulos)
        dia_guardados, dia_skip, dia_adopt = g_dia, s_dia, a_dia
        fallidos += f_dia
        if verbose:
            print(f"resúmenes por día — {g_dia} guardados, {s_dia} skip (caché), {a_dia} adoptados, {f_dia} fallidos")
    except Exception as e:
        fallidos += 1
        if verbose:
            print(f"  resúmenes por día — FALLO: {e}")
            if isinstance(e, ErrorParseoJSON):
                print(f"    crudo: {e.crudo[:300]!r}")

    return {
        "pares_guardados": pares_guardados,
        "pares_skip": pares_skip,
        "dia_guardados": dia_guardados,
        "dia_skip": dia_skip,
        "dia_adopt": dia_adopt,
        "fallidos": fallidos,
    }


# =======================================================================
# Backfill sobre historias activas (muchas historias, una corrida acotada en tiempo)
# =======================================================================

def _historias_activas(horas=72):
    """Story_ids con actividad reciente (fecha_captura de algún artículo dentro de
    las últimas `horas`), para que el backfill priorice lo que se está moviendo
    ahora. Orden: más recientes primero: a igual recencia, las historias con más
    notas tipo=noticia (más señal para corroborar/sintetizar).

    Trae solo las filas de story_articles cuyo artículo cae dentro de la ventana
    (join !inner + gte) y agrega en Python — evita traer el historial completo de
    story_articles solo para descartarlo. Pagina en bloques de 1000 (patrón del
    módulo: un .select() sin paginar se trunca en silencio)."""
    corte = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
    stats = {}  # story_id -> [max_fecha_captura, count_noticia]
    desde = 0
    while True:
        pagina = (sb.table("story_articles")
                  .select("story_id, articles!inner(fecha_captura, tipo)")
                  .gte("articles.fecha_captura", corte)
                  .range(desde, desde + 999).execute().data)
        if not pagina:
            break
        for fila in pagina:
            sid = fila["story_id"]
            art = fila.get("articles") or {}
            fecha = art.get("fecha_captura") or ""
            actual = stats.setdefault(sid, ["", 0])
            if fecha > actual[0]:
                actual[0] = fecha
            if art.get("tipo") == "noticia":
                actual[1] += 1
        if len(pagina) < 1000:
            break
        desde += 1000

    ordenados = sorted(stats.items(), key=lambda kv: (kv[1][0], kv[1][1]), reverse=True)
    return [sid for sid, _ in ordenados]


def backfill_activas(presupuesto_seg=19800, horas=72):
    """Corre analizar_story sobre todas las historias activas (últimas `horas`),
    con verbose=False (una línea de resumen por historia, no el detalle por-par/
    por-día). Presupuesto de tiempo con time.monotonic(): si se agota a mitad de
    la lista, corta limpio — no hay estado que perder, el caché por hash hace que
    la próxima corrida no repita el trabajo ya guardado. Cada historia en su
    propio try/except: una que revienta no mata el resto del backfill."""
    inicio = time.monotonic()
    sids = _historias_activas(horas=horas)
    n = len(sids)
    print(f"[fase3-backfill] {n} historias activas (últimas {horas}h)")

    hechas = saltadas_tiempo = falladas = 0
    total_dia_guardados = total_dia_adopt = 0

    for i, sid in enumerate(sids, 1):
        if time.monotonic() - inicio > presupuesto_seg:
            saltadas_tiempo = n - i + 1
            print(f"[fase3-backfill] presupuesto agotado: {saltadas_tiempo} historias sin "
                  f"procesar, se retoman en la próxima corrida")
            break
        try:
            articulos = cargar_story_y_articulos(sid)
            c = analizar_story(sid, articulos, verbose=False)
            hechas += 1
            total_dia_guardados += c["dia_guardados"]
            total_dia_adopt += c["dia_adopt"]
            print(f"  [{i}/{n}] {sid} — {c['dia_guardados']}d guardados, {c['dia_skip']}d skip, "
                  f"{c['dia_adopt']}d adopt, {c['fallidos']}f fallidos")
        except Exception as e:
            falladas += 1
            print(f"  [{i}/{n}] {sid} — FALLO: {e}")
            continue

    print(f"[fase3-backfill] {hechas} historias procesadas, {saltadas_tiempo} saltadas por "
          f"tiempo, {falladas} falladas — {total_dia_guardados} días guardados, "
          f"{total_dia_adopt} días adoptados")


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


def main(story_id):
    articulos = cargar_story_y_articulos(story_id)
    contadores = analizar_story(story_id, articulos, verbose=True)
    print(f"\n{'='*40}\n"
          f"Guardados: {contadores['pares_guardados']} | "
          f"Skip: {contadores['pares_skip']} | "
          f"Fallidos: {contadores['fallidos']}\n{'='*40}")


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Fase 3: análisis de comparación/resumen sobre UN story_id, "
                     "o --backfill sobre las historias activas recientes.")
    parser.add_argument("story_id", nargs="?", help="UUID de la story a analizar")
    parser.add_argument("--backfill", action="store_true",
                         help="Corre sobre historias activas en vez de un story_id puntual")
    parser.add_argument("--horas", type=int, default=72,
                         help="Ventana de actividad para --backfill, en horas (default 72)")
    parser.add_argument("--presupuesto", type=int, default=19800,
                         help="Presupuesto de tiempo para --backfill, en segundos (default 19800)")
    args = parser.parse_args()

    if args.backfill and args.story_id:
        parser.error("--backfill no acepta story_id (son modos mutuamente excluyentes)")
    if not args.backfill and not args.story_id:
        parser.error("falta story_id (o pasa --backfill)")
    return args


if __name__ == "__main__":
    args = _parse_args()
    if args.backfill:
        backfill_activas(presupuesto_seg=args.presupuesto, horas=args.horas)
    else:
        main(args.story_id)
