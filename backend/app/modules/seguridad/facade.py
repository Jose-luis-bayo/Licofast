"""Facade del módulo Seguridad: lo único que los demás módulos pueden usar."""
from ...db import read
from ...core.errors import no_autenticado
from .repository import UsuarioRepository as U

PERMISOS = {  # matriz RBAC resumida (SDD 7.14)
    'catalogo.mantener': {'administrador'}, 'stock.mantener': {'administrador', 'empleado'},
    'venta.mostrador': {'cajero'}, 'pedido.crear': {'cliente'}, 'caja.operar': {'cajero'},
    'entrega.cerrar': {'repartidor'}, 'usuarios.mantener': {'administrador'}, 'auditoria.ver': {'administrador'},
}


class SeguridadFacade:
    @staticmethod
    def identidad(datos_token):
        """Convierte un JWT válido en el usuario actual, comprobando que la cuenta siga activa."""
        with read() as cur:
            u = U.por_id(cur, int(datos_token['sub']))
        if not u or not u['activo']:
            raise no_autenticado('Cuenta inexistente o inactiva')
        return {'id': u['id'], 'rol': u['rol'], 'usuario': u['usuario'], 'nombre': f"{u['nombre']} {u['apellido']}",
                'telefono': u['telefono'], 'fecha_nacimiento': u['fecha_nacimiento'], 'jti': datos_token.get('jti'), 'exp': datos_token.get('exp')}

    @staticmethod
    def tiene_permiso(rol, permiso): return rol in PERMISOS.get(permiso, set())

    @staticmethod
    def buscar_clientes(q=None):
        from .repository import buscar_clientes
        with read() as cur:
            return buscar_clientes(cur, q)

    @staticmethod
    def cliente_por_id(cur, uid):
        u = U.por_id(cur, uid)
        return u if u and u['rol'] == 'cliente' and u['activo'] else None
