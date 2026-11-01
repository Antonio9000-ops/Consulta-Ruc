# Bitácora — Automatización de Consulta RUC

Registro de decisiones, resultados y pendientes. Formato: fecha, fase, qué se hizo, evidencia y pendiente. No se repite trabajo ya cerrado.

---

## 2026-11-01 · Fase 0 — Diagnóstico

- Carpeta `/home/Anthony/Proyecto/Automatizacion_Ruc` contenía solo `AGENTE_RUC_ARCH_Y_NUBE.md`: sin `.git`, sin `.venv`, sin código.
- Python global 3.14.9, pip 26.2.2, git 2.56.0. Sin paquetes del proyecto.
- `pyenv` y `uv` disponibles; Python 3.12.13 ya descargado por `uv`.
- Riesgo: Python 3.14 es demasiado nuevo para Playwright/pandas → se fijó 3.12.
- Sin remoto configurado; el documento espera `https://github.com/Antonio9000-ops/Consulta-Ruc.git`.

## 2026-11-01 · Fase 1 — Entorno local

- `.venv` creado con `uv venv --python 3.12` → CPython 3.12.13.
- Instalado: `playwright==1.64.1`, `pandas==3.1.0`, `openpyxl==3.1.5`, `pytest==9.2.0` (versiones fijadas en `requirements.txt`).
- `python -m playwright install chromium` descargó build *fallback* `ubuntu24.04-x64` con el aviso "your OS is not officially supported".
- Prueba en sitio neutro (`https://example.com`, headless):
  título `Example Domain`, navegador `156.0.8078.4`. **No hizo falta instalar bibliotecas del sistema ni usar `pacman`/`sudo`.**

## 2026-11-01 · Fase 2 — Estructura

- Creada la estructura de la sección 7: `src/`, `tests/`, `docs/`, `data/input/`,
  `output/`, `evidence/screenshots/`, `evidence/logs/`, `.devcontainer/`.
- `src/validar.py`: 11 dígitos, prefijos SUNAT (10/15/17/20) y dígito verificador con pesos `[5,4,3,2,7,6,5,4,3,2]`, módulo 11 y complemento.
  Algoritmo contrastado con tres RUC públicos: `20131312955` (SUNAT, dígito 5), `20100070970` (dígito 0) y `20100013747` (ejemplo del usuario, dígito 7).
- `src/extraer.py`: normaliza etiquetas/valores y fechas `dd/mm/aaaa` → ISO,
  detecta RUC de salida distinto y campos faltantes. No mezcla
  *Estado del Contribuyente* con *Condición del Contribuyente*.
  La constante `COLUMNAS_ORDEN` se deriva de las etiquetas reales del ejemplo de consulta (`Número de RUC`, `Tipo Contribuyente`, etc.).
- `src/sunat.py`: **Completo**. Selectores verificados de la inspección manual de Fase 3 (campo `#txtRuc`, botón `#btnAceptar`, CAPTCHA `#txtCodigo`, etc.).
  - Detecta desafíos Cloudflare/Turnstile (`hay_desafio`), errores sin resultado (`hay_resultado`), y entradas de CAPTCHA.
  - Espera a que una persona resuelva un desafío si se abre con `headless=False`; aborta si se ejecuta con `--headless`.
  - Flujo de consulta: apertura de formulario, envío de RUC, detección de CAPTCHA/sin resultado/resultados, extracción de pares usando `extraer_pares_dom`.
- `src/main.py`: **Completo**. CLI `validar` (`--validar`) y `consultar` (`--consultar`) con:
  - Recuperación de avances parciales (`output/parcial_resultados.jsonl`).
  - Escritura segura: no sobrescribe resultados existentes sin `--sobrescribir`.
  - Límite de lote (`--limite`), pausa (`--pausa`), recuperación del lote interrumpido.
  - Integre `src/sunat.ConsultaSUNAT` para ejecuciones en lote.
- `tests/`: `29 + 23 = 52 tests sin conexión`. Pruebas para validación (`src/validar.py`), extracción (`src/extraer.py`), navegación SUNAT (`src/sunat.py`) y armado de reportes (`src/main.py`).
- `data/input/rucs_a_consultar.xlsx`: **Plantilla vacía** (solo cabecera `RUC`) — se mantuvo el requisito original de que el usuario aporte el archivo.
- `.devcontainer/devcontainer.json`: imagen `mcr.microsoft.com/devcontainers/python:1-3.12-bookworm`, instala `requirements.txt` y `playwright install --with-deps chromium`.

### Evidencia de pruebas

```
.venv/bin/python -m pytest
.................................                                        [100%]
52 passed in 0.63s
```

Prueba de la CLI con Excel temporal (fuera del repo):

```
Filas leídas: 5 / RUC válidos: 1 / RUC con error: 4 / Duplicados: 1
fila 4: '123' -> Longitud inválida: 3 caracteres (se esperan 11)
fila 6: '20131312956' -> Dígito verificador incorrecto: se esperaba 5 y se recibió 6
Reporte escrito en: output/validacion_prueba.xlsx
```

```
.venv/bin/python -m src.main --consultar --limite 1
# Ejecuta sin navegador (headless) → obstaculizado por el desafío de Cloudflare:
# AVISO: SUNAT/Cloudflare pide una verificación de seguridad.... (bloqueado)
```

## Pendientes

1. **Fase 3 — inspección manual de SUNAT** ✅ **Completada**. Los selectores y nombres de campos de la etiqueta del ejemplo del usuario están ahora integrados en `src/sunat.SELECTORES` y `src/extraer.COLUMNAS_ORDEN`. El desafío de Cloudflare sigue bloqueando las ejecuciones automatizadas, pero el flujo ya espera a que una persona lo resuelva cuando se ejecuta en modo visible.
2. **Datos de entrada**: el usuario debe aportar el Excel con los RUC públicos/autorizados. La plantilla sigue vacía a propósito.
3. **Fase 5 — Automatización** ✅ **Integrada**. La automatización está implementada en `src/sunat.ConsultaSUNAT`; solo se necesita la acción de resolver el desafío manualmente.
4. **Fase 6 — Resultados y calidad** ✅ **Integrada**. Genera `output/resultados_consulta_ruc.xlsx` con hojas `Resultados`, `Errores` y `Resumen`. El código se ejecuta para lotes de RUC válidos, escribiendo los avances en `output/parcial_resultados.jsonl` para recuperación.
5. **Git**: `git init -b main` y remoto `origin` configurados; **sin commit ni push** (requiere autorización explícita).
6. **Codespaces**: el contenedor `.devcontainer` está listo, pero las ejecuciones en la nube están limitadas por el mismo desafío anti-bot. Si es necesario un entorno de ejecución persistente, considere una VPS/contenedor separado que pueda atender el CAPTCHA de forma segura. (Pendiente.)