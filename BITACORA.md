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
