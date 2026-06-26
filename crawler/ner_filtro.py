# crawler/ner_filtro.py — fuente UNICA del filtro NER. Lo importan backfill_fase2.py
# (articulos nuevos) y rebackfill_ner.py (re-proceso del banco). Misma logica = pasado
# y futuro consistentes. Validado con diag_ner (Diag B, 2026-06-26): >=1 PROPN o sigla
# descarta ruido (MISC 57%) sin matar señal (PER/ORG/LOC ~96% conservado).

TIPOS_ENT = {"PER", "ORG", "LOC", "MISC"}

# Medios del proyecto: ORG reales que ligan por FUENTE, no por hecho. Lista CERRADA.
# Ampliar SOLO al activar un medio nuevo. NO crecer con boilerplate (eso es deuda de
# extraccion, no de NER) — "el espectador manténgase" es un sintoma de CTA en el cuerpo.
MEDIOS = {
    "el espectador", "el tiempo", "el colombiano", "voragine", "vorágine",
    "las2orillas", "noticias caracol", "el espectador manténgase",
}

MAX_CHARS = 60    # institucionales largas reales llegan a ~43 chars
MAX_TOKENS = 8    # guardia anti-oracion; las institucionales mas largas vistas tienen <=7 tokens

def es_sigla(texto: str) -> bool:
    s = texto.replace(".", "").strip()
    return s.isalpha() and s.isupper() and 2 <= len(s) <= 6

def entidad_valida(ent) -> bool:
    """ent = Span de spaCy (iterable de Tokens con .pos_). Conserva si:
    tiene >=1 token PROPN o es sigla, no es medio, y cabe en los topes."""
    t = ent.text.strip()
    if not (2 <= len(t) <= MAX_CHARS):
        return False
    if len(t.split()) > MAX_TOKENS:
        return False
    if t.lower() in MEDIOS:
        return False
    return any(tok.pos_ == "PROPN" for tok in ent) or es_sigla(t)

def extraer_entidades(nlp, titulo: str, cuerpo: str) -> list[str]:
    """Titulo + primeros 2000 chars. Dedup por minusculas, guarda primera forma original."""
    doc = nlp(f"{titulo}. {(cuerpo or '')[:2000]}")
    vistas, fuera = set(), []
    for e in doc.ents:
        if e.label_ not in TIPOS_ENT:
            continue
        if not entidad_valida(e):
            continue
        clave = e.text.strip().lower()
        if clave not in vistas:
            vistas.add(clave)
            fuera.append(e.text.strip())
    return fuera