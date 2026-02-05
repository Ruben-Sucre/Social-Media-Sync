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

### Desarrollo Local

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

### Despliegue en VM/Producción

Para despliegue en un servidor Linux limpio (Ubuntu/Debian), consulta la [Guía de Despliegue](DEPLOYMENT.md) que incluye:

1. **Provisión automática del sistema:**
   ```bash
   sudo bash provision.sh
   ```
   Instala Python 3, FFmpeg, Docker y Docker Compose.

2. **Orquestación con n8n:**

   Este repositorio no incluye `docker-compose.yml` por seguridad. Copia `docker-compose.yml.example` a `docker-compose.yml` y crea un archivo `.env` con las variables necesarias antes de ejecutar `docker-compose up -d`.

   Ejemplo:

   ```bash
   cp docker-compose.yml.example docker-compose.yml
   # editar .env según necesidades
   docker-compose up -d
   ```

   Levanta n8n para automatizar workflows de ingestión, edición y publicación.

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

## Pruebas

El proyecto cuenta con una suite de tests robusta que cubre los principales flujos de ingestión, edición y publicación de videos.

- Ejecuta todos los tests con:
	```bash
	pytest -v tests
	```
- Los tests utilizan `pytest` y `pytest-mock` para simular dependencias externas como MoviePy y YoutubeDL, permitiendo ejecuciones rápidas y deterministas.
- Se han implementado mocks y pruebas de excepciones para asegurar la robustez ante errores y casos límite.
- La integración continua (CI) ejecuta automáticamente los tests en cada push o pull request usando GitHub Actions.

## Limpieza y Mantenimiento

Antes de desplegar en producción o hacer commits importantes, limpia archivos temporales y de prueba:

```bash
bash cleanup.sh
```

Este script elimina:
- Videos de prueba en `videos/raw/` y `videos/processed/`
- Logs antiguos en `logs/`
- Cache de Python (`__pycache__`, archivos `.pyc`, `.pyo`)

**Nota:** El inventario de datos (`data/*.parquet`) se conserva por defecto. Descomenta la línea correspondiente en el script si deseas limpiar también el inventario.

## Manejo de Errores

El sistema implementa un manejo de errores centralizado y explícito:

- Todas las operaciones críticas (ingestión, edición, publicación) capturan y reportan excepciones personalizadas definidas en `scripts/exceptions.py`.
- Los errores se registran en logs y el inventario se actualiza con el estado correspondiente (`failed`, etc.), permitiendo trazabilidad y recuperación.
- Los tests incluyen casos de error para validar que el sistema responde correctamente ante fallos de red, archivos corruptos o dependencias externas.

Esto garantiza que el flujo de trabajo sea resiliente y fácil de depurar ante cualquier incidente.

## Notas de diseño

- El inventario se mantiene en `data/inventario_videos.parquet` y es el registro de verdad.
- Fechas y timestamps se manejan en UTC y las columnas `created_at` y `updated_at` tienen zona horaria explícita (`UTC`).
- Se usa `filelock` para evitar condiciones de carrera cuando varios procesos actualizan el inventario.

---

Para más detalles o integraciones (Playwright, pipelines CI/CD, despliegue), dime qué priorizar y lo abordamos por sprints.
