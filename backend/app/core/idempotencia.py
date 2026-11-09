"""Cabecera Idempotency-Key para POST /pedidos y POST /pagos (SDD 7.10)."""
import json
from functools import wraps
from flask import g, jsonify, request, make_response
from ..db import transaction, one, run
from .errors import AppError, conflicto


def idempotente(fn):
    @wraps(fn)
    def w(*a, **k):
        clave = request.headers.get('Idempotency-Key')
        if not clave or not getattr(g, 'user', None):
            return fn(*a, **k)
        clave = clave[:80]
        uid = g.user['id']
        with transaction() as cur:
            previo = one(cur, 'SELECT status, respuesta FROM idempotencia WHERE clave=%s AND usuario_id=%s FOR UPDATE', (clave, uid))
            if previo is None:
                run(cur, 'INSERT INTO idempotencia(clave,usuario_id,ruta,status) VALUES(%s,%s,%s,0)', (clave, uid, request.path[:120]))
        if previo is not None:
            if previo['status'] == 0:
                raise conflicto('PETICION_EN_CURSO', 'La petición con esta Idempotency-Key aún se está procesando')
            resp = make_response(previo['respuesta'], previo['status'])
            resp.headers['Content-Type'] = 'application/json'
            resp.headers['Idempotent-Replay'] = 'true'
            return resp
        try:
            r = fn(*a, **k)
        except AppError:
            with transaction() as cur:
                run(cur, 'DELETE FROM idempotencia WHERE clave=%s AND usuario_id=%s', (clave, uid))
            raise
        except Exception:
            with transaction() as cur:
                run(cur, 'DELETE FROM idempotencia WHERE clave=%s AND usuario_id=%s', (clave, uid))
            raise
        resp = make_response(r)
        with transaction() as cur:
            run(cur, 'UPDATE idempotencia SET status=%s, respuesta=%s WHERE clave=%s AND usuario_id=%s',
                (resp.status_code, resp.get_data(as_text=True), clave, uid))
        return resp
    return w
