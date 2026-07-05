# crawler/clustering_fase2.py — Tier 2, load-bearing.
# Arma clústeres (stories) sobre el archivo completo. Recalcula TODO cada corrida:
# borra stories/story_articles y los reconstruye. NO toca articles (inmutable).
#
# Las dos compuertas validadas (sesión 2026-06-16):
#   candidato si: medios distintos + ±72h + peso_idf(entidades compartidas) >= UMBRAL_IDF
#   confirmado si además: similitud coseno >= UMBRAL_COSENO
# Ambos umbrales son PROVISIONALES (muestra de 2.5 días). Recalibrar con volumen.
#
# Correr a mano. Mirar los clústeres que produce y juzgarlos a ojo: ESE es el
# trabajo de validación de Fase 2 temprana, no la automatización.

import os
import re
import math
import uuid
from collections import defaultdict
from datetime import datetime

import json  
import numpy as np
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# --- Umbrales (las dos compuertas) ---
UMBRAL_IDF = 20.0       # peso mínimo de entidades compartidas (sustancia específica)
UMBRAL_COSENO = 0.70    # similitud mínima (mismo hecho, no solo mismo tema)
VENTANA_HORAS = 72      # filtro grueso de candidatos
SOLO_NOTICIAS = True    # solo 'noticia' forma clúster núcleo (§6). Opinión = reacción.

# Namespace fijo para uuid5 de stories. NUNCA cambiar: define la identidad
# de TODAS las historias. Si cambia, todos los enlaces /historia/[id] se
# rompen de golpe. Generado una vez (2026-06-21), constante para siempre.
NAMESPACE_STORIES = uuid.UUID("6f3a1c2e-7b4d-5a9e-8c1f-2d3e4f5a6b7c")

# --- Relaciones inter-clúster (story_relations) ---
# Config VALIDADA contra diag_relaciones v1-v4 (2026-06-25). NO apretar sin medir:
# cos>=0.55 tira Beto Coral (cos 0.544); subir n_esp puede tirar Air-e.
UMBRAL_N_ESPECIFICAS = 3      # MOTOR: específicas compartidas mínimas
GUARDIA_COSENO_REL   = 0.50   # GUARDIA: coseno entre centroides mínimo (load-bearing)
FRAC_GENERICA        = 0.08   # entidad en > este % de clústeres = genérica

# Limpieza CONGELADA desde diag v4. MITIGACIÓN TEMPORAL: el RUIDO_DURO de conectores es
# un parche por el NER básico de backfill. Se RETIRA con el re-backfill de NER (queda solo
# medios + genéricas-por-DF). NO crecer esta lista: ruido nuevo = señal de hacer el fix de
# NER, no de añadir aquí. El grafo NO se expone en la web hasta ese re-backfill.
RUIDO_DURO = {
    "además","asimismo","según","sin embargo","por su parte","no obstante","en cambio",
    "entre tanto","mientras tanto","de hecho","aun así","ahora","después","hay","bajo",
    "este","podría","fueron","siga","conozca","lea","encuentre","deje","felicito","más",
    "quién","la directora del","el proceso","la medida","la decisión","el decreto",
    "su defensa","su trayectoria","la ley","el comandante de las",
    "el presidente de estados unidos","el gobierno nacional","los hechos","las imágenes",
    "el anuncio","según las autoridades","la captura","información",
    "match electoral de el espectador",
    "el espectador","el tiempo","el colombiano","vorágine","las2orillas","noticias caracol",
}
GEOGRAFIA = {
    "amazonas","antioquia","arauca","atlántico","bolívar","boyacá","caldas","caquetá",
    "casanare","cauca","cesar","chocó","córdoba","cundinamarca","guainía","guaviare",
    "huila","la guajira","magdalena","meta","nariño","norte de santander","putumayo",
    "quindío","risaralda","santander","sucre","tolima","valle del cauca","valle","vaupés",
    "vichada","san andrés","providencia","caribe","el caribe","pacífico","pacífica",
    "andina","andino","orinoquía","amazonía","eje cafetero","los llanos","colombia",
    "de colombia","bogotá","bogotá d.c.",
}

ALIAS = {
    "ee. uu": "estados unidos", "ee.uu": "estados unidos", "ee uu": "estados unidos",
    "eeuu": "estados unidos", "estados unidos de américa": "estados unidos",
    "trump": "donald trump",
    "uribe": "álvaro uribe", "álvaro uribe vélez": "álvaro uribe",
    "petro": "gustavo petro",
    "abelardo": "abelardo de la espriella", "espriella": "abelardo de la espriella",
    "de la espriella": "abelardo de la espriella",
    "cepeda": "iván cepeda", "iván cepeda castro": "iván cepeda",
    "restrepo": "josé manuel restrepo",
    "germán": "germán vargas lleras", "germán vargas": "germán vargas lleras",
    "sarabia": "laura sarabia",
    "abadía": "juan carlos abadía",
    "amaya": "carlos amaya",
    "beto": "beto coral", "coral": "beto coral",
    "mordisco": "iván mordisco",
    "cne": "consejo nacional electoral",
    "moe": "misión de observación electoral",
    "jep": "jurisdicción especial para la paz",
    "sgc": "servicio geológico colombiano",
    "icbf": "instituto colombiano de bienestar familiar",
    "dirección de investigación criminal": "dijín", "investigación criminal": "dijín",
    "fiscalía general de la nación": "fiscalía", "fiscalía general": "fiscalía",
    "procuraduría general de la nación": "procuraduría", "procuraduría general": "procuraduría",
    "corte suprema de justicia": "corte suprema",
    "sala de instrucción": "corte suprema", "sala de casación penal": "corte suprema",
    "registraduría nacional": "registraduría",
    "registraduría nacional del estado civil": "registraduría",
    "policía": "policía nacional", "policía de colombia": "policía nacional",
    "ejército": "ejército nacional",
    "instituto de hidrología, meteorología y estudios ambientales": "ideam",
    "meteorología y estudios ambientales": "ideam",
}

GEO_EXTRA = {
    "estados unidos", "washington", "venezuela", "ecuador", "perú", "chile", "brasil",
    "argentina", "bolivia", "uruguay", "paraguay", "méxico", "panamá", "costa rica",
    "el salvador", "salvador", "guatemala", "honduras", "nicaragua", "cuba", "puerto rico",
    "italia", "españa", "francia", "alemania", "reino unido", "inglaterra", "portugal",
    "europa", "américa", "américa latina", "latinoamérica", "suramérica", "sudamérica",
    "centroamérica", "norteamérica", "aragua", "caracas", "miami", "arizona", "roma",
    "londres", "madrid", "canadá", "china", "rusia", "ucrania", "israel", "suecia",
}

_LEAD = re.compile(r"^(el|la|los|las|lo|en|de|del|al)\s+")

def canon(e):
    e = re.sub(r"\s+", " ", (e or "")).strip().lower()
    e = re.sub(r"^[^0-9a-záéíóúñü]+", "", e)
    e = e.strip(" .,;:¿?¡!\"'“”‘’`´")
    for _ in range(2):
        e2 = _LEAD.sub("", e)
        if e2 == e:
            break
        e = e2
    return ALIAS.get(e, e)

def ents_rel(lista):
    """Normalización para RELACIONES (diag v3/v4): colapsa espacios + strip + lower.
    SEPARADA de normaliza_ents (que alimenta las compuertas del clustering): no la
    tocamos para no perturbar el clustering validado."""
    out = {re.sub(r"\s+", " ", e).strip().lower() for e in (lista or [])}
    out.discard("")
    return out

def centroide_de_cluster(ids, por_id):
    """Centroide VOTO-POR-ARTÍCULO. Tras el split #2 (2026-06-28) la usa SOLO la
    guardia coseno de relaciones (PASADA 2); su calibración FRAC=0.08/guardia=0.50
    se midió contra ESTE centroide, por eso NO se toca. La neutralidad/ancla usa
    centroide_neutralidad. Asume ids ya colapsados por URL en carga (ARQUITECTURA 2026-06-23)."""
    return np.mean([np.asarray(por_id[i]["embedding"]) for i in ids], axis=0)

def centroide_neutralidad(ids, por_id):
    """Centroide UN-VOTO-POR-MEDIO, SOLO para neutralidad/ancla en calcular_scores.
    Promedia primero dentro de cada medio, luego entre medios: un medio de alto
    volumen ya no arrastra el centro (fix #2; diag 2026-06-28: 23 anclas cambian,
    de-sesgo hacia medios subrepresentados como Las2orillas). NO la usa la guardia
    de relaciones — esa sigue con centroide_de_cluster (voto-por-artículo)."""
    por_medio = {}
    for i in ids:
        por_medio.setdefault(por_id[i]["outlet_id"], []).append(
            np.asarray(por_id[i]["embedding"]))
    return np.mean([np.mean(v, axis=0) for v in por_medio.values()], axis=0)

# ---------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------

def _parse_embedding(v):
    """Supabase devuelve vector(384) como string '[...]' o como list. Normaliza a list[float]."""
    if isinstance(v, str):
        return json.loads(v)        # '[0.1,-0.2,...]' -> [0.1, -0.2, ...]
    return v                        # ya es lista (algún driver lo hace)

def colapsar_por_url(articulos):
    """Colapsa capturas a artículos únicos. El átomo de Trama es la url, no la
    captura: una nota editada genera filas nuevas (hash distinto, inmutabilidad),
    pero es UN artículo. Representante = última captura (estado actual de la nota),
    coherente con colapsarCluster.js del frontend. Colapsar AQUÍ —antes de IDF,
    aristas y scores— hace que TODO el pipeline opere sobre el átomo correcto sin
    tocar nada más: el conteo, el centroide y las compuertas heredan urls únicos.
    Una nota muy editada ya no pesa Nx en el centroide ni infla n_articulos."""
    por_url = {}
    for a in articulos:
        u = a["url"]
        if u not in por_url or a["fecha_captura"] > por_url[u]["fecha_captura"]:
            por_url[u] = a
    return list(por_url.values())

def cargar_articulos():
    """Trae artículos con embedding y entidades. Pagina para no reventar RAM."""
    filas, desde = [], 0
    while True:
        q = (sb.table("articles")
             .select("id, outlet_id, url, titulo, tipo, fecha_publicacion, fecha_captura, entidades, embedding")
             .not_.is_("embedding", "null")
             .range(desde, desde + 999)
             .execute().data)
        if not q:
            break
        filas.extend(q)
        desde += 1000
    # Normalizar embeddings de string a lista UNA vez, al cargar.
    for a in filas:
        a["embedding"] = np.asarray(_parse_embedding(a["embedding"]), dtype=np.float32)
    filas = colapsar_por_url(filas) 
    return filas

def cuando(a):
    f = a["fecha_publicacion"] or a["fecha_captura"]
    return datetime.fromisoformat(f.replace("Z", "+00:00"))

def uuid_estable(ids, por_id):
    """UUID determinista de un clúster: uuid5 sembrado en la url del
    artículo más antiguo. Determinismo total: desempata por url cuando dos
    artículos comparten fecha (sin esto, el 'más antiguo' lo decidiría el
    orden de iteración → uuid inestable). El url es permanente (nunca se
    borra), así que mientras el artículo más antiguo siga en el clúster, el
    id no cambia entre corridas."""
    semilla = min(ids, key=lambda i: (cuando(por_id[i]), por_id[i]["url"]))
    return str(uuid.uuid5(NAMESPACE_STORIES, por_id[semilla]["url"]))

def normaliza_ents(lista):
    """Set de entidades en minúsculas para comparar."""
    return {e.lower() for e in (lista or [])}

# ---------------------------------------------------------------------
# IDF sobre TODO el archivo (no sobre muestra: ahora sí es producción)
# ---------------------------------------------------------------------
def calcular_idf(articulos):
    N = len(articulos)
    df = defaultdict(int)
    for a in articulos:
        for e in normaliza_ents(a["entidades"]):
            df[e] += 1
    return {e: math.log(N / c) for e, c in df.items()}, N

def peso_compartidas(ents_a, ents_b, idf):
    comp = ents_a & ents_b
    return sum(idf.get(e, 0.0) for e in comp), comp

# ---------------------------------------------------------------------
# Construcción de clústeres por componentes conexas
# ---------------------------------------------------------------------
# Cada par que pasa las DOS compuertas es una arista. Los clústeres son las
# componentes conexas del grafo resultante (union-find). Decisión clave:
# transitividad. Si A~B y B~C pero A no se comparó alto con C, igual quedan
# juntos. Es lo correcto para "mismo hecho": si tres medios cubren un evento,
# forman una sola historia aunque dos de ellos redacten muy distinto.

class UnionFind:
    def __init__(self, ids):
        self.padre = {i: i for i in ids}
    def find(self, x):
        while self.padre[x] != x:
            self.padre[x] = self.padre[self.padre[x]]  # path compression
            x = self.padre[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.padre[ra] = rb

def coseno(va, vb):
    a, b = np.asarray(va), np.asarray(vb)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))

def construir_clusteres(articulos, idf):
    if SOLO_NOTICIAS:
        articulos = [a for a in articulos if a["tipo"] == "noticia"]
    print(f"Artículos núcleo (noticia): {len(articulos)}")

    ents = {a["id"]: normaliza_ents(a["entidades"]) for a in articulos}
    por_id = {a["id"]: a for a in articulos}
    uf = UnionFind([a["id"] for a in articulos])

    aristas = 0
    n = len(articulos)
    for i in range(n):
        a = articulos[i]
        for j in range(i + 1, n):
            b = articulos[j]
            if a["outlet_id"] == b["outlet_id"]:
                continue
            if abs((cuando(a) - cuando(b)).total_seconds()) > VENTANA_HORAS * 3600:
                continue
            # Compuerta 1: entidades
            peso, _ = peso_compartidas(ents[a["id"]], ents[b["id"]], idf)
            if peso < UMBRAL_IDF:
                continue
            # Compuerta 2: semántica
            if coseno(a["embedding"], b["embedding"]) < UMBRAL_COSENO:
                continue
            uf.union(a["id"], b["id"])
            aristas += 1

    print(f"Aristas que pasan las dos compuertas: {aristas}")

    # Agrupar por raíz
    grupos = defaultdict(list)
    for a in articulos:
        grupos[uf.find(a["id"])].append(a["id"])
    # Solo clústeres de 2+ medios distintos (un clúster de un solo medio no es
    # "cobertura cruzada"; queda como clúster de tamaño 1, lo ignoramos por ahora).
    clusteres = []
    for raiz, ids in grupos.items():
        medios = {por_id[i]["outlet_id"] for i in ids}
        if len(ids) >= 2 and len(medios) >= 2:
            clusteres.append(ids)
    return clusteres, por_id

# ---------------------------------------------------------------------
# Los tres scores (contrato §6)
# ---------------------------------------------------------------------
def calcular_scores(ids, por_id, idf):
    """Devuelve (scores, anclas, ancla_principal).
    scores: dict id -> (neutralidad, cobertura, divergencia).
    anclas: set de ids ancla (principal + divergente).
    ancla_principal: id de la card ancla principal (la que ganó el gate)."""
    vecs = {i: np.asarray(por_id[i]["embedding"]) for i in ids}
    centroide = centroide_neutralidad(ids, por_id)

    # Entidades del clúster (unión), para cobertura
    ents_cluster = set()
    for i in ids:
        ents_cluster |= normaliza_ents(por_id[i]["entidades"])

    scores = {}
    for i in ids:
        v = vecs[i]
        # neutralidad: cercanía al centroide (1 = idéntico al centro)
        neutr = float(v @ centroide / (np.linalg.norm(v) * np.linalg.norm(centroide)))
        # cobertura: qué fracción de entidades del clúster menciona
        cob = len(normaliza_ents(por_id[i]["entidades"]) & ents_cluster) / max(len(ents_cluster), 1)
        # divergencia: 1 - máxima similitud con cualquier otro del clúster
        sims = [float(v @ vecs[j] / (np.linalg.norm(v) * np.linalg.norm(vecs[j])))
                for j in ids if j != i]
        diverg = 1.0 - max(sims) if sims else 0.0
        scores[i] = (neutr, cob, diverg)

    # Ancla principal: GATE de neutralidad + desempate por cobertura.
    # Multiplicar neutr*cob fallaba en clústeres grandes: neutr es casi constante
    # (~0.8-0.95) y cob de alta varianza, así que el producto ordenaba de facto
    # por cobertura y dejaba anclar una REACCIÓN editorializada que satura las
    # entidades centrales (caso Chalá, medido 2026-06-17). Separar las preguntas:
    # primero "¿es central?" (piso p75 de neutralidad del clúster), luego entre
    # los que pasan "¿es el más completo?" (mayor cobertura). Umbral p75 PROVISIONAL,
    # calibrado sobre 2.5 días dominados por un macro-tema. Recalibrar con volumen.
    neutrs = sorted(scores[i][0] for i in ids)
    k = (len(neutrs) - 1) * 0.75
    lo = int(k); hi = min(lo + 1, len(neutrs) - 1)
    piso_neutr = neutrs[lo] + (neutrs[hi] - neutrs[lo]) * (k - lo)

    candidatos = [i for i in ids if scores[i][0] >= piso_neutr] or list(ids)
    por_central = sorted(candidatos, key=lambda i: scores[i][1], reverse=True)
    por_diverg = sorted(ids, key=lambda i: scores[i][2], reverse=True)
    anclas = {por_central[0]}
    for i in por_diverg:
        if i not in anclas:
            anclas.add(i)
            break
    # Devolvemos la ancla principal EXPLÍCITA (la que ganó el gate). No se
    # reelige fuera con neutr*cob: esa fórmula vieja era justo el bug (Chalá).
    # `anclas` incluye además la divergente, que NO pasó necesariamente el gate.
    return scores, anclas, por_central[0]

# ---------------------------------------------------------------------
# Escritura (upsert de stories + reconstrucción de derivados)
# ---------------------------------------------------------------------
def reescribir_stories(clusteres, por_id, idf):
    # sid por clúster, calculado UNA vez (uuid_estable es determinista: mismo
    # clúster -> mismo id). Se necesita antes de tocar la BD para saber qué
    # stories existentes ya no corresponden a ningún clúster de esta corrida.
    sids = [uuid_estable(ids, por_id) for ids in clusteres]
    sids_actuales = set(sids)
    existentes = {fila["id"] for fila in sb.table("stories").select("id").execute().data}
    huerfanas = list(existentes - sids_actuales)

    # Borrado de derivados (NO toca articles). story_relations/story_articles se
    # recomputan enteros cada corrida (scores y aristas cambian aunque la story
    # sobreviva) — delete-then-insert total sigue siendo aceptable ahí: ninguna
    # tabla externa tiene FK hacia ellas (deuda ya registrada en BITACORA,
    # aceptada, fuera de alcance de esta unidad).
    # `stories` YA NO se borra entera: eso es lo que rompía la identidad estable
    # (uuid5) y el FK de analyses en el caso común. Se PODA de forma acotada:
    # solo las huérfanas (ids que ya no salen de ningún clúster de esta corrida).
    # Esta poda acotada es el único punto donde el ON DELETE SET NULL de
    # analyses.story_id entra en juego.
    sb.table("story_relations").delete().not_.is_("origen_id", "null").execute()
    sb.table("story_articles").delete().not_.is_("article_id", "null").execute()
    for k in range(0, len(huerfanas), 500):
        sb.table("stories").delete().in_("id", huerfanas[k:k + 500]).execute()

    # Uniones de entidades por clúster (para genéricas-por-DF de CLÚSTER).
    ents_union = []
    for ids in clusteres:
        u = set()
        for i in ids:
            u |= {ce for e in (por_id[i]["entidades"] or []) if (ce := canon(e))}
        ents_union.append(u)

    n_cl = len(clusteres)
    df_cl = defaultdict(int)
    for u in ents_union:
        for e in u:
            df_cl[e] += 1
    umbral_gen = max(2, int(FRAC_GENERICA * n_cl))
    GENERICAS = {e for e, c in df_cl.items() if c >= umbral_gen}

    def es_especifica(e):
        return e not in RUIDO_DURO and e not in GEOGRAFIA and e not in GEO_EXTRA and e not in GENERICAS

    # PASADA 1: stories (upsert) + story_articles; stashear (sid, centroide, específicas).
    nodos = []
    for sid, ids, u in zip(sids, clusteres, ents_union):
        scores, anclas, ancla_principal = calcular_scores(ids, por_id, idf)
        fechas = [cuando(por_id[i]) for i in ids]

        sb.table("stories").upsert({
            "id": sid,
            "titulo": por_id[ancla_principal]["titulo"],
            "fecha_inicio": min(fechas).isoformat(),
            "fecha_fin": max(fechas).isoformat(),
            "n_articulos": len(ids),
            "n_medios": len({por_id[i]["outlet_id"] for i in ids}),
        }, on_conflict="id").execute()

        sb.table("story_articles").insert([{
            "story_id": sid, "article_id": i,
            "score_neutralidad": round(scores[i][0], 4),
            "score_cobertura": round(scores[i][1], 4),
            "score_divergencia": round(scores[i][2], 4),
            "es_ancla": i in anclas,
        } for i in ids]).execute()

        esp = {canon(e) for e in u if es_especifica(canon(e))}
        nodos.append((sid, centroide_de_cluster(ids, por_id), esp))

    # PASADA 2: aristas espejo (story_relations). Motor n_especificas, guardia coseno.
    rel_filas = []
    for x in range(len(nodos)):
        sid_a, cen_a, esp_a = nodos[x]
        for y in range(x + 1, len(nodos)):
            sid_b, cen_b, esp_b = nodos[y]
            comp = esp_a & esp_b
            if len(comp) < UMBRAL_N_ESPECIFICAS:
                continue
            cos = coseno(cen_a, cen_b)
            if cos < GUARDIA_COSENO_REL:
                continue
            ev, n, c = sorted(comp), len(comp), round(cos, 4)
            rel_filas.append({"origen_id": sid_a, "destino_id": sid_b,
                              "n_especificas": n, "coseno": c, "entidades_compartidas": ev})
            rel_filas.append({"origen_id": sid_b, "destino_id": sid_a,
                              "n_especificas": n, "coseno": c, "entidades_compartidas": ev})
    for k in range(0, len(rel_filas), 500):
        sb.table("story_relations").insert(rel_filas[k:k+500]).execute()
    print(f"story_relations: {len(rel_filas)//2} pares ({len(rel_filas)} filas espejo)")

# ---------------------------------------------------------------------
def main():
    print("Cargando archivo...")
    articulos = cargar_articulos()
    print(f"Artículos con embedding: {len(articulos)}")

    idf, N = calcular_idf(articulos)
    clusteres, por_id = construir_clusteres(articulos, idf)

    print(f"\n{'='*60}")
    print(f"Clústeres formados (2+ artículos, 2+ medios): {len(clusteres)}")
    tamanos = sorted((len(c) for c in clusteres), reverse=True)
    print(f"Tamaños: {tamanos}")
    print(f"Artículos clusterizados: {sum(tamanos)} de {len(articulos)} noticias")
    print(f"{'='*60}\n")

    reescribir_stories(clusteres, por_id, idf)
    print("stories/story_articles reescritos. Revisá con el query de inspección.")

if __name__ == "__main__":
    main()