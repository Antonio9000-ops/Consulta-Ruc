# Consulta RUC — SUNAT (Python + Playwright)

Proyecto académico de validación y consulta de RUC en el portal *e-consultaruc* de SUNAT.

> **Estado actual:** Fases 0–2 completas. Validación del Excel lista; la consulta a SUNAT **no está implementada todavía** debido a desafíos anti-bot en el sitio. El usuario debe atender manualmente cualquier desafío de CAPTCHA/seguridad que aparezca.

## Requisitos

- Python 3.12 (probado con 3.12.13 en Arch Linux).
- `playwright` >=1.64.1 (descarga Chromium dentro del entorno virtual).

## Instalación

```bash
cd /home/Anthony/Proyecto/Automatizacion_Ruc
uv venv --python 3.12 .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Uso

### 1. Validar un Excel de entrada

Coloca el Excel en `data/input/rucs_a_consultar.xlsx` con una columna `RUC` (11 dígitos, como texto). Luego ejecuta:

```bash
.venv/bin/python -m src.main   # genera output/validacion_ruc.xlsx
```

**Resultado:** `output/validacion_ruc.xlsx` con hojas `Validos`, `Errores` y `Resumen`.

El script **no sobrescribe** un archivo existente; usa `--sobrescribir` si realmente deseas regenerar.

### 2. Validar y consultar RUCs en SUNAT

**⚠️ Importante:** El sitio SUNAT utiliza un control anti-bot de Cloudflare/Turnstile. Si aparece, el flujo espera a que una persona lo resuelva en la ventana visible del navegador o aborta si se ejecuta con `--headless`. No se intenta eludir ni automatizar el desafío.

Ejecuta (único RUC válido):

```bash
.venv/bin/python -m src.main --consultar --entrada data/input/rucs_a_consultar.xlsx --salida output/resultados_consulta_ruc.xlsx --limite 1
```

Parámetros:
- `--entrada` – ruta del Excel (por defecto: `data/input/rucs_a_consultar.xlsx`)
- `--salida` – ruta del reporte final (por defecto: `output/resultados_consulta_ruc.xlsx`)
- `--parcial` – historial de avance (`output/parcial_resultados.jsonl`)
- `--limite` – máximo de consultas por lote (1-20) – 1 es seguro para pruebas
- `--pausa` – segundos entre consultas (por defecto: 3 s)
- `--headless` – ejecuta sin navegador visible (no se puede atender el CAPTCHA)
- `--sobrescribir` – permite sobrescribir un reporte existente

El `--consultar` primero valida todos los RUCs (longitud, prefijo, dígito verificador, duplicados) y luego envía los RUCs válidos a SUNAT secuencialmente. El avance se guarda en `parciales.jsonl` para que puedas reanudar el lote más tarde.

### 3. Reanudar un lote interrumpido

Edita `--parcial` (por defecto: `output/parcial_resultados.jsonl`) o simplemente ejecuta el mismo comando `--consultar` de nuevo. El script omite los RUCs que ya están en el historial y continúa con los siguientes, respetando el límite y la pausa.

### 4. Modo solo validación (por defecto)

Si ejecutas `src.main` sin `--consultar`, solo validas y produces el libro de validación (el modo más rápido para verificar el formato del Excel).

## Estructura del proyecto

```text
├── src/
│   ├── validar.py           # Validación de RUC (longitud, prefijos SUNAT, dígito verificador)
│   ├── sunat.py             # Navegación y consulta a SUNAT (bloquea si aparece el desafío)
│   ├── extraer.py           # Normalización de etiquetas/valores devueltos por SUNAT
│   └── main.py              # CLI y orquestación del flujo
├── tests/                   # Pruebas unitarias sin conexión (52 tests)
├── docs/bitacora.md         # Registro de decisiones y pendientes
├── docs/informe.md          # Esqueleto del informe académico
├── .devcontainer/          # IDE remoto reproducible (Codespaces)
├── requirements.txt         # dependencias Python fijadas
└── pytest.ini              # configuración de pytest
```

## Evidencia de pruebas (línea de base)

```bash
.venv/bin/python -m pytest
# → 52 passed in 0.45s
```

## Informe actual (vacío — completado por el usuario)

El ``docs/informe.md`` actual es un esqueleto. Llénalo con:

- Caso de negocio ficticio
- Información del equipo (si corresponde)
- Diagrama del flujo
- Evidencias de cada consulta
- Conclusiones

## Próximos pasos recomendados

1. **Probar la validación**
   `python -m src.main --entrada data/input/rucs_a_consultar.xlsx`
   → espera el archivo `validacion_ruc.xlsx`.

2. **Probar una consulta manual con `--consultar`**
   Si la PC local tiene un navegador, puedes ejecutar con `--consultar --limite 1` y atender cualquier desafío si aparece.

3. **Reunir el registro del desafío**
   El proyecto captura capturas de pantalla y logs en `evidence/` cuando aparecen desafíos o errores; úsalos para el informe.

4. **Generar el informe final**
   Completa ``docs/informe.md`` con los datos reales de las consultas, las capturas de pantalla y el registro de decisiones de la bitácora.

## Licencia

Proyecto académico: no se requieren requisitos de licencia; usa responsibly.
