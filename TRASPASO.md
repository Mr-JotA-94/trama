# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> **Propósito de este archivo:** dárselo a un chat nuevo de Claude para que retome
> el proyecto con todo el contexto, sin releer conversaciones viejas. Léelo junto
> con ARQUITECTURA.md (el plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-06-14**.

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
  verificar algo en su entorno (ej. los medios bloquean su IP de datacenter), me
  da un script para correr en mi máquina y decidimos sobre datos verdaderos.
- **Eficiencia de la sesión:** scripts chicos como código en el chat (yo genero
  el .py), no como archivos. Para cambios de código, bloques/diffs puntuales, no
  reescribir archivos enteros (sobre todo el crawler, que es load-bearing). No
  subir volcados de resultados completos: pegar solo el resumen.

## Qué es Trama (una frase)

Hemeroteca forense de medios colombianos: archiva el contenido públicamente
visible de cada noticia con hash SHA-256 y marca de tiempo, para (Fase 2+) rastrear
cómo un mismo hecho se cubre distinto entre medios y (Fase 3) señalar técnicas de
persuasión. Objetivo de fondo: que el lector vea todos los ángulos, sin sesgo.
Público: periodistas, verificadores, ciudadanos activos. NO el público general.
Nota de enfoque: el expediente web es el archivo público de respaldo (lectura del
original = enlace al medio); el valor para el usuario será el sumario/comparación
entre medios, no leer la nota completa dentro de Trama.

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

## DÓNDE ESTAMOS — estado real al 2026-06-14

**Fase 1 COMPLETA y desplegada.** El crawler corre solo, la web está pública.
- 5 medios balanceados: Vorágine, Las2orillas, El Espectador, El Tiempo, El Colombiano
- Deduplicación por hash verificada en CI
- Web con 3 vistas: registro (feed), expediente (artículo+hash), perfil de medio
- Sistema de diseño propio: papel/tinta/resaltador/hilo rojo, tipografía Archivo
- Columnas reservadas para perfiles de medios (Fase 3)
- Sección temática extraída por URL (regla por medio); tipo (noticia/opinion/etc)
- **Extracción híbrida por bucket (NUEVO, esta sesión):** articleBody del JSON-LD
  con trafilatura de respaldo para El Tiempo/El Colombiano/El Espectador; solo
  trafilatura para Vorágine/Las2orillas. Config en outlets.extraccion.

**Estamos en la semana de observación de Fase 1** (criterio: 7 días verde, ≥150
artículos, 5 medios, cero duplicados, tipos correctos ≥80%).

**Lo último que hicimos (sesión 2026-06-14):** se diagnosticó articleBody en los 5
medios con datos reales, se decidió y construyó la extracción híbrida por bucket
(migración #6 + crawler v2), se añadió filtro de notas-video de El Tiempo, y se
midió la calidad del archivo guardado (boilerplate 0%, deuda menor identificada).
Cambios verificados (Vorágine/Las2orillas intactos, buckets OK, sintaxis OK) y
pusheados.

## PRÓXIMO PASO cuando retomemos

**Fase 2 — clustering / el hilo rojo conecta versiones del mismo hecho.**
La materia prima ya está más limpia (boilerplate 0%) tras la extracción híbrida.
Revisar BITACORA.md antes: hay deuda menor vigilada, ninguna bloqueante.

**Decisiones de Fase 2 pendientes de cerrar** (están en ARQUITECTURA.md):
- Umbral de similitud (hipótesis 0.62, calibrar con datos reales)
- Ventana temporal (±72h, revisar)
- Qué hacer con clústeres de tamaño 1
- Grafo de historias RELACIONADAS (idea de Jota): enlazar nota y su derivada/
  reacción entre clústeres. Implementar DESPUÉS de validar el clustering simple.

## Fase 2 NO obliga a reconstruir al agregar medios
El clustering opera sobre artículos, no sobre medios. Agregar un medio = config
nueva en outlets (feed + regla de sección + bucket de extracción), no toca el
clustering. Solo los umbrales se recalibran. **Al agregar un medio: diagnosticar
articleBody primero (script de la sesión 2026-06-14) y fijar su bucket explícito.**
Recomendación: validar clustering con 5 medios antes de expandir. Cola:
Colombia+20, La Silla Vacía, Semana, Caracol/W Radio, RTVC (medio público estatal).

## Cómo verificar el estado en cualquier momento
- Salud del archivo: contar artículos/tipos/secciones por medio en Supabase.
- Buckets de extracción: `select slug, extraccion from outlets order by slug;`
- Corridas del crawler: pestaña Actions del repo (deben estar en verde).
- La web: trama-co.vercel.app