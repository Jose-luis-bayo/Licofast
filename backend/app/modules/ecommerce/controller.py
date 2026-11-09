"""Capa 2: endpoints REST del módulo E-commerce."""
from flask import Blueprint, g, jsonify, request
from ...core.auth import auth_required
from ...core.errors import prohibido
from ...core.idempotencia import idempotente
from ...core import validators as v
from ..seguridad.facade import SeguridadFacade
from .service import CatalogoService, InventarioService, PedidoService, PromocionService, ReporteService

bp = Blueprint('ecommerce', __name__, url_prefix='/api/v1')


def _json(): return request.get_json(silent=True) or {}


@bp.get('/productos')
@auth_required(optional=True)
def productos():
    if request.args.get('todos'):
        if not g.user or g.user['rol'] not in ('administrador', 'cajero', 'empleado'):
            raise prohibido()
        return jsonify(CatalogoService.listar_todos())
    cat = request.args.get('categoria_id', type=int)
    return jsonify(CatalogoService.listar_publico(request.args.get('q'), cat))


@bp.post('/productos')
@auth_required('administrador')
def productos_post(): return jsonify(CatalogoService.crear(_json(), g.user['id'])), 201


@bp.put('/productos/<int:pid>')
@auth_required('administrador')
def productos_put(pid): return jsonify(CatalogoService.actualizar(pid, _json(), g.user['id']))


@bp.delete('/productos/<int:pid>')
@auth_required('administrador')
def productos_del(pid): return jsonify(CatalogoService.eliminar(pid, g.user['id']))


@bp.get('/categorias')
def categorias(): return jsonify(CatalogoService.categorias())


@bp.post('/categorias')
@auth_required('administrador')
def categorias_post(): return jsonify(CatalogoService.categoria_crear(_json(), g.user['id'])), 201


@bp.put('/categorias/<int:cid>')
@auth_required('administrador')
def categorias_put(cid): return jsonify(CatalogoService.categoria_actualizar(cid, _json(), g.user['id']))


@bp.get('/promociones')
@auth_required('administrador')
def promos_get(): return jsonify(PromocionService.listar())


@bp.post('/promociones')
@auth_required('administrador')
def promos_post(): return jsonify(PromocionService.crear(_json(), g.user['id'])), 201


@bp.put('/promociones/<int:pid>')
@auth_required('administrador')
def promos_put(pid): return jsonify(PromocionService.actualizar(pid, _json(), g.user['id']))


@bp.delete('/promociones/<int:pid>')
@auth_required('administrador')
def promos_del(pid): return jsonify(PromocionService.eliminar(pid, g.user['id']))


@bp.post('/carrito/cotizar')
def cotizar(): return jsonify(PedidoService.cotizar(_json().get('items')))


@bp.get('/clientes')
@auth_required('administrador', 'cajero')
def clientes(): return jsonify(SeguridadFacade.buscar_clientes(request.args.get('q')))


@bp.post('/pedidos')
@auth_required('cliente')
@idempotente
def pedidos_post(): return jsonify(PedidoService.crear_pedido(g.user, _json())), 201


@bp.post('/pedidos/whatsapp')
@auth_required('cajero', 'administrador')
def pedidos_whatsapp(): return jsonify(PedidoService.pedido_whatsapp(g.user, _json())), 201


@bp.get('/pedidos')
@auth_required('cliente', 'administrador')
def pedidos_get():
    page, size, off = v.pagina(request.args)
    f = {k: request.args.get(k) for k in ('estado', 'estado_pago', 'tipo', 'desde', 'hasta')}
    r = PedidoService.listar(g.user, f, size, off)
    return jsonify({**r, 'page': page, 'size': size})


@bp.get('/pedidos/<int:vid>')
@auth_required()
def pedido_get(vid): return jsonify(PedidoService.obtener(g.user, vid))


@bp.post('/ventas')
@auth_required('cajero')
def ventas_post(): return jsonify(PedidoService.venta_mostrador(g.user, _json())), 201


@bp.get('/ventas')
@auth_required('administrador', 'cajero')
def ventas_get():
    page, size, off = v.pagina(request.args)
    f = {k: request.args.get(k) for k in ('estado', 'estado_pago', 'tipo', 'desde', 'hasta', 'alcance')}
    r = PedidoService.listar(g.user, f, size, off)
    return jsonify({**r, 'page': page, 'size': size})


@bp.get('/inventario/movimientos')
@auth_required('administrador', 'empleado')
def mov_get(): return jsonify(InventarioService.movimientos(request.args.get('producto_id', type=int), request.args.get('limit', 100, type=int)))


@bp.post('/inventario/movimientos')
@auth_required('administrador', 'empleado')
def mov_post(): return jsonify(InventarioService.movimiento(_json(), g.user['id'])), 201


@bp.get('/inventario/alertas')
@auth_required('administrador', 'empleado', 'cajero')
def alertas(): return jsonify(InventarioService.alertas())


@bp.get('/reportes/resumen')
@auth_required('administrador')
def resumen(): return jsonify(ReporteService.resumen())
