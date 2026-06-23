# diag_colapso_diff.py — READ-ONLY. Compara clustering SIN colapsar (estado viejo)
# vs CON colapso por url (estado nuevo). No escribe nada. Reporta qué cambió.
import os, math, uuid, json
from collections import defaultdict
from datetime import datetime
import numpy as np
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

UMBRAL_IDF, UMBRAL_COSENO, VENTANA_HORAS = 20.0, 0.70, 72
NAMESPACE_STORIES = uuid.UUID("6f3a1c2e-7b4d-5a9e-8c1f-2d3e4f5a6b7c")

def _emb(v): return json.loads(v) if isinstance(v, str) else v
def normaliza_ents(l): return {e.lower() for e in (l or [])}
def cuando(a):
    f = a["fecha_publicacion"] or a["fecha_captura"]
    return datetime.fromisoformat(f.replace("Z","+00:00"))

def cargar():
    filas, desde = [], 0
    while True:
        q = (sb.table("articles")
             .select("id, outlet_id, url, titulo, tipo, fecha_publicacion, fecha_captura, entidades, embedding")
             .not_.is_("embedding","null").range(desde, desde+999).execute().data)
        if not q: break
        filas.extend(q); desde += 1000
    for a in filas:
        a["embedding"] = np.asarray(_emb(a["embedding"]), dtype=np.float32)
    return filas

def colapsar(arts):
    por_url = {}
    for a in arts:
        u = a["url"]
        if u not in por_url or a["fecha_captura"] > por_url[u]["fecha_captura"]:
            por_url[u] = a
    return list(por_url.values())

def cos(a,b): return float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)))

def clusterizar(arts):
    arts = [a for a in arts if a["tipo"]=="noticia"]
    ents = {a["id"]: normaliza_ents(a["entidades"]) for a in arts}
    por_id = {a["id"]: a for a in arts}
    N = len(arts)
    df = defaultdict(int)
    for a in arts:
        for e in ents[a["id"]]: df[e]+=1
    idf = {e: math.log(max(N,2)/c) for e,c in df.items()}
    padre = {a["id"]: a["id"] for a in arts}
    def find(x):
        while padre[x]!=x: padre[x]=padre[padre[x]]; x=padre[x]
        return x
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb: padre[ra]=rb
    n=len(arts)
    for i in range(n):
        a=arts[i]
        for j in range(i+1,n):
            b=arts[j]
            if a["outlet_id"]==b["outlet_id"]: continue
            if abs((cuando(a)-cuando(b)).total_seconds())>VENTANA_HORAS*3600: continue
            comp = ents[a["id"]] & ents[b["id"]]
            if sum(idf.get(e,0.0) for e in comp) < UMBRAL_IDF: continue
            if cos(a["embedding"],b["embedding"]) < UMBRAL_COSENO: continue
            union(a["id"],b["id"])
    grupos = defaultdict(list)
    for a in arts: grupos[find(a["id"])].append(a["id"])
    cls = [ids for ids in grupos.values()
           if len(ids)>=2 and len({por_id[i]["outlet_id"] for i in ids})>=2]
    return cls, por_id

def uid(ids, por_id):
    s = min(ids, key=lambda i: (cuando(por_id[i]), por_id[i]["url"]))
    return str(uuid.uuid5(NAMESPACE_STORIES, por_id[s]["url"]))

raw = cargar()
print(f"Capturas con embedding: {len(raw)}")
col = colapsar(raw)
print(f"Tras colapso por url: {len(col)} artículos únicos ({len(raw)-len(col)} capturas absorbidas)")

cls_v, pid_v = clusterizar(raw)     # viejo: sin colapsar
cls_n, pid_n = clusterizar(col)     # nuevo: colapsado
print(f"\nVIEJO (sin colapsar): {len(cls_v)} clústeres")
print(f"NUEVO (colapsado):    {len(cls_n)} clústeres\n")

# Identidad por uuid. Para diff, mapeo url-set por clúster.
def urlset(ids, pid): return frozenset(pid[i]["url"] for i in ids)
viejo = {uid(ids,pid_v): (ids, urlset(ids,pid_v)) for ids in cls_v}
nuevo = {uid(ids,pid_n): (ids, urlset(ids,pid_n)) for ids in cls_n}

uv, un = set(viejo), set(nuevo)
print(f"uuids iguales (clúster intacto en identidad): {len(uv & un)}")
print(f"uuids solo en VIEJO (desaparecieron): {len(uv - un)}")
print(f"uuids solo en NUEVO (aparecieron):    {len(un - uv)}\n")

# Para cada clúster nuevo que apareció, ¿de qué clúster viejo salieron sus urls?
print("="*64)
print("CLÚSTERES NUEVOS (aparecieron) — ¿separación legítima o fragmento roto?")
print("="*64)
viejo_por_url = {}
for k,(ids,us) in viejo.items():
    for u in us: viejo_por_url[u] = k
for k in (un - uv):
    ids, us = nuevo[k]
    origenes = defaultdict(int)
    for u in us:
        origenes[viejo_por_url.get(u, "NINGUNO(nuevo)")] += 1
    print(f"\nNUEVO {k[:8]} n={len(ids)} | urls venían de: "
          f"{ {o[:8] if o!='NINGUNO(nuevo)' else o: c for o,c in origenes.items()} }")
    for i in ids:
        print(f"    [{pid_n[i]['outlet_id'][:8]}] {pid_n[i]['titulo'][:66]}")

print("\n"+"="*64)
print("CLÚSTERES VIEJOS QUE DESAPARECIERON (se partieron o fusionaron)")
print("="*64)
nuevo_por_url = {}
for k,(ids,us) in nuevo.items():
    for u in us: nuevo_por_url[u] = k
for k in (uv - un):
    ids, us = viejo[k]
    destinos = defaultdict(int)
    for u in us:
        destinos[nuevo_por_url.get(u, "DISUELTO")] += 1
    print(f"\nVIEJO {k[:8]} n={len(ids)} | sus urls fueron a: "
          f"{ {d[:8] if d not in ('DISUELTO',) else d: c for d,c in destinos.items()} }")