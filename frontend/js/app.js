// Enrutador, menú por rol y arranque de la aplicación.
window.LF = window.LF || {};

const MENUS = {
  publico: [['#/', 'Catálogo'], ['#/carrito', 'Carrito']],
  cliente: [['#/', 'Catálogo'], ['#/carrito', 'Carrito'], ['#/pedidos', 'Mis pedidos'], ['#/perfil', 'Perfil']],
  cajero: [['#/pos', 'Punto de venta'], ['#/caja', 'Caja'], ['#/ventas', 'Mis ventas'], ['#/whatsapp', 'Pedido WhatsApp'], ['#/perfil', 'Perfil']],
  empleado: [['#/stock', 'Inventario'], ['#/movimientos', 'Movimientos'], ['#/perfil', 'Perfil']],
  repartidor: [['#/entregas', 'Entregas'], ['#/historial', 'Historial'], ['#/perfil', 'Perfil']],
  administrador: [['#/panel', 'Panel'], ['#/pedidos-admin', 'Pedidos'], ['#/productos', 'Productos'], ['#/stock', 'Inventario'], ['#/promociones', 'Promociones'], ['#/usuarios', 'Usuarios'], ['#/cobranzas', 'Cobranzas'], ['#/auditoria', 'Auditoría'], ['#/respaldos', 'Respaldos'], ['#/', 'Ver tienda'], ['#/perfil', 'Perfil']],
};
const PERMITIDAS = {   // ruta → roles (el servidor valida de todos modos)
  '/pos': ['cajero', 'administrador'], '/caja': ['cajero'], '/ventas': ['cajero'], '/whatsapp': ['cajero'], '/stock': ['empleado', 'administrador'], '/movimientos': ['empleado', 'administrador'],
  '/entregas': ['repartidor', 'administrador'], '/historial': ['repartidor'], '/pedidos': ['cliente', 'administrador'], '/panel': ['administrador'], '/pedidos-admin': ['administrador'], '/productos': ['administrador'],
  '/promociones': ['administrador'], '/usuarios': ['administrador'], '/cobranzas': ['administrador'], '/auditoria': ['administrador'], '/respaldos': ['administrador'], '/perfil': ['cliente', 'cajero', 'empleado', 'repartidor', 'administrador'],
};
LF.inicio = () => ({ cajero: '#/pos', empleado: '#/stock', repartidor: '#/entregas', administrador: '#/panel' }[LF.user && LF.user.rol] || '#/');

LF.menu = () => {
  const rol = LF.user ? LF.user.rol : 'publico', n = LF.carrito.reduce((s, l) => s + l.cantidad, 0);
  LF.$('#menu').innerHTML = MENUS[rol].map(([h, t]) => `<a href="${h}" class="${location.hash === h || (h === '#/' && !location.hash) ? 'on' : ''}">${t}${h === '#/carrito' && n ? ` (${n})` : ''}</a>`).join('');
  LF.$('#sesion').innerHTML = LF.user ? `<span>${LF.esc(LF.user.nombre)} · <b>${LF.esc(LF.rolNombre(LF.user.rol))}</b></span><button class="btn sm sec" data-act="salir">Salir</button>` : `<a href="#/login" class="btn sm">Ingresar</a><a href="#/registro" style="color:#cbbfe0">Registrarse</a>`;
};
LF.acc.salir = async () => { try { await LF.post('/auth/logout'); } catch (e) {} LF.setToken(null); LF.user = null; LF.menu(); location.hash = '#/'; LF.render(); };
LF.sesionVencida = () => { LF.toast('Su sesión venció. Ingrese nuevamente.', 'bad'); LF.menu(); location.hash = '#/login'; };

LF.render = async (silencioso) => {
  const ruta = (location.hash.replace(/^#/, '') || '/').split('?')[0];
  LF.menu();
  const permitidos = PERMITIDAS[ruta];
  if (permitidos && (!LF.user || !permitidos.includes(LF.user.rol))) { location.hash = LF.user ? LF.inicio() : '#/login'; return; }
  const vista = LF.rutas[ruta] || LF.rutas['/'];
  const app = LF.$('#app'); const y = window.scrollY;
  if (!silencioso) app.innerHTML = '<p class="sub">Cargando…</p>';
  try { app.innerHTML = await vista(); if (silencioso) window.scrollTo(0, y); }
  catch (e) { app.innerHTML = `<div class="card note bad"><b>${LF.esc(e.mensaje || 'Error')}</b><br>${e.codigo === 'SIN_CONEXION' ? 'Inicie el backend con <code>python run.py</code> y recargue la página.' : ''}</div>`; }
};
window.addEventListener('hashchange', () => { LF.cerrar(); LF.render(); });
document.addEventListener('input', ev => { const el = ev.target.closest('[data-input]'); if (el && LF.inp[el.dataset.input]) LF.inp[el.dataset.input](el); });
document.addEventListener('change', ev => { const el = ev.target; if (el.matches && el.matches('select[data-act]') || el.matches('input[type=checkbox][data-act]')) { const fn = LF.acc[el.dataset.act]; fn && Promise.resolve(fn(el)).catch(LF.err); } });

(async () => {
  if (LF.token) { try { LF.user = await LF.get('/auth/me'); } catch (e) { LF.setToken(null); } }
  if (LF.user && !location.hash) location.hash = LF.inicio();
  LF.render();
})();
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !LF.$('#modal').hidden) LF.cerrar(); });
