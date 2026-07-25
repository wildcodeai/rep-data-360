#!/usr/bin/env python3
"""Actualiza el mapa publicado con los pre-registros de la planilla.

    python3 tools/publicar_mapa.py respuestas.csv

Hace toda la cadena de una vez:

    1. lee el CSV que bajaste de la planilla
    2. regenera mapa-detallado.html  (local, con domicilios: NO se publica)
    3. regenera mapa.html            (agregado por comuna: si se publica)
    4. commit y push  ->  GitHub Pages redespliega solo en ~1 minuto

Para bajar el CSV: abri la planilla de respuestas y anda a
Archivo > Descargar > Valores separados por comas (.csv)

Agrega --sin-publicar si solo queres ver los mapas sin subir nada.
"""

import subprocess
import sys
from pathlib import Path

import generar_mapa
import generar_mapa_publico

# SITIO es el repo publico (donde corren los git). RAIZ es la carpeta de trabajo
# local, un nivel mas arriba: ahi viven el CSV de la planilla y el mapa detallado
# con domicilios, que nunca deben entrar al repo.
SITIO = Path(__file__).resolve().parent.parent
RAIZ = SITIO.parent


def corro(*args, **kw):
    return subprocess.run(args, cwd=SITIO, capture_output=True, text=True, **kw)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    publicar = "--sin-publicar" not in sys.argv

    if not args:
        print(__doc__)
        return 1

    entrada = Path(args[0]).resolve()
    if not entrada.exists():
        print(f"No encuentro {entrada}")
        return 1

    # sin_pruebas: esta cadena siempre lee la planilla real, y ahi los .demo@ son
    # basura de probar el formulario. El contador del sitio los descarta igual;
    # si no lo hicieramos aca, el mapa y el contador dirian numeros distintos.
    puntos, descartadas = generar_mapa.cargar(entrada, sin_pruebas=True)
    if not puntos and not descartadas:
        print(f"{entrada.name} no tiene registros. No toco nada.")
        return 1

    print(f"Leidos {len(puntos)} pre-registro(s) de {entrada.name}"
          + (f", {len(descartadas)} sin ubicar" if descartadas else ""))
    for f, motivo in descartadas:
        print(f"   sin ubicar: {f.get('correo', '?')} — {motivo}")

    # 1. Mapa detallado, local. Tiene domicilios: nunca se versiona.
    detallado = RAIZ / "mapa-detallado.html"
    generar_mapa.escribir_fuera_del_repo(
        detallado, generar_mapa.construir(puntos, descartadas))
    print(f"   {detallado.name} (local, con domicilios)")

    # 2. Mapa publico, agregado por comuna.
    publicar_publico(puntos)

    # 3. Contador de la portada. Va en la misma corrida a proposito: son dos
    # archivos que cuentan lo mismo, y cuando se actualizaban por separado el
    # contador quedaba atras del mapa y la portada mostraba un numero viejo.
    r = corro(sys.executable, str(Path(__file__).parent / "actualizar_contador.py"),
              str(entrada))
    if r.returncode:
        print("No pude actualizar el contador:", r.stderr.strip())
        return 1
    for linea in r.stdout.strip().splitlines():
        print("   " + linea.strip())

    if not publicar:
        print("\n--sin-publicar: no subo nada. Revisa mapa.html y volve a correr sin la bandera.")
        return 0

    # 4. Commit y push.
    #
    # El mapa se compara por archivo, pero contador.json no: lleva el instante
    # del corte, que cambia en cada corrida aunque no haya entrado nadie nuevo.
    # Sin esto, cada `publicar_mapa.py` dejaria un commit vacio de contenido.
    estado = corro("git", "status", "--porcelain", "mapa.html")
    if not estado.stdout.strip() and not contador_cambio():
        print("\nEl mapa publicado no cambio. No hay nada que subir.")
        corro("git", "checkout", "--", "datos/contador.json")
        return 0

    rama = corro("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if rama != "main":
        print(f"\nEstas en la rama '{rama}', no en main. Cambiate a main y volve a correr.")
        return 1

    corro("git", "add", "mapa.html", "datos/contador.json")
    r = corro("git", "-c", "user.email=wildcodeai@gmail.com",
              "-c", "user.name=César Guerrero Torres",
              "commit", "-m",
              f"Actualizar el mapa de demanda ({len(puntos)} pre-registros)")
    if r.returncode:
        print("No pude commitear:", r.stderr.strip())
        return 1

    r = corro("git", "push")
    if r.returncode:
        print("No pude pushear:", r.stderr.strip())
        return 1

    print("\nPublicado. GitHub Pages tarda ~1 minuto en redesplegar:")
    print("   https://wildcodeai.github.io/rep-data-360/mapa.html")
    return 0


def contador_cambio():
    """True si cambiaron los numeros del contador, ignorando el instante del corte."""
    import json

    def numeros(texto):
        try:
            d = json.loads(texto)
        except (ValueError, TypeError):
            return None
        return (d.get("generados"), d.get("reales"), d.get("total"))

    publicado = corro("git", "show", "HEAD:datos/contador.json")
    if publicado.returncode:
        return True   # todavia no esta versionado: hay que subirlo
    nuevo = (SITIO / "datos" / "contador.json").read_text(encoding="utf-8")
    return numeros(publicado.stdout) != numeros(nuevo)


def publicar_publico(puntos):
    """Genera mapa.html con datos reales (sin banner de demostracion)."""
    from collections import Counter
    g = generar_mapa_publico
    conteo = Counter(p["comuna"] or "Sin comuna" for p in puntos)
    grandes = [(c, n) for c, n in conteo.most_common() if n >= g.MINIMO]
    ocultas = [(c, n) for c, n in conteo.most_common() if n < g.MINIMO]
    centros = g.centroides([c for c, _ in grandes]) if grandes else {}
    publicas = [(c, n, centros.get(c)) for c, n in grandes]
    (SITIO / "mapa.html").write_text(
        g.construir(publicas, ocultas, len(puntos), demo=False), encoding="utf-8")
    print(f"   mapa.html ({len(publicas)} comuna(s) en el mapa, "
          f"{len(ocultas)} en «Otras»)")


if __name__ == "__main__":
    sys.exit(main())
