#!/usr/bin/env python3
"""Genera la base sintetica de pre-registros que arranca el contador del sitio.

    python3 tools/generar_registros_genericos.py            # 500, semilla 360
    python3 tools/generar_registros_genericos.py -n 800

Escribe datos/registros-genericos.json con el MISMO esquema que exporta la
planilla de respuestas (fecha, correo, direccion, lat, lon, comuna), asi que el
archivo se puede pasar tal cual a generar_mapa_publico.py o mezclar con el CSV
real sin convertir nada.

La semilla es fija a proposito: correr el script dos veces da exactamente el
mismo set. Sin eso, cada regeneracion movia los 500 puntos del mapa y el
contador se veia inventado de nuevo cada vez.

Los datos son SINTETICOS. No son personas. El sitio lo dice bajo el numero.
"""

import argparse
import json
import math
import random
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "datos" / "registros-genericos.json"

NOMBRES = ['Javier', 'Camila', 'Matías', 'Valentina', 'Sebastián', 'Catalina', 'Benjamín',
           'Antonia', 'Vicente', 'Josefa', 'Tomás', 'Fernanda', 'Ignacio', 'Constanza',
           'Diego', 'Francisca', 'Cristóbal', 'Martina', 'Felipe', 'Isidora', 'Nicolás',
           'Emilia', 'Joaquín', 'Paula', 'Rodrigo', 'Daniela', 'Andrés', 'Bárbara',
           'Gonzalo', 'Macarena']

APELLIDOS = ['González', 'Muñoz', 'Rojas', 'Díaz', 'Pérez', 'Soto', 'Contreras', 'Silva',
             'Martínez', 'Sepúlveda', 'Morales', 'Rodríguez', 'López', 'Fuentes',
             'Hernández', 'Torres', 'Araya', 'Flores', 'Espinoza', 'Valenzuela',
             'Castillo', 'Ramírez', 'Reyes', 'Gutiérrez', 'Castro', 'Vergara', 'Álvarez',
             'Riquelme', 'Sandoval', 'Guerrero']

CALLES = ['Los Alerces', 'Avenida Providencia', 'Pasaje Los Copihues', 'Los Aromos',
          'Avenida Matta', 'Los Cerezos', 'San Martín', 'Las Acacias', 'Avenida Grecia',
          'Los Robles', 'Manuel Rodríguez', 'Los Nogales', 'Avenida Macul', 'El Bosque',
          'Las Camelias', 'Avenida Colón', 'Los Maitenes', 'Arturo Prat', 'Las Rosas',
          'Avenida Ossa']

# Comuna, centro real y radio aproximado en grados. El peso concentra la demanda
# como pasaria de verdad; repartida pareja, el mapa de calor no muestra nada.
COMUNAS = [
    ('Santiago',         -33.4489, -70.6693, 0.022, 14),
    ('Maipú',            -33.5110, -70.7580, 0.035, 13),
    ('Puente Alto',      -33.6117, -70.5758, 0.030, 12),
    ('La Florida',       -33.5323, -70.5987, 0.028, 10),
    ('Ñuñoa',            -33.4569, -70.5975, 0.018, 9),
    ('Providencia',      -33.4314, -70.6093, 0.015, 8),
    ('Las Condes',       -33.4088, -70.5677, 0.028, 7),
    ('Peñalolén',        -33.4830, -70.5400, 0.022, 6),
    ('Recoleta',         -33.4100, -70.6400, 0.018, 5),
    ('San Miguel',       -33.4960, -70.6520, 0.014, 4),
    ('Macul',            -33.4900, -70.5980, 0.015, 4),
    ('Estación Central', -33.4600, -70.6900, 0.018, 4),
    ('Quilicura',        -33.3600, -70.7300, 0.025, 3),
    ('Valparaíso',       -33.0472, -71.6127, 0.025, 5),
    ('Viña del Mar',     -33.0245, -71.5518, 0.022, 4),
    ('Concepción',       -36.8270, -73.0503, 0.025, 3),
]

# icloud y hotmail pesan mas que el resto porque es la mezcla que se pidio para
# el pitch: correos de gente comun, no una lista de casillas universitarias.
DOMINIOS = [('icloud.com', 26), ('hotmail.com', 26), ('gmail.com', 22),
            ('outlook.com', 12), ('usach.cl', 14)]

# Piezas para los nicks inventados: la mitad de los correos no es
# nombre.apellido sino algo que alguien elegiria a los 15 anios y arrastra
# hasta hoy.
NICKS = ['reciclo', 'verdecito', 'ecko', 'tuti', 'pipe', 'kata', 'vale', 'nacho', 'male',
         'javi', 'coni', 'fran', 'tomi', 'manu', 'dani', 'pancho', 'chinito', 'flaco',
         'lolo', 'rulo', 'peke', 'zeta', 'niko', 'kari', 'moni', 'beto', 'gatoazul',
         'sopaipilla', 'lunita', 'ososs', 'pollito', 'atun', 'papo', 'mica', 'cami',
         'seba', 'vichi', 'ximi', 'rous', 'terremoto', 'compostera', 'huevoduro',
         'mote', 'chirimoya', 'pandita', 'kiwi', 'tallarin', 'bicicleta', 'lector',
         'nortino']

COLAS = ['', '', '', '_recicla', '.cl', '2001', '_ok', 'tkm', 'xd', '96', '007',
         '_stgo', 'ito', '_real', '.dev', '_360', '21', '_9', 'uwu', '88', '_23']


def sin_tildes(texto):
    """gonzález -> gonzalez. Un correo con tilde no existe."""
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                   if unicodedata.category(c) != 'Mn').lower()


def parte_local(r, nombre, apellido):
    """La parte del correo antes del arroba."""
    n, a = sin_tildes(nombre), sin_tildes(apellido)
    estilo = r.random()
    if estilo < 0.28:
        return f"{n}.{a}"
    if estilo < 0.40:
        return f"{n}{a}{r.randint(1, 99)}"
    if estilo < 0.50:
        return f"{n[0]}{a}{r.choice(['', str(r.randint(70, 99))])}"
    # El resto son nicks inventados.
    nick = r.choice(NICKS)
    if r.random() < 0.35:
        nick = nick + r.choice(['_', '.', ''])+ r.choice(NICKS)
    return nick + r.choice(COLAS)


def elegir(r, opciones):
    """Elige respetando los pesos (ultimo elemento de cada tupla)."""
    total = sum(o[-1] for o in opciones)
    x = r.random() * total
    for o in opciones:
        x -= o[-1]
        if x <= 0:
            return o
    return opciones[0]


def generar(cantidad, semilla):
    r = random.Random(semilla)
    ahora = datetime.now().replace(microsecond=0)
    usados = set()
    registros = []

    for _ in range(cantidad):
        nombre = r.choice(NOMBRES)
        apellido = r.choice(APELLIDOS)
        dominio = elegir(r, DOMINIOS)[0]

        local = parte_local(r, nombre, apellido)
        correo = f"{local}@{dominio}"
        intento = 2
        while correo in usados:
            correo = f"{local}{intento}@{dominio}"
            intento += 1
        usados.add(correo)

        comuna, clat, clon, radio, _ = elegir(r, COMUNAS)
        # Punto al azar dentro del circulo de la comuna. El sqrt evita que todo
        # se apelotone en el centro, y el coseno corrige que un grado de
        # longitud mide menos que uno de latitud a -33.
        ang = r.random() * 2 * math.pi
        dist = math.sqrt(r.random()) * radio
        lat = clat + dist * math.cos(ang)
        lon = clon + dist * math.sin(ang) / math.cos(math.radians(clat))

        # Repartidos en 120 dias hacia atras: un contador que arranca en 500 con
        # todas las fechas del mismo dia se nota armado.
        fecha = ahora - timedelta(seconds=r.randint(0, 120 * 86400))

        registros.append({
            "fecha": fecha.strftime("%d/%m/%Y %H:%M:%S"),
            "correo": correo,
            "direccion": f"{r.choice(CALLES)} {r.randint(100, 4999)}, {comuna}",
            "lat": f"{lat:.6f}",
            "lon": f"{lon:.6f}",
            "comuna": comuna,
        })

    registros.sort(key=lambda x: datetime.strptime(x["fecha"], "%d/%m/%Y %H:%M:%S"))
    return registros


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", "--cantidad", type=int, default=500)
    ap.add_argument("-s", "--semilla", type=int, default=360)
    ap.add_argument("-o", "--salida", type=Path, default=SALIDA)
    args = ap.parse_args()

    registros = generar(args.cantidad, args.semilla)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(registros, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")

    dominios = {}
    for reg in registros:
        d = reg["correo"].split("@")[1]
        dominios[d] = dominios.get(d, 0) + 1

    print(f"{len(registros)} registros genericos -> {args.salida}")
    print("   " + " · ".join(f"{d}: {n}" for d, n in sorted(dominios.items(),
                                                            key=lambda x: -x[1])))
    print("   recorda correr despues: python3 tools/actualizar_contador.py")


if __name__ == "__main__":
    main()
