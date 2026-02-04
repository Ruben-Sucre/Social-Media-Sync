#!/usr/bin/env bash
#
# provision.sh - Sistema de aprovisionamiento para Social-Media-Sync
# Instala todas las dependencias del sistema necesarias en una VM Linux limpia
#
# Uso: sudo bash provision.sh

set -euo pipefail

echo "=========================================="
echo "Social-Media-Sync - Provision Script"
echo "=========================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar que se ejecuta como root
if [[ $EUID -ne 0 ]]; then
   log_error "Este script debe ejecutarse como root (usa sudo)"
   exit 1
fi

# 1. Actualizar índice de paquetes
log_info "Actualizando índice de paquetes del sistema..."
apt-get update -qq

# 2. Instalar Python 3 y herramientas básicas
log_info "Instalando Python 3 y herramientas de desarrollo..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    git \
    curl \
    wget \
    ca-certificates \
    gnupg \
    lsb-release

# Verificar Python instalado
PYTHON_VERSION=$(python3 --version)
log_info "Python instalado: $PYTHON_VERSION"

# 3. Instalar FFmpeg (crítico para MoviePy)
log_info "Instalando FFmpeg (requerido por MoviePy)..."
apt-get install -y ffmpeg

# Verificar FFmpeg instalado
FFMPEG_VERSION=$(ffmpeg -version | head -n1)
log_info "FFmpeg instalado: $FFMPEG_VERSION"

# 4. Instalar Docker
log_info "Instalando Docker..."

# Limpiar instalaciones previas de Docker
apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Agregar repositorio oficial de Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Actualizar e instalar Docker
apt-get update -qq
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Habilitar y arrancar Docker
systemctl enable docker
systemctl start docker

# Verificar Docker instalado
DOCKER_VERSION=$(docker --version)
log_info "Docker instalado: $DOCKER_VERSION"

# 5. Instalar Docker Compose (standalone, por compatibilidad)
log_info "Instalando Docker Compose standalone..."
DOCKER_COMPOSE_VERSION="v2.24.5"
curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Verificar Docker Compose instalado
COMPOSE_VERSION=$(docker-compose --version)
log_info "Docker Compose instalado: $COMPOSE_VERSION"

# 6. Configurar permisos Docker (opcional: agregar usuario al grupo docker)
if [[ -n "${SUDO_USER:-}" ]]; then
    log_info "Agregando usuario $SUDO_USER al grupo docker..."
    usermod -aG docker "$SUDO_USER"
    log_warn "El usuario $SUDO_USER debe cerrar sesión y volver a entrar para que los cambios surtan efecto"
fi

# 7. Verificar instalaciones
log_info "Verificando instalaciones..."
echo ""
echo "✓ Python:         $(python3 --version)"
echo "✓ pip:            $(pip3 --version)"
echo "✓ FFmpeg:         $(ffmpeg -version | head -n1 | cut -d' ' -f3)"
echo "✓ Docker:         $(docker --version | cut -d' ' -f3 | tr -d ',')"
echo "✓ Docker Compose: $(docker-compose --version | cut -d' ' -f4 | tr -d ',')"
echo ""

log_info "=========================================="
log_info "Provisión completada exitosamente ✓"
log_info "=========================================="
log_info "Próximos pasos:"
echo "  1. Clonar el repositorio: git clone <repo-url>"
echo "  2. Crear entorno virtual: python3 -m venv venv"
echo "  3. Activar entorno: source venv/bin/activate"
echo "  4. Instalar dependencias Python: pip install -r requirements.txt"
echo "  5. Levantar n8n: docker-compose up -d"
echo ""
