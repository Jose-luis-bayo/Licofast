// Dirección base de la API REST de LicoFast.
// Si la página se abre desde Apache/XAMPP (puerto 80 u omitido) o cualquier puerto distinto de 5000,
// se conecta automáticamente al servicio Flask en http://localhost:5000.
// Si se abre directamente desde Flask (puerto 5000), utiliza ruta relativa.
(function() {
  var host = window.location.hostname || 'localhost';
  var port = window.location.port;
  if (port === '5000') {
    window.LF_API_BASE = '';
  } else {
    window.LF_API_BASE = window.location.protocol + '//' + host + ':5000';
  }
})();
