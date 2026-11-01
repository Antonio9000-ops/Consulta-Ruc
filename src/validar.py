"""Validación de RUC peruano (SUNAT).

Reglas implementadas
--------------------
1. El RUC tiene exactamente 11 dígitos numéricos (sin espacios ni guiones).
2. Los dos primeros dígitos corresponden a un tipo de contribuyente válido
   publicado por SUNAT: 10, 15, 17 y 20.
3. El undécimo dígito es el dígito verificador, calculado con el algoritmo
   oficial de SUNAT: pesos [5,4,3,2,7,6,5,4,3,2] sobre los 10 primeros
   dígitos, suma, módulo 11 y complemento a 11. Si el resultado es 10 se
   usa 0 y si es 11 se usa 1.

El algoritmo fue contrastado con RUC públicos reales:
- 20131312955 (SUNAT)          -> dígito verificador 5
- 20100070970 (empresa pública) -> dígito verificador 0

Advertencia importante: un dígito verificador correcto **no** demuestra que
el RUC exista, esté activo ni esté habido. Eso solo lo confirma la consulta
en SUNAT.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PREFIJOS_VALIDOS: tuple[str, ...] = ("10", "15", "17", "20")
PESOS_DIGITO_VERIFICADOR: tuple[int, ...] = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
LONGITUD_RUC = 11
SOLO_DIGITOS = re.compile(r"^\d{11}$")


@dataclass
class ResultadoValidacion:
    """Resultado de validar un RUC."""

    valor_original: str
    ruc: str = ""
    valido: bool = False
    motivos: list[str] = field(default_factory=list)

    @property
    def motivo(self) -> str:
        return "; ".join(self.motivos)


def normalizar_ruc(valor: object) -> str:
    """Devuelve el RUC como texto sin espacios exteriores.

    Se eliminan también espacios internos y guiones, que suelen aparecer
    cuando el Excel guarda el valor con formato. Nunca se convierte a entero
    para no perder ceros ni precisión.
    """
    if valor is None:
        return ""
    texto = str(valor).strip()
    texto = texto.replace(" ", "").replace("-", "")
    return texto


def calcular_digito_verificador(diez_digitos: str) -> int:
    """Calcula el dígito verificador de SUNAT para los 10 primeros dígitos."""
    if len(diez_digitos) != 10 or not diez_digitos.isdigit():
        raise ValueError("Se requieren exactamente 10 dígitos numéricos")
    suma = sum(int(d) * p for d, p in zip(diez_digitos, PESOS_DIGITO_VERIFICADOR))
    resto = suma % 11
    digito = 11 - resto
    if digito == 10:
        return 0
    if digito == 11:
        return 1
    return digito


def validar_ruc(valor: object) -> ResultadoValidacion:
    """Valida un RUC y devuelve el detalle de los motivos de rechazo."""
    original = "" if valor is None else str(valor)
    ruc = normalizar_ruc(valor)
    resultado = ResultadoValidacion(valor_original=original, ruc=ruc)

    if not ruc:
        resultado.motivos.append("RUC vacío")
        return resultado

    if not SOLO_DIGITOS.match(ruc):
        if len(ruc) != LONGITUD_RUC:
            resultado.motivos.append(
                f"Longitud inválida: {len(ruc)} caracteres (se esperan {LONGITUD_RUC})"
            )
        if not ruc.isdigit():
            resultado.motivos.append("Contiene caracteres no numéricos")
        return resultado

    if ruc[:2] not in PREFIJOS_VALIDOS:
        resultado.motivos.append(
            f"Prefijo '{ruc[:2]}' no corresponde a un tipo de RUC SUNAT "
            f"({', '.join(PREFIJOS_VALIDOS)})"
        )

    esperado = calcular_digito_verificador(ruc[:10])
    if int(ruc[10]) != esperado:
        resultado.motivos.append(
            f"Dígito verificador incorrecto: se esperaba {esperado} y se recibió {ruc[10]}"
        )

    resultado.valido = not resultado.motivos
    return resultado


def validar_lote(valores: list[object]) -> tuple[list[ResultadoValidacion], dict[str, list[int]]]:
    """Valida una lista de RUC y detecta duplicados.

    Devuelve (resultados, duplicados) donde ``duplicados`` mapea cada RUC
    repetido a la lista de índices (base 0) en que aparece.
    """
    resultados = [validar_ruc(v) for v in valores]

    indices_por_ruc: dict[str, list[int]] = {}
    for i, r in enumerate(resultados):
        if r.ruc:
            indices_por_ruc.setdefault(r.ruc, []).append(i)

    duplicados = {ruc: idx for ruc, idx in indices_por_ruc.items() if len(idx) > 1}

    for ruc, indices in duplicados.items():
        for i in indices:
            resultados[i].motivos.append(
                f"RUC duplicado en el archivo (aparece {len(indices)} veces)"
            )
            resultados[i].valido = False

    return resultados, duplicados
