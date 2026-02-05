# Deployment Guide - Social-Media-Sync

Este documento describe el proceso de despliegue del proyecto Social-Media-Sync en una VM Linux limpia (Ubuntu/Debian).

## 📋 Requisitos Previos

- VM Linux (Ubuntu 20.04+ o Debian 11+)
- Acceso root o sudo
- Conexión a Internet

## 🚀 Pasos de Despliegue

### 1. Provisión del Sistema

Ejecutar el script de provisión como root para instalar todas las dependencias del sistema:

```bash
sudo bash provision.sh
```

Este script instala:
- Python 3 y herramientas de desarrollo
- FFmpeg (requerido por MoviePy)
- Docker y Docker Compose
- Dependencias del sistema

**Tiempo estimado:** 5-10 minutos

### 2. Configuración del Proyecto

```bash
# Clonar el repositorio
git clone <repository-url> social-media-sync
cd social-media-sync

# Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias Python
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Limpieza Pre-Producción

Antes del primer despliegue, limpiar archivos de desarrollo:

```bash
bash cleanup.sh
```

Este script elimina:
- Videos de prueba en `videos/raw/` y `videos/processed/`
- Logs antiguos en `logs/`
- Cache de Python (`__pycache__`, `.pyc`)

### 4. Configuración de Variables de Entorno

Crear archivo `.env` en la raíz del proyecto:

```bash
# .env
YOUTUBE_SOURCE_URL=https://www.youtube.com/@tu-canal
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=tu-password-seguro
```

### 5. Levantar n8n

Este repositorio no incluye `docker-compose.yml` por seguridad. Copia `docker-compose.yml.example` a `docker-compose.yml` en la raíz y configura tus secretos/variables en un archivo `.env` antes de levantar los servicios.

```bash
# Copiar plantilla a archivo activo (una sola vez)
cp docker-compose.yml.example docker-compose.yml
# Crear/editar .env y establecer N8N_BASIC_AUTH_PASSWORD, etc.
# Iniciar n8n en modo daemon
docker-compose up -d

# Verificar que n8n está corriendo
docker-compose ps
docker-compose logs -f n8n
```

**Acceso a n8n:**
- URL: `http://<vm-ip>:5678`
- Usuario: valor de `N8N_BASIC_AUTH_USER` en `.env`
- Password: valor de `N8N_BASIC_AUTH_PASSWORD` en `.env`

### 6. Configurar Workflows en n8n

1. Acceder a la interfaz web de n8n
2. Crear un nuevo workflow
3. Agregar nodos de ejecución:

**Ejemplo de Workflow - Ingestor Cron:**
```
Cron Node (cada hora)
  ↓
Execute Command Node:
  Command: /workspace/social-media-sync/venv/bin/python
  Arguments: /workspace/social-media-sync/scripts/ingestor.py
  Working Directory: /workspace/social-media-sync
```

**Ejemplo de Workflow - Editor + Publicador:**
```
Webhook Node (POST /process)
  ↓
Execute Command Node (Editor):
  Command: /workspace/social-media-sync/venv/bin/python
  Arguments: /workspace/social-media-sync/scripts/editor.py
  ↓
Execute Command Node (Publicador):
  Command: /workspace/social-media-sync/venv/bin/python
  Arguments: /workspace/social-media-sync/scripts/publicador.py
```

### Arranque automático con systemd

Para que la pila de n8n se levante automáticamente al arrancar la VM, crea el archivo de unidad systemd y actívalo. He incluido `systemd/social-media-sync.service` en el repositorio; en la VM copia y habilita el servicio con estos comandos:

```bash
sudo cp /workspaces/Social-Media-Sync/systemd/social-media-sync.service /etc/systemd/system/social-media-sync.service
sudo systemctl daemon-reload
sudo systemctl enable --now social-media-sync.service
```

Comprobar status y seguir logs:

```bash
sudo systemctl status social-media-sync.service
sudo journalctl -u social-media-sync.service -f
```

El servicio depende de `docker.service`, arranca la pila desde `/workspaces/Social-Media-Sync` y ejecuta `docker compose up -d` al inicio. Antes de habilitar el servicio, asegura que el archivo `.env` existe en la raíz del proyecto —puedes crear uno a partir del ejemplo incluido:

```bash
cp /workspaces/Social-Media-Sync/.env.example /workspaces/Social-Media-Sync/.env
# Edita /workspaces/Social-Media-Sync/.env para establecer una contraseña segura en N8N_BASIC_AUTH_PASSWORD
```

## 🔧 Troubleshooting

### Docker no arranca
```bash
sudo systemctl status docker
sudo systemctl restart docker
```

### n8n no responde
```bash
docker-compose logs n8n
docker-compose restart n8n
```

### FFmpeg no encontrado
```bash
which ffmpeg
# Si no existe, reinstalar:
sudo apt-get install -y ffmpeg
```

### Permisos de Docker
Si el usuario no puede ejecutar comandos Docker:
```bash
sudo usermod -aG docker $USER
# Cerrar sesión y volver a entrar
```

## 📊 Monitoreo

### Logs de n8n
```bash
docker-compose logs -f n8n
```

### Logs de la aplicación
```bash
tail -f logs/pipeline.log
```

### Estado de containers
```bash
docker-compose ps
docker stats
```

## 🛑 Detener Servicios

```bash
# Detener n8n
docker-compose down

# Detener y eliminar volúmenes (CUIDADO: elimina workflows)
docker-compose down -v
```

## 🔄 Actualización

```bash
# Actualizar código
git pull origin main

# Reinstalar dependencias si cambiaron
pip install -r requirements.txt

# Reiniciar n8n
docker-compose restart n8n
```

## 🔐 Seguridad

### Cambiar credenciales de n8n

Editar `docker-compose.yml`:
```yaml
environment:
  - N8N_BASIC_AUTH_USER=nuevo-usuario
  - N8N_BASIC_AUTH_PASSWORD=password-fuerte-aqui
```

Luego reiniciar:
```bash
docker-compose down
docker-compose up -d
```

### Firewall

Si usas UFW, permitir acceso a n8n:
```bash
sudo ufw allow 5678/tcp
sudo ufw enable
```

## 📁 Estructura de Directorios en Producción

```
/opt/social-media-sync/
├── venv/                   # Entorno virtual Python
├── scripts/                # Scripts principales
├── tests/                  # Tests (no se ejecutan en prod)
├── videos/
│   ├── raw/               # Videos descargados
│   └── processed/         # Videos procesados
├── logs/                   # Logs de la aplicación
├── data/                   # Inventario Polars
├── provision.sh           # Script de provisión
├── cleanup.sh             # Script de limpieza
├── docker-compose.yml     # Configuración n8n
├── requirements.txt       # Dependencias Python
└── .env                   # Variables de entorno

Docker Volumes:
└── social-media-sync-n8n-data/  # Datos persistentes de n8n
```

## ✅ Checklist de Despliegue

- [ ] Ejecutar `provision.sh` como root
- [ ] Clonar repositorio
- [ ] Crear entorno virtual
- [ ] Instalar dependencias Python
- [ ] Ejecutar `cleanup.sh`
- [ ] Crear archivo `.env`
- [ ] Levantar n8n con `docker-compose up -d`
- [ ] Acceder a interfaz de n8n
- [ ] Configurar workflows
- [ ] Probar ejecución manual
- [ ] Configurar cron/webhooks
- [ ] Verificar logs

## 📞 Soporte

Para problemas o preguntas:
- Revisar logs: `docker-compose logs n8n` y `tail -f logs/pipeline.log`
- Verificar tests: `pytest -v`
- Documentación n8n: https://docs.n8n.io/
