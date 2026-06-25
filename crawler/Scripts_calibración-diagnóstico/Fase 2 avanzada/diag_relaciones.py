# crawler/diag_relaciones.py — Tier 0, READ-ONLY, desechable.
# Diagnóstico para Fase 2 avanzada: ¿existe una "banda media" limpia que ligue
# clústeres RELACIONADOS sin fusionarlos? MIDE, no decide. No escribe a la base.
#
# Qué hace, en orden:
#   1. Carga artículos embebidos (igual que clustering_fase2.cargar_articulos).
#   2. Construye el IDF a nivel ARTÍCULO (idéntico al del clustering) para usar la
#      misma vara de "entidad rara = sustancia" un nivel arriba.
#   3. Lee los clústeres REALES de producción (stories + story_articles).
#   4. Por clúster: colapsa por url (defensivo), calcula centroide y unión de entidades.
#   5. Por cada PAR de clústeres: peso-IDF de entidades compartidas + coseno entre
#      centroides.
#   6. Imprime distribuciones + dos top-N (por coseno y por peso) para juzgar a ojo.
#
# OJO: los umbrales del clustering (IDF>=20, coseno>=0.70) son de pares de ARTÍCULOS.
# A nivel de clúster NO transfieren (centroide promedia -> achata coseno; unión de
# entidades es grande -> infla peso). Por eso medimos la distribución a nivel clúster
# ANTES de fijar cualquier corte de "relación".

import os
import math
import json
from collections import defaultdict

import numpy as np
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

TOP_N = 30  # cuántos pares candidatos imprimir por cada criterio para revisión a ojo


def _parse_embedding(v):
    return json.loads(v) if isinstance(v, str) else v


def normaliza_ents(lista):
    return {e.lower() for e in (lista or [])}


def cuando_captura(a):
    return a.get("fecha_captura") or a.get("fecha_publicacion") or ""


def coseno(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return 0.0 if na == 0 or nb == 0 else float(a @ b / (na * nb))


# ----------------------------------------------------------------------
# Carga
# ----------------------------------------------------------------------
def cargar_articulos():
    """Artículos con embedding (id, url, outlet_id, tipo, entidades, embedding,
    fecha_captura). Pagina para no reventar RAM, igual que el clustering."""
    filas, desde = [], 0
    while True:
        q = (sb.table("articles")
             .select("id, url, outlet_id, tipo, entidades, embedding, fecha_captura")
             .not_.is_("embedding", "null")
             .range(desde, desde + 999)
             .execute().data)
        if not q:
            break
        filas.extend(q)
        desde += 1000
    for a in filas:
        a["embedding"] = np.asarray(_parse_embedding(a["embedding"]), dtype=np.float32)
    return filas


def calcular_idf(articulos):
    """IDF a nivel artículo, idéntico a clustering_fase2.calcular_idf."""
    N = len(articulos)
    df = defaultdict(int)
    for a in articulos:
        for e in normaliza_ents(a["entidades"]):
            df[e] += 1
    return {e: math.log(N / c) for e, c in df.items()}, N


def cargar_story_articles():
    filas, desde = [], 0
    while True:
        q = (sb.table("story_articles")
             .select("story_id, article_id")
             .range(desde, desde + 999)
             .execute().data)
        if not q:
            break
        filas.extend(q)
        desde += 1000
    return filas


def cargar_stories():
    return (sb.table("stories")
            .select("id, titulo, n_articulos, n_medios")
            .execute().data)


# ----------------------------------------------------------------------
def main():
    print("Cargando artículos embebidos...")
    arts = cargar_articulos()
    por_id = {a["id"]: a for a in arts}
    idf, N = calcular_idf(arts)
    print(f"  artículos embebidos: {len(arts)} | entidades distintas en IDF: {len(idf)}")

    print("Leyendo clústeres de producción (stories/story_articles)...")
    sas = cargar_story_articles()
    stories = {s["id"]: s for s in cargar_stories()}
    miembros = defaultdict(list)
    for r in sas:
        if r["article_id"] in por_id:   # solo miembros existentes y embebidos
            miembros[r["story_id"]].append(r["article_id"])

    # Por clúster: colapso por url (defensivo) -> centroide + unión de entidades
    cl = {}
    for sid, ids in miembros.items():
        por_url = {}
        for i in ids:
            a = por_id[i]
            u = a["url"]
            if u not in por_url or cuando_captura(a) > cuando_captura(por_url[u]):
                por_url[u] = a            # representante = captura más reciente
        reps = list(por_url.values())
        if len(reps) < 2:
            continue
        centroide = np.stack([r["embedding"] for r in reps]).mean(axis=0)
        ents = set()
        for r in reps:
            ents |= normaliza_ents(r["entidades"])
        cl[sid] = {
            "centroide": centroide,
            "ents": ents,
            "n_urls": len(reps),
            "titulo": (stories.get(sid) or {}).get("titulo", "(sin título)"),
        }

    print(f"  clústeres con >=2 urls: {len(cl)}\n")

    # Todos los pares de clústeres
    sids = list(cl.keys())
    pares = []
    for x in range(len(sids)):
        A = cl[sids[x]]
        for y in range(x + 1, len(sids)):
            B = cl[sids[y]]
            comp = A["ents"] & B["ents"]
            peso = sum(idf.get(e, 0.0) for e in comp)
            cos = coseno(A["centroide"], B["centroide"])
            pares.append((peso, cos, sids[x], sids[y], comp))

    print(f"Pares de clústeres evaluados: {len(pares)}\n")
    if not pares:
        print("No hay pares (¿menos de 2 clústeres con embedding?). Nada que medir.")
        return

    # Distribuciones
    def hist(vals, edges, etiqueta):
        print(f"Distribución de {etiqueta}:")
        for lo, hi in zip(edges, edges[1:]):
            c = sum(1 for v in vals if lo <= v < hi)
            print(f"  [{lo:7.2f}, {hi:7.2f})  {c:5d}  {'#' * min(c, 60)}")
        print()

    pesos = [p[0] for p in pares]
    cosenos = [p[1] for p in pares]
    hist(cosenos, [i / 10 for i in range(0, 11)], "coseno entre centroides")
    hist(pesos, [0, 5, 10, 20, 40, 80, 160, 320, max(pesos) + 1], "peso IDF de entidades compartidas")

    def imprimir_top(titulo, ordenados):
        print(f"=== {titulo} ===")
        for peso, cos, a, b, comp in ordenados:
            comp_top = sorted(comp, key=lambda e: idf.get(e, 0), reverse=True)[:6]
            print(f"\ncos={cos:.3f}  pesoIDF={peso:7.1f}  (|comparten|={len(comp)})")
            print(f"  A: {cl[a]['titulo'][:72]}")
            print(f"  B: {cl[b]['titulo'][:72]}")
            print(f"  comparten (top IDF): {', '.join(comp_top)}")
        print()

    # Dos caras del mismo problema:
    # - por COSENO alto: ¿son temáticamente cercanos? ¿alguno debió fusionarse?
    # - por PESO alto: mismos actores; ¿mismo tema, distinto hecho (la cantera real)?
    imprimir_top(f"Top {TOP_N} por COSENO de centroides (desc)",
                 sorted(pares, key=lambda p: p[1], reverse=True)[:TOP_N])
    imprimir_top(f"Top {TOP_N} por PESO IDF de entidades compartidas (desc)",
                 sorted(pares, key=lambda p: p[0], reverse=True)[:TOP_N])


if __name__ == "__main__":
    main()
