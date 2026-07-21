# REP DATA 360

REP DATA 360 es un Proyecto de Innovación enmarcado en la Ley REP N°20.920 (Chile). Propone una bolsa de reciclaje domiciliario con un indicador químico que cambia de color según su nivel de limpieza (verde: limpia, ámbar: intermedia, roja: contaminada) y un chip RFID que registra la hora y el lugar de retiro. La idea es dar trazabilidad al reciclaje desde el hogar, antes de que el camión llegue a la planta.

Sitio publicado: **https://wildcodeai.github.io/rep-data-360/**

> [!WARNING]
> **El formulario de pre-registro no está guardando datos.** Al día de hoy, el endpoint de Google Apps Script configurado en `index.html` (constante `SHEET_URL`) devuelve **HTTP 401**, así que cualquier persona que complete el formulario va a ver el mensaje de error ("No pudimos registrar tus datos..."), y ningún dato se está escribiendo en la Google Sheet.
>
> Para arreglarlo hay que volver a desplegar el Apps Script: **Implementar > Gestionar implementaciones > editar (lápiz) > Nueva versión**, copiar la URL nueva que termina en `/exec` y reemplazar el valor de `SHEET_URL` en `index.html`. Ver la sección [Configurar el backend](#configurar-el-backend-google-apps-script) más abajo para el detalle completo.

## Estructura del proyecto

```
.
├── index.html                          Todo el sitio: HTML, CSS y JS inline en un solo archivo.
├── apps-script.gs                      Backend del formulario: recibe el POST y escribe en una Google Sheet.
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

Como el formulario usa `fetch` (para consultar direcciones en Nominatim y para enviar el pre-registro al Apps Script), no alcanza con abrir `index.html` directamente desde el navegador con `file://`: los navegadores bloquean o restringen `fetch` bajo el protocolo `file://` por política de CORS/origen, así que hay que servir la carpeta por HTTP.

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

1. **Validación de dirección**: mientras la persona escribe, el JS consulta la API pública de **Nominatim / OpenStreetMap** (`nominatim.openstreetmap.org/search`) restringida a Chile (`countrycodes=cl`), muestra sugerencias en un dropdown y marca la dirección como verificada cuando se elige una. Si al enviar el formulario la dirección todavía no fue verificada, se hace una última consulta antes de continuar. Si el servicio de Nominatim falla, el formulario no bloquea el envío igual (se prioriza no perder el lead).
2. **Honeypot anti-bots**: hay un campo oculto (`empresa`) fuera de la vista, con `tabindex="-1"` y `aria-hidden`. Si viene lleno, es porque lo rellenó un bot, así que se simula un envío exitoso sin mandar ningún dato real.
3. **Envío**: los datos (`correo`, `direccion`, `fecha`) se mandan por `POST` como `FormData` a una URL de **Google Apps Script** (constante `SHEET_URL` en el `<script>` de `index.html`), que actúa como backend sin servidor propio. El `fetch` lee la respuesta y solo muestra el mensaje de éxito si el Apps Script contesta `{result:'ok'}`; si falla, muestra el error y no borra lo que la persona escribió. A propósito no se usa `mode:'no-cors'`: con esa opción la respuesta queda opaca, el navegador nunca la deja leer y el formulario terminaría diciendo que todo salió bien incluso cuando el registro no se guardó.
4. El Apps Script (`apps-script.gs`) recibe el `POST` en su función `doPost`, y agrega una fila a la Google Sheet activa con fecha, correo y dirección (si es la primera fila, antes agrega el encabezado).

## Configurar el backend (Google Apps Script)

Pasos para desplegar (o redesplegar) el backend, tal como están documentados en el propio `apps-script.gs`:

1. Crea una Google Sheet nueva (o usa una existente) para guardar los leads.
2. Andá a **Extensiones > Apps Script**.
3. Borrá el código de ejemplo y pegá el contenido completo de `apps-script.gs`.
4. Guardá el proyecto (`Ctrl+S` / ícono de guardar).
5. **Implementar > Nueva implementación**.
6. Seleccioná tipo: **"Aplicación web"**.
7. Configuración:
   - Ejecutar como: **Yo** (tu cuenta)
   - Quién tiene acceso: **Cualquier usuario**
8. Implementar. La primera vez Google va a pedir autorizar permisos: aceptá (vas a ver una advertencia de "app no verificada" porque es tuya, es normal; **Avanzado > Ir a [nombre del proyecto] (no seguro) > Permitir**).
9. Copiá la URL que termina en `/exec`.
10. Pegala en `index.html`, reemplazando el valor de `SHEET_URL` dentro del `<script>` final.

Si más adelante cambiás el código de `apps-script.gs`, tenés que volver a **Implementar > Gestionar implementaciones > editar (lápiz) > Nueva versión** para que el cambio se refleje en la URL `/exec` ya publicada; guardar el archivo no alcanza.

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
