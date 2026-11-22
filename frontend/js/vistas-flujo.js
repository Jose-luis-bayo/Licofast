// Etapas internas de un pedido online: Caja (confirma) → Bodega (prepara y libera) → Repartidor (asignado automáticamente).
window.LF = window.LF || {};
LF.refresco = { '/pedidos-online': 15000, '/preparar': 15000, '/entregas': 15000, '/pedidos-admin': 20000 };   // recarga automática (ms)

LF.telWa = t => { const n = String(t || '').replace(/\D/g, ''); return n.length === 8 ? '591' + n : n; };
LF.pagoTxt = p => `${LF.METODOS[p.metodo_pago] || p.metodo_pago} · ${p.estado_pago === 'pagado' ? '<span class="badge b-pagado">pagado</span>' : (p.estado_pago === 'anulado' ? '<span class="badge b-anulado">anulado</span>' : '<span class="badge b-pendiente">sin pagar</span>')}`;
LF.tarjetaPedido = (p, botones = '') => `<div class="card ped">
  <div class="row"><b>Pedido #${p.id}</b>${LF.badgeEstado(p.estado)}<span class="sp"></span><b>${LF.bs(p.total)}</b></div>
  <dl class="kv" style="margin-top:8px">
    <dt>Cliente</dt><dd>${LF.esc(p.tipo_venta === 'retiro' ? p.factura_nombre : (p.cliente || '—'))} · <a href="tel:${LF.esc(p.telefono_contacto)}">${LF.esc(p.telefono_contacto)}</a> <a class="wa-mini" target="_blank" rel="noopener" href="https://wa.me/${LF.telWa(p.telefono_contacto)}">💬</a></dd>
    ${p.tipo_venta === 'retiro' ? `<dt>NIT / CI</dt><dd>${LF.esc(p.factura_nit)}</dd><dt>Entrega</dt><dd><b>🏬 Retiro en bodega</b> (compra en quiosco)</dd>` :
      `<dt>Dirección</dt><dd><b>${LF.esc(p.direccion_entrega)}</b> ${LF.esc(p.referencia_entrega || '')} ${p.lat_entrega != null ? `<a target="_blank" rel="noopener" href="https://www.google.com/maps?q=${p.lat_entrega},${p.lng_entrega}">📍 mapa</a>` : ''}</dd>`}
    <dt>Pago</dt><dd>${LF.pagoTxt(p)}</dd>
    <dt>Recibido</dt><dd>${LF.fecha(p.created_at)}${p.canal === 'whatsapp' ? ' · 💬 WhatsApp' : ''}</dd>
    ${p.repartidor ? `<dt>Repartidor</dt><dd><b>${LF.esc(p.repartidor)}</b></dd>` : ''}
  </dl>
  ${p.items ? `<ul class="its">${p.items.map(i => `<li><b>${i.cantidad}×</b> ${LF.esc(i.nombre)}</li>`).join('')}</ul>` : ''}
  ${botones ? `<div class="row" style="margin-top:10px">${botones}</div>` : ''}</div>`;

// ---------------- Caja: pedidos online por confirmar ----------------
LF.rutas['/pedidos-online'] = async () => {
  const lista = await LF.get('/pedidos/online');
  const nuevos = lista.filter(p => p.estado === 'pendiente'), curso = lista.filter(p => p.estado !== 'pendiente');
  const btn = p => {
    const falta = ['qr', 'paypal'].includes(p.metodo_pago) && p.estado_pago !== 'pagado';
    return `<button class="btn ok" data-act="confirmarPed" data-id="${p.id}" ${falta ? 'disabled title="Espere a que el cliente pague"' : ''}>✅ Confirmar y enviar a bodega</button><button class="btn bad" data-act="rechazarPed" data-id="${p.id}">❌ Rechazar</button>${falta ? '<span class="sub" style="margin:0">Esperando el pago del cliente…</span>' : ''}`;
  };
  return LF.pagina('Pedidos online', 'Revise cada pedido nuevo y envíelo a bodega. Se actualiza solo cada 15 segundos.',
    `<h2>Por confirmar (${nuevos.length})</h2>${nuevos.length ? `<div class="grid g2">${nuevos.map(p => LF.tarjetaPedido(p, btn(p))).join('')}</div>` : '<div class="card empty">No hay pedidos nuevos 🎉</div>'}
     <h2>En proceso (${curso.length})</h2>${curso.length ? `<div class="grid g2">${curso.map(p => LF.tarjetaPedido(p)).join('')}</div>` : '<div class="card empty">Sin pedidos en proceso</div>'}`);
};
LF.acc.confirmarPed = async el => { const r = await LF.put('/pedidos/' + el.dataset.id + '/confirmar'); LF.toast(r.mensaje, 'ok'); return LF.render(true); };
LF.acc.rechazarPed = el => LF.modal(`<h2>Rechazar pedido #${el.dataset.id}</h2><p class="sub">Los productos volverán al inventario. Si el cliente ya pagó en línea, deberá escribirle por WhatsApp para devolverle el dinero (el cliente envía su QR).</p>
  <form id="frz">${LF.campo('motivo', 'Motivo (obligatorio)', 'text', '', 'required')}</form>
  <p class="row"><button class="btn bad" data-act="enviarRechazo" data-id="${el.dataset.id}">Rechazar pedido</button><button class="btn sec" data-act="cerrar">Cancelar</button></p>`);
LF.acc.enviarRechazo = async el => { const f = LF.form('#frz'); if (!f.motivo) return LF.toast('Indique el motivo', 'bad');
  const r = await LF.put('/pedidos/' + el.dataset.id + '/rechazar', f); LF.cerrar(); LF.toast(r.mensaje, r.requiere_reembolso ? 'bad' : 'ok'); return LF.render(true); };

// ---------------- Bodega: preparar y liberar ----------------
LF.selectorRepartidor = (p, reps) => `<select data-act="asignar" data-id="${p.id}" aria-label="Repartidor" style="min-width:170px;max-width:240px">${LF.opciones(reps.map(r => [r.id, `${r.nombre} (${r.por_salir + r.en_camino} pedidos)`]), p.repartidor_id, 'Sin asignar')}</select>`;
LF.rutas['/preparar'] = async () => {
  const [lista, reps] = await Promise.all([LF.get('/pedidos/online'), LF.get('/repartidores')]);
  const prep = lista.filter(p => p.estado === 'confirmado' && p.tipo_venta !== 'retiro'), listos = lista.filter(p => ['preparado', 'en_camino'].includes(p.estado) && p.tipo_venta !== 'retiro');
  const kPrep = lista.filter(p => p.tipo_venta === 'retiro' && p.estado === 'confirmado'), kListos = lista.filter(p => p.tipo_venta === 'retiro' && p.estado === 'preparado');
  const kiosko = `<h2>🏬 Quiosco · por preparar (${kPrep.length})</h2>${kPrep.length ? `<div class="grid g2">${kPrep.map(p => LF.tarjetaPedido(p, `<button class="btn" data-act="prepararPed" data-id="${p.id}">📦 Preparar para retiro</button><button class="btn bad sm" data-act="rechazarPed" data-id="${p.id}">🚫 Cancelar</button>${p.whatsapp_factura_url ? `<a class="btn sec sm" target="_blank" rel="noopener" href="${p.whatsapp_factura_url}">💬 Enviar factura por WhatsApp</a>` : ''}`)).join('')}</div>` : '<div class="card empty">Sin compras del quiosco por preparar</div>'}
     <h2>🏬 Quiosco · listos para entregar al cliente (${kListos.length})</h2>${kListos.length ? `<div class="grid g2">${kListos.map(p => LF.tarjetaPedido(p, `<input id="cod${p.id}" inputmode="numeric" maxlength="4" placeholder="Código de 4 dígitos" aria-label="Código de retiro" style="max-width:170px"><button class="btn ok" data-act="entregarRetiro" data-id="${p.id}">✅ Entregar al cliente</button><button class="btn bad sm" data-act="rechazarPed" data-id="${p.id}">🚫 Cancelar</button>${p.whatsapp_factura_url ? `<a class="btn sec sm" target="_blank" rel="noopener" href="${p.whatsapp_factura_url}">💬 Factura por WhatsApp</a>` : ''}`)).join('')}</div>` : '<div class="card empty">Ningún pedido del quiosco espera retiro</div>'}`;
  const carga = `<div class="chips">${reps.map(r => `<span class="chip">🛵 ${LF.esc(r.nombre)} · <b>${r.por_salir}</b> por salir · <b>${r.en_camino}</b> en camino</span>`).join('') || '<span class="sub">No hay repartidores activos</span>'}</div>`;
  return LF.pagina('Pedidos a preparar', 'Alista los productos y libere el pedido: el sistema lo asigna al repartidor con menos carga. Solo bodega y administrador pueden cambiar de repartidor.',
    `${kiosko}${carga}<h2>Por preparar (${prep.length})</h2>${prep.length ? `<div class="grid g2">${prep.map(p => LF.tarjetaPedido(p, `<button class="btn" data-act="prepararPed" data-id="${p.id}">📦 Preparar y liberar</button><button class="btn bad" data-act="rechazarPed" data-id="${p.id}">🚫 Cancelar pedido</button>`)).join('')}</div>` : '<div class="card empty">Nada por preparar por ahora</div>'}
     <h2>Liberados (${listos.length})</h2>${listos.length ? `<div class="grid g2">${listos.map(p => LF.tarjetaPedido(p, `<label style="margin:0">Cambiar repartidor</label>${LF.selectorRepartidor(p, reps)}${p.estado === 'preparado' ? `<button class="btn bad sm" data-act="rechazarPed" data-id="${p.id}">🚫 Cancelar</button>` : ''}`)).join('')}</div>` : '<div class="card empty">Sin pedidos liberados</div>'}`);
};
LF.acc.entregarRetiro = async el => {
  const codigo = (document.getElementById('cod' + el.dataset.id).value || '').trim();
  if (!/^\d{4}$/.test(codigo)) return LF.toast('Escriba el código de 4 dígitos del cliente', 'bad');
  const r = await LF.put('/pedidos/' + el.dataset.id + '/entregar-retiro', { codigo }); LF.toast('✅ ' + r.mensaje, 'ok'); return LF.render(true); };
LF.acc.prepararPed = async el => { const r = await LF.put('/pedidos/' + el.dataset.id + '/preparar'); LF.toast('📦 ' + r.mensaje, 'ok'); return LF.render(true); };
