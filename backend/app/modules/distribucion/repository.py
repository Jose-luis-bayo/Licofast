"""Capa 4: acceso a datos del módulo Distribución."""
from ...db import one, all_, run

BASE = ("SELECT v.id,v.total,v.estado,v.estado_pago,IF(v.estado_pago='pagado',0,v.total) AS a_cobrar,v.direccion_entrega,v.referencia_entrega,v.telefono_contacto,"
        "v.observacion_entrega,v.fecha_entrega,v.created_at,v.repartidor_id,v.canal,v.lat_entrega,v.lng_entrega,v.metodo_pago,v.confirmado_en,v.preparado_en,v.tipo_venta,v.factura_nombre,v.factura_nit,v.factura_telefono,"
        "CONCAT(c.nombre,' ',c.apellido) AS cliente,CONCAT(r.nombre,' ',r.apellido) AS repartidor "
        "FROM ventas v LEFT JOIN usuarios c ON c.id=v.usuario_id LEFT JOIN usuarios r ON r.id=v.repartidor_id WHERE v.tipo_venta IN ('delivery','retiro') AND ")


class EntregaRepository:
    @staticmethod
    def abiertas_para(cur, repartidor_id=None, estado=None):
        """Repartidor: solo sus pedidos ya liberados por bodega. Administrador: todos los abiertos."""
        if repartidor_id:
            w, a = "v.estado IN ('preparado','en_camino') AND v.repartidor_id=%s", [repartidor_id]
            if estado in ('preparado', 'en_camino'):
                w, a = 'v.estado=%s AND v.repartidor_id=%s', [estado, repartidor_id]
            return all_(cur, BASE + w + ' ORDER BY v.id', a)
        w, a = "v.estado IN ('pendiente','confirmado','preparado','en_camino')", []
        if estado in ('pendiente', 'confirmado', 'preparado', 'en_camino'):
            w, a = 'v.estado=%s', [estado]
        return all_(cur, BASE + w + ' ORDER BY v.id', a)

    @staticmethod
    def online(cur, limite=150):
        """Pedidos online abiertos (cajero y bodega los trabajan por etapas)."""
        return all_(cur, BASE + "v.estado IN ('pendiente','confirmado','preparado','en_camino') ORDER BY v.id LIMIT %s", (limite,))

    @staticmethod
    def repartidor_menos_cargado(cur):
        """Reparto equitativo: quien tiene menos pedidos abiertos; si empatan, quien lleva más tiempo sin recibir uno."""
        return one(cur, "SELECT u.id, CONCAT(u.nombre,' ',u.apellido) AS nombre, "
                        "(SELECT COUNT(*) FROM ventas v WHERE v.repartidor_id=u.id AND v.estado IN ('preparado','en_camino')) AS carga, "
                        "(SELECT MAX(e.asignada_en) FROM entregas e WHERE e.repartidor_id=u.id) AS ultima "
                        "FROM usuarios u WHERE u.rol='repartidor' AND u.activo=1 ORDER BY carga, (ultima IS NOT NULL), ultima, u.id LIMIT 1")

    @staticmethod
    def cargas(cur):
        return all_(cur, "SELECT u.id, CONCAT(u.nombre,' ',u.apellido) AS nombre, u.telefono, "
                         "(SELECT COUNT(*) FROM ventas v WHERE v.repartidor_id=u.id AND v.estado='preparado') AS por_salir, "
                         "(SELECT COUNT(*) FROM ventas v WHERE v.repartidor_id=u.id AND v.estado='en_camino') AS en_camino "
                         "FROM usuarios u WHERE u.rol='repartidor' AND u.activo=1 ORDER BY u.id")

    @staticmethod
    def historial(cur, repartidor_id=None, limit=100):
        if repartidor_id:
            return all_(cur, BASE + "v.estado IN ('entregada','no_entregado') AND v.repartidor_id=%s ORDER BY v.fecha_entrega DESC LIMIT %s", (repartidor_id, limit))
        return all_(cur, BASE + "v.estado IN ('entregada','no_entregado') ORDER BY v.fecha_entrega DESC LIMIT %s", (limit,))

    @staticmethod
    def abierta(cur, venta_id): return one(cur, 'SELECT * FROM entregas WHERE venta_id=%s AND cerrada_en IS NULL ORDER BY id DESC LIMIT 1 FOR UPDATE', (venta_id,))

    @staticmethod
    def insertar(cur, venta_id, repartidor_id): return run(cur, 'INSERT INTO entregas(venta_id,repartidor_id,asignada_en) VALUES(%s,%s,NOW())', (venta_id, repartidor_id))

    @staticmethod
    def reasignar(cur, eid, repartidor_id): run(cur, 'UPDATE entregas SET repartidor_id=%s, asignada_en=NOW() WHERE id=%s', (repartidor_id, eid))

    @staticmethod
    def cerrar(cur, eid, resultado, obs): run(cur, 'UPDATE entregas SET resultado=%s, observacion=%s, cerrada_en=NOW() WHERE id=%s', (resultado, obs, eid))

    @staticmethod
    def historial_venta(cur, venta_id): return all_(cur, 'SELECT e.asignada_en,e.cerrada_en,e.resultado,e.observacion,CONCAT(u.nombre," ",u.apellido) AS repartidor FROM entregas e JOIN usuarios u ON u.id=e.repartidor_id WHERE e.venta_id=%s ORDER BY e.id', (venta_id,))


# --- Ubicación en vivo del repartidor (la tabla se crea sola la primera vez; no requiere migración manual) ---
_TABLA_UBICACION = False


def asegurar_tabla_ubicacion():
    global _TABLA_UBICACION
    if _TABLA_UBICACION:
        return
    from ...db import transaction
    with transaction() as cur:
        run(cur, 'CREATE TABLE IF NOT EXISTS ubicaciones_entrega (venta_id INT PRIMARY KEY, repartidor_id INT NOT NULL, '
                 'lat DECIMAL(9,6) NOT NULL, lng DECIMAL(9,6) NOT NULL, actualizado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP) ENGINE=InnoDB', ())
    _TABLA_UBICACION = True


class UbicacionRepository:
    @staticmethod
    def guardar(cur, venta_id, repartidor_id, lat, lng):
        run(cur, 'INSERT INTO ubicaciones_entrega(venta_id,repartidor_id,lat,lng) VALUES(%s,%s,%s,%s) '
                 'ON DUPLICATE KEY UPDATE repartidor_id=VALUES(repartidor_id), lat=VALUES(lat), lng=VALUES(lng), actualizado=NOW()', (venta_id, repartidor_id, lat, lng))

    @staticmethod
    def de_venta(cur, venta_id):
        return one(cur, 'SELECT venta_id,lat,lng,actualizado,TIMESTAMPDIFF(SECOND, actualizado, NOW()) AS hace_seg FROM ubicaciones_entrega WHERE venta_id=%s', (venta_id,))
