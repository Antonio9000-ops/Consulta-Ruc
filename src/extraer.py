"""Extracción y normalización de los datos devueltos por SUNAT.

La parte frágil (el DOM) se resuelve en :func:`extraer_pares_dom`, que prueba
varias estructuras en orden y devuelve pares etiqueta/valor. Todo lo demás es
lógica verificable con pruebas unitarias.

Las etiquetas se conservan tal como las entrega SUNAT. En particular no se
debe confundir "Estado del Contribuyente" con "Condición del Contribuyente"
ni con "Condición del Domicilio Fiscal" (sección 10 del documento).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

# Orden de columnas del reporte. Son etiquetas observadas en SUNAT; si el sitio
# entrega etiquetas nuevas se agregan al final sin perder información.
COLUMNAS_ORDEN: tuple[str, ...] = (
    "Número de RUC",
    "Tipo Contribuyente",
    "Nombre Comercial",
    "Fecha de Inscripción",
    "Fecha de Inicio de Actividades",
    "Estado del Contribuyente",
    "Condición del Contribuyente",
    "Condición del Domicilio Fiscal",
    "Domicilio Fiscal",
    "Sistema Emisión de Comprobante",
    "Actividad Comercio Exterior",
    "Sistema Contabilidad",
    "Actividad(es) Económica(s)",
    "Comprobantes de Pago c/aut. de impresión (F. 806 u 816)",
    "Sistema de Emisión Electrónica",
    "Emisor electrónico desde",
    "Comprobantes Electrónicos",
    "Afiliado al PLE desde",
    "Padrones",
    "Fecha consulta",
)

# Campos mínimos para considerar que la respuesta es un resultado real.
CAMPOS_CLAVE: tuple[str, ...] = ("Número de RUC", "Estado del Contribuyente")

_ESPACIOS = re.compile(r"\s+")
_FORMATO_FECHA_SUNAT = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


@dataclass
class ResultadoRuc:
    """Un registro consultado, con las etiquetas exactas de SUNAT."""

    ruc: str
    campos: dict[str, str] = field(default_factory=dict)
    fecha_consulta: str = ""
    observacion: str = ""

    def obtener(self, etiqueta: str) -> str:
        return self.campos.get(etiqueta, "")

    @property
    def sin_resultado(self) -> bool:
        return not self.campos

    def razon_social(self) -> str:
        """Razón social sin el prefijo del RUC que antepone SUNAT."""
        valor = self.obtener("Número de RUC") or self.obtener("Razón Social")
        if " - " in valor:
            return valor.split(" - ", 1)[1].strip()
        return valor


def normalizar_etiqueta(texto: str) -> str:
    """Colapsa espacios y quita los dos puntos finales de una etiqueta."""
    limpio = _ESPACIOS.sub(" ", (texto or "")).strip()
    return limpio.rstrip(":").strip()


def normalizar_valor(texto: str) -> str:
    """Colapsa espacios repetidos y saltos de línea de un valor del DOM."""
    return _ESPACIOS.sub(" ", (texto or "")).strip()


def normalizar_fecha(valor: str) -> str:
    """Convierte ``dd/mm/aaaa`` de SUNAT a ISO ``aaaa-mm-dd``.

    Si el valor no tiene ese formato se devuelve tal cual, sin inventar datos.
    """
    limpio = normalizar_valor(valor)
    coincidencia = _FORMATO_FECHA_SUNAT.match(limpio)
    if not coincidencia:
        return limpio
    dia, mes, anio = coincidencia.groups()
    try:
        return datetime(int(anio), int(mes), int(dia)).strftime("%Y-%m-%d")
    except ValueError:
        return limpio


def extraer_pares_dom(pagina) -> dict[str, str]:
    """Extrae pares etiqueta/valor del DOM del resultado de SUNAT.

    Prueba, en orden:
      1. bloques ``.list-group-item`` con encabezado y texto;
      2. filas de tabla de dos celdas;
      3. etiquetas que terminan en ``:`` seguidas de su valor hermano.

    Si varias etiquetas se repiten, los valores se unen con ``" | "`` para no
    perder información.
    """
    return pagina.evaluate(
        """
        () => {
          const pares = {};
          const limpiar = (s) => (s || '').replace(/\\s+/g, ' ').trim();
          const sinDosPuntos = (s) => limpiar(s).replace(/:+$/, '').trim();
          const agregar = (k, v) => {
            if (!k || !v) return;
            pares[k] = pares[k] ? pares[k] + ' | ' + v : v;
          };

          // 1) List-group de Bootstrap (maquetación por bloques etiqueta/valor)
          for (const item of document.querySelectorAll('.list-group-item')) {
            const encabezado = item.querySelector('.list-group-item-heading, h4, h5');
            const valor = item.querySelector('.list-group-item-text, p');
            if (encabezado && valor) agregar(sinDosPuntos(encabezado.innerText), limpiar(valor.innerText));
          }

          // 2) Filas de tabla con exactamente dos celdas
          if (!Object.keys(pares).length) {
            for (const fila of document.querySelectorAll('table tr')) {
              if (fila.cells.length !== 2) continue;
              agregar(sinDosPuntos(fila.cells[0].innerText), limpiar(fila.cells[1].innerText));
            }
          }

          // 3) Etiquetas terminadas en ':' con el valor en el hermano siguiente
          if (!Object.keys(pares).length) {
            for (const el of document.querySelectorAll('label, strong, b, h4, h5, span, td')) {
              const crudo = limpiar(el.innerText);
              if (!crudo.endsWith(':') || crudo.length > 80) continue;
              const hermano = el.nextElementSibling;
              if (hermano) agregar(sinDosPuntos(crudo), limpiar(hermano.innerText));
            }
          }

          return pares;
        }
        """
    )


def construir_resultado(
    ruc_consultado: str,
    pares: dict[str, str],
    observacion: str = "",
    fecha_consulta: datetime | None = None,
) -> ResultadoRuc:
    """Arma un :class:`ResultadoRuc` a partir de etiquetas crudas del DOM."""
    campos: dict[str, str] = {}
    for etiqueta, valor in pares.items():
        clave = normalizar_etiqueta(etiqueta)
        if not clave:
            continue
        limpio = normalizar_valor(valor)
        # Las etiquetas de fecha de SUNAT vienen como dd/mm/aaaa: se pasan a ISO.
        campos[clave] = normalizar_fecha(limpio) if "fecha" in clave.lower() else limpio

    fecha = (fecha_consulta or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    return ResultadoRuc(ruc=ruc_consultado, campos=campos, fecha_consulta=fecha, observacion=observacion)


def campos_faltantes(resultado: ResultadoRuc) -> list[str]:
    """Lista los campos clave que SUNAT no devolvió."""
    return [c for c in CAMPOS_CLAVE if not resultado.obtener(c)]


def ruc_devuelto(resultado: ResultadoRuc) -> str:
    """RUC que aparece en el resultado, sin la razón social que le sigue."""
    valor = resultado.obtener("Número de RUC")
    return valor.split(" - ", 1)[0].strip() if valor else ""


def detectar_respuesta_sospechosa(resultado: ResultadoRuc) -> list[str]:
    """Señala resultados que parecen errores disfrazados de datos."""
    problemas: list[str] = []
    if resultado.sin_resultado:
        problemas.append("SUNAT no devolvió ningún campo")
        return problemas

    devuelto = ruc_devuelto(resultado)
    if devuelto and devuelto != resultado.ruc:
        problemas.append(f"El RUC devuelto ({devuelto}) no coincide con el consultado ({resultado.ruc})")

    faltantes = campos_faltantes(resultado)
    if faltantes:
        problemas.append("Campos clave no devueltos: " + ", ".join(faltantes))
    return problemas
