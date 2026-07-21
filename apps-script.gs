// Pega este código en Extensiones > Apps Script de la Google Sheet donde
// quieras recibir los pre-registros de REP DATA 360. Ver instrucciones de
// despliegue al final del archivo.

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['Fecha', 'Correo', 'Dirección']);
  }

  var params = e.parameter;
  sheet.appendRow([
    params.fecha || new Date().toISOString(),
    params.correo || '',
    params.direccion || ''
  ]);

  return ContentService
    .createTextOutput(JSON.stringify({ result: 'ok' }))
    .setMimeType(ContentService.MimeType.JSON);
}

/*
DESPLIEGUE (una sola vez):

1. Crea una Google Sheet nueva (o usa una existente) para guardar los leads.
2. Extensiones > Apps Script.
3. Borra el código de ejemplo y pega este archivo completo.
4. Guarda el proyecto (Ctrl+S / ícono de guardar).
5. Implementar > Nueva implementación.
6. Selecciona tipo: "Aplicación web".
7. Configuración:
   - Ejecutar como: Yo (tu cuenta)
   - Quién tiene acceso: Cualquier usuario
8. Implementar. La primera vez Google pedirá autorizar permisos: acepta
   (verás una advertencia de "app no verificada" porque es tuya, es normal;
   Avanzado > Ir a [nombre del proyecto] (no seguro) > Permitir).
9. Copia la URL que termina en /exec.
10. Pégala en site/index.html reemplazando el valor de SHEET_URL
    (buscar 'REEMPLAZA_CON_TU_APPS_SCRIPT_ID').

Si más adelante cambias el código de este script, tenés que volver a
"Implementar > Gestionar implementaciones > editar (lápiz) > Nueva versión"
para que el cambio se refleje en la URL /exec ya publicada.
*/
