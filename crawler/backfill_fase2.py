# crawler/backfill_fase2.py — Tier 2, load-bearing (escribe a articles).
# Rellena entidades y embedding de los artículos que aún no los tienen.
# IDEMPOTENTE: procesa solo WHERE embedding IS NULL. Correr cuantas veces quieras.
# NO modifica contenido_visible ni hash — solo agrega los campos de procesamiento.

import os
from dotenv import load_dotenv
from supabase import create_client
import spacy
from sentence_transformers import SentenceTransformer

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

TIPOS_ENT = {"PER", "ORG", "LOC", "MISC"}
LOTE = 50  # cuántos artículos por tanda al actualizar (no saturar la API)

# Filtro anti-basura de NER: descarta los falsos positivos que vimos en el
# diagnóstico ("Además", "Asimismo", frases largas que spaCy marca como entidad).
STOPWORDS_ENT = {
    "además", "asimismo", "según", "sin embargo", "por su parte",
    "no obstante", "en cambio", "entre tanto", "mientras tanto",
}

def entidad_valida(texto: str) -> bool:
    t = texto.strip()
    if len(t) <= 2 or len(t) > 40:          # muy corta o frase larga (no es entidad)
        return False
    if t.lower() in STOPWORDS_ENT:
        return False
    if t.count(" ") > 4:                    # 5+ palabras: casi seguro ruido de NER
        return False
    return True

def extraer_entidades(nlp, titulo: str, cuerpo: str) -> list[str]:
    doc = nlp(f"{titulo}. {cuerpo[:2000]}")
    vistas, fuera = set(), []
    for e in doc.ents:
        if e.label_ not in TIPOS_ENT:
            continue
        t = e.text.strip()
        if not entidad_valida(t):
            continue
        clave = t.lower()
        if clave not in vistas:             # dedup por forma en minúsculas
            vistas.add(clave)
            fuera.append(t)                 # guardamos la forma original
    return fuera

def main():
    print("Cargando modelos...")
    nlp = spacy.load("es_core_news_md")
    modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    # Solo lo no procesado. Trae lo necesario; pagina para no cargar todo en RAM.
    pendientes = (sb.table("articles")
                  .select("id, titulo, contenido_visible")
                  .is_("embedding", "null")
                  .execute().data)
    print(f"Artículos por procesar: {len(pendientes)}")
    if not pendientes:
        print("Nada pendiente. Backfill al día.")
        return

    procesados = 0
    for i in range(0, len(pendientes), LOTE):
        tanda = pendientes[i:i + LOTE]
        textos = [f"{a['titulo']}. {a['contenido_visible'][:1000]}" for a in tanda]
        vectores = modelo.encode(textos, show_progress_bar=False)

        for art, vec in zip(tanda, vectores):
            ents = extraer_entidades(nlp, art["titulo"], art["contenido_visible"])
            # UPDATE solo de campos de procesamiento. contenido_visible/hash intactos.
            sb.table("articles").update({
                "entidades": ents,
                "embedding": vec.tolist(),
            }).eq("id", art["id"]).execute()
            procesados += 1

        print(f"  {procesados}/{len(pendientes)}")

    print(f"Backfill completo: {procesados} artículos.")

if __name__ == "__main__":
    main()