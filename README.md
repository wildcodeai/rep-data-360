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
├── datos/
│   ├── registros-genericos.json        500 pre-registros sintéticos: la base del contador y del mapa.
│   └── contador.json                   Solo números. Es lo único que lee el contador del sitio.
├── tools/                              Scripts. Ninguno guarda datos personales acá adentro.
│   ├── generar_registros_genericos.py  Regenera los 500 sintéticos (semilla fija).
│   ├── actualizar_contador.py          Mezcla los reales de la planilla con los sintéticos.
│   ├── publicar_mapa.py                Cadena completa: CSV → mapa + contador → commit y push.
│   ├── generar_mapa.py                 Mapa detallado, un marcador por domicilio. Escribe FUERA del repo.
│   ├── generar_mapa_publico.py         Mapa agregado por comuna. Este sí se publica.
│   └── comunas_centroides.json         Centro oficial de cada comuna, cacheado.
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

El formulario (sección `#registro` de `index.html`) le pide a la persona su correo y su dirección para medir la demanda por comuna. **No hay entrega de bolsas**: ver [Aviso post-registro](#aviso-post-registro-no-se-entrega-ninguna-bolsa). El flujo es:

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

## Aviso post-registro: no se entrega ninguna bolsa

Al guardarse un pre-registro se abre un **modal** que dice, con todas las letras, que la persona **no va a recibir ninguna bolsa**, que REP DATA 360 es un trabajo para el ramo de Innovación de la Usach, y le agradece haber participado.

No es un detalle de copy: la página le pide **correo y dirección real** a gente que no conocemos. Si alguien se registra creyendo que le llega un despacho, le sacamos un dato personal a cambio de algo que no existe. Por eso el resto de la sección de registro promete lo mismo que el modal: un punto en el mapa de demanda, no una bolsa.

Si en algún momento el proyecto sí entrega bolsas, hay que tocar **las dos cosas juntas**: el modal y los tres puntos de la lista de la sección `#registro`.

El contador **no** aclara que su base es sintética: el número se muestra pelado, por decisión del equipo. Dónde sí queda dicho es en el banner del mapa, que detalla cuántos de esos pre-registros son reales.

## Contador de pre-registrados

El recuadro de la sección `#registro` muestra cuánta gente se pre-registró:

```
total = registros sintéticos (500) + pre-registros reales de la planilla
```

El sitio es **estático** y la planilla es **privada**, así que el navegador no puede contar las respuestas reales por su cuenta: lee `datos/contador.json`, que es un archivo de tres números que se regenera a mano.

**Para actualizarlo**, no hace falta nada aparte: `publicar_mapa.py` lo regenera y lo sube junto con el mapa. Se hacían por separado y el contador quedaba atrás del mapa, mostrando un número viejo en la portada. Si querés correrlo suelto (mismo CSV que usa el mapa):

```bash
python3 tools/actualizar_contador.py respuestas.csv
```

### El +1 de quien se acaba de pre-registrar

Entre que alguien envía el formulario y que se regenera `contador.json` pasan horas o días. En el medio, esa persona vería su propio pre-registro sin ningún efecto y pensaría que no llegó. Por eso el navegador guarda el instante de su envío en `localStorage` (`repdata360:registrado`) y le suma **1** al número, tanto en la portada como en el KPI del mapa.

Ese +1 se aplica solo si el envío es **posterior a `generado`**, el instante exacto del corte que deja el script. Si ya está adentro del archivo, no se cuenta dos veces. Va en UTC terminado en `Z` a propósito: es el mismo formato que `toISOString()` del navegador, y así los dos se comparan como texto. Antes se comparaba solo la fecha, y quien se pre-registraba **el mismo día** en que se había regenerado el corte no veía su +1 nunca.

El mapa suma ese +1 al KPI pero **no dibuja el punto**: el desglose por comuna se hornea al generar el archivo. Cuando eso pasa, aparece la nota de abajo del KPI explicándolo. Y aunque se regenere, una comuna con menos de 3 pre-registros sigue sin círculo propio: se suma en «Otras comunas».

El script **descarta las filas `.demo@`**: son los envíos que deja el botón «Enviar al formulario real» del generador al probar el circuito, no personas. Es la misma marca que usa `COMO-ACTUALIZAR-EL-MAPA.md` para poder borrarlas a mano de la planilla, y avisa cuántas descartó.

El banner del mapa dice cuántos de esos pre-registros son reales (*«A esa base se le suman N pre-registros reales, agregados por comuna»*). No es cosmético: sin eso, el aviso de «base de ejemplo» sería falso justo en la página donde esa gente está contada. La frase se **hornea** al generar el archivo y además la reescribe el `<script>`: el aviso no puede depender de que un `fetch` salga bien. Los domicilios nunca aparecen, y las comunas con menos de 3 pre-registros se agrupan en «Otras comunas», así que nadie queda señalado por un círculo propio.

> [!NOTE]
> Hubo una opción `--mezcla` que dejaba los dos sets juntos en un archivo con correos y direcciones reales, para alimentar un segundo mapa. Ya no existe: hay un solo mapa y `publicar_mapa.py` mezcla **en memoria**, contando por comuna, sin escribir nada con datos personales.

**Para que el número se actualice solo** (opcional, un solo paso manual):

1. En la planilla, creá una hoja nueva —llamala `Conteo`— con una sola celda: `=CONTARA(Respuestas!B2:B)`.
2. *Archivo > Compartir > Publicar en la web*, elegí **esa hoja** (no la de respuestas) y formato **CSV**.
3. Pegá la URL en `CONTADOR.csvPublicado`, en el `<script>` de `index.html`.

Los reales pasan a leerse en vivo en cada visita y `contador.json` queda como base sintética y como red de seguridad si Google no responde. **Publicá la hoja de conteo, no la de respuestas**: publicar en la web es público de verdad, y la de respuestas lleva correos y direcciones. El lector acepta las dos formas (una celda con el número, o filas menos encabezado), pero solo una es segura.

**Detalles de comportamiento**, para que nadie los tome por bugs:

- Quien se registra ve el número subir **en el acto**, aunque nadie haya regenerado el JSON. Queda anotada la fecha en `localStorage` para no contarse dos veces cuando el JSON ya lo incluya, y para no contarse de nuevo si se registra otra vez desde el mismo navegador. **Ese +1 solo lo ve esa persona**: el resto de las visitas ve el número del JSON hasta la próxima actualización.
- El número **anima al entrar en pantalla**, no al cargar la página (el contador está bajo el pliegue). Con `prefers-reduced-motion` aparece directo.
- Si `contador.json` no carga, queda el número escrito en el HTML (500). Nunca se ve vacío ni en cero.
- **El mapa muestra el mismo número.** `mapa.html` lee ese mismo `datos/contador.json`, así que su KPI «Pre-registros» dice siempre lo mismo que la portada, con la misma regla para el +1 propio. Si el contador ya suma registros que todavía no se dibujaron —porque nadie regeneró el mapa—, lo aclara debajo del KPI, en vez de dejar arriba un total que no cuadra con el ranking de comunas. Ese `<script>` lo inyecta `tools/generar_mapa_publico.py`.

**Los 500 sintéticos** salen de `tools/generar_registros_genericos.py`, con semilla fija: correrlo dos veces da exactamente el mismo set, así que el mapa no se reacomoda solo. Usan el mismo esquema que exporta la planilla (`fecha, correo, direccion, lat, lon, comuna`) y los correos se reparten entre `icloud.com`, `hotmail.com`, `gmail.com`, `outlook.com` y `usach.cl`, con nicks inventados además de los `nombre.apellido`. **No son personas.**

## Mapa de demanda

Las columnas `Lat`, `Lon` y `Comuna` de la planilla existen para responder **dónde se concentra la demanda**: qué comunas piden más bolsas, que es el dato que le sirve a un sistema de gestión para priorizar rutas.

**Hay un solo mapa publicado**, `mapa.html`, y cuenta exactamente lo mismo que `datos/contador.json`: los 500 sintéticos más los pre-registros reales. Los dos salen de la misma corrida de `publicar_mapa.py`.

Hasta el 25 jul 2026 había dos, `mapa.html` con los reales solos y `mapa-demo.html` con la base de ejemplo, y la portada enlazaba el segundo. Se generaban por caminos distintos, así que se desincronizaban entre ellos y con el contador, y no quedaba claro cuál mirar. `mapa-demo.html` quedó como redirección: la URL vieja anda en el deck y en el PDF de la demo.

Aparte del publicado está el mapa **detallado**, que no es una alternativa sino otra cosa: es la herramienta local para ver quién se registró.

| | Detalle | Dónde vive | Contenido |
|---|---|---|---|
| `mapa.html` (este repo) | Agregado por comuna | **Publicado** en Pages | Solo conteos. Sin domicilios. |
| `mapa-detallado.html` | Un marcador por domicilio | **Solo local**, nunca se versiona | Direcciones y coordenadas de personas |

El detallado no se publica nunca: sus marcadores llevan la dirección exacta en el tooltip, y este repositorio es público.

### Cómo el mapa público protege los datos

Dos decisiones deliberadas, no accidentes de implementación:

1. **Cada círculo se ubica en el centro oficial de la comuna**, geocodificado aparte y cacheado. No se usa el promedio de los domicilios: con pocos registros ese promedio queda pegado a una casa real.
2. **Las comunas con menos de 3 pre-registros no se dibujan**: se suman en «Otras comunas». Un círculo solo sobre una comuna con 1 registro apunta, en la práctica, a ese domicilio.

Los generadores viven en `tools/`. Lo que **no** vive acá son los datos: el CSV que baja de la planilla, `datos.json` y `mapa-detallado.html` se quedan en la carpeta de trabajo local, un nivel más arriba del repo.

Esa separación no es cosmética. `mapa-detallado.html` lleva la dirección exacta de cada persona en el tooltip, así que `tools/generar_mapa.py` **se niega a escribirlo adentro del repo** y el `.gitignore` lo bloquea por segunda vez. Si algún día ese mapa aparece acá, algo se rompió.

El lector de coordenadas tolera los tres formatos que puede dejar Sheets (`-33.44`, `-33,44` y el `-33.444.710` roto por el separador de miles) y descarta lo que caiga fuera de Chile, así que un cambio de configuración regional en la planilla no rompe el mapa.

## Privacidad

El formulario recolecta **correo electrónico y dirección domiciliaria**, que son datos personales bajo la Ley 19.628 sobre Protección de la Vida Privada (Chile). Recomendaciones mientras dure el piloto:

- No dejar la Google Sheet con acceso público ni compartida más allá de quienes necesitan gestionarla. Si se publica la hoja para el contador en vivo, **publicá solo una hoja con el conteo** (una celda con un `COUNTA`), nunca la de respuestas con correos y direcciones.
- Usar los datos solo para lo que se le dijo a la persona: medir la demanda para este trabajo académico. No hay entrega, ni contacto comercial.
- Borrar los datos recolectados una vez que termine el ramo.

## Equipo

- César Guerrero Torres
- Jaritza Ramírez Valles
- Sandy Suárez Urriola
- Valentina Villalba Lleufo
