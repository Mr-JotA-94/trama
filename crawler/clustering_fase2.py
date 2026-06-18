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
import math
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

# ---------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------

def _parse_embedding(v):
    """Supabase devuelve vector(384) como string '[...]' o como list. Normaliza a list[float]."""
    if isinstance(v, str):
        return json.loads(v)        # '[0.1,-0.2,...]' -> [0.1, -0.2, ...]
    return v                        # ya es lista (algún driver lo hace)

def cargar_articulos():
    """Trae artículos con embedding y entidades. Pagina para no reventar RAM."""
    filas, desde = [], 0
    while True:
        q = (sb.table("articles")
             .select("id, outlet_id, titulo, tipo, fecha_publicacion, fecha_captura, entidades, embedding")
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
    return filas

def cuando(a):
    f = a["fecha_publicacion"] or a["fecha_captura"]
    return datetime.fromisoformat(f.replace("Z", "+00:00"))

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
    centroide = np.mean([vecs[i] for i in ids], axis=0)

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
# Escritura (borra y reconstruye)
# ---------------------------------------------------------------------
def reescribir_stories(clusteres, por_id, idf):
    # Recalcular todo = limpiar derivados. NO toca articles.
    # PK es uuid: usamos un filtro is-not-null sobre una columna que toda fila tiene.
    sb.table("story_articles").delete().not_.is_("article_id", "null").execute()
    sb.table("stories").delete().not_.is_("id", "null").execute()

    for ids in clusteres:
        scores, anclas, ancla_principal = calcular_scores(ids, por_id, idf)
        fechas = [cuando(por_id[i]) for i in ids]

        story = sb.table("stories").insert({
            "titulo": por_id[ancla_principal]["titulo"],
            "fecha_inicio": min(fechas).isoformat(),
            "fecha_fin": max(fechas).isoformat(),
            "n_articulos": len(ids),
            "n_medios": len({por_id[i]["outlet_id"] for i in ids}),
        }).execute().data[0]

        filas = [{
            "story_id": story["id"],
            "article_id": i,
            "score_neutralidad": round(scores[i][0], 4),
            "score_cobertura": round(scores[i][1], 4),
            "score_divergencia": round(scores[i][2], 4),
            "es_ancla": i in anclas,
        } for i in ids]
        sb.table("story_articles").insert(filas).execute()

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