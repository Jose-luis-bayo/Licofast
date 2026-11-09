"""LicoFast: servicio web REST (monolito modular, 4 módulos, 5 capas). Ver SDD secciones 7 y 8."""
import logging
import threading
import time
import uuid
from decimal import Decimal
from flask import Flask, jsonify, send_from_directory
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
import datetime
from .config import Config
from .core.errors import AppError

log = logging.getLogger('licofast')


class Proveedor(DefaultJSONProvider):
    ensure_ascii = False
    sort_keys = False

    @staticmethod
    def default(o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat(sep=' ') if isinstance(o, datetime.datetime) else o.isoformat()
        return DefaultJSONProvider.default(o)


def _barrido(app):
    from .modules.pagos.facade import PagosFacade
    from .modules.ecommerce.service import PedidoService
    while True:
        time.sleep(Config.BARRIDO_SEG)
        try:
            PagosFacade.expirar_vencidos()
            PedidoService.cancelar_vencidos()
        except Exception:
            log.exception('Error en la tarea de barrido')


def create_app():
    app = Flask(__name__, static_folder=None)
    app.json = Proveedor(app)
    CORS(app, resources={r'/api/*': {'origins': Config.CORS_ORIGINS}}, allow_headers=['Content-Type', 'Authorization', 'Idempotency-Key', 'X-Firma'])

    from .modules.seguridad.controller import bp as seg
    from .modules.ecommerce.controller import bp as eco
    from .modules.pagos.controller import bp as pag
    from .modules.distribucion.controller import bp as dis
    for bp in (seg, eco, pag, dis):
        app.register_blueprint(bp)

    @app.get('/api/v1/health')
    def health():
        from .db import read, one
        try:
            with read() as cur:
                one(cur, 'SELECT 1')
            bd = 'ok'
        except Exception:
            bd = 'error'
        return jsonify(ok=bd == 'ok', backend='python-flask', version='1.0', base_de_datos=bd, modulos=['seguridad', 'ecommerce', 'pagos', 'distribucion'])

    @app.errorhandler(AppError)
    def _app_error(e):
        return jsonify(error={'codigo': e.codigo, 'mensaje': e.mensaje, 'detalle': e.detalle, 'traza': uuid.uuid4().hex[:8]}), e.status

    @app.errorhandler(HTTPException)
    def _http_error(e):
        cod = {404: 'RUTA_NO_ENCONTRADA', 405: 'METODO_NO_PERMITIDO', 400: 'PETICION_INVALIDA', 415: 'TIPO_NO_SOPORTADO'}.get(e.code, 'ERROR_HTTP')
        return jsonify(error={'codigo': cod, 'mensaje': e.description, 'detalle': None, 'traza': uuid.uuid4().hex[:8]}), e.code

    @app.errorhandler(Exception)
    def _error_interno(e):
        traza = uuid.uuid4().hex[:8]
        log.exception('Error interno [%s]', traza)
        return jsonify(error={'codigo': 'ERROR_INTERNO', 'mensaje': 'Ocurrió un error interno. Informe el código de traza.', 'detalle': None, 'traza': traza}), 500

    @app.after_request
    def _cabeceras(r):
        r.headers.setdefault('X-Content-Type-Options', 'nosniff')
        r.headers.setdefault('X-Frame-Options', 'DENY')
        r.headers.setdefault('Referrer-Policy', 'same-origin')
        if not r.headers.get('Cache-Control') and not r.mimetype.startswith('image'):
            r.headers['Cache-Control'] = 'no-store' if r.mimetype == 'application/json' else 'no-cache'
        return r

    @app.get('/')
    def index():
        return send_from_directory(Config.FRONTEND_DIR, 'index.html')

    @app.get('/<path:ruta>')
    def estaticos(ruta):
        if ruta.startswith('api/'):
            raise AppError('RUTA_NO_ENCONTRADA', 'Ruta no encontrada', 404)
        return send_from_directory(Config.FRONTEND_DIR, ruta)

    if not Config.TESTING and Config.BARRIDO_SEG > 0:
        threading.Thread(target=_barrido, args=(app,), daemon=True, name='barrido').start()
    return app
