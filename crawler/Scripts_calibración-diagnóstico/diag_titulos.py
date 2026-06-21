# crawler/diag_titulos.py — DIAGNÓSTICO. No escribe nada. Tier 2.
import os, re
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# --- Heurística de título-cita (PROVISIONAL, juzgá falsos positivos a ojo) ---
VERBOS = (r"dijo|dice|aseguró|asegura|señaló|señala|afirmó|afirma|reiteró|reitera|"
          r"advirtió|advierte|respondió|responde|reveló|revela|anunció|anuncia|"
          r"ratificó|ratifica|declaró|declara|sostuvo|manifestó|confesó|admitió|"
          r"pidió|denunció|cuestionó|criticó|lamentó|insistió|aclaró")
RE_COMILLA = re.compile(r'["\'«»“”‘’]')
RE_VERBO   = re.compile(rf'\b({VERBOS})\b', re.I)
RE_DELANTE = re.compile(r'^\s*["«“\'‘].{8,}?["»”\'’]\s*:')   # "cita": atribución
RE_ATRAS   = re.compile(r':\s*["«“\'‘].{8,}', re.S)          # atribución: "cita…

def es_cita(t: str) -> bool:
    t = (t or "").strip()
    if not RE_COMILLA.search(t):
        return False
    if RE_DELANTE.search(t) or RE_ATRAS.search(t):
        return True
    return bool(RE_VERBO.search(t))   # comillas + verbo de habla

def cargar_titulos():
    m, d = {}, 0
    while True:
        q = sb.table("articles").select("id, titulo").range(d, d+999).execute().data
        if not q: break
        for a in q: m[a["id"]] = a["titulo"]
        d += 1000
    return m

titulos = cargar_titulos()
stories = sb.table("stories").select("id, titulo, n_articulos, n_medios").execute().data
sa = sb.table("story_articles").select("story_id, article_id, score_neutralidad").execute().data

por_story = {}
for r in sa:
    por_story.setdefault(r["story_id"], []).append(r)

filas = []
for s in stories:
    miembros = por_story.get(s["id"], [])
    tit_pipe = s["titulo"] or ""
    top = max(miembros, key=lambda r: r["score_neutralidad"] or 0) if miembros else None
    tit_maxneut = titulos.get(top["article_id"], "") if top else ""
    tits = [titulos.get(r["article_id"], "") for r in miembros]
    alts = [t for t in tits if t and not es_cita(t)]
    filas.append(dict(id=s["id"][:8], n=s["n_articulos"], med=s["n_medios"],
                      pipe_cita=es_cita(tit_pipe), maxneut_cita=es_cita(tit_maxneut),
                      difieren=tit_pipe.strip() != tit_maxneut.strip(),
                      n_alt=len(alts), tit=tit_pipe, alts=alts))

citas = [f for f in filas if f["pipe_cita"]]
con_alt = [f for f in citas if f["n_alt"] >= 1]
print(f"Clústeres: {len(filas)}")
print(f"Con título-cita: {len(citas)}")
print(f"  con ≥1 alternativa no-cita: {len(con_alt)}")
print(f"  SIN alternativa (todos cita/teaser): {len(citas)-len(con_alt)}")
print(f"stories.titulo ≠ titular de mayor neutralidad: {sum(f['difieren'] for f in filas)} clústeres")
print("\n== CLÚSTERES CON TÍTULO-CITA ==")
for f in citas:
    print(f"\n[{f['id']}] {f['n']}art/{f['med']}med · alts no-cita: {f['n_alt']}")
    print(f"  ACTUAL: {f['tit'][:95]}")
    for a in f["alts"][:3]:
        print(f"   alt → {a[:95]}")