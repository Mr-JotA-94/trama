# crawler/diag_relaciones_v2.py — Tier 0, READ-ONLY, desechable.
#
# v2: LIMPIA LA VARA antes de medir relaciones entre clústeres. El v1 mostró que el
# peso IDF crudo estaba podrido de boilerplate de fuente y conectores (NER básico), y
# que el coseno entre centroides liga por TEMA, no por hecho (clima del domingo vs
# resultados por ciudad: cos 0.86). Aquí corregimos ambos.
#
# Tres capas sobre las entidades COMPARTIDAS de cada par:
#   (1) RUIDO_DURO  -> se ELIMINA. Conectores, muletillas, CTAs/widgets de fuente que
#                      NER marcó como entidad. No son entidades.
#   (2) GEOGRAFIA   -> se CLASIFICA, no se borra. Departamentos/regiones/país siguen
#                      sumando al peso, pero NO cuentan como "entidad específica":
#                      geografía genérica no es sustancia del hecho.
#   (3) GENÉRICAS   -> por DF de clúster (data-driven, no a mano). Entidad que aparece
#                      en > FRAC_GENERICA de los clústeres no discrimina (en campaña
#                      "iván cepeda" está en casi todos). No cuenta como específica.
#
# Métrica candidata NUEVA: n_especificas = |entidades compartidas reales y específicas|.
# El coseno pasa a ser GUARDIA (descartar pares lejanos), nunca motor.
#
# MIDE, no decide. No escribe a la base. No toca el repo.

import os
import math
import json
from collections import defaultdict

import numpy as np
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

TOP_N = 25
FRAC_GENERICA = 0.15        # entidad en > este % de clústeres = genérica (no específica)
# Criterios TENTATIVOS solo para VER el grado/madeja. NO es la decisión final.
CRITERIOS = [(3, 0.50), (4, 0.55)]   # (n_especificas mínimo, coseno guardia mínimo)

# --- Capa 1: ruido duro (NO son entidades). Solo lo indefendible va aquí. ---
# Lo ambiguo ("estado", "presidencia", "gobierno") NO se lista: lo demota la capa 3.
RUIDO_DURO = {
    # conectores / muletillas
    "además", "asimismo", "según", "sin embargo", "por su parte", "no obstante",
    "en cambio", "entre tanto", "mientras tanto", "de hecho", "aun así", "ahora",
    "después", "hay", "bajo", "este", "podría", "fueron", "siga", "conozca", "lea",
    "encuentre", "deje", "felicito",
    # fragmentos de cláusula que NER cortó como entidad
    "la directora del", "el proceso", "la medida", "la decisión", "el decreto",
    "su defensa", "su trayectoria", "la ley", "el comandante de las",
    "el presidente de estados unidos", "el gobierno nacional",
    # CTAs / widgets de fuente (ligaban por MEDIO, no por hecho)
    "match electoral de el espectador",
}

# --- Capa 2: geografía (clasificada, NO borrada del peso) ---
GEOGRAFIA = {
    # 32 departamentos + variantes
    "amazonas", "antioquia", "arauca", "atlántico", "bolívar", "boyacá", "caldas",
    "caquetá", "casanare", "cauca", "cesar", "chocó", "córdoba", "cundinamarca",
    "guainía", "guaviare", "huila", "la guajira", "magdalena", "meta", "nariño",
    "norte de santander", "putumayo", "quindío", "risaralda", "santander", "sucre",
    "tolima", "valle del cauca", "valle", "vaupés", "vichada", "san andrés", "providencia",
    # macro-regiones
    "caribe", "el caribe", "pacífico", "pacífica", "andina", "andino", "orinoquía",
    "amazonía", "eje cafetero", "los llanos",
    # país / capital-distrito
    "colombia", "de colombia", "bogotá", "bogotá d.c.",
}


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
    return sb.table("stories").select("id, titulo, n_articulos, n_medios").execute().data


# ----------------------------------------------------------------------
def main():
    print("Cargando artículos embebidos...")
    arts = cargar_articulos()
    por_id = {a["id"]: a for a in arts}
    idf, N = calcular_idf(arts)
    print(f"  artículos: {len(arts)} | entidades en IDF: {len(idf)}")

    print("Leyendo clústeres de producción...")
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
        cl[sid] = {
            "centroide": np.stack([r["embedding"] for r in reps]).mean(axis=0),
            "ents": ents,
            "titulo": (stories.get(sid) or {}).get("titulo", "(sin título)"),
        }
    n_cl = len(cl)
    print(f"  clústeres con >=2 urls: {n_cl}\n")

    # --- Capa 3: DF de clúster -> entidades genéricas ---
    df_cl = defaultdict(int)
    for d in cl.values():
        for e in d["ents"]:
            df_cl[e] += 1
    umbral_gen = max(2, int(FRAC_GENERICA * n_cl))
    GENERICAS = {e for e, c in df_cl.items() if c >= umbral_gen}

    def es_especifica(e):
        return e not in RUIDO_DURO and e not in GEOGRAFIA and e not in GENERICAS

    # --- Reporte de limpieza (validar que filtramos lo correcto) ---
    print(f"=== Capa 3: genéricas por DF de clúster (>= {umbral_gen} de {n_cl} clústeres) ===")
    print(f"  entidades marcadas genéricas: {len(GENERICAS)}")
    top_gen = sorted(GENERICAS, key=lambda e: df_cl[e], reverse=True)[:25]
    for e in top_gen:
        print(f"    {df_cl[e]:3d}  {e}")
    print()

    # --- Pares ---
    sids = list(cl.keys())
    pares = []
    for x in range(len(sids)):
        A = cl[sids[x]]
        for y in range(x + 1, len(sids)):
            B = cl[sids[y]]
            comp = A["ents"] & B["ents"]
            comp_limpio = comp - RUIDO_DURO
            peso = sum(idf.get(e, 0.0) for e in comp_limpio)   # peso incluye geografía
            esp = {e for e in comp_limpio if es_especifica(e)}
            cos = coseno(A["centroide"], B["centroide"])
            pares.append({"cos": cos, "peso": peso, "n_esp": len(esp),
                          "esp": esp, "a": sids[x], "b": sids[y]})
    print(f"Pares evaluados: {len(pares)}\n")

    # --- Cuánto peso fantasma matamos: top tokens de ruido duro por IDF aportado ---
    aporte_ruido = defaultdict(float)
    for p in pares:
        comp = cl[p["a"]]["ents"] & cl[p["b"]]["ents"]
        for e in comp & RUIDO_DURO:
            aporte_ruido[e] += idf.get(e, 0.0)
    print("=== Capa 1: ruido duro que más peso fantasma aportaba (IDF sumado en pares) ===")
    for e, w in sorted(aporte_ruido.items(), key=lambda kv: kv[1], reverse=True)[:15]:
        print(f"    {w:8.1f}  {e}")
    print()

    # --- Distribución de n_especificas ---
    print("Distribución de n_especificas (entidades específicas reales compartidas):")
    for k in range(0, 11):
        c = sum(1 for p in pares if p["n_esp"] == k)
        marca = "  <- pares sin sustancia específica" if k == 0 else ""
        print(f"  n_esp = {k:2d}   {c:5d}  {'#' * min(c, 50)}{marca}")
    c = sum(1 for p in pares if p["n_esp"] > 10)
    print(f"  n_esp > 10   {c:5d}  {'#' * min(c, 50)}")
    print()

    # --- Top pares por n_especificas (la señal candidata) ---
    print(f"=== Top {TOP_N} por n_especificas (desc, desempate coseno) ===")
    top = sorted(pares, key=lambda p: (p["n_esp"], p["cos"]), reverse=True)[:TOP_N]
    for p in top:
        esp_orden = sorted(p["esp"], key=lambda e: idf.get(e, 0), reverse=True)[:7]
        print(f"\nn_esp={p['n_esp']:2d}  cos={p['cos']:.3f}  pesoIDF={p['peso']:6.1f}")
        print(f"  A: {cl[p['a']]['titulo'][:72]}")
        print(f"  B: {cl[p['b']]['titulo'][:72]}")
        print(f"  específicas: {', '.join(esp_orden)}")
    print()

    # --- Grado por clúster bajo criterios tentativos (ver si colapsa la madeja) ---
    for K, G in CRITERIOS:
        aristas = [p for p in pares if p["n_esp"] >= K and p["cos"] >= G]
        grado = defaultdict(int)
        for p in aristas:
            grado[p["a"]] += 1
            grado[p["b"]] += 1
        n_conectados = len(grado)
        print(f"=== Criterio TENTATIVO: n_esp >= {K} Y cos >= {G} ===")
        print(f"  aristas (relaciones): {len(aristas)}  |  clústeres conectados: {n_conectados}/{n_cl}")
        if grado:
            dist = defaultdict(int)
            for g in grado.values():
                dist[g] += 1
            print("  distribución de grado: " +
                  ", ".join(f"{g}->{dist[g]}" for g in sorted(dist)))
            print("  hubs (mayor grado, posible madeja):")
            for sid, g in sorted(grado.items(), key=lambda kv: kv[1], reverse=True)[:8]:
                print(f"    grado {g:2d}  {cl[sid]['titulo'][:64]}")
        print()


if __name__ == "__main__":
    main()
