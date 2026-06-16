# inspeccionar_pares.py — Tier 0, SOLO LECTURA. Para calibrar el umbral a ojo.
#
# Muestra los pares con >=3 entidades compartidas, ordenados por similitud coseno
# DESCENDENTE. Vos leés título + entidades compartidas y marcás mentalmente:
# ¿misma noticia (✓) o casualidad (✗)? El umbral real es donde los ✓ se acaban.
#
# Reusa los mismos modelos del diagnóstico. Mismas dependencias, nada nuevo.

import os
from datetime import datetime
from itertools import combinations

from dotenv import load_dotenv
from supabase import create_client
import spacy
from sentence_transformers import SentenceTransformer, util

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

VENTANA_HORAS = 72
MIN_ENTIDADES = 3       # solo pares que pasan el filtro de la etapa 1
LIMITE = 200
TIPOS_ENT = {"PER", "ORG", "LOC", "MISC"}

print("Cargando modelos...")
nlp = spacy.load("es_core_news_md")
modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# Traemos también el slug del medio para que veas QUIÉN publicó cada nota.
filas = (sb.table("articles")
         .select("id, outlet_id, titulo, subtitulo, fecha_publicacion, fecha_captura, contenido_visible, outlets(slug)")
         .eq("tipo", "noticia")
         .order("fecha_captura", desc=True)
         .limit(LIMITE)
         .execute().data)
print(f"Artículos traídos: {len(filas)}")

def entidades(art):
    texto = f"{art['titulo']}. {art['contenido_visible'][:2000]}"
    doc = nlp(texto)
    return {e.text.strip() for e in doc.ents          # conservamos mayúsculas para mostrar
            if e.label_ in TIPOS_ENT and len(e.text.strip()) > 2}

print("Extrayendo entidades...")
ents = {a["id"]: entidades(a) for a in filas}
# set en minúsculas para comparar, pero guardamos el original para imprimir
ents_low = {k: {e.lower(): e for e in v} for k, v in ents.items()}

print("Calculando embeddings...")
textos = [f"{a['titulo']}. {a['contenido_visible'][:1000]}" for a in filas]
vecs = modelo.encode(textos, convert_to_tensor=True, show_progress_bar=True)
idx = {a["id"]: i for i, a in enumerate(filas)}
por_id = {a["id"]: a for a in filas}

def cuando(a):
    f = a["fecha_publicacion"] or a["fecha_captura"]
    return datetime.fromisoformat(f.replace("Z", "+00:00"))

def slug(a):
    o = a.get("outlets")
    return (o or {}).get("slug", "?") if isinstance(o, dict) else "?"

# --- Recolectar pares candidatos ---
pares = []
for a, b in combinations(filas, 2):
    if a["outlet_id"] == b["outlet_id"]:
        continue
    if abs((cuando(a) - cuando(b)).total_seconds()) > VENTANA_HORAS * 3600:
        continue
    compartidas_low = set(ents_low[a["id"]]) & set(ents_low[b["id"]])
    if len(compartidas_low) < MIN_ENTIDADES:
        continue
    sim = float(util.cos_sim(vecs[idx[a["id"]]], vecs[idx[b["id"]]]))
    # nombres originales de las entidades compartidas
    nombres = sorted({ents_low[a["id"]][e] for e in compartidas_low})
    pares.append((sim, len(compartidas_low), a["id"], b["id"], nombres))

pares.sort(reverse=True)  # mayor similitud primero
print(f"\nPares con >={MIN_ENTIDADES} entidades en ±{VENTANA_HORAS}h: {len(pares)}\n")
print("="*78)
print("Leé de arriba hacia abajo. Marcá dónde los pares dejan de ser 'misma noticia'.")
print("Ese punto de similitud es tu umbral real.")
print("="*78)

for rank, (sim, n_ent, id_a, id_b, nombres) in enumerate(pares, 1):
    a, b = por_id[id_a], por_id[id_b]
    print(f"\n[{rank:>3}] sim={sim:.3f} | {n_ent} entidades compartidas")
    print(f"   {slug(a):>13}: {a['titulo'][:70]}")
    print(f"   {slug(b):>13}: {b['titulo'][:70]}")
    print(f"   ents: {', '.join(nombres[:8])}")
    # URLs por si querés verificar un caso dudoso a mano
    # print(f"   A: {a.get('url','')}\n   B: {b.get('url','')}")