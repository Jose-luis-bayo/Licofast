// Vistas del encargado de bodega (stock) y del repartidor (entregas).
window.LF = window.LF || {};
LF.soloBajos = false;

LF.rutas['/stock'] = async () => {
  const [prods, alertas] = await Promise.all([LF.get('/productos?todos=1'), LF.get('/inventario/alertas')]);
  const lista = LF.soloBajos ? alertas : prods;
  return LF.pagina('Inventario', 'Entradas, ajustes y alertas de stock bajo.', `${alertas.length ? `<div class="note bad">⚠️ ${alertas.length} producto(s) con stock bajo o agotado.</div>` : '<div class="note ok">Todo el stock está sobre el mínimo.</div>'}
    <div class="row" style="margin-bottom:10px"><label style="margin:0"><input type="checkbox" style="width:auto" ${LF.soloBajos ? 'checked' : ''} data-act="soloBajos"> Mostrar solo stock bajo</label><span class="sp"></span><a class="btn sec sm" href="#/movimientos">Ver movimientos</a></div>
    ${LF.tabla([{ t: 'Producto', f: p => `${LF.ico(p.categoria)} ${LF.esc(p.nombre)} ${p.activo ? '' : '<span class="badge b-bad">inactivo</span>'}` }, { t: 'Categoría', f: p => LF.esc(p.categoria || '—') },
      { t: 'Stock', cls: 'num', f: p => `<b>${p.stock}</b>` }, { t: 'Mínimo', cls: 'num', f: p => p.stock_minimo }, { t: 'Estado', f: p => p.stock <= p.stock_minimo ? '<span class="badge b-bad">bajo</span>' : '<span class="badge b-ok">ok</span>' },
      { t: '', f: p => `<button class="btn sm" data-act="movStock" data-id="${p.id}" data-tipo="entrada" data-nombre="${LF.esc(p.nombre)}">+ Entrada</button> <button class="btn sm sec" data-act="movStock" data-id="${p.id}" data-tipo="ajuste" data-nombre="${LF.esc(p.nombre)}">Ajuste</button>` }], lista)}`);
};
LF.acc.soloBajos = el => { LF.soloBajos = el.checked; return LF.render(true); };
LF.acc.movStock = el => LF.modal(`<h2>${el.dataset.tipo === 'entrada' ? 'Registrar entrada' : 'Ajuste de inventario'}</h2><p class="sub">${LF.esc(el.dataset.nombre)}</p><form id="fms">
  ${LF.campo('cantidad', el.dataset.tipo === 'entrada' ? 'Cantidad que ingresa' : 'Cantidad (use negativo para descontar)', 'number', '', 'required')}${LF.campo('motivo', el.dataset.tipo === 'ajuste' ? 'Motivo (obligatorio)' : 'Motivo / proveedor (opcional)')}
  <p class="row"><button class="btn" data-act="guardarMov" data-id="${el.dataset.id}" data-tipo="${el.dataset.tipo}">Guardar</button><button class="btn sec" data-act="cerrar">Cancelar</button></p></form>`);
LF.acc.guardarMov = async el => { const f = LF.form('#fms'); const r = await LF.post('/inventario/movimientos', { ...f, producto_id: +el.dataset.id, tipo: el.dataset.tipo });
  LF.cerrar(); LF.toast('Stock actualizado: ' + r.stock + (r.bajo_minimo ? ' (bajo el mínimo)' : ''), r.bajo_minimo ? 'bad' : 'ok'); return LF.render(true); };

LF.rutas['/movimientos'] = async () => {
  const m = await LF.get('/inventario/movimientos?limit=150');
  return LF.pagina('Movimientos de stock', 'Trazabilidad de entradas, ventas, reposiciones y ajustes.', LF.tabla([{ t: 'Fecha', f: x => LF.fecha(x.created_at) }, { t: 'Producto', f: x => LF.esc(x.producto) },
    { t: 'Tipo', f: x => `<span class="badge">${LF.esc(x.tipo)}</span>` }, { t: 'Cant.', cls: 'num', f: x => (x.cantidad > 0 ? '+' : '') + x.cantidad }, { t: 'Motivo', f: x => LF.esc(x.motivo || '') }, { t: 'Usuario', f: x => LF.esc(x.usuario || '—') }], m));
};

// ---------------- Repartidor ----------------
LF.rutas['/entregas'] = async () => {
  const e = await LF.get('/entregas');
  return LF.pagina('Mis entregas', 'Pedidos por entregar. Notifique y confirme el resultado de cada uno.', e.length ? `<div class="grid g2">${e.map(p => {
    const telLimpio = String(p.telefono_contacto || '').replace(/\D/g, '');
    const telWa = telLimpio.length === 8 ? '591' + telLimpio : telLimpio;
    const enLugar = p.observacion_entrega === 'Repartidor en el lugar de entrega';
    return `<div class="card"><div class="row"><b>Pedido #${p.id}</b>${LF.badge(p.estado)}<span class="sp"></span>${p.a_cobrar > 0 ? `<b style="color:var(--dis)">Cobrar ${LF.bs(p.a_cobrar)}</b>` : '<span class="badge b-ok">Ya pagado</span>'}</div>
    <dl class="kv" style="margin-top:8px">
      <dt>Cliente</dt><dd>${LF.esc(p.cliente)}</dd>
      <dt>Dirección</dt><dd><b>${LF.esc(p.direccion_entrega)}</b> ${LF.esc(p.referencia_entrega || '')}</dd>
      <dt>Teléfono</dt><dd>
        <a href="tel:${LF.esc(p.telefono_contacto)}">${LF.esc(p.telefono_contacto)}</a>
        ${telWa ? `<a href="https://wa.me/${telWa}" target="_blank" class="badge" style="background:#25D366;color:#fff;margin-left:6px;text-decoration:none">💬 Chat WhatsApp</a>` : ''}
      </dd>
      <dt>Total</dt><dd>${LF.bs(p.total)}</dd>
      ${enLugar ? `<dt>Ubicación</dt><dd><span class="badge b-ok">📍 Cliente avisado: en el lugar</span></dd>` : ''}
    </dl>
    <div class="row" style="margin-top:10px">
      ${p.estado === 'pendiente' ? `<button class="btn sm warn" data-act="enCamino" data-id="${p.id}">🛵 Salí a entregar (Avisar)</button>` : ''}
      ${p.estado === 'en_camino' && !enLugar ? `<button class="btn sm" style="background:#2563eb;color:#fff" data-act="enDestino" data-id="${p.id}">📍 Llegué a la ubicación (Avisar)</button>` : ''}
      <button class="btn sm ok" data-act="cerrarEntrega" data-id="${p.id}" data-accion="entregado">✅ Entregado</button>
      <button class="btn sm bad" data-act="cerrarEntrega" data-id="${p.id}" data-accion="no_entregado">❌ No entregado</button>
    </div></div>`;
  }).join('')}</div>` : '<div class="card empty">No tiene entregas pendientes 🎉</div>');
};
LF.acc.enCamino = async el => {
  const r = await LF.put('/entregas/' + el.dataset.id + '/en-camino');
  LF.toast('Pedido en camino; WhatsApp preparado para el cliente', 'ok');
  if (r.whatsapp_url) {
    window.open(r.whatsapp_url, '_blank');
  }
  return LF.render(true);
};
LF.acc.enDestino = async el => {
  const r = await LF.put('/entregas/' + el.dataset.id + '/en-destino');
  LF.toast('Aviso de llegada enviado al cliente por WhatsApp', 'ok');
  if (r.whatsapp_url) {
    window.open(r.whatsapp_url, '_blank');
  }
  return LF.render(true);
};
LF.acc.cerrarEntrega = el => LF.modal(`<h2>${el.dataset.accion === 'entregado' ? 'Confirmar entrega' : 'Marcar como no entregado'} · #${el.dataset.id}</h2>
  <p class="sub">${el.dataset.accion === 'entregado' ? 'Confirma que entregó el pedido y cobró el monto indicado.' : 'Los productos volverán al inventario y el cobro quedará anulado.'}</p>
  <form id="fe"><label>Observación (opcional)</label><textarea name="observacion" rows="3" placeholder="${el.dataset.accion === 'entregado' ? 'Entrega conforme' : 'Ej.: el cliente no respondió'}"></textarea></form>
  <p class="row"><button class="btn ${el.dataset.accion === 'entregado' ? 'ok' : 'bad'}" data-act="enviarCierre" data-id="${el.dataset.id}" data-accion="${el.dataset.accion}">Confirmar</button><button class="btn sec" data-act="cerrar">Cancelar</button></p>`);
LF.acc.enviarCierre = async el => { const r = await LF.put('/entregas/' + el.dataset.id, { accion: el.dataset.accion, ...LF.form('#fe') }); LF.cerrar(); LF.toast(r.mensaje, 'ok'); return LF.render(true); };
LF.rutas['/historial'] = async () => {
  const h = await LF.get('/entregas/historial');
  return LF.pagina('Historial de entregas', '', LF.tabla([{ t: '#', f: p => p.id }, { t: 'Fecha', f: p => LF.fecha(p.fecha_entrega) }, { t: 'Cliente', f: p => LF.esc(p.cliente) }, { t: 'Dirección', f: p => LF.esc(p.direccion_entrega) },
    { t: 'Resultado', f: p => LF.badge(p.estado) }, { t: 'Cobrado', cls: 'num', f: p => p.estado === 'entregada' ? LF.bs(p.total) : '—' }, { t: 'Observación', f: p => LF.esc(p.observacion_entrega || '') }], h, 'Aún no tiene entregas.'));
};
