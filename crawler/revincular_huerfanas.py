# crawler/revincular_huerfanas.py — Tier 2, load-bearing.
#
# Re-vincula filas de `resumenes_dia` que quedaron con story_id NULL.
#
# POR QUÉ EXISTE (mecanismo verificado en código, 2026-08-23):
# `clustering_fase2.reescribir_stories()` calcula el sid de cada clúster con
# uuid5 sembrado en la URL del artículo MÁS ANTIGUO. Un clúster que crece e
# incorpora una nota anterior a su semilla cambia de sid. El sid viejo sale de
# `sids_actuales`, la poda borra esa fila de `stories`, y la FK
# `resumenes_dia.story_id ON DELETE SET NULL` deja el análisis huérfano.
# El análisis existe y está pagado; simplemente ya nadie lo puede ver, porque la
# web consulta por story_id.
#
# POR QUÉ NO LO ARREGLA LA ADOPCIÓN QUE YA EXISTE:
# `procesar_dia` adopta por `dia_key` = sha256 del set de hashes del día. Sólo
# rescata si la composición del día es IDÉNTICA. Un clúster que pasó de 8 a 47
# artículos cambió la composición de sus días -> dia_key nuevo -> esas filas no
# se adoptan nunca. Este módulo re-vincula por PERTENENCIA de los artículos, que
# sobrevive al cambio de composición.
#
# ORDEN DE EJECUCIÓN — NO NEGOCIABLE:
# Lee `story_articles`, y `reescribir_stories()` BORRA ESA TABLA ENTERA antes de
# reconstruirla (`delete().not_.is_("article_id","null")`). Correr esto en
# paralelo con el clustering leería una tabla vacía o a medio llenar y
# concluiría "ninguna huérfana tiene story actual". Va ENCADENADO después del
# clustering, nunca en un cron propio.
#
# QUÉ TOCA: sólo la columna `story_id`, que es metadata derivada. No roza
# contenido_visible ni hash. `resumenes_dia` es caché regenerable (lo declara el
# docstring de guardar_resumen_dia), no archivo inmutable.
#
# SEGURO POR DISEÑO: `guardar_resumen_dia` retira las filas previas del mismo
# (story_id, dia) tras un insert exitoso. Si re-vinculamos una fila y más tarde
# el backfill regenera ese día, la vieja se retira sola. No produce duplicados.

import os
import argparse
from collections import defaultdict

from dotenv import load_dotenv
from supabase import create_client

# override=True a propósito: deuda registrada el 2026-08-22 — en local, una
# variable de entorno de Windows pisa el .env en silencio.
load_dotenv(override=True)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

PAGINA = 1000   # patrón del módulo: un .select() sin paginar se trunca en silencio
LOTE_IN = 200   # tamaño de los .in_(): URLs largas revientan el endpoint


# =======================================================================
# Lectura
# =======================================================================

def _paginar(construir_query):
    """Ejecuta una query paginada hasta agotarla. `construir_query` recibe
    (desde, hasta) y devuelve la query lista para .execute().
    Existe porque el truncado silencioso de PostgREST ya mordió antes en este
    proyecto: una página incompleta acá se leería como 'no hay más huérfanas'."""
    filas, desde = [], 0
    while True:
        lote = construir_query(desde, desde + PAGINA - 1).execute().data or []
        filas.extend(lote)
        if len(lote) < PAGINA:
            return filas
        desde += PAGINA


def cargar_huerfanas():
    return _paginar(lambda d, h: (
        sb.table("resumenes_dia")
          .select("id, dia, article_ids, member_hashes")
          .is_("story_id", "null")
          .range(d, h)
    ))


def cargar_dias_ocupados():
    """Set de (story_id, dia) que YA tienen análisis vigente. Una huérfana cuyo
    día cae acá es material SUPERADO: el día se regeneró con la composición
    nueva, y re-vincular la versión vieja sería mostrar el peor de los dos."""
    filas = _paginar(lambda d, h: (
        sb.table("resumenes_dia")
          .select("story_id, dia")
          .not_.is_("story_id", "null")
          .range(d, h)
    ))
    return {(f["story_id"], str(f["dia"])[:10]) for f in filas}


def cargar_pertenencia(article_ids):
    """article_id -> set(story_id) según el estado ACTUAL de story_articles.
    En condiciones normales cada artículo cae en una sola story, pero no se
    asume: si el beat-split dejara un artículo en dos, queremos verlo, no
    promediarlo."""
    mapa = defaultdict(set)
    ids = sorted(article_ids)
    for k in range(0, len(ids), LOTE_IN):
        trozo = ids[k:k + LOTE_IN]
        desde = 0
        while True:
            lote = (sb.table("story_articles")
                    .select("story_id, article_id")
                    .in_("article_id", trozo)
                    .range(desde, desde + PAGINA - 1)
                    .execute().data) or []
            for f in lote:
                mapa[f["article_id"]].add(f["story_id"])
            if len(lote) < PAGINA:
                break
            desde += PAGINA
    return mapa


# =======================================================================
# Clasificación
# =======================================================================

def clasificar(huerfana, pertenencia, dias_ocupados):
    """Decide qué hacer con UNA fila huérfana. Devuelve (clase, story_id|None, detalle).

    Criterio de re-vinculación: CONTENCIÓN TOTAL — la story candidata debe
    contener TODOS los artículos del día. Es deliberadamente más estricto que
    'la story que más comparte': si el día se partió entre dos clústeres, ese
    análisis ya no describe a ninguno de los dos y re-vincularlo a la mayoría
    sería colgarle a una historia un análisis que incluye material de otra.
    Preferimos dejarlo huérfano y visible en el conteo."""
    aids = huerfana.get("article_ids") or []
    dia = str(huerfana["dia"])[:10]

    if not aids:
        return "sin_articulos", None, "la fila no tiene article_ids"

    conjuntos = [pertenencia.get(aid, set()) for aid in aids]
    huerfanos = [aid for aid, s in zip(aids, conjuntos) if not s]
    if huerfanos:
        return ("sin_story", None,
                f"{len(huerfanos)}/{len(aids)} artículos no están en ningún clúster")

    candidatas = set.intersection(*conjuntos)
    if not candidatas:
        # Cada artículo está en alguna story, pero ninguna las tiene todas:
        # el día quedó repartido entre clústeres.
        repartido = sorted({sid for s in conjuntos for sid in s})
        return ("repartida", None,
                f"el día quedó repartido entre {len(repartido)} clústeres")

    if len(candidatas) > 1:
        return ("ambigua", None,
                f"{len(candidatas)} stories contienen todos los artículos")

    sid = candidatas.pop()
    if (sid, dia) in dias_ocupados:
        return "superada", sid, "ese día ya fue regenerado bajo la story actual"
    return "revinculable", sid, ""


def mayoritaria(huerfana, pertenencia):
    """Criterio ALTERNATIVO, sólo para el informe: la story que más artículos
    comparte. Es el que usó el diag SQL. Se reporta al lado del criterio
    estricto para que la diferencia entre ambos sea visible y decidible con
    datos, en vez de que el script parezca 'no cuadrar' con el diag."""
    conteo = defaultdict(int)
    for aid in (huerfana.get("article_ids") or []):
        for sid in pertenencia.get(aid, set()):
            conteo[sid] += 1
    if not conteo:
        return None
    return max(conteo.items(), key=lambda kv: kv[1])[0]


# =======================================================================
# Ejecución
# =======================================================================

def revincular(aplicar=False, verbose=False):
    huerfanas = cargar_huerfanas()
    print(f"[revincular] {len(huerfanas)} filas con story_id NULL")
    if not huerfanas:
        return

    todos_aids = {aid for h in huerfanas for aid in (h.get("article_ids") or [])}
    pertenencia = cargar_pertenencia(todos_aids)
    dias_ocupados = cargar_dias_ocupados()
    print(f"[revincular] {len(todos_aids)} artículos consultados, "
          f"{len(dias_ocupados)} días ya ocupados")

    cuentas = defaultdict(int)
    # (story_id, dia) -> [(n_articulos, fila_id)] — se agrupa ANTES de escribir.
    candidatas = defaultdict(list)
    # Cuántas que el criterio estricto descarta SÍ tendrían una story mayoritaria.
    # Es la medida de cuánto estamos dejando sobre la mesa por ser estrictos.
    rescatables_por_mayoria = 0

    for h in huerfanas:
        clase, sid, detalle = clasificar(h, pertenencia, dias_ocupados)
        cuentas[clase] += 1
        if clase == "revinculable":
            candidatas[(sid, str(h["dia"])[:10])].append(
                (len(h.get("article_ids") or []), h["id"]))
        else:
            if clase in ("repartida", "ambigua") and mayoritaria(h, pertenencia):
                rescatables_por_mayoria += 1
        if verbose and clase != "revinculable":
            print(f"    {h['id']} ({str(h['dia'])[:10]}) — {clase}: {detalle}")

    # Desempate INTRA-LOTE. `dias_ocupados` es una foto tomada al inicio: no ve
    # las filas que este mismo bucle está por escribir. Dos huérfanas distintas
    # pueden ser dos composiciones viejas del MISMO día bajo la MISMA story —
    # ambas pasan el guard `superada` y ambas se escribirían, creando justo el
    # duplicado que el guard existe para evitar.
    # NO es teórico: en la corrida del 2026-08-23 esta ausencia creó el duplicado
    # de e1369247 / 2026-08-21. Gana la composición más completa; el resto se
    # cuenta y se reporta, nunca se descarta en silencio.
    a_escribir = []
    for (sid, dia), grupo in candidatas.items():
        grupo.sort(key=lambda t: (-t[0], t[1]))   # más artículos primero; id desempata estable
        a_escribir.append((grupo[0][1], sid))
        if len(grupo) > 1:
            cuentas["colision_lote"] += len(grupo) - 1
            print(f"    colisión en ({sid[:8]}…, {dia}): {len(grupo)} huérfanas al mismo día "
                  f"— gana la de {grupo[0][0]} artículos, "
                  f"{len(grupo) - 1} descartada(s): "
                  f"{', '.join(fid for _, fid in grupo[1:])}")

    print("\n[revincular] clasificación:")
    for clase in ("revinculable", "colision_lote", "superada", "repartida",
                  "ambigua", "sin_story", "sin_articulos"):
        if cuentas[clase]:
            print(f"    {clase:<14} {cuentas[clase]}")
    if cuentas["colision_lote"]:
        print(f"    {'→ se escriben':<14} {len(a_escribir)} "
              f"(revinculable − colisiones descartadas)")
    if rescatables_por_mayoria:
        print(f"\n[revincular] NOTA: {rescatables_por_mayoria} de las descartadas tendrían "
              f"una story mayoritaria. El criterio estricto (contención total) las deja "
              f"fuera a propósito. Si ese número es alto, la decisión de criterio se "
              f"revisa CON este dato, no en abstracto.")

    if not aplicar:
        print(f"\n[revincular] DRY-RUN: no se escribió nada. "
              f"{len(a_escribir)} filas se re-vincularían. Usá --aplicar para escribir.")
        return

    escritas = fallidas = 0
    for fila_id, sid in a_escribir:
        try:
            sb.table("resumenes_dia").update({"story_id": sid}).eq("id", fila_id).execute()
            escritas += 1
        except Exception as e:
            fallidas += 1
            print(f"    FALLO al re-vincular {fila_id}: {e}")
    print(f"\n[revincular] {escritas} re-vinculadas, {fallidas} falladas")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Re-vincula filas de resumenes_dia con story_id NULL. "
                    "Corre DESPUÉS del clustering, nunca en paralelo.")
    p.add_argument("--aplicar", action="store_true",
                   help="escribe de verdad; sin esto es dry-run")
    p.add_argument("--verbose", action="store_true",
                   help="imprime una línea por cada fila NO re-vinculada")
    args = p.parse_args()
    revincular(aplicar=args.aplicar, verbose=args.verbose)