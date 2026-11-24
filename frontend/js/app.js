// Enrutador, menú por rol y arranque de la aplicación.
window.LF = window.LF || {};

const MENUS = {
  publico: [['#/', 'Catálogo'], ['#/carrito', 'Carrito']],
  cliente: [['#/', 'Catálogo'], ['#/carrito', 'Carrito'], ['#/pedidos', 'Mis pedidos'], ['#/mis-cupones', 'Mis cupones'], ['#/perfil', 'Perfil']],
  cajero: [['#/pedidos-online', 'Pedidos online'], ['#/pos', 'Punto de venta'], ['#/caja', 'Caja'], ['#/ventas', 'Mis ventas'], ['#/whatsapp', 'Pedido WhatsApp'], ['#/perfil', 'Perfil']],
  empleado: [['#/preparar', 'Pedidos a preparar'], ['#/stock', 'Inventario'], ['#/movimientos', 'Movimientos'], ['#/perfil', 'Perfil']],
  repartidor: [['#/entregas', 'Entregas'], ['#/historial', 'Historial'], ['#/perfil', 'Perfil']],
  administrador: [['#/panel', 'Panel'], ['#/pedidos-admin', 'Pedidos'], ['#/productos', 'Productos'], ['#/stock', 'Inventario'], ['#/promociones', 'Promociones'], ['#/cupones', 'Cupones'], ['#/usuarios', 'Usuarios'], ['#/cobranzas', 'Cobranzas'], ['#/auditoria', 'Auditoría'], ['#/respaldos', 'Respaldos'], ['#/', 'Ver tienda'], ['#/perfil', 'Perfil']],
};
const PERMITIDAS = {   // ruta → roles (el servidor valida de todos modos)
  '/pedidos-online': ['cajero'], '/preparar': ['empleado'], '/pos': ['cajero', 'administrador'], '/caja': ['cajero'], '/ventas': ['cajero'], '/whatsapp': ['cajero'], '/stock': ['empleado', 'administrador'], '/movimientos': ['empleado', 'administrador'],
  '/entregas': ['repartidor', 'administrador'], '/historial': ['repartidor'], '/pedidos': ['cliente', 'administrador'], '/panel': ['administrador'], '/pedidos-admin': ['administrador'], '/productos': ['administrador'],
  '/promociones': ['administrador'], '/cupones': ['administrador'], '/mis-cupones': ['cliente'], '/usuarios': ['administrador'], '/cobranzas': ['administrador'], '/auditoria': ['administrador'], '/respaldos': ['administrador'], '/perfil': ['cliente', 'cajero', 'empleado', 'repartidor', 'administrador'],
};
LF.inicio = () => ({ cajero: '#/pedidos-online', empleado: '#/preparar', repartidor: '#/entregas', administrador: '#/panel' }[LF.user && LF.user.rol] || '#/');

const ICONOS = { '#/': '🏪', '#/carrito': '🛒', '#/pedidos': '📦', '#/perfil': '👤', '#/pedidos-online': '🧾', '#/pos': '💳', '#/caja': '💵', '#/ventas': '📈', '#/whatsapp': '💬', '#/preparar': '📦', '#/stock': '🗃️', '#/movimientos': '🔁', '#/entregas': '🛵', '#/historial': '🕘', '#/panel': '📊', '#/pedidos-admin': '🧾', '#/productos': '🍾', '#/promociones': '🏷️', '#/cupones': '🎟️', '#/mis-cupones': '🎟️', '#/usuarios': '👥', '#/cobranzas': '💰', '#/auditoria': '🔍', '#/respaldos': '💾' };
const PERSONAL = ['cajero', 'empleado', 'repartidor', 'administrador'];   // personal: menú lateral hamburguesa en cualquier pantalla
LF.menu = () => {
  const rol = LF.user ? LF.user.rol : 'publico', n = LF.carrito.reduce((x, l) => x + l.cantidad, 0);
  const activo = h => location.hash === h || (h === '#/' && !location.hash);
  const enlace = ([h, t]) => `<a href="${h}" class="${activo(h) ? 'on' : ''}"><i>${ICONOS[h] || '•'}</i>${t}${h === '#/carrito' && n ? ` <em>${n}</em>` : ''}</a>`;
  document.body.classList.toggle('staff', PERSONAL.includes(rol));
  LF.$('#menu').innerHTML = MENUS[rol].map(([h, t]) => `<a href="${h}" class="${activo(h) ? 'on' : ''}">${t}${h === '#/carrito' && n ? ` (${n})` : ''}</a>`).join('');
  LF.$('#drawerMenu').innerHTML = MENUS[rol].map(enlace).join('');
  LF.$('#drawerUser').innerHTML = LF.user ? `<div class="dr-user"><b>${LF.esc(LF.user.nombre)}</b><span>${LF.esc(LF.rolNombre(LF.user.rol))}</span></div>` : '<div class="dr-user"><b>Bienvenido</b><span>Inicie sesión para hacer pedidos</span></div>';
  LF.$('#drawerPie').innerHTML = LF.user ? '<button class="btn sec dr-salir" data-act="salir">Cerrar sesión</button>' : '<a class="btn dr-salir" href="#/login">Ingresar</a><a class="btn sec dr-salir" href="#/registro">Crear cuenta</a>';
  LF.$('#sesion').innerHTML = LF.user ? `<span>${LF.esc(LF.user.nombre)} · <b>${LF.esc(LF.rolNombre(LF.user.rol))}</b></span><button class="btn sm sec" data-act="salir">Salir</button>` : `<a href="#/login" class="btn sm">Ingresar</a><a href="#/registro" style="color:#bfdbfe">Registrarse</a>`;
};
LF.acc.salir = async () => { try { await LF.post('/auth/logout'); } catch (e) {} LF.gpsSincronizar([]); LF.drawer().hide(); LF.setToken(null); LF.user = null; LF.menu(); location.hash = '#/'; LF.render(); };
LF.sesionVencida = () => { LF.toast('Su sesión venció. Ingrese nuevamente.', 'bad'); LF.menu(); location.hash = '#/login'; };

LF.render = async (silencioso) => {
  const ruta = (location.hash.replace(/^#/, '') || '/').split('?')[0];
  LF.menu();
  clearTimeout(LF._auto);
  if (ruta !== '/entregas') LF.gpsSincronizar && LF.gpsSincronizar([]);
  const ms = LF.refresco && LF.refresco[ruta];
  if (ms) LF._auto = setTimeout(() => { if (document.hidden || !LF.$('#modal').hidden || document.activeElement && document.activeElement.tagName === 'SELECT') return LF.render(true); LF.render(true); }, ms);
  const btnApp = LF.$('#appFlot'); if (btnApp) btnApp.hidden = !(ruta === '/' && (!LF.user || LF.user.rol === 'cliente'));
  const permitidos = PERMITIDAS[ruta];
  if (permitidos && (!LF.user || !permitidos.includes(LF.user.rol))) { location.hash = LF.user ? LF.inicio() : '#/login'; return; }
  const vista = LF.rutas[ruta] || LF.rutas['/'];
  const app = LF.$('#app'); const y = window.scrollY;
  if (!silencioso) app.innerHTML = '<p class="sub">Cargando…</p>';
  try { app.innerHTML = await vista(); if (silencioso) window.scrollTo(0, y); if (ruta === '/login' || ruta === '/registro') LF.montarGoogle(); }
  catch (e) { app.innerHTML = `<div class="card note bad"><b>${LF.esc(e.mensaje || 'Error')}</b><br>${e.codigo === 'SIN_CONEXION' ? 'Inicie el backend con <code>python run.py</code> y recargue la página.' : ''}</div>`; }
};
// Menú hamburguesa: Offcanvas de Bootstrap (se abre desde la izquierda y se cierra al elegir una opción)
LF.drawer = () => ({ show() { try { bootstrap.Offcanvas.getOrCreateInstance('#drawer').show(); } catch (e) {} }, hide() { try { bootstrap.Offcanvas.getOrCreateInstance('#drawer').hide(); } catch (e) {} }, toggle() { try { bootstrap.Offcanvas.getOrCreateInstance('#drawer').toggle(); } catch (e) {} } });
LF.acc.menu = () => LF.drawer().toggle();
LF.$('#drawerMenu').addEventListener('click', ev => { if (ev.target.closest('a')) LF.drawer().hide(); });
window.addEventListener('hashchange', () => { LF.drawer().hide(); LF.cerrar(); LF.render(); });
document.addEventListener('input', ev => { const el = ev.target.closest('[data-input]'); if (el && LF.inp[el.dataset.input]) LF.inp[el.dataset.input](el); });
document.addEventListener('change', ev => { const el = ev.target; if (el.matches && el.matches('select[data-act]') || el.matches('input[type=checkbox][data-act]')) { const fn = LF.acc[el.dataset.act]; fn && Promise.resolve(fn(el)).catch(LF.err); } });

(async () => {
  if (LF.token) { try { LF.user = await LF.get('/auth/me'); } catch (e) { LF.setToken(null); } }
  if (LF.user && !location.hash) location.hash = LF.inicio();
  LF.render();
})();
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !LF.$('#modal').hidden) LF.cerrar(); });
