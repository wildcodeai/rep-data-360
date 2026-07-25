#!/usr/bin/env python3
"""Cuenta los pre-registros reales mas la base sintetica y actualiza el contador.

    python3 tools/actualizar_contador.py                       # solo la base
    python3 tools/actualizar_contador.py respuestas.csv         # base + reales

El CSV es el que baja de la planilla de respuestas del Google Formulario
(Archivo > Descargar > Valores separados por comas).

Escribe datos/contador.json, que son solo numeros y es lo unico que lee el sitio.

Normalmente no hace falta correrlo a mano: publicar_mapa.py lo llama, para que el
mapa y el contador salgan siempre del mismo corte.

Hubo una opcion --mezcla que dejaba los dos sets juntos en un archivo, para
alimentar el segundo mapa. Ya no hay segundo mapa, y ese archivo llevaba correos
y direcciones reales con la obligacion de acordarse de guardarlo fuera de este
repo, que es publico. Se saco: publicar_mapa.py mezcla en memoria, contando por
comuna, sin escribir nada con datos personales.
"""

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GENERICOS = RAIZ / "datos" / "registros-genericos.json"
CONTADOR = RAIZ / "datos" / "contador.json"

# Hoja «Conteo» de la planilla, publicada en la web como CSV: una sola celda con
# =CONTARA(...). Es lo unico publico de una planilla que por lo demas es privada,
# y por eso puede leerla el navegador de cualquiera que entre al sitio: sin esto,
# el numero solo cambia cuando alguien regenera contador.json a mano.
#
# Publicar la hoja de RESPUESTAS en vez de esta seria filtrar correos y
# direcciones. Si algun dia hay que rehacerla, que sea otra vez una celda sola.
#
# Lo que devuelve NO es el numero de pre-registros: esa formula cuenta tambien el
# encabezado y las filas .demo@ de prueba. No se corrige en la planilla a
# proposito: el sitio se calibra solo guardando aca abajo cuanto marcaba la celda
# en este corte, y despues suma la diferencia. Asi funciona con cualquier formula
# que crezca de a uno por fila nueva, y si se borran filas, tambien baja.
CSV_PUBLICADO = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vSw5w4U9IS5zsJstyxGxWVRqA"
    "CVjfsXqH9m1D7T8UIE0PuUxIaeuCTdmnES2EpPTNS9Qfo__LlSt5LS/pub"
    "?gid=127842915&single=true&output=csv"
)

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


def leer_celda_publicada():
    """Cuanto marca ahora la celda publicada. None si no se pudo leer.

    Se lee al generar para dejar anotado el punto de partida. El navegador
    despues compara contra ese numero, asi que lo unico que importa es que sea
    el mismo valor que va a ver el, no que signifique algo por si solo.
    """
    import random
    import urllib.request
    # El parametro de mas es para saltear la cache del CDN de Google, que sirve
    # esa URL con el valor de hace un rato: recien probado, la URL pelada devolvia
    # 19 y con el parametro 17, que era lo correcto. Calibrar contra el numero
    # viejo dejaria al contador arrastrando esa diferencia para siempre.
    url = f"{CSV_PUBLICADO}&_={random.randrange(10 ** 9)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            texto = r.read().decode("utf-8-sig")
    except Exception as e:
        print(f"   no pude leer la celda publicada ({e.__class__.__name__}): el "
              "contador va a quedar en el numero del archivo hasta la proxima")
        return None

    lineas = [l.strip().strip('"') for l in texto.splitlines() if l.strip()]
    if len(lineas) > 2 or not lineas or not lineas[-1].isdigit():
        # Mas de dos lineas es la hoja de respuestas entera, no la celda del
        # conteo. Se ignora: si se publico eso por error, el problema es otro y
        # mucho mas grave que un contador desactualizado.
        print("   la URL publicada no devuelve una celda con un numero. La ignoro.")
        return None
    return int(lineas[-1])


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
                        "los pre-registros de la planilla al dia de 'actualizado'. "
                        "'generado' es el instante exacto del corte: con el la "
                        "pagina sabe si quien la mira ya esta contado aca."),
        "generados": len(genericos),
        "reales": len(reales),
        "total": len(genericos) + len(reales),
        "actualizado": date.today().isoformat(),
        # Con fecha sola, quien se pre-registra el mismo dia en que se regenero
        # el corte no ve su +1: '2026-07-25' no es mayor que '2026-07-25'. El
        # instante desempata. Va en UTC y terminado en Z a proposito: el navegador
        # guarda su marca con toISOString(), que tambien es UTC, y asi las dos se
        # pueden comparar como texto. Con husos distintos esa comparacion miente.
        "generado": (datetime.now(timezone.utc).replace(microsecond=0)
                     .strftime("%Y-%m-%dT%H:%M:%S.000Z")),
    }

    # El par que deja el contador en vivo: la URL de la celda publicada y cuanto
    # marcaba en este corte. El navegador la vuelve a leer y suma la diferencia,
    # asi que no hace falta regenerar nada para que el numero suba. Si no se pudo
    # leer, no se escriben: sin el punto de partida la diferencia no significa
    # nada, y es preferible el numero del archivo antes que uno inventado.
    celda = leer_celda_publicada() if args.csv else None
    if celda is not None:
        contador["planilla_csv"] = CSV_PUBLICADO
        contador["planilla_al_corte"] = celda

    CONTADOR.parent.mkdir(parents=True, exist_ok=True)
    CONTADOR.write_text(json.dumps(contador, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")

    print(f"contador: {contador['total']} "
          f"({contador['generados']} genericos + {contador['reales']} reales)")
    if celda is not None:
        print(f"   celda publicada en {celda}: de aca en mas el sitio suma solo "
              "lo que entre a la planilla")
    if pruebas:
        print(f"   {len(pruebas)} fila(s) .demo@ descartada(s): son envios de prueba "
              "del generador, no personas")
    print(f"   {CONTADOR.relative_to(RAIZ)}")

    if not args.csv:
        print("   (sin CSV: reales quedo en 0. Baja la planilla y pasala como "
              "argumento para sumarlos.)")


if __name__ == "__main__":
    main()
