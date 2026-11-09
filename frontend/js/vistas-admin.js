// Vistas del administrador: panel, usuarios, productos, promociones, pedidos, cobranzas, auditoría y respaldos.
window.LF = window.LF || {};
LF.ROLES = [['cliente', 'Cliente'], ['cajero', 'Cajero'], ['empleado', 'Bodega'], ['repartidor', 'Repartidor'], ['administrador', 'Administrador']];
LF.rolNombre = r => (LF.ROLES.find(x => x[0] === r) || [0, r])[1];

LF.rutas['/panel'] = async () => {
  const r = await LF.get('/reportes/resumen'); const st = (k) => r.por_estado[k] || 0;
  return LF.pagina('Panel de control', 'Resumen del día (CU-E10).', `<div class="grid g4">
    <div class="card stat"><div class="l">Ventas pagadas hoy</div><div class="v">${r.hoy.ventas}</div></div><div class="card stat"><div class="l">Monto cobrado hoy</div><div class="v" style="color:var(--pag)">${LF.bs(r.hoy.monto)}</div></div>
    <div class="card stat"><div class="l">Deliveries abiertos</div><div class="v" style="color:var(--dis)">${r.deliveries_abiertos}</div></div><div class="card stat"><div class="l">Productos con stock bajo</div><div class="v" style="color:var(--bad)">${r.stock_bajo}</div></div></div>
  <div class="grid g2" style="margin-top:16px"><div class="card"><h3>Pedidos por estado</h3>${['pendiente', 'pagada', 'en_camino', 'entregada', 'no_entregado'].map(k => `<div class="row" style="padding:3px 0">${LF.badge(k)}<span class="sp"></span><b>${st(k)}</b></div>`).join('')}</div>
  <div class="card"><h3>Cobros de hoy</h3>${r.cobros_hoy.map(c => `<div class="row" style="padding:3px 0">${LF.esc(c.metodo)} (${c.n})<span class="sp"></span><b>${LF.bs(c.monto)}</b></div>`).join('') || '<p class="sub">Sin cobros todavía</p>'}</div>
  <div class="card"><h3>Más vendidos hoy</h3>${r.top_productos.map(t => `<div class="row" style="padding:3px 0">${LF.esc(t.nombre)}<span class="sp"></span><b>${t.unidades}</b></div>`).join('') || '<p class="sub">Sin ventas todavía</p>'}</div></div>`);
};

// ---- Usuarios ----
LF.filtroRol = '';
LF.rutas['/usuarios'] = async () => {
  const u = await LF.get('/usuarios' + (LF.filtroRol ? '?rol=' + LF.filtroRol : ''));
  return LF.pagina('Usuarios y roles', 'Altas, cambios de rol y bajas (CU-S04, CU-S05).', `<div class="row" style="margin-bottom:10px"><select data-act="filtroRol" style="max-width:220px">${LF.opciones(LF.ROLES, LF.filtroRol, 'Todos los roles')}</select><span class="sp"></span><button class="btn" data-act="formUsuario">+ Nuevo usuario</button></div>
  ${LF.tabla([{ t: 'Usuario', f: x => `<b>${LF.esc(x.usuario)}</b>` }, { t: 'Nombre', f: x => LF.esc(x.nombre + ' ' + x.apellido) }, { t: 'CI', f: x => LF.esc(x.ci) }, { t: 'Rol', f: x => `<span class="badge">${LF.rolNombre(x.rol)}</span>` }, { t: 'Edad', f: x => x.edad },
    { t: 'Estado', f: x => x.activo ? '<span class="badge b-ok">activo</span>' : '<span class="badge b-bad">inactivo</span>' },
    { t: '', f: x => `<button class="btn sm sec" data-act="formUsuario" data-id="${x.id}">Editar</button> <button class="btn sm bad" data-act="bajaUsuario" data-id="${x.id}" data-nombre="${LF.esc(x.usuario)}">Eliminar</button>` }], u)}`);
};
LF.acc.filtroRol = el => { LF.filtroRol = el.value; return LF.render(true); };
LF.acc.formUsuario = async el => {
  const x = el.dataset.id ? (await LF.get('/usuarios')).find(u => u.id == el.dataset.id) : {};
  LF.modal(`<h2>${x.id ? 'Editar' : 'Nuevo'} usuario</h2><form id="fu"><div class="f2"><div>${LF.campo('nombre', 'Nombre', 'text', x.nombre || '', 'required')}</div><div>${LF.campo('apellido', 'Apellido', 'text', x.apellido || '', 'required')}</div>
    <div>${LF.campo('ci', 'CI', 'text', x.ci || '', 'required')}</div><div>${LF.campo('fecha_nacimiento', 'Fecha de nacimiento', 'date', (x.fecha_nacimiento || '').slice(0, 10))}</div>
    <div>${LF.campo('usuario', 'Usuario', 'text', x.usuario || '', 'required')}</div><div>${LF.campo('telefono', 'Teléfono', 'tel', x.telefono || '')}</div>
    <div><label>Rol</label><select name="rol">${LF.opciones(LF.ROLES, x.rol || 'cliente')}</select></div><div><label>Estado</label><select name="activo">${LF.opciones([[1, 'Activo'], [0, 'Inactivo']], x.activo ?? 1)}</select></div></div>
    ${LF.campo('password', x.id ? 'Nueva contraseña (dejar vacío para no cambiar)' : 'Contraseña (mín. 8)', 'password', '', x.id ? '' : 'required')}
    <p class="row"><button class="btn" data-act="guardarUsuario" data-id="${x.id || ''}">Guardar</button><button class="btn sec" data-act="cerrar">Cancelar</button></p></form>`, true);
};
LF.acc.guardarUsuario = async el => { const f = LF.form('#fu'); el.dataset.id ? await LF.put('/usuarios/' + el.dataset.id, f) : await LF.post('/usuarios', f); LF.cerrar(); LF.toast('Usuario guardado', 'ok'); return LF.render(true); };
LF.acc.bajaUsuario = async el => { if (!confirm('¿Eliminar al usuario «' + el.dataset.nombre + '»? Si tiene historial se desactivará.')) return; const r = await LF.del('/usuarios/' + el.dataset.id); LF.toast(r.mensaje, 'ok'); return LF.render(true); };

// ---- Productos y categorías ----
LF.rutas['/productos'] = async () => {
  const [p, cats] = await Promise.all([LF.get('/productos?todos=1'), LF.get('/categorias')]); LF.cats = cats;
  return LF.pagina('Productos', 'Catálogo y precios (CU-E06).', `<div class="row" style="margin-bottom:10px"><button class="btn" data-act="formProducto">+ Nuevo producto</button><button class="btn sec" data-act="formCategoria">+ Categoría</button><span class="sp"></span>${cats.map(c => `<span class="badge">${LF.esc(c.nombre)}</span>`).join(' ')}</div>
  ${LF.tabla([
    { t: 'Producto', f: x => `<div class="row" style="gap:8px">${x.imagen_url ? `<img src="${LF.esc(x.imagen_url)}" style="width:34px;height:34px;object-fit:contain;background:#fff;border-radius:6px;border:1px solid var(--line)">` : `<span style="font-size:20px">${LF.ico(x.categoria)}</span>`}<b>${LF.esc(x.nombre)}</b></div>` },
    { t: 'Categoría', f: x => LF.esc(x.categoria || '—') },
    { t: 'Precio', cls: 'num', f: x => LF.bs(x.precio) },
    { t: 'Stock', cls: 'num', f: x => x.stock },
    { t: 'Estado', f: x => x.activo ? '<span class="badge b-ok">activo</span>' : '<span class="badge b-bad">inactivo</span>' },
    { t: '', f: x => `<button class="btn sm sec" data-act="formProducto" data-id="${x.id}">Editar</button> <button class="btn sm bad" data-act="bajaProducto" data-id="${x.id}" data-nombre="${LF.esc(x.nombre)}">Eliminar</button>` }
  ], p)}`);
};
LF.acc.formProducto = async el => {
  const x = el.dataset.id ? (await LF.get('/productos?todos=1')).find(u => u.id == el.dataset.id) : {};
  const imgsDisponibles = [
    ['', '— Seleccionar imagen local —'],
    ['img/aranjues.jpeg', 'Vino Aranjuez (aranjues.jpeg)'],
    ['img/blacklabel.jpeg', 'Whisky Black Label (blacklabel.jpeg)'],
    ['img/buckanan.jpg', 'Whisky Buchanan\'s (buckanan.jpg)'],
    ['img/chivas.jpeg', 'Whisky Chivas Regal (chivas.jpeg)'],
    ['img/jackd.jpg', 'Whisky Jack Daniel\'s (jackd.jpg)'],
    ['img/jhony.jpg', 'Whisky Red Label (jhony.jpg)'],
    ['img/3.jpeg', 'Whisky Royal Salute (3.jpeg)'],
    ['img/kolberg.jpeg', 'Vino Kohlberg (kolberg.jpeg)'],
    ['img/images.jpeg', 'Vino Don Enzo (images.jpeg)'],
    ['img/navar1.jpeg', 'Vino Navarro Correas (navar1.jpeg)'],
    ['img/uvairenda.jpeg', 'Vino 1750 Uvairenda (uvairenda.jpeg)'],
    ['img/valle.jpeg', 'Vino Valle de la Concepción (valle.jpeg)'],
    ['img/4.jpeg', 'Vino TRI Gran Reserva (4.jpeg)'],
    ['img/cerveza1.jpg', 'Cerveza Six Pack (cerveza1.jpg)'],
    ['img/pilsener.jpeg', 'Cerveza Paceña 620ml (pilsener.jpeg)'],
    ['img/huari.jpeg', 'Cerveza Huari (huari.jpeg)'],
    ['img/taquiña.jpeg', 'Cerveza Taquiña (taquiña.jpeg)'],
    ['img/potosina.jpeg', 'Cerveza Potosina (potosina.jpeg)'],
    ['img/sureña.jpeg', 'Cerveza Sureña (sureña.jpeg)'],
    ['img/ducal.jpeg', 'Cerveza Ducal (ducal.jpeg)'],
    ['img/nuevo.jpg', 'Cerveza Cordillera Lata (nuevo.jpg)'],
    ['img/sausini.jpeg', 'Singani Sausini (sausini.jpeg)'],
    ['img/combo1.jpg', 'Combo Chuflay Casa Real (combo1.jpg)'],
    ['img/combo2.jpeg', 'Combo Red Label (combo2.jpeg)'],
    ['img/promocion2.jpeg', 'Combo Chuflay Rujero (promocion2.jpeg)'],
    ['img/promocion1.jpg', 'Trilogía de Vinos (promocion1.jpg)'],
    ['img/promo3.jpg', 'Set de Lujo Whisky (promo3.jpg)']
  ];
  LF.modal(`<h2>${x.id ? 'Editar' : 'Nuevo'} producto</h2>
   <form id="fpr">${LF.campo('nombre', 'Nombre', 'text', x.nombre || '', 'required')}${LF.campo('descripcion', 'Descripción', 'text', x.descripcion || '')}
   <div class="f2"><div>${LF.campo('precio', 'Precio (Bs)', 'number', x.precio ?? '', 'step="0.01" min="0" required')}</div><div>${LF.campo('stock_minimo', 'Stock mínimo', 'number', x.stock_minimo ?? 5, 'min="0"')}</div>
   ${x.id ? '' : `<div>${LF.campo('stock', 'Stock inicial', 'number', 0, 'min="0"')}</div>`}<div><label>Categoría</label><select name="categoria_id">${LF.opciones(LF.cats.map(c => [c.id, c.nombre]), x.categoria_id, 'Sin categoría')}</select></div>
   <div>
     <label>Imagen</label>
     <select onchange="document.querySelector('#inpImgUrl').value=this.value">${imgsDisponibles.map(([v, t]) => `<option value="${v}" ${v === (x.imagen_url || '') ? 'selected' : ''}>${t}</option>`).join('')}</select>
     <input id="inpImgUrl" name="imagen_url" type="text" value="${LF.esc(x.imagen_url || '')}" placeholder="O escriba URL/ruta de imagen" style="margin-top:6px">
   </div>
   <div><label>Estado</label><select name="activo">${LF.opciones([[1, 'Activo'], [0, 'Inactivo']], x.activo ?? 1)}</select></div></div>
   <p class="row"><button class="btn" data-act="guardarProducto" data-id="${x.id || ''}">Guardar</button><button class="btn sec" data-act="cerrar">Cancelar</button></p></form>`, true);
};
LF.acc.guardarProducto = async el => { const f = LF.form('#fpr'); el.dataset.id ? await LF.put('/productos/' + el.dataset.id, f) : await LF.post('/productos', f); LF.cerrar(); LF.toast('Producto guardado', 'ok'); return LF.render(true); };
LF.acc.bajaProducto = async el => { if (!confirm('¿Eliminar «' + el.dataset.nombre + '»? Si tiene ventas se desactivará.')) return; const r = await LF.del('/productos/' + el.dataset.id); LF.toast(r.mensaje, 'ok'); return LF.render(true); };
LF.acc.formCategoria = () => LF.modal(`<h2>Nueva categoría</h2><form id="fcat">${LF.campo('nombre', 'Nombre', 'text', '', 'required')}<p class="row"><button class="btn" data-act="guardarCategoria">Guardar</button><button class="btn sec" data-act="cerrar">Cancelar</button></p></form>`);
LF.acc.guardarCategoria = async () => { await LF.post('/categorias', LF.form('#fcat')); LF.cerrar(); return LF.render(true); };

// ---- Promociones ----
LF.rutas['/promociones'] = async () => {
  const [pr, prods, cats] = await Promise.all([LF.get('/promociones'), LF.get('/productos?todos=1'), LF.get('/categorias')]); LF.pp = { prods, cats };
  return LF.pagina('Promociones y descuentos', 'Vigentes se aplican solas al catálogo, al carrito y al POS (CU-E09).', `<p><button class="btn" data-act="formPromo">+ Nueva promoción</button></p>
  ${LF.tabla([{ t: 'Nombre', f: x => `<b>${LF.esc(x.nombre)}</b>` }, { t: 'Descuento', f: x => x.tipo === 'porcentaje' ? x.valor + ' %' : LF.bs(x.valor) }, { t: 'Aplica a', f: x => LF.esc(x.producto || x.categoria || 'Todos los productos') },
   { t: 'Vigencia', f: x => LF.esc(String(x.desde).slice(0, 10)) + ' → ' + LF.esc(String(x.hasta).slice(0, 10)) }, { t: 'Estado', f: x => x.activo ? '<span class="badge b-ok">activa</span>' : '<span class="badge b-bad">inactiva</span>' },
   { t: '', f: x => `<button class="btn sm sec" data-act="formPromo" data-id="${x.id}">Editar</button> <button class="btn sm bad" data-act="bajaPromo" data-id="${x.id}">Eliminar</button>` }], pr)}`);
};
LF.acc.formPromo = async el => {
  const x = el.dataset.id ? (await LF.get('/promociones')).find(u => u.id == el.dataset.id) : {}; const hoy = new Date().toISOString().slice(0, 10);
  LF.modal(`<h2>${x.id ? 'Editar' : 'Nueva'} promoción</h2><form id="fpm">${LF.campo('nombre', 'Nombre', 'text', x.nombre || '', 'required')}
   <div class="f2"><div><label>Tipo</label><select name="tipo">${LF.opciones([['porcentaje', 'Porcentaje'], ['monto', 'Monto fijo (Bs)']], x.tipo)}</select></div><div>${LF.campo('valor', 'Valor', 'number', x.valor ?? '', 'step="0.01" min="0.01" required')}</div>
   <div><label>Producto (opcional)</label><select name="producto_id">${LF.opciones(LF.pp.prods.map(p => [p.id, p.nombre]), x.producto_id, '—')}</select></div><div><label>Categoría (opcional)</label><select name="categoria_id">${LF.opciones(LF.pp.cats.map(p => [p.id, p.nombre]), x.categoria_id, '—')}</select></div>
   <div>${LF.campo('desde', 'Desde', 'date', String(x.desde || hoy).slice(0, 10), 'required')}</div><div>${LF.campo('hasta', 'Hasta', 'date', String(x.hasta || hoy).slice(0, 10), 'required')}</div></div>
   <label>Estado</label><select name="activo">${LF.opciones([[1, 'Activa'], [0, 'Inactiva']], x.activo ?? 1)}</select><p class="sub">Si no elige producto ni categoría, aplica a todo el catálogo.</p>
   <p class="row"><button class="btn" data-act="guardarPromo" data-id="${x.id || ''}">Guardar</button><button class="btn sec" data-act="cerrar">Cancelar</button></p></form>`, true);
};
LF.acc.guardarPromo = async el => { const f = LF.form('#fpm'); el.dataset.id ? await LF.put('/promociones/' + el.dataset.id, f) : await LF.post('/promociones', f); LF.cerrar(); LF.toast('Promoción guardada', 'ok'); return LF.render(true); };
LF.acc.bajaPromo = async el => { if (!confirm('¿Eliminar la promoción?')) return; await LF.del('/promociones/' + el.dataset.id); return LF.render(true); };

// ---- Pedidos y asignación ----
LF.filtroPed = '';
LF.rutas['/pedidos-admin'] = async () => {
  const [d, reps] = await Promise.all([LF.get('/pedidos?size=60' + (LF.filtroPed ? '&estado=' + LF.filtroPed : '')), LF.get('/usuarios?rol=repartidor')]); LF.reps = reps.filter(r => r.activo);
  return LF.pagina('Pedidos', 'Supervisión y asignación de repartidores (CU-D02, CU-D08).', `<div class="row" style="margin-bottom:10px"><select data-act="filtroPed" style="max-width:220px">${LF.opciones([['pendiente', 'Pendientes'], ['en_camino', 'En camino'], ['entregada', 'Entregados'], ['no_entregado', 'No entregados'], ['pagada', 'Pagadas (mostrador)']], LF.filtroPed, 'Todos los estados')}</select></div>
  ${LF.tabla([{ t: '#', f: v => v.id }, { t: 'Fecha', f: v => LF.fecha(v.created_at) }, { t: 'Tipo', f: v => LF.esc(v.tipo_venta) + (v.canal === 'whatsapp' ? ' 💬' : '') }, { t: 'Cliente', f: v => LF.esc(v.cliente || '—') }, { t: 'Total', cls: 'num', f: v => LF.bs(v.total) },
   { t: 'Estado', f: v => LF.badge(v.estado) }, { t: 'Pago', f: v => LF.badge(v.estado_pago) },
   { t: 'Repartidor', f: v => v.tipo_venta === 'delivery' && ['pendiente', 'en_camino'].includes(v.estado) ? `<select data-act="asignar" data-id="${v.id}" style="min-width:150px">${LF.opciones(LF.reps.map(r => [r.id, r.nombre + ' ' + r.apellido]), v.repartidor_id, 'Sin asignar')}</select>` : LF.esc(v.repartidor || '—') }], d.items)}`);
};
LF.acc.filtroPed = el => { LF.filtroPed = el.value; return LF.render(true); };
LF.acc.asignar = async el => { if (!el.value) return; await LF.put('/pedidos/' + el.dataset.id + '/asignacion', { repartidor_id: +el.value }); LF.toast('Pedido asignado', 'ok'); };

// ---- Cobranzas y cajas ----
LF.rutas['/cobranzas'] = async () => {
  const [d, cajas] = await Promise.all([LF.get('/pagos?size=60'), LF.get('/cajas')]); const r = d.resumen;
  return LF.pagina('Cobranzas y cajas', 'Reporte de pagos (CU-P08) y arqueos de caja.', `<div class="grid g4"><div class="card stat"><div class="l">Pagos registrados</div><div class="v">${r.n}</div></div><div class="card stat"><div class="l">Confirmado</div><div class="v" style="color:var(--pag)">${LF.bs(r.confirmado)}</div></div>
   <div class="card stat"><div class="l">En efectivo</div><div class="v">${LF.bs(r.efectivo)}</div></div><div class="card stat"><div class="l">Por QR</div><div class="v">${LF.bs(r.qr)}</div></div></div>
  <h2>Pagos</h2>${LF.tabla([{ t: '#', f: p => p.id }, { t: 'Venta', f: p => p.venta_id }, { t: 'Fecha', f: p => LF.fecha(p.created_at) }, { t: 'Método', f: p => LF.esc(p.metodo) }, { t: 'Monto', cls: 'num', f: p => LF.bs(p.monto) }, { t: 'Estado', f: p => LF.badge(p.estado) },
   { t: '', f: p => p.estado === 'confirmado' ? `<button class="btn sm bad" data-act="anularPago" data-id="${p.id}">Anular</button>` : '' }], d.items)}
  <h2>Cajas</h2>${LF.tabla([{ t: '#', f: c => c.id }, { t: 'Cajero', f: c => LF.esc(c.cajero) }, { t: 'Apertura', f: c => LF.fecha(c.abierta_en) }, { t: 'Cierre', f: c => c.cerrada_en ? LF.fecha(c.cerrada_en) : '<span class="badge b-pendiente">abierta</span>' },
   { t: 'Inicial', cls: 'num', f: c => LF.bs(c.monto_inicial) }, { t: 'Esperado', cls: 'num', f: c => c.monto_esperado == null ? '—' : LF.bs(c.monto_esperado) }, { t: 'Contado', cls: 'num', f: c => c.monto_contado == null ? '—' : LF.bs(c.monto_contado) }], cajas)}`);
};
LF.acc.anularPago = async el => { const m = prompt('Motivo de la anulación (obligatorio):'); if (!m) return; const r = await LF.post('/pagos/' + el.dataset.id + '/anular', { motivo: m }); LF.toast(r.mensaje, 'ok'); return LF.render(true); };

// ---- Auditoría y respaldos ----
LF.audPag = 1; LF.audFiltro = {};
LF.rutas['/auditoria'] = async () => {
  const q = new URLSearchParams({ page: LF.audPag, size: 30, ...LF.audFiltro }); const d = await LF.get('/auditoria?' + q);
  return LF.pagina('Bitácora de auditoría', 'Quién hizo qué y cuándo (CU-S06).', `<div class="row" style="margin-bottom:10px"><input data-input="audAccion" placeholder="Filtrar por acción (ej. PedidoCreado)" value="${LF.esc(LF.audFiltro.accion || '')}" style="max-width:320px"><span class="sp"></span>
   <button class="btn sm sec" data-act="audPrev" ${LF.audPag <= 1 ? 'disabled' : ''}>◀</button><span>Página ${d.page} de ${Math.max(1, d.paginas)} · ${d.total} registros</span><button class="btn sm sec" data-act="audNext" ${LF.audPag >= d.paginas ? 'disabled' : ''}>▶</button></div>
  ${LF.tabla([{ t: 'Fecha', f: a => LF.fecha(a.created_at) }, { t: 'Usuario', f: a => LF.esc(a.usuario || 'sistema') }, { t: 'Acción', f: a => `<b>${LF.esc(a.accion)}</b>` }, { t: 'Entidad', f: a => LF.esc(a.entidad) + (a.entidad_id ? ' #' + a.entidad_id : '') }, { t: 'Detalle', f: a => `<span class="mono">${LF.esc(a.detalle || '')}</span>` }, { t: 'IP', f: a => LF.esc(a.ip || '') }], d.items)}`);
};
LF.inp.audAccion = el => { clearTimeout(LF._t); LF._t = setTimeout(() => { LF.audFiltro = el.value ? { accion: el.value } : {}; LF.audPag = 1; LF.render(true).then(() => { const i = LF.$('[data-input=audAccion]'); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }); }, 400); };
LF.acc.audPrev = () => { LF.audPag--; return LF.render(true); }; LF.acc.audNext = () => { LF.audPag++; return LF.render(true); };

LF.rutas['/respaldos'] = async () => {
  const l = await LF.get('/admin/respaldos');
  return LF.pagina('Respaldos de la base de datos', 'Copias con mysqldump (CU-S07). Se guardan en backend/respaldos/.', `<p><button class="btn" data-act="respaldar">Crear respaldo ahora</button></p>
  ${LF.tabla([{ t: 'Archivo', f: r => `<span class="mono">${LF.esc(r.archivo)}</span>` }, { t: 'Tamaño', cls: 'num', f: r => (r.bytes / 1024).toFixed(1) + ' KB' }], l, 'Aún no hay respaldos.')}
  <div class="note">Para restaurar: <span class="mono">mysql -u root licofast &lt; backend/respaldos/ARCHIVO.sql</span> (o importe el archivo en phpMyAdmin).</div>`);
};
LF.acc.respaldar = async () => { const r = await LF.post('/admin/respaldo'); LF.toast('Respaldo creado: ' + r.archivo, 'ok'); return LF.render(true); };
