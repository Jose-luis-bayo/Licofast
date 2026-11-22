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


@bp.put('/entregas/<int:vid>/ubicacion')
@auth_required('repartidor')
def guardar_ubicacion(vid): return jsonify(EntregaService.guardar_ubicacion(g.user, vid, _json()))


@bp.get('/pedidos/<int:vid>/ubicacion')
@auth_required('cliente', 'administrador', 'repartidor')
def ubicacion(vid): return jsonify(EntregaService.ubicacion(g.user, vid))


@bp.get('/pedidos/online')
@auth_required('cajero', 'empleado', 'administrador')
def online(): return jsonify(EntregaService.online(g.user))


@bp.get('/repartidores')
@auth_required('empleado', 'administrador')
def repartidores(): return jsonify(EntregaService.repartidores(g.user))


@bp.put('/pedidos/<int:vid>/confirmar')
@auth_required('cajero', 'administrador')
def confirmar(vid): return jsonify(EntregaService.confirmar(g.user, vid))


@bp.put('/pedidos/<int:vid>/rechazar')
@auth_required('cajero', 'administrador', 'empleado')
def rechazar(vid): return jsonify(EntregaService.rechazar(g.user, vid, _json()))


@bp.put('/pedidos/<int:vid>/preparar')
@auth_required('empleado', 'administrador')
def preparar(vid): return jsonify(EntregaService.preparar(g.user, vid))


@bp.put('/pedidos/<int:vid>/entregar-retiro')
@auth_required('empleado', 'administrador')
def entregar_retiro(vid): return jsonify(EntregaService.entregar_retiro(g.user, vid, _json()))


@bp.put('/pedidos/<int:vid>/asignacion')
@auth_required('administrador', 'empleado')
def asignar(vid): return jsonify(EntregaService.asignar(g.user, vid, _json()))


@bp.get('/pedidos/<int:vid>/seguimiento')
@auth_required('cliente', 'administrador')
def seguimiento(vid): return jsonify(EntregaService.seguimiento(g.user, vid))
