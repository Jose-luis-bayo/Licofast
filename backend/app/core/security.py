"""PBKDF2-SHA256 (ADR-05) y JWT HS256 (ADR-04)."""
import base64
import hashlib
import hmac
import secrets
import time
import uuid
import jwt
from ..config import Config
from .errors import no_autenticado

_BLOQUEADOS = {}  # jti -> exp  (cierre de sesión; en memoria, ver SDD ADR-04)


def hash_password(p, iteraciones=None):
    it = iteraciones or Config.PBKDF2_ITER
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac('sha256', p.encode(), salt, it, 32)
    return f'PBKDF2-SHA256${it}${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}'


def verify_password(p, almacenado):
    try:
        a = almacenado.split('$')
        if a[0] != 'PBKDF2-SHA256':
            return False
        salt, viejo = base64.b64decode(a[2]), base64.b64decode(a[3])
        nuevo = hashlib.pbkdf2_hmac('sha256', p.encode(), salt, int(a[1]), 32)
        return hmac.compare_digest(nuevo, viejo)
    except Exception:
        return False


_DUMMY = hash_password('contraseña-ficticia')


def verify_dummy(p):
    """Gasta el mismo tiempo cuando el usuario no existe (evita enumerar cuentas)."""
    verify_password(p, _DUMMY)


def crear_token(usuario_id, rol):
    ahora = int(time.time())
    payload = {'sub': str(usuario_id), 'rol': rol, 'iat': ahora, 'exp': ahora + Config.JWT_HORAS * 3600, 'jti': uuid.uuid4().hex}
    return jwt.encode(payload, Config.JWT_SECRET, algorithm='HS256')


def leer_token(token):
    try:
        d = jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'], options={'require': ['exp', 'sub', 'rol']})
    except jwt.PyJWTError:
        raise no_autenticado('Token inválido o vencido')
    if d.get('jti') in _BLOQUEADOS:
        raise no_autenticado('La sesión fue cerrada')
    return d


def revocar_token(d):
    ahora = time.time()
    for k in [k for k, v in _BLOQUEADOS.items() if v < ahora]:
        _BLOQUEADOS.pop(k, None)
    _BLOQUEADOS[d['jti']] = d['exp']


def firmar_hmac(cuerpo: bytes, secreto: str) -> str:
    return hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()


def firma_valida(cuerpo: bytes, firma: str, secreto: str) -> bool:
    return bool(firma) and hmac.compare_digest(firmar_hmac(cuerpo, secreto), firma)
