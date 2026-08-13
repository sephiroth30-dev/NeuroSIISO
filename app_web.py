"""Interfaz web local para consultar historias clínicas del backup SIISO.

Permite buscar un paciente por número de documento, ver sus datos básicos y
la lista de sus historias clínicas, y mostrar el PDF reconstruido de la
historia elegida embebido en el navegador.

Reutiliza la capa de datos ya validada (src.db, src.service) y el generador
de PDF de la Fase 2 (src.pdf_render, a través de src.pdf_cache); aquí no hay
SQL nuevo y la base solo se lee.

Ejecución:
- Solo este equipo:  iniciar_web.bat           (uvicorn en 127.0.0.1:8000)
- Intranet:          iniciar_web_intranet.bat  (uvicorn en 0.0.0.0:8000)

Luego abrir http://127.0.0.1:8000 (o la IP del equipo desde otra máquina).

Notas de seguridad (modo intranet SIN login, elegido por la IPS):
- La app NO pide contraseña: cualquier equipo de la red interna puede consultar
  cualquier paciente por documento. Usar solo en una red interna controlada.
- Toda consulta queda en una bitácora pasiva (var/bitacora/accesos-AAAA-MM.csv):
  fecha, IP del equipo, método, ruta y documento consultado. No la commitees:
  var/ está en .gitignore y la bitácora contiene identificadores de pacientes.
"""
import csv
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from src.db import get_connection
from src.pdf_cache import obtener_pdf_historia
from src.service import obtener_historia_completa
from src.web_utils import (campos_escalares, documento_de_solicitud,
                           documento_valido, linea_bitacora, listar_historias,
                           tabla_historias)

RAIZ = Path(__file__).resolve().parent
plantillas = Jinja2Templates(directory=str(RAIZ / "templates" / "web"))

app = FastAPI(title="NeuroFic — Consulta de historias clínicas SIISO")

# ------------------------------------------------------------- bitácora
# Registro pasivo de accesos (sin login). Sirve como rastro mínimo de quién
# (por IP) consultó a qué paciente. Vive en var/, que está en .gitignore.
BITACORA_DIR = RAIZ / "var" / "bitacora"
_BITACORA_ENCABEZADO = ["momento", "ip", "metodo", "ruta", "documento", "estado"]
_RUTAS_REGISTRABLES = ("/buscar", "/historia/", "/pdf/")
_bitacora_candado = threading.Lock()


def _registrar_bitacora(fila: list[str]) -> None:
    """Anexa una fila a la bitácora mensual de accesos (CSV en var/bitacora/)."""
    BITACORA_DIR.mkdir(parents=True, exist_ok=True)
    archivo = BITACORA_DIR / f"accesos-{datetime.now():%Y-%m}.csv"
    nuevo = not archivo.exists()
    with _bitacora_candado, archivo.open("a", newline="", encoding="utf-8") as fh:
        escritor = csv.writer(fh)
        if nuevo:
            escritor.writerow(_BITACORA_ENCABEZADO)
        escritor.writerow(fila)


@app.middleware("http")
async def bitacora_de_accesos(request: Request, call_next):
    """Registra cada consulta de paciente; nunca debe tumbar la respuesta."""
    respuesta = await call_next(request)
    ruta = request.url.path
    if ruta.startswith(_RUTAS_REGISTRABLES):
        documento = documento_de_solicitud(
            ruta, request.query_params.get("documento", ""))
        if documento:
            try:
                _registrar_bitacora(linea_bitacora(
                    f"{datetime.now():%Y-%m-%d %H:%M:%S}",
                    request.client.host if request.client else "",
                    request.method, ruta, documento, respuesta.status_code))
            except Exception:
                pass  # la bitácora es best-effort; no interrumpe el servicio
    return respuesta


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
