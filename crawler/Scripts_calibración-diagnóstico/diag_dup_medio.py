# diag_dup_medio.py — READ-ONLY. ¿Los duplicados de medio dentro de un clúster
# son recapturas del mismo URL o URLs distintos? Lee stories ya escritas en BD.
import os
from collections import defaultdict
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# story_articles -> article_ids por story
sa = defaultdict(list)
desde = 0
while True:
    q = sb.table("story_articles").select("story_id, article_id").range(desde, desde+999).execute().data
    if not q: break
    for r in q: sa[r["story_id"]].append(r["article_id"])
    desde += 1000

# articles: id -> (outlet_id, url)
art = {}
desde = 0
while True:
    q = sb.table("articles").select("id, outlet_id, url").range(desde, desde+999).execute().data
    if not q: break
    for r in q: art[r["id"]] = (r["outlet_id"], r["url"])
    desde += 1000

n_stories = len(sa)
con_dup_medio = 0          # clústeres con 2+ articles del mismo medio
recaptura_pura = 0         # esos duplicados son MISMO url (recaptura)
url_distinto = 0           # esos duplicados son URLs distintos (cobertura)
mezcla = 0
detalle = []

for sid, ids in sa.items():
    por_medio = defaultdict(list)
    for i in ids:
        if i not in art: continue
        o, u = art[i]
        por_medio[o].append(u)
    # ¿hay algún medio con 2+ artículos en este clúster?
    medios_dup = {o: urls for o, urls in por_medio.items() if len(urls) > 1}
    if not medios_dup: continue
    con_dup_medio += 1
    hubo_recap = hubo_dist = False
    for o, urls in medios_dup.items():
        if len(set(urls)) == 1:        # todas mismas url = recaptura pura
            hubo_recap = True
        elif len(set(urls)) == len(urls):  # todas distintas = URLs distintos
            hubo_dist = True
        else:
            hubo_recap = hubo_dist = True
    if hubo_recap and hubo_dist: mezcla += 1
    elif hubo_recap: recaptura_pura += 1
    else: url_distinto += 1
    # guardar un puñado para inspección
    if len(detalle) < 15:
        resumen = {o: f"{len(urls)} arts / {len(set(urls))} urls" for o,urls in medios_dup.items()}
        detalle.append((sid, len(ids), resumen))

print(f"Stories totales: {n_stories}")
print(f"Con duplicado de medio (2+ arts mismo medio): {con_dup_medio}")
print(f"  recaptura pura (mismo url):     {recaptura_pura}")
print(f"  URLs distintos (cobertura):     {url_distinto}")
print(f"  mezcla:                         {mezcla}")
print(f"\n-- muestra (story, n_arts, {{medio: arts/urls}}) --")
for sid, n, res in detalle:
    print(f"  {sid[:8]} n={n} {res}")