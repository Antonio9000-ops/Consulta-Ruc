# Informe — Automatización de Consulta RUC (SUNAT)

> **Esqueleto.** Los marcadores `<!-- PENDIENTE: ... -->` indican datos que debe aportar el usuario o que dependen de fases aún no ejecutadas. No se inventan integrantes, certificaciones, capturas ni resultados.

## Portada

- Título: Automatización de consulta de RUC en el portal SUNAT
- Curso: <!-- PENDIENTE: nombre del curso -->
- Docente: <!-- PENDIENTE: nombre del docente -->
- Integrantes: <!-- PENDIENTE: nombres y códigos -->
- Institución y fecha: <!-- PENDIENTE -->

## 1. Objetivo

Validar y consultar de forma secuencial y trazable un lote de RUC en el portal *e-consultaruc* de SUNAT, conservando las etiquetas y valores exactos que publica el sitio, y dejando evidencia de cada etapa del proceso.

## 2. Caso de negocio (ficticio)

<!-- PENDIENTE: describir la empresa ficticia, el área solicitante y el volumen mensual de consultas. Debe quedar claro que los datos son ficticios. -->

## 3. Herramientas y justificación

| Herramienta | Versión | Uso |
| --- | --- | --- |
| Python | 3.12.13 | Lenguaje del proyecto |
| Playwright | 1.64.1 | Automatización del navegador Chromium |
| pandas | 3.1.0 | Lectura del Excel y armado de reportes |
| openpyxl | 3.1.5 | Escritura del libro de resultados |
| pytest | 9.2.0 | Pruebas unitarias |

Justificación: Playwright permite esperas explícitas sobre el DOM y maneja Chromium con la misma versión en local y en contenedor, lo que hace reproducible el entorno entre Arch Linux y GitHub Codespaces.

## 4. Diagrama del flujo

```text
Excel (columna RUC)
      │
      ▼
validar.py  ── longitud, prefijo, dígito verificador, duplicados
      │
      ▼
sunat.py    ── navegación secuencial + pausa + límite por lote
      │        (detiene el flujo ante CAPTCHA o bloqueo)
      ▼
extraer.py  ── etiquetas/valores exactos → registro normalizado
      │
      ▼
output/resultados_consulta_ruc.xlsx  (Resultados · Errores · Resumen)
```

## 5. Validación

- 11 dígitos numéricos, sin convertir a entero.
- Prefijos SUNAT admitidos: 10, 15, 17, 20.
- Dígito verificador: pesos `[5,4,3,2,7,6,5,4,3,2]`, módulo 11, complemento a 11.
- Duplicados detectados por fila; los errores no detienen el lote.
- Un RUC válido **no** implica que exista, esté activo o esté habido.

## 6. Método de consulta

<!-- PENDIENTE (Fase 3): describir el flujo real observado en SUNAT, con los
selectores y los nombres exactos de los campos. No completar por suposición. -->

**Estado actual:** Selectores verificados el 2026-11-01 manualmente con navegador visible:

- `#btnPorRuc` – pestaña **Por RUC**.
- `#txtRuc` – campo de entrada RUC.
- `#btnAceptar` – botón **Buscar**.
- `#imgCodigo` / `#txtCodigo` – campos de CAPTCHA (ocultos en este entorno).

Todo el flujo de consulta en `src/sunat.ConsultaSUNAT`:
- Detecta desafíos Cloudflare/Turnstile (`hay_desafio`) → espera a que una persona los resuelva (si `headless=False`) o aborta si se ejecuta con `--headless`.
- Si aparece un CAPTCHA visible (`captcha_visible`), se requiere que una persona lo resuelva mediante la interfaz `al_detectar_captcha`.
- Si el sitio devuelve un mensaje sin resultado (ejemplo: "no se ha encontrado resultados para el ruc ingresado"), se registra como `SIN RESULTADO`.
- Extrae etiquetas/valores usando `extraer_pares_dom` (blocks de Bootstrap, filas de tabla o pares etiqueta/valor).

## 7. CAPTCHA y límites de uso

- Si el sitio presenta CAPTCHA, el flujo automatizado se detiene y lo resuelve una persona, siempre que el sitio y el docente lo permitan.
- No se usan servicios externos de resolución de CAPTCHA.
- Consultas secuenciales, pausa configurable (3 s por defecto) y máximo 20 por lote.
- Ante bloqueo, limitación o cambio del sitio: se detiene la ejecución.

## 8. Pruebas

| Etapa | Estado |
| --- | --- |
| Pruebas unitarias sin conexión | **52 pruebas aprobadas** |
| Chromium en sitio neutro | Aprobado (`example.com`, Chromium 156.0.8078.4) |
| Inspección manual SUNAT | ✅ Completada (selectores de Fase 3) |
| 1 RUC autorizado | <!-- PENDIENTE: probar con RUC real si se desea --> |
| 2 RUC | <!-- PENDIENTE --> |
| 20 RUC | <!-- PENDIENTE: solo con autorización --> |

## 9. Control de calidad

- Coincidencia entre RUC de entrada y de salida.
- Detección de duplicados y de respuestas vacías o inesperadas.
- Fechas normalizadas a ISO; se conserva el valor original si el formato no corresponde, sin inventar datos.
- Comparación manual de al menos 3 registros contra SUNAT. <!-- PENDIENTE -->

## 10. Resultados

<!-- PENDIENTE (Fase 6): pegar el resumen real del libro de resultados. -->

## 11. Limitaciones

- La automatización depende de la estructura del portal SUNAT; un cambio de maquetación exige volver a inspeccionar el sitio.
- El CAPTCHA impide la ejecución desatendida.
- Codespaces es un entorno de desarrollo, no un servidor 24/7.
- Un dígito verificador correcto no garantiza la existencia del RUC.

## 12. Evidencias

<!-- PENDIENTE: capturas en evidence/screenshots/ y logs en evidence/logs/.
Sin datos personales ni CAPTCHA. -->

## 13. Conclusiones

<!-- PENDIENTE: redactar al cerrar las fases 3 a 7. -->