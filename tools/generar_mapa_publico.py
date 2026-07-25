#!/usr/bin/env python3
"""Genera la version PUBLICA del mapa de demanda: sitio/mapa.html

A diferencia de mapa-detallado.html (local, con un marcador por domicilio),
esta version solo contiene CONTEOS POR COMUNA. No lleva direcciones, ni
correos, ni coordenadas de casas: se publica en GitHub Pages.

Dos decisiones de privacidad, deliberadas:

1. Cada circulo se ubica en el CENTRO OFICIAL de la comuna, geocodificado
   aparte. No se usa el promedio de los domicilios: con pocos registros ese
   promedio queda pegado a una casa real.

2. Las comunas con menos de MINIMO pre-registros no se dibujan; se suman en
   "Otras comunas". Un circulo solo sobre una comuna con 1 registro apunta,
   en la practica, a ese domicilio.

    python3 generar_mapa_publico.py
"""

import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from html import escape
from pathlib import Path

from generar_mapa import cargar, RAMPA

# Este si escribe adentro del repo, y puede: son conteos por comuna, sin
# domicilios ni correos. El que lleva direcciones es generar_mapa.py, que escribe
# afuera a proposito.
RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "mapa.html"
CACHE = Path(__file__).resolve().parent / "comunas_centroides.json"

# Umbral por debajo del cual una comuna no se dibuja sola.
MINIMO = 3

UA = "REP-DATA-360-mapa/1.0 (wildcodeai@gmail.com)"


def centroides(comunas):
    """Centro oficial de cada comuna. Se cachea: no cambia y es 1 req/seg."""
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    faltan = [c for c in comunas if c not in cache]

    for i, comuna in enumerate(faltan):
        if i:
            time.sleep(1.1)                      # politica de uso de Nominatim
        q = urllib.parse.urlencode({
            "q": f"{comuna}, Chile", "countrycodes": "cl",
            "format": "json", "limit": "1",
        })
        pedido = urllib.request.Request(
            "https://nominatim.openstreetmap.org/search?" + q,
            headers={"User-Agent": UA},
        )
        try:
            with urllib.request.urlopen(pedido, timeout=20) as r:
                res = json.load(r)
            cache[comuna] = ([round(float(res[0]["lat"]), 5),
                              round(float(res[0]["lon"]), 5)] if res else None)
            print(f"   centro de {comuna}: {cache[comuna]}")
        except Exception as e:
            print(f"   no se pudo ubicar {comuna}: {e}")
            cache[comuna] = None

    if faltan:
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    return cache


def color_de(n, maximo):
    if maximo <= 0:
        return RAMPA[1]
    idx = min(len(RAMPA) - 1, int((n / maximo) * (len(RAMPA) - 1) + 0.5))
    return RAMPA[max(1, idx)]


BANNER_DEMO = """
  <div style="background:#FDF6E3;border:1px solid #F6C544;border-radius:12px;
       padding:14px 18px;font-size:13.5px;line-height:1.55;margin-bottom:20px">
    <b>Datos de demostración — la base de estas cifras es sintética.</b>
    Se generó para mostrar cómo se ve el mapa cuando haya demanda real, y no
    corresponde a personas ni a domicilios. <span id="bannerMezcla"></span>
    El mapa hecho solo con pre-registros reales está en
    <a href="./mapa.html">mapa.html</a>.
  </div>"""

# Solo para el mapa de demostracion. El "Pre-registros" de arriba se hornea al
# generar el HTML, asi que se queda congelado mientras el contador de la portada
# sigue subiendo: las dos paginas terminan diciendo numeros distintos del mismo
# dato. Esto lo lee de datos/contador.json, que es la misma fuente que usa la
# portada.
#
# El mapa REAL (mapa.html) no lleva esto a proposito: contador.json incluye la
# base sintetica, y sumarsela al mapa de datos reales seria inflarlo.
SYNC_CONTADOR = """
<script>
(function () {
  var dibujados = __DIBUJADOS__;
  var kpi = document.getElementById('kpiPreregistros');
  var nota = document.getElementById('kpiDesfase');
  var mezcla = document.getElementById('bannerMezcla');
  if (!kpi) return;

  fetch('./datos/contador.json', { cache: 'no-store' }).then(function (r) {
    if (!r.ok) throw new Error('contador.json: ' + r.status);
    return r.json();
  }).then(function (c) {
    var total = +c.total || 0;
    if (!total) return;

    // El +1 de quien acaba de registrarse. La portada lo suma en el acto, sin
    // esperar a que alguien regenere contador.json; si el mapa no hace lo mismo,
    // las dos paginas muestran numeros distintos justo para la persona que las
    // esta mirando. Misma clave y misma regla de fechas que index.html.
    try {
      var marca = localStorage.getItem('repdata360:registrado') || '';
      if (c.actualizado && marca > c.actualizado) total += 1;
    } catch (e) {
      // localStorage bloqueado (modo privado, cookies de terceros): sin el +1
      // el mapa muestra el numero del archivo, que es el que ve todo el mundo.
    }

    kpi.textContent = total.toLocaleString('es-CL');

    // El banner dice que la base es sintetica. Cuando el mapa ya lleva mezclados
    // pre-registros de verdad, hay que decirlo ahi mismo: si no, el aviso pasa a
    // ser falso justo en la pagina donde esa gente esta contada.
    var reales = +c.reales || 0;
    if (reales > 0 && mezcla) {
      mezcla.textContent = reales === 1
        ? 'A esa base se le suma 1 pre-registro real, agregado por comuna.'
        : 'A esa base se le suman ' + reales + ' pre-registros reales, agregados por comuna.';
    }

    // El desglose por comuna se hornea al generar el mapa. Si el contador ya
    // suma pre-registros que todavia no se dibujaron, hay que decirlo: si no,
    // el total de arriba no cuadra con la suma del ranking de abajo.
    var faltan = total - dibujados;
    if (faltan > 0 && nota) {
      nota.textContent = faltan === 1
        ? '1 pre-registro más reciente todavía no está dibujado en el mapa: entra al regenerarlo.'
        : faltan + ' pre-registros más recientes todavía no están dibujados en el mapa: entran al regenerarlo.';
      nota.style.display = 'block';
    }
  }).catch(function () {
    // Sin contador.json queda el numero horneado, que es exactamente el que
    // dibuja el mapa. Nunca se ve vacio ni en cero.
  });
})();
</script>"""


# El mapa de datos reales no puede leer el total de contador.json: ese numero
# incluye la base sintetica y aca solo se dibujan pre-registros de verdad. Lo
# unico que necesita del JSON es el instante del corte, para saber si quien esta
# mirando se pre-registro despues y todavia no entro al archivo.
SYNC_PROPIO = """
<script>
(function () {
  var dibujados = __DIBUJADOS__;
  var kpi = document.getElementById('kpiPreregistros');
  var nota = document.getElementById('kpiDesfase');
  if (!kpi) return;

  var marca = '';
  try {
    marca = localStorage.getItem('repdata360:registrado') || '';
  } catch (e) {
    return;   // localStorage bloqueado: queda el numero horneado, el de todos.
  }
  if (!marca) return;

  fetch('./datos/contador.json', { cache: 'no-store' }).then(function (r) {
    if (!r.ok) throw new Error('contador.json: ' + r.status);
    return r.json();
  }).then(function (c) {
    // Misma regla y misma clave que index.html: solo suma si el pre-registro es
    // posterior al corte. Si ya entro al archivo, esta contado en 'dibujados'.
    var corte = c.generado || c.actualizado || '';
    if (!corte || marca <= corte) return;

    kpi.textContent = (dibujados + 1).toLocaleString('es-CL');

    // El desglose por comuna se hornea al generar el mapa, asi que el punto de
    // esta persona todavia no esta. Decirlo evita la lectura de que el envio se
    // perdio, y de paso explica por que el total no cuadra con el ranking.
    if (nota) {
      nota.textContent = 'Tu pre-registro ya está guardado, pero todavía no está '
        + 'dibujado en el mapa: entra en la próxima actualización. Las comunas con '
        + 'menos de ' + __MINIMO__ + ' pre-registros tampoco se muestran por separado.';
      nota.style.display = 'block';
    }
  }).catch(function () {
    // Sin contador.json queda el numero horneado, que es el que dibuja el mapa.
  });
})();
</script>"""


def construir(publicas, ocultas, total, demo=False):
    maximo = publicas[0][1] if publicas else 0
    lider = publicas[0][0] if publicas else "—"
    n_comunas = len(publicas) + len(ocultas)

    puntos = [{"comuna": c, "n": n, "lat": p[0], "lon": p[1],
               "color": color_de(n, maximo)}
              for c, n, p in publicas if p]

    filas = "".join(
        f"""
        <div class="fila">
          <div class="nombre">{escape(c)}</div>
          <div class="pista"><div class="barra" style="width:{n / maximo * 100:.1f}%;background:{color_de(n, maximo)}"></div></div>
          <div class="valor">{n}</div>
        </div>"""
        for c, n, _ in publicas
    )

    if ocultas:
        suma = sum(n for _, n in ocultas)
        filas += f"""
        <div class="fila">
          <div class="nombre otras">Otras comunas</div>
          <div class="pista"><div class="barra otras-barra" style="width:{suma / maximo * 100 if maximo else 0:.1f}%"></div></div>
          <div class="valor">{suma}</div>
        </div>"""

    if not publicas and not ocultas:
        filas = '<p class="vacio">Todavía no hay pre-registros. Cuando lleguen, aparecen acá.</p>'

    tabla = "".join(
        f"<tr><td>{escape(c)}</td><td>{n}</td><td>{n / total * 100:.0f}%</td></tr>"
        for c, n, _ in publicas
    )
    if ocultas:
        suma = sum(n for _, n in ocultas)
        tabla += (f"<tr><td>Otras comunas ({len(ocultas)})</td><td>{suma}</td>"
                  f"<td>{suma / total * 100:.0f}%</td></tr>")
    tabla = tabla or '<tr><td colspan="3">Sin datos todavía</td></tr>'

    nota_umbral = (
        f"<p class=\"umbral\">Las comunas con menos de {MINIMO} pre-registros no se "
        f"muestran por separado: se suman en «Otras comunas». Con números chicos, "
        f"un punto sobre el mapa señalaría un domicilio.</p>"
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>REP DATA 360 · Demanda por comuna{" (datos de demostración)" if demo else ""}</title>
<meta name="description" content="{"Ejemplo con datos sintéticos de cómo se ve la demanda de bolsas REP DATA 360 por comuna." if demo else "Dónde se concentra la demanda de bolsas REP DATA 360, agregada por comuna."}">
<meta name="robots" content="noindex">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  :root{{
    --verde-oscuro:#1E3A2E; --verde:#2FB179; --verde-fuerte:#1F8A5C;
    --menta:#F2FBF6; --borde:#BFD6CB; --tinta-suave:#55685E;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;padding:28px 20px 48px;background:var(--menta);
    font-family:Calibri,"Segoe UI",system-ui,sans-serif;color:var(--verde-oscuro)}}
  .hoja{{max-width:1020px;margin:0 auto}}
  h1{{font-family:"Arial Black",Arial,sans-serif;font-weight:900;font-size:24px;margin:0 0 4px}}
  .sub{{margin:0 0 24px;color:var(--tinta-suave);font-size:14px}}
  .kpis{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:20px}}
  .kpi{{background:#fff;border:1px solid var(--borde);border-radius:14px;
    padding:16px 20px;min-width:190px;flex:1}}
  .kpi .et{{font-size:11px;letter-spacing:1.4px;text-transform:uppercase;
    color:var(--tinta-suave);margin:0 0 6px}}
  .kpi .num{{font-size:44px;line-height:1;font-weight:700;margin:0}}
  .kpi .txt{{font-size:26px;line-height:1.15;font-weight:700;margin:0}}
  .panel{{background:#fff;border:1px solid var(--borde);border-radius:14px;
    padding:20px;margin-bottom:20px}}
  .panel h2{{font-size:15px;margin:0 0 4px}}
  .panel .nota{{font-size:12.5px;color:var(--tinta-suave);margin:0 0 16px}}
  #mapa{{height:460px;border-radius:10px;border:1px solid var(--borde)}}
  .escala{{display:flex;align-items:center;gap:10px;margin-top:12px;
    font-size:12px;color:var(--tinta-suave)}}
  .tira{{flex:1;max-width:260px;height:10px;border-radius:5px;
    background:linear-gradient(90deg,{",".join(RAMPA)})}}
  .fila{{display:grid;grid-template-columns:150px 1fr 44px;align-items:center;
    gap:12px;margin-bottom:8px}}
  .nombre{{font-size:13.5px;text-align:right;overflow:hidden;
    text-overflow:ellipsis;white-space:nowrap}}
  .nombre.otras{{color:var(--tinta-suave);font-style:italic}}
  .pista{{background:#EFF5F1;border-radius:4px;height:22px;overflow:hidden}}
  .barra{{height:100%;border-radius:0 4px 4px 0;min-width:3px}}
  .otras-barra{{background:repeating-linear-gradient(45deg,#BFD6CB,#BFD6CB 4px,#D7E5DC 4px,#D7E5DC 8px)}}
  .valor{{font-size:13.5px;font-weight:700}}
  .vacio{{color:var(--tinta-suave);font-size:14px;margin:0}}
  table{{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:6px}}
  th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid #E6EFE9}}
  th{{font-size:11px;letter-spacing:1.2px;text-transform:uppercase;
    color:var(--tinta-suave);font-weight:400}}
  td:nth-child(2),td:nth-child(3),th:nth-child(2),th:nth-child(3){{text-align:right;width:90px}}
  details{{margin-top:14px}}
  summary{{cursor:pointer;font-size:13px;color:var(--tinta-suave)}}
  .umbral{{font-size:12.5px;color:var(--tinta-suave);margin:16px 0 0;
    padding-top:14px;border-top:1px solid #E6EFE9}}
  .pie{{font-size:11.5px;color:var(--tinta-suave);text-align:center;
    margin-top:22px;line-height:1.6}}
  .desfase{{font-size:12.5px;color:var(--tinta-suave);margin:-8px 0 20px}}
  a{{color:var(--verde-fuerte)}}
</style>
</head>
<body>
<div class="hoja">

  <h1>Demanda de bolsas por comuna</h1>
  <p class="sub">REP DATA 360 · Proyecto de Innovación Ley REP N°20.920</p>
{BANNER_DEMO if demo else ""}

  <div class="kpis">
    <div class="kpi"><p class="et">Pre-registros</p><p class="num" id="kpiPreregistros">{total}</p></div>
    <div class="kpi"><p class="et">Comuna con más demanda</p><p class="txt">{escape(lider)}</p></div>
    <div class="kpi"><p class="et">Comunas alcanzadas</p><p class="num">{n_comunas}</p></div>
  </div>
  <p class="desfase" id="kpiDesfase" style="display:none"></p>

  <div class="panel">
    <h2>Dónde se concentra</h2>
    <p class="nota">Un círculo por comuna, ubicado en su centro. Mientras más grande y
       más oscuro, más pre-registros. Pasa el cursor por encima para ver el detalle.</p>
    <div id="mapa"></div>
    <div class="escala"><span>Menos</span><div class="tira"></div><span>Más demanda</span></div>
  </div>

  <div class="panel">
    <h2>Ranking de comunas</h2>
    <p class="nota">Cantidad de pre-registros por comuna, de mayor a menor.</p>
    {filas}
    <details>
      <summary>Ver como tabla</summary>
      <table>
        <thead><tr><th>Comuna</th><th>Pre-reg.</th><th>Share</th></tr></thead>
        <tbody>{tabla}</tbody>
      </table>
    </details>
    {nota_umbral}
  </div>

  <p class="pie">
    Datos agregados por comuna. Esta página no contiene domicilios ni datos de personas.<br>
    <a href="./">← Volver a REP DATA 360</a> · Mapa © OpenStreetMap · Teselas © CARTO
  </p>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var COMUNAS = {json.dumps(puntos, ensure_ascii=False)};

var mapa = L.map('mapa', {{ scrollWheelZoom: false }}).setView([-33.45, -70.66], 10);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '&copy; OpenStreetMap &copy; CARTO', maxZoom: 19
}}).addTo(mapa);

if (COMUNAS.length) {{
  var maxN = Math.max.apply(null, COMUNAS.map(function (c) {{ return c.n; }}));

  // Area proporcional al conteo: el radio va con la raiz, si no las comunas
  // grandes se ven exageradas.
  function radioBase(c) {{ return 7 + 22 * Math.sqrt(c.n / maxN); }}

  var capas = COMUNAS.map(function (c) {{
    var capa = L.circleMarker([c.lat, c.lon], {{
      radius: radioBase(c), color: '#FFFFFF', weight: 2,
      fillColor: c.color, fillOpacity: 0.85
    }}).bindTooltip(
      '<b>' + c.comuna + '</b><br>' + c.n + ' pre-registro' + (c.n === 1 ? '' : 's'),
      {{ direction: 'top' }}
    ).addTo(mapa);
    return {{ c: c, capa: capa }};
  }});

  // El radio de un circleMarker es fijo en pixeles, asi que al alejarse las
  // comunas vecinas se solapan hasta volverse una mancha. Se reescala con el
  // zoom para que en vista nacional sigan separadas.
  function ajustarRadios() {{
    var f = Math.min(1.8, Math.max(0.4, Math.pow(1.28, mapa.getZoom() - 10)));
    capas.forEach(function (o) {{
      o.capa.setRadius(Math.max(3.5, radioBase(o.c) * f));
    }});
  }}
  mapa.on('zoomend', ajustarRadios);

  // Encuadre: las comunas que concentran el 80% de la demanda. Si se encuadra
  // todo el pais, una comuna lejana con pocos registros aleja el mapa hasta que
  // el nucleo real queda del tamano de un punto. El resto sigue ahi: basta
  // alejar el zoom, y el ranking de abajo las lista todas.
  var total = COMUNAS.reduce(function (a, c) {{ return a + c.n; }}, 0);
  var orden = COMUNAS.slice().sort(function (a, b) {{ return b.n - a.n; }});
  var nucleo = [], suma = 0;
  for (var i = 0; i < orden.length; i++) {{
    nucleo.push(orden[i]);
    suma += orden[i].n;
    if (suma >= total * 0.8 && nucleo.length >= 3) break;
  }}

  mapa.fitBounds(nucleo.map(function (c) {{ return [c.lat, c.lon]; }}),
                 {{ padding: [55, 55], maxZoom: 12 }});
  ajustarRadios();
}}
</script>
{(SYNC_CONTADOR if demo else SYNC_PROPIO).replace("__DIBUJADOS__", str(total)).replace("__MINIMO__", str(MINIMO))}
</body>
</html>
"""


def main():
    # Sin argumentos: datos reales -> sitio/mapa.html (el que se publica).
    # Con argumentos: cualquier otro par entrada/salida, p.ej. los datos de
    # demostracion, que llevan un banner y NO se publican.
    import sys
    entrada = sys.argv[1] if len(sys.argv) > 1 else None
    salida = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else SALIDA
    demo = bool(entrada)

    puntos, _ = cargar(entrada)
    total = len(puntos)
    conteo = Counter(p["comuna"] or "Sin comuna" for p in puntos)

    grandes = [(c, n) for c, n in conteo.most_common() if n >= MINIMO]
    ocultas = [(c, n) for c, n in conteo.most_common() if n < MINIMO]

    centros = centroides([c for c, _ in grandes]) if grandes else {}
    publicas = [(c, n, centros.get(c)) for c, n in grandes]

    salida.write_text(construir(publicas, ocultas, total, demo), encoding="utf-8")
    # relative_to revienta si la salida cae fuera del repo, y salidas de afuera
    # son legitimas (una prueba en /tmp, por ejemplo).
    try:
        nombre = salida.relative_to(RAIZ)
    except ValueError:
        nombre = salida
    print(f"{nombre} generado · {total} pre-registro(s) · "
          f"{len(publicas)} comuna(s) en el mapa, {len(ocultas)} agrupada(s) en «Otras»"
          + ("  [DEMOSTRACIÓN]" if demo else ""))


if __name__ == "__main__":
    main()
