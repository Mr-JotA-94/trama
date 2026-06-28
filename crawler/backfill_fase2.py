# crawler/backfill_fase2.py — Tier 2, load-bearing (escribe a articles).
# Rellena entidades y embedding de los artículos que aún no los tienen.
# IDEMPOTENTE: procesa solo WHERE embedding IS NULL. Correr cuantas veces quieras.
# NO modifica contenido_visible ni hash — solo agrega los campos de procesamiento.

import os
import time
import random
from dotenv import load_dotenv
from supabase import create_client
import spacy
from sentence_transformers import SentenceTransformer
from ner_filtro import extraer_entidades

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

LOTE = 50  # cuántos artículos por tanda al actualizar (no saturar la API)


def cargar_modelo_con_reintentos(nombre: str, intentos: int = 4, espera_base: int = 5):
    """Carga un SentenceTransformer tolerando 429/errores de red transitorios
    de HF. Backoff exponencial con jitter. Si agota intentos, re-lanza."""
    ultimo_error = None
    for i in range(intentos):
        try:
            return SentenceTransformer(nombre)
        except Exception as e:  # 429 de HF, timeouts, cortes de red
            ultimo_error = e
            if i == intentos - 1:
                break
            espera = espera_base * (2 ** i) + random.uniform(0, 3)
            print(f"  Fallo al cargar modelo (intento {i+1}/{intentos}): "
                  f"{type(e).__name__}. Reintento en {espera:.0f}s...")
            time.sleep(espera)
    raise RuntimeError(f"No se pudo cargar el modelo tras {intentos} intentos") from ultimo_error


def main():
    print("Cargando modelos...")
    nlp = spacy.load("es_core_news_md")
    modelo = cargar_modelo_con_reintentos("paraphrase-multilingual-MiniLM-L12-v2")

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