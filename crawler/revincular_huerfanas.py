# crawler/revincular_huerfanas.py — Tier 2, load-bearing.
#
# Fase 0: invalida vínculos de `resumenes_dia` que dejaron de cumplir la
# contención total contra la composición ACTUAL de su story.
# Fase 1: re-vincula filas que quedaron (o que la fase 0 acaba de dejar) con
# story_id NULL.
#
# POR QUÉ EXISTE LA FASE 1 (mecanismo verificado en código, 2026-08-23):
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
# POR QUÉ EXISTE LA FASE 0 (medido 2026-08-26, síntoma en producción):
# `story_articles` se borra entera y se reconstruye en cada corrida del
# clustering. La fase 1 arregla vínculos ROTOS (story_id NULL) pero nunca
# revisaba los que YA TIENEN dueño: un resumen vinculado el martes, cuando la
# contención se cumplía, sigue apuntando a esa story el miércoles aunque el
# clustering le haya quitado notas. Síntoma real en preview: un expediente
# mostraba "0 notas · 3 medios" con botón "Hechos del día", y el modal citaba a
# un medio ausente de esa historia — contaminación del expediente con material
# de otra historia, justo lo que la contención total existe para impedir.
# Medido: 244/259 vínculos (94,2%) siguen siendo coherentes; el trabajo de esta
# fase son ~15 filas, no un problema generalizado.
#
# EL PREDICADO ES UNO SOLO — `contiene_todos()`. Fase 0 (¿el vínculo vigente
# sigue siendo válido?) y fase 1 (¿qué story candidata es válida?) llaman a la
# MISMA función. Si divergieran, un vínculo podría des-vincularse y
# re-vincularse en cada corrida (oscilación): peor que el bug que esto arregla,
# porque el bug original al menos era estable. No reimplementar el criterio en
# ninguna de las dos fases.
#
# ORDEN DE EJECUCIÓN — NO NEGOCIABLE:
# Lee `story_articles`, y `reescribir_stories()` BORRA ESA TABLA ENTERA antes de
# reconstruirla (`delete().not_.is_("article_id","null")`). Correr esto en
# paralelo con el clustering leería una tabla vacía o a medio llenar y
# concluiría "ningún vínculo es válido" / "ninguna huérfana tiene story actual".
# Va ENCADENADO después del clustering, nunca en un cron propio.
#
# QUÉ TOCA: sólo la columna `story_id`, que es metadata derivada. No roza
# contenido_visible ni hash. `resumenes_dia` es caché regenerable (lo declara el
# docstring de guardar_resumen_dia), no archivo inmutable. El total de filas
# (count(*)) es invariante: esto re-apunta vínculos, nunca borra análisis.
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
    proyecto: una página incompleta acá se leería como 'no hay más filas'."""
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


def cargar_vinculadas():
    """Filas con story_id NOT NULL: universo sobre el que la fase 0 verifica
    contención. También se usa para derivar `dias_ocupados` (mismo snapshot,
    una sola lectura — no una segunda query que pudiera desincronizarse de
    ésta, ver nota de módulo sobre la trampa de la foto del estado)."""
    return _paginar(lambda d, h: (
        sb.table("resumenes_dia")
          .select("id, dia, story_id, article_ids")
          .not_.is_("story_id", "null")
          .range(d, h)
    ))


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
# El predicado — ÚNICO, compartido por las dos fases
# =======================================================================

def contiene_todos(sid, aids, pertenencia):
    """¿La story `sid` contiene TODOS los `aids` según la pertenencia ACTUAL?
    Es el criterio de CONTENCIÓN TOTAL del módulo: deliberadamente más
    estricto que 'la story que más comparte'. Si el día se partió entre dos
    clústeres, ese análisis ya no describe a ninguno de los dos y colgárselo
    a la mayoría sería mezclar en un expediente material de otra historia.

    Llamada por fase 0 (¿el vínculo vigente sigue siendo válido?) y por
    clasificar() en fase 1 (¿qué story candidata lo es?). Es la MISMA función
    en los dos sitios a propósito: dos implementaciones "equivalentes"
    podrían divergir en un caso borde y hacer que un vínculo oscile
    (se invalide y re-vincule) de corrida en corrida.

    Precondición: `aids` no vacío (los llamadores filtran antes; una fila sin
    article_ids no tiene contención que evaluar)."""
    return all(sid in pertenencia.get(aid, set()) for aid in aids)


# =======================================================================
# Fase 0 — invalidar vínculos que ya no cumplen contención
# =======================================================================

def clasificar_invalidaciones(vinculadas, pertenencia):
    """Filas con story_id NOT NULL cuyo vínculo YA NO cumple contención total
    contra la composición actual de story_articles. Devuelve la lista de
    filas (dicts completos, no solo ids) a invalidar."""
    a_invalidar = []
    for f in vinculadas:
        aids = f.get("article_ids") or []
        if not aids:
            continue  # nada que verificar: no se puede evaluar contención sin artículos
        if not contiene_todos(f["story_id"], aids, pertenencia):
            a_invalidar.append(f)
    return a_invalidar


# =======================================================================
# Fase 1 — re-vincular huérfanas (criterio sin cambios)
# =======================================================================

def clasificar(huerfana, pertenencia, dias_ocupados):
    """Decide qué hacer con UNA fila huérfana. Devuelve (clase, story_id|None, detalle)."""
    aids = huerfana.get("article_ids") or []
    dia = str(huerfana["dia"])[:10]

    if not aids:
        return "sin_articulos", None, "la fila no tiene article_ids"

    conjuntos = [pertenencia.get(aid, set()) for aid in aids]
    huerfanos = [aid for aid, s in zip(aids, conjuntos) if not s]
    if huerfanos:
        return ("sin_story", None,
                f"{len(huerfanos)}/{len(aids)} artículos no están en ningún clúster")

    # Universo de stories a probar: unión de las que tocan estos artículos.
    # Filtrado con contiene_todos (no set.intersection directo) para que fase 0
    # y fase 1 pasen literalmente por el mismo predicado — ver su docstring.
    universo = set.union(*conjuntos)
    candidatas = {sid for sid in universo if contiene_todos(sid, aids, pertenencia)}
    if not candidatas:
        # Cada artículo está en alguna story, pero ninguna las tiene todas:
        # el día quedó repartido entre clústeres.
        repartido = sorted(universo)
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
    # ── Fase 0: invalidar ──────────────────────────────────────────────
    vinculadas = cargar_vinculadas()
    huerfanas = cargar_huerfanas()
    print(f"[revincular] {len(vinculadas)} filas vinculadas, {len(huerfanas)} con story_id NULL")

    todos_aids = {aid for h in vinculadas + huerfanas for aid in (h.get("article_ids") or [])}
    pertenencia = cargar_pertenencia(todos_aids)
    print(f"[revincular] {len(todos_aids)} artículos consultados")

    a_invalidar = clasificar_invalidaciones(vinculadas, pertenencia)
    print(f"\n[revincular] fase 0 — invalidar: {len(a_invalidar)} vínculo(s) "
          f"ya no cumplen contención total")
    if verbose:
        for f in a_invalidar:
            print(f"    {f['id']} ({str(f['dia'])[:10]}, story {f['story_id'][:8]}…) "
                  f"— ya no contiene todos sus artículos")

    invalidadas = fallidas_invalidar = 0
    invalidadas_ok = set()
    if aplicar:
        for f in a_invalidar:
            try:
                sb.table("resumenes_dia").update({"story_id": None}).eq("id", f["id"]).execute()
                invalidadas += 1
                invalidadas_ok.add(f["id"])
            except Exception as e:
                fallidas_invalidar += 1
                print(f"    FALLO al invalidar {f['id']}: {e}")
        print(f"[revincular] {invalidadas} invalidada(s), {fallidas_invalidar} fallida(s)")
        # RELEER el estado real: la fase 1 debe ver las filas que la fase 0
        # ACABA de liberar, no una foto tomada antes de escribir (BITACORA
        # 2026-08-26 — un guard contra una foto no protege de lo que el propio
        # lote está escribiendo). Una re-lectura real también hereda
        # correctamente los fallos parciales: si una invalidación falló, esa
        # fila sigue vinculada en la base y así aparece acá.
        huerfanas = cargar_huerfanas()
    else:
        if a_invalidar:
            print(f"[revincular] DRY-RUN: no se invalidó nada; se simula su "
                  f"liberación para que el reporte de fase 1 sea honesto.")
        invalidadas = len(a_invalidar)   # cifra "se invalidarían", para el reporte
        invalidadas_ok = {f["id"] for f in a_invalidar}
        huerfanas = huerfanas + [{**f, "story_id": None} for f in a_invalidar]

    # dias_ocupados se deriva del MISMO snapshot de `vinculadas`, restando solo
    # lo que realmente quedó invalidado (aplicado o simulado según el modo) —
    # no una segunda query que pudiera ver un estado distinto al que acabamos
    # de razonar sobre arriba.
    dias_ocupados = {
        (f["story_id"], str(f["dia"])[:10])
        for f in vinculadas if f["id"] not in invalidadas_ok
    }

    # ── Fase 1: re-vincular huérfanas (incluye las liberadas arriba) ────
    if not huerfanas:
        print(f"\n[revincular] invalidadas={invalidadas} · revinculadas=0 · "
              f"repartidas=0 · sin_story=0")
        return

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

    # Desempate INTRA-LOTE. `dias_ocupados` es una foto tomada al inicio de esta
    # fase: no ve las filas que este mismo bucle está por escribir. Dos
    # huérfanas distintas pueden ser dos composiciones viejas del MISMO día
    # bajo la MISMA story — ambas pasan el guard `superada` y ambas se
    # escribirían, creando justo el duplicado que el guard existe para evitar.
    # NO es teórico: en la corrida del 2026-08-23 esta ausencia creó el
    # duplicado de e1369247 / 2026-08-21. Gana la composición más completa; el
    # resto se cuenta y se reporta, nunca se descarta en silencio.
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

    print("\n[revincular] clasificación (fase 1):")
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
        print(f"\n[revincular] invalidadas={invalidadas} · revinculadas={len(a_escribir)} · "
              f"repartidas={cuentas['repartida']} · sin_story={cuentas['sin_story']}")
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

    print(f"\n[revincular] invalidadas={invalidadas} · revinculadas={escritas} · "
          f"repartidas={cuentas['repartida']} · sin_story={cuentas['sin_story']}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Fase 0: invalida vínculos de resumenes_dia que ya no cumplen "
                    "contención total. Fase 1: re-vincula lo que queda (o quedó) con "
                    "story_id NULL. Corre DESPUÉS del clustering, nunca en paralelo.")
    p.add_argument("--aplicar", action="store_true",
                   help="escribe de verdad; sin esto es dry-run")
    p.add_argument("--verbose", action="store_true",
                   help="imprime una línea por cada fila invalidada y por cada huérfana NO re-vinculada")
    args = p.parse_args()
    revincular(aplicar=args.aplicar, verbose=args.verbose)
