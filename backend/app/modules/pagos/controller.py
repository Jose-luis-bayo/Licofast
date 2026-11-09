"""Capa 2: endpoints REST del módulo Pagos."""
from flask import Blueprint, g, jsonify, request
from ...core.auth import auth_required
from ...core.idempotencia import idempotente
from ...core import validators as v
from .service import PagoService, CajaService, ComprobanteService

bp = Blueprint('pagos', __name__, url_prefix='/api/v1')


def _json(): return request.get_json(silent=True) or {}


@bp.post('/pagos')
@auth_required('cliente', 'cajero')
@idempotente
def pagos_post(): return jsonify(PagoService.iniciar(g.user, _json())), 201


@bp.get('/pagos')
@auth_required('administrador')
def pagos_get():
    page, size, off = v.pagina(request.args)
    PagoService.expirar_vencidos()
    r = PagoService.reporte({k: request.args.get(k) for k in ('metodo', 'estado', 'desde', 'hasta')}, size, off)
    return jsonify({**r, 'page': page, 'size': size})


@bp.get('/pagos/<int:pid>')
@auth_required('cliente', 'cajero', 'administrador')
def pago_get(pid): return jsonify(PagoService.consultar(g.user, pid))


@bp.post('/pagos/webhook/qr')
def webhook_qr():
    return jsonify(PagoService.confirmar_qr(request.get_data(), request.headers.get('X-Firma', '')))


@bp.post('/pagos/simulador/qr/<referencia>/pagar')
@auth_required('cliente', 'cajero', 'administrador')
def simulador(referencia): return jsonify(PagoService.simular_pago(g.user, referencia))


@bp.post('/pagos/<int:pid>/anular')
@auth_required('administrador')
def pago_anular(pid): return jsonify(PagoService.anular(g.user, pid, _json()))


@bp.post('/cajas/apertura')
@auth_required('cajero')
def caja_abrir(): return jsonify(CajaService.abrir(g.user, _json())), 201


@bp.get('/cajas/actual')
@auth_required('cajero')
def caja_actual(): return jsonify(CajaService.actual(g.user))


@bp.get('/cajas')
@auth_required('administrador')
def caja_listar(): return jsonify(CajaService.listar())


@bp.post('/cajas/<int:cid>/movimientos')
@auth_required('cajero')
def caja_mov(cid): return jsonify(CajaService.movimiento(g.user, cid, _json())), 201


@bp.post('/cajas/<int:cid>/cierre')
@auth_required('cajero', 'administrador')
def caja_cierre(cid): return jsonify(CajaService.cerrar(g.user, cid, _json()))


@bp.get('/comprobantes/<int:cid>')
@auth_required('cliente', 'cajero', 'administrador')
def comprobante(cid): return jsonify(ComprobanteService.obtener(g.user, cid=cid))


@bp.get('/comprobantes')
@auth_required('cliente', 'cajero', 'administrador')
def comprobante_venta(): return jsonify(ComprobanteService.obtener(g.user, venta_id=request.args.get('venta_id', type=int)))
