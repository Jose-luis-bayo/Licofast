"""Quiosco de autoservicio: pedidos anónimos pagados en pantalla y retirados en bodega.
Seguridad: la app del quiosco envía la clave compartida X-Kiosko-Clave (KIOSKO_CLAVE; vacía = quiosco desactivado) y, para
leer/pagar/cancelar un pedido concreto, el token X-Kiosko-Acceso que el servidor entregó al crearlo (HMAC por pedido)."""
import hmac
from functools import wraps
from flask import Blueprint, jsonify, request
from ...config import Config
from ...core.errors import AppError, no_autenticado, no_encontrado
from ...core.idempotencia import idempotente
from ..ecommerce.service import PedidoService
from ..pagos.facade import PagosFacade

bp = Blueprint('kiosko', __name__, url_prefix='/api/v1/kiosko')


def _json(): return request.get_json(silent=True) or {}


def _base_publica(): return (Config.PUBLIC_URL or request.url_root).rstrip('/')


def kiosko_requerido(f):
    @wraps(f)
    def w(*a, **k):
        if not Config.KIOSKO_CLAVE:
            raise AppError('KIOSKO_DESACTIVADO', 'El quiosco no está habilitado en este servidor', 503)
        if not hmac.compare_digest(request.headers.get('X-Kiosko-Clave', ''), Config.KIOSKO_CLAVE):
            raise no_autenticado('Clave de quiosco inválida')
        return f(*a, **k)
    return w


def _acceso(vid):
    if not hmac.compare_digest(request.headers.get('X-Kiosko-Acceso', ''), PedidoService.acceso_kiosko(vid)):
        raise no_encontrado('Pedido no encontrado')


@bp.post('/pedidos')
@kiosko_requerido
@idempotente
def crear(): return jsonify(PedidoService.crear_kiosko(_json())), 201


@bp.get('/pedidos/<int:vid>')
@kiosko_requerido
def obtener(vid):
    _acceso(vid)
    return jsonify(PedidoService.obtener_kiosko(vid))


@bp.post('/pedidos/<int:vid>/pago')
@kiosko_requerido
def pagar(vid):
    _acceso(vid)
    pago = PagosFacade.iniciar_kiosko(vid, _json().get('metodo'), _base_publica())
    return jsonify({'pago': pago, 'simulable': _simulable(pago['metodo'])}), 201


@bp.post('/pedidos/<int:vid>/simular')
@kiosko_requerido
def simular(vid):
    _acceso(vid)
    return jsonify(PagosFacade.simular_kiosko(vid))


@bp.post('/pedidos/<int:vid>/cancelar')
@kiosko_requerido
def cancelar(vid):
    _acceso(vid)
    return jsonify(PedidoService.cancelar_kiosko(vid))


def _simulable(metodo):
    return {'qr': Config.QR_MODO == 'simulado', 'paypal': Config.PAYPAL_MODO == 'simulado', 'tarjeta': Config.TARJETA_MODO == 'simulado'}.get(metodo, False)
