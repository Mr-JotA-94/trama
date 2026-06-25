# crawler/diag_fix_titulos.py — verifica el fix de título-cita. Solo lee. Tier 2.
import os, re
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# Réplica EXACTA de la heurística del frontend (colapsarCluster.js).
RE_DELANTE = re.compile(r'^\s*["«“\'‘].{15,}?["»”\'’]\s*:')
RE_ATRAS   = re.compile(r':\s*["«“\'‘].{15,}', re.S)
def es_cita(t):
    t = (t or "").strip()
    return bool(RE_DELANTE.search(t) or RE_ATRAS.search(t))

def titulo_viejo(noticias):
    if not noticias: return None
    return max(noticias, key=lambda a: a["score_neutralidad"] or 0)["titulo"]

def titulo_nuevo(noticias):
    if not noticias: return None
    no_cita = [a for a in noticias if not es_cita(a["titulo"])]
    pool = no_cita or noticias
    return max(pool, key=lambda a: a["score_neutralidad"] or 0)["titulo"]

# Cargar títulos + tipo de articles
titulos = {}
d = 0
while True:
    q = sb.table("articles").select("id, titulo, tipo").range(d, d+999).execute().data
    if not q: break
    for a in q: titulos[a["id"]] = a
    d += 1000

stories = sb.table("stories").select("id, titulo").execute().data
sa = sb.table("story_articles").select("story_id, article_id, score_neutralidad").execute().data

por_story = {}
for r in sa:
    a = titulos.get(r["article_id"])
    if not a: continue
    por_story.setdefault(r["story_id"], []).append(
        {"titulo": a["titulo"], "tipo": a["tipo"], "score_neutralidad": r["score_neutralidad"]})

cambiados, residual, sin_noticia = [], [], []
for s in stories:
    miembros = por_story.get(s["id"], [])
    noticias = [m for m in miembros if m["tipo"] == "noticia"]
    viejo, nuevo = titulo_viejo(noticias), titulo_nuevo(noticias)
    if nuevo is None:
        sin_noticia.append(s["id"][:8]); continue
    if viejo != nuevo:
        cambiados.append((s["id"][:8], viejo, nuevo))
    elif es_cita(nuevo):
        residual.append((s["id"][:8], nuevo))  # sigue cita = sin alternativa

print(f"Clústeres totales: {len(stories)}")
print(f"Títulos que CAMBIAN con el fix: {len(cambiados)}")
print(f"Residual (cita sin alternativa, no cambia): {len(residual)}")
print(f"Sin noticia (cae a fallback): {len(sin_noticia)}")
print("\n== CAMBIOS ==")
for cid, v, n in cambiados:
    print(f"\n[{cid}]")
    print(f"  ANTES: {v[:90]}")
    print(f"  AHORA: {n[:90]}")
    print(f"  ¿nuevo es cita?: {es_cita(n)}")   # debe ser False en todos
print("\n== RESIDUAL (esperado: Germán 656a7e6c) ==")
for cid, n in residual:
    print(f"[{cid}] {n[:90]}")