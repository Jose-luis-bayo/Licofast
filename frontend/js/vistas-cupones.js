// Cupones y vales: "Mis cupones" del cliente y administración de cupones (crear, regalar un vale, activar/desactivar, recompensas).
LF.rutas['/mis-cupones'] = async () => {
  const mis = await LF.get('/mis-cupones');
  return LF.pagina('Mis cupones', 'Use el código en el carrito al confirmar su pedido. Los premios por compras frecuentes y antigüedad aparecen aquí solos.', mis.length ? `<div class="grid">${mis.map(m => `<div class="card"><h3 style="margin:0">${LF.esc(m.codigo)}</h3>
    <p class="sub">${LF.esc(m.descripcion || '')}</p><p><b>${m.tipo === 'porcentaje' ? m.valor + ' % de descuento' : LF.bs(m.valor) + ' de descuento'}</b></p>
    <p class="sub">${m.minimo_compra > 0 ? 'Compra mínima ' + LF.bs(m.minimo_compra) + '. ' : ''}${m.vigente_hasta ? 'Vence el ' + LF.esc(String(m.vigente_hasta).slice(0, 10)) + '.' : 'Sin vencimiento.'}</p>
    ${m.usable ? '<span class="badge b-ok">disponible</span>' : `<span class="badge b-bad">${LF.esc(m.motivo)}</span>`} ${m.origen === 'recompensa' ? '<span class="badge">🎁 recompensa</span>' : m.personal ? '<span class="badge">🎟️ vale personal</span>' : ''}</div>`).join('')}</div>`
    : '<div class="card empty">Por ahora no tiene cupones. ¡Pida seguido y gane recompensas!</div>');
};

LF.rutas['/cupones'] = async () => {
  const cs = await LF.get('/cupones');
  return LF.pagina('Cupones y vales', 'Cree códigos públicos, regale vales a un cliente o premie a los clientes frecuentes y antiguos.', `<div class="row" style="margin-bottom:10px">
    <button class="btn" data-act="formCupon">+ Nuevo cupón</button><button class="btn sec" data-act="formVale">🎟️ Regalar vale a un cliente</button><button class="btn sec" data-act="recompensas">🎁 Generar recompensas</button></div>
    ${LF.tabla([{ t: 'Código', f: x => `<b>${LF.esc(x.codigo)}</b>${x.origen === 'recompensa' ? ' 🎁' : ''}` }, { t: 'Descuento', f: x => x.tipo === 'porcentaje' ? x.valor + ' %' : LF.bs(x.valor) },
      { t: 'Para', f: x => x.cliente ? LF.esc(x.cliente) : 'Todos' }, { t: 'Usos', f: x => x.usos + (x.usos_max ? ' / ' + x.usos_max : '') }, { t: 'Vence', f: x => x.vigente_hasta ? LF.esc(String(x.vigente_hasta).slice(0, 10)) : '—' },
      { t: 'Estado', f: x => x.activo ? '<span class="badge b-ok">activo</span>' : '<span class="badge b-bad">inactivo</span>' },
      { t: '', f: x => `<button class="btn sm sec" data-act="alternarCupon" data-id="${x.id}" data-activo="${x.activo ? 0 : 1}">${x.activo ? 'Desactivar' : 'Activar'}</button>` }], cs)}`);
};
LF.acc.formCupon = () => LF.modal(`<h2>Nuevo cupón</h2><form id="fcp">${LF.campo('codigo', 'Código (letras y números)', 'text', '', 'required maxlength="30"')}${LF.campo('descripcion', 'Descripción (opcional)')}
  <div class="f2"><div><label>Tipo</label><select name="tipo">${LF.opciones([['porcentaje', 'Porcentaje'], ['monto', 'Monto fijo (Bs)']], 'porcentaje')}</select></div><div>${LF.campo('valor', 'Valor', 'number', '', 'step="0.01" min="0.01" required')}</div>
  <div>${LF.campo('minimo_compra', 'Compra mínima (Bs)', 'number', '0', 'step="0.01" min="0"')}</div><div>${LF.campo('usos_max', 'Usos totales (vacío = ilimitado)', 'number', '', 'min="1"')}</div>
  <div>${LF.campo('usos_por_cliente', 'Usos por cliente', 'number', '1', 'min="1"')}</div><div>${LF.campo('vigente_hasta', 'Vence el (opcional)', 'date')}</div></div>
  <p class="row"><button class="btn" data-act="guardarCupon">Crear</button><button class="btn sec" data-act="cerrar">Cancelar</button></p></form>`, true);
LF.acc.guardarCupon = async () => {
  const f = LF.form('#fcp'); for (const k of Object.keys(f)) if (f[k] === '') delete f[k];
  const r = await LF.post('/cupones', f); LF.cerrar(); LF.toast('Cupón ' + r.codigo + ' creado', 'ok'); return LF.render(true);
};
LF.acc.formVale = async () => {
  const cl = (await LF.get('/usuarios?rol=cliente')).filter(u => u.activo);
  LF.modal(`<h2>Regalar un vale</h2><form id="fvl"><label>Cliente</label><select name="usuario_id">${LF.opciones(cl.map(u => [u.id, `${u.nombre} ${u.apellido} (${u.usuario})`]))}</select>
  <div class="f2"><div><label>Tipo</label><select name="tipo">${LF.opciones([['monto', 'Monto fijo (Bs)'], ['porcentaje', 'Porcentaje']], 'monto')}</select></div><div>${LF.campo('valor', 'Valor', 'number', '', 'step="0.01" min="0.01" required')}</div>
  <div>${LF.campo('dias', 'Válido por (días)', 'number', '30', 'min="1"')}</div><div>${LF.campo('descripcion', 'Mensaje (opcional)')}</div></div>
  <p class="sub">Se genera un código único de un solo uso, visible para el cliente en «Mis cupones».</p>
  <p class="row"><button class="btn" data-act="guardarVale">Regalar</button><button class="btn sec" data-act="cerrar">Cancelar</button></p></form>`, true);
};
LF.acc.guardarVale = async () => {
  const f = LF.form('#fvl'); for (const k of Object.keys(f)) if (f[k] === '') delete f[k];
  const r = await LF.post('/cupones/asignar', f); LF.cerrar(); LF.toast(`Vale ${r.codigo} para ${r.cliente}`, 'ok'); return LF.render(true);
};
LF.acc.alternarCupon = async el => { await LF.put('/cupones/' + el.dataset.id, { activo: +el.dataset.activo }); return LF.render(true); };
LF.acc.recompensas = async () => { const r = await LF.post('/cupones/recompensas'); LF.toast(r.mensaje, 'ok'); return LF.render(true); };
