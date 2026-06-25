# crawler/diag_relaciones_v3.py — Tier 0, READ-ONLY, desechable.
#
# v3 = última medición antes de decidir esquema. Sobre v2:
#   (A) Nombres de los 5 medios -> ruido duro (mata contaminación por FUENTE de raíz).
#   (B) normaliza_ents ahora colapsa espacios + strip antes de lower (arregla el match
#       exacto que dejaba colar "sin embargo"/"hay" pese a estar en la lista).
#   (C) Reporte bajo CAP de top-K aristas por clúster (el cap que usará el tablero):
#       ¿quedan las vecindades acotadas? ¿se desinfla el hub topical (análisis Pastrana)
#       al mirar su IN-DEGREE bajo cap, en cuántos tableros sigue asomándose?
#
# MIDE, no decide. No escribe a la base. No toca el repo.

import os
import re
import math
import json
from collections import defaultdict

import numpy as np
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

TOP_N = 15
FRAC_GENERICA = 0.15
K_FLOOR = 3            # piso de n_especificas para que una arista CALIFIQUE
G_FLOOR = 0.50         # coseno guardia mínimo
K_SHOW = 5            # tope de aristas por clúster en presentación (el tablero)

RUIDO_DURO = {
    "además", "asimismo", "según", "sin embargo", "por su parte", "no obstante",
    "en cambio", "entre tanto", "mientras tanto", "de hecho", "aun así", "ahora",
    "después", "hay", "bajo", "este", "podría", "fueron", "siga", "conozca", "lea",
    "encuentre", "deje", "felicito", "más", "quién",
    "la directora del", "el proceso", "la medida", "la decisión", "el decreto",
    "su defensa", "su trayectoria", "la ley", "el comandante de las",
    "el presidente de estados unidos", "el gobierno nacional", "los hechos",
    "las imágenes", "el anuncio", "según las autoridades", "la captura", "información",
    "match electoral de el espectador",
    # (A) nombres de medios: ligaban por fuente, no por hecho
    "el espectador", "el tiempo", "el colombiano", "vorágine", "las2orillas",
}

GEOGRAFIA = {
    "amazonas", "antioquia", "arauca", "atlántico", "bolívar", "boyacá", "caldas",
    "caquetá", "casanare", "cauca", "cesar", "chocó", "córdoba", "cundinamarca",
    "guainía", "guaviare", "huila", "la guajira", "magdalena", "meta", "nariño",
    "norte de santander", "putumayo", "quindío", "risaralda", "santander", "sucre",
    "tolima", "valle del cauca", "valle", "vaupés", "vichada", "san andrés", "providencia",
    "caribe", "el caribe", "pacífico", "pacífica", "andina", "andino", "orinoquía",
    "amazonía", "eje cafetero", "los llanos",
    "colombia", "de colombia", "bogotá", "bogotá d.c.",
}


def _parse_embedding(v):
    return json.loads(v) if isinstance(v, str) else v


def normaliza_ents(lista):
    # (B) colapsar espacios + strip ANTES de lower: el match exacto contra las
    # stoplists fallaba por espacios raros en la forma almacenada.
    out = set()
    for e in (lista or []):
        out.add(re.sub(r"\s+", " ", e).strip().lower())
    out.discard("")
    return out


def cuando_captura(a):
    return a.get("fecha_captura") or a.get("fecha_publicacion") or ""


def coseno(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return 0.0 if na == 0 or nb == 0 else float(a @ b / (na * nb))


def cargar_articulos():
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
    N = len(articulos)
    df = defaultdict(int)
    for a in articulos:
        for e in normaliza_ents(a["entidades"]):
            df[e] += 1
    return {e: math.log(N / c) for e, c in df.items()}, N


def cargar_story_articles():
    filas, desde = [], 0
    while True:
        q = (sb.table("story_articles").select("story_id, article_id")
             .range(desde, desde + 999).execute().data)
        if not q:
            break
        filas.extend(q)
        desde += 1000
    return filas


def cargar_stories():
    return sb.table("stories").select("id, titulo").execute().data


def main():
    print("Cargando...")
    arts = cargar_articulos()
    por_id = {a["id"]: a for a in arts}
    idf, N = calcular_idf(arts)

    sas = cargar_story_articles()
    stories = {s["id"]: s for s in cargar_stories()}
    miembros = defaultdict(list)
    for r in sas:
        if r["article_id"] in por_id:
            miembros[r["story_id"]].append(r["article_id"])

    cl = {}
    for sid, ids in miembros.items():
        por_url = {}
        for i in ids:
            a = por_id[i]
            u = a["url"]
            if u not in por_url or cuando_captura(a) > cuando_captura(por_url[u]):
                por_url[u] = a
        reps = list(por_url.values())
        if len(reps) < 2:
            continue
        ents = set()
        for r in reps:
            ents |= normaliza_ents(r["entidades"])
        cl[sid] = {"centroide": np.stack([r["embedding"] for r in reps]).mean(axis=0),
                   "ents": ents, "titulo": (stories.get(sid) or {}).get("titulo", "(s/t)")}
    n_cl = len(cl)
    print(f"  clústeres: {n_cl}\n")

    df_cl = defaultdict(int)
    for d in cl.values():
        for e in d["ents"]:
            df_cl[e] += 1
    umbral_gen = max(2, int(FRAC_GENERICA * n_cl))
    GENERICAS = {e for e, c in df_cl.items() if c >= umbral_gen}

    def es_especifica(e):
        return e not in RUIDO_DURO and e not in GEOGRAFIA and e not in GENERICAS

    sids = list(cl.keys())
    pares = []
    for x in range(len(sids)):
        A = cl[sids[x]]
        for y in range(x + 1, len(sids)):
            B = cl[sids[y]]
            comp = (A["ents"] & B["ents"]) - RUIDO_DURO
            esp = {e for e in comp if es_especifica(e)}
            pares.append({"cos": coseno(A["centroide"], B["centroide"]),
                          "n_esp": len(esp), "esp": esp, "a": sids[x], "b": sids[y]})

    print("Distribución de n_especificas (post limpieza v3):")
    for k in range(0, 11):
        c = sum(1 for p in pares if p["n_esp"] == k)
        print(f"  n_esp = {k:2d}   {c:5d}  {'#' * min(c, 50)}")
    print(f"  n_esp > 10   {sum(1 for p in pares if p['n_esp'] > 10):5d}\n")

    print(f"=== Top {TOP_N} por n_especificas ===")
    for p in sorted(pares, key=lambda p: (p["n_esp"], p["cos"]), reverse=True)[:TOP_N]:
        esp = sorted(p["esp"], key=lambda e: idf.get(e, 0), reverse=True)[:7]
        print(f"\nn_esp={p['n_esp']:2d}  cos={p['cos']:.3f}")
        print(f"  A: {cl[p['a']]['titulo'][:70]}")
        print(f"  B: {cl[p['b']]['titulo'][:70]}")
        print(f"  específicas: {', '.join(esp)}")
    print()

    # --- (C) Grafo bajo CAP de presentación ---
    edges = [p for p in pares if p["n_esp"] >= K_FLOOR and p["cos"] >= G_FLOOR]
    adj = defaultdict(list)
    for p in edges:
        adj[p["a"]].append(p)
        adj[p["b"]].append(p)

    def ego(sid):
        return sorted(adj[sid], key=lambda p: (p["n_esp"], p["cos"]), reverse=True)[:K_SHOW]

    indeg = defaultdict(int)
    mostrado = set()
    for sid in adj:
        for p in ego(sid):
            otro = p["b"] if p["a"] == sid else p["a"]
            indeg[otro] += 1
            mostrado.add(frozenset((p["a"], p["b"])))

    print(f"=== CAP de presentación (piso n_esp>={K_FLOOR}, cos>={G_FLOOR}; tope {K_SHOW}/clúster) ===")
    print(f"  aristas que califican (sin cap): {len(edges)}")
    print(f"  aristas distintas mostradas (con cap): {len(mostrado)}")
    print(f"  clústeres con >=1 vecino: {len(adj)}/{n_cl}")
    dist = defaultdict(int)
    for v in indeg.values():
        dist[v] += 1
    print("  IN-DEGREE bajo cap (en cuántos tableros aparece c/clúster):")
    print("    " + ", ".join(f"{g}->{dist[g]}" for g in sorted(dist)))
    print("\n  Mayor in-degree (¿sigue un hub topical dominando tableros?):")
    for sid, g in sorted(indeg.items(), key=lambda kv: kv[1], reverse=True)[:8]:
        print(f"    in={g:2d}  {cl[sid]['titulo'][:62]}")

    # --- Vecindarios ego de los would-be hubs: ¿son coherentes los top-5? ---
    qual_deg = {sid: len(adj[sid]) for sid in adj}
    print("\n=== Vecindario top-5 de los clústeres de mayor grado (eyeball) ===")
    for sid, _ in sorted(qual_deg.items(), key=lambda kv: kv[1], reverse=True)[:6]:
        print(f"\n  FOCO: {cl[sid]['titulo'][:66]}  (grado bruto {qual_deg[sid]})")
        for p in ego(sid):
            otro = p["b"] if p["a"] == sid else p["a"]
            print(f"     n_esp={p['n_esp']:2d} cos={p['cos']:.3f}  {cl[otro]['titulo'][:58]}")


if __name__ == "__main__":
    main()
