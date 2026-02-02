# Social-Media-Sync (TikTok -> FB pipeline)

Estructura inicial del pipeline y pasos para implementarlo incrementalmente.

## Estructura del proyecto

- data/
  - inventario_videos.parquet  # Base de verdad (inventory)
- videos/
  - raw/                       # Descargas crudas
  - processed/                 # Editados / listos para subir
- logs/
  - pipeline.log               # Registros del pipeline
- scripts/
  - common.py                  # Configuración y utilidades comunes
  - ingestor.py                # Descarga e ingestión (yt-dlp)
  - editor.py                  # Hook que prepara archivos para publicación
  - publicador.py              # CLI para integrarlo con n8n
- requirements.txt             # Dependencias básicas

---

## Plan de trabajo (paso a paso) ✅

1. Configuración común (ya implementado)
   - `scripts/common.py` expone rutas relativas (portable), manejo básico de
     inventario y un logger central que escribe en consola y `logs/pipeline.log`.

2. Ingestor (mínimo viable)
   - `scripts/ingestor.py` contiene stubs para `obtener_tendencias` y realiza
     descargas con `yt-dlp` en `videos/raw/`. Registra metadatos en el
     inventario con `status_fb = 'pending'`.
   - Usar `scan_parquet` (lazy) para verificaciones de duplicados antes de
     agregar entradas.

3. Editor / Hook (mínimo viable)
   - `scripts/editor.py` busca ítems `pending` que tienen archivos en `videos/raw/`,
     los mueve a `videos/processed/` y actualiza `path_local` en el inventario.
   - `TODO` marcado donde irá la lógica de MoviePy (recorte, reescalado, watermark).

4. Publicador
   - `scripts/publicador.py` ofrece CLI: `--get-next` (imprime la ruta) y
     `--mark-posted VIDEO_ID` (marca `status_fb = 'posted'`).

5. Archivos de soporte
   - `.gitignore` actualizado para excluir blobs grandes (`videos/**`),
     `data/*.parquet` y `logs/**` manteniendo `.gitkeep` para estructura.
   - `requirements.txt` mínimo con `polars` y `yt-dlp` (nota sobre `pathlib`).

---

## Próximos pasos sugeridos (priorizados)

1. Escribir tests unitarios para `common._append_to_inventory` y `find_next_processed_pending`.
2. Implementar la recolección real de URLs (Playwright) en `ingestor.obtener_tendencias`.
3. Añadir la edición con MoviePy en `editor.process_pending` y tests que verifiquen
   la duración / resolución.
4. Crear un flujo n8n que use `publicador --get-next` y `publicador --mark-posted`.

---

Si quieres, puedo seguir y:
- Añadir tests y GitHub Actions para CI ✅
- Implementar la integración Playwright + descargar lots de URLs ✅
- Añadir una pequeña CLI al `ingestor` para ejecutar por hashtag/playlist

Dime qué quieres priorizar y lo vamos avanzando por sprints pequeños.
