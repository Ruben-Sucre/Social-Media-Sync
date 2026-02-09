# Workflows n8n para Social-Media-Sync Pipeline

Este directorio contiene workflows de n8n para testing y producción del pipeline.

## ⭐ Workflows Disponibles

### 1. ingestor-production-click.json (Original)
**Status**: Legacy - Implementación básica

**Propósito**: Descargar video de TikTok y verificar registro en inventario

**Características**:
- Manual trigger
- Configuración de hashtag URL
- Logging básico de errores
- Verificación simple del inventario

**Uso**: Testing inicial y desarrollo

---

### 2. ingestor-production-robust.json ⭐ (Recomendado)
**Status**: Production-Ready (Opción B)

**Propósito**: Pipeline robusto con error handling y métricas

**Características**:
- ✅ **Error branching**: Rutas separadas para éxito/error
- ✅ **Status checking**: Nodo IF para validar ejecución
- ✅ **Structured logging**: Output en formato JSON
- ✅ **Métricas**: Success rate, duración, progreso
- ✅ **Alertas de error**: Mensajes formateados (listo para webhooks)
- ✅ **Observabilidad mejorada**: Contexto detallado de ejecución

**Nodos**:
1. **Manual Trigger** - Iniciar workflow manualmente
2. **Set Hashtag Config** - Configurar URL y max_videos
3. **Run Hashtag Ingestor** - Ejecutar ingestion con structured logging
4. **Check Status** - Nodo IF para rutear éxito vs error
5. **Verify Inventory** (ruta éxito) - Cargar y mostrar stats del inventario
6. **Format Error Alert** (ruta error) - Preparar notificación de error
7. **Error Note** - Nota con instrucciones para integración de webhooks

**Uso**: Deployment en producción con monitoreo
1. Manual Trigger - Ejecutar manualmente
2. Set TikTok URL - Define URL del video de TikTok (actualizar con URL real)
3. Run Ingestor - Ejecuta `scripts/ingestor.py` con la URL
4. Verify Inventory - Valida que el `video_id` fue registrado con `status_fb='pending'`

**Uso**:
- Importar workflow en n8n
- Actualizar URL de TikTok en el nodo "Set TikTok URL"
- Click en "Execute Workflow"
- Verificar output del nodo "Verify Inventory"

### 2. `editor-test.json` - Test de Editor
**Propósito**: Procesar videos pendientes y validar transformación

**Flujo**:
1. Manual Trigger
2. Check Inventory Before - Ver estado actual del inventario
3. Run Editor (process_pending) - Ejecuta `scripts/editor.py` para procesar videos con `status_fb='pending'`
4. Check Inventory After - Verificar transición a `status_fb='ready'`
5. Verify Processed Files - Listar archivos en `videos/processed/`

**Prerequisitos**: 
- Debe existir al menos un video con `status_fb='pending'` (ejecutar ingestor primero)

**Uso**:
- Ejecutar después de correr el workflow del ingestor
- Verificar que el video cambió de `pending` → `ready`
- Confirmar existencia del archivo en `videos/processed/`

### 3. `publicador-facebook-test.json` - Test de Publicador con Facebook
**Propósito**: Obtener video procesado y subirlo a Facebook

**Flujo**:
1. Manual Trigger
2. Get Next Video - Ejecuta `publicador.py --get-next` para obtener path del video con `status_fb='ready'`
3. Check If Video Available - Valida que hay video disponible
4. Parse Video Info - Extrae `video_id` y `video_path`
5. Upload to Facebook - Sube video a Facebook usando Graph API
6. Mark as Posted - Marca video como `posted` si éxito
7. Mark as Failed - Marca video como `failed` si error
8. Final Inventory Status - Muestra estado final del inventario

**Prerequisitos**:
- Debe existir video con `status_fb='ready'` (ejecutar editor primero)
- **Configurar credenciales de Facebook Graph API en n8n**:
  - Page ID
  - Access Token con permisos `pages_manage_posts`, `pages_read_engagement`
  
**Notas**:
- El nodo "Upload to Facebook" requiere configuración de credenciales
- Si el upload falla, el video se marca automáticamente como `failed`
- Usar el branch "No Videos Available" si no hay videos listos

### 4. `pipeline-completo.json` - Pipeline Integrado Completo
**Propósito**: Ejecutar pipeline completo TikTok → Editor → Facebook en una sola ejecución

**Flujo**:
1. Schedule Every 6 Hours (puede cambiarse a Manual Trigger para testing)
2. Set TikTok Source - URL del video o canal de TikTok
3. **Stage 1: Ingest Video** - Descarga video
4. Ingest Success? - Validación
5. Get Ingested Video Info - Obtiene detalles del `video_id`
6. **Stage 2: Process Video** - Transforma video (`pending` → `ready`)
7. Editor Success? - Validación
8. **Stage 3: Get Next Video** - Obtiene video procesado
9. Video Ready for Upload? - Validación
10. Parse Video Details - Extrae información
11. Upload to Facebook Page - Sube a Facebook
12. Mark as Posted/Failed - Actualiza estado según resultado
13. Final Status Report - Reporte completo con estadísticas

**Manejo de Errores**:
- Cada etapa tiene validación de exit code
- Branches de error para cada stage (Ingest Error, Editor Error, No Videos Ready)
- Marcado automático como `failed` en caso de error de upload

**Configuración**:
- Cambiar Schedule Trigger a Manual Trigger para pruebas
- Actualizar URL de TikTok en "Set TikTok Source"
- Configurar credenciales de Facebook Graph API
- Ajustar schedule (cron: `0 */6 * * *` = cada 6 horas)

## Script Helper: `inventory_stats.py`

Todos los workflows usan este script para consultar el estado del inventario.

**Uso CLI**:
```bash
# Ver estadísticas completas
python3 scripts/inventory_stats.py --json --pretty

# Ver solo último video
python3 scripts/inventory_stats.py --last-video

# Output formato JSON compacto
python3 scripts/inventory_stats.py
```

**Output Ejemplo**:
```json
{
  "total": 5,
  "by_status": {
    "pending": 1,
    "ready": 2,
    "posted": 1,
    "failed": 1
  },
  "last_video": {
    "video_id": "7123456789",
    "source_url": "https://www.tiktok.com/...",
    "title": "Video Title",
    "status_fb": "ready",
    "created_at": "2026-02-05T12:00:00Z",
    "updated_at": "2026-02-05T12:05:00Z"
  }
}
```

## Orden Recomendado de Testing

### Testing por Partes (Desarrollo)
1. **Test Ingestor**: Ejecutar `ingestor-production-click.json`
   - Verificar descarga exitosa
   - Confirmar entrada en inventario con `status_fb='pending'`
   - Verificar `video_id` único

2. **Test Editor**: Ejecutar `editor-test.json`
   - Confirmar transición `pending` → `ready`
   - Verificar archivo en `videos/processed/`
   - Validar transformaciones aplicadas

3. **Test Publicador**: Ejecutar `publicador-facebook-test.json`
   - Confirmar lectura de video `ready`
   - Probar upload a Facebook (requiere credenciales)
   - Verificar transición `ready` → `posted` o `failed`

### Testing Integrado (Pre-producción)
4. **Pipeline Completo**: Ejecutar `pipeline-completo.json`
   - Validar flujo completo end-to-end
   - Verificar manejo de errores en cada etapa
   - Confirmar estadísticas finales correctas

## Configuración de Credenciales de Facebook

Para los workflows que usan Facebook Graph API:

1. **Crear App de Facebook**:
   - Ir a https://developers.facebook.com/apps
   - Crear app con caso de uso "Business"
   - Agregar producto "Facebook Login"

2. **Obtener Access Token**:
   - Graph API Explorer: https://developers.facebook.com/tools/explorer
   - Permisos requeridos:
     - `pages_show_list`
     - `pages_manage_posts`
     - `pages_read_engagement`
   - Generar token de larga duración

3. **Obtener Page ID**:
   ```bash
   curl "https://graph.facebook.com/v18.0/me/accounts?access_token=YOUR_TOKEN"
   ```

4. **Configurar en n8n**:
   - Settings → Credentials → Add Credential
   - Buscar "Facebook Graph API"
   - Ingresar Access Token y Page ID
   - Nombrar como "Facebook Graph API Account"

## Monitoreo y Debugging

### Ver estado del inventario en cualquier momento:
```bash
python3 scripts/inventory_stats.py --pretty
```

### Inspeccionar logs del pipeline:
```bash
tail -f logs/pipeline.log
```

### Listar videos descargados:
```bash
ls -lh videos/raw/
```

### Listar videos procesados:
```bash
ls -lh videos/processed/
```

### Consultar inventario con Polars (Python):
```python
import polars as pl
df = pl.read_parquet('data/inventario_videos.parquet')
print(df)
print(df.group_by('status_fb').count())
```

## Troubleshooting

### Problema: "No videos ready for publishing"
**Solución**: Ejecutar editor-test.json primero para procesar videos pending

### Problema: "Inventory file not found"
**Solución**: 
```bash
python3 -c "from scripts.common import ensure_inventory; ensure_inventory()"
```

### Problema: "Facebook upload failed"
**Solución**: 
- Verificar credenciales de Facebook
- Confirmar permisos del access token
- Revisar que el archivo existe en disco
- Verificar tamaño y formato del video

### Problema: "Video already exists"
**Solución**: Normal, el sistema previene duplicados usando `video_id` como hash único

### Problema: "Editor no procesa videos"
**Solución**: 
- Verificar que hay videos con `status_fb='pending'`
- Confirmar que MoviePy está instalado: `pip install moviepy`
- Revisar logs en `logs/pipeline.log`

## Variables de Entorno para Testing

Para acelerar las pruebas (deshabilitar waits):
```bash
export SKIP_WAITS=1
```

## Producción

Para desplegar en producción:

1. Cambiar Schedule Trigger en `pipeline-completo.json` a tu frecuencia deseada
2. Actualizar URLs de TikTok con canales reales o sistema de discovery
3. Configurar credenciales de Facebook Graph API
4. Activar workflow: cambiar `"active": false` → `"active": true`
5. Monitorear ejecuciones en n8n dashboard
6. Configurar alertas para errores (opcional: agregar nodo Slack/Email en branches de error)

## Notas Importantes

- ⚠️ **El `video_id` es el hash único** generado por yt-dlp para prevenir duplicados
- ⚠️ **Todos los timestamps usan UTC** (configurado en `scripts/common.py`)
- ⚠️ **FileLock previene race conditions** en escritura concurrente al inventario
- ⚠️ **Videos missing se marcan automáticamente como `failed`** (ver `publicador.py`)
- ⚠️ **Cambiar URL de TikTok de ejemplo** antes de ejecutar workflows
