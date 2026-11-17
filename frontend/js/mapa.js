// Mapa en vivo (Leaflet + OpenStreetMap, sin clave), ubicación actual del cliente, GPS del repartidor y pago PayPal.
window.LF = window.LF || {};
LF.CIUDAD = 'Sucre, Bolivia';
LF.CENTRO = [-19.0333, -65.2627];

// ---------- Ubicación actual (cliente al hacer el pedido) ----------
LF.ubic = null;   // {lat,lng,precision}
LF.obtenerUbicacion = () => new Promise((ok, mal) => {
  if (!navigator.geolocation) return mal({ mensaje: 'Este navegador no permite obtener la ubicación.' });
  navigator.geolocation.getCurrentPosition(
    p => ok({ lat: +p.coords.latitude.toFixed(6), lng: +p.coords.longitude.toFixed(6), precision: Math.round(p.coords.accuracy) }),
    e => mal({ mensaje: e.code === 1 ? 'Permiso de ubicación denegado. Actívelo en el navegador o escriba su dirección.' : 'No se pudo obtener su ubicación. Escriba su dirección.' }),
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
});
LF.acc.usarUbicacion = async () => {
  const st = LF.$('#ubicEstado'); if (st) st.textContent = 'Obteniendo ubicación…';
  try {
    LF.ubic = await LF.obtenerUbicacion();
    const d = LF.$('#fc [name=direccion_entrega]'); if (d && !d.value.trim()) d.value = 'Mi ubicación actual (GPS)';
    if (st) st.innerHTML = `✅ Ubicación guardada (precisión ~${LF.ubic.precision} m) · <a target="_blank" rel="noopener" href="https://www.google.com/maps?q=${LF.ubic.lat},${LF.ubic.lng}">ver en el mapa</a> · <a href="#" data-act="quitarUbicacion">quitar</a>`;
  } catch (e) { LF.ubic = null; if (st) st.textContent = ''; LF.err(e); }
};
LF.acc.quitarUbicacion = () => { LF.ubic = null; const st = LF.$('#ubicEstado'); if (st) st.textContent = ''; };

// ---------- Mapa de seguimiento en vivo ----------
const icono = (emoji, color) => L.divIcon({ className: 'pin', html: `<div class="pin-in" style="background:${color}"><span>${emoji}</span></div>`, iconSize: [38, 38], iconAnchor: [19, 38] });
LF.geocodificar = async dir => {
  try {
    const r = await fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(dir + ', ' + LF.CIUDAD));
    const d = await r.json(); return d[0] ? [+d[0].lat, +d[0].lon] : null;
  } catch (e) { return null; }
};
LF.mapaVivo = async (id, direccion) => {
  LF.modal(`<h2>Pedido #${id} en vivo</h2><div id="mapaVivo" class="mapa"></div><div id="mapaInfo" class="note">Buscando al repartidor…</div>
    <div class="row noprint"><span class="sp"></span><button class="btn sec" data-act="cerrar">Cerrar</button></div>`, true);
  if (!window.L) { LF.$('#mapaInfo').textContent = 'No se pudo cargar el mapa (revise su conexión a internet).'; return; }
  const mapa = L.map('mapaVivo').setView(LF.CENTRO, 14);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(mapa);
  let mRep = null, mDes = null, centrado = false;
  const ajustar = () => {
    const pts = [mRep, mDes].filter(Boolean).map(m => m.getLatLng());
    if (pts.length === 2) mapa.fitBounds(L.latLngBounds(pts).pad(.3), { maxZoom: 17 }); else if (pts.length === 1) mapa.setView(pts[0], 16);
  };
  const ponerDestino = ll => { if (!ll) return; mDes = L.marker(ll, { icon: icono('🏠', '#be123c') }).addTo(mapa).bindPopup('Su dirección'); ajustar(); };
  const tick = async () => {
    let u; try { u = await LF.get('/pedidos/' + id + '/ubicacion'); } catch (e) { return; }
    if (!mDes && !LF._dest) { LF._dest = 1; if (u.destino_lat != null) ponerDestino([u.destino_lat, u.destino_lng]); else LF.geocodificar(direccion || u.direccion_entrega).then(ponerDestino); }
    const info = LF.$('#mapaInfo'); if (!info) return;
    if (u.estado === 'entregada') { info.className = 'note ok'; info.textContent = '✅ ¡Su pedido fue entregado!'; clearInterval(LF._poll); return; }
    if (u.estado === 'no_entregado') { info.className = 'note bad'; info.textContent = 'El pedido no pudo entregarse.'; clearInterval(LF._poll); return; }
    if (!u.disponible) { info.className = 'note'; info.textContent = u.estado === 'en_camino' ? '🛵 El repartidor salió. Esperando su señal GPS…' : 'El repartidor aún no salió con su pedido.'; return; }
    const ll = [u.lat, u.lng];
    if (!mRep) mRep = L.marker(ll, { icon: icono('🛵', '#1d4ed8') }).addTo(mapa).bindPopup('Repartidor'); else mRep.setLatLng(ll);
    if (!centrado) { ajustar(); centrado = true; }
    info.className = 'note ok'; info.innerHTML = `🛵 <b>${LF.esc(u.repartidor || 'El repartidor')}</b> va hacia su dirección · actualizado hace ${u.hace_seg}s`;
  };
  await new Promise(r => setTimeout(r, 300)); mapa.invalidateSize();     // el modal ya tiene su tamaño final
  LF._dest = 0; clearInterval(LF._poll); await tick(); LF._poll = setInterval(tick, 5000);
  setTimeout(() => { mapa.invalidateSize(); ajustar(); }, 600);
};
LF.acc.verMapa = el => LF.mapaVivo(el.dataset.id, el.dataset.dir);

// ---------- GPS del repartidor desde el navegador (mientras la página está abierta) ----------
LF.gps = { ids: new Set(), timer: null, ultimo: null };
LF.gpsSincronizar = ids => {                          // ids = pedidos «en camino» de este repartidor
  LF.gps.ids = new Set(ids);
  if (!ids.length) { clearInterval(LF.gps.timer); LF.gps.timer = null; return; }
  if (LF.gps.timer) return;
  const enviar = () => {
    if (!LF.gps.ids.size || !navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(p => {
      LF.gps.ultimo = Date.now();
      LF.gps.ids.forEach(id => LF.put('/entregas/' + id + '/ubicacion', { lat: p.coords.latitude, lng: p.coords.longitude }).catch(e => { if (e.status === 409 || e.status === 404 || e.status === 403) LF.gps.ids.delete(id); }));
      const el = LF.$('#gpsEstado'); if (el) el.textContent = '📡 Compartiendo su ubicación con el cliente';
    }, () => { const el = LF.$('#gpsEstado'); if (el) el.textContent = '⚠️ Active el GPS y permita la ubicación para que el cliente lo vea'; }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 });
  };
  enviar(); LF.gps.timer = setInterval(enviar, 10000);
};

// ---------- Pago con PayPal ----------
LF.verPaypal = (pago, onPagado) => {
  LF.modal(`<h2>Pagar con PayPal</h2>
    <p class="sub">Se abrirá PayPal en otra pestaña para que apruebe el pago de <b>${LF.bs(pago.monto)}</b> (PayPal cobra en dólares; la conversión se hace al tipo de cambio de la tienda).</p>
    <p style="text-align:center"><a class="btn lg" href="${LF.esc(pago.qr_payload)}" target="_blank" rel="noopener" style="display:block;background:#0070ba">💳 Ir a PayPal</a></p>
    <div id="ppEstado" class="note">⏳ Esperando que complete el pago en PayPal…</div>
    <div class="row noprint"><span class="sp"></span><button class="btn sec" data-act="cerrar">Cerrar</button></div>`);
  clearInterval(LF._poll);
  LF._poll = setInterval(async () => {
    try {
      const p = await LF.get('/pagos/' + pago.id);
      if (p.estado === 'confirmado') { clearInterval(LF._poll); const e = LF.$('#ppEstado'); if (e) { e.className = 'note ok'; e.textContent = '✅ Pago confirmado'; } LF.toast('Pago confirmado', 'ok'); setTimeout(() => { LF.cerrar(); onPagado && onPagado(p); }, 900); }
      else if (p.estado === 'anulado' || p.estado === 'vencido') { clearInterval(LF._poll); const e = LF.$('#ppEstado'); if (e) { e.className = 'note bad'; e.textContent = 'El pago ya no está vigente. Genere uno nuevo.'; } }
    } catch (e) { clearInterval(LF._poll); }
  }, 2500);
};
LF.iniciarPago = async (ventaId, metodo, alTerminar) => {
  const pago = await LF.post('/pagos', { venta_id: +ventaId, metodo }, { 'Idempotency-Key': LF.uuid() });
  if (metodo === 'paypal') LF.verPaypal(pago, alTerminar); else LF.verQr(pago, alTerminar);
};
