// Botón «Descarga la app»: modal con un QR que lleva directo al APK de Android.
LF.urlApp = () => new URL(window.LF_APP_URL || 'descargas/licofast.apk', location.origin + '/').href;

LF.acc.descargarApp = async () => {
  const url = LF.urlApp();
  const qr = qrcode(0, 'M'); qr.addData(url); qr.make();
  LF.modal(`<div class="dl-app">
    <div class="dl-logo">🍾</div>
    <h2>Descarga la app <span style="color:var(--brand)">LicoFast</span></h2>
    <p class="sub" style="margin:0">Pide más rápido, sigue tu pedido en el mapa y paga con QR.</p>
    <div class="qrbox">${qr.createSvgTag({ cellSize: 6, margin: 1, scalable: true })}</div>
    <div class="sub" style="margin:0 0 10px">Escanea el código con la cámara de tu celular</div>
    <div class="row"><a class="btn lg" id="dlBtn" href="${LF.esc(url)}" download>⬇️ Descargar la app (Android)</a></div>
    <div id="dlEstado" class="note" style="margin:10px auto;max-width:420px" hidden></div>
    <ol>
      <li>Escanea el QR o toca el botón de descarga.</li>
      <li>Abre el archivo descargado (<b>licofast.apk</b>).</li>
      <li>Si Android lo pide, permite <b>instalar apps de esta fuente</b>.</li>
      <li>Pulsa <b>Instalar</b> y abre LicoFast.</li>
    </ol>
    <p class="sub" style="margin:6px 0 0">Disponible para Android. En iPhone puedes usar esta misma página web.</p>
    <div class="row" style="margin-top:12px"><button class="btn sec" onclick="LF.cerrar()">Cerrar</button></div>
  </div>`);
  // Comprueba que el archivo exista y muestra su tamaño
  try {
    const r = await fetch(url, { method: 'HEAD', cache: 'no-store' });
    const ok = r.ok && !/text\/html/.test(r.headers.get('content-type') || '');
    const est = LF.$('#dlEstado'); if (!est) return;
    if (!ok) { est.hidden = false; est.className = 'note bad'; est.textContent = 'La app todavía no está disponible para descargar. Inténtalo más tarde.'; const b = LF.$('#dlBtn'); if (b) { b.removeAttribute('href'); b.classList.add('sec'); } }
    else { const n = Number(r.headers.get('content-length') || 0); if (n) { est.hidden = false; est.className = 'note ok'; est.textContent = `Archivo listo · ${(n / 1048576).toFixed(1)} MB`; } }
  } catch (e) { /* sin conexión: se deja el botón normal */ }
};
