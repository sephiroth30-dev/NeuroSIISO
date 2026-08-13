"""Utilidades puras para la interfaz web de consulta de historias clínicas.

Este módulo no depende de la base de datos, de Playwright ni del resto del
proyecto, para poder probarlo de forma aislada (ver tests/test_interfaz_web.py).
"""
from __future__ import annotations

import dataclasses
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

# Documento: letras y números (algunos documentos traen letras, p. ej. CE o
# pasaportes), con punto o guion intermedios. Acota longitud y evita cualquier
# carácter peligroso porque el documento también nombra la carpeta de caché.
_PATRON_DOCUMENTO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,29}$")

# Tipos que se muestran tal cual en pantalla; lo demás (listas de diagnósticos,
# órdenes, firmas en bytes, dataclasses anidadas) no va en la ficha resumida.
_TIPOS_ESCALARES = (str, int, float, bool, Decimal, datetime, date)


def documento_valido(documento: str) -> bool:
    """Indica si el texto ingresado es un número de documento razonable."""
    return bool(documento) and _PATRON_DOCUMENTO.match(documento) is not None


def a_texto(valor) -> str:
    """Convierte un valor de la base a texto presentable en la interfaz."""
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def etiqueta(nombre_campo: str) -> str:
    """Convierte un nombre de campo (snake_case) en una etiqueta legible."""
    return nombre_campo.replace("_", " ").strip().capitalize()


def _pares_crudos(objeto) -> list[tuple[str, object]]:
    """Pares (nombre, valor) de un dataclass o de un objeto cualquiera."""
    if dataclasses.is_dataclass(objeto):
        return [(c.name, getattr(objeto, c.name)) for c in dataclasses.fields(objeto)]
    return [(n, v) for n, v in vars(objeto).items() if not n.startswith("_")]


def campos_escalares(objeto) -> list[tuple[str, str]]:
    """Pares (etiqueta, valor en texto) de los campos simples de un objeto.

    Omite colecciones, bytes y objetos anidados: la ficha muestra solo los
    datos básicos; el detalle completo está en el PDF.
    """
    pares = []
    for nombre, valor in _pares_crudos(objeto):
        if valor is None or isinstance(valor, _TIPOS_ESCALARES):
            pares.append((etiqueta(nombre), a_texto(valor)))
    return pares


def listar_historias(hc_completa) -> list:
    """Extrae la lista de historias de una HistoriaClinicaCompleta."""
    for nombre in ("historias", "historias_clinicas", "lista_historias"):
        valor = getattr(hc_completa, nombre, None)
        if isinstance(valor, (list, tuple)):
            return list(valor)
    return []


def tabla_historias(historias: list) -> tuple[list[str], list[list[str]]]:
    """Arma (encabezados, filas) para la tabla de historias del paciente.

    Las columnas salen de los campos escalares de la primera historia (todas
    son de la misma clase), de modo que fecha, servicio, profesional, etc.
    aparezcan sin depender de nombres de atributo concretos.
    """
    if not historias:
        return [], []
    nombres = [n for n, v in _pares_crudos(historias[0])
               if v is None or isinstance(v, _TIPOS_ESCALARES)]
    encabezados = [etiqueta(n) for n in nombres]
    filas = []
    for historia in historias:
        fila = []
        for nombre in nombres:
            valor = getattr(historia, nombre, None)
            fila.append(a_texto(valor) if valor is None or isinstance(valor, _TIPOS_ESCALARES) else "…")
        filas.append(fila)
    return encabezados, filas


def _ids_posibles(historia) -> list[str]:
    """Valores identificadores de la historia que podrían ir en el nombre del PDF."""
    valores = []
    for atributo in ("id", "historia_id", "historias_clinicas_id", "hc_id",
                     "numero", "consecutivo"):
        valor = getattr(historia, atributo, None)
        if valor not in (None, ""):
            valores.append(str(valor))
    return valores


def elegir_archivo_pdf(archivos: list[Path], historia, indice: int,
                       total_historias: int) -> Path:
    """Elige, entre los PDF generados de un paciente, el de la historia pedida.

    generar_pdfs_de_paciente produce un PDF por historia; aquí se asocia cada
    archivo con su historia. Estrategia, en orden:

    1. Un único archivo y una única historia → ese archivo.
    2. El nombre del archivo contiene el id de la historia (delimitado, para
       que el id 5 no coincida con "15").
    3. Tantos archivos como historias → emparejar por posición, con los
       archivos ordenados por nombre (se generan en el mismo orden de la lista).

    Si nada aplica, lanza RuntimeError indicando dónde ajustar.
    """
    archivos = sorted(archivos)
    if len(archivos) == 1 and total_historias == 1:
        return archivos[0]
    for valor in _ids_posibles(historia):
        patron = re.compile(rf"(?<![A-Za-z0-9]){re.escape(valor)}(?![A-Za-z0-9])")
        candidatos = [a for a in archivos if patron.search(a.stem)]
        if len(candidatos) == 1:
            return candidatos[0]
    if len(archivos) == total_historias:
        return archivos[indice]
    raise RuntimeError(
        "No fue posible asociar el PDF generado con la historia elegida. "
        "Ajuste elegir_archivo_pdf en src/web_utils.py según el nombre de "
        "archivo que produce generar_pdfs_de_paciente (src/pdf_render.py)."
    )


# ---------------------------------------------------------------- bitácora
def documento_de_solicitud(ruta: str, documento_query: str = "") -> str:
    """Extrae el documento consultado a partir de la ruta o del query string.

    Se usa para la bitácora de accesos. En /historia/<doc>/<i> y /pdf/<doc>/<i>
    el documento es el primer segmento tras el prefijo; en /buscar viene como
    parámetro 'documento'.
    """
    partes = [p for p in ruta.split("/") if p]
    if len(partes) >= 2 and partes[0] in ("historia", "pdf"):
        return partes[1]
    return (documento_query or "").strip()


def linea_bitacora(momento: str, ip: str, metodo: str, ruta: str,
                   documento: str, estado) -> list[str]:
    """Arma la fila (lista de campos) de un evento para la bitácora CSV."""
    return [momento, ip or "", metodo or "", ruta or "", documento or "",
            str(estado)]
