"""Navegación y consulta en SUNAT (e-consultaruc).

Selectores verificados el 2026-11-01 contra el sitio real (abierto manualmente en navegador visible).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.extraer import (
    ResultadoRuc,
    construir_resultado,
    detectar_respuesta_sospechosa,
    extraer_pares_dom,
    campos_faltantes,
)

URL_FORMULARIO = (
    "https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp"
)

SELECTORES = {
    "formulario": "#form01",
    "pestana_ruc": "#btnPorRuc",
    "campo_ruc": "#txtRuc",
    "boton_buscar": "#btnAceptar",
    "captcha_imagen": "#imgCodigo",
    "captcha_entrada": "#txtCodigo",
    "captcha_refrescar": "#spanRefrescaCodigo",
}

PAUSA_ENTRE_CONSULTAS_SEG = 3.0
MAXIMO_CONSULTAS_POR_LOTE = 20
MAXIMO_REINTENTOS_TRANSITORIOS = 2
ESPERA_DESAFIO_SEG = 300
ESPERA_RESULTADO_MS = 45_000

MARCAS_DESAFIO = (
    "un momento",
    "verificación de seguridad en curso",
    "verificacion de seguridad en curso",
    "just a moment",
    "checking your browser",
)

MARCAS_SIN_RESULTADO = (
    "no se ha encontrado resultados para el ruc ingresado",
    "no se ha encontrado",
    "no se encontró",
    "no se encontro",
    "no existe",
    "no registra",
    "no figura",
    "no se encuentra en nuestros registros",
    "el número de ruc ingresado",
    "el numero de ruc ingresado",
    "ningún resultado",
    "sin resultado",
)

class FaseInspeccionPendiente(RuntimeError):
    pass

class CaptchaDetectado(RuntimeError):
    pass

class BloqueoSunat(RuntimeError):
    pass

class SinResultado(RuntimeError):
    pass

@dataclass
class ConfiguracionNavegacion:
    headless: bool = False
    pausa_segundos: float = PAUSA_ENTRE_CONSULTAS_SEG
    maximo_consultas: int = MAXIMO_CONSULTAS_POR_LOTE
    reintentos_transitorios: int = MAXIMO_REINTENTOS_TRANSITORIOS
    espera_desafio_segundos: int = ESPERA_DESAFIO_SEG
    perfil_navegador: Path = Path(".browser-profile")
    directorio_evidencias: Path = Path("evidence/screenshots")
    directorio_logs: Path = Path("evidence/logs")
    guardar_evidencia_en_error: bool = True

def verificar_selectores_verificados() -> None:
    faltantes = [c for c in ("campo_ruc", "boton_buscar") if not SELECTORES.get(c)]
    if faltantes:
        raise FaseInspeccionPendiente(
            "Selectores verificados de SUNAT faltantes: " + ", ".join(faltantes)
        )

def _texto_visible(pagina) -> str:
    try:
        return " ".join(pagina.inner_text("body").split()).lower()
    except Exception:
        return ""

def hay_desafio(pagina) -> bool:
    try:
        if "challenges.cloudflare.com" in pagina.url:
            return True
        titulo = (pagina.title() or "").lower()
        if any(m in titulo for m in MARCAS_DESAFIO):
            return True
        texto = _texto_visible(pagina)
        return any(m in texto for m in ("verificación de seguridad en curso", "verificacion de seguridad en curso"))
    except Exception:
        return False

def hay_resultado(pagina) -> bool:
    texto = _texto_visible(pagina)
    for marca in MARCAS_SIN_RESULTADO:
        if marca in texto:
            return False
    return True

def captcha_visible(pagina) -> bool:
    try:
        return pagina.locator(SELECTORES["captcha_entrada"]).is_visible()
    except Exception:
        return False

class ConsultaSUNAT:
    def __init__(self, config: ConfiguracionNavegacion | None = None):
        self.config = config or ConfiguracionNavegacion()
        self._pw = None
        self._contexto = None
        self._pagina = None
        self.consultas_realizadas = 0

    def __enter__(self) -> "ConsultaSUNAT":
        from playwright.sync_api import sync_playwright

        verificar_selectores_verificados()
        self.config.directorio_evidencias.mkdir(parents=True, exist_ok=True)
        self.config.directorio_logs.mkdir(parents=True, exist_ok=True)
        self.config.perfil_navegador.mkdir(parents=True, exist_ok=True)

        self._pw = sync_playwright().start()
        
        # --- Opción A: Usar el Chromium de Playwright (sin channel="chrome") ---
        self._contexto = self._pw.chromium.launch_persistent_context(
            str(self.config.perfil_navegador),
            headless=self.config.headless,
            ignore_default_args=["--enable-automation"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
            locale="es-PE",
            viewport={"width": 1360, "height": 900},
        )
        
        self._pagina = (
            self._contexto.pages[0] if self._contexto.pages else self._contexto.new_page()
        )
        self._pagina.set_default_timeout(ESPERA_RESULTADO_MS)
        self._abrir_formulario()
        return self

    def __exit__(self, *_excepcion) -> None:
        try:
            if self._contexto is not None:
                self._contexto.close()
        finally:
            if self._pw is not None:
                self._pw.stop()

    def _abrir_formulario(self) -> None:
        ultimo_error: Exception | None = None
        for intento in range(self.config.reintentos_transitorios + 1):
            try:
                self._pagina.goto(URL_FORMULARIO, wait_until="domcontentloaded")
                self._pagina.wait_for_timeout(3000)
                self._esperar_fin_desafio()
                self._pagina.wait_for_selector(SELECTORES["campo_ruc"], timeout=ESPERA_RESULTADO_MS)
                return
            except Exception as error:
                ultimo_error = error
                if intento < self.config.reintentos_transitorios:
                    try:
                        self._pagina.wait_for_timeout(2000)
                    except Exception:
                        break
        self._capturar_evidencia("error_formulario")
        raise BloqueoSunat(f"No se pudo abrir el formulario de SUNAT: {ultimo_error}")

    def _esperar_fin_desafio(self) -> None:
        if not hay_desafio(self._pagina):
            return
        if self.config.headless:
            self._capturar_evidencia("bloqueo_desafio")
            raise BloqueoSunat(
                "Cloudflare pide verificación y el navegador está en modo headless: "
                "no hay ventana para atenderla. Ejecuta sin --headless."
            )

        print(
            "\nAVISO: SUNAT/Cloudflare pide una verificación de seguridad (Check Humano).\n"
            "       Atiéndela en la ventana del navegador que se abrió.\n"
            f"       Se esperará hasta {self.config.espera_desafio_segundos} s.\n",
            flush=True,
        )
        inicio = time.time()
        while time.time() - inicio < self.config.espera_desafio_segundos:
            try:
                if self._pagina.is_closed():
                    raise BloqueoSunat("La ventana del navegador fue cerrada manualmente.")
                self._pagina.wait_for_timeout(2000)
            except Exception as e:
                raise BloqueoSunat(f"El navegador se cerró inesperadamente: {e}")
                
            if not hay_desafio(self._pagina):
                print("Verificación superada. Continuando...\n", flush=True)
                return
        self._capturar_evidencia("bloqueo_desafio")
        raise BloqueoSunat(
            "El desafío anti-bot no se resolvió en el tiempo de espera. "
            "No se reintenta ni se intenta eludir."
        )

    def consultar(
        self,
        ruc: str,
        al_detectar_captcha: Callable[[], str] | None = None,
    ) -> ResultadoRuc:
        if self.consultas_realizadas >= self.config.maximo_consultas:
            raise BloqueoSunat(
                f"Límite de {self.config.maximo_consultas} consultas por lote alcanzado."
            )

        try:
            self._esperar_fin_desafio()
            pagina = self._pagina
            pagina.goto(URL_FORMULARIO, wait_until="domcontentloaded")
            pagina.wait_for_selector(SELECTORES["campo_ruc"])

            pagina.fill(SELECTORES["campo_ruc"], ruc)
            pagina.click(SELECTORES["boton_buscar"])

            try:
                pagina.wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            self._esperar_fin_desafio()
            pagina.wait_for_timeout(1500)
            self.consultas_realizadas += 1
        except Exception as e:
            if "Target page, context or browser has been closed" in str(e):
                raise BloqueoSunat("El navegador fue cerrado antes de terminar la consulta.")
            raise e

        if captcha_visible(pagina):
            return self._resolver_captcha_manual(ruc, al_detectar_captcha)

        texto = _texto_visible(pagina)
        if hay_resultado(pagina):
            pares = extraer_pares_dom(pagina)
            if pares:
                return construir_resultado(ruc, pares)
            else:
                self._capturar_evidencia(f"sin_resultado_sin_campos_{ruc}")
                return ResultadoRuc(
                    ruc=ruc,
                    campos={},
                    fecha_consulta=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    observacion="SUNAT no devolvió campos (extracción vacía)",
                )
        else:
            self._capturar_evidencia(f"sin_resultado_detectado_{ruc}")
            return ResultadoRuc(
                ruc=ruc,
                campos={},
                fecha_consulta=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                observacion="SUNAT reportó que el RUC no tiene resultados",
            )

    def _resolver_captcha_manual(
        self, ruc: str, al_detectar_captcha: Callable[[], str] | None
    ) -> ResultadoRuc:
        if al_detectar_captcha is None:
            self._capturar_evidencia(f"captcha_{ruc}")
            raise CaptchaDetectado(
                "SUNAT pidió CAPTCHA. Se detiene el flujo: no se resuelve de forma "
                "automática ni con servicios externos."
            )
        codigo = al_detectar_captcha()
        self._pagina.fill(SELECTORES["captcha_entrada"], codigo)
        self._pagina.click(SELECTORES["boton_buscar"])
        self._pagina.wait_for_load_state("domcontentloaded")
        self._pagina.wait_for_timeout(1500)
        if captcha_visible(self._pagina):
            self._capturar_evidencia(f"captcha_incorrecto_{ruc}")
            raise CaptchaDetectado("CAPTCHA incorrecto: no se reintenta automáticamente.")
        return construir_resultado(ruc, extraer_pares_dom(self._pagina))

    def _capturar_evidencia(self, nombre: str) -> None:
        if not self.config.guardar_evidencia_en_error or self._pagina is None:
            return
        if self._pagina.is_closed():
            return
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{marca}_{nombre}"
        try:
            self.config.directorio_evidencias.mkdir(parents=True, exist_ok=True)
            self.config.directorio_logs.mkdir(parents=True, exist_ok=True)
            self._pagina.screenshot(path=str(self.config.directorio_evidencias / f"{base}.png"))
            with open(self.config.directorio_logs / f"{base}.log", "w", encoding="utf-8") as log:
                log.write(f"URL: {self._pagina.url}\nTÍTULO: {self._pagina.title()}\n\n")
                log.write(" ".join(self._pagina.inner_text("body").split())[:4000])
        except Exception:
            pass


def pausa_entre_consultas(config: ConfiguracionNavegacion) -> None:
    time.sleep(max(config.pausa_segundos, 0))
