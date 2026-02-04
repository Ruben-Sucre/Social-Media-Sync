#!/usr/bin/env bash
#
# cleanup.sh - Script de limpieza pre-vuelo
# Limpia carpetas de trabajo antes del despliegue en producción
#
# Uso: bash cleanup.sh

set -euo pipefail

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Directorio raíz del proyecto
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_info "=========================================="
log_info "Social-Media-Sync - Cleanup Script"
log_info "=========================================="
log_info "Directorio del proyecto: $PROJECT_ROOT"
echo ""

# Función para limpiar un directorio
cleanup_dir() {
    local dir="$1"
    local pattern="$2"
    
    if [[ ! -d "$dir" ]]; then
        log_warn "Directorio no encontrado: $dir (se omite)"
        return 0
    fi
    
    local count=$(find "$dir" -type f -name "$pattern" 2>/dev/null | wc -l)
    
    if [[ $count -eq 0 ]]; then
        log_info "✓ $dir: Ya está limpio (0 archivos)"
    else
        log_info "Limpiando $dir ($count archivos)..."
        find "$dir" -type f -name "$pattern" -delete
        log_info "✓ $dir: Limpiado ($count archivos eliminados)"
    fi
}

# 1. Limpiar videos/raw/
log_info "Paso 1/5: Limpiando videos/raw/..."
cleanup_dir "$PROJECT_ROOT/videos/raw" "*"

# 2. Limpiar videos/processed/
log_info "Paso 2/5: Limpiando videos/processed/..."
cleanup_dir "$PROJECT_ROOT/videos/processed" "*"

# 3. Limpiar logs/
log_info "Paso 3/5: Limpiando logs/..."
cleanup_dir "$PROJECT_ROOT/logs" "*.log"

# 4. Limpiar archivos temporales de Python
log_info "Paso 4/5: Limpiando archivos temporales de Python..."
find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$PROJECT_ROOT" -type f -name "*.pyo" -delete 2>/dev/null || true
find "$PROJECT_ROOT" -type f -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
log_info "✓ Archivos temporales de Python eliminados"

# 5. Limpiar datos de inventario (opcional, comentado por seguridad)
# Descomenta la siguiente línea si quieres limpiar también el inventario de Polars
# cleanup_dir "$PROJECT_ROOT/data" "*.parquet"
log_info "Paso 5/5: Conservando datos de inventario (data/*.parquet)"
log_warn "Si deseas limpiar el inventario, descomenta la línea en el script"

echo ""
log_info "=========================================="
log_info "Limpieza completada exitosamente ✓"
log_info "=========================================="
log_info "El proyecto está listo para:"
echo "  • git add ."
echo "  • git commit -m 'chore: cleanup before production deployment'"
echo "  • git push origin main"
echo ""
log_warn "Recuerda: Los archivos en .gitignore no se commitearán automáticamente"
echo ""
