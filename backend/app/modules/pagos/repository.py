"""Capa 4: acceso a datos del módulo Pagos."""
from ...db import one, all_, run


class PagoRepository:
    @staticmethod
    def insertar_efectivo(cur, venta_id, monto):
        return run(cur, "INSERT INTO pagos(venta_id,metodo,monto,estado,confirmado_en) VALUES(%s,'efectivo',%s,'confirmado',NOW())", (venta_id, monto))

    @staticmethod
    def insertar_qr(cur, venta_id, monto, referencia, payload, minutos):
        return run(cur, "INSERT INTO pagos(venta_id,metodo,monto,estado,referencia,qr_payload,qr_expira_en) VALUES(%s,'qr',%s,'pendiente',%s,%s,DATE_ADD(NOW(), INTERVAL %s MINUTE))",
                   (venta_id, monto, referencia, payload, minutos))

    @staticmethod
    def por_id(cur, pid, lock=False): return one(cur, 'SELECT * FROM pagos WHERE id=%s' + (' FOR UPDATE' if lock else ''), (pid,))

    @staticmethod
    def por_referencia(cur, ref, lock=False): return one(cur, 'SELECT * FROM pagos WHERE referencia=%s' + (' FOR UPDATE' if lock else ''), (ref,))

    @staticmethod
    def de_venta(cur, vid, lock=False): return all_(cur, 'SELECT * FROM pagos WHERE venta_id=%s ORDER BY id DESC' + (' FOR UPDATE' if lock else ''), (vid,))

    @staticmethod
    def ultimo(cur, vid):
        return one(cur, "SELECT id,metodo,monto,estado,referencia,qr_payload,qr_expira_en,confirmado_en,(qr_expira_en IS NOT NULL AND qr_expira_en<NOW()) AS expirado "
                        "FROM pagos WHERE venta_id=%s ORDER BY id DESC LIMIT 1", (vid,))

    @staticmethod
    def actualizar(cur, pid, campos): run(cur, f"UPDATE pagos SET {','.join(k + '=%s' for k in campos)} WHERE id=%s", [*campos.values(), pid])

    @staticmethod
    def marcar_confirmado(cur, pid, tx): run(cur, "UPDATE pagos SET estado='confirmado', confirmado_en=NOW(), id_transaccion=%s WHERE id=%s", (tx, pid))

    @staticmethod
    def qr_vencidos(cur): return all_(cur, "SELECT * FROM pagos WHERE metodo='qr' AND estado='pendiente' AND qr_expira_en<NOW() ORDER BY id FOR UPDATE")

    @staticmethod
    def reporte(cur, f, limit, offset):
        w, a = ['1=1'], []
        for campo, col in (('metodo', 'p.metodo'), ('estado', 'p.estado')):
            if f.get(campo):
                w.append(f'{col}=%s'); a.append(f[campo])
        if f.get('desde'):
            w.append('p.created_at>=%s'); a.append(f['desde'])
        if f.get('hasta'):
            w.append('p.created_at<DATE_ADD(%s, INTERVAL 1 DAY)'); a.append(f['hasta'])
        where = ' AND '.join(w)
        res = one(cur, f"SELECT COUNT(*) AS n, COALESCE(SUM(CASE WHEN p.estado='confirmado' THEN p.monto END),0) AS confirmado, "
                       f"COALESCE(SUM(CASE WHEN p.estado='confirmado' AND p.metodo='efectivo' THEN p.monto END),0) AS efectivo, "
                       f"COALESCE(SUM(CASE WHEN p.estado='confirmado' AND p.metodo='qr' THEN p.monto END),0) AS qr FROM pagos p WHERE {where}", a)
        filas = all_(cur, f'SELECT p.id,p.venta_id,p.metodo,p.monto,p.estado,p.referencia,p.confirmado_en,p.motivo_anulacion,p.created_at FROM pagos p WHERE {where} ORDER BY p.id DESC LIMIT %s OFFSET %s', [*a, limit, offset])
        return res, filas


class CajaRepository:
    @staticmethod
    def abierta(cur, cajero_id, lock=False):
        return one(cur, 'SELECT * FROM cajas WHERE cajero_id=%s AND cerrada_en IS NULL ORDER BY id DESC LIMIT 1' + (' FOR UPDATE' if lock else ''), (cajero_id,))

    @staticmethod
    def por_id(cur, cid, lock=False): return one(cur, 'SELECT * FROM cajas WHERE id=%s' + (' FOR UPDATE' if lock else ''), (cid,))

    @staticmethod
    def abrir(cur, cajero_id, monto): return run(cur, 'INSERT INTO cajas(cajero_id,monto_inicial,abierta_en) VALUES(%s,%s,NOW())', (cajero_id, monto))

    @staticmethod
    def cerrar(cur, cid, esperado, contado):
        run(cur, 'UPDATE cajas SET monto_esperado=%s, monto_contado=%s, cerrada_en=NOW() WHERE id=%s', (esperado, contado, cid))

    @staticmethod
    def mov_insertar(cur, caja_id, pago_id, tipo, monto, concepto):
        return run(cur, 'INSERT INTO movimientos_caja(caja_id,pago_id,tipo,monto,concepto) VALUES(%s,%s,%s,%s,%s)', (caja_id, pago_id, tipo, monto, concepto))

    @staticmethod
    def sumas(cur, cid):
        return one(cur, "SELECT COALESCE(SUM(CASE WHEN tipo='ingreso' THEN monto END),0) AS ingresos, COALESCE(SUM(CASE WHEN tipo='egreso' THEN monto END),0) AS egresos "
                        "FROM movimientos_caja WHERE caja_id=%s", (cid,))

    @staticmethod
    def movimientos(cur, cid): return all_(cur, 'SELECT * FROM movimientos_caja WHERE caja_id=%s ORDER BY id DESC', (cid,))

    @staticmethod
    def listar(cur, limit):
        return all_(cur, 'SELECT c.*, CONCAT(u.nombre," ",u.apellido) AS cajero FROM cajas c JOIN usuarios u ON u.id=c.cajero_id ORDER BY c.id DESC LIMIT %s', (limit,))


class ComprobanteRepository:
    @staticmethod
    def por_venta(cur, vid): return one(cur, 'SELECT * FROM comprobantes WHERE venta_id=%s', (vid,))

    @staticmethod
    def por_id(cur, cid): return one(cur, 'SELECT * FROM comprobantes WHERE id=%s', (cid,))

    @staticmethod
    def insertar(cur, vid):
        cid = run(cur, 'INSERT INTO comprobantes(venta_id,numero,emitido_en) VALUES(%s,%s,NOW())', (vid, f'TMP-{vid}'))
        run(cur, 'UPDATE comprobantes SET numero=%s WHERE id=%s', (f'C-{cid:06d}', cid))
        return cid
