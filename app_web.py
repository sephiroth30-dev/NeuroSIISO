"""Interfaz web local para consultar historias clínicas del backup SIISO.

Permite buscar un paciente por número de documento, ver sus datos básicos y
la lista de sus historias clínicas, y mostrar el PDF reconstruido de la
historia elegida embebido en el navegador.

Reutiliza la capa de datos ya validada (src.db, src.service) y el generador
de PDF de la Fase 2 (src.pdf_render, a través de src.pdf_cache); aquí no hay
SQL nuevo y la base solo se lee.

Ejecución (desde la carpeta del proyecto, con el venv activo):

    py -m uvicorn app_web:app --host 127.0.0.1 --port 8000

Luego abrir http://127.0.0.1:8000 en el navegador.

Notas de seguridad:
- Servir únicamente en localhost (127.0.0.1); no exponer a la red.
- PENDIENTE (fase posterior): autenticación de usuarios y bitácora de accesos.
"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from src.db import get_connection
from src.pdf_cache import obtener_pdf_historia
from src.service import obtener_historia_completa
from src.web_utils import (campos_escalares, documento_valido,
                           listar_historias, tabla_historias)

RAIZ = Path(__file__).resolve().parent
plantillas = Jinja2Templates(directory=str(RAIZ / "templates" / "web"))

app = FastAPI(title="NeuroFic — Consulta de historias clínicas SIISO")

# Los manejadores son funciones síncronas a propósito: FastAPI las ejecuta en
# un hilo aparte, requisito del API síncrono de Playwright usado en pdf_render.


def _cargar_historia_completa(documento: str):
    """Consulta la historia completa del paciente.

    Devuelve (hc_completa, mensaje_error). Si ambos son None, el documento no
    existe en la base. ValueError/LookupError del servicio se interpretan como
    "no encontrado"; cualquier otra excepción, como error de base de datos.
    """
    try:
        with get_connection() as conn:
            hc = obtener_historia_completa(conn, documento)
    except (ValueError, LookupError):
        return None, None
    except Exception as exc:
        return None, f"Error consultando la base de datos: {exc}"
    if hc is None or getattr(hc, "paciente", None) is None:
        return None, None
    return hc, None


def _pagina_busqueda(request: Request, documento: str = "", error: str = ""):
    """Renderiza la página de búsqueda, opcionalmente con un mensaje de error."""
    return plantillas.TemplateResponse(
        request, "index.html", {"documento": documento, "error": error})


def _validar_y_cargar(request: Request, documento: str):
    """Valida el documento y carga la historia; devuelve (hc, respuesta_error)."""
    documento = (documento or "").strip()
    if not documento_valido(documento):
        return None, _pagina_busqueda(
            request, documento,
            "Ingrese un número de documento válido (solo letras y números).")
    hc, error = _cargar_historia_completa(documento)
    if error:
        return None, _pagina_busqueda(request, documento, error)
    if hc is None:
        return None, _pagina_busqueda(
            request, documento,
            f"No se encontró ningún paciente con documento {documento}.")
    return hc, None


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    """Página de inicio con el formulario de búsqueda por documento."""
    return _pagina_busqueda(request)


@app.get("/buscar", response_class=HTMLResponse)
def buscar(request: Request, documento: str = ""):
    """Busca un paciente por documento y muestra su ficha y sus historias."""
    documento = (documento or "").strip()
    hc, respuesta_error = _validar_y_cargar(request, documento)
    if respuesta_error is not None:
        return respuesta_error
    historias = listar_historias(hc)
    encabezados, filas = tabla_historias(historias)
    return plantillas.TemplateResponse(request, "paciente.html", {
        "documento": documento,
        "paciente": campos_escalares(hc.paciente),
        "total_historias": len(historias),
        "encabezados": encabezados,
        "filas": filas,
    })


@app.get("/historia/{documento}/{indice}", response_class=HTMLResponse)
def ver_historia(request: Request, documento: str, indice: int, regenerar: int = 0):
    """Genera (si hace falta) el PDF de una historia y lo muestra embebido."""
    hc, respuesta_error = _validar_y_cargar(request, documento)
    if respuesta_error is not None:
        return respuesta_error
    historias = listar_historias(hc)
    if not historias:
        return _pagina_busqueda(request, documento,
                                "El paciente no tiene historias clínicas registradas.")
    if not 0 <= indice < len(historias):
        return _pagina_busqueda(request, documento, "Historia clínica inexistente.")
    try:
        with get_connection() as conn:
            pdf = obtener_pdf_historia(conn, hc, documento, historias, indice,
                                       regenerar=bool(regenerar))
    except Exception as exc:
        return _pagina_busqueda(request, documento,
                                f"No fue posible generar el PDF: {exc}")
    return plantillas.TemplateResponse(request, "visor.html", {
        "documento": documento,
        "indice": indice,
        "numero": indice + 1,
        "total_historias": len(historias),
        "nombre_archivo": pdf.name,
    })


@app.get("/pdf/{documento}/{indice}")
def servir_pdf(request: Request, documento: str, indice: int):
    """Sirve el PDF de una historia para el visor embebido del navegador."""
    documento = (documento or "").strip()
    if not documento_valido(documento):
        return HTMLResponse("Documento inválido.", status_code=400)
    hc, error = _cargar_historia_completa(documento)
    if error or hc is None:
        return HTMLResponse(error or "Paciente no encontrado.", status_code=404)
    historias = listar_historias(hc)
    if not 0 <= indice < len(historias):
        return HTMLResponse("Historia clínica inexistente.", status_code=404)
    try:
        with get_connection() as conn:
            pdf = obtener_pdf_historia(conn, hc, documento, historias, indice)
    except Exception as exc:
        return HTMLResponse(f"No fue posible generar el PDF: {exc}", status_code=500)
    return FileResponse(
        pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{pdf.name}"'})
