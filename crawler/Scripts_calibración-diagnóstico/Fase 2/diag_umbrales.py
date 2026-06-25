# diag_umbrales.py — READ-ONLY. No escribe a Supabase. Recomputa la formación
# con la MISMA lógica de clustering_fase2.py para auditar IDF≥20 / coseno≥0.70.
import os, math, json
from collections import defaultdict
from datetime import datetime
import numpy as np
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

UMBRAL_IDF, UMBRAL_COSENO, VENTANA_HORAS = 20.0, 0.70, 72
# Bandas de "casi" para detectar falsos negativos:
COS_CASI_LO, PESO_CASI_LO = 0.65, 15.0

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

arts = cargar()
N = len(arts)
df = defaultdict(int)
for a in arts:
    for e in normaliza_ents(a["entidades"]): df[e] += 1
idf = {e: math.log(N/c) for e,c in df.items()}

noticias = [a for a in arts if a["tipo"] == "noticia"]
ents = {a["id"]: normaliza_ents(a["entidades"]) for a in noticias}
por_id = {a["id"]: a for a in noticias}
print(f"Banco: {N} con embedding | {len(noticias)} noticias (núcleo)")

def cos(a,b): return float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)))

aristas, casi_sem, casi_ent = [], [], []   # (id_a, id_b, peso, coseno)
n = len(noticias)
for i in range(n):
    a = noticias[i]
    for j in range(i+1, n):
        b = noticias[j]
        if a["outlet_id"] == b["outlet_id"]: continue
        if abs((cuando(a)-cuando(b)).total_seconds()) > VENTANA_HORAS*3600: continue
        comp = ents[a["id"]] & ents[b["id"]]
        peso = sum(idf.get(e,0.0) for e in comp)
        # solo vale calcular coseno si hay algo de entidades en juego
        if peso < PESO_CASI_LO: continue
        c = cos(a["embedding"], b["embedding"])
        if peso >= UMBRAL_IDF and c >= UMBRAL_COSENO:
            aristas.append((a["id"], b["id"], peso, c))
        elif peso >= UMBRAL_IDF and COS_CASI_LO <= c < UMBRAL_COSENO:
            casi_sem.append((a["id"], b["id"], peso, c))
        elif c >= UMBRAL_COSENO and PESO_CASI_LO <= peso < UMBRAL_IDF:
            casi_ent.append((a["id"], b["id"], peso, c))

# Union-find solo con aristas reales
padre = {a["id"]: a["id"] for a in noticias}
def find(x):
    while padre[x]!=x: padre[x]=padre[padre[x]]; x=padre[x]
    return x
def union(a,b):
    ra,rb=find(a),find(b)
    if ra!=rb: padre[ra]=rb
for ia,ib,_,_ in aristas: union(ia,ib)

grupos = defaultdict(list)
for a in noticias: grupos[find(a["id"])].append(a["id"])
clusteres = [ids for ids in grupos.values()
             if len(ids)>=2 and len({por_id[i]["outlet_id"] for i in ids})>=2]

# Aristas internas por clúster
miembro = {}
for k,ids in enumerate(clusteres):
    for i in ids: miembro[i]=k
ar_por_cl = defaultdict(list)
for ia,ib,p,c in aristas:
    if ia in miembro and miembro[ia]==miembro.get(ib): ar_por_cl[miembro[ia]].append((p,c))

def hist(vals, bins):
    out=[]
    for lo,hi in bins:
        n=sum(1 for v in vals if lo<=v<hi)
        out.append((lo,hi,n))
    return out

print(f"\n{'='*64}\nGLOBAL")
print(f"Pares evaluados (peso>={PESO_CASI_LO}): {len(aristas)+len(casi_sem)+len(casi_ent)}")
print(f"  Aristas (pasan ambas):   {len(aristas)}")
print(f"  Casi-semántica (cos bajo): {len(casi_sem)}")
print(f"  Casi-entidades (peso bajo): {len(casi_ent)}")
print(f"Clústeres formados: {len(clusteres)} | tamaños: {sorted((len(c) for c in clusteres),reverse=True)}")

print(f"\n-- Histograma PESO IDF de aristas --")
for lo,hi,c in hist([p for _,_,p,_ in aristas], [(20,23),(23,28),(28,40),(40,60),(60,1e9)]):
    print(f"  [{lo:>3}-{hi if hi<1e9 else '∞':>4}) {'#'*c} {c}")
print(f"-- Histograma COSENO de aristas --")
for lo,hi,c in hist([c for _,_,_,c in aristas], [(0.70,0.73),(0.73,0.78),(0.78,0.85),(0.85,0.92),(0.92,1.01)]):
    print(f"  [{lo:.2f}-{hi:.2f}) {'#'*c} {c}")

print(f"\n{'='*64}\nCLÚSTERES FRÁGILES (arista mínima marginal: peso<23 o cos<0.73)")
for k,ids in enumerate(clusteres):
    ars = ar_por_cl[k]
    if not ars: continue
    pmin = min(p for p,_ in ars); cmin = min(c for _,c in ars)
    if pmin < 23 or cmin < 0.73:
        print(f"  cl#{k} n={len(ids)} aristas={len(ars)} peso_min={pmin:.1f} cos_min={cmin:.3f}")

print(f"\n{'='*64}\nCLÚSTERES CHICOS (2-3) — juzgar a ojo")
for k,ids in enumerate(clusteres):
    if len(ids)>3: continue
    ars = ar_por_cl[k]
    rng = f"peso[{min(p for p,_ in ars):.1f}] cos[{min(c for _,c in ars):.3f}]" if ars else "?"
    print(f"  cl#{k} n={len(ids)} {rng}")
    for i in ids:
        print(f"      [{por_id[i]['outlet_id']}] {por_id[i]['titulo'][:70]}")

print(f"\n{'='*64}\nTOP CASI-FALLOS (¿deberían haber entrado?)")
print("-- casi por SEMÁNTICA (peso ok, cos 0.65-0.70), top 10 por peso --")
for ia,ib,p,c in sorted(casi_sem, key=lambda x:x[2], reverse=True)[:10]:
    print(f"  peso={p:.1f} cos={c:.3f}")
    print(f"    [{por_id[ia]['outlet_id']}] {por_id[ia]['titulo'][:62]}")
    print(f"    [{por_id[ib]['outlet_id']}] {por_id[ib]['titulo'][:62]}")
print("-- casi por ENTIDADES (cos ok, peso 15-20), top 10 por cos --")
for ia,ib,p,c in sorted(casi_ent, key=lambda x:x[3], reverse=True)[:10]:
    print(f"  peso={p:.1f} cos={c:.3f}")
    print(f"    [{por_id[ia]['outlet_id']}] {por_id[ia]['titulo'][:62]}")
    print(f"    [{por_id[ib]['outlet_id']}] {por_id[ib]['titulo'][:62]}")