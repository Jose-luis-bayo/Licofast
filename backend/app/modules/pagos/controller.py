"""Capa 2: endpoints REST del módulo Pagos."""
from html import escape
from flask import Blueprint, Response, g, jsonify, request
from ...config import Config
from ...core.auth import auth_required
from ...core.idempotencia import idempotente
from ...core import validators as v
from ...core.errors import prohibido
from .service import PagoService, CajaService, ComprobanteService

bp = Blueprint('pagos', __name__, url_prefix='/api/v1')


def _json(): return request.get_json(silent=True) or {}


def _base_publica():
    """URL pública del sitio (para que PayPal sepa a dónde regresar al cliente)."""
    return (Config.PUBLIC_URL or request.url_root).rstrip('/')


def _pagina(titulo, cuerpo, ok=True):
    color = '#047857' if ok else '#be123c'
    html = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{titulo}</title>'
            f'<style>body{{font-family:system-ui,Segoe UI,Arial;background:#f1f6fd;display:grid;place-items:center;min-height:100vh;margin:0;padding:16px}}'
            f'.c{{background:#fff;border-radius:16px;padding:28px;max-width:420px;text-align:center;box-shadow:0 10px 30px #0b1f4b22}}'
            f'h1{{color:{color};font-size:22px}}a,button{{display:inline-block;margin-top:14px;background:#1d4ed8;color:#fff;border:0;border-radius:10px;padding:12px 20px;font-size:16px;text-decoration:none;cursor:pointer}}</style></head>'
            f'<body><div class="c"><div style="font-size:46px">🍾</div><h1>{titulo}</h1>{cuerpo}</div></body></html>')
    return Response(html, mimetype='text/html')


@bp.post('/pagos')
@auth_required('cliente', 'cajero')
@idempotente
def pagos_post(): return jsonify(PagoService.iniciar(g.user, _json(), _base_publica())), 201


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


@bp.get('/pagos/paypal/retorno')
def paypal_retorno():
    try:
        PagoService.confirmar_paypal(request.args.get('token'))
    except Exception as e:
        return _pagina('No se pudo confirmar el pago', f'<p>{getattr(e, "mensaje", "Ocurrió un error")}</p><a href="{_base_publica()}/#/pedidos">Volver a LicoFast</a>', ok=False), 200
    return _pagina('¡Pago recibido!', f'<p>Gracias. Ya puede cerrar esta ventana y volver a LicoFast: su pedido se actualizará solo.</p><a href="{_base_publica()}/#/pedidos">Ir a mis pedidos</a>')


@bp.get('/pagos/paypal/cancelado')
def paypal_cancelado():
    return _pagina('Pago cancelado', '<p>No se realizó ningún cobro. Puede intentarlo de nuevo desde su pedido o pagar en efectivo al recibirlo.</p>', ok=False)


@bp.get('/pagos/simulador/paypal/<referencia>')
def paypal_simulador(referencia):
    if Config.PAYPAL_MODO != 'simulado':
        raise prohibido('El simulador solo está disponible en modo simulado')
    return _pagina('PayPal (simulación)', f'<p>Esta es una página de <b>prueba</b>: no se cobra dinero real.</p><a href="{_base_publica()}/api/v1/pagos/paypal/retorno?token={escape(referencia)}">Pagar con PayPal</a>')


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
