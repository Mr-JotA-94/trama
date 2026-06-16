# diagnostico_fase2.py — Tier 0, SOLO LECTURA. No escribe a Supabase, no se commitea.
#
# Pregunta que responde: ¿son sensatos los umbrales "≥3 entidades" y "coseno ≥0.62"?
# Cómo: toma artículos reales recientes, mide entidades compartidas y similitud
#       entre TODOS los pares dentro de ±72h, e imprime la distribución.
#
# Instalación (una vez):
#   pip install supabase python-dotenv spacy sentence-transformers
#   python -m spacy download es_core_news_md
#
# Lee SUPABASE_URL y SUPABASE_SERVICE_KEY del .env (los mismos del crawler).

import os
from datetime import datetime, timedelta
from itertools import combinations

from dotenv import load_dotenv
from supabase import create_client
import spacy
from sentence_transformers import SentenceTransformer, util

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

VENTANA_HORAS = 72          # hipótesis a evaluar
TIPOS_NUCLEO = ("noticia",) # solo noticias forman clúster núcleo (ARQUITECTURA §6)
LIMITE = 200                # cuántos artículos traer (recientes). Sube si querés más señal.

print("Cargando modelos (primera vez descarga ~160MB)...")
nlp = spacy.load("es_core_news_md")
modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")  # 384 dims, = vector(384)

# --- 1. Traer artículos núcleo recientes ---
filas = (sb.table("articles")
         .select("id, outlet_id, titulo, contenido_visible, fecha_publicacion, fecha_captura, tipo")
         .in_("tipo", list(TIPOS_NUCLEO))
         .order("fecha_captura", desc=True)
         .limit(LIMITE)
         .execute().data)
print(f"Artículos núcleo traídos: {len(filas)}")

# --- 2. Entidades por artículo (NER sobre titulo + cuerpo) ---
# Normalizamos a minúsculas y nos quedamos con tipos que importan para noticias:
# personas, organizaciones, lugares, misceláneos (eventos/leyes suelen caer en MISC).
TIPOS_ENT = {"PER", "ORG", "LOC", "MISC"}

def entidades(art):
    texto = f"{art['titulo']}. {art['contenido_visible'][:2000]}"  # cap por velocidad
    doc = nlp(texto)
    return {e.text.strip().lower() for e in doc.ents
            if e.label_ in TIPOS_ENT and len(e.text.strip()) > 2}

print("Extrayendo entidades...")
ents = {a["id"]: entidades(a) for a in filas}
n_ent = [len(v) for v in ents.values()]
print(f"  Entidades por artículo: min={min(n_ent)} mediana={sorted(n_ent)[len(n_ent)//2]} max={max(n_ent)}")

# --- 3. Embeddings del cuerpo (mismo modelo que usará Fase 2) ---
print("Calculando embeddings...")
textos = [f"{a['titulo']}. {a['contenido_visible'][:1000]}" for a in filas]
vecs = modelo.encode(textos, convert_to_tensor=True, show_progress_bar=True)
idx = {a["id"]: i for i, a in enumerate(filas)}

# --- 4. Recorrer pares dentro de ±72h ---
def cuando(a):
    f = a["fecha_publicacion"] or a["fecha_captura"]
    return datetime.fromisoformat(f.replace("Z", "+00:00"))

pares_en_ventana = 0
dist_ent = {0:0, 1:0, 2:0, 3:0, 4:0}   # nº de pares por entidades compartidas (4 = "4 o más")
sims_por_ent = {0:[], 1:[], 2:[], 3:[]} # similitudes agrupadas por entidades compartidas (3 = "3+")

for a, b in combinations(filas, 2):
    if a["outlet_id"] == b["outlet_id"]:
        continue  # mismo medio no forma par de cobertura cruzada
    if abs((cuando(a) - cuando(b)).total_seconds()) > VENTANA_HORAS * 3600:
        continue
    pares_en_ventana += 1
    comp = len(ents[a["id"]] & ents[b["id"]])
    dist_ent[min(comp, 4)] += 1
    sim = float(util.cos_sim(vecs[idx[a["id"]]], vecs[idx[b["id"]]]))
    sims_por_ent[min(comp, 3)].append(sim)

# --- 5. Reporte ---
print("\n" + "="*60)
print(f"Pares de medios distintos dentro de ±{VENTANA_HORAS}h: {pares_en_ventana}")
print("\nDistribución de ENTIDADES compartidas por par:")
for k in sorted(dist_ent):
    etq = f"{k}+" if k == 4 else str(k)
    print(f"  {etq} entidades: {dist_ent[k]:>6} pares")

print("\nSimilitud coseno según entidades compartidas")
print("(esto te dice si '≥3 entidades' y 'coseno ≥0.62' apuntan al mismo lugar):")
for k in sorted(sims_por_ent):
    s = sims_por_ent[k]
    if not s:
        print(f"  {k}{'+' if k==3 else ''} ent: (sin pares)")
        continue
    s.sort()
    n = len(s)
    p50 = s[n//2]
    p90 = s[int(n*0.9)]
    print(f"  {k}{'+' if k==3 else ''} ent: n={n:>5} | sim mediana={p50:.3f} | p90={p90:.3f} | max={max(s):.3f}")

print("\nLectura: si los pares con 3+ entidades tienen sim mediana MUY por encima")
print("de los de 0 entidades, ambas señales coinciden y el plan es sano. Si la")
print("similitud no separa, hay que repensar el umbral o el orden de filtrado.")