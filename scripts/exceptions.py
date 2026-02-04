"""
Módulo de excepciones personalizadas para Social-Media-Sync.
"""

class DownloadError(Exception):
    """Excepción para errores relacionados con la descarga de videos."""
    def __init__(self, message="Error durante la descarga del video."):
        super().__init__(message)


class InventoryUpdateError(Exception):
    """Excepción para errores al actualizar el inventario."""
    def __init__(self, message="Error al actualizar el inventario de videos."):
        super().__init__(message)


class VideoProcessingError(Exception):
    """Excepción para errores relacionados con el procesamiento de videos."""
    def __init__(self, message="Error durante el procesamiento del video."):
        super().__init__(message)