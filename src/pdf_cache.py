"""Generación bajo demanda y caché local de los PDF de historias clínicas.

Reutiliza el generador ya validado de la Fase 2
(src.pdf_render.generar_pdfs_de_paciente) sin modificarlo: los PDF de un
paciente se generan una sola vez en var/pdf_cache/<documento>/ y las
peticiones siguientes se sirven directamente desde disco.
"""
from __future__ import annotations

import shutil
import threading
from pathlib import Path

from src.web_utils import elegir_archivo_pdf

# Carpeta de caché, anclada a la raíz del proyecto (junto a src/), para no
# depender del directorio desde el que se lance el servidor.
CARPETA_CACHE = Path(__file__).resolve().parents[1] / "var" / "pdf_cache"

# La generación con Chromium es pesada; se serializa para evitar dos
# generaciones simultáneas del mismo paciente (uso local, un solo usuario).
_CANDADO = threading.Lock()


def limpiar_cache_paciente(documento: str) -> None:
    """Borra los PDF cacheados de un paciente para forzar su regeneración."""
    shutil.rmtree(CARPETA_CACHE / documento, ignore_errors=True)


def obtener_pdf_historia(conn, hc_completa, documento: str, historias: list,
                         indice: int, *, regenerar: bool = False) -> Path:
    """Devuelve la ruta del PDF correspondiente a historias[indice].

    Si los PDF del paciente no están en caché (o si regenerar=True), los
    genera con generar_pdfs_de_paciente y luego elige el archivo de la
    historia pedida.
    """
    # Import perezoso: requiere Playwright/Chromium, que solo hace falta al
    # generar; así las utilidades y las pruebas no lo necesitan instalado.
    from src.pdf_render import generar_pdfs_de_paciente

    carpeta = CARPETA_CACHE / documento
    with _CANDADO:
        if regenerar:
            shutil.rmtree(carpeta, ignore_errors=True)
        if not list(carpeta.glob("*.pdf")):
            carpeta.mkdir(parents=True, exist_ok=True)
            generar_pdfs_de_paciente(conn, hc_completa, str(carpeta))
        archivos = sorted(carpeta.glob("*.pdf"))
    if not archivos:
        raise RuntimeError("El generador no produjo ningún PDF para este paciente.")
    return elegir_archivo_pdf(archivos, historias[indice], indice, len(historias))
