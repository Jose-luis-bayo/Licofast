// Vistas del visitante y del cliente: catálogo, carrito, pedidos, perfil, login y registro.
window.LF = window.LF || {};
LF.rutas = LF.rutas || {}; LF.inp = LF.inp || {};
LF.carrito = JSON.parse(localStorage.getItem('lf_cart') || '[]');
LF.guardarCarrito = () => { localStorage.setItem('lf_cart', JSON.stringify(LF.carrito)); LF.menu && LF.menu(); };
LF.filtro = { q: '', cat: '' };

LF.rutas['/login'] = async () => `<div class="card auth"><h1>Iniciar sesión</h1><p class="sub">Ingrese con su usuario y contraseña.</p>
  <form id="fl">${LF.campo('usuario', 'Usuario', 'text', '', 'autocomplete="username" required')}${LF.campo('password', 'Contraseña', 'password', '', 'autocomplete="current-password" required')}
  <p><button class="btn lg" data-act="login">Ingresar</button></p></form>
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
  <p><button class="btn lg" data-act="registrar">Crear cuenta</button></p></form><p class="sub">¿Ya tiene cuenta? <a href="#/login">Inicie sesión</a></p></div>`;
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
  <div class="hero" style="padding:18px 24px">
    <h1>Su licorería, a un clic 🍾</h1>
    <p>Bebidas nacionales e importadas para mayores de 18 años. Pague por QR o en efectivo contra entrega.</p>
  </div>
  <div class="row" style="margin-bottom:12px">
    <input data-input="buscar" placeholder="Buscar por producto, marca o tipo…" value="${LF.esc(LF.filtro.q)}" style="max-width:380px">
  </div>
  <div class="chips">
    <span class="chip ${!LF.filtro.cat ? 'on' : ''}" data-act="cat" data-id="">Todos</span>
    ${cats.filter(c => c.activo).map(c => `<span class="chip ${String(LF.filtro.cat) === String(c.id) ? 'on' : ''}" data-act="cat" data-id="${c.id}">${LF.ico(c.nombre)} ${LF.esc(c.nombre)}</span>`).join('')}
  </div>
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
  const u = LF.user;
  return LF.pagina('Mi carrito', 'Revise su pedido y confirme la entrega.', `<div class="split"><div>${LF.tabla([
    { t: 'Producto', f: l => LF.esc(l.nombre) + (l.promocion ? ` <span class="badge b-ok">${LF.esc(l.promocion)}</span>` : '') + (l.stock_suficiente ? '' : ' <span class="badge b-bad">stock insuficiente</span>') },
    { t: 'Cantidad', f: l => `<span class="qty"><button data-act="menos" data-id="${l.producto_id}">−</button>${l.cantidad}<button data-act="mas" data-id="${l.producto_id}">+</button></span>` },
    { t: 'Subtotal', cls: 'num', f: l => LF.bs(l.subtotal) }, { t: '', f: l => `<button class="btn sm bad" data-act="quitar" data-id="${l.producto_id}">✕</button>` }], c.lineas)}</div>
    <div class="card"><h3>Resumen</h3>${c.descuento > 0 ? `<div class="row"><span>Descuento</span><span class="sp"></span><b>− ${LF.bs(c.descuento)}</b></div>` : ''}
    <div class="ticket"><div class="tot"><span>Total</span><span>${LF.bs(c.total)}</span></div></div>
    ${u && u.rol === 'cliente' ? `<form id="fc"><h3>Datos de entrega</h3>${LF.campo('direccion_entrega', 'Dirección', 'text', '', 'required')}${LF.campo('referencia_entrega', 'Referencia (opcional)')}${LF.campo('telefono_contacto', 'Teléfono de contacto', 'tel', u.telefono || '', 'required')}
      <label><input type="checkbox" id="mayor" style="width:auto"> Declaro ser mayor de 18 años</label>
      <p><button class="btn lg" data-act="confirmar">Confirmar pedido</button></p></form>`
    : `<div class="note">Para confirmar su pedido <a href="#/login">inicie sesión</a> o <a href="#/registro">cree una cuenta</a>.</div>`}</div></div>`);
};
LF.acc.mas = el => { const l = LF.carrito.find(x => x.id == el.dataset.id); l.cantidad++; LF.guardarCarrito(); return LF.render(); };
LF.acc.menos = el => { const l = LF.carrito.find(x => x.id == el.dataset.id); if (l.cantidad > 1) l.cantidad--; LF.guardarCarrito(); return LF.render(); };
LF.acc.quitar = el => { LF.carrito = LF.carrito.filter(x => x.id != el.dataset.id); LF.guardarCarrito(); return LF.render(); };
LF.acc.confirmar = async () => {
  if (!LF.$('#mayor').checked) return LF.toast('Debe declarar que es mayor de 18 años', 'bad');
  const f = LF.form('#fc'); if (!f.direccion_entrega || !f.telefono_contacto) return LF.toast('Complete dirección y teléfono', 'bad');
  LF._idem = LF._idem || LF.uuid();                                 // reintentos seguros (Idempotency-Key)
  const p = await LF.api('POST', '/pedidos', { ...f, items: LF.carrito.map(l => ({ producto_id: l.id, cantidad: l.cantidad })) }, { 'Idempotency-Key': LF._idem });
  LF._idem = null; LF.carrito = []; LF.guardarCarrito(); LF.toast('Pedido #' + p.id + ' registrado', 'ok'); location.hash = '#/pedidos'; LF.detallePedido(p.id);
};

// ---------------- Mis pedidos ----------------
LF.rutas['/pedidos'] = async () => {
  const d = await LF.get('/pedidos?size=50');
  return LF.pagina('Mis pedidos', 'Seguimiento de sus compras.', LF.tabla([
    { t: '#', f: p => p.id }, { t: 'Fecha', f: p => LF.fecha(p.created_at) }, { t: 'Total', cls: 'num', f: p => LF.bs(p.total) },
    { t: 'Estado', f: p => LF.badge(p.estado) }, { t: 'Pago', f: p => LF.badge(p.estado_pago) },
    { t: '', f: p => `<button class="btn sm sec" data-act="verPedido" data-id="${p.id}">Ver</button>` }], d.items, 'Aún no tiene pedidos.'));
};
LF.acc.verPedido = el => LF.detallePedido(el.dataset.id);
LF.detallePedido = async (id) => {
  const [p, seg] = await Promise.all([LF.get('/pedidos/' + id), LF.get('/pedidos/' + id + '/seguimiento').catch(() => null)]);
  const puedePagar = p.estado_pago === 'pendiente' && ['pendiente', 'en_camino'].includes(p.estado);
  LF.modal(`<h2>Pedido #${p.id} ${LF.badge(p.estado)} ${LF.badge(p.estado_pago)}</h2>
    <dl class="kv"><dt>Entrega</dt><dd>${LF.esc(p.direccion_entrega)} ${LF.esc(p.referencia_entrega || '')}</dd><dt>Contacto</dt><dd>${LF.esc(p.telefono_contacto)}</dd><dt>Repartidor</dt><dd>${LF.esc(p.repartidor || 'Sin asignar')}</dd></dl>
    ${LF.tabla([{ t: 'Producto', f: i => LF.esc(i.nombre) }, { t: 'Cant.', f: i => i.cantidad }, { t: 'Subtotal', cls: 'num', f: i => LF.bs(i.subtotal) }], p.items)}
    <p class="ticket"><span class="tot"><span>Total</span><span>${LF.bs(p.total)}</span></span></p>
    ${seg ? `<h3>Seguimiento</h3><ul class="tl">${seg.linea_tiempo.map(e => `<li><b>${LF.esc(e.evento)}</b> <span class="sub">${LF.fecha(e.fecha)} ${LF.esc(e.detalle || '')}</span></li>`).join('')}</ul>` : ''}
    <div class="row noprint">${puedePagar ? `<button class="btn ok" data-act="pagarQr" data-id="${p.id}">Pagar con QR</button><span class="sub" style="margin:0">o pague en efectivo al recibir</span>` : ''}
    ${p.estado_pago === 'pagado' ? `<button class="btn sec" data-act="comprobante" data-id="${p.id}">Ver comprobante</button>` : ''}<span class="sp"></span><button class="btn sec" data-act="cerrar">Cerrar</button></div>`, true);
};
LF.acc.pagarQr = async el => { const pago = await LF.post('/pagos', { venta_id: +el.dataset.id, metodo: 'qr' }, { 'Idempotency-Key': LF.uuid() }); LF.verQr(pago, () => { LF.render(); LF.detallePedido(el.dataset.id); }); };

// ---------------- Perfil ----------------
LF.rutas['/perfil'] = async () => {
  const u = await LF.get('/auth/me'); LF.user = { ...LF.user, ...u };
  return LF.pagina('Mi perfil', `${LF.esc(u.usuario)} · rol ${LF.esc(u.rol === 'empleado' ? 'bodega' : u.rol)}`, `<div class="card" style="max-width:520px"><form id="fp">
    <div class="f2"><div>${LF.campo('nombre', 'Nombre', 'text', u.nombre)}</div><div>${LF.campo('apellido', 'Apellido', 'text', u.apellido)}</div></div>${LF.campo('telefono', 'Teléfono', 'tel', u.telefono || '')}
    <h3 style="margin-top:18px">Cambiar contraseña</h3>${LF.campo('password_actual', 'Contraseña actual', 'password')}${LF.campo('password_nueva', 'Nueva contraseña (mín. 8)', 'password')}
    <p><button class="btn" data-act="guardarPerfil">Guardar cambios</button></p></form></div>`);
};
LF.acc.guardarPerfil = async () => { const u = await LF.put('/auth/me', LF.form('#fp')); LF.user = { ...LF.user, ...u }; LF.toast('Perfil actualizado', 'ok'); LF.menu(); };
