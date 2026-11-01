"""Pruebas sin conexión de las salvaguardas de navegación (src/sunat.py)."""

from __future__ import annotations

import pytest

from src.sunat import (
    SELECTORES,
    BloqueoSunat,
    ConfiguracionNavegacion,
    ConsultaSUNAT,
    FaseInspeccionPendiente,
    hay_desafio,
    hay_resultado,
    verificar_selectores_verificados,
)


class PaginaFalsa:
    """Sustituto mínimo de una página de Playwright."""

    def __init__(self, url: str = "", titulo: str = "", texto: str = ""):
        self.url = url
        self._titulo = titulo
        self._texto = texto

    def title(self) -> str:
        return self._titulo

    def inner_text(self, _selector: str) -> str:
        return self._texto


class TestDeteccionDeDesafio:
    def test_url_de_cloudflare_es_desafio(self):
        pagina = PaginaFalsa(url="https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g")
        assert hay_desafio(pagina)

    @pytest.mark.parametrize("titulo", ["Un momento…", "Just a moment...", "Checking your browser"])
    def test_titulo_de_desafio(self, titulo):
        assert hay_desafio(PaginaFalsa(titulo=titulo))

    def test_texto_de_verificacion_es_desafio(self):
        pagina = PaginaFalsa(texto="Verificación de seguridad en curso. Este sitio web utiliza un servicio...")
        assert hay_desafio(pagina)

    def test_pagina_normal_no_es_desafio(self):
        pagina = PaginaFalsa(titulo="SUNAT - Consulta Ruc", texto="Consulta RUC Por RUC Buscar")
        assert not hay_desafio(pagina)


class TestMensajeSinResultado:
    def test_detecta_mensaje_de_sin_resultado(self):
        assert not hay_resultado(PaginaFalsa(texto="no se ha encontrado resultados para el ruc ingresado"))
        assert not hay_resultado(PaginaFalsa(texto="no se ha encontrado resultados para el ruc ingresado"))
        assert hay_resultado(PaginaFalsa(texto="número de ruc: 20100013747 - biocón del perú s.a.c. estado del contribuyente: activo"))

    def test_pagina_con_resultado_no_es_sin_resultado(self):
        texto = "número de ruc: 20100013747 - biocón del perú s.a.c. estado del contribuyente: activo"
        assert hay_resultado(PaginaFalsa(texto=texto))


class TestSalvaguardas:
    def test_selectores_verificados_estan_completos(self):
        # Si esto falla, alguien vació un selector verificado contra el sitio real.
        assert SELECTORES["campo_ruc"] == "#txtRuc"
        assert SELECTORES["boton_buscar"] == "#btnAceptar"
        verificar_selectores_verificados()

    def test_limite_de_consultas_por_lote(self):
        config = ConfiguracionNavegacion(maximo_consultas=2)
        sesion = ConsultaSUNAT(config)
        sesion.consultas_realizadas = 2
        with pytest.raises(BloqueoSunat, match="Límite de 2"):
            sesion.consultar("20100013747")

    def test_sin_selectores_se_bloquea(self, monkeypatch):
        monkeypatch.setitem(SELECTORES, "campo_ruc", "")
        with pytest.raises(FaseInspeccionPendiente):
            verificar_selectores_verificados()

    def test_headless_por_defecto_es_falso(self):
        # La sección 5 pide inspección con navegador visible.
        assert ConfiguracionNavegacion().headless is False
