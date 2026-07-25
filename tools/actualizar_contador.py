#!/usr/bin/env python3
"""Mezcla los pre-registros reales con la base sintetica y actualiza el contador.

    python3 tools/actualizar_contador.py                       # solo la base
    python3 tools/actualizar_contador.py respuestas.csv         # base + reales
    python3 tools/actualizar_contador.py respuestas.csv --mezcla ../mezcla.json

El CSV es el que baja de la planilla de respuestas del Google Formulario
(Archivo > Descargar > Valores separados por comas).

Que escribe:

  datos/contador.json        solo numeros. Es lo unico que lee el sitio.
  --mezcla RUTA              los dos sets juntos, para regenerar el mapa.

OJO con --mezcla: ese archivo lleva correos y direcciones de personas reales, y
este repo es publico. Guardalo FUERA del repo (por eso no tiene default) y
pasaselo a generar_mapa_publico.py, que agrega por comuna y no publica domicilios.
"""

import argparse
import csv
import json
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GENERICOS = RAIZ / "datos" / "registros-genericos.json"
CONTADOR = RAIZ / "datos" / "contador.json"

# Encabezados de la planilla -> nombres que usamos aca. Mismo mapeo que
# generar_mapa.py, que lee el mismo CSV.
COLUMNAS = {
    "marca temporal": "fecha",
    "timestamp": "fecha",
    "correo electrónico": "correo",
    "correo electronico": "correo",
    "correo": "correo",
    "dirección": "direccion",
    "direccion": "direccion",
    "lat": "lat",
    "latitud": "lat",
    "lon": "lon",
    "longitud": "lon",
    "comuna": "comuna",
}


def leer_csv(ruta):
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        filas = [
            {COLUMNAS.get((k or "").strip().lower(), (k or "").strip().lower()):
             (v or "").strip()
             for k, v in fila.items()}
            for fila in csv.DictReader(f)
        ]
    # Una fila sin correo ni direccion es una fila vacia al final de la planilla,
    # no una persona.
    return [f for f in filas if f.get("correo") or f.get("direccion")]


def es_prueba(fila):
    """Envio de prueba, no una persona.

    El generador de datos demo tiene un boton "Enviar al formulario real" para
    probar el circuito completo, y lo que manda queda mezclado con los registros
    de verdad en la planilla. Por eso marca esos correos con .demo@: es la misma
    marca que usa COMO-ACTUALIZAR-EL-MAPA.md para borrarlos a mano.
    """
    return ".demo@" in (fila.get("correo") or "").lower()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", type=Path,
                    help="respuestas.csv bajado de la planilla")
    ap.add_argument("--mezcla", type=Path,
                    help="donde escribir genericos + reales juntos (fuera del repo)")
    args = ap.parse_args()

    if not GENERICOS.exists():
        ap.error(f"falta {GENERICOS.relative_to(RAIZ)}. "
                 "Corre primero: python3 tools/generar_registros_genericos.py")

    genericos = json.loads(GENERICOS.read_text(encoding="utf-8"))
    filas = leer_csv(args.csv) if args.csv else []
    pruebas = [f for f in filas if es_prueba(f)]
    reales = [f for f in filas if not es_prueba(f)]

    contador = {
        "_comentario": ("Lo lee el contador de index.html. 'generados' es la base "
                        "sintetica de datos/registros-genericos.json; 'reales' son "
                        "los pre-registros de la planilla al dia de 'actualizado'."),
        "generados": len(genericos),
        "reales": len(reales),
        "total": len(genericos) + len(reales),
        "actualizado": date.today().isoformat(),
    }
    CONTADOR.parent.mkdir(parents=True, exist_ok=True)
    CONTADOR.write_text(json.dumps(contador, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")

    print(f"contador: {contador['total']} "
          f"({contador['generados']} genericos + {contador['reales']} reales)")
    if pruebas:
        print(f"   {len(pruebas)} fila(s) .demo@ descartada(s): son envios de prueba "
              "del generador, no personas")
    print(f"   {CONTADOR.relative_to(RAIZ)}")

    if args.mezcla:
        if RAIZ in args.mezcla.resolve().parents:
            ap.error("--mezcla apunta adentro del repo, que es publico, y el archivo "
                     "lleva correos y direcciones reales. Elegi una ruta de afuera.")
        args.mezcla.parent.mkdir(parents=True, exist_ok=True)
        args.mezcla.write_text(
            json.dumps(genericos + reales, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")
        print(f"   {args.mezcla}  ({len(genericos) + len(reales)} registros)")
        print("   para el mapa: python3 generar_mapa_publico.py "
              f"{args.mezcla} sitio/mapa-demo.html")

    if not args.csv:
        print("   (sin CSV: reales quedo en 0. Baja la planilla y pasala como "
              "argumento para sumarlos.)")


if __name__ == "__main__":
    main()
