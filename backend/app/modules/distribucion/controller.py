"""Capa 2: endpoints REST del módulo Distribución."""
from flask import Blueprint, g, jsonify, request
from ...core.auth import auth_required
from .service import EntregaService

bp = Blueprint('distribucion', __name__, url_prefix='/api/v1')


def _json(): return request.get_json(silent=True) or {}


@bp.get('/entregas')
@auth_required('repartidor', 'administrador')
def entregas(): return jsonify(EntregaService.listar(g.user, request.args.get('estado')))


@bp.get('/entregas/historial')
@auth_required('repartidor', 'administrador')
def historial(): return jsonify(EntregaService.historial(g.user))


@bp.put('/entregas/<int:vid>')
@auth_required('repartidor')
def cerrar(vid): return jsonify(EntregaService.cerrar(g.user, vid, _json()))


@bp.put('/entregas/<int:vid>/en-camino')
@auth_required('repartidor')
def en_camino(vid): return jsonify(EntregaService.en_camino(g.user, vid))


@bp.put('/entregas/<int:vid>/en-destino')
@auth_required('repartidor')
def en_destino(vid): return jsonify(EntregaService.en_destino(g.user, vid))


@bp.put('/pedidos/<int:vid>/asignacion')
@auth_required('administrador')
def asignar(vid): return jsonify(EntregaService.asignar(g.user, vid, _json()))


@bp.get('/pedidos/<int:vid>/seguimiento')
@auth_required('cliente', 'administrador')
def seguimiento(vid): return jsonify(EntregaService.seguimiento(g.user, vid))
