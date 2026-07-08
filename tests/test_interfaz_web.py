"""Pruebas de las utilidades puras de la interfaz web (src/web_utils.py).

No requieren base de datos, Playwright ni FastAPI.
"""
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.web_utils import (a_texto, campos_escalares, documento_valido,
                           elegir_archivo_pdf, etiqueta, listar_historias,
                           tabla_historias)


# ------------------------------------------------------------- documento
def test_documento_valido_acepta_cedulas_y_documentos_con_letras():
    assert documento_valido("29957147")
    assert documento_valido("CE12345")
    assert documento_valido("1.234.567")


def test_documento_valido_rechaza_vacios_y_caracteres_peligrosos():
    assert not documento_valido("")
    assert not documento_valido("   ")
    assert not documento_valido("../otro")
    assert not documento_valido("1; DROP TABLE Pacientes")
    assert not documento_valido("a" * 40)


# ------------------------------------------------------------- presentación
def test_a_texto_formatea_fechas_y_vacios():
    assert a_texto(None) == "—"
    assert a_texto("") == "—"
    assert a_texto(datetime(2025, 5, 2, 14, 30)) == "02/05/2025 14:30"
    assert a_texto(date(1941, 2, 3)) == "03/02/1941"
    assert a_texto(29957147) == "29957147"


def test_etiqueta_convierte_snake_case():
    assert etiqueta("fecha_nacimiento") == "Fecha nacimiento"


@dataclass
class PacienteFalso:
    nombres: str = "MARÍA"
    documento: str = "29957147"
    fecha_nacimiento: date = date(1941, 2, 3)
    telefono: str | None = None
    firma: bytes = b"\x00\x01"          # no debe mostrarse
    diagnosticos: list = field(default_factory=list)  # no debe mostrarse


def test_campos_escalares_omite_bytes_y_colecciones():
    pares = dict(campos_escalares(PacienteFalso()))
    assert pares["Nombres"] == "MARÍA"
    assert pares["Fecha nacimiento"] == "03/02/1941"
    assert pares["Telefono"] == "—"
    assert "Firma" not in pares
    assert "Diagnosticos" not in pares


@dataclass
class HistoriaFalsa:
    id: int
    fecha: datetime
    servicio: str
    ordenes: list = field(default_factory=list)


@dataclass
class HCCompletaFalsa:
    paciente: PacienteFalso
    historias: list


def test_listar_historias_encuentra_la_lista():
    hc = HCCompletaFalsa(PacienteFalso(), [HistoriaFalsa(1, datetime(2024, 1, 1), "Fisiatría")])
    assert len(listar_historias(hc)) == 1
    assert listar_historias(object()) == []


def test_tabla_historias_arma_encabezados_y_filas():
    historias = [
        HistoriaFalsa(1, datetime(2024, 1, 1, 8, 0), "Fisiatría"),
        HistoriaFalsa(2, datetime(2024, 3, 5, 9, 30), "Terapia física"),
    ]
    encabezados, filas = tabla_historias(historias)
    assert encabezados == ["Id", "Fecha", "Servicio"]
    assert filas[0] == ["1", "01/01/2024 08:00", "Fisiatría"]
    assert filas[1] == ["2", "05/03/2024 09:30", "Terapia física"]
    assert tabla_historias([]) == ([], [])


# ------------------------------------------------------------- elección de PDF
def _historia(hid):
    return HistoriaFalsa(hid, datetime(2024, 1, 1), "Fisiatría")


def test_elegir_pdf_unico_archivo_unica_historia():
    archivos = [Path("hc_29957147.pdf")]
    assert elegir_archivo_pdf(archivos, _historia(7), 0, 1) == archivos[0]


def test_elegir_pdf_por_id_en_el_nombre():
    archivos = [Path("historia_15.pdf"), Path("historia_5.pdf")]
    elegido = elegir_archivo_pdf(archivos, _historia(5), 0, 2)
    assert elegido == Path("historia_5.pdf")


def test_elegir_pdf_id_no_confunde_5_con_15():
    archivos = [Path("historia_15.pdf"), Path("historia_155.pdf")]
    # El id 15 solo debe coincidir con historia_15, no con historia_155.
    elegido = elegir_archivo_pdf(archivos, _historia(15), 0, 2)
    assert elegido == Path("historia_15.pdf")


def test_elegir_pdf_por_posicion_si_no_hay_id():
    archivos = [Path("hc_001.pdf"), Path("hc_002.pdf"), Path("hc_003.pdf")]
    historia = HistoriaFalsa(0, datetime(2024, 1, 1), "X")
    historia.id = None
    assert elegir_archivo_pdf(archivos, historia, 1, 3) == Path("hc_002.pdf")


def test_elegir_pdf_falla_con_mensaje_claro_si_no_puede_asociar():
    archivos = [Path("a.pdf"), Path("b.pdf")]
    historia = HistoriaFalsa(99, datetime(2024, 1, 1), "X")
    historia.id = None
    with pytest.raises(RuntimeError, match="web_utils"):
        elegir_archivo_pdf(archivos, historia, 0, 3)
