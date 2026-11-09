"""Capa 3: reglas del módulo Pagos."""
import json
import uuid
from decimal import Decimal
from ...config import Config
from ...db import read, transaction
from ...core.errors import AppError, conflicto, invalido, no_encontrado, no_autenticado, prohibido
from ...core.events import bus
from ...core import validators as v
from ..ecommerce.facade import EcommerceFacade as ECO
from .adapter import QrSasAdapter
from .repository import PagoRepository as R, CajaRepository as C, ComprobanteRepository as K
from .strategies import ESTRATEGIAS


def _num(row):
    return {k: (float(x) if isinstance(x, Decimal) else x) for k, x in row.items()} if row else row


class ComprobanteService:
    @staticmethod
    def emitir(cur, venta_id):
        c = K.por_venta(cur, venta_id)
        return c['id'] if c else K.insertar(cur, venta_id)

    @staticmethod
    def obtener(user, cid=None, venta_id=None):
        with read() as cur:
            c = K.por_id(cur, cid) if cid else K.por_venta(cur, venta_id)
            if not c:
                raise no_encontrado('Comprobante no encontrado')
            venta = ECO.venta(cur, c['venta_id'])
            if user['rol'] == 'cliente' and venta['usuario_id'] != user['id']:
                raise no_encontrado('Comprobante no encontrado')
            if user['rol'] not in ('cliente', 'cajero', 'administrador'):
                raise prohibido()
            items = ECO.detalle(cur, c['venta_id'])
            pago = R.ultimo(cur, c['venta_id'])
        return {'comprobante': c, 'venta': _num(venta), 'items': [_num(i) for i in items], 'pago': _num(pago), 'negocio': 'LicoFast — Licorería'}


class CajaService:
    @staticmethod
    def _estado(cur, caja):
        s = C.sumas(cur, caja['id'])
        esperado = Decimal(caja['monto_inicial']) + Decimal(s['ingresos']) - Decimal(s['egresos'])
        return {**_num(caja), 'ingresos': float(s['ingresos']), 'egresos': float(s['egresos']), 'esperado': float(esperado)}

    @staticmethod
    def abrir(user, d):
        monto = v.decimal(d, 'monto_inicial', minimo=0)
        with transaction() as cur:
            if C.abierta(cur, user['id'], lock=True):
                raise conflicto('CAJA_YA_ABIERTA', 'Ya tiene una caja abierta')
            cid = C.abrir(cur, user['id'], monto)
        bus.publish('CajaAbierta', usuario_id=user['id'], entidad='caja', entidad_id=cid, detalle={'monto_inicial': str(monto)})
        return CajaService.actual(user)

    @staticmethod
    def actual(user):
        with read() as cur:
            caja = C.abierta(cur, user['id'])
            if not caja:
                return None
            r = CajaService._estado(cur, caja)
            r['movimientos'] = [_num(m) for m in C.movimientos(cur, caja['id'])]
            return r

    @staticmethod
    def movimiento(user, caja_id, d):
        tipo = d.get('tipo')
        if tipo not in ('ingreso', 'egreso'):
            raise invalido('El tipo debe ser «ingreso» o «egreso»')
        monto, concepto = v.decimal(d, 'monto', minimo=0.01), v.texto(d, 'concepto', max_len=200)
        with transaction() as cur:
            caja = C.por_id(cur, caja_id, lock=True)
            if not caja or caja['cajero_id'] != user['id']:
                raise no_encontrado('Caja no encontrada')
            if caja['cerrada_en']:
                raise conflicto('CAJA_CERRADA', 'La caja ya fue cerrada')
            mid = C.mov_insertar(cur, caja_id, None, tipo, monto, concepto)
        bus.publish('MovimientoCaja', usuario_id=user['id'], entidad='caja', entidad_id=caja_id, detalle={'tipo': tipo, 'monto': str(monto), 'concepto': concepto})
        return {'id': mid, 'caja': CajaService.actual(user)}

    @staticmethod
    def cerrar(user, caja_id, d):
        contado = v.decimal(d, 'monto_contado', minimo=0)
        with transaction() as cur:
            caja = C.por_id(cur, caja_id, lock=True)
            if not caja or (caja['cajero_id'] != user['id'] and user['rol'] != 'administrador'):
                raise no_encontrado('Caja no encontrada')
            if caja['cerrada_en']:
                raise conflicto('CAJA_CERRADA', 'La caja ya fue cerrada')
            est = CajaService._estado(cur, caja)
            esperado = Decimal(str(est['esperado']))
            C.cerrar(cur, caja_id, esperado, contado)
        dif = contado - esperado
        bus.publish('CajaCerrada', usuario_id=user['id'], entidad='caja', entidad_id=caja_id, detalle={'esperado': str(esperado), 'contado': str(contado), 'diferencia': str(dif)})
        return {'caja_id': caja_id, 'esperado': float(esperado), 'contado': float(contado), 'diferencia': float(dif),
                'resultado': 'cuadra' if dif == 0 else ('sobrante' if dif > 0 else 'faltante')}

    @staticmethod
    def listar(limit=50):
        with read() as cur:
            return [_num(c) for c in C.listar(cur, limit)]


class PagoService:
    @staticmethod
    def cobrar_efectivo_mostrador(cur, venta_id, monto, caja_id, usuario_id):
        pid = ESTRATEGIAS['efectivo'].iniciar(cur, venta_id, monto)
        C.mov_insertar(cur, caja_id, pid, 'ingreso', monto, f'Venta #{venta_id} en efectivo')
        ComprobanteService.emitir(cur, venta_id)
        ECO.marcar_pagada(cur, venta_id)
        return pid

    @staticmethod
    def _qr_en_tx(cur, venta):
        """Devuelve el QR vigente de la venta o crea uno nuevo."""
        for p in R.de_venta(cur, venta['id'], lock=True):
            if p['estado'] == 'confirmado':
                raise conflicto('VENTA_YA_PAGADA', 'La venta ya fue pagada')
            if p['metodo'] == 'qr' and p['estado'] == 'pendiente':
                vigente = R.ultimo(cur, venta['id'])
                if vigente and vigente['id'] == p['id'] and not vigente['expirado']:
                    return p['id']
                R.actualizar(cur, p['id'], {'estado': 'vencido'})
        return ESTRATEGIAS['qr'].iniciar(cur, venta['id'], venta['total'])

    @staticmethod
    def _cobrable(venta):
        if venta['estado_pago'] != 'pendiente' or venta['estado'] not in ('pendiente', 'en_camino'):
            raise conflicto('VENTA_NO_COBRABLE', 'La venta no está pendiente de cobro')

    @staticmethod
    def iniciar(user, d):
        venta_id, metodo = v.entero(d, 'venta_id', 1), d.get('metodo')
        if metodo not in ESTRATEGIAS:
            raise invalido('El método debe ser «efectivo» o «qr»')
        with transaction() as cur:
            venta = ECO.bloquear_venta(cur, venta_id)
            if not venta:
                raise no_encontrado('Venta no encontrada')
            if user['rol'] == 'cliente':
                if venta['usuario_id'] != user['id'] or venta['tipo_venta'] != 'delivery':
                    raise no_encontrado('Venta no encontrada')
                if metodo != 'qr':
                    raise prohibido('El cliente solo puede pagar por QR; el efectivo se cobra contra entrega')
            elif user['rol'] == 'cajero':
                if venta['tipo_venta'] != 'mostrador' or venta['cajero_id'] != user['id']:
                    raise prohibido('Solo puede cobrar ventas de su propio mostrador')
            else:
                raise prohibido()
            PagoService._cobrable(venta)
            if metodo == 'qr':
                pid = PagoService._qr_en_tx(cur, venta)
            else:
                caja = C.abierta(cur, user['id'])
                if not caja:
                    raise conflicto('CAJA_CERRADA', 'Debe abrir su caja antes de cobrar')
                for p in R.de_venta(cur, venta_id, lock=True):
                    if p['estado'] == 'pendiente':
                        R.actualizar(cur, p['id'], {'estado': 'anulado', 'motivo_anulacion': 'Reemplazado por cobro en efectivo'})
                pid = PagoService.cobrar_efectivo_mostrador(cur, venta_id, venta['total'], caja['id'], user['id'])
            pago = _num(R.por_id(cur, pid))
        bus.publish('PagoIniciado', usuario_id=user['id'], entidad='pago', entidad_id=pid, detalle={'venta_id': venta_id, 'metodo': metodo})
        if metodo == 'efectivo':
            bus.publish('PagoConfirmado', usuario_id=user['id'], entidad='pago', entidad_id=pid, venta_id=venta_id, detalle={'metodo': 'efectivo'})
        return pago

    @staticmethod
    def iniciar_qr_sistema(venta_id, usuario_id):
        """Usado por E-commerce tras registrar una venta de mostrador con QR."""
        try:
            with transaction() as cur:
                venta = ECO.bloquear_venta(cur, venta_id)
                pid = PagoService._qr_en_tx(cur, venta)
                pago = _num(R.por_id(cur, pid))
        except AppError as e:
            if e.status == 503:           # EC-6: el banco no responde → la venta sigue pendiente, se puede cobrar en efectivo
                return {'error': {'codigo': e.codigo, 'mensaje': e.mensaje}}
            raise
        bus.publish('PagoIniciado', usuario_id=usuario_id, entidad='pago', entidad_id=pago['id'], detalle={'venta_id': venta_id, 'metodo': 'qr'})
        return pago

    @staticmethod
    def consultar(user, pid):
        PagoService.expirar_vencidos()
        with read() as cur:
            p = R.por_id(cur, pid)
            if not p:
                raise no_encontrado('Pago no encontrado')
            venta = ECO.venta(cur, p['venta_id'])
            if user['rol'] == 'cliente' and venta['usuario_id'] != user['id']:
                raise no_encontrado('Pago no encontrado')
            if user['rol'] == 'cajero' and venta['cajero_id'] != user['id']:
                raise prohibido()
            if user['rol'] not in ('cliente', 'cajero', 'administrador'):
                raise prohibido()
            r = _num(p)
            r['venta_estado'], r['venta_estado_pago'] = venta['estado'], venta['estado_pago']
        return r

    @staticmethod
    def confirmar_qr(cuerpo: bytes, firma: str):
        """Webhook del banco: firma, monto y referencia se validan; es idempotente."""
        if not QrSasAdapter.firma_valida(cuerpo, firma):
            bus.publish('WebhookRechazado', usuario_id=None, entidad='pago', entidad_id=None, detalle={'motivo': 'firma inválida'})
            raise no_autenticado('Firma inválida')
        try:
            d = json.loads(cuerpo.decode('utf-8'))
        except Exception:
            raise invalido('Cuerpo JSON inválido')
        ref, tx = d.get('referencia'), str(d.get('id_transaccion') or uuid.uuid4().hex)[:80]
        monto = v.decimal(d, 'monto', minimo=0.01)
        if d.get('estado') != 'PAGADO':
            return {'ok': True, 'ignorado': True}
        with transaction() as cur:
            p = R.por_referencia(cur, ref, lock=True) if ref else None
            if not p:
                raise no_encontrado('Referencia desconocida')
            if p['estado'] == 'confirmado':
                return {'ok': True, 'idempotente': True, 'pago_id': p['id']}
            if p['estado'] in ('vencido', 'anulado'):
                bus.publish('PagoTardio', usuario_id=None, entidad='pago', entidad_id=p['id'], detalle={'estado': p['estado'], 'monto': str(monto)})
                raise conflicto('PAGO_FUERA_DE_PLAZO', 'El pago llegó cuando la referencia ya no estaba vigente; requiere revisión manual')
            if Decimal(p['monto']) != monto:
                bus.publish('MontoIncorrecto', usuario_id=None, entidad='pago', entidad_id=p['id'], detalle={'esperado': str(p['monto']), 'recibido': str(monto)})
                raise invalido('El monto no coincide con el de la referencia', codigo='MONTO_INCORRECTO')
            R.marcar_confirmado(cur, p['id'], tx)
            ComprobanteService.emitir(cur, p['venta_id'])
            ECO.marcar_pagada(cur, p['venta_id'])
            pid, vid = p['id'], p['venta_id']
        bus.publish('PagoConfirmado', usuario_id=None, entidad='pago', entidad_id=pid, venta_id=vid, detalle={'metodo': 'qr', 'tx': tx})
        return {'ok': True, 'pago_id': pid}

    @staticmethod
    def simular_pago(user, referencia):
        """Solo QR_MODO=simulado: reproduce lo que haría el banco (cuerpo firmado con el secreto)."""
        if Config.QR_MODO != 'simulado':
            raise prohibido('El simulador solo está disponible en modo simulado')
        with read() as cur:
            p = R.por_referencia(cur, referencia)
            if not p:
                raise no_encontrado('Referencia desconocida')
            venta = ECO.venta(cur, p['venta_id'])
        if user['rol'] == 'cliente' and venta['usuario_id'] != user['id']:
            raise no_encontrado('Referencia desconocida')
        cuerpo = json.dumps({'referencia': referencia, 'monto': str(p['monto']), 'estado': 'PAGADO', 'id_transaccion': 'SIM-' + uuid.uuid4().hex[:10]}).encode()
        return PagoService.confirmar_qr(cuerpo, QrSasAdapter.firmar(cuerpo))

    @staticmethod
    def registrar_cobro_entrega(cur, venta_id, monto, repartidor_id):
        """Cobro en efectivo contra entrega (lo llama Distribución dentro de su transacción)."""
        for p in R.de_venta(cur, venta_id, lock=True):
            if p['estado'] == 'pendiente':
                R.actualizar(cur, p['id'], {'estado': 'anulado', 'motivo_anulacion': 'Cobrado contra entrega'})
        pid = ESTRATEGIAS['efectivo'].iniciar(cur, venta_id, monto)
        ComprobanteService.emitir(cur, venta_id)
        return pid

    @staticmethod
    def anular_pagos_de_venta(cur, venta_id, motivo):
        for p in R.de_venta(cur, venta_id, lock=True):
            if p['estado'] in ('pendiente', 'confirmado'):
                R.actualizar(cur, p['id'], {'estado': 'anulado', 'motivo_anulacion': motivo[:200]})

    @staticmethod
    def anular(user, pid, d):
        """CU-P07: anulación de un cobro de mostrador, con motivo y sin borrar el registro."""
        motivo = v.texto(d, 'motivo', max_len=200)
        with transaction() as cur:
            p = R.por_id(cur, pid, lock=True)
            if not p:
                raise no_encontrado('Pago no encontrado')
            if p['estado'] == 'anulado':
                raise conflicto('PAGO_YA_ANULADO', 'El pago ya está anulado')
            venta = ECO.bloquear_venta(cur, p['venta_id'])
            if venta['tipo_venta'] != 'mostrador' or venta['estado'] not in ('pagada', 'pendiente'):
                raise conflicto('PAGO_NO_ANULABLE', 'Solo se anulan cobros de ventas de mostrador; los pedidos delivery se cierran desde Distribución')
            R.actualizar(cur, pid, {'estado': 'anulado', 'motivo_anulacion': motivo})
            if p['estado'] == 'confirmado' and p['metodo'] == 'efectivo' and venta['cajero_id']:
                caja = C.abierta(cur, venta['cajero_id'])
                if caja:
                    C.mov_insertar(cur, caja['id'], pid, 'egreso', p['monto'], f"Anulación de venta #{venta['id']}: {motivo}")
            ECO.reponer_stock(cur, venta['id'], user['id'], 'Anulación de cobro')
            ECO.actualizar_venta(cur, venta['id'], {'estado': 'no_entregado', 'estado_pago': 'anulado', 'monto_cobrado': 0, 'observacion_entrega': f'Anulada: {motivo}'[:255]})
        bus.publish('PagoAnulado', usuario_id=user['id'], entidad='pago', entidad_id=pid, detalle={'venta_id': p['venta_id'], 'motivo': motivo})
        return {'mensaje': 'Pago anulado; el stock fue repuesto'}

    @staticmethod
    def expirar_vencidos():
        n = 0
        with transaction() as cur:
            for p in R.qr_vencidos(cur):
                R.actualizar(cur, p['id'], {'estado': 'vencido'})
                venta = ECO.bloquear_venta(cur, p['venta_id'])
                if venta and venta['tipo_venta'] == 'mostrador' and venta['estado'] == 'pendiente' and venta['estado_pago'] == 'pendiente':
                    ECO.cancelar_venta(cur, venta['id'], 'QR vencido sin pago', None)
                n += 1
        if n:
            bus.publish('QrVencidos', usuario_id=None, entidad='pago', entidad_id=None, detalle={'cantidad': n})
        return n

    @staticmethod
    def reporte(f, limit, offset):
        with read() as cur:
            res, filas = R.reporte(cur, f, limit, offset)
        return {'resumen': _num(res), 'items': [_num(x) for x in filas]}
