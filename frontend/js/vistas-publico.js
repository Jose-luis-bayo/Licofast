// Vistas del visitante y del cliente: catálogo, carrito, pedidos, perfil, login y registro.
window.LF = window.LF || {};
LF.rutas = LF.rutas || {}; LF.inp = LF.inp || {};
LF.carrito = JSON.parse(localStorage.getItem('lf_cart') || '[]');
LF.guardarCarrito = () => { localStorage.setItem('lf_cart', JSON.stringify(LF.carrito)); LF.menu && LF.menu(); };
LF.filtro = { q: '', cat: '' };

LF.rutas['/login'] = async () => `<div class="card auth"><h1>Iniciar sesión</h1><p class="sub">Ingrese con su usuario y contraseña.</p>
  <form id="fl">${LF.campo('usuario', 'Usuario', 'text', '', 'autocomplete="username" required')}${LF.campo('password', 'Contraseña', 'password', '', 'autocomplete="current-password" required')}
  <p><button class="btn lg" data-act="login">Ingresar</button></p></form>
  <div class="o-sep"><span>o</span></div><div id="gbtn" class="gbtn"></div>
  <p class="sub">¿No tiene cuenta? <a href="#/registro">Regístrese</a></p>
  <div class="demo"><b>Usuarios de demostración</b> (haga clic para autocompletar, clave: <code>Admin1234</code>):<br>
    <div class="chips" style="margin-top:8px">
      <span class="chip" data-act="autoLogin" data-u="admin_api" title="Administrador general">👑 admin_api (Admin)</span>
      <span class="chip" data-act="autoLogin" data-u="cajero1" title="Cajero">💵 cajero1 (Cajero)</span>
      <span class="chip" data-act="autoLogin" data-u="bodega1" title="Encargado de bodega">📦 bodega1 (Bodega)</span>
      <span class="chip" data-act="autoLogin" data-u="repartidor1" title="Repartidor delivery">🛵 repartidor1 (Repartidor)</span>
      <span class="chip" data-act="autoLogin" data-u="cliente1" title="Cliente">🛒 cliente1 (Cliente)</span>
    </div>
  </div></div>`;
// ---------------- Inicio de sesión con Google ----------------
LF.montarGoogle = async () => {
  const caja = LF.$('#gbtn'); if (!caja) return;
  const ocultar = () => { caja.parentElement.querySelectorAll('.o-sep,#gbtn').forEach(e => e.remove()); };
  try {
    const cfg = await LF.get('/config/publica');
    if (!cfg.google_client_id) return ocultar();
    if (!window.google) await new Promise((ok, err) => { const s = document.createElement('script'); s.src = 'https://accounts.google.com/gsi/client'; s.async = true; s.onload = ok; s.onerror = err; document.head.appendChild(s); });
    google.accounts.id.initialize({ client_id: cfg.google_client_id, callback: r => LF.acc.googleCred(r.credential).catch(LF.err) });
    google.accounts.id.renderButton(caja, { theme: 'outline', size: 'large', shape: 'pill', text: 'continue_with', locale: 'es', width: Math.min(340, caja.clientWidth || 340) });
  } catch (e) { ocultar(); }
};
LF.acc.googleCred = async credential => {
  const d = await LF.post('/auth/google', { credential }); LF.setToken(d.token); LF.user = d.usuario;
  LF.toast('Bienvenido, ' + d.usuario.nombre, 'ok');
  if (d.usuario.perfil_incompleto) { LF.toast('Complete su fecha de nacimiento y CI para poder comprar', 'ok'); location.hash = '#/perfil'; } else location.hash = LF.inicio();
  LF.menu(); LF.render();
};
LF.acc.autoLogin = el => {
  const u = LF.$('#fl input[name=usuario]');
  const p = LF.$('#fl input[name=password]');
  if (u && p) {
    u.value = el.dataset.u;
    p.value = 'Admin1234';
    LF.toast('Credenciales de ' + el.dataset.u + ' listas. Presione Ingresar.', 'ok');
  }
};
LF.acc.login = async () => {
  const f = LF.form('#fl'); if (!f.usuario || !f.password) return LF.toast('Complete usuario y contraseña', 'bad');
  const d = await LF.post('/auth/login', f); LF.setToken(d.token); LF.user = d.usuario;
  LF.toast('Bienvenido, ' + d.usuario.nombre, 'ok'); location.hash = LF.inicio(); LF.menu(); LF.render();
};
document.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.closest('#fl')) { e.preventDefault(); LF.acc.login().catch(LF.err); } });

LF.rutas['/registro'] = async () => `<div class="card auth"><h1>Crear cuenta</h1><p class="sub">Solo para mayores de 18 años.</p><form id="fr">
  <div class="f2"><div>${LF.campo('nombre', 'Nombre', 'text', '', 'required')}</div><div>${LF.campo('apellido', 'Apellido', 'text', '', 'required')}</div>
  <div>${LF.campo('ci', 'CI', 'text', '', 'required')}</div><div>${LF.campo('fecha_nacimiento', 'Fecha de nacimiento', 'date', '', 'required')}</div>
  <div>${LF.campo('telefono', 'Teléfono')}</div><div>${LF.campo('usuario', 'Usuario', 'text', '', 'required')}</div></div>
  ${LF.campo('password', 'Contraseña (mínimo 8 caracteres)', 'password', '', 'required minlength="8"')}
  <label><input type="checkbox" name="terminos" style="width:auto"> Acepto los términos y declaro ser mayor de 18 años</label>
  <p><button class="btn lg" data-act="registrar">Crear cuenta</button></p></form><div class="o-sep"><span>o</span></div><div id="gbtn" class="gbtn"></div><p class="sub">¿Ya tiene cuenta? <a href="#/login">Inicie sesión</a></p></div>`;
LF.acc.registrar = async () => { await LF.post('/auth/register', LF.form('#fr')); LF.toast('Cuenta creada. Ya puede iniciar sesión.', 'ok'); location.hash = '#/login'; };

// ---------------- Catálogo ----------------
LF.rutas['/'] = async () => {
  const [cats, prods] = await Promise.all([
    LF.get('/categorias'),
    LF.get('/productos?' + new URLSearchParams({ q: LF.filtro.q, ...(LF.filtro.cat ? { categoria_id: LF.filtro.cat } : {}) }))
  ]);
  LF._catalogoProds = prods;

  const banners = [
    { img: 'img/inicio.jpeg', alt: 'Granier Ortiz Principia' },
    { img: 'img/carrusel1.webp', alt: 'Disfruta junto a tus favoritos' },
    { img: 'img/2.jpeg', alt: 'Campos de Solana - Esther Ortiz' },
    { img: 'img/Licor_House_Banner_1800x1100_b8621e94-2a9c-40ac-b2bc-b7b504186680_580x.webp', alt: 'Promoción 2x1' }
  ];
  const slideActivo = LF._slide || 0;

  clearInterval(LF._bTimer);
  LF._bTimer = setInterval(() => {
    const slides = LF.$$('.banner-slide');
    if (!slides.length) return clearInterval(LF._bTimer);
    LF._slide = ((LF._slide || 0) + 1) % slides.length;
    slides.forEach((s, i) => s.classList.toggle('active', i === LF._slide));
    LF.$$('.banner-dot').forEach((d, i) => d.classList.toggle('active', i === LF._slide));
  }, 4500);

  return `<div class="banner-box">
    ${banners.map((b, i) => `<img src="${b.img}" alt="${b.alt}" class="banner-slide ${i === slideActivo ? 'active' : ''}">`).join('')}
    <div class="banner-controls">
      ${banners.map((_, i) => `<button class="banner-dot ${i === slideActivo ? 'active' : ''}" data-act="bannerIr" data-idx="${i}"></button>`).join('')}
    </div>
  </div>
  ${LF.user && LF.user.perfil_incompleto ? '<div class="note"><b>Falta un paso:</b> complete su CI y fecha de nacimiento en <a href="#/perfil">Mi perfil</a> para poder comprar.</div>' : ''}
  <section class="sec"><div class="sec-t"><h2>Nuestras categorías</h2></div>
    <div class="cats">
      <div class="cat-tile ${!LF.filtro.cat ? 'on' : ''}" data-act="cat" data-id=""><span class="ci">🛍️</span><span>Todos</span></div>
      ${cats.filter(c => c.activo).map(c => `<div class="cat-tile ${String(LF.filtro.cat) === String(c.id) ? 'on' : ''}" data-act="cat" data-id="${c.id}"><span class="ci">${LF.ico(c.nombre)}</span><span>${LF.esc(c.nombre)}</span></div>`).join('')}
    </div></section>
  <section class="sec servicios">
    <div class="srv"><span class="si">🛵</span><div><b>Delivery a domicilio</b><p>Pedidos en línea con seguimiento de tu entrega.</p></div></div>
    <div class="srv"><span class="si">📲</span><div><b>Paga con QR o efectivo</b><p>QR bancario o contra entrega, tú eliges.</p></div></div>
    <div class="srv"><span class="si">🔞</span><div><b>Compra responsable</b><p>Venta solo a mayores de 18 años. Beber con moderación.</p></div></div>
  </section>
  ${prods.some(p => p.promocion) ? `<section class="sec ofertas"><div class="of-txt"><h2>¿Buscas precios realmente especiales?</h2><p>Aprovecha nuestras promociones vigentes.</p></div>
    <div class="of-list">${prods.filter(p => p.promocion).slice(0, 4).map(p => `<div class="of-item" data-act="verProd" data-id="${p.id}"><span class="ribbon">${LF.esc(p.promocion)}</span><b>${LF.esc(p.nombre)}</b><span>${LF.bs(p.precio_final)} <s>${LF.bs(p.precio)}</s></span></div>`).join('')}</div></section>` : ''}
  <section class="sec"><div class="sec-t"><h2>${LF.filtro.q || LF.filtro.cat ? 'Resultados' : 'Recomendados del mes'}</h2>
    <input data-input="buscar" placeholder="🔎 ¿Qué estás buscando?" value="${LF.esc(LF.filtro.q)}" class="buscar"></div></section>
  <div class="grid g2">${prods.map(p => `
    <div class="card prod">
      ${p.promocion ? `<span class="ribbon">${LF.esc(p.promocion)}</span>` : ''}
      ${p.imagen_url ? `
        <div class="prod-img-wrap" data-act="verProd" data-id="${p.id}" style="cursor:pointer">
          <img src="${LF.esc(p.imagen_url)}" alt="${LF.esc(p.nombre)}" class="prod-img" loading="lazy" onerror="this.onerror=null;this.parentElement.innerHTML='<div class=\\'ico\\'>${LF.ico(p.categoria)}</div>'">
        </div>` : `
        <div class="ico" data-act="verProd" data-id="${p.id}" style="cursor:pointer">${LF.ico(p.categoria)}</div>`}
      <div class="nm" data-act="verProd" data-id="${p.id}" style="cursor:pointer">${LF.esc(p.nombre)}</div>
      <div class="sub" style="margin:0;font-size:13px">${LF.esc(p.descripcion || '')}</div>
      <div>
        <span class="pr">${LF.bs(p.precio_final)}</span>
        ${p.precio_final < p.precio ? `<span class="old">${LF.bs(p.precio)}</span>` : ''}
      </div>
      <div class="row">
        <span class="badge ${p.stock > 0 ? 'b-ok' : 'b-bad'}">${p.stock > 0 ? 'Disponible (' + p.stock + ')' : 'Agotado'}</span>
        <span class="sp"></span>
        <button class="btn sm" data-act="agregar" data-id="${p.id}" data-nombre="${LF.esc(p.nombre)}" data-precio="${p.precio_final}" data-stock="${p.stock}" ${p.stock > 0 ? '' : 'disabled'}>Agregar</button>
      </div>
    </div>`).join('') || '<div class="card empty">No se encontraron productos en esta categoría</div>'}
  </div>`;
};
LF.acc.bannerIr = el => {
  LF._slide = +el.dataset.idx;
  LF.$$('.banner-slide').forEach((s, i) => s.classList.toggle('active', i === LF._slide));
  LF.$$('.banner-dot').forEach((d, i) => d.classList.toggle('active', i === LF._slide));
};
LF.acc.verProd = el => {
  const p = (LF._catalogoProds || []).find(x => x.id === +el.dataset.id);
  if (!p) return;
  LF.modal(`
    <div style="text-align:center;margin-bottom:12px">
      ${p.imagen_url ? `<img src="${LF.esc(p.imagen_url)}" alt="${LF.esc(p.nombre)}" style="max-height:240px;max-width:100%;object-fit:contain;border-radius:10px">` : `<div style="font-size:64px">${LF.ico(p.categoria)}</div>`}
    </div>
    <h2>${LF.esc(p.nombre)} ${p.promocion ? `<span class="badge b-ok">${LF.esc(p.promocion)}</span>` : ''}</h2>
    <p class="sub">${LF.esc(p.descripcion || 'Sin descripción detallada.')}</p>
    <dl class="kv">
      <dt>Categoría</dt><dd>${LF.esc(p.categoria || 'Sin categoría')}</dd>
      <dt>Precio</dt><dd><span style="font-size:20px;font-weight:800;color:var(--brand)">${LF.bs(p.precio_final)}</span> ${p.precio_final < p.precio ? `<span class="old">${LF.bs(p.precio)}</span>` : ''}</dd>
      <dt>Stock</dt><dd><span class="badge ${p.stock > 0 ? 'b-ok' : 'b-bad'}">${p.stock > 0 ? p.stock + ' unidades disponibles' : 'Agotado'}</span></dd>
    </dl>
    <p class="row" style="margin-top:16px">
      <span class="sp"></span>
      <button class="btn sec" data-act="cerrar">Cerrar</button>
      <button class="btn" data-act="agregar" data-id="${p.id}" data-nombre="${LF.esc(p.nombre)}" data-precio="${p.precio_final}" data-stock="${p.stock}" ${p.stock > 0 ? '' : 'disabled'}>Agregar al carrito</button>
    </p>
  `);
};
LF.inp.buscar = el => { clearTimeout(LF._t); LF._t = setTimeout(() => { LF.filtro.q = el.value; LF.render(true).then(() => { const i = LF.$('[data-input=buscar]'); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }); }, 300); };
LF.acc.cat = el => { LF.filtro.cat = el.dataset.id; return LF.render(); };
LF.acc.agregar = el => {
  const id = +el.dataset.id, stock = +el.dataset.stock; let l = LF.carrito.find(x => x.id === id);
  if (l) { if (l.cantidad >= stock) return LF.toast('No hay más stock disponible', 'bad'); l.cantidad++; } else LF.carrito.push({ id, nombre: el.dataset.nombre, precio: +el.dataset.precio, cantidad: 1 });
  LF.guardarCarrito(); LF.toast('Agregado al carrito', 'ok');
  LF.cerrar();
};

// ---------------- Carrito y checkout ----------------
LF.rutas['/carrito'] = async () => {
  if (!LF.carrito.length) return LF.pagina('Mi carrito', '', '<div class="card empty">Su carrito está vacío. <a href="#/">Ver catálogo</a></div>');
  const c = await LF.post('/carrito/cotizar', { items: LF.carrito.map(l => ({ producto_id: l.id, cantidad: l.cantidad })) });
  const u = LF.user, ed = LF.editando || {};
  const mis = u && u.rol === 'cliente' ? await LF.get('/mis-cupones').catch(() => []) : [];
  LF.cupon = null; LF._totalBase = c.total;
  return LF.pagina('Mi carrito', 'Revise su pedido y confirme la entrega.', `<div class="split"><div>${LF.tabla([
    { t: 'Producto', f: l => LF.esc(l.nombre) + (l.promocion ? ` <span class="badge b-ok">${LF.esc(l.promocion)}</span>` : '') + (l.stock_suficiente ? '' : ' <span class="badge b-bad">stock insuficiente</span>') },
    { t: 'Cantidad', f: l => `<span class="qty"><button data-act="menos" data-id="${l.producto_id}">−</button>${l.cantidad}<button data-act="mas" data-id="${l.producto_id}">+</button></span>` },
    { t: 'Subtotal', cls: 'num', f: l => LF.bs(l.subtotal) }, { t: '', f: l => `<button class="btn sm bad" data-act="quitar" data-id="${l.producto_id}">✕</button>` }], c.lineas)}</div>
    <div class="card"><h3>Resumen</h3>${c.descuento > 0 ? `<div class="row"><span>Descuento${c.promocion_pedido ? ' (' + LF.esc(c.promocion_pedido) + ')' : ''}</span><span class="sp"></span><b>− ${LF.bs(c.descuento)}</b></div>` : ''}
    <div id="cuponLinea"></div>
    <div class="ticket"><div class="tot"><span>Total</span><span id="totalFinal">${LF.bs(c.total)}</span></div></div>
    ${u && u.rol === 'cliente' ? `<form id="fc"><h3>Datos de entrega</h3>${LF.editando ? `<div class="note">✏️ Editando el pedido #${ed.id}: al confirmar reemplaza al anterior. <button type="button" class="btn sm sec" data-act="descartarEdicion">Descartar cambios</button></div>` : ''}${LF.campo('direccion_entrega', 'Dirección', 'text', ed.direccion_entrega || '', 'required')}
      <div class="row" style="margin:8px 0 2px"><button type="button" class="btn sm sec" data-act="usarUbicacion">📍 Usar mi ubicación actual</button><span id="ubicEstado" class="sub" style="margin:0">${LF.ubic ? '✅ Ubicación guardada' : ''}</span></div>
      ${LF.campo('referencia_entrega', 'Referencia (opcional)', 'text', ed.referencia_entrega || '')}${LF.campo('telefono_contacto', 'Teléfono de contacto', 'tel', ed.telefono_contacto || u.telefono || '', 'required')}
      <h3 style="margin-top:14px">Cupón de descuento</h3>
      <div class="row"><input id="cuponCodigo" value="${LF.esc(ed.cupon || '')}" placeholder="Código (ej. VALE-1A2B3C)" style="max-width:220px;text-transform:uppercase"><button type="button" class="btn sm sec" data-act="aplicarCupon">Aplicar</button><button type="button" class="btn sm sec" data-act="quitarCupon" id="btnQuitarCupon" hidden>Quitar</button></div>
      ${mis.filter(m => m.usable).length ? `<p class="sub" style="margin:6px 0 0">Sus cupones: ${mis.filter(m => m.usable).map(m => `<button type="button" class="badge b-ok" style="cursor:pointer;border:0" data-act="usarCupon" data-codigo="${LF.esc(m.codigo)}">${LF.esc(m.codigo)} · ${m.tipo === 'porcentaje' ? m.valor + ' %' : LF.bs(m.valor)}</button>`).join(' ')}</p>` : ''}
      <h3 style="margin-top:14px">Forma de pago</h3>
      <div class="pagos">${Object.entries(LF.METODOS).map(([k, t], i) => `<label class="opt"><input type="radio" name="metodo_pago" value="${k}" ${(ed.metodo_pago ? k === ed.metodo_pago : i === 0) ? 'checked' : ''}><span>${t}</span></label>`).join('')}</div>
      <p class="sub" style="margin:6px 0 0">Efectivo: paga al repartidor al recibir. QR y PayPal: paga en línea y su pedido pasa a caja ya pagado.</p>
      <label style="margin-top:12px"><input type="checkbox" id="mayor" style="width:auto"> Declaro ser mayor de 18 años</label>
      <p><button class="btn lg" data-act="confirmar">Confirmar pedido</button></p></form>`
    : `<div class="note">Para confirmar su pedido <a href="#/login">inicie sesión</a> o <a href="#/registro">cree una cuenta</a>.</div>`}</div></div>`);
};
LF.pintarCupon = () => {
  const c = LF.cupon;
  LF.$('#cuponLinea').innerHTML = c ? `<div class="row"><span>Cupón ${LF.esc(c.codigo)}</span><span class="sp"></span><b>− ${LF.bs(c.descuento_cupon)}</b></div>` : '';
  LF.$('#totalFinal').textContent = LF.bs(c ? c.total : LF._totalBase);
  const q = LF.$('#btnQuitarCupon'); if (q) q.hidden = !c;
};
LF.acc.aplicarCupon = async () => {
  const codigo = LF.$('#cuponCodigo').value.trim(); if (!codigo) return LF.toast('Escriba el código del cupón', 'bad');
  LF.cupon = await LF.post('/cupones/validar', { codigo, items: LF.carrito.map(l => ({ producto_id: l.id, cantidad: l.cantidad })) });
  LF.pintarCupon(); LF.toast('Cupón aplicado: − ' + LF.bs(LF.cupon.descuento_cupon), 'ok');
};
LF.acc.usarCupon = el => { LF.$('#cuponCodigo').value = el.dataset.codigo; return LF.acc.aplicarCupon(); };
LF.acc.quitarCupon = () => { LF.cupon = null; LF.$('#cuponCodigo').value = ''; LF.pintarCupon(); };
LF.acc.mas = el => { const l = LF.carrito.find(x => x.id == el.dataset.id); l.cantidad++; LF.guardarCarrito(); return LF.render(); };
LF.acc.menos = el => { const l = LF.carrito.find(x => x.id == el.dataset.id); if (l.cantidad > 1) l.cantidad--; LF.guardarCarrito(); return LF.render(); };
LF.acc.quitar = el => { LF.carrito = LF.carrito.filter(x => x.id != el.dataset.id); LF.guardarCarrito(); return LF.render(); };
LF.acc.confirmar = async () => {
  if (!LF.$('#mayor').checked) return LF.toast('Debe declarar que es mayor de 18 años', 'bad');
  const f = LF.form('#fc'); if (!f.direccion_entrega || !f.telefono_contacto) return LF.toast('Complete dirección y teléfono', 'bad');
  LF._idem = LF._idem || LF.uuid();                                 // reintentos seguros (Idempotency-Key)
  const cuerpo = { ...f, items: LF.carrito.map(l => ({ producto_id: l.id, cantidad: l.cantidad })) };
  if (LF.cupon) cuerpo.cupon = LF.cupon.codigo;
  if (LF.ubic) { cuerpo.lat = LF.ubic.lat; cuerpo.lng = LF.ubic.lng; }
  const ed = LF.editando;
  if (ed) { cuerpo.cupon = LF.cupon ? LF.cupon.codigo : (LF.$('#cuponCodigo').value.trim() || ''); if (!LF.ubic) { cuerpo.lat = ed.lat; cuerpo.lng = ed.lng; } }
  const p = ed ? await LF.api('PUT', '/pedidos/' + ed.id, cuerpo) : await LF.api('POST', '/pedidos', cuerpo, { 'Idempotency-Key': LF._idem });
  LF._idem = null; LF.editando = null; LF.carrito = []; LF.ubic = null; LF.cupon = null; LF.guardarCarrito();
  LF.toast((ed ? 'Pedido corregido: nuevo #' : 'Pedido #') + p.id + ' registrado', 'ok'); location.hash = '#/pedidos';
  if (p.metodo_pago !== 'efectivo') LF.iniciarPago(p.id, p.metodo_pago, () => { LF.render(); LF.detallePedido(p.id); }).catch(LF.err);   // QR / PayPal: paga ahora, sin pasos intermedios
  else await LF.detallePedido(p.id);
};

// ---------------- Mis pedidos ----------------
LF.rutas['/pedidos'] = async () => {
  const d = await LF.get('/pedidos?size=50');
  return LF.pagina('Mis pedidos', 'Seguimiento de sus compras.', LF.tabla([
    { t: '#', f: p => p.id }, { t: 'Fecha', f: p => LF.fecha(p.created_at) }, { t: 'Total', cls: 'num', f: p => LF.bs(p.total) },
    { t: 'Estado', f: p => LF.badgeEstado(p.estado) }, { t: 'Pago', f: p => LF.badge(p.estado_pago) },
    { t: '', f: p => `<button class="btn sm sec" data-act="verPedido" data-id="${p.id}">Ver</button>` }], d.items, 'Aún no tiene pedidos.'));
};
LF.acc.verPedido = el => LF.detallePedido(el.dataset.id);
LF.detallePedido = async (id) => {
  const [p, seg] = await Promise.all([LF.get('/pedidos/' + id), LF.get('/pedidos/' + id + '/seguimiento').catch(() => null)]);
  const puedePagar = p.estado_pago === 'pendiente' && ['pendiente', 'confirmado', 'preparado', 'en_camino'].includes(p.estado);
  const mapa = p.estado === 'en_camino';
  LF.modal(`<h2>Pedido #${p.id} ${LF.badgeEstado(p.estado)} ${LF.badge(p.estado_pago)}</h2>
    ${mapa ? `<p><button class="btn lg" data-act="verMapa" data-id="${p.id}" data-dir="${LF.esc(p.direccion_entrega)}">🛵 Seguir mi pedido en vivo</button></p>` : ''}
    <dl class="kv"><dt>Entrega</dt><dd>${LF.esc(p.direccion_entrega)} ${LF.esc(p.referencia_entrega || '')} ${p.lat_entrega != null ? `<a target="_blank" rel="noopener" href="https://www.google.com/maps?q=${p.lat_entrega},${p.lng_entrega}">📍 ubicación</a>` : ''}</dd><dt>Contacto</dt><dd>${LF.esc(p.telefono_contacto)}</dd><dt>Pago</dt><dd>${LF.METODOS[p.metodo_pago] || ''}</dd><dt>Repartidor</dt><dd>${LF.esc(p.repartidor || 'Se asignará al preparar el pedido')}</dd></dl>
    ${LF.tabla([{ t: 'Producto', f: i => LF.esc(i.nombre) }, { t: 'Cant.', f: i => i.cantidad }, { t: 'Subtotal', cls: 'num', f: i => LF.bs(i.subtotal) }], p.items)}
    <p class="ticket"><span class="tot"><span>Total</span><span>${LF.bs(p.total)}</span></span></p>
    ${seg ? `<h3>Seguimiento</h3><ul class="tl">${seg.linea_tiempo.map(e => `<li><b>${LF.esc(e.evento)}</b> <span class="sub">${LF.fecha(e.fecha)} ${LF.esc(e.detalle || '')}</span></li>`).join('')}</ul>` : ''}
    ${p.devolucion_pendiente ? `<div class="note bad">Su pedido fue cancelado y usted ya había pagado. Para la <b>devolución del dinero</b> escriba al cajero por WhatsApp y envíele su QR.<br><a class="btn sm" style="margin-top:8px;background:#25d366" target="_blank" rel="noopener" href="${LF.esc(p.whatsapp_url)}">💬 Escribir al cajero</a></div>` : ''}
    ${p.puede_cancelar ? '<p class="sub">Aún no pagó: puede corregir su pedido o cancelarlo.</p>' : (p.puede_editar ? '<p class="sub">Puede corregir su pedido mientras caja no lo confirme.</p>' : '')}
    <div class="row noprint">${puedePagar && p.metodo_pago === 'qr' ? `<button class="btn ok" data-act="pagarQr" data-id="${p.id}">Pagar con QR</button>` : ''}${puedePagar && p.metodo_pago === 'paypal' ? `<button class="btn" style="background:#0070ba" data-act="pagarPaypal" data-id="${p.id}">Pagar con PayPal</button>` : ''}${p.metodo_pago === 'efectivo' && ['pendiente', 'confirmado', 'preparado', 'en_camino'].includes(p.estado) ? '<span class="sub" style="margin:0">💵 Pagará en efectivo al recibir</span>' : ''}
    ${p.puede_editar ? `<button class="btn sec" data-act="editarPedido" data-id="${p.id}">✏️ Editar pedido</button>` : ''}${p.puede_cancelar ? `<button class="btn bad" data-act="cancelarPedido" data-id="${p.id}">🚫 Cancelar pedido</button>` : ''}
    ${!p.puede_cancelar && ['pendiente', 'confirmado', 'preparado'].includes(p.estado) && p.whatsapp_url ? `<a class="btn sec sm" target="_blank" rel="noopener" href="${LF.esc(p.whatsapp_url)}">💬 Cancelar / devolución por WhatsApp</a>` : ''}
    ${p.estado_pago === 'pagado' ? `<button class="btn sec" data-act="comprobante" data-id="${p.id}">Ver comprobante</button>` : ''}<span class="sp"></span><button class="btn sec" data-act="cerrar">Cerrar</button></div>`, true);
};
LF.acc.cancelarPedido = async el => {
  if (!confirm('¿Cancelar el pedido #' + el.dataset.id + '? Los productos volverán al inventario.')) return;
  await LF.put('/pedidos/' + el.dataset.id + '/cancelar'); LF.toast('Pedido cancelado', 'ok'); LF.cerrar(); LF.render(true);
};
// Editar: el pedido se carga de nuevo en el carrito; al confirmar reemplaza al anterior (conserva dirección, ubicación y forma de pago)
LF.acc.editarPedido = async el => {
  const p = await LF.get('/pedidos/' + el.dataset.id);
  LF.carrito = p.items.map(i => ({ id: i.producto_id, nombre: i.nombre, precio: +i.precio_unitario || 0, cantidad: i.cantidad }));
  LF.editando = { id: p.id, direccion_entrega: p.direccion_entrega, telefono_contacto: p.telefono_contacto, referencia_entrega: p.referencia_entrega || '', metodo_pago: p.metodo_pago, lat: p.lat_entrega, lng: p.lng_entrega, cupon: p.cupon_codigo || '' };
  if (p.lat_entrega != null) LF.ubic = { lat: p.lat_entrega, lng: p.lng_entrega };
  LF.guardarCarrito(); LF.cerrar(); LF.toast('Modifique su carrito y confirme: reemplazará al pedido #' + p.id, 'ok'); location.hash = '#/carrito'; LF.render(true);
};
LF.acc.descartarEdicion = () => { LF.editando = null; LF.ubic = null; LF.carrito = []; LF.guardarCarrito(); location.hash = '#/pedidos'; LF.render(true); };
LF.acc.pagarQr = el => LF.iniciarPago(el.dataset.id, 'qr', () => { LF.render(); LF.detallePedido(el.dataset.id); });
LF.acc.pagarPaypal = el => LF.iniciarPago(el.dataset.id, 'paypal', () => { LF.render(); LF.detallePedido(el.dataset.id); });

// ---------------- Perfil ----------------
LF.rutas['/perfil'] = async () => {
  const u = await LF.get('/auth/me'); LF.user = { ...LF.user, ...u };
  const falta = u.perfil_incompleto ? `<div class="note"><b>Complete sus datos para poder comprar.</b> Por ley solo vendemos alcohol a mayores de 18 años: ingrese su CI y su fecha de nacimiento (no podrá cambiarlos después).</div>
    <div class="f2"><div>${LF.campo('ci', 'CI', 'text', '', 'required')}</div><div>${LF.campo('fecha_nacimiento', 'Fecha de nacimiento', 'date', '', 'required')}</div></div>
    <label><input type="checkbox" name="terminos" style="width:auto"> Acepto los términos y declaro ser mayor de 18 años</label><hr style="border:0;border-top:1px solid var(--line);margin:14px 0">` : '';
  const nombreUsuario = u.usuario.startsWith('g_') ? 'Cuenta de Google' : u.usuario;
  return LF.pagina('Mi perfil', `${LF.esc(nombreUsuario)} · rol ${LF.esc(u.rol === 'empleado' ? 'bodega' : u.rol)}`, `<div class="card" style="max-width:520px"><form id="fp">${falta}
    <div class="f2"><div>${LF.campo('nombre', 'Nombre', 'text', u.nombre)}</div><div>${LF.campo('apellido', 'Apellido', 'text', u.apellido)}</div></div>${LF.campo('telefono', 'Teléfono', 'tel', u.telefono || '')}
    ${u.usuario.startsWith('g_') ? '' : `<h3 style="margin-top:18px">Cambiar contraseña</h3>${LF.campo('password_actual', 'Contraseña actual', 'password')}${LF.campo('password_nueva', 'Nueva contraseña (mín. 8)', 'password')}`}
    <p><button class="btn" data-act="guardarPerfil">Guardar cambios</button></p></form></div>`);
};
LF.acc.guardarPerfil = async () => { const u = await LF.put('/auth/me', LF.form('#fp')); LF.user = { ...LF.user, ...u }; LF.toast('Perfil actualizado', 'ok'); LF.menu(); if (!u.perfil_incompleto) LF.render(); };
