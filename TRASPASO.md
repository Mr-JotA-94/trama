# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> **Propósito de este archivo:** dárselo a un chat nuevo de Claude para que retome
> el proyecto con todo el contexto, sin releer conversaciones viejas. Léelo junto
> con ARQUITECTURA.md (el plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-06-15**.

---

## Quién soy y cómo trabajamos

Soy Jota (Johan). Claude es "Claudio". Reglas de trabajo que NO deben perderse:
- **Challenge-first:** Claudio cuestiona enfoques con fallas ANTES de construir,
  nunca obedece en silencio. Honestidad por encima de complacencia.
- **Declarar Tier (0–3) + componentes load-bearing antes de construir.**
- **Directo y conciso**, enfoque instructivo (me explica la lógica para aprender,
  no solo me da código). Español.
- **Medir antes de arreglar:** no se mete código por reflejo; se evalúa impacto vs
  riesgo. Varias veces hemos decidido NO arreglar un bug medido de bajo impacto.
- **Diagnóstico con datos reales, no suposiciones.** Cuando Claudio no puede
  verificar algo en su entorno, me da un script para correr en mi máquina.
- **Eficiencia de la sesión:** scripts chicos como código en el chat, no como
  archivos. Para cambios de código, bloques/diffs puntuales, no reescribir archivos
  enteros. No subir volcados de resultados completos: pegar solo el resumen.

## Qué es Trama (una frase)

Hemeroteca forense de medios colombianos: archiva el contenido públicamente
visible de cada noticia con hash SHA-256 y marca de tiempo, para (Fase 2+) rastrear
cómo un mismo hecho se cubre distinto entre medios y (Fase 3) señalar técnicas de
persuasión. Objetivo de fondo: que el lector vea todos los ángulos, sin sesgo.
Público: periodistas, verificadores, ciudadanos activos. NO el público general.

## Stack (todo gratis)
- **Crawler:** Python (httpx + trafilatura + articleBody del JSON-LD), corre en
  GitHub Actions cada 6h
- **BD:** Supabase (Postgres + pgvector), región São Paulo. Claves formato nuevo
  (sb_secret_ para crawler / sb_publishable_ para web). RLS = solo lectura pública.
- **Web:** Next.js 14 (Server Components), deploy en Vercel → trama-co.vercel.app
- **Repo:** GitHub JotaLabs/trama (privado). Estructura: /crawler, /web,
  /supabase/migrations, ARQUITECTURA.md, BITACORA.md, CIERRE.md
- **Esquema versionado** en migraciones numeradas (van 6: la última es
  000006_extraccion_por_medio).

## DÓNDE ESTAMOS — estado real al 2026-06-15

**Fase 1 COMPLETA y desplegada.** El crawler corre solo, la web está pública.
- 5 medios balanceados: Vorágine, Las2orillas, El Espectador, El Tiempo, El Colombiano
- Deduplicación por hash verificada en CI
- Web con 3 vistas: registro (feed), expediente (artículo+hash), perfil de medio
- Sistema de diseño propio: papel/tinta/resaltador/hilo rojo, tipografía Archivo
- Extracción híbrida por bucket activa (migración #6)

**Estamos en la semana de observación de Fase 1** (criterio: 7 días verde, ≥150
artículos, 5 medios, cero duplicados, tipos correctos ≥80%).

**Lo último que hicimos (sesión 2026-06-15):** sesión de diseño puro. Se prototipó
iterativamente la vista de clúster de Fase 2 en mockup interactivo. Decisiones de
diseño cerradas y listas para implementar cuando el clustering esté listo.

## DISEÑO DE FASE 2 — decisiones cerradas (sesión 2026-06-15)

Estas decisiones están aprobadas visualmente y deben guiar la implementación:

**Vista de historia (expediente de clúster):**
- Resumen del hecho: bloque prominente arriba, placeholder en Fase 2, generado
  por LLM en Fase 3. Anotación visible: "Fase 3 · generado por LLM por clúster".
- Layout bento editorial: 2 cards ancla (tamaño completo, borde izquierdo 3px
  del color del medio) + N cards secundarias (grid compacto, borde 1px).
- Criterio de anclas: mayor neutralidad + mayor cobertura de hechos + mayor
  divergencia semántica del clúster. Calculable con embeddings. El label en la
  UI debe ser explícito — es un contrato con el backend.
- Análisis de persuasión: acordeón colapsable por card, disponible en Fase 3.
  Placeholder visible desde Fase 2 con anotación de fase.
- Sección del artículo: esquina superior derecha en cada card y en el feed.
- Reacciones (opinión/análisis): sección separada debajo de las versiones de
  noticia, no mezcladas con el clúster núcleo.

**Hilo cronológico:**
- Muestra primera captura y última edición por medio.
- Ediciones: hora original tachada (line-through + opacity 0.45) + hora nueva
  en rojo + badge "editada".
- Cada nodo es clickeable y abre popup con historial completo de versiones
  (todas las capturas con hash de ese medio en esa historia).
- Nodo de historia relacionada: círculo hueco al final del hilo, separado por
  segmento discontinuo (· · ·), con flecha ↗ y título abreviado.
- **Pendiente de precisar en implementación:** el hilo no debe ser línea recta.
  Usar SVG path con curvas tipo "hilo que cuelga entre clavos" (curvas de Bézier
  con tensión orgánica). El nodo de historia relacionada se desvía hacia una
  esquina (derecha-abajo preferido). Un solo desvío visible por historia; las
  demás conexiones viven en el grafo panorámico. Prioridad: que no se vea
  desordenado — elegancia sobre dramatismo.

**Grafo panorámico de historias conectadas:**
- Botón expandible al final del expediente: "Ver historias conectadas".
- Nodo activo con borde #C8442E 2px; nodos relacionados con borde normal.
- Líneas SVG discontinuas entre nodos, dibujadas dinámicamente sobre posición
  real del DOM (no coordenadas hardcodeadas).
- Cada nodo es clickeable → abre el expediente de esa historia.
- Disponible en Fase 2 avanzada (requiere relaciones entre clústeres calculadas).
  En Fase 2 temprana: placeholder con nodos ilustrativos y nota de fase.

**Barra de búsqueda:**
- Input con ícono lupa + botón "Filtros" que despliega panel.
- Filtros: sección, tipo (noticia/opinión/análisis/editorial), medio, fecha desde,
  fecha hasta. Botón "Aplicar".
- Búsqueda por texto: aprovechar entidades/embeddings de Fase 2. En Fase 2
  temprana: búsqueda simple sobre título.

## PRÓXIMO PASO cuando retomemos

**Opción A (recomendada):** completar la semana de observación de Fase 1 y
arrancar Fase 2 — clustering. El diseño ya está cerrado; la siguiente sesión
de trabajo real es implementar el pipeline de entidades + embeddings.

**Opción B:** si la observación ya pasó satisfactoriamente, ir directo a las
decisiones pendientes de Fase 2: umbral de similitud, ventana temporal, clústeres
de tamaño 1. Ver BITACORA.md.

## Fase 2 NO obliga a reconstruir al agregar medios
El clustering opera sobre artículos, no sobre medios. Agregar un medio = config
nueva en outlets. Solo los umbrales se recalibran. Validar clustering con 5 medios
antes de expandir. Cola: Colombia+20, La Silla Vacía, Semana, Caracol/W Radio, RTVC.

## Cómo verificar el estado en cualquier momento
- Salud del archivo: contar artículos/tipos/secciones por medio en Supabase.
- Buckets de extracción: `select slug, extraccion from outlets order by slug;`
- Corridas del crawler: pestaña Actions del repo (deben estar en verde).
- La web: trama-co.vercel.app