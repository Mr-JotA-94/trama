# diagnostico_ancla.py — DESECHABLE, no se commitea (regla de scope).
# Mide qué artículo elige cada criterio de ancla sobre los clústeres reales.
# No escribe en la base: solo imprime. Correr: python diagnostico_ancla.py
from collections import defaultdict
import numpy as np
from clustering_fase2 import (
    cargar_articulos, calcular_idf, construir_clusteres, normaliza_ents,
)

def analizar(ids, por_id):
    vecs = {i: np.asarray(por_id[i]["embedding"], dtype=np.float64) for i in ids}
    centroide = np.mean([vecs[i] for i in ids], axis=0); nc = np.linalg.norm(centroide)
    ents = {i: normaliza_ents(por_id[i]["entidades"]) for i in ids}
    union = set().union(*ents.values())
    cdf = defaultdict(int)
    for i in ids:
        for e in ents[i]:
            cdf[e] += 1
    peso_total = sum(cdf.values())
    filas = []
    for i in ids:
        v = vecs[i]
        neutr = float(v @ centroide / (np.linalg.norm(v) * nc))
        ca = len(ents[i] & union) / max(len(union), 1)          # cobertura ACTUAL
        cf = sum(cdf[e] for e in ents[i]) / max(peso_total, 1)  # cobertura por FRECUENCIA
        filas.append({"out": str(por_id[i]["outlet_id"])[:8],
                      "tit": (por_id[i]["titulo"] or "")[:58],
                      "neutr": neutr, "ca": ca, "cf": cf,
                      "p_act": neutr*ca, "p_frq": neutr*cf})
        # Calcula el pick "piso de neutralidad -> max cobertura" a dos umbrales.
    neutrs = sorted(x["neutr"] for x in filas)
    def percentil(p):
        if not neutrs: return 0.0
        k = (len(neutrs) - 1) * p
        lo = int(k); hi = min(lo + 1, len(neutrs) - 1)
        return neutrs[lo] + (neutrs[hi] - neutrs[lo]) * (k - lo)
    return filas, percentil
    

def main():
    arts = cargar_articulos()
    idf, _ = calcular_idf(arts)
    clusteres, por_id = construir_clusteres(arts, idf)
    clusteres.sort(key=len, reverse=True)
    for ids in clusteres:
        f, percentil = analizar(ids, por_id)
        a_act = max(f, key=lambda x: x["p_act"])
        # Piso de neutralidad -> entre los que pasan, el de mayor cobertura actual.
        def pick_piso(q):
            piso = percentil(q)
            cand = [x for x in f if x["neutr"] >= piso] or f
            return max(cand, key=lambda x: x["ca"])
        a_p50 = pick_piso(0.50)
        a_p75 = pick_piso(0.75)
        cambia = len({a_act["tit"], a_p50["tit"], a_p75["tit"]}) > 1
        print("="*80)
        print(f"CLÚSTER n={len(ids)} medios={len({x['out'] for x in f})}"
              f"{'   <<< DIFIERE' if cambia else ''}")
        print(f"  ACTUAL (neutr*cob)        : {a_act['tit']}")
        print(f"  PISO p50 -> max cobertura : {a_p50['tit']}")
        print(f"  PISO p75 -> max cobertura : {a_p75['tit']}")
        if len(ids) >= 6:
            print(f"  {'out':>8} {'neutr':>6} {'cob_a':>6} {'p_act':>6}  titulo")
            for x in sorted(f, key=lambda x: x["neutr"], reverse=True):
                print(f"  {x['out']:>8} {x['neutr']:>6.3f} {x['ca']:>6.3f} {x['p_act']:>6.3f}  {x['tit']}")

if __name__ == "__main__":
    main()