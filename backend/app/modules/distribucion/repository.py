"""Capa 4: acceso a datos del módulo Distribución."""
from ...db import one, all_, run

BASE = ("SELECT v.id,v.total,v.estado,v.estado_pago,IF(v.estado_pago='pagado',0,v.total) AS a_cobrar,v.direccion_entrega,v.referencia_entrega,v.telefono_contacto,"
        "v.observacion_entrega,v.fecha_entrega,v.created_at,v.repartidor_id,v.canal,CONCAT(c.nombre,' ',c.apellido) AS cliente,CONCAT(r.nombre,' ',r.apellido) AS repartidor "
        "FROM ventas v LEFT JOIN usuarios c ON c.id=v.usuario_id LEFT JOIN usuarios r ON r.id=v.repartidor_id WHERE v.tipo_venta='delivery' AND ")


class EntregaRepository:
    @staticmethod
    def abiertas_para(cur, repartidor_id=None, estado=None):
        w, a = "v.estado IN ('pendiente','en_camino')", []
        if estado in ('pendiente', 'en_camino'):
            w, a = 'v.estado=%s', [estado]
        if repartidor_id:
            w += ' AND (v.repartidor_id IS NULL OR v.repartidor_id=%s)'; a.append(repartidor_id)
        return all_(cur, BASE + w + ' ORDER BY v.id', a)

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
