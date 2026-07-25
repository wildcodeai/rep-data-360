#!/usr/bin/env python3
"""Genera mapa.html (mapa de calor + ranking de comunas) desde datos.json.

datos.json son las respuestas de la planilla de Google, con las columnas
fecha, correo, direccion, lat, lon, comuna.

    python3 generar_mapa.py

El archivo mapa-detallado.html es local a proposito: contiene direcciones y coordenadas
de personas, asi que NO se publica (esta en .gitignore).
"""

import csv
import json
from collections import Counter
from html import escape
from pathlib import Path

# Este script vive DENTRO del repo publico, pero lo que produce lleva domicilios
# y correos, asi que entra y sale de la carpeta de trabajo local, que esta un
# nivel mas arriba y no es un repositorio. La regla no es una convencion: es lo
# unico que impide que un `git add .` distraido publique las direcciones de las
# personas. Ver escribir_fuera_del_repo().
REPO = Path(__file__).resolve().parent.parent
TRABAJO = REPO.parent
DATOS = TRABAJO / "datos.json"
SALIDA = TRABAJO / "mapa-detallado.html"


def escribir_fuera_del_repo(salida, contenido):
    """Escribe, salvo que la ruta caiga adentro del repo publico.

    Es la segunda linea de defensa detras del .gitignore: si alguien pasa
    `sitio/mapa-detallado.html` como salida, este mapa lleva un marcador por
    domicilio y el repo es publico. Preferimos fallar ruidosamente.
    """
    salida = Path(salida).resolve()
    if salida == REPO or REPO in salida.parents:
        raise SystemExit(
            f"ERROR: {salida} cae adentro del repo publico, y este mapa lleva "
            f"domicilios en los tooltips. Elegi una ruta de afuera "
            f"(por ejemplo {SALIDA}).")
    salida.write_text(contenido, encoding="utf-8")
    return salida

# Chile continental, para descartar coordenadas imposibles.
LAT_MIN, LAT_MAX = -56.0, -17.0
LON_MIN, LON_MAX = -76.0, -66.0

# Rampa secuencial verde de la PPT, clara -> oscura (monotonica en luminosidad).
RAMPA = ["#DFF5E9", "#8BD4A8", "#2FB179", "#1F8A5C", "#1E3A2E"]


def coordenada(valor, digitos_enteros=2):
    """Interpreta una coordenada tolerando los formatos que puede dejar Sheets.

    Acepta  -33.058421   (punto decimal)
            -33,058421   (coma decimal, configuracion regional chilena)
            -33.444.710  (punto como separador de miles: el decimal se perdio)
    """
    s = str(valor).strip()
    if not s:
        return None
    negativo = s.startswith("-")
    s = s.lstrip("+-").strip()

    if "," in s and "." in s:            # -33.444,71
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                        # -33,058421
        s = s.replace(",", ".")
    elif s.count(".") > 1:                # -33.444.710  (danado)
        d = s.replace(".", "")
        s = d[:digitos_enteros] + "." + d[digitos_enteros:]

    try:
        x = float(s)
    except ValueError:
        return None

    # Si el decimal se perdio del todo (-33444710), lo reponemos.
    limite = 90 if digitos_enteros == 2 else 180
    intentos = 0
    while abs(x) > limite and intentos < 8:
        x /= 10.0
        intentos += 1

    return -x if negativo else x


# Encabezados del CSV que exporta Google Sheets -> nombres que usamos aca.
COLUMNAS_CSV = {
    "marca temporal": "fecha", "timestamp": "fecha",
    "correo": "correo", "correo electrónico": "correo",
    "dirección": "direccion", "direccion": "direccion",
    "lat": "lat", "latitud": "lat",
    "lon": "lon", "longitud": "lon",
    "comuna": "comuna",
}


def leer_csv(ruta):
    """Lee el CSV que baja de la planilla (Archivo > Descargar > CSV)."""
    with ruta.open(newline="", encoding="utf-8-sig") as f:
        return [
            {COLUMNAS_CSV.get((k or "").strip().lower(), (k or "").strip().lower()): v
             for k, v in fila.items()}
            for fila in csv.DictReader(f)
        ]


def cargar(ruta=None, sin_pruebas=False):
    """Acepta el .json de siempre o el .csv exportado de la planilla.

    sin_pruebas descarta las filas .demo@ que deja el generador al probar el
    circuito del formulario. Solo aplica al CSV de la planilla: en un dataset de
    demostracion los .demo@ SON el dataset, y filtrarlos lo vaciaria.
    """
    ruta = Path(ruta) if ruta else DATOS
    if not ruta.exists():
        return [], []

    if ruta.suffix.lower() == ".csv":
        filas = leer_csv(ruta)
        if sin_pruebas:
            pruebas = [f for f in filas
                       if ".demo@" in (f.get("correo") or "").lower()]
            if pruebas:
                filas = [f for f in filas if f not in pruebas]
                print(f"   {len(pruebas)} fila(s) .demo@ descartada(s): "
                      "son envios de prueba del generador, no personas")
    else:
        filas = json.loads(ruta.read_text(encoding="utf-8"))
    buenas, descartadas = [], []
    for f in filas:
        # Filas vacias: quedan al borrar el contenido de una respuesta sin
        # borrar la fila. No son un error, no hay nada que reportar.
        if not any(str(f.get(c) or "").strip()
                   for c in ("correo", "direccion", "lat", "lon", "comuna")):
            continue

        lat = coordenada(f.get("lat"))
        lon = coordenada(f.get("lon"))
        if lat is None or lon is None:
            descartadas.append((f, "sin coordenadas"))
            continue
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            descartadas.append((f, f"fuera de Chile ({lat:.4f}, {lon:.4f})"))
            continue
        buenas.append({
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "comuna": (f.get("comuna") or "Sin comuna").strip(),
            "direccion": (f.get("direccion") or "").strip(),
            "fecha": (f.get("fecha") or "").strip(),
        })
    return buenas, descartadas


def color_de(n, maximo):
    """Paso de la rampa segun la intensidad relativa."""
    if maximo <= 0:
        return RAMPA[0]
    idx = min(len(RAMPA) - 1, int((n / maximo) * (len(RAMPA) - 1) + 0.5))
    return RAMPA[max(1, idx)]


def construir(puntos, descartadas):
    conteo = Counter(p["comuna"] for p in puntos)
    ranking = conteo.most_common()
    total = len(puntos)
    maximo = ranking[0][1] if ranking else 0
    lider = ranking[0][0] if ranking else "—"

    # Filas del ranking: barra + etiqueta directa con el numero.
    filas = []
    for comuna, n in ranking:
        ancho = (n / maximo * 100) if maximo else 0
        filas.append(f"""
        <div class="fila">
          <div class="nombre">{escape(comuna)}</div>
          <div class="pista"><div class="barra" style="width:{ancho:.1f}%;background:{color_de(n, maximo)}"></div></div>
          <div class="valor">{n}</div>
        </div>""")
    ranking_html = "".join(filas) or '<p class="vacio">Todavía no hay pre-registros.</p>'

    tabla = "".join(
        f"<tr><td>{escape(c)}</td><td>{n}</td>"
        f"<td>{n / total * 100:.0f}%</td></tr>"
        for c, n in ranking
    ) or '<tr><td colspan="3">Sin datos</td></tr>'

    aviso = ""
    if descartadas:
        detalle = "".join(
            f"<li>{escape(str(f.get('direccion') or f.get('correo') or '?'))} — {escape(motivo)}</li>"
            for f, motivo in descartadas
        )
        aviso = (f'<div class="aviso"><b>{len(descartadas)} registro(s) sin ubicar</b>'
                 f'<ul>{detalle}</ul></div>')

    centro = ([sum(p["lat"] for p in puntos) / total, sum(p["lon"] for p in puntos) / total]
              if total else [-33.45, -70.66])

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>REP DATA 360 · Dónde se concentran los pre-registros</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  :root{{
    --verde-oscuro:#1E3A2E; --verde:#2FB179; --verde-fuerte:#1F8A5C;
    --menta:#F2FBF6; --borde:#BFD6CB; --tinta-suave:#55685E; --ambar:#F6C544;
  }}
  *{{box-sizing:border-box}}
  body{{
    margin:0; padding:28px 20px 48px; background:var(--menta);
    font-family:Calibri,"Segoe UI",system-ui,sans-serif; color:var(--verde-oscuro);
  }}
  .hoja{{max-width:1020px;margin:0 auto}}
  h1{{font-family:"Arial Black",Arial,sans-serif;font-weight:900;font-size:24px;margin:0 0 4px}}
  .sub{{margin:0 0 24px;color:var(--tinta-suave);font-size:14px}}

  .kpis{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:20px}}
  .kpi{{
    background:#fff;border:1px solid var(--borde);border-radius:14px;
    padding:16px 20px;min-width:190px;flex:1;
  }}
  .kpi .et{{font-size:11px;letter-spacing:1.4px;text-transform:uppercase;color:var(--tinta-suave);margin:0 0 6px}}
  .kpi .num{{font-size:44px;line-height:1;font-weight:700;margin:0}}
  .kpi .txt{{font-size:26px;line-height:1.15;font-weight:700;margin:0}}

  .panel{{background:#fff;border:1px solid var(--borde);border-radius:14px;padding:20px;margin-bottom:20px}}
  .panel h2{{font-size:15px;margin:0 0 4px}}
  .panel .nota{{font-size:12.5px;color:var(--tinta-suave);margin:0 0 16px}}

  #mapa{{height:460px;border-radius:10px;border:1px solid var(--borde)}}

  .escala{{display:flex;align-items:center;gap:10px;margin-top:12px;font-size:12px;color:var(--tinta-suave)}}
  .tira{{flex:1;max-width:260px;height:10px;border-radius:5px;
        background:linear-gradient(90deg,{",".join(RAMPA)})}}

  .fila{{display:grid;grid-template-columns:150px 1fr 44px;align-items:center;gap:12px;margin-bottom:8px}}
  .nombre{{font-size:13.5px;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .pista{{background:#EFF5F1;border-radius:4px;height:22px;overflow:hidden}}
  .barra{{height:100%;border-radius:0 4px 4px 0;min-width:3px}}
  .valor{{font-size:13.5px;font-weight:700}}
  .vacio{{color:var(--tinta-suave);font-size:14px;margin:0}}

  table{{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:6px}}
  th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid #E6EFE9}}
  th{{font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:var(--tinta-suave);font-weight:400}}
  td:nth-child(2),td:nth-child(3),th:nth-child(2),th:nth-child(3){{text-align:right;width:90px}}

  .aviso{{background:#FDF6E3;border:1px solid var(--ambar);border-radius:12px;padding:14px 18px;font-size:13px;margin-bottom:20px}}
  .aviso ul{{margin:8px 0 0;padding-left:18px}}
  details{{margin-top:14px}}
  summary{{cursor:pointer;font-size:13px;color:var(--tinta-suave)}}
  .pie{{font-size:11.5px;color:var(--tinta-suave);text-align:center;margin-top:22px;line-height:1.6}}
</style>
</head>
<body>
<div class="hoja">

  <h1>¿Dónde se concentran los pre-registros?</h1>
  <p class="sub">REP DATA 360 · Proyecto de Innovación Ley REP N°20.920</p>

  {aviso}

  <div class="kpis">
    <div class="kpi"><p class="et">Pre-registros ubicados</p><p class="num">{total}</p></div>
    <div class="kpi"><p class="et">Comuna con más demanda</p><p class="txt">{escape(lider)}</p></div>
    <div class="kpi"><p class="et">Comunas alcanzadas</p><p class="num">{len(ranking)}</p></div>
  </div>

  <div class="panel">
    <h2>Mapa de calor</h2>
    <p class="nota">Cada punto es un domicilio pre-registrado. Mientras más oscura la mancha,
       más concentración. Pasa el cursor sobre un punto para ver la dirección.</p>
    <div id="mapa"></div>
    <div class="escala">
      <span>Menos</span><div class="tira"></div><span>Más concentración</span>
    </div>
  </div>

  <div class="panel">
    <h2>Ranking de comunas</h2>
    <p class="nota">Cantidad de pre-registros por comuna, de mayor a menor.</p>
    {ranking_html}
    <details>
      <summary>Ver como tabla</summary>
      <table>
        <thead><tr><th>Comuna</th><th>Pre-reg.</th><th>Share</th></tr></thead>
        <tbody>{tabla}</tbody>
      </table>
    </details>
  </div>

  <p class="pie">
    Generado desde la planilla de respuestas · Contiene datos personales: no publicar.<br>
    Mapa © colaboradores de OpenStreetMap · Teselas © CARTO
  </p>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<script>
var PUNTOS = {json.dumps(puntos, ensure_ascii=False)};

var mapa = L.map('mapa', {{ scrollWheelZoom: false }}).setView({json.dumps(centro)}, PUNTOS.length > 1 ? 11 : 13);

// Base clara y desaturada para que el verde del calor se lea encima.
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '&copy; OpenStreetMap &copy; CARTO', maxZoom: 19
}}).addTo(mapa);

if (PUNTOS.length) {{
  L.heatLayer(PUNTOS.map(function (p) {{ return [p.lat, p.lon, 1]; }}), {{
    radius: 28, blur: 22, minOpacity: 0.35,
    gradient: {{ 0.0:'{RAMPA[0]}', 0.35:'{RAMPA[1]}', 0.6:'{RAMPA[2]}', 0.8:'{RAMPA[3]}', 1.0:'{RAMPA[4]}' }}
  }}).addTo(mapa);

  PUNTOS.forEach(function (p) {{
    L.circleMarker([p.lat, p.lon], {{
      radius: 5, color: '#FFFFFF', weight: 2,      // anillo de 2px sobre el calor
      fillColor: '{RAMPA[3]}', fillOpacity: 1
    }}).bindTooltip(
      '<b>' + (p.comuna || 'Sin comuna') + '</b><br>' + (p.direccion || ''),
      {{ direction: 'top' }}
    ).addTo(mapa);
  }});

  if (PUNTOS.length > 1) {{
    mapa.fitBounds(PUNTOS.map(function (p) {{ return [p.lat, p.lon]; }}), {{ padding: [45, 45] }});
  }}
}}
</script>
</body>
</html>
"""


def main():
    # Sin argumentos: datos reales -> mapa-detallado.html
    # Con argumentos: otro par entrada/salida (p.ej. los datos de demostracion).
    import sys
    entrada = sys.argv[1] if len(sys.argv) > 1 else None
    salida = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else SALIDA

    puntos, descartadas = cargar(entrada)
    escribir_fuera_del_repo(salida, construir(puntos, descartadas))
    print(f"{salida.name} generado · {len(puntos)} punto(s) ubicado(s), "
          f"{len(descartadas)} descartado(s)")
    for f, motivo in descartadas:
        print(f"   descartado: {f.get('correo', '?')} — {motivo}")


if __name__ == "__main__":
    main()
