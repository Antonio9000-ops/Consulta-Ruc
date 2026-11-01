"""Pruebas sin conexión del armado del reporte final (src/main.py)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from src.main import (
    agregar_parcial,
    cargar_parcial,
    construir_libro_resultados,
    escribir_libro,
    fila_resultado,
)
from src.validar import validar_lote

RUC_BIOCON = "20100013747"
RUC_SUNAT = "20131312955"

CAMPOS_BIOCON = {
    "Número de RUC": f"{RUC_BIOCON} - BIOCON DEL PERU S.A.C.",
    "Tipo Contribuyente": "SOCIEDAD ANONIMA CERRADA",
    "Nombre Comercial": "BIOCONCOLORS",
    "Fecha de Inscripción": "1992-10-09",
    "Fecha de Inicio de Actividades": "1983-07-20",
    "Estado del Contribuyente": "ACTIVO",
    "Condición del Contribuyente": "HABIDO",
    "Domicilio Fiscal": "CAL.OMICRON NRO. 512 URB. PARQUE INTERNACIONAL",
}


@pytest.fixture
def parciales(tmp_path):
    ruta = tmp_path / "parcial.jsonl"
    agregar_parcial(
        ruta,
        _resultado(RUC_BIOCON, CAMPOS_BIOCON),
        "CONSULTADO",
    )
    return ruta


def _resultado(ruc, campos, observacion=""):
    from src.extraer import ResultadoRuc

    return ResultadoRuc(ruc=ruc, campos=campos, fecha_consulta="2026-11-01 01:15:00", observacion=observacion)


class TestParcial:
    def test_guardar_y_reanudar(self, parciales):
        hechos = cargar_parcial(parciales)
        assert list(hechos) == [RUC_BIOCON]
        assert hechos[RUC_BIOCON]["estado"] == "CONSULTADO"

    def test_archivo_inexistente_no_falla(self, tmp_path):
        assert cargar_parcial(tmp_path / "no_existe.jsonl") == {}

    def test_linea_corrupta_se_ignora(self, tmp_path):
        ruta = tmp_path / "parcial.jsonl"
        ruta.write_text("{esto no es json}\n", encoding="utf-8")
        agregar_parcial(ruta, _resultado(RUC_BIOCON, CAMPOS_BIOCON), "CONSULTADO")
        assert list(cargar_parcial(ruta)) == [RUC_BIOCON]

    def test_una_linea_por_ruc(self, parciales):
        lineas = parciales.read_text(encoding="utf-8").strip().splitlines()
        assert len(lineas) == 1
        assert json.loads(lineas[0])["ruc"] == RUC_BIOCON


class TestFilaResultado:
    def test_columnas_en_orden_y_sin_perder_datos(self):
        fila = fila_resultado(
            {"ruc": RUC_BIOCON, "campos": CAMPOS_BIOCON, "observacion": "", "estado": "CONSULTADO"}
        )
        assert fila["RUC"] == RUC_BIOCON
        assert fila["Estado del Contribuyente"] == "ACTIVO"
        assert fila["Condición del Contribuyente"] == "HABIDO"
        assert fila["Estado del proceso"] == "CONSULTADO"

    def test_etiqueta_desconocida_se_conserva(self):
        fila = fila_resultado(
            {
                "ruc": RUC_BIOCON,
                "campos": {"Número de RUC": RUC_BIOCON, "Etiqueta Nueva de SUNAT": "valor"},
                "observacion": "",
                "estado": "CONSULTADO",
            }
        )
        assert fila["Etiqueta Nueva de SUNAT"] == "valor"


class TestLibroResultados:
    def _hojas(self, rucs, parciales, errores=()):
        resultados, _ = validar_lote(rucs)
        return construir_libro_resultados([r for r in resultados if r.valido], parciales, list(errores), len(rucs))

    def test_hojas_requeridas(self, parciales):
        hojas = self._hojas([RUC_BIOCON], cargar_parcial(parciales))
        assert set(hojas) == {"Resultados", "Errores", "Resumen"}
        assert "RUC" in hojas["Resultados"].columns
        assert list(hojas["Errores"].columns) == ["RUC", "Etapa", "Motivo", "Fecha/hora"]

    def test_resumen_cuenta_sin_resultado_y_fallidos(self, parciales):
        hechos = cargar_parcial(parciales)
        hechos[RUC_SUNAT] = {
            "ruc": RUC_SUNAT,
            "campos": {},
            "observacion": "SUNAT no devolvió resultados para el RUC consultado",
            "estado": "SIN RESULTADO",
        }
        hojas = self._hojas([RUC_BIOCON, RUC_SUNAT], hechos)
        resumen = dict(zip(hojas["Resumen"]["Métrica"], hojas["Resumen"]["Valor"]))
        assert resumen["RUC consultados"] == 2
        assert resumen["Consultas exitosas"] == 1
        assert resumen["Consultas sin resultado"] == 1
        assert resumen["Consultas fallidas"] == 0

    def test_ruc_invalido_no_se_consulta(self, parciales):
        hojas = self._hojas(["123", RUC_BIOCON], cargar_parcial(parciales))
        resumen = dict(zip(hojas["Resumen"]["Métrica"], hojas["Resumen"]["Valor"]))
        assert resumen["RUC válidos"] == 1
        assert resumen["RUC inválidos (no consultados)"] == 1


class TestEscritura:
    def test_no_sobrescribe_sin_autorizacion(self, tmp_path):
        ruta = tmp_path / "salida.xlsx"
        hojas = {"Resumen": pd.DataFrame({"Métrica": ["a"], "Valor": [1]})}
        escribir_libro(hojas, ruta, sobrescribir=False)
        with pytest.raises(FileExistsError, match="ya existe"):
            escribir_libro(hojas, ruta, sobrescribir=False)

    def test_sobrescribe_con_autorizacion(self, tmp_path):
        ruta = tmp_path / "salida.xlsx"
        hojas = {"Resumen": pd.DataFrame({"Métrica": ["a"], "Valor": [1]})}
        escribir_libro(hojas, ruta, sobrescribir=False)
        escribir_libro(hojas, ruta, sobrescribir=True)
        assert pd.ExcelFile(ruta).sheet_names == ["Resumen"]
