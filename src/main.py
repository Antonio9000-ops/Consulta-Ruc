"""Punto de entrada del proyecto de consulta de RUC.

Uso:
    python -m src.main                        # solo valida el Excel de entrada
    python -m src.main --consultar            # valida y consulta SUNAT (1 RUC)
    python -m src.main --consultar --limite 3 # lote pequeño y autorizado

Modos
-----
``--validar`` (por defecto)
    Lee el Excel, normaliza y valida cada RUC y escribe un libro de validación
    con las hojas Validos, Errores y Resumen. No toca SUNAT.

``--consultar``
    Consulta SUNAT de forma secuencial, con pausa entre consultas y límite por
    lote. Guarda el avance en ``output/parcial_resultados.jsonl`` para poder
    reanudar sin repetir consultas ya completadas.

Ninguno de los dos modos sobrescribe resultados existentes sin ``--sobrescribir``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.extraer import COLUMNAS_ORDEN, ResultadoRuc, detectar_respuesta_sospechosa
from src.validar import ResultadoValidacion, validar_lote

RUTA_ENTRADA_POR_DEFECTO = Path("data/input/rucs_a_consultar.xlsx")
RUTA_VALIDACION_POR_DEFECTO = Path("output/validacion_ruc.xlsx")
RUTA_RESULTADOS_POR_DEFECTO = Path("output/resultados_consulta_ruc.xlsx")
RUTA_PARCIAL_POR_DEFECTO = Path("output/parcial_resultados.jsonl")
COLUMNA_RUC = "RUC"

COLUMNAS_RESULTADOS = ("RUC", *COLUMNAS_ORDEN, "Observación", "Estado del proceso")
COLUMNAS_ERRORES = ("RUC", "Etapa", "Motivo", "Fecha/hora")


# --- lectura y validación ------------------------------------------------
def leer_rucs(ruta: Path) -> list[str]:
    """Lee la columna RUC como texto, sin convertirla nunca a entero."""
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe el archivo de entrada: {ruta}\n"
            f"Crea un Excel con una columna '{COLUMNA_RUC}' y colócalo en {ruta}."
        )

    tabla = pd.read_excel(ruta, dtype=str)
    if COLUMNA_RUC not in tabla.columns:
        raise ValueError(
            f"El archivo {ruta} no tiene la columna '{COLUMNA_RUC}'. "
            f"Columnas encontradas: {', '.join(map(str, tabla.columns)) or 'ninguna'}"
        )

    return ["" if pd.isna(v) else str(v) for v in tabla[COLUMNA_RUC].tolist()]


def construir_libro_validacion(
    resultados: list[ResultadoValidacion],
    ruta_entrada: Path,
) -> dict[str, pd.DataFrame]:
    """Arma las hojas Validos, Errores y Resumen del libro de validación."""
    marca = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    filas_validas = [
        {"Fila": i + 2, "RUC": r.ruc, "Estado de validación": "VÁLIDO"}
        for i, r in enumerate(resultados)
        if r.valido
    ]

    filas_error = [
        {"Fila": i + 2, "RUC": r.ruc or r.valor_original, "Motivo": r.motivo, "Fecha/hora": marca}
        for i, r in enumerate(resultados)
        if not r.valido
    ]

    total = len(resultados)
    validos = len(filas_validas)
    resumen = [
        {"Métrica": "Archivo de entrada", "Valor": str(ruta_entrada)},
        {"Métrica": "Fecha/hora de validación", "Valor": marca},
        {"Métrica": "Total de filas leídas", "Valor": total},
        {"Métrica": "RUC válidos", "Valor": validos},
        {"Métrica": "RUC con error", "Valor": total - validos},
        {"Métrica": "RUC consultados en SUNAT", "Valor": 0},
        {"Métrica": "Nota", "Valor": "Solo validación: no se consultó SUNAT en este modo"},
    ]

    return {
        "Validos": pd.DataFrame(filas_validas, columns=["Fila", "RUC", "Estado de validación"]),
        "Errores": pd.DataFrame(filas_error, columns=["Fila", "RUC", "Motivo", "Fecha/hora"]),
        "Resumen": pd.DataFrame(resumen, columns=["Métrica", "Valor"]),
    }


# --- escritura de archivos ----------------------------------------------
def verificar_destino(ruta: Path, sobrescribir: bool) -> None:
    if ruta.exists() and not sobrescribir:
        raise FileExistsError(
            f"{ruta} ya existe. Renómbralo, bórralo tú mismo o usa --sobrescribir "
            f"(el proyecto no sobrescribe resultados sin autorización)."
        )


def escribir_libro(hojas: dict[str, pd.DataFrame], ruta: Path, sobrescribir: bool) -> None:
    verificar_destino(ruta, sobrescribir)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ruta, engine="openpyxl") as escritor:
        for nombre, tabla in hojas.items():
            tabla.to_excel(escritor, sheet_name=nombre, index=False)


# --- consulta a SUNAT ---------------------------------------------------
def cargar_parcial(ruta: Path) -> dict[str, dict]:
    """Lee el avance previo: RUC -> registro ya consultado."""
    if not ruta.exists():
        return {}
    hechos: dict[str, dict] = {}
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea:
                continue
            try:
                registro = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if registro.get("ruc"):
                hechos[registro["ruc"]] = registro
    return hechos


def agregar_parcial(ruta: Path, resultado: ResultadoRuc, estado: str) -> None:
    """Añade un registro al avance incremental (una línea JSON por RUC)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    registro = {
        "ruc": resultado.ruc,
        "campos": resultado.campos,
        "fecha_consulta": resultado.fecha_consulta,
        "observacion": resultado.observacion,
        "estado": estado,
    }
    with open(ruta, "a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")


def fila_resultado(registro: dict) -> dict:
    """Convierte un registro guardado en una fila del reporte."""
    campos = registro.get("campos") or {}
    fila = {"RUC": registro.get("ruc", "")}
    for columna in COLUMNAS_ORDEN:
        fila[columna] = campos.get(columna, "")
    for etiqueta, valor in campos.items():
        if etiqueta not in fila:
            fila[etiqueta] = valor
    fila["Observación"] = registro.get("observacion", "")
    fila["Estado del proceso"] = registro.get("estado", "")
    return fila


def construir_libro_resultados(
    validos: list[ResultadoValidacion],
    parciales: dict[str, dict],
    errores: list[dict],
    total_leidos: int,
) -> dict[str, pd.DataFrame]:
    """Arma las hojas Resultados, Errores y Resumen del libro final."""
    filas = [fila_resultado(parciales[r.ruc]) for r in validos if r.ruc in parciales]
    columnas = ["RUC", *COLUMNAS_ORDEN, "Observación", "Estado del proceso"]
    tabla = pd.DataFrame(filas)
    for extra in [c for c in tabla.columns if c not in columnas]:
        columnas.append(extra)

    exitosos = sum(1 for r in filas if r["Estado del proceso"] == "CONSULTADO")
    sin_resultado = sum(1 for r in filas if r["Estado del proceso"] == "SIN RESULTADO")
    fallidos = sum(1 for r in filas if r["Estado del proceso"] == "ERROR")

    resumen = [
        {"Métrica": "Fecha/hora del reporte", "Valor": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Métrica": "Total de filas leídas", "Valor": total_leidos},
        {"Métrica": "RUC válidos", "Valor": len(validos)},
        {"Métrica": "RUC inválidos (no consultados)", "Valor": total_leidos - len(validos)},
        {"Métrica": "RUC consultados", "Valor": len(filas)},
        {"Métrica": "Consultas exitosas", "Valor": exitosos},
        {"Métrica": "Consultas sin resultado", "Valor": sin_resultado},
        {"Métrica": "Consultas fallidas", "Valor": fallidos},
        {"Métrica": "RUC válidos pendientes de consultar", "Valor": len(validos) - len(filas)},
    ]

    return {
        "Resultados": tabla.reindex(columns=columnas),
        "Errores": pd.DataFrame(errores, columns=list(COLUMNAS_ERRORES)),
        "Resumen": pd.DataFrame(resumen, columns=["Métrica", "Valor"]),
    }


def ejecutar_consulta(args: argparse.Namespace, resultados_validacion, total_leidos: int) -> int:
    from src.sunat import (
        BloqueoSunat,
        CaptchaDetectado,
        ConfiguracionNavegacion,
        ConsultaSUNAT,
        pausa_entre_consultas,
    )

    validos = [r for r in resultados_validacion if r.valido]
    if not validos:
        print("No hay RUC válidos para consultar.", file=sys.stderr)
        return 1

    limite = max(1, min(args.limite, 20))
    config = ConfiguracionNavegacion(
        headless=args.headless,
        pausa_segundos=max(args.pausa, 0.0),
        maximo_consultas=limite,
    )

    parciales = cargar_parcial(args.parcial)
    pendientes = [r.ruc for r in validos if r.ruc not in parciales]
    if parciales:
        print(f"Reanudando: {len(parciales)} RUC ya consultados antes.")
    pendientes = pendientes[:limite]
    print(f"Se consultarán {len(pendientes)} RUC (límite {limite}, pausa {config.pausa_segundos}s).")

    errores: list[dict] = []
    abortado: str | None = None

    try:
        with ConsultaSUNAT(config) as sesion:
            for posicion, ruc in enumerate(pendientes, start=1):
                if posicion > 1:
                    pausa_entre_consultas(config)
                print(f"[{posicion}/{len(pendientes)}] {ruc} ... ", end="", flush=True)
                try:
                    resultado = sesion.consultar(ruc)
                except CaptchaDetectado as error:
                    print("CAPTCHA")
                    errores.append(_error(ruc, "CAPTCHA", str(error)))
                    abortado = "CAPTCHA detectado: se detiene el lote."
                    break
                except BloqueoSunat as error:
                    print("BLOQUEO")
                    errores.append(_error(ruc, "BLOQUEO", str(error)))
                    abortado = "SUNAT bloqueó la ejecución: se detiene el lote."
                    break
                except Exception as error:  # fallo inesperado de un solo RUC
                    print("ERROR")
                    errores.append(_error(ruc, "CONSULTA", f"{type(error).__name__}: {error}"))
                    continue

                if resultado.sin_resultado:
                    estado = "SIN RESULTADO"
                    print(f"sin resultado ({resultado.observacion})")
                else:
                    estado = "CONSULTADO"
                    print(resultado.razon_social()[:50] or "ok")

                for problema in detectar_respuesta_sospechosa(resultado):
                    errores.append(_error(ruc, "CALIDAD", problema))

                agregar_parcial(args.parcial, resultado, estado)
                parciales[ruc] = {
                    "ruc": resultado.ruc,
                    "campos": resultado.campos,
                    "fecha_consulta": resultado.fecha_consulta,
                    "observacion": resultado.observacion,
                    "estado": estado,
                }
    except BloqueoSunat as error:
        errores.append(_error("", "NAVEGADOR", str(error)))
        abortado = "No se pudo iniciar la sesión de navegador."

    hojas = construir_libro_resultados(
        [r.ruc for r in validos], validos, parciales, errores, total_leidos
    )
    escribir_libro(hojas, args.salida, args.sobrescribir)
    print(f"Reporte escrito en: {args.salida}")

    if abortado:
        print(f"DETENIDO: {abortado}", file=sys.stderr)
        return 2
    return 0


def _error(ruc: str, etapa: str, motivo: str) -> dict:
    return {
        "RUC": ruc,
        "Etapa": etapa,
        "Motivo": motivo,
        "Fecha/hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# --- validación sola ----------------------------------------------------
def ejecutar_validacion(ruta_entrada: Path, ruta_salida: Path, sobrescribir: bool) -> int:
    rucs = leer_rucs(ruta_entrada)
    if not rucs:
        print(f"El archivo {ruta_entrada} no contiene filas en la columna '{COLUMNA_RUC}'.")
        return 1

    resultados, duplicados = validar_lote(rucs)
    validos = sum(1 for r in resultados if r.valido)

    print(f"Filas leídas: {len(resultados)}")
    print(f"RUC válidos:  {validos}")
    print(f"RUC con error: {len(resultados) - validos}")
    if duplicados:
        print(f"Duplicados detectados: {len(duplicados)}")

    for i, r in enumerate(resultados):
        if not r.valido:
            print(f"  fila {i + 2}: {r.ruc or r.valor_original!r} -> {r.motivo}")

    escribir_libro(construir_libro_validacion(resultados, ruta_entrada), ruta_salida, sobrescribir)
    print(f"Reporte escrito en: {ruta_salida}")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validación y consulta de RUC (SUNAT) — proyecto académico."
    )
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--validar", action="store_true", help="Solo validar el Excel (por defecto).")
    modo.add_argument("--consultar", action="store_true", help="Validar y consultar SUNAT.")
    parser.add_argument("--entrada", type=Path, default=RUTA_ENTRADA_POR_DEFECTO)
    parser.add_argument("--salida", type=Path, default=None)
    parser.add_argument("--parcial", type=Path, default=RUTA_PARCIAL_POR_DEFECTO)
    parser.add_argument("--limite", type=int, default=1, help="Máximo de consultas por lote (1-20).")
    parser.add_argument("--pausa", type=float, default=3.0, help="Segundos entre consultas.")
    parser.add_argument("--headless", action="store_true", help="Navegador sin ventana.")
    parser.add_argument(
        "--sobrescribir",
        action="store_true",
        help="Permite reemplazar un reporte existente.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    args.salida = args.salida or (
        RUTA_RESULTADOS_POR_DEFECTO if args.consultar else RUTA_VALIDACION_POR_DEFECTO
    )

    try:
        if args.consultar:
            rucs = leer_rucs(args.entrada)
            if not rucs:
                print(f"El archivo {args.entrada} no tiene filas en la columna '{COLUMNA_RUC}'.")
                return 1
            resultados, _ = validar_lote(rucs)
            return ejecutar_consulta(args, resultados, len(rucs))
        return ejecutar_validacion(args.entrada, args.salida, args.sobrescribir)
    except (FileNotFoundError, ValueError, FileExistsError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
