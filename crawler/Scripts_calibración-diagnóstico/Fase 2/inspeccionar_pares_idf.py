# inspeccionar_pares_idf.py — Tier 0, SOLO LECTURA.
# Recalcula los pares ponderando entidades por rareza (IDF) en vez de contarlas.
# Pregunta: ¿el peso-IDF separa "mismo hecho" de "mismo tema" mejor que el conteo?
#
# Reusa modelos y dependencias del script anterior. Nada nuevo que instalar.

import os
import math
from datetime import datetime
from itertools import combinations
from collections import defaultdict

from dotenv import load_dotenv
from supabase import create_client
import spacy
from sentence_transformers import SentenceTransformer, util

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

VENTANA_HORAS = 72
MIN_ENTIDADES = 3          # mismo filtro de entrada que antes, para comparar manzanas con manzanas
LIMITE = 200
TIPOS_ENT = {"PER", "ORG", "LOC", "MISC"}

print("Cargando modelos...")
nlp = spacy.load("es_core_news_md")
modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

filas = (sb.table("articles")
         .select("id, outlet_id, titulo, fecha_publicacion, fecha_captura, contenido_visible, outlets(slug)")
         .eq("tipo", "noticia")
         .order("fecha_captura", desc=True)
         .limit(LIMITE)
         .execute().data)
print(f"Artículos: {len(filas)}")

def entidades(art):
    texto = f"{art['titulo']}. {art['contenido_visible'][:2000]}"
    doc = nlp(texto)
    return {e.text.strip() for e in doc.ents
            if e.label_ in TIPOS_ENT and len(e.text.strip()) > 2}

print("Extrayendo entidades...")
ents = {a["id"]: entidades(a) for a in filas}
# Mapa lower->original para mostrar; comparación en lower para no duplicar por mayúsculas
ents_low = {k: {e.lower(): e for e in v} for k, v in ents.items()}

# --- IDF: en cuántos artículos aparece cada entidad (sobre la muestra) ---
N = len(filas)
doc_freq = defaultdict(int)
for k, mapa in ents_low.items():
    for e_low in mapa:
        doc_freq[e_low] += 1
# Peso de cada entidad. +1 en denominador evita div por cero; log da la escala.
idf = {e: math.log(N / df) for e, df in doc_freq.items()}

# Muestra de control: las entidades más comunes (peso bajo) vs más raras (peso alto)
comunes = sorted(doc_freq.items(), key=lambda x: -x[1])[:8]
print("\nEntidades más COMUNES (peso IDF bajo, casi no discriminan):")
for e, df in comunes:
    print(f"   {df:>3} notas | IDF={idf[e]:.2f} | {ents_low[next(k for k in ents_low if e in ents_low[k])][e]}")

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

# --- Recolectar pares con su score-IDF y su similitud ---
pares = []
for a, b in combinations(filas, 2):
    if a["outlet_id"] == b["outlet_id"]:
        continue
    if abs((cuando(a) - cuando(b)).total_seconds()) > VENTANA_HORAS * 3600:
        continue
    comp = set(ents_low[a["id"]]) & set(ents_low[b["id"]])
    if len(comp) < MIN_ENTIDADES:
        continue
    peso_idf = sum(idf[e] for e in comp)          # <-- la métrica nueva
    sim = float(util.cos_sim(vecs[idx[a["id"]]], vecs[idx[b["id"]]]))
    nombres = sorted(comp, key=lambda e: -idf[e]) # entidades de la más rara a la más común
    nombres_orig = [ents_low[a["id"]][e] for e in nombres]
    pares.append({
        "sim": sim, "peso": peso_idf, "n": len(comp),
        "a": a["id"], "b": b["id"], "ents": nombres_orig,
        "ents_low": nombres,
    })

# --- Ranking por PESO-IDF (la lista que importa juzgar) ---
pares.sort(key=lambda p: -p["peso"])
print(f"\n{'='*80}")
print(f"RANKING POR PESO-IDF (entidades raras pesan más). Top 30.")
print("Pregunta: ¿los hechos puntuales suben y la 'zona gris electoral' baja?")
print(f"{'='*80}")
for rank, p in enumerate(pares[:30], 1):
    a, b = por_id[p["a"]], por_id[p["b"]]
    # marcamos las entidades raras (IDF alto) que cargan el peso
    detalle = ", ".join(f"{e}[{idf[le]:.1f}]" for e, le in zip(p["ents"][:5], p["ents_low"][:5]))
    print(f"\n[{rank:>3}] peso_idf={p['peso']:.1f} | sim={p['sim']:.3f} | {p['n']} ents")
    print(f"   {slug(a):>13}: {a['titulo'][:68]}")
    print(f"   {slug(b):>13}: {b['titulo'][:68]}")
    print(f"   ents(rara→común): {detalle}")

# --- Cola: los de menor peso-IDF, para ver el piso ---
print(f"\n{'='*80}")
print("COLA POR PESO-IDF (entidades genéricas, peso bajo). Últimos 10.")
print(f"{'='*80}")
for rank, p in enumerate(pares[-10:], len(pares)-9):
    a, b = por_id[p["a"]], por_id[p["b"]]
    detalle = ", ".join(f"{e}[{idf[le]:.1f}]" for e, le in zip(p["ents"][:5], p["ents_low"][:5]))
    print(f"\n[{rank:>3}] peso_idf={p['peso']:.1f} | sim={p['sim']:.3f} | {p['n']} ents")
    print(f"   {slug(a):>13}: {a['titulo'][:68]}")
    print(f"   {slug(b):>13}: {b['titulo'][:68]}")
    print(f"   ents(rara→común): {detalle}")