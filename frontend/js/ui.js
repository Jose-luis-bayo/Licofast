// Utilidades de interfaz: plantillas, mensajes, ventanas y formato.
window.LF = window.LF || {};
LF.esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
LF.bs = n => 'Bs ' + Number(n || 0).toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
LF.fecha = s => s ? String(s).replace('T', ' ').slice(0, 16) : '—';
LF.badge = (e) => `<span class="badge b-${LF.esc(e)}">${LF.esc(String(e).replace('_', ' '))}</span>`;
LF.ico = c => ({ Ron: '🥃', Vodka: '🍸', Whisky: '🥃', Cerveza: '🍺', Vino: '🍷', Singani: '🍇', 'Combos y Promociones': '🎁' }[c] || '🍾');
LF.$ = (s, r = document) => r.querySelector(s);
LF.$$ = (s, r = document) => [...r.querySelectorAll(s)];

LF.toast = (msg, tipo = '') => {
  const t = document.createElement('div'); t.className = 'toast ' + tipo; t.textContent = msg;
  LF.$('#toasts').appendChild(t); setTimeout(() => t.remove(), 4500);
};
LF.err = e => LF.toast(e && e.mensaje ? e.mensaje : 'Ocurrió un error', 'bad');

LF.modal = (html, ancho = false) => {
  const m = LF.$('#modal'); m.hidden = false;
  m.innerHTML = `<div class="box ${ancho ? 'wide' : ''}">${html}</div>`;
  m.onclick = ev => { if (ev.target === m) LF.cerrar(); };
};
LF.cerrar = () => { const m = LF.$('#modal'); m.hidden = true; m.innerHTML = ''; clearInterval(LF._poll); };

// Acciones declarativas: <button data-act="nombre" data-id="3">  →  LF.acc.nombre(elemento)
LF.acc = {};
document.addEventListener('click', ev => {
  const el = ev.target.closest('[data-act]');
  if (!el) return;
  const fn = LF.acc[el.dataset.act];
  if (fn) { ev.preventDefault(); Promise.resolve(fn(el, ev)).catch(LF.err); }
});

// Lee un formulario como objeto (vacíos = omitidos)
LF.form = (sel) => {
  const o = {};
  LF.$$(sel + ' [name]').forEach(el => {
    if (el.type === 'checkbox') o[el.name] = el.checked;
    else if (el.type === 'radio') { if (el.checked) o[el.name] = el.value; }
    else if (el.value !== '') o[el.name] = el.value;
  });
  return o;
};

LF.campo = (nombre, etiqueta, tipo = 'text', valor = '', extra = '') =>
  `<label>${etiqueta}</label><input name="${nombre}" type="${tipo}" value="${LF.esc(valor)}" ${extra}>`;
LF.opciones = (lista, sel, vacio) => (vacio ? `<option value="">${vacio}</option>` : '') + lista.map(([v, t]) => `<option value="${LF.esc(v)}" ${String(v) === String(sel) ? 'selected' : ''}>${LF.esc(t)}</option>`).join('');

LF.pagina = (titulo, sub, cuerpo) => `<h1>${titulo}</h1><p class="sub">${sub || ''}</p>${cuerpo}`;
LF.tabla = (cols, filas, vacio = 'Sin registros') =>
  filas.length ? `<div class="tw"><table><thead><tr>${cols.map(c => `<th class="${c.cls || ''}">${c.t}</th>`).join('')}</tr></thead><tbody>${filas.map(f => `<tr>${cols.map(c => `<td class="${c.cls || ''}">${c.f(f)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
  : `<div class="card empty">${vacio}</div>`;

// Muestra un QR de pago y consulta el estado hasta confirmarse
LF.verQr = (pago, onPagado) => {
  LF._pagoActual = pago; LF._onPagadoActual = onPagado;
  const tipo = LF._qrTipo || 'dinamico';
  const qr = qrcode(0, 'M'); qr.addData(pago.qr_payload); qr.make();
  LF.modal(`<h2>Pagar con QR</h2>
    <div class="row" style="justify-content:center;margin-bottom:12px;gap:6px">
      <button class="btn sm ${tipo === 'dinamico' ? '' : 'sec'}" data-act="qrModo" data-tipo="dinamico">QR Dinámico</button>
      <button class="btn sm ${tipo === 'oficial' ? '' : 'sec'}" data-act="qrModo" data-tipo="oficial">QR Banco Económico</button>
    </div>
    <div class="qrbox" style="min-height:230px;display:flex;align-items:center;justify-content:center">
      ${tipo === 'oficial' ? '<img src="img/QR.jpg" alt="QR Banco Económico" style="max-height:240px;max-width:240px;border-radius:8px;object-fit:contain">' : qr.createSvgTag({ cellSize: 6, margin: 2, scalable: true })}
    </div>
    <p style="text-align:center;font-size:22px;font-weight:800;margin:8px 0">${LF.bs(pago.monto)}</p>
    <p class="mono" style="text-align:center">Ref: ${LF.esc(pago.referencia)}</p>
    <div id="qrEstado" class="note">⏳ Esperando la confirmación del banco… vence ${LF.fecha(pago.qr_expira_en)}</div>
    <div class="row noprint"><button class="btn sec sm" data-act="simularQr" data-ref="${LF.esc(pago.referencia)}">Demo: simular pago del banco</button><span class="sp"></span><button class="btn sec" data-act="cerrar">Cerrar</button></div>`);
  clearInterval(LF._poll);
  LF._poll = setInterval(async () => {
    try {
      const p = await LF.get('/pagos/' + pago.id);
      if (p.estado === 'confirmado') { clearInterval(LF._poll); LF.$('#qrEstado').className = 'note ok'; LF.$('#qrEstado').innerHTML = '✅ Pago confirmado'; LF.toast('Pago confirmado', 'ok'); setTimeout(() => { LF.cerrar(); onPagado && onPagado(p); }, 900); }
      else if (p.estado === 'vencido' || p.estado === 'anulado') { clearInterval(LF._poll); LF.$('#qrEstado').className = 'note bad'; LF.$('#qrEstado').innerHTML = 'El QR venció. Genere uno nuevo.'; }
    } catch (e) { clearInterval(LF._poll); }
  }, 2500);
};
LF.acc.qrModo = el => { LF._qrTipo = el.dataset.tipo; LF.verQr(LF._pagoActual, LF._onPagadoActual); };
LF.acc.cerrar = () => LF.cerrar();
LF.acc.simularQr = async el => { await LF.post('/pagos/simulador/qr/' + el.dataset.ref + '/pagar'); };

LF.comprobante = async (ventaId) => {
  const d = await LF.get('/comprobantes?venta_id=' + ventaId);
  const v = d.venta;
  LF.modal(`<div class="ticket"><h2 style="text-align:center;margin-bottom:2px">${LF.esc(d.negocio)}</h2>
    <p style="text-align:center;margin:0 0 10px" class="sub">Comprobante ${LF.esc(d.comprobante.numero)} · ${LF.fecha(d.comprobante.emitido_en)}</p>
    ${d.items.map(i => `<div class="ln"><span>${i.cantidad} × ${LF.esc(i.nombre)}</span><span>${LF.bs(i.subtotal)}</span></div>`).join('')}
    ${v.descuento > 0 ? `<div class="ln"><span>Descuento</span><span>− ${LF.bs(v.descuento)}</span></div>` : ''}
    <div class="tot"><span>TOTAL</span><span>${LF.bs(v.total)}</span></div>
    <p class="sub">Venta #${v.id} · ${LF.esc(v.tipo_venta)} · Pago: ${d.pago ? LF.esc(d.pago.metodo) : '—'} (${d.pago ? LF.esc(d.pago.estado) : '—'})</p></div>
    <div class="row noprint"><button class="btn" onclick="window.print()">Imprimir</button><span class="sp"></span><button class="btn sec" data-act="cerrar">Cerrar</button></div>`);
};
LF.acc.comprobante = el => LF.comprobante(el.dataset.id);
