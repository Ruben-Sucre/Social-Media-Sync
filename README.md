# Social-Media-Sync

Sistema de sincronización y edición aleatoria de video (ingestión → edición → publicación).

## Descripción

Social-Media-Sync es un conjunto de utilidades y scripts para:
- descubrir/ingestar videos usando `yt-dlp` y registrar metadatos en un inventario Parquet,
- aplicar transformaciones aleatorias y ligeras (zoom, espejo, color, velocidad) para generar contenido único con MoviePy,
- exponer utilidades para integración con orquestadores (por ejemplo `n8n`) para publicar y marcar videos.

El proyecto está optimizado para `polars-lts-cpu` y maneja timestamps en UTC para compatibilidad y reproducibilidad.

## Tecnologías

- polars-lts-cpu (manipulación rápida de DataFrames y Parquet)
- MoviePy 2.x (edición de video)
- yt-dlp (descarga de video)
- filelock (bloqueo simple para concurrencia) 

## Instalación

1. Crear y activar un entorno virtual:

```bash
python -m venv .venv
. .venv/bin/activate
```

2. Instalar dependencias de desarrollo (incluye dependencias de producción):

```bash
pip install -r requirements-dev.txt
```

Nota: Asegúrate de tener `ffmpeg` disponible en la máquina si ejecutas MoviePy contra videos reales.

## Uso

- Ingestor: descargar e ingestar un video (agrega `status_fb = 'pending'`):

```bash
python -m scripts.ingestor "<source_url>"
```

- Editor: procesa el primer video `pending` y lo transforma/ejecuta export:

```bash
python -m scripts.editor
```

- Publicador (CLI): obtener el siguiente procesado, marcar un video como publicado o como fallido:

```bash
python -m scripts.publicador --get-next
python -m scripts.publicador --mark-posted <VIDEO_ID>
python -m scripts.publicador --mark-failed <VIDEO_ID>  # Marca videos fallidos durante la subida externa (n8n).
```

## Tests

Ejecuta la suite de tests con:

```bash
pytest -v tests
```

Los tests usan `pytest` y `pytest-mock` y simulan MoviePy para ejecuciones rápidas y deterministas.

## Notas de diseño

- El inventario se mantiene en `data/inventario_videos.parquet` y es el registro de verdad.
- Fechas y timestamps se manejan en UTC y las columnas `created_at` y `updated_at` tienen zona horaria explícita (`UTC`).
- Se usa `filelock` para evitar condiciones de carrera cuando varios procesos actualizan el inventario.

---

Para más detalles o integraciones (Playwright, pipelines CI/CD, despliegue), dime qué priorizar y lo abordamos por sprints.
