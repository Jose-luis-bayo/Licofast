"""Capa 2: JwtMiddleware + RbacGuard (Front Controller)."""
from functools import wraps
from flask import g, request
from .errors import no_autenticado, prohibido
from .security import leer_token


def _bearer():
    h = request.headers.get('Authorization', '')
    return h[7:].strip() if h.lower().startswith('bearer ') else None


def auth_required(*roles, optional=False):
    """Exige token válido y, si se indican, uno de los roles. optional=True permite anónimo."""
    def deco(fn):
        @wraps(fn)
        def w(*a, **k):
            from ..modules.seguridad.facade import SeguridadFacade
            tok = _bearer()
            if not tok:
                if optional:
                    g.user = None
                    return fn(*a, **k)
                raise no_autenticado()
            g.user = SeguridadFacade.identidad(leer_token(tok))
            if roles and g.user['rol'] not in roles:
                raise prohibido()
            return fn(*a, **k)
        return w
    return deco


def es_staff(user):
    return user and user['rol'] in ('administrador', 'cajero', 'empleado')
