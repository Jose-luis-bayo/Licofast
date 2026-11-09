"""Errores de aplicación con formato uniforme (SDD 7.10)."""


class AppError(Exception):
    def __init__(self, codigo, mensaje, status=400, detalle=None):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.status, self.detalle = codigo, mensaje, status, detalle


def invalido(mensaje, detalle=None, codigo='DATOS_INVALIDOS'): return AppError(codigo, mensaje, 422, detalle)
def conflicto(codigo, mensaje, detalle=None): return AppError(codigo, mensaje, 409, detalle)
def no_encontrado(mensaje='Recurso no encontrado'): return AppError('NO_ENCONTRADO', mensaje, 404)
def prohibido(mensaje='No tiene permiso para esta operación'): return AppError('PROHIBIDO', mensaje, 403)
def no_autenticado(mensaje='Token requerido o inválido'): return AppError('NO_AUTENTICADO', mensaje, 401)
