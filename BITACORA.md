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

### Extracción El Tiempo — notas con embed temprano (2026-06-13)
- **Síntoma:** ~1.7% de notas de El Tiempo (casos: Cartagena, El Poblado) quedan
  cortadas al lead. El cuerpo real existe en el HTML pero trafilatura no lo extrae.
- **Causa probable:** un embed (tweet/video) insertado cerca del inicio confunde
  a trafilatura, que lo toma como fin del contenido. NO es la firma
  "PERIODISTA/Actualizado:" (esa está en todas las notas y no rompe), NI la
  longitud (promedio de El Tiempo es sano, 4441 chars).
- **Decisión:** NO arreglar. Impacto bajo (1.7%), riesgo del fix alto (código
  nuevo en el componente más delicado, podría romper el 98% que funciona).
- **Reactivar SI:** al sumar volumen o medios, el % de notas <600 chars en El
  Tiempo supera ~10%, o si se ve afectando notas claramente relevantes.
- **Fix candidato:** extractor específico para El Tiempo vía articleBody del
  JSON-LD (no verificado aún si El Tiempo lo expone — correr probar_tiempo2.py).

### Sección de Las2orillas no disponible (2026-06-12)
- La sección no vive en la URL del artículo de Las2orillas (vive en URLs de
  categoría /c/seccion/). Se guarda null.
- **Fix candidato:** extraer del HTML/breadcrumb al crawlear. Baja prioridad.

### Clasificador de tipo en Las2orillas y Vorágine (2026-06-12)
- Ninguno usa /opinion/ en el path, así que si publican columnas de opinión las
  marcamos como 'noticia'. Bajo volumen, bajo impacto. Vigilar.

### Feed plano silencia medios de baja frecuencia (2026-06-12)
- El feed muestra los 80 más recientes; El Tiempo (alto volumen) desplaza a
  Vorágine (baja frecuencia) fuera de la ventana. Irónico para un proyecto sobre
  representación.
- **Fix candidato:** paginación, o feed que garantice presencia de todos los
  medios. Resolver en iteración de web.

### rfind vs find en limpiar_contenido — REVERTIR (2026-06-13)
- Se cambió find→rfind en el corte de cabecera creyendo que el título duplicado
  causaba el recorte de El Poblado. El script probar_rfind.py demostró que el
  título aparece 1 sola vez en el texto extraído: find y rfind dan idéntico.
  El cambio no rompe nada pero tampoco arregla nada.
- **Acción pendiente:** revertir a find por honestidad del código.

---

## Ideas registradas (no son deuda, son evolución futura)

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

- GitHub Actions: crons no son puntuales (corren con retraso variable). Normal en
  tier gratis. También: Actions desactiva crons tras 60 días sin commits del repo.
- Vercel cachea el feed (revalidate 300s) y artículos (3600s). Tras un truncate,
  los enlaces viejos dan 404 hasta redeploy. En operación normal (solo agregar,
  no borrar) esto no molesta.
- WinError 10054 ocasional en el crawler = el servidor del medio cerró la
  conexión (throttling transitorio). El try/except lo aísla; el artículo entra
  en la siguiente corrida. Solo preocupa si es en cascada.
