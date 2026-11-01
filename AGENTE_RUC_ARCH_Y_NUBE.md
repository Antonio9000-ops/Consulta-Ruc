# AGENTE.md — Automatización de Consulta RUC (Arch Linux + nube)

## Misión

Desarrollar un proyecto académico de consulta de RUC usando Python y Playwright. El código debe funcionar localmente en Arch Linux y poder ejecutarse después en GitHub Codespaces, sin depender de la PC del usuario.

**No programes contra supuestos:** inspecciona primero el sitio real de SUNAT y confirma selectores, flujo, CAPTCHA y campos de respuesta.

## 1. Datos fijos del proyecto

- PC local: Arch Linux x86_64, bash, X11/i3.
- CPU: Intel Core i3-6100; RAM: 8 GB (aprox. 7.65 GB utilizables).
- GPU: NVIDIA GeForce GT 740.
- Carpeta local: `/home/Anthony/Proyecto/Automatizacion_Ruc/`
- Repositorio: `https://github.com/Antonio9000-ops/Consulta-Ruc.git`
- Sitio SUNAT: `https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp`
- Idioma de respuestas y documentación: español.
- No cambies la ruta de trabajo ni crees copias del proyecto en otras carpetas.

## 2. Arquitectura objetivo: local + nube

Mantén **un solo repositorio Git** como fuente del proyecto.

1. **Local (Arch Linux):** desarrollo, inspección con navegador visible, depuración y pruebas unitarias.
2. **GitHub:** almacenamiento del código y sincronización mediante commits/push autorizados.
3. **GitHub Codespaces:** entorno Linux remoto para ejecutar el mismo proyecto cuando la PC no esté disponible.
4. **Futuro opcional:** si se necesita ejecución programada y permanente, evaluar un servidor/VPS o servicio de tareas. Codespaces es un entorno de desarrollo, no un servidor 24/7.

No mantengas dos versiones distintas del código. Usa configuración reproducible (`requirements.txt` o `pyproject.toml`) y `.devcontainer` para que local y Codespaces instalen las mismas dependencias de Python.

## 3. Reglas para ahorrar tokens y evitar daños

- Trabaja por fases; no repitas todo el plan en cada respuesta.
- Antes de actuar, inspecciona archivos y estado Git. No recrees lo que ya existe.
- Muestra solo resúmenes de comandos y errores relevantes; no imprimas HTML extenso ni archivos completos.
- No inventes selectores, RUC, datos, endpoints, cuotas ni resultados.
- No uses `sudo`, no instales paquetes, no borres ni sobrescribas archivos y no hagas commits/push sin autorización explícita.
- No ejecutes comandos destructivos (`rm -rf`, `git reset --hard`, `git clean`).
- Nunca solicites ni guardes contraseñas, tokens o credenciales en el repositorio.
- Mantén `README.md` conciso y `docs/bitacora.md` con decisiones, resultados y pendientes para no repetir trabajo.
- Si falta un dato imprescindible, haz una sola pregunta concreta. Si puedes avanzar sin riesgo, declara el supuesto.
- Al final de cada fase informa: resultado, archivos modificados, pruebas, pendientes y siguiente acción.

## 4. Límites de uso de SUNAT

- Consulta solo datos públicos y respeta las condiciones y controles del sitio.
- No evadas ni automatices el bypass de CAPTCHA, controles anti-bot, límites o bloqueos.
- Si aparece CAPTCHA, detén el flujo automatizado y solicita que el usuario lo resuelva manualmente, únicamente si el sitio y el docente permiten ese procedimiento.
- No uses servicios externos de resolución de CAPTCHA.
- Consultas secuenciales, con pausas prudentes y límite configurable; nunca paralelices el lote.
- Ante bloqueo, limitación o cambio del sitio, detén la ejecución. No intentes eludirlo.
- No recolectes ni guardes datos personales que no exija la consigna.

## 5. Fase 0 — Diagnóstico (primera tarea; no modificar nada)

Trabaja exclusivamente en la carpeta indicada:

```bash
cd /home/Anthony/Proyecto/Automatizacion_Ruc
pwd
git status --short --branch
git remote -v
find . -maxdepth 2 -type f -not -path './.git/*' | sort | head -80
python --version
python -m pip --version
git --version
```

Verifica si ya existe `.git`, rama, cambios locales y remoto. Si el remoto no coincide, informa; no lo reemplaces automáticamente. Si hay archivos, consérvalos. Resume el diagnóstico en máximo 10 líneas y espera aprobación antes de instalar o modificar.

## 6. Fase 1 — Entorno local Arch Linux

Usa entorno virtual Python. No instales paquetes globales:

```bash
cd /home/Anthony/Proyecto/Automatizacion_Ruc
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install playwright pandas openpyxl pytest
python -m playwright install chromium
```

Arch es rolling release; no presupongas que las instrucciones `--with-deps` de Playwright para Debian/Ubuntu funcionan en Arch. Si faltan bibliotecas, identifica el error y consulta paquetes de Arch; solicita autorización antes de usar `pacman`/`sudo`.

No mezcles sin necesidad `python-playwright` de pacman con `playwright` instalado por pip en el mismo entorno. Fija las versiones que realmente funcionen en `requirements.txt`.

Prueba Chromium primero con una página pública neutra. Para inspección, usa `headless=False`. No consumas consultas SUNAT durante esta prueba.

## 7. Fase 2 — Estructura del proyecto

Adapta la estructura a los archivos que ya existan; evita duplicados y carpetas vacías:

```text
.
├── README.md
├── AGENTE.md
├── requirements.txt
├── .gitignore
├── .devcontainer/
│   └── devcontainer.json
├── data/input/
│   └── rucs_a_consultar.xlsx
├── output/
├── evidence/
│   ├── screenshots/
│   └── logs/
├── src/
│   ├── validar.py
│   ├── sunat.py
│   ├── extraer.py
│   └── main.py
├── tests/
│   └── test_validar.py
└── docs/
    ├── bitacora.md
    └── informe.md
```

`.gitignore` debe excluir como mínimo `.venv/`, `__pycache__/`, `*.pyc`, `.env`, perfiles de navegador, archivos temporales y resultados/evidencias que contengan datos sensibles. No excluyas automáticamente entregables académicos no sensibles que el usuario quiera conservar en Git.

## 8. Fase 3 — Inspección real del sitio SUNAT

Antes de escribir el scraper:

1. Abre la URL oficial manualmente en el navegador local.
2. Inspecciona cómo se elige la consulta por RUC.
3. Identifica campo RUC, CAPTCHA (imagen y entrada, si existe), botón de consulta, contenedor de resultados y mensajes de error.
4. Anota selectores reales y evidencia mínima.
5. Haz una consulta manual autorizada y registra los nombres exactos de los campos.
6. No supongas que IDs como `txtRuc` o `btnAceptar` existen.
7. Si el sitio impide automatización o sus condiciones no permiten el método, detente y documenta la limitación.

No programes interacción con SUNAT hasta completar esta fase.

## 9. Fase 4 — Excel y validación

- Entrada: Excel con columna `RUC`.
- Leer con `dtype=str`; nunca convertir RUC a entero.
- Normalizar espacios exteriores.
- Validar 11 dígitos, unicidad y dígito verificador mediante algoritmo/fuente confiable comprobada.
- Un dígito verificador válido no demuestra que el RUC exista, esté activo o esté habido.
- No inventes los 20 RUC. El usuario debe aportar registros públicos/autorizados.
- Informar errores por fila y continuar con los registros válidos.
- Crear pruebas unitarias para longitud, caracteres, duplicados y dígito verificador.
- No reemplazar un Excel existente sin autorización.

## 10. Fase 5 — Automatización

Implementa solo con los selectores y flujo verificados.

- Python + Playwright; API síncrona si basta.
- Ejecución local inicial con `headless=False`.
- Código independiente para validación, navegación y extracción.
- Esperas explícitas y manejo de errores por etapa.
- Procesamiento secuencial, pausa configurable y límite de consultas.
- Reintentos limitados solo para fallos transitorios seguros; no reintentar CAPTCHA incorrecto, bloqueos ni límites.
- Ante CAPTCHA, intervención humana manual si está permitida.
- Captura de pantalla/log cuando ocurra un error o respuesta inesperada.
- No guardar CAPTCHA ni datos innecesarios.
- Usar selectores DOM robustos; evitar regex sobre texto completo si se pueden localizar etiquetas y contenedores.
- Cerrar página, contexto y navegador con `try/finally`.
- Guardar cada resultado de forma incremental y permitir reanudar sin repetir consultas completadas.
- No grabar video automáticamente; habilitarlo solo si se requiere evidencia y no expone información sensible.

Campos candidatos (solo los que realmente entregue SUNAT y requiera la consigna): RUC, razón social, estado del contribuyente, condición del domicilio fiscal, domicilio fiscal, fecha de inicio de actividades, fecha/hora de consulta y observación.

**No confundas estado del contribuyente con condición del domicilio fiscal.** Conserva las etiquetas y valores exactos de SUNAT; no reduzcas todo a HABIDO/NO HABIDO.

## 11. Fase 6 — Resultados y calidad

Genera `output/resultados_consulta_ruc.xlsx` con hojas:

- `Resultados`: una fila por RUC y estado del proceso.
- `Errores`: RUC, etapa, motivo y fecha/hora.
- `Resumen`: totales leídos, válidos, consultados, exitosos y fallidos.

Verifica coincidencia de RUC de entrada/salida, duplicados, formato de fechas y ausencia de errores disfrazados como datos. Compara manualmente al menos 3 registros con SUNAT. No declares exactitud total sin evidencia.

## 12. Fase 7 — Pruebas progresivas

Orden obligatorio:

1. Pruebas unitarias sin conexión.
2. Prueba Chromium en sitio neutro.
3. Inspección manual SUNAT.
4. Un RUC autorizado.
5. Comparación manual del resultado.
6. Dos RUC.
7. Veinte RUC solo con autorización del usuario y si SUNAT lo permite.

Solicita confirmación antes de consultas externas por lotes o de reemplazar resultados.

## 13. Fase 8 — Nube: GitHub Codespaces

El proyecto debe abrirse desde el mismo repositorio, no desde una copia manual.

1. Crear `.devcontainer/devcontainer.json` con una imagen Debian/Ubuntu compatible, versión Python fijada y comandos de instalación reproducibles.
2. Instalar dependencias Python desde `requirements.txt`.
3. Instalar Chromium y dependencias de sistema dentro del contenedor usando una imagen/entorno compatible con Playwright.
4. Fijar una versión de Playwright y mantener la misma versión de navegador en local y nube.
5. Probar primero tests unitarios y una página neutra.
6. Después de sincronizar el código a GitHub, crear Codespace desde `main` (o la rama acordada).
7. No guardar datos sensibles ni tokens en el repositorio; usar secretos de Codespaces solo si realmente hacen falta.
8. Configurar apagado por inactividad y detener el Codespace al terminar.
9. Comprobar cuota y facturación antes de usarlo. En cuentas personales GitHub Free, la documentación consultada indica una cuota incluida de 120 horas de cómputo al mes y 15 GB-mes de almacenamiento; la cuota y precios pueden cambiar. Revisar el panel de Billing antes de ejecutar.
10. No asumir que el Codespace estará activo permanentemente: puede detenerse por inactividad y consume cuota mientras se ejecuta.

**CAPTCHA en la nube:** `headless=False` no implica que veas una ventana en tu PC. Si se requiere interacción manual, diseña y prueba un mecanismo visible accesible desde el navegador del Codespace, por ejemplo escritorio remoto/noVNC con puerto reenviado, o pausa segura que permita aportar el código manualmente. No expongas puertos públicamente sin autenticación. Si no se puede atender el CAPTCHA de forma permitida y segura, la ejecución cloud no es viable mediante ese flujo; evalúa una API autorizada.

## 14. Fase 9 — ¿Codespaces o servidor permanente?

- Para desarrollo y ejecuciones manuales ocasionales: Codespaces es la primera opción.
- Para un proceso que debe ejecutarse a una hora aunque el usuario no abra el entorno: Codespaces no es la solución adecuada por sí solo.
- Para operación programada continua: evaluar VPS, contenedor en un servicio cloud o automatización CI, considerando costos, políticas del sitio, CAPTCHA y persistencia de archivos.
- GitHub Actions no debe usarse para intentar saltar CAPTCHA ni para consultas masivas. Solo considerar pruebas unitarias/CI y tareas permitidas.
- No contratar ni desplegar servicios sin aprobación explícita.

## 15. Fase 10 — API alternativa

Si scraping no es viable, investigar proveedores de API RUC en Perú. Verificar documentación, existencia, operación, campos, autenticación, límites, precio, privacidad y términos. No afirmar que es gratuita u oficial sin prueba. Pedir aprobación docente. Guardar credenciales fuera de Git. Mantener cliente API separado del scraper.

## 16. Fase 11 — Informe y evidencias

Crear `docs/informe.md` con: portada (marcadores para datos faltantes), objetivo, caso de negocio ficticio, herramientas y justificación, diagrama, validación, método de consulta, CAPTCHA, pruebas, control de calidad, resultados, limitaciones, evidencias y conclusiones.

No inventes integrantes, certificaciones, capturas ni resultados. Verifica certificaciones en páginas oficiales antes de citarlas. No incluyas datos privados en capturas o videos.

## 17. Git y seguridad

Antes de commit: revisar `git status` y `git diff`. Excluir `.env`, tokens, credenciales, perfiles de navegador, CAPTCHA y datos privados. No hagas commit/push sin autorización. No sobrescribas cambios ajenos.

## 18. Primera acción requerida

Comienza únicamente por la **Fase 0 (diagnóstico)**. No instales, edites, borres, hagas commit ni push. Inspecciona la carpeta, Git, remoto, rama, cambios locales, Python, pip y Git. Devuelve un resumen de máximo 10 líneas y espera autorización.

## Referencias oficiales

- Playwright Python: https://playwright.dev/python/docs/intro
- Playwright browsers/dependencies: https://playwright.dev/python/docs/browsers
- Playwright Docker y Codespaces/noVNC: https://playwright.dev/python/docs/docker
- GitHub Codespaces billing: https://docs.github.com/en/billing/concepts/product-billing/github-codespaces
- GitHub Codespaces: https://docs.github.com/en/codespaces
- SUNAT: https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp
