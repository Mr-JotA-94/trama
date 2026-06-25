# crawler/diag_relaciones_v4.py — Tier 0, READ-ONLY, desechable.
#
# EXCEPCIÓN consciente al "no hay v4": el v3 no iteró, RESPONDIÓ (el cap no desinfla el
# hub). Esto contesta la pregunta NUEVA que el v3 destapó.
#
# Hallazgo de diseño: la rareza correcta a nivel de clúster NO es df de ARTÍCULO (el IDF
# que veníamos usando) sino df de CLÚSTER. "preconteo" es raro entre artículos pero está
# en muchos clústeres electorales -> no discrimina ENTRE clústeres. "andeg" está en ~2
# clústeres -> sí discrimina. Esa es la SEGUNDA COMPUERTA un nivel arriba (el clustering
# ya tiene dos abajo; las relaciones tenían una sola).
#
# Mide dos cosas:
#  (1) PERFIL de cada clúster: difuso (muchas entidades anchas, como el análisis Pastrana)
#      vs concentrado (pocas raras, como Air-e). Métrica: df-de-clúster promedio de sus
#      entidades específicas.
#  (2) Re-puntúa pares con peso de CLÚSTER-IDF y re-mide in-degree bajo cap: ¿cae el hub
#      topical al rankear por cluster-IDF en vez de por conteo de específicas?
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

FRAC_GENERICA = 0.15
K_FLOOR = 3            # piso de n_especificas para que un par sea CANDIDATO (igual a v3)
G_FLOOR = 0.50
K_SHOW = 5

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
    "el espectador", "el tiempo", "el colombiano", "vorágine", "las2orillas",
    "noticias caracol",
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
             .select("id, url, entidades, embedding, fecha_captura")
             .not_.is_("embedding", "null").range(desde, desde + 999).execute().data)
        if not q:
            break
        filas.extend(q)
        desde += 1000
    for a in filas:
        a["embedding"] = np.asarray(_parse_embedding(a["embedding"]), dtype=np.float32)
    return filas


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

    # df de CLÚSTER + IDF de clúster
    df_cl = defaultdict(int)
    for d in cl.values():
        for e in d["ents"]:
            df_cl[e] += 1
    idf_cl = {e: math.log(n_cl / c) for e, c in df_cl.items()}
    umbral_gen = max(2, int(FRAC_GENERICA * n_cl))
    GENERICAS = {e for e, c in df_cl.items() if c >= umbral_gen}

    def es_especifica(e):
        return e not in RUIDO_DURO and e not in GEOGRAFIA and e not in GENERICAS

    # (1) Perfil de clúster: difuso vs concentrado
    perfil = {}
    for sid, d in cl.items():
        esp = {e for e in d["ents"] if es_especifica(e)}
        if not esp:
            continue
        mean_df = sum(df_cl[e] for e in esp) / len(esp)   # alto = entidades anchas = difuso
        perfil[sid] = {"n_esp": len(esp), "mean_df": mean_df}

    print("=== (1) PERFIL — clústeres MÁS DIFUSOS (mean_df de sus específicas alto) ===")
    print("    (mean_df = en cuántos clústeres vive en promedio cada entidad 'específica' suya)")
    difusos = sorted([s for s in perfil if perfil[s]["n_esp"] >= 4],
                     key=lambda s: perfil[s]["mean_df"], reverse=True)[:12]
    for s in difusos:
        print(f"    mean_df={perfil[s]['mean_df']:4.1f}  n_esp={perfil[s]['n_esp']:3d}  {cl[s]['titulo'][:56]}")
    print("\n=== (1) PERFIL — clústeres MÁS CONCENTRADOS (mean_df bajo = buen ancla) ===")
    conc = sorted([s for s in perfil if perfil[s]["n_esp"] >= 4],
                  key=lambda s: perfil[s]["mean_df"])[:12]
    for s in conc:
        print(f"    mean_df={perfil[s]['mean_df']:4.1f}  n_esp={perfil[s]['n_esp']:3d}  {cl[s]['titulo'][:56]}")
    print()

    # Pares: n_esp (v3) + peso_cl (v4, cluster-IDF de específicas compartidas)
    sids = list(cl.keys())
    pares = []
    for x in range(len(sids)):
        A = cl[sids[x]]
        for y in range(x + 1, len(sids)):
            B = cl[sids[y]]
            comp = (A["ents"] & B["ents"]) - RUIDO_DURO
            esp = {e for e in comp if es_especifica(e)}
            peso_cl = sum(idf_cl.get(e, 0.0) for e in esp)
            pares.append({"cos": coseno(A["centroide"], B["centroide"]),
                          "n_esp": len(esp), "peso_cl": peso_cl,
                          "esp": esp, "a": sids[x], "b": sids[y]})

    print("=== (2) Top 15 pares por peso_cl (cluster-IDF de específicas compartidas) ===")
    for p in sorted(pares, key=lambda p: p["peso_cl"], reverse=True)[:15]:
        esp = sorted(p["esp"], key=lambda e: idf_cl.get(e, 0), reverse=True)[:6]
        print(f"\npeso_cl={p['peso_cl']:5.1f}  n_esp={p['n_esp']:2d}  cos={p['cos']:.3f}")
        print(f"  A: {cl[p['a']]['titulo'][:68]}")
        print(f"  B: {cl[p['b']]['titulo'][:68]}")
        print(f"  específicas (raras entre clústeres): {', '.join(esp)}")
    print()

    # (2) in-degree bajo cap, rankeando ego por n_esp (v3) vs por peso_cl (v4)
    edges = [p for p in pares if p["n_esp"] >= K_FLOOR and p["cos"] >= G_FLOOR]
    adj = defaultdict(list)
    for p in edges:
        adj[p["a"]].append(p)
        adj[p["b"]].append(p)

    def indegree(clave):
        ind = defaultdict(int)
        for sid in adj:
            top = sorted(adj[sid], key=lambda p: (clave(p), p["cos"]), reverse=True)[:K_SHOW]
            for p in top:
                otro = p["b"] if p["a"] == sid else p["a"]
                ind[otro] += 1
        return ind

    ind_v3 = indegree(lambda p: p["n_esp"])
    ind_v4 = indegree(lambda p: p["peso_cl"])

    print(f"=== (2) IN-DEGREE bajo cap (top {K_SHOW}/clúster) — RANKEO POR n_esp (v3) ===")
    for sid, g in sorted(ind_v3.items(), key=lambda kv: kv[1], reverse=True)[:8]:
        print(f"    in={g:2d}  {cl[sid]['titulo'][:60]}")
    print(f"\n=== (2) IN-DEGREE bajo cap — RANKEO POR peso_cl (v4, cluster-IDF) ===")
    for sid, g in sorted(ind_v4.items(), key=lambda kv: kv[1], reverse=True)[:8]:
        print(f"    in={g:2d}  {cl[sid]['titulo'][:60]}")

    # Tabla decisiva: focos conocidos, in-degree bajo ambos rankeos + perfil
    print("\n=== TABLA DECISIVA: focos conocidos ===")
    print(f"  {'in_v3':>6} {'in_v4':>6} {'n_esp_p':>8} {'mean_df':>8}  título")
    for needle in ["Pastrana", "cierres de campaña", "última fase del escrutinio",
                   "Air-e", "Chalá", "alias 24", "Arizabaleta", "Putumayo"]:
        sid = next((s for s in cl if needle.lower() in cl[s]["titulo"].lower()), None)
        if not sid:
            print(f"  (no encontré foco: {needle})")
            continue
        pp = perfil.get(sid, {"n_esp": 0, "mean_df": 0})
        print(f"  {ind_v3.get(sid,0):6d} {ind_v4.get(sid,0):6d} "
              f"{pp['n_esp']:8d} {pp['mean_df']:8.1f}  {cl[sid]['titulo'][:46]}")


if __name__ == "__main__":
    main()
