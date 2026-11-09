"""Capa 3: reglas del módulo Distribución."""
import datetime
from decimal import Decimal
from ...db import read, transaction
from ...core.errors import conflicto, invalido, no_encontrado, prohibido
from ...core.events import bus
from ...core import validators as v
from ..ecommerce.estado import EstadoPedido
from ..ecommerce.facade import EcommerceFacade as ECO
from ..pagos.facade import PagosFacade
from ..seguridad.repository import UsuarioRepository as U
from . import notificacion  # noqa: F401  (registra los observadores)
from .repository import EntregaRepository as E


def _num(row):
    return {k: (float(x) if isinstance(x, Decimal) else x) for k, x in row.items()}


class EntregaService:
    @staticmethod
    def listar(user, estado=None):
        from ..ecommerce.service import PedidoService
        PedidoService.cancelar_vencidos()
        with read() as cur:
            filas = E.abiertas_para(cur, user['id'] if user['rol'] == 'repartidor' else None, estado)
        return [_num(f) for f in filas]

    @staticmethod
    def historial(user):
        with read() as cur:
            filas = E.historial(cur, user['id'] if user['rol'] == 'repartidor' else None)
        return [_num(f) for f in filas]

    @staticmethod
    def _delivery_abierto(cur, vid):
        venta = ECO.bloquear_venta(cur, vid)
        if not venta or venta['tipo_venta'] != 'delivery':
            raise no_encontrado('Pedido no encontrado')
        return venta

    @staticmethod
    def asignar(admin, vid, d):
        rep_id = v.entero(d, 'repartidor_id', 1)
        with transaction() as cur:
            venta = EntregaService._delivery_abierto(cur, vid)
            if venta['estado'] not in ('pendiente', 'en_camino'):
                raise conflicto('PEDIDO_YA_PROCESADO', 'El pedido ya fue procesado')
            rep = U.por_id(cur, rep_id)
            if not rep or rep['rol'] != 'repartidor' or not rep['activo']:
                raise invalido('El usuario indicado no es un repartidor activo')
            ECO.actualizar_venta(cur, vid, {'repartidor_id': rep_id})
            ab = E.abierta(cur, vid)
            E.reasignar(cur, ab['id'], rep_id) if ab else E.insertar(cur, vid, rep_id)
        bus.publish('PedidoAsignado', usuario_id=admin['id'], entidad='venta', entidad_id=vid, detalle={'repartidor_id': rep_id})
        return {'mensaje': 'Pedido asignado', 'repartidor_id': rep_id}

    @staticmethod
    def en_camino(user, vid):
        with transaction() as cur:
            venta = EntregaService._delivery_abierto(cur, vid)
            if venta['repartidor_id'] not in (None, user['id']):
                raise prohibido('El pedido está asignado a otro repartidor')
            EstadoPedido.validar(venta['estado'], 'en_camino')
            ECO.actualizar_venta(cur, vid, {'estado': 'en_camino', 'repartidor_id': user['id']})
            ab = E.abierta(cur, vid)
            E.reasignar(cur, ab['id'], user['id']) if ab else E.insertar(cur, vid, user['id'])
            items = [_num(i) for i in ECO.detalle(cur, vid)]

        wa_url = notificacion.NotificacionService.en_camino(
            entidad_id=vid,
            telefono=venta['telefono_contacto'],
            items=items,
            total=venta['total'],
            estado_pago=venta['estado_pago'],
            direccion=venta['direccion_entrega']
        )
        bus.publish('PedidoEnCamino', usuario_id=user['id'], entidad='venta', entidad_id=vid,
                    telefono=venta['telefono_contacto'], detalle={'items_count': len(items)})
        return {'mensaje': 'Pedido en camino y WhatsApp enviado al cliente', 'estado': 'en_camino', 'whatsapp_url': wa_url}

    @staticmethod
    def en_destino(user, vid):
        with transaction() as cur:
            venta = EntregaService._delivery_abierto(cur, vid)
            if venta['repartidor_id'] not in (None, user['id']):
                raise prohibido('El pedido está asignado a otro repartidor')
            if venta['estado'] != 'en_camino':
                raise conflicto('ESTADO_INVALIDO', 'El pedido debe estar en camino para marcar que llegó al lugar')
            ECO.actualizar_venta(cur, vid, {'observacion_entrega': 'Repartidor en el lugar de entrega'})

        wa_url = notificacion.NotificacionService.en_destino(
            entidad_id=vid,
            telefono=venta['telefono_contacto'],
            total=venta['total'],
            estado_pago=venta['estado_pago']
        )
        bus.publish('PedidoEnDestino', usuario_id=user['id'], entidad='venta', entidad_id=vid,
                    telefono=venta['telefono_contacto'], detalle=None)
        return {'mensaje': 'Se notificó al cliente por WhatsApp que el repartidor llegó al lugar', 'whatsapp_url': wa_url}

    @staticmethod
    def cerrar(user, vid, d):
        """CU-D04 / CU-D05: transacción con bloqueo; el stock se repone una sola vez (corrige H-03)."""
        accion = d.get('accion')
        if accion not in ('entregado', 'no_entregado'):
            raise invalido('Indique la acción: «entregado» o «no_entregado»', {'campo': 'accion'})
        obs = v.texto(d, 'observacion', obligatorio=False, max_len=255)
        with transaction() as cur:
            venta = EntregaService._delivery_abierto(cur, vid)
            EstadoPedido.validar(venta['estado'], 'entregada' if accion == 'entregado' else 'no_entregado')   # 409 si ya fue procesado
            if venta['repartidor_id'] not in (None, user['id']):
                raise prohibido('El pedido está asignado a otro repartidor')
            ahora = datetime.datetime.now()
            if accion == 'entregado':
                if venta['estado_pago'] != 'pagado':
                    PagosFacade.registrar_cobro_entrega(cur, vid, venta['total'], user['id'])
                campos = {'estado': 'entregada', 'estado_pago': 'pagado', 'monto_cobrado': venta['total'], 'observacion_entrega': obs or 'Entrega conforme'}
                resultado = {'mensaje': 'Entrega confirmada', 'cobrado': float(venta['total'])}
            else:
                ECO.reponer_stock(cur, vid, user['id'], 'Pedido no entregado')
                PagosFacade.anular_pagos_de_venta(cur, vid, 'Pedido no entregado')
                campos = {'estado': 'no_entregado', 'estado_pago': 'anulado', 'monto_cobrado': 0, 'observacion_entrega': obs or 'El cliente no recibió el pedido'}
                resultado = {'mensaje': 'Pedido marcado como NO entregado. Los productos volvieron al inventario.', 'stock_repuesto': True, 'cobrado': 0.0}
                if venta['estado_pago'] == 'pagado':
                    resultado['requiere_reembolso'] = True
            campos.update(repartidor_id=user['id'], fecha_entrega=ahora)
            ECO.actualizar_venta(cur, vid, campos)
            ab = E.abierta(cur, vid)
            eid = ab['id'] if ab else E.insertar(cur, vid, user['id'])
            E.cerrar(cur, eid, accion, campos['observacion_entrega'])
        evento = 'PedidoEntregado' if accion == 'entregado' else 'PedidoNoEntregado'
        bus.publish(evento, usuario_id=user['id'], entidad='venta', entidad_id=vid, telefono=venta['telefono_contacto'], detalle={'observacion': campos['observacion_entrega']})
        resultado['estado'] = campos['estado']
        return resultado

    @staticmethod
    def seguimiento(user, vid):
        with read() as cur:
            venta = ECO.venta(cur, vid)
            if not venta or venta['tipo_venta'] != 'delivery' or (user['rol'] == 'cliente' and venta['usuario_id'] != user['id']):
                raise no_encontrado('Pedido no encontrado')
            etapas = E.historial_venta(cur, vid)
        linea = [{'evento': 'Pedido recibido', 'fecha': venta['created_at']}]
        for e in etapas:
            linea.append({'evento': f"Asignado a {e['repartidor']}", 'fecha': e['asignada_en']})
            if e['cerrada_en']:
                linea.append({'evento': 'Entregado' if e['resultado'] == 'entregado' else 'No se pudo entregar', 'fecha': e['cerrada_en'], 'detalle': e['observacion']})
        if venta['estado'] == 'en_camino':
            if venta.get('observacion_entrega') == 'Repartidor en el lugar de entrega':
                linea.append({'evento': '📍 ¡El repartidor ya llegó a su ubicación!', 'fecha': None})
            else:
                linea.append({'evento': '🛵 En camino hacia su dirección', 'fecha': None})
        return {'id': vid, 'estado': venta['estado'], 'estado_pago': venta['estado_pago'], 'repartidor': venta['repartidor'], 'total': float(venta['total']),
                'direccion_entrega': venta['direccion_entrega'], 'linea_tiempo': linea}
