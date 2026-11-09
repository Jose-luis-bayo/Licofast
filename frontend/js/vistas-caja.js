// Vistas del cajero: punto de venta, caja, ventas del día y pedidos por WhatsApp.
window.LF = window.LF || {};
LF.pos = { items: [], cliente: null, metodo: 'efectivo', q: '', prods: [] };

LF.rutas['/pos'] = async () => {
  const [caja, prods] = await Promise.all([LF.get('/cajas/actual'), LF.get('/productos?' + new URLSearchParams({ q: LF.pos.q }))]);
  LF.pos.prods = prods;
  const total = LF.pos.items.reduce((s, i) => s + i.precio * i.cantidad, 0);
  return LF.pagina('Punto de venta', 'Venta de mostrador (CU-E05).', `${caja ? '' : '<div class="note bad">Debe <a href="#/caja">abrir su caja</a> antes de vender.</div>'}
  <div class="split"><div><input data-input="posq" placeholder="Buscar producto…" value="${LF.esc(LF.pos.q)}" style="margin-bottom:12px">
  <div class="grid g2" style="grid-template-columns:repeat(auto-fill,minmax(190px,1fr))">${prods.map(p => `
    <div class="card prod" style="padding:10px">
      ${p.imagen_url ? `<div class="prod-img-pos"><img src="${LF.esc(p.imagen_url)}" alt="${LF.esc(p.nombre)}" onerror="this.parentElement.style.display='none'"></div>` : ''}
      <div class="nm" style="font-size:13.5px">${LF.ico(p.categoria)} ${LF.esc(p.nombre)}</div>
      <div class="row"><span class="pr" style="font-size:16px">${LF.bs(p.precio_final)}</span><span class="sp"></span><span class="sub" style="margin:0">stock ${p.stock}</span></div>
      <button class="btn sm" data-act="posAdd" data-id="${p.id}" ${p.stock > 0 ? '' : 'disabled'}>+ Agregar</button>
    </div>`).join('')}</div></div>
  <div class="card"><h3>Ticket</h3>${LF.pos.items.map(i => `<div class="ln row" style="border-bottom:1px dashed var(--line);padding:5px 0"><span>${LF.esc(i.nombre)}</span><span class="sp"></span>
    <span class="qty"><button data-act="posMenos" data-id="${i.id}">−</button>${i.cantidad}<button data-act="posAdd" data-id="${i.id}">+</button></span><b>${LF.bs(i.precio * i.cantidad)}</b></div>`).join('') || '<p class="sub">Agregue productos</p>'}
  <div class="ticket"><div class="tot"><span>Total</span><span>${LF.bs(total)}</span></div></div>
  <label>Cliente (opcional)</label><div class="row"><input data-input="buscarCliente" placeholder="Buscar por nombre, CI o teléfono" style="flex:1"></div>
  <div id="resCli" class="sub"></div><div id="cliSel" class="sub">${LF.pos.cliente ? 'Cliente: <b>' + LF.esc(LF.pos.cliente.nombre) + '</b> <a href="#" data-act="posSinCli">quitar</a>' : 'Sin cliente asociado (mayoría de edad verificada por el cajero)'}</div>
  <label>Método de pago</label><div class="row"><label style="margin:0"><input type="radio" name="metodo" value="efectivo" style="width:auto" ${LF.pos.metodo === 'efectivo' ? 'checked' : ''} data-act="posMetodo"> Efectivo</label>
  <label style="margin:0"><input type="radio" name="metodo" value="qr" style="width:auto" ${LF.pos.metodo === 'qr' ? 'checked' : ''} data-act="posMetodo"> QR (Banco Económico)</label></div>
  <p><button class="btn lg ok" data-act="posCobrar" ${LF.pos.items.length && caja ? '' : 'disabled'}>Cobrar ${LF.bs(total)}</button></p>
  <button class="btn sec sm" data-act="posLimpiar">Vaciar ticket</button></div></div>`);
};
LF.inp.posq = el => { clearTimeout(LF._t); LF._t = setTimeout(() => { LF.pos.q = el.value; LF.render(true).then(() => { const i = LF.$('[data-input=posq]'); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }); }, 300); };
LF.acc.posAdd = el => { const id = +el.dataset.id, p = LF.pos.prods.find(x => x.id === id); let l = LF.pos.items.find(x => x.id === id);
  if (l) { if (l.cantidad >= p.stock) return LF.toast('Sin más stock', 'bad'); l.cantidad++; } else LF.pos.items.push({ id, nombre: p.nombre, precio: p.precio_final, cantidad: 1 }); return LF.render(true); };
LF.acc.posMenos = el => { const l = LF.pos.items.find(x => x.id == el.dataset.id); l.cantidad--; if (l.cantidad < 1) LF.pos.items = LF.pos.items.filter(x => x !== l); return LF.render(true); };
LF.acc.posLimpiar = () => { LF.pos.items = []; LF.pos.cliente = null; return LF.render(true); };
LF.acc.posMetodo = el => { LF.pos.metodo = el.value; };
LF.acc.posSinCli = () => { LF.pos.cliente = null; return LF.render(true); };
LF.inp.buscarCliente = el => { clearTimeout(LF._t2); LF._t2 = setTimeout(async () => {
  if (el.value.length < 2) return LF.$('#resCli').innerHTML = '';
  const r = await LF.get('/clientes?q=' + encodeURIComponent(el.value));
  LF.$('#resCli').innerHTML = r.map(c => `<a href="#" data-act="${LF.cliAct || 'posCli'}" data-id="${c.id}" data-nombre="${LF.esc(c.nombre + ' ' + c.apellido)}" data-tel="${LF.esc(c.telefono || '')}">${LF.esc(c.nombre + ' ' + c.apellido)} · CI ${LF.esc(c.ci)}</a>`).join('<br>') || 'Sin resultados'; }, 300); };
LF.acc.posCli = el => { LF.pos.cliente = { id: +el.dataset.id, nombre: el.dataset.nombre }; return LF.render(true); };
LF.acc.posCobrar = async el => {
  el.disabled = true;
  try {
    const r = await LF.post('/ventas', { items: LF.pos.items.map(i => ({ producto_id: i.id, cantidad: i.cantidad })), metodo: LF.pos.metodo, cliente_id: LF.pos.cliente ? LF.pos.cliente.id : undefined });
    LF.pos.items = []; LF.pos.cliente = null;
    if (r.pago && r.pago.error) { LF.toast(r.pago.error.mensaje, 'bad'); }
    else if (r.pago) { LF.verQr(r.pago, () => { LF.render(true); LF.comprobante(r.id); }); }
    else { LF.toast('Venta #' + r.id + ' cobrada: ' + LF.bs(r.total), 'ok'); LF.comprobante(r.id); }
    LF.render(true);
  } finally { el.disabled = false; }
};

LF.rutas['/caja'] = async () => {
  const c = await LF.get('/cajas/actual');
  if (!c) return LF.pagina('Caja', 'No tiene una caja abierta.', `<div class="card" style="max-width:420px"><form id="fcaja">${LF.campo('monto_inicial', 'Monto inicial en efectivo (Bs)', 'number', '0', 'step="0.01" min="0"')}<p><button class="btn" data-act="abrirCaja">Abrir caja</button></p></form></div>`);
  return LF.pagina('Caja abierta', `Desde ${LF.fecha(c.abierta_en)}`, `<div class="grid g4"><div class="card stat"><div class="l">Monto inicial</div><div class="v">${LF.bs(c.monto_inicial)}</div></div><div class="card stat"><div class="l">Ingresos</div><div class="v">${LF.bs(c.ingresos)}</div></div>
    <div class="card stat"><div class="l">Egresos</div><div class="v">${LF.bs(c.egresos)}</div></div><div class="card stat"><div class="l">Esperado en caja</div><div class="v" style="color:var(--brand)">${LF.bs(c.esperado)}</div></div></div>
  <div class="grid g2" style="margin-top:16px"><div class="card"><h3>Registrar ingreso / egreso</h3><form id="fmov"><label>Tipo</label><select name="tipo"><option value="egreso">Egreso</option><option value="ingreso">Ingreso</option></select>
    ${LF.campo('monto', 'Monto (Bs)', 'number', '', 'step="0.01" min="0.01"')}${LF.campo('concepto', 'Concepto')}<p><button class="btn" data-act="movCaja" data-id="${c.id}">Registrar</button></p></form></div>
  <div class="card"><h3>Cerrar caja (arqueo)</h3><form id="fcierre">${LF.campo('monto_contado', 'Efectivo contado (Bs)', 'number', '', 'step="0.01" min="0"')}<p><button class="btn warn" data-act="cerrarCaja" data-id="${c.id}">Cerrar caja</button></p></form></div></div>
  <h2>Movimientos</h2>${LF.tabla([{ t: 'Hora', f: m => LF.fecha(m.created_at) }, { t: 'Tipo', f: m => LF.badge(m.tipo === 'ingreso' ? 'ok' : 'bad').replace(/>.*?</, `>${m.tipo}<`) }, { t: 'Concepto', f: m => LF.esc(m.concepto) }, { t: 'Monto', cls: 'num', f: m => LF.bs(m.monto) }], c.movimientos)}`);
};
LF.acc.abrirCaja = async () => { await LF.post('/cajas/apertura', LF.form('#fcaja')); LF.toast('Caja abierta', 'ok'); return LF.render(); };
LF.acc.movCaja = async el => { await LF.post('/cajas/' + el.dataset.id + '/movimientos', LF.form('#fmov')); LF.toast('Movimiento registrado', 'ok'); return LF.render(); };
LF.acc.cerrarCaja = async el => {
  const r = await LF.post('/cajas/' + el.dataset.id + '/cierre', LF.form('#fcierre'));
  LF.modal(`<h2>Caja cerrada</h2><dl class="kv"><dt>Esperado</dt><dd>${LF.bs(r.esperado)}</dd><dt>Contado</dt><dd>${LF.bs(r.contado)}</dd><dt>Diferencia</dt><dd><b>${LF.bs(r.diferencia)}</b> (${r.resultado})</dd></dl><p class="row"><span class="sp"></span><button class="btn" data-act="cerrar">Aceptar</button></p>`);
  return LF.render();
};

LF.rutas['/ventas'] = async () => {
  const d = await LF.get('/ventas?size=50');
  return LF.pagina('Mis ventas', 'Ventas registradas desde su caja.', LF.tabla([{ t: '#', f: v => v.id }, { t: 'Hora', f: v => LF.fecha(v.created_at) }, { t: 'Cliente', f: v => LF.esc(v.cliente || '—') }, { t: 'Total', cls: 'num', f: v => LF.bs(v.total) },
    { t: 'Estado', f: v => LF.badge(v.estado) }, { t: 'Pago', f: v => LF.badge(v.estado_pago) }, { t: '', f: v => v.estado_pago === 'pagado' ? `<button class="btn sm sec" data-act="comprobante" data-id="${v.id}">Comprobante</button>` : (v.estado_pago === 'pendiente' ? `<button class="btn sm" data-act="cobrarVenta" data-id="${v.id}">Cobrar QR</button>` : '') }], d.items));
};
LF.acc.cobrarVenta = async el => { const p = await LF.post('/pagos', { venta_id: +el.dataset.id, metodo: 'qr' }); LF.verQr(p, () => { LF.render(); LF.comprobante(el.dataset.id); }); };

LF.rutas['/whatsapp'] = async () => {
  const prods = await LF.get('/productos'); LF.wa = LF.wa || { items: [], cli: null }; LF.wa.prods = prods;
  LF.cliAct = 'waCli';
  return LF.pagina('Pedido por WhatsApp', 'Cargue un pedido recibido por WhatsApp a nombre de un cliente registrado (CU-E11).', `<div class="card" style="max-width:720px"><form id="fwa">
   <label>Cliente registrado</label><input data-input="buscarCliente" placeholder="Buscar por nombre, CI o teléfono"><div id="resCli" class="sub"></div><div id="cliSel" class="sub">${LF.wa.cli ? 'Cliente: <b>' + LF.esc(LF.wa.cli.nombre) + '</b>' : 'Sin cliente'}</div>
   <div class="f2"><div>${LF.campo('direccion_entrega', 'Dirección', 'text', '', 'required')}</div><div>${LF.campo('telefono_contacto', 'Teléfono', 'tel', LF.wa.cli ? LF.wa.cli.tel : '', 'required')}</div></div>
   <label>Productos</label><div class="row"><select id="waProd" style="flex:2">${LF.opciones(prods.filter(p => p.stock > 0).map(p => [p.id, p.nombre + ' — ' + LF.bs(p.precio_final)]))}</select><input id="waCant" type="number" min="1" value="1" style="width:90px"><button class="btn sec" data-act="waAdd">Agregar</button></div>
   <div id="waItems">${LF.wa.items.map((i, n) => `<div class="row" style="padding:4px 0">${i.cantidad} × ${LF.esc(i.nombre)} <span class="sp"></span><button class="btn sm bad" data-act="waQuitar" data-id="${n}">✕</button></div>`).join('')}</div>
   <p><button class="btn lg" data-act="waEnviar">Registrar pedido</button></p></form></div>`);
};
LF.acc.waCli = el => { LF.wa.cli = { id: +el.dataset.id, nombre: el.dataset.nombre, tel: el.dataset.tel }; return LF.render(true); };
LF.acc.waAdd = () => { const id = +LF.$('#waProd').value, p = LF.wa.prods.find(x => x.id === id); LF.wa.items.push({ producto_id: id, nombre: p.nombre, cantidad: +LF.$('#waCant').value || 1 }); return LF.render(true); };
LF.acc.waQuitar = el => { LF.wa.items.splice(+el.dataset.id, 1); return LF.render(true); };
LF.acc.waEnviar = async () => {
  if (!LF.wa.cli) return LF.toast('Seleccione un cliente registrado', 'bad');
  const p = await LF.post('/pedidos/whatsapp', { ...LF.form('#fwa'), cliente_id: LF.wa.cli.id, items: LF.wa.items.map(i => ({ producto_id: i.producto_id, cantidad: i.cantidad })) });
  LF.wa = { items: [], cli: null }; LF.toast('Pedido #' + p.id + ' registrado', 'ok'); return LF.render(true);
};
