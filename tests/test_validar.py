"""Pruebas unitarias sin conexión: validación de RUC y normalización de datos."""

from __future__ import annotations

import pytest

from src.extraer import (
    construir_resultado,
    detectar_respuesta_sospechosa,
    normalizar_fecha,
    normalizar_etiqueta,
    normalizar_valor,
    ruc_devuelto,
)
from src.validar import (
    calcular_digito_verificador,
    normalizar_ruc,
    validar_lote,
    validar_ruc,
)

# RUC públicos usados solo para comprobar el algoritmo del dígito verificador.
RUC_SUNAT = "20131312955"
RUC_EMPRESA_PUBLICA = "20100070970"
# RUC real aportado por el usuario como evidencia de la consulta (2026-11-01).
RUC_BIOCON = "20100013747"


class TestLongitudYCaracteres:
    def test_ruc_valido_es_aceptado(self):
        assert validar_ruc(RUC_SUNAT).valido

    def test_ruc_con_menos_de_11_digitos_es_rechazado(self):
        resultado = validar_ruc("2013131295")
        assert not resultado.valido
        assert "Longitud inválida" in resultado.motivo

    def test_ruc_con_mas_de_11_digitos_es_rechazado(self):
        assert not validar_ruc("201313129555").valido

    def test_ruc_con_letras_es_rechazado(self):
        resultado = validar_ruc("2013131295A")
        assert not resultado.valido
        assert "no numéricos" in resultado.motivo

    def test_ruc_vacio_es_rechazado(self):
        assert not validar_ruc("").valido
        assert not validar_ruc(None).valido

    @pytest.mark.parametrize("valor", ["20 131312955", "20131312955 ", "201-31312955"])
    def test_normalizacion_quita_espacios_y_guiones(self, valor):
        resultado = validar_ruc(valor)
        assert resultado.ruc == RUC_SUNAT
        assert resultado.valido

    def test_ruc_no_se_convierte_a_entero(self):
        # Un RUC que empieza con cero perdería el cero si se tratara como número.
        assert normalizar_ruc("02013131295") == "02013131295"


class TestDigitoVerificador:
    @pytest.mark.parametrize(
        ("ruc", "esperado"),
        [(RUC_SUNAT, 5), (RUC_EMPRESA_PUBLICA, 0)],
    )
    def test_digito_calculado_coincide_con_ruc_publico(self, ruc, esperado):
        assert calcular_digito_verificador(ruc[:10]) == esperado

    def test_digito_verificador_incorrecto_es_rechazado(self):
        alterado = RUC_SUNAT[:10] + "9"
        resultado = validar_ruc(alterado)
        assert not resultado.valido
        assert "Dígito verificador incorrecto" in resultado.motivo

    def test_digito_verificador_requiere_diez_digitos(self):
        with pytest.raises(ValueError):
            calcular_digito_verificador("201313129")
        with pytest.raises(ValueError):
            calcular_digito_verificador("20131312A5")

    def test_prefijo_invalido_es_rechazado(self):
        resultado = validar_ruc("99131312955")
        assert not resultado.valido
        assert "Prefijo" in resultado.motivo

    def test_prefijos_validos_reconocidos(self):
        for prefijo in ("10", "15", "17", "20"):
            base = prefijo + "131312955"[:8]
            digito = calcular_digito_verificador(base)
            resultado = validar_ruc(f"{base}{digito}")
            assert resultado.valido, f"prefijo {prefijo} debería ser aceptado: {resultado.motivo}"


class TestDuplicados:
    def test_duplicados_marcan_todas_las_apariciones(self):
        resultados, duplicados = validar_lote([RUC_SUNAT, RUC_EMPRESA_PUBLICA, RUC_SUNAT])
        assert duplicados == {RUC_SUNAT: [0, 2]}
        assert not resultados[0].valido
        assert resultados[1].valido
        assert not resultados[2].valido
        assert "duplicado" in resultados[0].motivo.lower()

    def test_sin_duplicados(self):
        _, duplicados = validar_lote([RUC_SUNAT, RUC_EMPRESA_PUBLICA])
        assert duplicados == {}

    def test_errores_por_fila_no_detienen_el_lote(self):
        resultados, _ = validar_lote(["abc", RUC_SUNAT, ""])
        assert [r.valido for r in resultados] == [False, True, False]


class TestExtraccion:
    def test_normalizar_etiqueta_quita_dos_puntos(self):
        assert normalizar_etiqueta("  Estado del   Contribuyente:  ") == "Estado del Contribuyente"

    def test_normalizar_valor_colapsa_espacios_y_saltos(self):
        assert normalizar_valor(" Lima\n  Cercado   de Lima ") == "Lima Cercado de Lima"

    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [("15/03/2019", "2019-03-15"), ("01/01/2020", "2020-01-01")],
    )
    def test_normalizar_fecha_a_iso(self, entrada, esperado):
        assert normalizar_fecha(entrada) == esperado

    def test_fecha_invalida_se_conserva_sin_inventar(self):
        assert normalizar_fecha("31/02/2020") == "31/02/2020"
        assert normalizar_fecha("NO DECLARADA") == "NO DECLARADA"

    def test_construir_resultado_conserva_etiquetas_exactas(self):
        # Datos reales observados en SUNAT (RUC 20100013747, consulta 2026-11-01).
        resultado = construir_resultado(
            RUC_BIOCON,
            {
                "Número de RUC": "20100013747 - BIOCON DEL PERU S.A.C.",
                "Tipo Contribuyente": "SOCIEDAD ANONIMA CERRADA",
                "Nombre Comercial": "BIOCONCOLORS",
                "Fecha de Inscripción": "09/10/1992",
                "Fecha de Inicio de Actividades": "20/07/1983",
                "Estado del Contribuyente": "ACTIVO",
                "Condición del Contribuyente": "HABIDO",
                "Domicilio Fiscal": "CAL.OMICRON NRO. 512 URB. PARQUE INTERNACIONAL",
            },
        )
        assert resultado.obtener("Estado del Contribuyente") == "ACTIVO"
        assert resultado.obtener("Condición del Contribuyente") == "HABIDO"
        assert resultado.obtener("Fecha de Inscripción") == "1992-10-09"
        assert resultado.obtener("Fecha de Inicio de Actividades") == "1983-07-20"
        assert resultado.obtener("Nombre Comercial") == "BIOCONCOLORS"
        assert not resultado.sin_resultado

    def test_estado_y_condicion_no_se_mezclan(self):
        resultado = construir_resultado(
            RUC_BIOCON,
            {
                "Número de RUC": f"{RUC_BIOCON} - BIOCON DEL PERU S.A.C.",
                "Estado del Contribuyente": "BAJA DEFINITIVA",
                "Condición del Contribuyente": "NO HABIDO",
            },
        )
        assert resultado.obtener("Estado del Contribuyente") == "BAJA DEFINITIVA"
        assert resultado.obtener("Condición del Contribuyente") == "NO HABIDO"
        assert resultado.obtener("Estado del Contribuyente") != resultado.obtener(
            "Condición del Contribuyente"
        )

    def test_valor_multilinea_se_unifica_sin_perder_texto(self):
        resultado = construir_resultado(
            RUC_BIOCON,
            {
                "Número de RUC": f"{RUC_BIOCON} - BIOCON DEL PERU S.A.C.",
                "Comprobantes de Pago c/aut. de impresión (F. 806 u 816)":
                    "FACTURA\nBOLETA DE VENTA\nLIQUIDACION DE COMPRA",
            },
        )
        valor = resultado.obtener("Comprobantes de Pago c/aut. de impresión (F. 806 u 816)")
        assert valor == "FACTURA BOLETA DE VENTA LIQUIDACION DE COMPRA"

    def test_ruc_de_salida_distinto_se_reporta(self):
        resultado = construir_resultado("20131312955", {"Número de RUC": "20100070970 - OTRA EMPRESA"})
        problemas = detectar_respuesta_sospechosa(resultado)
        assert any("no coincide" in p for p in problemas)

    def test_razon_social_quita_el_ruc_antepuesto(self):
        resultado = construir_resultado(
            RUC_SUNAT, {"Número de RUC": "20131312955 - SUPERINTENDENCIA NACIONAL DE ADUANAS"}
        )
        assert resultado.razon_social() == "SUPERINTENDENCIA NACIONAL DE ADUANAS"
        assert ruc_devuelto(resultado) == "20131312955"

    def test_respuesta_vacia_se_reporta(self):
        problemas = detectar_respuesta_sospechosa(construir_resultado(RUC_SUNAT, {}))
        assert any("ningún campo" in p for p in problemas)
