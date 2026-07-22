# REP DATA 360

REP DATA 360 es un Proyecto de Innovación enmarcado en la Ley REP N°20.920 (Chile). Propone una bolsa de reciclaje domiciliario con un indicador químico que cambia de color según su nivel de limpieza (verde: limpia, ámbar: intermedia, roja: contaminada) y un chip RFID que registra la hora y el lugar de retiro. La idea es dar trazabilidad al reciclaje desde el hogar, antes de que el camión llegue a la planta.

Sitio publicado: **https://wildcodeai.github.io/rep-data-360/**

> [!NOTE]
> **El formulario volvió a guardar datos.** El backend de Google Apps Script quedaba caído con **HTTP 401** cada vez que había que redesplegarlo a mano, así que se reemplazó por un **Google Formulario**, que no se despliega y por lo tanto no tiene ese modo de falla. Las respuestas caen en la planilla vinculada al formulario.
>
> El formulario ahora también guarda **latitud, longitud y comuna** de cada dirección verificada, que es lo que alimenta el mapa de calor de demanda por zona.

## Estructura del proyecto

```
.
├── index.html                          Todo el sitio: HTML, CSS y JS inline en un solo archivo.
├── apps-script.gs                      Backend anterior (Apps Script). Ya no se usa, se conserva como referencia.
├── assets/                             Imágenes y video usados por index.html.
│   ├── hero-laboratorio.webp
│   ├── mascota-verde.webp / mascota-ambar.webp / mascota-roja.webp
│   ├── etiqueta-ambar.webp / etiqueta-roja.webp
│   ├── og-image.jpg                    Imagen de previsualización al compartir el link (1200x630).
│   └── video-pitch.mp4
├── REP_DATA_360_Pitch - Reparado.pptx  Pitch deck del proyecto.
└── wireframe-original.jpeg             Boceto a mano del que salió el diseño de la página.
```

`index.html` no tiene dependencias externas de build: no hay `npm`, ni bundler, ni framework. Todo el CSS vive en un `<style>` dentro del `<head>` y todo el JS del formulario vive en un `<script>` al final del `<body>`.

## Cómo desarrollar localmente

Como el formulario usa `fetch` (para consultar direcciones en Nominatim y para enviar el pre-registro al Google Formulario), no alcanza con abrir `index.html` directamente desde el navegador con `file://`: los navegadores bloquean o restringen `fetch` bajo el protocolo `file://` por política de CORS/origen, así que hay que servir la carpeta por HTTP.

Desde la raíz del repo:

```bash
python3 -m http.server 8000
```

Y abrir `http://localhost:8000/` en el navegador.

## Cómo se despliega

El sitio se sirve con **GitHub Pages** directamente desde la raíz de la rama `main`. No hay paso de build: cada `merge` a `main` dispara un redespliegue automático que tarda aproximadamente **1 minuto**.

GitHub Pages usa un CDN que cachea el contenido por unos **10 minutos**. Si hacés un cambio y no lo ves reflejado, probá:

- Un hard refresh (`Ctrl+Shift+R` / `Cmd+Shift+R`).
- Agregar un parámetro de cache-busting a la URL, por ejemplo `https://wildcodeai.github.io/rep-data-360/?v=2`.
- Esperar los ~10 minutos de caché del CDN antes de asumir que algo salió mal.

## Formulario de pre-registro

El formulario (sección `#registro` de `index.html`) le pide a la persona su correo y su dirección para enviarle una bolsa gratis. El flujo es:

1. **Validación de dirección**: cuando la persona termina de escribir (evento `blur`) o al enviar, el JS consulta una vez la API pública de **Nominatim / OpenStreetMap** (`nominatim.openstreetmap.org/search`) restringida a Chile (`countrycodes=cl`).
   - **Una sola coincidencia** → queda verificada.
   - **Varias** → se muestran para que elija. No se adivina por ella: "Los Alerces 890" tiene 5 coincidencias en Chile y la primera está en Viña del Mar, no en Valparaíso.
   - **Ninguna** → se muestra el error y no se envía.

   Escribir **no** dispara consultas. La [política de uso de Nominatim](https://operations.osmfoundation.org/policies/nominatim/) prohíbe explícitamente el autocompletado y limita a 1 consulta por segundo; una consulta por tecla es la forma más rápida de que bloqueen la IP. Tampoco se repite la búsqueda de un texto ya consultado.

   Si el servicio de Nominatim falla, el formulario no bloquea el envío (se prioriza no perder el lead): el registro se guarda sin coordenadas y aparece como "sin ubicar" en el mapa.

2. **Dirección normalizada**: se guarda `calle número, comuna` (`Avenida Providencia 1234, Providencia`) en vez del `display_name` crudo de Nominatim (`Normandie, 1234, Avenida Providencia, Barrio Tajamar, Providencia, Provincia de Santiago, ...`), que es ruidoso para despachar una bolsa. Cuando Nominatim resuelve la calle pero no el número, **se conserva el número que escribió la persona** —perderlo dejaría la dirección inservible para la entrega— y el estado lo dice: *"Calle y comuna verificadas — revisa que el número esté bien"*.
3. **Ubicación**: al aceptar una dirección se guardan también su **latitud, longitud y comuna**, tomadas de la misma respuesta de Nominatim. Es lo que permite dibujar el mapa de calor por zona.
4. **Honeypot anti-bots**: hay un campo oculto (`empresa`) fuera de la vista, con `tabindex="-1"` y `aria-hidden`. Si viene lleno, es porque lo rellenó un bot, así que se simula un envío exitoso sin mandar ningún dato real.
5. **Envío**: los datos se mandan por `POST` como `FormData` al `formResponse` de un **Google Formulario** (constante `FORM` en el `<script>` de `index.html`), que actúa como buzón sin servidor propio. Cada campo viaja con el `entry.XXXX` de su pregunta.

### Un detalle que cuesta caro si se olvida

La planilla de respuestas está en **configuración regional chilena**, donde el punto es separador de miles. Si las coordenadas se mandan como `-33.444710`, Sheets las interpreta como el entero `-33.444.710` y **se pierde el decimal**: el punto queda en cualquier parte menos en Chile. Por eso se mandan con **coma decimal** (`-33,444710`), que es lo que esa configuración espera.

### Compromiso conocido: la confirmación es optimista

Un Google Formulario no manda cabeceras CORS, así que el envío obliga a `mode:'no-cors'` y la respuesta queda *opaque*: el navegador no deja leer el status. El `fetch` **sí rechaza** si la red falla, así que un error de conexión se detecta; lo que no se puede distinguir es un 200 de un 500 del lado de Google.

Es un paso atrás respecto del Apps Script, que sí permitía confirmar el guardado de verdad. Se aceptó a cambio de eliminar el redespliegue manual, que es exactamente lo que rompió el formulario. **La fuente de verdad es la planilla**: conviene revisarla cada tanto.

### Si hay que cambiar el formulario

Los `entry.XXXX` son los IDs internos de cada pregunta. Si agregás, borrás o recreás preguntas, cambian: hay que sacarlos de nuevo del HTML público del formulario y actualizar `FORM.campos` en `index.html`.

`apps-script.gs` se conserva solo como referencia del backend anterior; **ya no se usa**.

## Mapa de calor de demanda

Las columnas `Lat`, `Lon` y `Comuna` de la planilla existen para responder **dónde se concentra la demanda**: qué comunas piden más bolsas, que es el dato que le sirve a un sistema de gestión para priorizar rutas.

El generador (`generar_mapa.py`) vive **fuera de este repo**, junto a la planilla exportada, y produce un `mapa.html` con capa de calor, ranking de comunas y tabla. No se versiona acá a propósito: el mapa contiene domicilios de personas y este repositorio es público.

El lector de coordenadas tolera los tres formatos que puede dejar Sheets (`-33.44`, `-33,44` y el `-33.444.710` roto por el separador de miles) y descarta lo que caiga fuera de Chile, así que un cambio de configuración regional en la planilla no rompe el mapa.

## Privacidad

El formulario recolecta **correo electrónico y dirección domiciliaria**, que son datos personales bajo la Ley 19.628 sobre Protección de la Vida Privada (Chile). Recomendaciones mientras dure el piloto:

- No dejar la Google Sheet con acceso público ni compartida más allá de quienes necesitan gestionarla.
- Usar los datos solo para lo que se le dijo a la persona (coordinar entrega y retiro de la bolsa piloto).
- Borrar los datos recolectados una vez que termine el piloto.

## Equipo

- César Guerrero Torres
- Jaritza Ramírez Valles
- Sandy Suárez Urriola
- Valentina Villalba Lleufo
