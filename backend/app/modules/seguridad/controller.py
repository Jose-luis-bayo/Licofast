"""Capa 2: endpoints REST del módulo Seguridad."""
import time
from collections import defaultdict, deque
from flask import Blueprint, g, jsonify, request
from ...config import Config
from ...core.auth import auth_required
from ...core.errors import AppError, invalido
from ...core import validators as v
from ...core.security import leer_token
from . import respaldo
from .service import AuthService, UsuarioService, AuditoriaService

bp = Blueprint('seguridad', __name__, url_prefix='/api/v1')
_intentos = defaultdict(deque)


def _limite_login():
    """Límite por IP (en producción lo refuerza Nginx)."""
    ip, ahora = request.remote_addr or '-', time.time()
    q = _intentos[ip]
    while q and q[0] < ahora - 60:
        q.popleft()
    if len(q) >= Config.RATE_LOGIN_POR_MIN:
        raise AppError('DEMASIADAS_PETICIONES', 'Demasiados intentos. Espere un minuto.', 429)
    q.append(ahora)


@bp.post('/auth/login')
def login():
    _limite_login()
    d = request.get_json(silent=True) or {}
    return jsonify(AuthService.login(d.get('usuario'), d.get('password')))


@bp.post('/auth/register')
def register():
    _limite_login()
    return jsonify(AuthService.registrar(request.get_json(silent=True) or {})), 201


@bp.get('/auth/me')
@auth_required()
def me():
    return jsonify(AuthService.perfil(g.user['id']))


@bp.put('/auth/me')
@auth_required()
def me_put():
    return jsonify(AuthService.actualizar_perfil(g.user['id'], request.get_json(silent=True) or {}))


@bp.post('/auth/logout')
@auth_required()
def logout():
    AuthService.logout({'jti': g.user['jti'], 'exp': g.user['exp']}, g.user['id'])
    return jsonify({'mensaje': 'Sesión cerrada'})


@bp.get('/usuarios')
@auth_required('administrador')
def usuarios_get():
    return jsonify(UsuarioService.listar(request.args.get('rol')))


@bp.post('/usuarios')
@auth_required('administrador')
def usuarios_post():
    return jsonify(UsuarioService.crear(request.get_json(silent=True) or {}, g.user['id'])), 201


@bp.put('/usuarios/<int:uid>')
@auth_required('administrador')
def usuarios_put(uid):
    return jsonify(UsuarioService.actualizar(uid, request.get_json(silent=True) or {}, g.user['id']))


@bp.delete('/usuarios/<int:uid>')
@auth_required('administrador')
def usuarios_del(uid):
    return jsonify(UsuarioService.eliminar(uid, g.user['id']))


@bp.get('/auditoria')
@auth_required('administrador')
def auditoria():
    page, size, off = v.pagina(request.args)
    r = AuditoriaService.listar({k: request.args.get(k) for k in ('usuario_id', 'accion', 'entidad', 'desde', 'hasta')}, size, off)
    return jsonify({**r, 'page': page, 'size': size, 'paginas': -(-r['total'] // size)})


@bp.post('/admin/respaldo')
@auth_required('administrador')
def respaldo_post():
    return jsonify(respaldo.respaldar()), 201


@bp.get('/admin/respaldos')
@auth_required('administrador')
def respaldo_get():
    return jsonify(respaldo.listar())
