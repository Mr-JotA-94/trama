# BITÁCORA — TRAMA

Registro de decisiones, operaciones sobre datos y deuda técnica conocida.
No es documentación de arquitectura (eso vive en ARQUITECTURA.md) ni migraciones
(esas viven en supabase/migrations/). Aquí va lo que pasó y por qué, para que el
yo-del-futuro entienda el estado actual sin tener que reconstruirlo de memoria.

---

## Operaciones sobre datos (truncates y borrados)

Regla de Trama: el archivo es inmutable, nada se borra. Los truncates de abajo
ocurrieron SOLO durante la fase de calibración (Fase 1), cuando el archivo aún no
tenía valor histórico. A partir de Fase 2, truncar deja de ser aceptable: los
cambios de esquema se hacen con migraciones que preservan datos.  

- **2026-06-27** — recómputo de story_relations con criterio recalibrado (NO es truncate
  de archivo). Al correr clustering_fase2.py con las capas nuevas (canon/ALIAS/GEO_EXTRA +
  FRAC_GENERICA=0.08), story_relations se reconstruyó (delete-then-insert, caché derivada):
  ~101 pares / 202 filas espejo sobre 149 clústeres. El crecimiento vs la medición offline
  (68 pares) es real, no bug: dos mega-historias estallaron entre corridas (terremoto de
  Venezuela y formación de gabinete de De la Espriella). Validado: hub Pastrana grado 4,
  control de andamiaje = 0 pares. articles jamás se toca; story_relations es reconstruible.

- **2026-06-27** — APRENDIZAJE (regresión de cronología de ediciones). Colapsar en
  el pipeline no exime de verificar qué capas leían las capturas SIN colapsar. El
  colapso por URL del 2026-06-23 documentó "el historial de capturas se preserva
  intacto" — cierto para `articles`, pero indujo a no revisar que `story_articles`
  (lo que la vista de cronología leía) sí perdía las capturas intermedias. Resultado:
  la cronología dejó de mostrar ediciones sin que nadie lo notara hasta semanas
  después. Regla para el yo-futuro: cuando se introduzca una deduplicación/colapso en
  una capa, auditar TODAS las capas aguas abajo que dependían del dato sin colapsar
  (aquí: la vista esperaba N capturas por URL para detectar ediciones). El dato nunca
  se pierde si el archivo es inmutable; lo que se rompe es el CAMINO del dato a la
  vista. Buscar el camino roto, no el dato.

- **2026-06-25** — migración 000010 (crea story_relations; NO toca datos de archivo).
  Tabla nueva, vacía al crear; el clustering la pobló en su corrida (137 clústeres →
  289 pares / 578 filas espejo). story_relations es CÁLCULO DERIVADO reconstruible
  desde stories; se borra/recomputa cada corrida igual que stories/story_articles.
  articles jamás se toca. RLS activo + policy de SELECT pública explícita (lección
  migración 000009: tabla nueva con RLS sin policy = web ve cero filas en silencio).

- **2026-06-23** — colapso por URL en el backend del clustering (NO es truncate de
  archivo). Al implementar colapsar_por_url() en clustering_fase2.py, el pipeline pasó
  a operar sobre artículos únicos (1904) en vez de capturas (2055): 151 capturas de
  notas editadas dejaron de contarse como artículos separados. Afecta SOLO el cómputo
  derivado (stories/story_articles): conteo, centroide y compuertas. articles
  (contenido_visible, hash) jamás se toca — la inmutabilidad y el historial de
  capturas se preservan intactos. Validado: determinismo del uuid confirmado (dos
  corridas idénticas → misma huella md5 7a9844b9...); diff vs estado sin colapsar
  (diag_colapso_diff.py, read-only) → 99 clústeres con identidad intacta, 4 viejos
  desaparecidos / 6 nuevos aparecidos (todos re-semillas limpias de origen único), 1
  disolución legítima (f0ac7e42: clúster de 2 medios que solo alcanzaba el segundo
  medio por contar una recaptura → al colapsar deja de calificar; correcto por diseño).
- **2026-06-21** — backfill + reclustering de los 663 pendientes (NO es truncate).
  Los ~663 artículos capturados por el crawler desde 06-18 tenían embedding NULL;
  backfill los rellenó (entidades + embedding) vía UPDATE idempotente. Banco:
  982 → 1645 artículos, todos embebidos. Tras esto, clustering reconstruyó
  stories/story_articles (derivado, no archivo): 48 → 83 clústeres / 329 noticias.
  contenido_visible y hash intactos. Inmutabilidad respetada.
- **2026-06-21** — última regeneración de uuids de stories (NO es truncate de archivo).
  Al implementar UUID estable, los 83 uuid aleatorios pasaron a su valor uuid5
  determinista en una corrida. Churn final aceptado (sin enlaces compartidos en
  producción aún). De aquí en adelante, estables. Solo afecta stories (caché derivada),
  jamás articles.

- **2026-06-18** — backfill de Fase 2 sobre artículos nuevos (NO es truncate).
  395 artículos nuevos (capturados por el crawler desde el último backfill) tenían
  embedding NULL; backfill los rellenó (entidades + embedding) vía UPDATE. Banco:
  587 → 982 artículos. Idempotente, solo campos de procesamiento; contenido_visible
  y hash intactos. Tras esto, clustering reconstruyó stories/story_articles (derivado,
  no archivo): 20 → 48 clústeres. Inmutabilidad respetada.

- **2026-06-17** — migración 000009_rls_lectura_stories (NO toca datos; es RLS).
  stories y story_articles (creadas en 000007/000008) nacieron con row level
  security ACTIVO pero SIN policy de SELECT. La clave publishable veía cero filas
  SIN error (RLS no falla: filtra todo en silencio) → la web mostraba "Fase 2 en
  construcción" con datos reales presentes. Fix: policy `lectura_publica` (SELECT
  to public using(true)) en ambas, copia literal de la de articles/outlets. La
  escritura sigue siendo solo del crawler con clave secreta (ignora RLS).
  **Lección:** toda tabla nueva con RLS necesita su policy de lectura pública
  explícita. El hueco pasó inadvertido porque el crawler (secret) nunca la necesitó;
  solo se vio al ponerle la web (publishable) encima. Verificar policies al crear
  tablas, no al consumirlas.
- **2026-06-16** — backfill de Fase 2 (NO es truncate ni borrado de archivo).
  Se poblaron las columnas nuevas entidades (jsonb) y embedding (vector 384) de
  los 587 artículos vía UPDATE. Es UPDATE sobre articles PERO solo de campos de
  procesamiento nuevos que estaban NULL; NO se tocó contenido_visible ni hash.
  La inmutabilidad del snapshot se respeta: añadir un campo derivado no altera
  el archivo, igual que un índice no altera los datos.
- **2026-06-16** — stories/story_articles se borran y reconstruyen en cada corrida
  del clustering (recalcular-todo). Esto NO viola la regla de Fase 2 de no-truncar:
  los clústeres son CÁLCULO DERIVADO reconstruible desde articles, no son archivo.
  articles (la fuente de verdad) jamás se toca.
- **2026-06-14** — cambio de extractor v1→v2 (NO es truncate). Se migró la
  extracción de cuerpo a esquema por bucket (columna outlets.extraccion, migración
  000006): 'articlebody' (El Tiempo, El Colombiano, El Espectador) con trafilatura
  de respaldo; 'trafilatura' sola (Vorágine, Las2orillas). Consecuencia sobre el
  archivo: en las próximas corridas, las notas que reaparezcan en los feeds se
  re-extraen con cuerpo más limpio → hash distinto → entran como fila nueva (no se
  borra ni se actualiza nada; la inmutabilidad se respeta). Estas filas nuevas
  reflejan un cambio NUESTRO de extractor, no editorial del medio; se acepta como
  evento único documentado, hecho aún en Fase 1 (antes de que el archivo tenga
  valor histórico y antes de la regla de Fase 2 de no-tocar). Las notas viejas con
  cuerpo sucio quedan como su versión; no se fuerza recrawl ni truncate.
- **2026-06-11** — truncate de articles/audit_log. Primera limpieza por
  contaminación de boilerplate (cookies, chatbot) en la corrida inicial.
- **2026-06-11** — delete solo de El Espectador, por contenido de reproductor de
  audio y caricaturas mal extraídas.
- **2026-06-12** — truncate completo. Mejoras de limpieza (cola promocional,
  parcial por marcador) + nueva columna sección.
- **2026-06-13** — truncate completo. Mejoras de extracción (quitar
  favor_precision recupera cuerpo en El Tiempo) + rescate de subtítulo vía
  twitter:description (El Colombiano). ÚLTIMA cirugía de calidad antes de Fase 2.

---

## Deuda técnica conocida

### Recalibración de relaciones: el problema era "qué cuenta como específica", no n_esp (2026-06-27)

Partimos de TRASPASO #1 ("la limpieza de NER baja n_esp, ¿hay que bajar el umbral a 2?").
**La pregunta estaba mal planteada.** Medido con diag_relaciones (v1→v3, read-only,
desechable): bajar a 2 sumaba 291 aristas de pura co-mención institucional; y subir tampoco
servía — el peor falso positivo tenía n_esp=15 (una lista de países: "La caída de Niño
Guerrero" ↔ "voto en el exterior"). La raíz eran TRES clases de basura en lo que el motor
contaba como específica: (1) duplicación de formas de superficie ("la procuraduría" /
"procuraduría general de la nación" = 3 formas, 1 referente), (2) geografía extranjera
contada como específica, (3) actores institucionales de DF medio (defensores de la patria,
registraduría, cne) que esquivaban FRAC=0.15.

**Fix (3 capas, ninguna toca n_esp ni la guardia), portado a la 2ª pasada de
clustering_fase2.py:** canon() + ALIAS (quita artículo inicial + dicc. acotado de siglas↔
expansión y fragmentos de nombre; NO fusiona instituciones hermanas), GEO_EXTRA (países/
regiones/ciudades extranjeras al filtro geográfico, antes solo Colombia), FRAC_GENERICA
0.15→0.08. canon se aplica en los TRES puntos: entrada de entidades, conteo df_cl (para que
las genéricas por DF se cuenten bien) y sets de exclusión (RUIDO_C/GEO_C canónicos).

**Medido (barrido de FRAC):** 0.15→191 aristas (aún madeja), 0.10→115, **0.08→68 (CORE 4/4)**,
0.06→51 (CORE 3/4: rompe Calavera↔24). Por eso 0.08 es el límite: el piso lo fija una
relación real (Calavera↔24) que descansa en {dijín, interpol, ejército nacional + el nombre
propio "elver vicente alfonso sanabria"}; en 0.06 los institucionales se vuelven genéricos y
queda solo el nombre → n_esp=1. Hub Pastrana 21→3. Andamiaje eliminado (control = 0).
**Decisión: n_esp=3 y guardia 0.50 NO se mueven** (consistente con cierre 2026-06-23 y con el
testigo Beto Coral, cos 0.589). Branch fix/relaciones-canon-frac008.

**Sub-decisiones con recibo:**
- **Air-e = FN aceptado.** Solo 2 específicas limpias (andeg + superservicios); cae bajo
  n_esp≥3. Bajar a 2 para salvarlo reabre la madeja (El Niño↔El Niño y Chalá↔Calavera también
  caen en 2, mezclados con co-mención del hub). Mismo patrón que Beto Coral para la guardia:
  costo de recall medido y aceptado, no se afloja el umbral global. Revisitar solo si Fase 3
  desambigua relaciones empresa-nombrada.
- **Retirar RUIDO_DURO (era TRASPASO #2) sigue bloqueado, ahora MEDIDO:** 9/50 términos
  sobreviven al NER limpio (incl. "match electoral de el espectador"). Viven en <11 clústeres,
  así que ni FRAC=0.08 los atrapa. Retirarlo re-contaminaría n_especificas. Disparador: mejor
  filtro de NER de cuerpo.
- **Grafo expuesto con cap de presentación.** /historia/[id]/page.js: Q3 por origen_id (espejo
  completo), top-5 por (n_especificas desc, coseno desc) + `<details>` "y N más". El cap de
  in-degree en LECTURA que se contemplaba queda SUPERSEDIDO para la vista per-historia: el
  top-5 ya contiene la densidad. Vuelve a hacer falta solo si se construye un grafo panorámico.

**Aprendizaje (autocrítica):** eyeball-ear de lejos engaña. Marqué "android/google/shakealert"
como basura de NER que tejía un FP entre dos sismos; Jota corrigió que es cobertura legítima
del sistema de alerta sísmica de Google — entidades reales y discriminantes. El criterio se
corrige con el dato concreto, no con la sospecha desde el título. NO se registró como deuda.

### Writes masivos uno-por-uno son frágiles — OBSERVADO (2026-06-26)
- **Síntoma medido:** el re-backfill (2732 UPDATE uno por uno sobre conexión HTTP/2
  persistente al pooler) se cortó a ~800 writes con WinError 10054 ("connection forcibly
  closed by remote host"). El pooler de Supabase cierra la conexión por volumen/duración.
- **Causa:** writes masivos sin resiliencia. Convierte en OBSERVADA la deuda teórica del
  delete-then-insert del clustering (registrada 2026-06-23): el modo de fallo es real.
- **Fix aplicado (en el re-backfill):** script REANUDABLE por diseño (UPDATE solo si las
  entidades cambian → re-correr salta lo ya limpio, sin archivo de checkpoint) + retry con
  backoff + reconexión ante corte + cliente fresco cada 300 writes. Criterio de
  consistencia: una corrida que diga aplicados=0.
- **Decisión:** NO robustecer el clustering ahora. Inserta por LOTES (no uno por uno) y
  aguantó esta corrida. Pero comparte el patrón; si al correrlo se corta, aplicar el mismo
  enfoque (su propia unidad de robustez, junto con la atomicidad del delete-then-insert).
- **Reactivar SI:** el clustering se corta a mitad en un run, o el banco crece y los writes
  empiezan a fallar/tardar.

### story_relations: esquema, criterio y limpieza congelada (2026-06-25)
- **Esquema (migración 000010):** grafo clúster↔clúster DIRIGIDO-ESPEJO. PK compuesta
  (origen_id, destino_id), FK a stories ON DELETE CASCADE, CHECK origen≠destino, índice
  (origen_id, n_especificas desc) para el cap de lectura, RLS + policy de SELECT pública.
  Columnas: n_especificas (MOTOR), coseno (GUARDIA), entidades_compartidas jsonb
  (EVIDENCIA, auditable + UI). Caché derivada pura: se borra/recomputa con stories.
  Dirigido-espejo (2 filas por par) elegido sobre no-dirigido: el cap de lectura es
  "top-K vecinos del foco" = índice limpio por origen, y la direccionalidad de Fase 3
  (derivada/reacción) entra sin rediseño. Costo 2× en tabla diminuta = trivial.
- **tipo_relacion OMITIDO a propósito.** DISPARADOR: al construir Fase 3, la anotación de
  LLM exige tabla aparte no-volátil (como analyses↔articles) o identidad estable de
  relación — el delete+insert del clustering la borraría. Añadir columna después es gratis.
- **Umbral VALIDADO: n_esp≥3 ∧ cos≥0.50. NO se apretó.** "Conservador = más estricto"
  rechazado con datos: cos≥0.55 tira Beto Coral (medido 0.544 en diag, 0.589 en producción),
  subir n_esp arriesga Air-e. Falso-negativo de apretar = MEDIDO; ganancia de precisión = NO
  medida. La banda n_esp=3 se audita sobre el grafo vivo; si sale basura se aprieta por n_esp
  dejando cos en 0.50.
- **Limpieza CONGELADA de diag v4 como mitigación TEMPORAL.** Excede la mitigación
  sancionada (medios + genéricas-por-DF): conectores sub-DF ("sin embargo", "hay") viven
  en <18 clústeres y genéricas-DF no los atrapa, solo el RUIDO_DURO completo. Sin él, los
  números validados no transfieren. RETIRO = re-backfill de NER (entonces la lista baja a
  medios + genéricas-DF). NO crecer la lista: ruido nuevo = señal de hacer el NER, no de
  añadir aquí. GATE: el grafo NO se expone en la web hasta el re-backfill de NER.
- **centroide_de_cluster() factorizado** (única fuente: calcular_scores + relaciones).
  ents_rel() separada de normaliza_ents (no se tocan las compuertas del clustering).
  DISPARADOR #2 (centroide-por-medio): se cambia 1 función y se REVALIDA la guardia de coseno.
- **O(clústeres²) sin ventana en la pasada 2** (a diferencia del ±72h del clustering de
  artículos). El coseno va gateado tras n_especificas, así que el cómputo es barato hoy.
  delete+insert ahora cubre 3 tablas (relations→story_articles→stories): ventana no
  transaccional más ancha, aceptada en frío a esta escala. Ver PROYECCION_ESCALA.
- **Reactivar/revisar SI:** el eyeball del grafo muestra basura (apretar n_esp), o llega
  el re-backfill de NER (retirar el RUIDO_DURO de conectores y quitar el gate de UI).

### Centroide no ponderado por medio sesga la neutralidad por volumen (2026-06-25)
- **Causa raíz (identificada, NO medida aún):** el centroide del clúster es np.mean de
  los embeddings de TODOS los artículos (calcular_scores, clustering_fase2.py), sin
  ponderar por medio. Si un medio domina en volumen dentro del clúster, el centroide se
  corre hacia su "centro de masa" → como neutralidad = cercanía al centroide, los
  artículos de ese medio salen sistemáticamente más "neutrales". Hipótesis de Jota: El
  Tiempo (alto volumen) queda anclado con frecuencia desproporcionada. Es el mismo sesgo
  de sobre-representación por volumen del feed, ahora DENTRO del clúster.
- **Fix candidato (decidido, pendiente de medir impacto):** centroide = promedio de los
  centroides-por-medio, sobre URLs colapsadas. Voto DURO: 1 medio = 1 voto, sin importar
  cuántas URLs aporte. Neutralidad pasa a medir "consenso ENTRE MEDIOS", no entre
  artículos. Ataca la causa raíz sin introducir sesgo nuevo.
- **Plan B (no de entrada):** si el voto duro da demasiado poder a medios de 1 nota
  ("poder de veto de la minoría" — un medio con 1 URL pesa 1/n_medios del centroide),
  amortiguar con peso 1/sqrt(n_notas_del_medio) en vez de voto duro. NO meterlo antes de
  medir: es optimización prematura. El efecto "voz a la minoría" se acepta de entrada
  como FEATURE (coherente con Trama: el ángulo minoritario no debe quedar aplastado),
  no como bug.
- **Lo que el fix NO toca (frontera explícita, para no esperar de más):** solo afecta la
  construcción del centroide → neutralidad. NO toca score_cobertura ni score_divergencia.
  NO resuelve el límite epistémico (si todos los medios comparten un punto ciego, el
  centroide lo hereda igual — eso es omisión, Fase 3). NO resuelve la asimetría del
  espectro mediático (curaduría, no fórmula).
- **DESCARTADO con razón:** ponderar por cobertura (idea inicial de Jota) — la cobertura
  premia mencionar muchas entidades, así que reforzaría las reacciones editorializadas
  densas (ya medido, caso Chalá 2026-06-17). Cambiaría "sesgo por volumen" por "sesgo por
  densidad de entidades". Dos males, no una solución.
- **Alcance del cambio:** la neutralidad re-ponderada es SOLO para elegir el ancla. NO se
  expone al usuario (coherente con la deuda de no exponer scores hasta que cobertura esté
  arreglada). Anotado: reevaluar ese nivel de transparencia con el usuario según evolucione.
- **Tier 2, load-bearing** (calcular_scores decide qué artículo representa el clúster en
  las cards). NO tocar sin medir impacto primero (ver diagnóstico en Ideas).
- **Reactivar/abordar SI:** el diagnóstico de impacto confirma dominancia frecuente Y que
  el ancla cambia en suficientes clústeres para mejor. Natural hacerlo ANTES de activar
  Semana/RTVC/La Silla, porque más medios con volumen asimétrico agravan el sesgo —
  medir el centroide-por-medio da la línea base.

### Relaciones inter-clúster: medición v1–v4 y decisión de criterio (2026-06-24)
- **Qué se midió (diag_relaciones v1→v4, read-only, desechables):** si existe un
  criterio para ligar clústeres relacionados (grafo de historias) sin fusionarlos.
- **Hallazgos con datos:**
  (1) El coseno entre centroides liga por TEMA, no por hecho (clima del domingo ↔
      resultados por ciudad: cos 0.86). No hay valle en su distribución. Sirve de
      GUARDIA, jamás de motor.
  (2) El peso IDF crudo estaba podrido de ruido NER: boilerplate de fuente ("match
      electoral de el espectador"), conectores ("sin embargo", "lea", "encuentre") y
      nombres de medios ("el tiempo", "el colombiano") — ligaban por FUENTE. El IDF
      premia lo raro, así que el boilerplate raro pesaba alto.
  (3) Limpieza en tres capas (ruido duro a mano + geografía clasificada-no-borrada +
      genéricas por DF de CLÚSTER) + métrica n_especificas: FUNCIONA para hechos
      discretos (Air-e, capturas, Arizabaleta, Beto Coral, Cauca, giro LatAm).
  (4) El macro-tema (campaña electoral) es un HUB IRREDUCIBLE. Medido: el cap de
      presentación NO lo desinfla (Pastrana in-degree 26 bajo cap top-5); cluster-IDF
      tampoco (26→23). Causa real: tamaño de clúster — Pastrana/Chalá tienen 125-134
      entidades específicas propias vs 31-40 de un hecho discreto → superficie de
      solapamiento gigante → tocan medio archivo por tamaño, no por relación.
  (5) mean_df (df-de-clúster promedio de las entidades propias) NO discrimina señal de
      ruido: separa "tema grande" de "hecho aislado". Hipótesis descartada con datos.
- **Decisión:** el criterio de story_relations será n_especificas ≥ umbral + coseno
  guardia. El hub se controla con CAP DE IN-DEGREE (+out-degree) en la capa de LECTURA
  (presentación, reversible), NO en la tabla. La distinción "contexto" vs "seguimiento"
  del macro-tema se DIFIERE a Fase 3 (LLM + tipo_relacion): ninguna vara de entidades la
  resuelve.
- **Reactivar/revisar SI:** al diseñar el esquema, el umbral elegido deja pasar madeja,
  o si la sobre-fusión (ver Ideas) resulta ser la causa raíz y la corrige.

### Ruido de NER contamina relaciones — el fix es upstream, no en relaciones (2026-06-24)
- **Síntoma medido:** aun con stoplist a mano, colaban "entidades" basura ("la captura",
  "según las autoridades", "los hechos") y nombres de medios. El stoplist a mano es
  perder: la cola de basura de NER es infinita.
- **Causa:** NER básico en backfill_fase2.py (ya registrado como Idea con disparador). A
  nivel artículo el IDF sobre miles de docs lo lavaba; a nivel de unión de entidades de
  clúster, el ruido se concentra y manda.
- **Decisión:** NO limpiar en la capa de relaciones (whack-a-mole). El fix de raíz es
  mejorar el filtro NER en backfill (Tier 2 load-bearing, requiere re-backfill) — su
  propia unidad. Las relaciones se protegen con genéricas-por-DF + stoplist duro acotado
  (medios) como mitigación, no como solución.
- **Reactivar SI:** se aborda la unidad de relaciones a fondo, o el ruido ensucia el
  grafo de forma visible al exponerlo.

### story_relations ensancha la ventana del delete-then-insert (2026-06-24)
- **Decisión en frío:** story_relations será caché derivada pura, recomputada en la
  misma corrida que stories (delete+insert). Coherente con "stories = caché derivada",
  pero AGREGA otra tabla a la ventana no transaccional ya documentada. A esta escala no
  muerde; registrado para no olvidarlo al hacer el clustering atómico/transaccional.
- **Reactivar SI:** se ataca la robustez del delete-then-insert (entonces cubrir ambas
  tablas), o el banco crece y la ventana de web vacía se vuelve inaceptable.

### Dependencias del clustering sin pin en CI (2026-06-23)
- **Síntoma:** ninguno aún. El job `clustering` de crawler.yml instala
  `pip install numpy supabase python-dotenv` sin versiones. El resto del proyecto
  instala desde requirements*.txt.
- **Riesgo:** un update mayor silencioso de numpy o supabase puede romper el
  clustering en un run nocturno (mismo patrón que ya mordió con `click` en backfill).
- **Decisión:** NO pinear ahora. El entorno es de 3 paquetes ligeros y a esta escala
  aguanta. Pero NO dejarlo silencioso — registrado para no repetir el olvido de
  backfill.
- **Fix de raíz (cuando muerda):** crear requirements-clustering.txt con `pip freeze`
  de un entorno limpio (solo numpy/supabase/dotenv + sus transitivas), apuntar el
  `cache-dependency-path` del job a ese archivo.
- **Reactivar SI:** un run de clustering falla por dependencia, o se actualiza numpy/
  supabase de versión mayor.

### Clustering delete-then-insert no transaccional (2026-06-23)
- **Síntoma:** ninguno medido. reescribir_stories() hace delete() de stories y
  story_articles, LUEGO inserta los clústeres nuevos. No es transaccional.
- **Riesgo:** si el script muere entre el borrado y el insert (timeout de Supabase,
  OOM, corte de red), las stories quedan vacías o parciales. La web mostraría "Fase 2
  en construcción" con datos reales en articles. Automatizado cada 6h, falla de
  madrugada y la web queda rota hasta el siguiente run o hasta que se note.
- **Por qué NO se atacó al automatizar:** a 1904 artículos el insert no falla; el
  recompute corre en ~2 min sin incidentes. Hacerlo transaccional/atómico (p. ej.
  escribir a tabla temporal y swap) es su propia unidad de robustez.
- **Decisión:** automatizar tal cual, documentar el modo de fallo.
- **Reactivar SI:** el banco crece y los inserts empiezan a tardar/fallar, o aparece
  tráfico real que haga inaceptable una ventana de web vacía.

### [VALIDADA — NO SE MOVIÓ] Umbrales provisionales del clustering (cierre 2026-06-23)
- La deuda "umbrales provisionales sin recalibrar con multitema" (abierta 2026-06-21)
  se cierra: recalibrados con datos sobre 105 clústeres multitema. Diagnóstico
  (diag_umbrales.py, read-only, recomputa la formación desde articles):
  529 aristas pasan ambas compuertas; histogramas de peso IDF y coseno densos por
  encima del corte sin valle que sugiera mover el umbral; casi-fallos por semántica
  (peso alto, coseno 0.65-0.70) son "mismo tema, distinto hecho" (captura Chalá vs
  homicidio periodista, etc.) — CORRECTOS de rechazar; casi-fallos por entidades
  (coseno alto, peso 15-20) son pares electorales genéricos — CORRECTOS de rechazar.
  Clústeres chicos (2-3) revisados a ojo: todos coherentes.
- **Conclusión:** IDF≥20 / coseno≥0.70 VALIDADOS con volumen multitema. NO se cambió
  ningún número — la metodología de dos compuertas aguantó el salto de 1 macro-tema a
  104 temas distintos. "Provisional" pasa a "validado".

### Árbol de dependencias de backfill en CI — parchado, no congelado (2026-06-23)
- **Síntoma:** al encadenar backfill a Actions, `import spacy` falló con
  ModuleNotFoundError: 'click'. click es dependencia transitiva de spaCy (vía su CLI)
  y la resolución de pip dejó el árbol inconsistente: pineamos spacy/sentence-transformers
  pero no sus transitivas.
- **Fix aplicado (camino rápido):** se agregó `click` explícito a requirements-backfill.txt.
  Funcionó. NO se hizo pip freeze del entorno local que sí funciona.
- **Decisión:** NO congelar ahora. El parche resolvió el único módulo faltante observado.
  Pero NO hay evidencia de árbol sano, solo de que click era lo único roto EN ESTE MOMENTO.
- **Riesgo:** un update transitivo de spaCy/torch/sentence-transformers puede volver a
  romper la resolución en un run nocturno silencioso (otro ModuleNotFoundError).
- **Fix de raíz (cuando muerda):** `pip freeze > requirements-backfill.txt` desde el
  entorno local validado, editando la línea de torch para dejarla sin pin (el step
  --index-url cpu la maneja antes). Replica en CI exactamente lo que funciona en local.
- **Reactivar SI:** un run de backfill vuelve a fallar por dependencia faltante, o se
  actualiza alguna de las libs ML pineadas.


### UUID estable de stories — RESUELTO (2026-06-21)
- **Contexto:** reescribir_stories hacía delete()+insert() dejando que Postgres
  generara gen_random_uuid → uuid nuevo cada corrida → todo enlace /historia/[uuid]
  compartido se rompía. Para una hemeroteca forense cuyo valor es "comparte este link
  como prueba", era una herida en la propuesta. Era prerequisito de automatizar el
  pipeline (automatizado, la rotura se multiplica a cada corrida).
- **Decisión de diseño (challenge-first):** entre las 3 opciones registradas, se
  eligió la #1 (semilla determinista) sobre la #2 (tabla story_identity persistente).
  Criterio que decidió: la #2 reintroduce ESTADO (matching difuso entre corridas),
  justo lo que se rechazó al descartar clustering incremental — convertiría stories de
  caché derivada pura a estado. La #1 COMPUTA el id desde datos (no lo almacena-y-busca),
  preservando stories como caché pura. Coherencia arquitectónica ya pagada.
- **Implementación:** uuid5(NAMESPACE_STORIES, url_del_más_antiguo). Corrección de
  granularidad sobre la idea original: se siembra del URL (átomo permanente de Trama),
  NO del article_id (cambia con cada re-captura). Determinismo total: el "más antiguo"
  se elige con min por (cuando(a), url) — el url como segundo criterio garantiza ganador
  único ante empates de fecha (sin esto, lo decidía el orden de iteración de Python →
  uuid inestable). NAMESPACE_STORIES es constante de módulo, NUNCA cambiar.
- **Validado:** dos corridas consecutivas sobre datos idénticos → los 83 uuids
  IDÉNTICOS (huella md5 del string_agg coincide). uuids son v5. Tier 2 load-bearing
  (escribe stories), no toca articles/esquema/umbrales/scores. Sin migración.
- **Residual aceptado (con disparador):** la #1 ata la identidad a UN artículo (el más
  antiguo). Flaquea en 3 casos RAROS, no medidos aún en frecuencia:
  (1) FUSIÓN: dos clústeres se unen; el más joven hereda el uuid del más viejo → su
  enlace se rompe. (2) EL MÁS ANTIGUO ABANDONA el clúster (recalibración le quita
  aristas): re-semilla con otro url → uuid nuevo (el caso más molesto). (3) SPLIT: la
  pieza sin el url-semilla original toma uuid nuevo. La opción #2 (matching por
  solapamiento) es robusta a los tres, pero pagar esa complejidad ahora es optimización
  prematura contra frecuencias no medidas. La #1 ES el instrumento que permite MEDIR
  esas frecuencias (con ids estables se observa qué historias persisten/fusionan entre
  corridas) — medir-antes-de-arreglar al meta-nivel.
- **Reactivar (escalar a opción #2) SI:** usuarios reportan enlaces rotos a historias
  que sí existen, rastreado a fusión/re-semilla frecuente.

  ### Búsqueda en /historias no paginada (2026-06-21)
- **Síntoma:** al agregar paginación al feed, la rama CON búsqueda (q3 en page.js)
  quedó SIN .limit()/.range() — devuelve todas las stories que matchean el texto. Hoy
  con 83 stories totales no muerde. La paginación de esta unidad cubrió solo el feed
  sin búsqueda (que era el problema del límite-30 reportado).
- **Decisión:** NO arreglar ahora. Acotado y visible. La búsqueda sí recibió el mismo
  orden (fecha_fin/n_medios/n_articulos) para no quedar con el created_at roto.
- **Reactivar SI:** la búsqueda empieza a devolver decenas de stories de forma habitual.

### Fix título-cita en el feed (display) — APLICADO 2026-06-21
- **Contexto:** la deuda titular-cita (2026-06-18) se volvió visible en producción
  (criterio de reactivación cumplido: 2 títulos-cita en el feed). Al investigar el
  punto #1 del TRASPASO (disconnect feed↔ancla) se halló la causa estructural: el
  título de display se computa en TRES lugares con criterios distintos —es_ancla
  (gate p75, backend), stories.titulo (hereda del ancla), y tituloCanonico
  (frontend, lib/colapsarCluster.js)—. El feed usa el tercero: máxima neutralidad
  PURA, justo la fórmula que el arreglo del ancla del 2026-06-18 descartó. Por eso
  ese arreglo era invisible en el feed.
- **Medido (diag_titulos.py sobre 48 clústeres):** 5 títulos-cita detectados, pero
  1 era falso positivo de la heurística inicial: «Comandante… anunció que 99
  disidentes de 'Walter Mendoza'…» — comillas envuelven un ALIAS, y el fallback
  "comillas + verbo de habla" sobre-disparó. Lección: en español la señal real es
  la cláusula entre comillas ADYACENTE a dos puntos (`"cita":` o `:"cita"`), no el
  verbo suelto. Heurística afinada a solo ese patrón (RE_CITA_DELANTE/RE_CITA_ATRAS,
  cláusula ≥15 chars): 4/4 citas reales, 0 falsos positivos.
- **Fix:** tituloCanonico (lib/colapsarCluster.js) ahora descarta titulares-cita;
  elige el titular noticia más neutral del subconjunto no-cita. Si todas las
  noticias son cita, cae a la más neutral (degradación elegante, no inventa título).
  Tier 2, presentación, NO toca scoring ni es_ancla — la cita puede seguir siendo
  es_ancla de las cards del bento; lo que cambia es solo el NOMBRE de la historia.
- **Validado (diag_fix_titulos.py, réplica de la heurística en Python sobre los 48):**
  3 títulos cambian (Petro b56729d8, Gaona 974f9571, Medicina Legal 3ce9745f), los
  tres a no-cita; 0 clústeres fuera de esos se mueven; residual = solo Germán
  656a7e6c (sus 2 noticias son ambas cita, sin alternativa); 0 caídas a fallback.
  Las alternativas elegidas eran tipo=noticia (confirmado: no cayeron a residual).
- **Residual aceptado:** Germán (1/48). Único caso donde generar título sería el
  único recurso; por 1 clúster NO se rompe inmutabilidad. Confirma parar en heurística.
- **Reactivar SI:** aumenta el % de clústeres sin alternativa no-cita con volumen, o
  se decide que el residual es inaceptable de cara al público.

### Doble-cómputo del título de historia — deuda estructural (2026-06-21)
- **Síntoma:** "qué texto representa el clúster" se decide en dos capas con criterios
  que pueden divergir: backend (stories.titulo, hereda del ancla por gate p75) y
  frontend (tituloCanonico, máx neutralidad no-cita). Hoy COINCIDEN de facto porque
  ambos sanean, pero el día que cambie el criterio de ancla otra vez, se
  desincronizan silenciosamente (ya pasó una vez: el arreglo del ancla 2026-06-18
  no surfaceó en el feed por esto mismo).
- **Decisión:** NO arreglar ahora. Documentar. El fix sería una fuente única de
  verdad para el título de display, pero hoy no hay divergencia visible.
- **Reactivar SI:** se cambia el criterio de selección de ancla, o aparece un título
  de feed que no concuerda con el ancla del expediente /historia/[id].

### [SUPERADO 2026-06-21 → ver "Fix título-cita en el feed"] Titular-cita de alta neutralidad ancla el clúster — el gate no la atrapa (2026-06-18)
- **Medido** al correr el banco 2× (48 clústeres): el gate p75 resuelve la
  *reacción de baja neutralidad* (Chalá) pero NO la *cita declarativa de alta
  neutralidad*. Caso "gringo" (n=6): ancla principal = «"Al parecer no violó a
  ninguno de sus hijos": presidente Petro…» (neut 0.920, cob 0.465). ACTUAL, p50 y
  p75 coinciden los tres: el gate no la corrige porque la cita SÍ pasa el piso de
  neutralidad (el embedding la ve central) y tiene la cobertura más alta.
- **Patrón, no caso único:** también n=2 "Germán le entregó sus programas bandera"
  y "No era una campaña cualquiera, fue una cruzada nacional". Titulares-cita de
  actor político anclando clústeres. Casi invisible con 20 clústeres, visible con 48.
- **Causa:** ninguna de las dos compuertas ni los tres scores miden "el titular es
  una cita declarativa, no una descripción del hecho". Es ortogonal a neutralidad y
  cobertura. Para Trama es justo el encuadre que el producto debe *señalar*, no
  adoptar como voz neutral del clúster.
- **Decisión:** NO arreglar ahora. Medido (existe) pero el fix es caro y riesgoso:
  detectar cita declarativa es heurística de lenguaje (comillas en titular, verbo
  de habla "dijo/aseguró/señaló", NER de actor como sujeto), toca el scoring
  (load-bearing). Es su propia unidad de trabajo con su propio diagnóstico.
- **Reactivar SI:** se decide priorizar calidad de anclas antes que volumen, o si
  al exponer scores/anclas al público el patrón se vuelve embarazoso de forma visible.
- **Matiz honesto:** el arreglo del ancla de hoy cerró UNA falla (reacción de baja
  neutralidad), no las dos. Esta es la otra cara del mismo problema de anclaje.
  
### [RESUELTO 2026-06-18] Ancla por cobertura — DISPARADOR CUMPLIDO (2026-06-17)
- Re la deuda "score_cobertura no comparable entre clústeres" (2026-06-16): su
  criterio de reactivación era "si el ancla por cobertura elige mal de forma
  visible". **Se cumplió, medido al renderizar.** En el clúster de Chalá el ancla
  "más neutral + completa" (mayor neutralidad×cobertura) salió siendo la reacción
  política "Alcalde de Medellín… hombre de Calarcá protegido por Petro"
  (neut 0.82 × cob 0.22 = 0.183, el máximo del clúster), no la nota factual de la
  captura. Causa: cobertura premia mencionar muchas entidades; una reacción que
  nombra a todos los actores puntúa alto pese a estar editorializada.
- **Decisión:** el fix es de BACKEND (renormalizar cobertura por tamaño de clúster,
  o recomputar es_ancla), su propia unidad de trabajo, medida — NO se maquilla en
  la vista. La vista lo muestra fiel con aviso visible.
- **Decisión ligada:** NO exponer los scores (neutralidad/cobertura/divergencia)
  al público hasta que cobertura esté arreglada y sea explicable. Mostrar a un
  público de verificadores un número que sabemos roto resta credibilidad. Hoy
  quedan como diagnóstico (mono pequeño), no prominentes. No invertir en tooltips
  sobre un score provisional.
- **[RESUELTO 2026-06-18]** El fix candidato registrado (renormalizar cobertura por
  tamaño / pesar por frecuencia) se MIDIÓ y se DESCARTÓ: pesar la cobertura por
  frecuencia dentro del clúster *reforzaba* la reacción en vez de castigarla
  (cob_frq de la reacción del Alcalde = 0.49 > cob actual 0.22). La reacción no gana
  por nombrar actores periféricos sino por saturar densamente las entidades
  centrales. Diagnóstico real: `neutr` es casi constante en un clúster (~0.80–0.95)
  y `cob` de alta varianza, así que el producto `neutr*cob` ordenaba de facto por
  cobertura. El bug no estaba en la cobertura sino en MULTIPLICAR dos scores de
  escalas incomparables.
- **Fix aplicado:** separar las preguntas. Gate de neutralidad (piso p75 del clúster)
  + desempate por cobertura entre los que pasan, para el ancla PRINCIPAL. El ancla
  secundaria sigue siendo la de mayor divergencia. Enmienda a ARQUITECTURA §6.
- **Validado sobre la base** (no sobre predicción): Chalá ancla "Legalizan captura"
  (neut 0.913), la reacción del Alcalde (neut 0.823) queda es_ancla=false. Sin
  regresión en clústeres ya sanos (Niño Guerrero, Air-e). Confirmado de nuevo con
  banco 2× (48 clústeres). Umbral p75 PROVISIONAL, calibrado sobre días dominados
  por macro-temas; recalibrar con volumen multitema.

### Lookup por URL — best-effort, no garantía (2026-06-17)
- **Medido:** el id del artículo vive siempre en el PATH en los 5 medios (sufijo
  -3564106, -EK37683689); ningún query param es significativo → la normalización
  quita TODOS los params (allowlist vacía). Pero el archivo guarda la URL exacta
  del feed RSS/sitemap sin normalizar, y eso es inconsistente por medio: El
  Espectador y Las2orillas con trailing slash, los demás sin; voragine.co sin www,
  los demás con www.
- **Mitigado:** variantesUrl() prueba 4 combinaciones (con/sin www × con/sin slash)
  en un solo .in() — query visible, no match difuso. Cubre el caso frecuente (pegar
  una nota de El Espectador sin el slash final).
- **NO cubierto (deuda aceptada):** variantes AMP (amp.medio.com), móvil
  (m.medio.com), o canónicas inconsistentes. Fallan silencioso ("no encontré tu
  noticia" cuando sí está).
- **Decisión:** NO arreglar más allá del fallback de 4 variantes.
- **Reactivar SI:** usuarios reportan no encontrar notas que sí están archivadas,
  o si AMP/m. se vuelven comunes en lo que pega la gente.
### es_parcial en El Espectador — investigado, NO es bug (2026-06-16)
- **Reporte:** notas de El Espectador (y algunas de El Tiempo) marcadas
  es_parcial=true viéndose completas y largas. Sospecha de falso positivo.
- **Hipótesis descartadas con datos:** (1) umbral de caracteres — es_parcial no
  mira longitud; (2) regex global de detectar_paywall_jsonld agarrando un nodo
  JSON-LD ajeno — el diagnóstico mostró que el nodo PRINCIPAL (mismo titular/URL)
  declara isAccessibleForFree=false; (3) enlace "Lea más:" incrustado como causa —
  una nota sin ningún "Lea más:" salió parcial igual.
- **Medido (% es_parcial por medio):** El Espectador 48.1% (115/239), El Tiempo
  15.6% (28/180), El Colombiano 1.1%, Las2orillas 0%, Vorágine 0%. El 48% (ni ~0%
  ni ~90%) indica que El Espectador distingue activamente abiertas vs restringidas:
  señal real, no ruido.
- **Conclusión:** el crawler lee correctamente isAccessibleForFree del nodo correcto.
  No hay bug. Confirma lo ya documentado en Ideas/"Paywall por isAccessibleForFree":
  El Espectador declara false aunque el cuerpo completo viaje en el HTML público
  (muro = overlay JS). es_parcial=true NO implica cuerpo recortado en este medio.
- **Doble semántica a recordar para Fase 2:** es_parcial funde "el medio declara
  la nota restringida" (detectar_paywall_jsonld) y "el cuerpo archivado está
  recortado" (detectar_parcial por marcador). NO usarlo como proxy de "incompleto"
  en el clustering — descartaría ~115 notas de El Espectador que están enteras.
- **Decisión:** NO tocar el crawler. El uso del flag es visual (badge "de pago"),
  para el que sirve tal cual.
### score_cobertura no comparable entre clústeres de distinto tamaño (2026-06-16)
- **Síntoma (medido sobre clústeres reales):** la cobertura (fracción de entidades
  del clúster que un artículo menciona) sale baja y plana en clústeres grandes
  (0.05–0.22 en el de 18 notas) y alta en chicos (0.5–0.8 en los de 2). Causa: en
  clústeres grandes la unión de entidades es enorme, así ninguna nota cubre gran
  parte. Matemáticamente correcto, pero el score no discrimina bien "cuál es la
  más completa" en clústeres grandes.
- **Decisión:** NO arreglar ahora. Para Fase 2 temprana el criterio de ancla
  funciona (verificado: las anclas elegidas tienen sentido). Es deuda de robustez,
  no de corrección.
- **Reactivar SI:** al construir la vista, el ancla por cobertura elige mal de
  forma visible, o se quiere comparar cobertura entre historias distintas.
- **Fix candidato:** normalizar cobertura por tamaño del clúster, o medirla solo
  contra las entidades de las anclas en vez de la unión total.

### [RESUELTO] Esquema vivo manda — verificar antes de escribir código (2026-06-16)
- **Qué pasó:** el clustering encadenó 4 errores de insert porque su código
  asumía el esquema de la migración 000007 dictada en chat, pero la base tenía
  un esquema distinto de stories/story_articles (boceto previo: titulo_descriptivo,
  articulo_origen_id, estado, todo uuid).
- **Causa raíz doble:** (1) se escribió el código sin leer el esquema real de la
  base primero; (2) la 000007 usó `create table IF NOT EXISTS`, que sobre tablas
  preexistentes NO hizo nada y NO avisó — fallo silencioso. El alter de articles
  sí corrió (por eso entidades/embedding quedaron bien).
- **Lección:** antes de escribir código que dependa del esquema, leer
  information_schema de la base, no confiar en el .sql dictado. Y en componentes
  load-bearing, evitar defensas que fallan en silencio (IF NOT EXISTS, try/except
  mudos): preferir el error ruidoso que delata el desajuste.
- **Fix:** migración 000008_corregir_esquema_stories (drop+create con uuid
  consistente con articles.id). 000007 se deja en disco como historia, con
  comentario que apunta a 000008 (migraciones son append-only, no se reescriben).

### articleBody plano y con enlaces incrustados (2026-06-14)
- **Síntoma 1 (formato):** articleBody del JSON-LD viene como string plano, sin
  saltos de párrafo (verificado con repr() sobre El Colombiano: \n=0). El cuerpo
  se archiva como muro de texto en los medios del bucket articlebody.
- **Síntoma 2 (enlaces incrustados):** articleBody incluye enlaces del medio en
  mitad del cuerpo ("Lea: ...", "Puede leer: ...") que no son contenido del
  artículo. limpiar_contenido no los corta porque van en el medio, no en la cola.
- **Decisión:** NO arreglar. El formato es irrelevante para Fase 2 (embeddings) y
  Fase 3 (sumario); el expediente web es archivo de respaldo, no experiencia de
  lectura. Los enlaces incrustados meten ruido leve, no rompen el clustering.
- **Reactivar SI:** el clustering de Fase 2 sale visiblemente ruidoso y se rastrea
  a estos enlaces, o si se decide hacer la lectura del original dentro de Trama.

### Respaldo trafilatura corta al lead (~10% El Tiempo) (2026-06-14)
- **Síntoma:** notas del bucket articlebody cuyo nodo JSON-LD no expone
  articleBody caen a trafilatura, que a veces extrae solo el lead + firma
  ("PERIODISTA / Actualizado: / LEA TAMBIÉN"). Caso: nota de la Registraduría.
- **Medido:** script de calidad sobre el archivo guardado → 'corto' (<600 chars)
  10% en El Tiempo, 7% en El Espectador, 0% en El Colombiano. 'residuo_firma' 7%
  en El Tiempo. Es la vieja deuda del embed/corte, ahora acotada por articleBody.
- **Decisión:** NO arreglar. Bajo impacto, es el respaldo haciendo su trabajo
  imperfecto en el residuo donde articleBody falta.
- **Reactivar SI:** 'corto' en El Tiempo supera ~20%, o afecta notas relevantes.

### Nota sobre el medidor de calidad (2026-06-14)
- El script de calidad agregado (banderas: corto / enlaces / residuo_firma /
  teasers / fuga_boilerplate) tiene falsos positivos en dos columnas por el texto
  plano de articleBody: 'teasers' se dispara por líneas largas sin puntuación de
  cierre (no son videos), y 'c/enlaces' cuenta "lea:" como substring (matchea
  palabras legítimas). Señal CREÍBLE del medidor: fuga_boilerplate=0% (limpieza
  sólida) y 'corto' (deuda real arriba). Las otras columnas, leer con pinza.

### Clasificador de tipo en Las2orillas y Vorágine (2026-06-12)
- Ninguno usa /opinion/ en el path, así que si publican columnas de opinión las
  marcamos como 'noticia'. Bajo volumen, bajo impacto. Vigilar.

### Feed plano silencia medios de baja frecuencia (2026-06-12)
- El feed muestra los 80 más recientes; El Tiempo (alto volumen) desplaza a
  Vorágine (baja frecuencia) fuera de la ventana. Irónico para un proyecto sobre
  representación.
- **Fix candidato:** paginación, o feed que garantice presencia de todos los
  medios. Resolver en iteración de web.
---

## Ideas registradas (no son deuda, son evolución futura)

### Destilar la vista de historia para no saturar al lector (idea, 2026-06-27)

Jota: "más adelante tendremos que destilar y limpiar para que no se sature de mucha
información y agote al lector de entrada." La vista /historia/[id] ya colapsa por defecto
(hilo: 3 visibles + resto; versiones: 2 + resto; conectadas: top-5 + N más), pero el criterio
de QUÉ mostrar primero sigue siendo crudo (las 3 primeras del hilo = las más antiguas por
orden cronológico). Cuando se llegue a esta pasada, decidir con la página enfrente: ¿primeras
en el tiempo? ¿las de medios más divergentes? ¿resumen de Fase 3 arriba y el resto plegado?
Es decisión de PRODUCTO, no de plumbing; no resolver en abstracto. (Quedó comentario-rastro
en el código del hilo.)

Micro-pendiente asociado: un segundo "ver menos" al FINAL del contenido largo desplegado
(hoy el toggle queda arriba, en la posición del "ver más", por ser <summary> nativo). Ponerlo
abajo requeriría JS de cliente — se difiere para no romper el principio cero-JS; el de arriba
cubre el 90%. Si el contenido es tan largo que molesta volver arriba, la señal es que ESE
clúster necesita destilado, no un botón más.

### Vía OR para reacciones entity-sparse en story_relations (idea, 2026-06-25)
- **Observación medida:** el motor solo-n_especificas deja fuera enlaces de cos alto y
  pocas específicas (1–2) — justo "hecho y su reacción", el corazón del grafo. Ej. extremo:
  Air-e liquidación↔pushback (cos 0.899, ~2 específicas reales tras quitar geografía).
- **Por qué es separable de la madeja:** los pares-madeja que se rechazaron (clima
  domingo↔resultados ciudad, cos 0.86) tienen ~CERO específicas (todo geografía); las
  reacciones reales sí tienen 1–2. Una vía OR "(n_esp≥3) OR (cos≥~0.85 AND n_esp≥2)"
  podría recuperarlas sin readmitir la madeja.
- **NO implementar por inferencia.** Antes: un diag del cuadrante cos-alto/n_esp-bajo para
  medir cuántas reacciones legítimas viven ahí. Solo si el eyeball del grafo vivo muestra
  que faltan. v1 va con compuerta única.

### Diagnóstico read-only: impacto del centroide ponderado por medio (2026-06-25)
- **Destraba la deuda "centroide no ponderado por medio".** Mide ANTES de tocar
  calcular_scores (Tier 2 load-bearing). Corrible sobre el snapshot estático que Jota
  monta a archivos del proyecto (no necesita la base viva).
- **Cuatro preguntas que debe responder:**
  (1) DOMINANCIA: ¿cuántos de los ~122 clústeres tienen un medio con mayoría de URLs?
      Si la mayoría son equilibrados (2-2, 3-2), el fix casi no mueve nada → no vale tocar
      load-bearing. Si muchos son 5-1-1, es real. ESTE número decide si el fix se justifica.
  (2) CORRELACIÓN: ¿el ancla principal actual correlaciona con el medio dominante en
      volumen? (¿se confirma la hipótesis de El Tiempo?).
  (3) DELTA: recalcular el centroide con voto-por-medio y contar en cuántos clústeres
      CAMBIA el ancla. Pocos → no vale; muchos → real.
  (4) CALIDAD: en los que cambian, juzgar a ojo si el ancla nuevo es más representativo
      o es una rareza de un medio de 1 nota (validación del "poder de veto de la minoría").
- **Unidad propia, measure-first.** NO mezclar con el chat del esquema story_relations ni
  con el de activar medios nuevos. Si los datos confirman impacto, recién ahí se toca
  calcular_scores en su propia unidad con Claude Code.

### Relaciones inter-clúster: medición v1–v4 y decisión de criterio (2026-06-24)
- **Qué se midió (diag_relaciones v1→v4, read-only, desechables):** si existe un
  criterio para ligar clústeres relacionados (grafo de historias) sin fusionarlos.
- **Hallazgos con datos:**
  (1) El coseno entre centroides liga por TEMA, no por hecho (clima del domingo ↔
      resultados por ciudad: cos 0.86). No hay valle en su distribución. Sirve de
      GUARDIA, jamás de motor.
  (2) El peso IDF crudo estaba podrido de ruido NER: boilerplate de fuente ("match
      electoral de el espectador"), conectores ("sin embargo", "lea", "encuentre") y
      nombres de medios ("el tiempo", "el colombiano") — ligaban por FUENTE. El IDF
      premia lo raro, así que el boilerplate raro pesaba alto.
  (3) Limpieza en tres capas (ruido duro a mano + geografía clasificada-no-borrada +
      genéricas por DF de CLÚSTER) + métrica n_especificas: FUNCIONA para hechos
      discretos (Air-e, capturas, Arizabaleta, Beto Coral, Cauca, giro LatAm).
  (4) El macro-tema (campaña electoral) es un HUB IRREDUCIBLE. Medido: el cap de
      presentación NO lo desinfla (Pastrana in-degree 26 bajo cap top-5); cluster-IDF
      tampoco (26→23). Causa real: tamaño de clúster — Pastrana/Chalá tienen 125-134
      entidades específicas propias vs 31-40 de un hecho discreto → superficie de
      solapamiento gigante → tocan medio archivo por tamaño, no por relación.
  (5) mean_df (df-de-clúster promedio de las entidades propias) NO discrimina señal de
      ruido: separa "tema grande" de "hecho aislado". Hipótesis descartada con datos.
- **Decisión:** el criterio de story_relations será n_especificas ≥ umbral + coseno
  guardia. El hub se controla con CAP DE IN-DEGREE (+out-degree) en la capa de LECTURA
  (presentación, reversible), NO en la tabla. La distinción "contexto" vs "seguimiento"
  del macro-tema se DIFIERE a Fase 3 (LLM + tipo_relacion): ninguna vara de entidades la
  resuelve.
- **Reactivar/revisar SI:** al diseñar el esquema, el umbral elegido deja pasar madeja,
  o si la sobre-fusión (ver Ideas) resulta ser la causa raíz y la corrige.

### Re-backfill de NER — fix de raíz del ruido de entidades (2026-06-26)
- **Resuelve** la deuda registrada 2026-06-24 ("Ruido de NER contamina relaciones — el
  fix es upstream"). No reescribo esa entrada (append-only); esta la cierra.
- **Diagnóstico measure-first, dos pasos:**
  (1) Diag A (snapshot CSV, read-only, lo corrió Claudio): el filtro que se barajaba
      —"descartar si el primer token es artículo/preposición"— FALLA por los dos lados.
      Mata señal real (La Guajira, La Fiscalía, los Estados Unidos, El Salvador, El
      Consejo Nacional Electoral; ~1509 ocurrencias) Y deja pasar ruido (No se pierda,
      Siga leyendo, Estamos, Gobierno nacional; ~1500+). Ningún filtro a nivel de string
      separa: el ruido viene capitalizado por inicio de oración, así que "minúscula
      inicial" no sirve.
  (2) Diag B (spaCy es_core_news_md, muestra 200, en máquina de Jota): el discriminador
      correcto es morfosintáctico — conservar la entidad si tiene ≥1 token PROPN o es
      sigla en mayúsculas. Descarta MISC 56,8%, conserva PER/ORG/LOC ~96%. El ~4% de
      PER/LOC/ORG descartado NO es señal: es ruido que spaCy MAL-ETIQUETÓ como entidad
      (Además→LOC, Según→PER, Estamos→ORG). El filtro PROPN es más robusto que el propio
      label de spaCy. Rescata siglas (CNE, DANE, CIDH, CTI). MISC se DEJA en TIPOS_ENT: el
      43% que conserva es señal con PROPN (eventos); el filtro la separa sin tratar el
      label como criterio.
- **Decisión de diseño:** filtro en ner_filtro.py como FUENTE ÚNICA, importado por
  backfill_fase2.py (futuros) y rebackfill_ner.py (banco). Una sola definición = pasado y
  futuro consistentes (evita el riesgo de divergencia de duplicar la lógica). Regla:
  ≥1 PROPN o sigla, no-medio (MEDIOS = lista CERRADA; NO crecer con boilerplate, eso es
  deuda de extracción), topes 60 chars / 8 tokens. DIVISIÓN DE TRABAJO: el filtro NER quita
  lo que NO es entidad; las genéricas reales (Petro, Gobierno nacional) las sigue manejando
  el IDF / FRAC_GENERICA, no el filtro. De paso corrige el bug viejo count(" ")>4, que
  mataba institucionales largas legítimas (Instituto Colombiano de Bienestar Familiar).
- **Dry-run (2732 art., sin escribir):** −20,2% entidades. 2 vacíos (notas cuyo NER era
  100% ruido — correcto, no anclan clúster). 80 ganancias (recuperación de largas con
  PROPN; mecanismo del bug viejo). Mayores pérdidas concentradas en horóscopos/opinión
  (ruido puro: tarot, primera persona, conectores). Ningún medio colapsa; voragine limpia
  más (26%, coherente con extracción trafilatura-only) pero queda con mediana 10,5 y cero
  vacíos.
- **Impacto en stories (medido contra snapshot _stories_pre_ner):** 151→149. uuid
  sobreviven 143 (94,7%), rotos 8, nuevos 6. El −2 neto = disolución de uniones espurias
  que existían por compartir boilerplate de alto IDF (uniones por fuente, no por hecho).
  Es el efecto buscado, no un daño. 8 enlaces /historia/[id] rotos: bajo, no dispara la
  tabla de identidad. Conexión con la sospecha de sobre-fusión (TRASPASO previo #2): el
  re-backfill atacó parcialmente esa causa (boilerplate inflando la compuerta 1).
- **Inmutabilidad:** UPDATE SOLO de entidades (campo derivado); contenido_visible/hash
  intactos. Coherente con stories = caché derivada.
- **Reactivar/revisar SI:** se cambia el filtro NER de nuevo (re-correr el re-backfill), o
  un medio nuevo se activa (agregar a MEDIOS), o aparece una clase de ruido que el filtro
  PROPN no atrapa (medir antes de tocar).

### Ruido de NER contamina relaciones — el fix es upstream, no en relaciones (2026-06-24)
- **Síntoma medido:** aun con stoplist a mano, colaban "entidades" basura ("la captura",
  "según las autoridades", "los hechos") y nombres de medios. El stoplist a mano es
  perder: la cola de basura de NER es infinita.
- **Causa:** NER básico en backfill_fase2.py (ya registrado como Idea con disparador). A
  nivel artículo el IDF sobre miles de docs lo lavaba; a nivel de unión de entidades de
  clúster, el ruido se concentra y manda.
- **Decisión:** NO limpiar en la capa de relaciones (whack-a-mole). El fix de raíz es
  mejorar el filtro NER en backfill (Tier 2 load-bearing, requiere re-backfill) — su
  propia unidad. Las relaciones se protegen con genéricas-por-DF + stoplist duro acotado
  (medios) como mitigación, no como solución.
- **Reactivar SI:** se aborda la unidad de relaciones a fondo, o el ruido ensucia el
  grafo de forma visible al exponerlo.

### story_relations ensancha la ventana del delete-then-insert (2026-06-24)
- **Decisión en frío:** story_relations será caché derivada pura, recomputada en la
  misma corrida que stories (delete+insert). Coherente con "stories = caché derivada",
  pero AGREGA otra tabla a la ventana no transaccional ya documentada. A esta escala no
  muerde; registrado para no olvidarlo al hacer el clustering atómico/transaccional.
- **Reactivar SI:** se ataca la robustez del delete-then-insert (entonces cubrir ambas
  tablas), o el banco crece y la ventana de web vacía se vuelve inaceptable.

### [RESUELTO 2026-06-21 → ver Deuda técnica/"UUID estable de stories"] Estabilidad de enlaces de historias (UUID estable) — prerequisito de automatización (2026-06-21)
- **Problema:** reescribir_stories (clustering_fase2.py) hace delete()+insert() de
  stories en cada corrida → uuid nuevo cada vez → todo enlace /historia/[uuid] que
  alguien comparta (redes, evidencia, cita) se ROMPE tras la siguiente corrida. Para
  una hemeroteca forense cuyo valor es "comparte este link como prueba", es una
  herida en la propuesta, no un detalle.
- **NO es optimización de cuota** (no hay cuota: el clustering es coseno en numpy
  sobre embeddings ya calculados, cero API). Es identidad + escala. Se aclara porque
  surgió de una idea de "recalcular solo lo reciente para ahorrar" que se descartó
  (ver abajo).
- **Por qué importa el ORDEN:** es prerequisito de automatizar clustering. Hoy se
  corre a mano y esporádico, daño bajo; automatizado, se multiplica. Ids estables
  ANTES de automatizar, no al revés. Reordena la cola por encima de "automatizar".
- **Opciones a evaluar (sin decidir):**
  * ID determinista por semilla estable: derivar el id del artículo más antiguo del
    clúster (primera captura casi nunca cambia). Robusto al crecimiento; borde =
    fusiones de clústeres (¿qué semilla gana?).
  * Tabla story_identity persistente que sobreviva los truncates y mapee
    firma-de-clúster → uuid estable, reusándolo entre corridas. Más robusto, más complejo.
  * Hash del conjunto de artículos: DESCARTADO de entrada — si el clúster gana un
    artículo (lo esperado), el hash cambia. No sirve.

### Clustering incremental (recalcular solo lo reciente) — DESCARTADO como optimización (2026-06-21)
- Idea: no recalcular clústeres viejos cada corrida, solo los recientes, para
  "ahorrar consumo/tiempo".
- **Descartada con tres razones:** (1) lo caro (embeddings + NER) YA es incremental
  vía backfill idempotente; el clustering NO recalcula embeddings, solo hace coseno
  en numpy sobre vectores existentes — cero API, cero cuota, segundos a 982 arts.
  Optimizar es prematuro (el O(n²) real aparece a decenas de miles, 10-14 meses
  lejos). (2) Convertiría stories de CACHÉ DERIVADA PURA (reconstruible) a ESTADO,
  con casos borde feos (artículo nuevo a clúster viejo: ¿re-ancla?; artículo puente
  fusiona clústeres: ¿qué uuid sobrevive?). (3) FOSILIZA umbrales provisionales:
  hoy cada recompute total es la oportunidad de re-juzgar el banco al recalibrar
  IDF/coseno/p75; incremental congela decisiones con umbrales viejos — justo lo que
  el TRASPASO bloquea hasta tener volumen multitema.
- **El grano de verdad de la intuición** se rescató como deuda aparte: la
  inestabilidad de UUID (arriba). Esa SÍ es real; la optimización de cómputo no.

### Generar título de historia por LLM — DESCARTADO (2026-06-21)
- Idea: usar NVIDIA NIM para generar el título de cada clúster. Cuota viable (48
  requests, ~1-2 min, sin créditos que gastar — la cuenta es rate-limited 40rpm).
- **Descartado pese a viabilidad de cuota**, por cuatro razones de fondo: (1)
  inmutabilidad/honestidad forense — un título generado es texto que ningún medio
  escribió, en el elemento más prominente del feed, sin etiqueta de IA (distinto del
  resumen LLM de Fase 3, que va ETIQUETADO como análisis). (2) no-determinismo
  rompe reproducibilidad. (3) alucinación en la cara del producto. (4) no es el
  arreglo rápido — monta media infra de Fase 3 dentro de Fase 2.
- **Jerarquía registrada:** heurística de selección (lo hecho hoy) < selección por
  LLM (el modelo ELIGE entre titulares reales, no inventa, no alucina, mantiene
  inmutabilidad) < generación por LLM (escribe título nuevo, rompe inmutabilidad).
  Si la heurística alguna vez se queda corta, el escalón siguiente es SELECCIÓN por
  LLM, no generación. Probablemente ese es el óptimo para Trama.
  
### Proveedor LLM de Fase 3 — DECIDIDO: NVIDIA NIM (2026-06-19)
- Cambio: el plan era Groq + Llama 3.3. Se adopta NVIDIA NIM (catálogo hosted
  build.nvidia.com), endpoint OpenAI-compat (https://integrate.api.nvidia.com/v1),
  modelo default meta/llama-3.3-70b-instruct.
- Por qué NVIDIA sobre Groq: variedad de modelos para evaluar (Nemotron Super 49b,
  Qwen, etc. bajo un mismo endpoint) y verificado que devuelve JSON estricto en
  español a temp baja. NO se eligió por potencia: reasoning models (DeepSeek,
  Nemotron Ultra) quedan descartados para esta tarea — más lentos, más cuota, cero
  ganancia en un clasificador conservador con JSON.
- Verificación de sostenibilidad (lo que destrababa la decisión): el panel de la
  cuenta muestra rate-limit (Up to 40 rpm), NO un balance de créditos que se agota.
  Para un job batch recurrente como Fase 3, eso es lo que se necesitaba. La
  ambigüedad "créditos vitalicios vs rate-limit" de la documentación pública NO
  aplica a esta cuenta. (Headers de respuesta NO exponen el límite; vive solo en
  el panel UI.)
- Es llamada API pura: NO se hostea nada, la GPU local (AMD) es irrelevante. El
  cómputo corre en datacenters NVIDIA. El "Downloadable NIM" (contenedor self-host
  + licencia AI Enterprise) es OTRO producto, fuera de alcance.
- Decisiones de implementación atadas:
  * Cliente SWAPPABLE: base_url + api_key + model_id en config/.env, nunca hardcode.
    Razón dura: el catálogo NIM rota casi a diario (doc "updated 10h ago") y no hay
    SLA — un model_id hardcodeado rompe Fase 3 cuando NVIDIA jubile el modelo.
  * JSON forzado por PROMPT + parse/validate/retry, NO por extensión propietaria de
    NVIDIA (nvext/guided). La extensión rompería la portabilidad a Groq y mataría el
    cliente swappable. El wrapper de validación se quería igual (sin SLA).
  * Modelo síncrono a propósito: los modelos grandes del catálogo usan patrón async
    (202 + status-polling); llama-3.3-70b-instruct es POST directo. Elegir un async
    es trabajo extra consciente, no default.
  * Retry con backoff en 429 (throttling por tráfico compartido, sin SLA).
- Groq + Llama 3.3 70B queda como FALLBACK documentado, mismo cliente OpenAI-compat.
- Reactivar/conmutar a Groq SI: las corridas empiezan a dar 402/403 por créditos
  agotados, o el throttling de NIM hace inviable el batch. Es cambio de config, sin
  reescritura.
  
### Iconos "ⓘ más información" contextuales en la UI (2026-06-18)
- Idea de Jota al recortar el aviso de "artículo sin clúster" en /buscar: el texto
  largo invadía el UI de entrada. Se recortó a una frase. La idea futura es añadir
  un icono "ⓘ" junto a textos breves que, al interactuar, revele el contexto
  completo bajo demanda — sin saturar la vista inicial.
- Patrón general, no solo para /buscar: aplicable a cualquier punto donde haga
  falta explicación secundaria (badges es_parcial, scores, etc.).
- NO implementar ahora. Es mejora de UX transversal; merece decidirse como patrón
  (¿tooltip hover? ¿popover tap-friendly en móvil? ¿accesibilidad/foco?) en vez de
  parchear caso por caso. Registrar para no perderla.
  
### Pequeños arreglos pendientes del buscador (2026-06-18)
- Iteración B quedó funcional y con tests verdes, pero Jota detectó arreglos
  menores a trabajar en chat aparte. (Detalle cuando se aborden — no se anticipan
  aquí para no inventar alcance.)

### JSDoc para chequeo de tipos sin migrar a TS (2026-06-17)
- El único valor que TS aportaría es tipar el contrato de los 3 scores (que es_ancla
  sea bool, scores números) para avisar si el shape de Supabase cambia. No justifica
  meter TypeScript a un proyecto JS. Si alguna vez el shape del backend muerde,
  JSDoc da chequeo en editor/CI sobre .jsx puro. No urgente.

### Política de archivado de bitácora (acordada 2026-06-16)
- BITACORA es append-only y NO se condensa (condensar pierde el "por qué"
  original, que es justo lo que la bitácora preserva). Cuando una entrada se
  resuelve, se le antepone marcador `[RESUELTO fecha]` sin borrarla.
- Al cerrar cada fase, las entradas de esa fase se mueven EN BLOQUE (sin
  reescribir) a `/archive/BITACORA_faseN.md`, dejando en la viva un puntero +
  las reglas de esa fase que sigan vigentes.
- **Disparador del primer corte:** cierre de Fase 2. No hacer antes (el costo de
  tokens de un MD largo es bajo; el riesgo real es dilución de señal, que el
  marcador [RESUELTO] ya mitiga sin necesidad de cortar).

### Filtro anti-basura de NER (2026-06-16)
- spaCy marca como entidad cosas que no lo son ("Además", "Asimismo", frases
  largas tipo "Un millón de personas deben inscribirse..."). El backfill ya aplica
  un filtro mínimo (longitud 2–40, ≤4 espacios, stopwords de conectores). Funcionó
  (ents_promedio sano = 16.9), pero es básico.
- **Mejora futura:** filtro más fino si el ruido de NER infla pesos IDF de pares
  aislados y ensucia clústeres. No urgente — los clústeres del 2026-06-16
  salieron limpios con el filtro mínimo.

### Feeds de cola verificados — RTVC y La Silla Vacía (2026-06-16)
- Verificados con script de feeds (diligencia previa, NO activados):
  - La Silla Vacía → https://www.lasillavacia.com/feed/ (rss, WordPress)
  - RTVC Noticias → https://www.rtvcnoticias.com/rss.xml (rss; su /feed/ da 404)
- **Pendiente antes de admitirlos:** diagnosticar su bucket de extracción
  (articlebody vs trafilatura) — no heredan el de nadie. La Silla es WordPress
  con paywall parcial (fuerte en análisis, bajo volumen de minuto a minuto); RTVC
  es estatal. Activarlos solo tras decidir construir sobre 7 medios — hoy se
  mantiene el banco de 5 validados.
  
### ⭐ articleBody — RESUELTO/IMPLEMENTADO (2026-06-14)
- La hipótesis de "migrar TODO a articleBody" se descartó con datos. El
  diagnóstico (muestra fresca + casos conocidos) mostró complementariedad:
  articleBody al 100% en El Tiempo y El Colombiano, 83% en El Espectador (donde
  trafilatura sufría boilerplate), AUSENTE en Vorágine (sin JSON-LD) y Las2orillas
  (donde trafilatura ya extrae limpio). Decisión: híbrido por bucket, no reemplazo.
- El premio real NO fue la deuda de El Tiempo (el corte midió 0: ya mitigada al
  quitar favor_precision la sesión anterior), sino cuerpos limpios (boilerplate 0%)
  como materia prima para el clustering de Fase 2.
- Riesgo ético del paywall: medido y descartado. El cuerpo de notas de pago de El
  Espectador ya lo capturaba trafilatura (muro = overlay JS, cuerpo en HTML
  público). articleBody no da acceso a nada nuevo.
- Se consideró REVERTIR a solo-trafilatura (corazonada de simplicidad) pero se
  mantuvo el híbrido: el dolor de articleBody es cosmético (formato), el beneficio
  es de contenido (boilerplate 0%). No re-evaluar desde cero sin un motivo nuevo.

### Filtro de notas-video de El Tiempo (2026-06-14)
- Decisión de alcance (no es deuda): se saltan notas cuyo título de feed empieza
  con "Video |". Son piezas de video sin cuerpo de texto archivable; no aportan
  snapshot ni materia para clustering. Filtro por convención de titulación de El
  Tiempo (no global). Si cambian el patrón, se colarían y caerían al filtro de
  longitud — vigilar.

### ⭐ articleBody del JSON-LD — posible cambio de enfoque de extracción (2026-06-13)
- **Hallazgo:** El Espectador expone "articleBody" dentro del JSON-LD (verificado
  con probar_paywall2.py). Es el cuerpo del artículo completo y estructurado,
  inmune a los problemas de maquetación que confunden a trafilatura.
- **Hipótesis de alto valor:** si los demás medios (sobre todo El Tiempo) también
  exponen articleBody, podríamos pasar de "trafilatura adivina el cuerpo" a "leer
  el cuerpo del JSON-LD". Resolvería de raíz la deuda de extracción de El Tiempo
  (Cartagena, El Poblado) y mejoraría la calidad general.
- **Por qué NO se hizo ahora:** es un cambio grande en el componente más delicado
  (extracción). Merece su propia sesión: diagnóstico de cobertura por medio
  (¿quién tiene articleBody?), validar que viene completo y limpio, decidir si
  reemplaza o complementa a trafilatura, y probar antes de tocar producción.
- **Primer paso cuando se retome:** correr un probador de articleBody sobre los 5
  medios (similar a probar_extraccion.py) y comparar largo/calidad vs trafilatura.

### Paywall por isAccessibleForFree — RESUELTO PARCIALMENTE (2026-06-13)
- El Espectador declara "isAccessibleForFree":"false" en su JSON-LD para notas de
  pago. Se agregó detectar_paywall_jsonld() al crawler; es_parcial ahora combina
  esa señal (OR) con detectar_parcial por marcador.
- **Limitación aceptada:** no se recrawleó (para no truncar de nuevo). Las notas
  de paywall ya capturadas siguen marcadas como completas; solo las nuevas entran
  bien marcadas. Impacto bajo, es solo un flag de honestidad.
- El muro visible ("CONTINÚA LEYENDO... $9.000") es un overlay JS que NO llega al
  crawler — por eso buscar su texto no sirve; isAccessibleForFree es la señal real.

### Grafo de historias relacionadas (idea de Jota, 2026-06-12)
- Más allá de clústeres aislados: artículos que no son la misma noticia pero
  están ligados (una nota y su derivada, un hecho y su reacción). Relación
  ENTRE clústeres, no solo dentro. Mejora el modelo original de Fase 2.
- Implementar después de validar que el clustering simple funciona.

### Expansión de medios (criterios acordados)
- Cola actual: Colombia+20, La Silla Vacía (Fase 2); Semana, Caracol/W Radio,
  RTVC (Fase 3). RTVC aporta ángulo de medio público estatal.
- **Criterios de admisión:** (1) cada medio nuevo debe aportar un ángulo que los
  actuales no cubren; (2) verificar feed con verificar_feeds.py antes de
  prometerle lugar. Medios de paywall duro aportan solo titulares/ledes.

### [RESUELTO 2026-06-18]Nav en móvil — diseño pendiente (2026-06-17)
- `.masthead-nav` se oculta con `display:none` en pantallas <560px (globals.css).
  Funciona en desktop; en móvil no hay acceso a /historias desde el masthead.
- **Diseño pendiente:** decidir entre menú hamburguesa, barra secundaria bajo
  el masthead, o integrar las rutas principales en el pie. No diseñar antes de
  tener usuarios móviles reales — priorizar por datos de uso.
- **No bloquea Fase 2:** la ruta /historias es accesible en móvil por URL directa.

### Filtros y navegación en la web (pendiente)
- Falta: filtrar por medio, por tipo, por sección; búsqueda. La búsqueda por
  texto conviene dejarla para Fase 2 (aprovechar entidades/embeddings). El filtro
  por medio/tipo/sección se puede hacer ya sobre datos actuales.

### Perfiles de medios (Fase 3, espacio ya reservado)
- Columnas en outlets listas (propietario, grupo_economico, etc.). UI mostrará
  lista de secciones por medio + filtro. Cada dato de propiedad/financiación
  necesita fuente citable; será lo más atacado del proyecto.

### Vista de clúster Fase 2 — diseño cerrado (2026-06-15)
- Sesión dedicada a prototipar la UI de la vista de historia (expediente de
  clúster). Todas las decisiones visuales están aprobadas y documentadas en
  TRASPASO.md bajo "DISEÑO DE FASE 2 — decisiones cerradas".
- **Decisiones que afectan el modelo de datos / backend:**
  - El criterio de anclas (neutralidad + cobertura + divergencia semántica)
    requiere que el pipeline de clustering produzca tres scores por artículo
    dentro del clúster. No es solo un dato de display — es un contrato con
    el algoritmo. Definir cómo se calculan antes de implementar la vista.
  - El historial de versiones por nodo del hilo requiere que `story_articles`
    pueda devolver todas las capturas de un mismo medio para una historia,
    ordenadas por fecha_captura. Verificar que el esquema lo soporte sin
    migración adicional.
  - El grafo panorámico requiere una tabla o vista de relaciones entre clústeres
    (stories). No existe aún. Es Fase 2 avanzada, no Fase 2 temprana.

### Hilo rojo curvo — pendiente de precisar (2026-06-15)
- **Idea aprobada, implementación pendiente:** el hilo cronológico no debe ser
  línea recta. Usar SVG `<path>` con curvas de Bézier para simular la física
  de un hilo real (cuelga levemente entre nodos). El nodo de historia relacionada
  se desvía hacia una esquina con el hilo curvándose hacia allá.
- **Restricción de diseño:** un solo desvío visible por historia. Las demás
  conexiones viven en el grafo panorámico. Elegancia sobre dramatismo.
- **Por qué no se implementó ahora:** es detalle de implementación visual, no
  de arquitectura. Se precisa cuando se construya la vista real en Next.js.
  En SVG: `<path d="M x0,y0 C cx1,cy1 cx2,cy2 x1,y1">` con puntos de control
  calculados dinámicamente según posición de los nodos.

### Grafo de historias relacionadas — modelo de datos implicado (2026-06-15)
- La vista panorámica del grafo (idea original de Jota, registrada 2026-06-12)
  ya tiene diseño aprobado. Lo que falta es la tabla de relaciones entre stories.
- **Propuesta de esquema mínimo cuando se implemente:**
  `story_relations(id, story_id_a, story_id_b, tipo_relacion, score, created_at)`
  donde `tipo_relacion` puede ser: 'derivada', 'reaccion', 'contexto', 'seguimiento'.
- Calcular con entidades compartidas entre clústeres + similitud semántica entre
  los embeddings promedio de cada clúster. Implementar DESPUÉS de validar
  clustering simple — no antes.
---

## Notas de operación

- **Pipeline CI encadenado (2026-06-23):** crawler.yml tiene dos jobs: crawl (cron 6h
  + dispatch) y backfill (needs:crawl). Entornos separados a propósito: crawl liviano
  (httpx+trafilatura), backfill pesado (torch CPU-only + spaCy + sentence-transformers,
  requirements-backfill.txt aparte). Caché pip + ~/.cache/huggingface (clave estática
  hf-...-minilm-l12-v2; subir sufijo si cambia el modelo en backfill_fase2.py). torch
  se instala con --index-url .../whl/cpu ANTES del requirements para evitar el build CUDA.
  El clustering NO está en este workflow (sigue manual, a la espera de recalibrar umbrales).
- **Divergencia silenciosa de git (2026-06-23):** un merge hecho en GitHub adelantó main
  remoto mientras se trabajaba local sin pull. El push pidió pull→merge commit. Mismo
  patrón de riesgo que el "manual-doble" de migraciones. Hábito: pull al EMPEZAR la unidad.
- **Remoto del repo:** github.com/Mr-JotA-94/trama (ojo: no JotaLabs/trama).

- **Capitalización de archivos (convención fijada 2026-06-17):** directorios de
  ruta lowercase (app/buscar/, app/components/), archivos de componente PascalCase
  (Buscador.js), archivos de ruta/lib lowercase (page.js, normalizarUrl.js).
  Windows NO distingue mayúsculas pero Vercel (Linux) SÍ: un import que funciona en
  local puede romper en producción. **Pendiente de limpieza:** revisar duplicados
  por capitalización en la raíz (Cierre.md vs CIERRE.md, Arquitectura.md vs
  ARQUITECTURA.md) — decidir UNA forma y alinear, o git los tratará como archivos
  distintos.
- **Flujo de migraciones es manual-doble:** pegar el SQL en el editor de Supabase
  ES lo que cambia la base (fuente de verdad); copiar el archivo a
  /supabase/migrations es solo espejo en git, NO se aplica solo. Riesgo: divergencia
  silenciosa si se pega algo y no se guarda igual. Pegar SIEMPRE exactamente lo que
  se guarda. Idea futura (otra sesión): invertir el flujo con `supabase db push`.

- GitHub Actions: crons no son puntuales (corren con retraso variable). Normal en
  tier gratis. También: Actions desactiva crons tras 60 días sin commits del repo.
- Vercel cachea el feed (revalidate 300s) y artículos (3600s). Tras un truncate,
  los enlaces viejos dan 404 hasta redeploy. En operación normal (solo agregar,
  no borrar) esto no molesta.
- WinError 10054 ocasional en el crawler = el servidor del medio cerró la
  conexión (throttling transitorio). El try/except lo aísla; el artículo entra
  en la siguiente corrida. Solo preocupa si es en cascada.
