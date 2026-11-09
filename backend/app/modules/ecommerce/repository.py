"""Capa 4: acceso a datos del módulo E-commerce (Repository)."""
from ...db import one, all_, run

PROD_COLS = 'p.id,p.nombre,p.descripcion,p.precio,p.stock,p.stock_minimo,p.imagen_url,p.categoria_id,p.activo,c.nombre AS categoria'


class ProductoRepository:
    @staticmethod
    def publico(cur, q=None, categoria_id=None):
        w, a = ['p.activo=1'], []
        if q:
            w.append('(p.nombre LIKE %s OR p.descripcion LIKE %s)'); a += [f'%{q}%'] * 2
        if categoria_id:
            w.append('p.categoria_id=%s'); a.append(categoria_id)
        return all_(cur, f"SELECT {PROD_COLS} FROM productos p LEFT JOIN categorias c ON c.id=p.categoria_id WHERE {' AND '.join(w)} ORDER BY p.nombre", a)

    @staticmethod
    def todos(cur): return all_(cur, f'SELECT {PROD_COLS} FROM productos p LEFT JOIN categorias c ON c.id=p.categoria_id ORDER BY p.nombre')

    @staticmethod
    def por_id(cur, pid): return one(cur, f'SELECT {PROD_COLS} FROM productos p LEFT JOIN categorias c ON c.id=p.categoria_id WHERE p.id=%s', (pid,))

    @staticmethod
    def bloquear(cur, ids):
        """SELECT … FOR UPDATE ordenado por id (evita interbloqueos, ADR-07)."""
        ids = sorted(set(ids))
        filas = all_(cur, f"SELECT * FROM productos WHERE id IN ({','.join(['%s'] * len(ids))}) ORDER BY id FOR UPDATE", ids)
        return {f['id']: f for f in filas}

    @staticmethod
    def insertar(cur, d):
        return run(cur, 'INSERT INTO productos(nombre,descripcion,precio,stock,stock_minimo,imagen_url,categoria_id,activo) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                   (d['nombre'], d['descripcion'], d['precio'], d['stock'], d['stock_minimo'], d['imagen_url'], d['categoria_id'], d['activo']))

    @staticmethod
    def actualizar(cur, pid, d):
        run(cur, 'UPDATE productos SET nombre=%s,descripcion=%s,precio=%s,stock_minimo=%s,imagen_url=%s,categoria_id=%s,activo=%s WHERE id=%s',
            (d['nombre'], d['descripcion'], d['precio'], d['stock_minimo'], d['imagen_url'], d['categoria_id'], d['activo'], pid))

    @staticmethod
    def desactivar(cur, pid): run(cur, 'UPDATE productos SET activo=0 WHERE id=%s', (pid,))

    @staticmethod
    def tiene_ventas(cur, pid): return one(cur, 'SELECT 1 AS x FROM detalle_venta WHERE producto_id=%s LIMIT 1', (pid,)) is not None

    @staticmethod
    def eliminar(cur, pid): run(cur, 'DELETE FROM productos WHERE id=%s', (pid,))

    @staticmethod
    def sumar_stock(cur, pid, n): run(cur, 'UPDATE productos SET stock=stock+%s WHERE id=%s', (n, pid))

    @staticmethod
    def alertas(cur):
        return all_(cur, f'SELECT {PROD_COLS} FROM productos p LEFT JOIN categorias c ON c.id=p.categoria_id WHERE p.activo=1 AND p.stock<=p.stock_minimo ORDER BY p.stock')


class CategoriaRepository:
    @staticmethod
    def listar(cur): return all_(cur, 'SELECT id,nombre,activo FROM categorias ORDER BY nombre')

    @staticmethod
    def insertar(cur, nombre): return run(cur, 'INSERT INTO categorias(nombre) VALUES(%s)', (nombre,))

    @staticmethod
    def actualizar(cur, cid, nombre, activo): run(cur, 'UPDATE categorias SET nombre=%s, activo=%s WHERE id=%s', (nombre, activo, cid))

    @staticmethod
    def existe(cur, cid): return one(cur, 'SELECT id FROM categorias WHERE id=%s', (cid,)) is not None


class PromocionRepository:
    @staticmethod
    def vigentes(cur): return all_(cur, 'SELECT * FROM promociones WHERE activo=1 AND CURDATE() BETWEEN desde AND hasta')

    @staticmethod
    def todas(cur):
        return all_(cur, 'SELECT pr.*, p.nombre AS producto, c.nombre AS categoria FROM promociones pr LEFT JOIN productos p ON p.id=pr.producto_id '
                         'LEFT JOIN categorias c ON c.id=pr.categoria_id ORDER BY pr.id DESC')

    @staticmethod
    def insertar(cur, d):
        return run(cur, 'INSERT INTO promociones(nombre,tipo,valor,producto_id,categoria_id,desde,hasta,activo) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                   (d['nombre'], d['tipo'], d['valor'], d['producto_id'], d['categoria_id'], d['desde'], d['hasta'], d['activo']))

    @staticmethod
    def actualizar(cur, pid, d):
        run(cur, 'UPDATE promociones SET nombre=%s,tipo=%s,valor=%s,producto_id=%s,categoria_id=%s,desde=%s,hasta=%s,activo=%s WHERE id=%s',
            (d['nombre'], d['tipo'], d['valor'], d['producto_id'], d['categoria_id'], d['desde'], d['hasta'], d['activo'], pid))

    @staticmethod
    def eliminar(cur, pid): run(cur, 'DELETE FROM promociones WHERE id=%s', (pid,))


class VentaRepository:
    COLS = ("v.id,v.usuario_id,v.cajero_id,v.repartidor_id,v.tipo_venta,v.canal,v.total,v.descuento,v.monto_cobrado,v.estado,v.estado_pago,"
            "v.direccion_entrega,v.referencia_entrega,v.telefono_contacto,v.observacion_entrega,v.fecha_entrega,v.created_at,"
            "CONCAT(c.nombre,' ',c.apellido) AS cliente, CONCAT(r.nombre,' ',r.apellido) AS repartidor")
    JOIN = 'FROM ventas v LEFT JOIN usuarios c ON c.id=v.usuario_id LEFT JOIN usuarios r ON r.id=v.repartidor_id'

    @staticmethod
    def insertar(cur, d):
        cols = list(d)
        return run(cur, f"INSERT INTO ventas({','.join(cols)}) VALUES({','.join(['%s'] * len(cols))})", [d[c] for c in cols])

    @staticmethod
    def insertar_detalle(cur, venta_id, pid, cant, precio):
        run(cur, 'INSERT INTO detalle_venta(venta_id,producto_id,cantidad,precio_unitario) VALUES(%s,%s,%s,%s)', (venta_id, pid, cant, precio))

    @staticmethod
    def bloquear(cur, vid): return one(cur, 'SELECT * FROM ventas WHERE id=%s FOR UPDATE', (vid,))

    @staticmethod
    def por_id(cur, vid): return one(cur, f'SELECT {VentaRepository.COLS} {VentaRepository.JOIN} WHERE v.id=%s', (vid,))

    @staticmethod
    def detalle(cur, vid):
        return all_(cur, 'SELECT d.producto_id,p.nombre,d.cantidad,d.precio_unitario,(d.cantidad*d.precio_unitario) AS subtotal '
                         'FROM detalle_venta d JOIN productos p ON p.id=d.producto_id WHERE d.venta_id=%s ORDER BY d.id', (vid,))

    @staticmethod
    def actualizar(cur, vid, campos):
        run(cur, f"UPDATE ventas SET {','.join(k + '=%s' for k in campos)} WHERE id=%s", [*campos.values(), vid])

    @staticmethod
    def listar(cur, f, limit, offset):
        w, a = ['1=1'], []
        for campo, col in (('usuario_id', 'v.usuario_id'), ('cajero_id', 'v.cajero_id'), ('tipo', 'v.tipo_venta'), ('estado', 'v.estado'), ('estado_pago', 'v.estado_pago')):
            if f.get(campo):
                w.append(f'{col}=%s'); a.append(f[campo])
        if f.get('desde'):
            w.append('v.created_at>=%s'); a.append(f['desde'])
        if f.get('hasta'):
            w.append('v.created_at<DATE_ADD(%s, INTERVAL 1 DAY)'); a.append(f['hasta'])
        where = ' AND '.join(w)
        total = one(cur, f'SELECT COUNT(*) AS n FROM ventas v WHERE {where}', a)['n']
        filas = all_(cur, f'SELECT {VentaRepository.COLS} {VentaRepository.JOIN} WHERE {where} ORDER BY v.id DESC LIMIT %s OFFSET %s', [*a, limit, offset])
        return total, filas

    @staticmethod
    def delivery_vencidos(cur, minutos):
        return all_(cur, "SELECT id FROM ventas WHERE tipo_venta='delivery' AND estado='pendiente' AND estado_pago='pendiente' AND repartidor_id IS NULL "
                         "AND created_at < DATE_SUB(NOW(), INTERVAL %s MINUTE) ORDER BY id FOR UPDATE", (minutos,))


class MovimientoRepository:
    @staticmethod
    def insertar(cur, pid, tipo, cantidad, motivo, venta_id, usuario_id):
        run(cur, 'INSERT INTO movimientos_stock(producto_id,tipo,cantidad,motivo,venta_id,usuario_id) VALUES(%s,%s,%s,%s,%s,%s)',
            (pid, tipo, cantidad, motivo, venta_id, usuario_id))

    @staticmethod
    def listar(cur, pid, limit):
        if pid:
            return all_(cur, 'SELECT m.*,p.nombre AS producto,u.usuario FROM movimientos_stock m JOIN productos p ON p.id=m.producto_id LEFT JOIN usuarios u ON u.id=m.usuario_id '
                             'WHERE m.producto_id=%s ORDER BY m.id DESC LIMIT %s', (pid, limit))
        return all_(cur, 'SELECT m.*,p.nombre AS producto,u.usuario FROM movimientos_stock m JOIN productos p ON p.id=m.producto_id LEFT JOIN usuarios u ON u.id=m.usuario_id '
                         'ORDER BY m.id DESC LIMIT %s', (limit,))
