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
from .repository import EntregaRepository as E, UbicacionRepository as UB, asegurar_tabla_ubicacion


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
    def online(user):
        """Bandeja de pedidos online abiertos, con sus productos (para que bodega sepa qué alistar)."""
        from ..ecommerce.service import PedidoService
        PedidoService.cancelar_vencidos()
        with read() as cur:
            filas = [_num(f) for f in E.online(cur)]
            for f in filas:
                f['items'] = [_num(i) for i in ECO.detalle(cur, f['id'])]
        return filas

    @staticmethod
    def repartidores(user):
        with read() as cur:
            return [_num(r) for r in E.cargas(cur)]

    # ---- Etapa 1: caja ----
    @staticmethod
    def confirmar(user, vid):
        """El cajero revisa el pedido (y su pago si fue QR/PayPal) y lo envía a bodega."""
        with transaction() as cur:
            venta = EntregaService._delivery_abierto(cur, vid)
            EstadoPedido.validar(venta['estado'], 'confirmado')
            if venta['metodo_pago'] in ('qr', 'paypal') and venta['estado_pago'] != 'pagado':
                raise conflicto('PAGO_PENDIENTE', f"El cliente eligió pagar con {venta['metodo_pago'].upper()} y todavía no pagó. Espere la confirmación del pago o rechace el pedido.")
            ECO.actualizar_venta(cur, vid, {'estado': 'confirmado', 'confirmado_en': datetime.datetime.now(), 'confirmado_por': user['id']})
        bus.publish('PedidoConfirmado', usuario_id=user['id'], entidad='venta', entidad_id=vid, detalle=None)
        return {'mensaje': 'Pedido confirmado y enviado a bodega', 'estado': 'confirmado'}

    @staticmethod
    def rechazar(user, vid, d):
        motivo = v.texto(d, 'motivo', max_len=200)
        with transaction() as cur:
            venta = EntregaService._delivery_abierto(cur, vid)
            if venta['estado'] not in ('pendiente', 'confirmado', 'preparado'):
                raise conflicto('ETAPA_INVALIDA', 'Solo se puede rechazar un pedido que aún no salió a reparto')
            pagado = venta['estado_pago'] == 'pagado'
            PagosFacade.anular_pagos_de_venta(cur, vid, 'Pedido rechazado: ' + motivo)
            ECO.cancelar_venta(cur, vid, 'Rechazado: ' + motivo, user['id'])
        bus.publish('PedidoRechazado', usuario_id=user['id'], entidad='venta', entidad_id=vid, detalle={'motivo': motivo})
        r = {'mensaje': 'Pedido rechazado; el stock volvió al inventario'}
        if pagado:
            r['requiere_reembolso'] = True
            r['mensaje'] += '. El cliente ya había pagado: debe escribirle por WhatsApp para devolverle el dinero (el cliente envía su QR).'
        return r

    # ---- Etapa 2: bodega ----
    @staticmethod
    def preparar(user, vid):
        """Bodega alista y libera el pedido; el sistema lo asigna al repartidor con menos carga."""
        with transaction() as cur:
            venta = EntregaService._delivery_abierto(cur, vid)
            EstadoPedido.validar(venta['estado'], 'preparado')
            rep_id = venta['repartidor_id']
            if rep_id:                                 # el administrador ya lo había asignado a mano
                rep = U.por_id(cur, rep_id)
                rep_nombre = f"{rep['nombre']} {rep['apellido']}" if rep else ''
            else:
                rep = E.repartidor_menos_cargado(cur)
                if not rep:
                    raise conflicto('SIN_REPARTIDORES', 'No hay repartidores activos. Cree o active un repartidor para liberar el pedido.')
                rep_id, rep_nombre = rep['id'], rep['nombre']
            ECO.actualizar_venta(cur, vid, {'estado': 'preparado', 'repartidor_id': rep_id, 'preparado_en': datetime.datetime.now(), 'preparado_por': user['id']})
            ab = E.abierta(cur, vid)
            E.reasignar(cur, ab['id'], rep_id) if ab else E.insertar(cur, vid, rep_id)
        bus.publish('PedidoPreparado', usuario_id=user['id'], entidad='venta', entidad_id=vid, detalle={'repartidor_id': rep_id})
        return {'mensaje': f'Pedido preparado y asignado a {rep_nombre}', 'estado': 'preparado', 'repartidor_id': rep_id, 'repartidor': rep_nombre}

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
            if venta['estado'] not in ('confirmado', 'preparado', 'en_camino'):
                raise conflicto('ETAPA_INVALIDA', 'Solo se puede cambiar el repartidor de un pedido confirmado, preparado o en camino')
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
            if venta['repartidor_id'] != user['id']:
                raise prohibido('El pedido no está asignado a usted')
            EstadoPedido.validar(venta['estado'], 'en_camino')
            ECO.actualizar_venta(cur, vid, {'estado': 'en_camino'})
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
            if venta['repartidor_id'] != user['id']:
                raise prohibido('El pedido no está asignado a usted')
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
            if venta['repartidor_id'] != user['id']:
                raise prohibido('El pedido no está asignado a usted')
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
        if accion == 'entregado' and venta.get('usuario_id'):
            try:                                              # premio por cliente frecuente / antigüedad; nunca debe romper la entrega
                from ..ecommerce.cupones import CuponService
                nuevos = CuponService.evaluar_recompensas(venta['usuario_id'])
                if nuevos: resultado['recompensa_cliente'] = nuevos
            except Exception:
                import logging; logging.getLogger(__name__).exception('No se pudo evaluar la recompensa')
        return resultado

    @staticmethod
    def guardar_ubicacion(user, vid, d):
        """El celular del repartidor envía su posición GPS mientras el pedido está «en camino»."""
        try:
            lat, lng = float(d.get('lat')), float(d.get('lng'))
        except (TypeError, ValueError):
            raise invalido('Latitud y longitud deben ser números', {'campo': 'lat/lng'})
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise invalido('Coordenadas fuera de rango', {'campo': 'lat/lng'})
        asegurar_tabla_ubicacion()
        with transaction() as cur:
            venta = EntregaService._delivery_abierto(cur, vid)
            if venta['repartidor_id'] != user['id']:
                raise prohibido('El pedido no está asignado a usted')
            if venta['estado'] != 'en_camino':
                raise conflicto('ESTADO_INVALIDO', 'Solo se comparte la ubicación mientras el pedido está en camino')
            UB.guardar(cur, vid, user['id'], round(lat, 6), round(lng, 6))
        return {'ok': True}

    @staticmethod
    def ubicacion(user, vid):
        """Última posición conocida del repartidor, para el mapa del cliente."""
        asegurar_tabla_ubicacion()
        with read() as cur:
            venta = ECO.venta(cur, vid)
            if not venta or venta['tipo_venta'] != 'delivery' or (user['rol'] == 'cliente' and venta['usuario_id'] != user['id']):
                raise no_encontrado('Pedido no encontrado')
            pos = UB.de_venta(cur, vid) if venta['estado'] == 'en_camino' else None
        out = {'venta_id': vid, 'estado': venta['estado'], 'repartidor': venta.get('repartidor'), 'direccion_entrega': venta['direccion_entrega'], 'destino_lat': float(venta['lat_entrega']) if venta.get('lat_entrega') is not None else None,
               'destino_lng': float(venta['lng_entrega']) if venta.get('lng_entrega') is not None else None, 'disponible': pos is not None}
        if pos:
            out.update(lat=float(pos['lat']), lng=float(pos['lng']), actualizado=pos['actualizado'], hace_seg=int(pos['hace_seg'] or 0))
        return out

    @staticmethod
    def seguimiento(user, vid):
        with read() as cur:
            venta = ECO.venta(cur, vid)
            if not venta or venta['tipo_venta'] != 'delivery' or (user['rol'] == 'cliente' and venta['usuario_id'] != user['id']):
                raise no_encontrado('Pedido no encontrado')
            etapas = E.historial_venta(cur, vid)
        linea = [{'evento': 'Pedido recibido', 'fecha': venta['created_at']}]
        if venta.get('confirmado_en'):
            linea.append({'evento': 'Confirmado por caja', 'fecha': venta['confirmado_en']})
        if venta.get('preparado_en'):
            linea.append({'evento': 'Preparado en bodega', 'fecha': venta['preparado_en']})
        for e in etapas:
            linea.append({'evento': f"Asignado a {e['repartidor']}", 'fecha': e['asignada_en']})
            if e['cerrada_en']:
                linea.append({'evento': 'Entregado' if e['resultado'] == 'entregado' else 'No se pudo entregar', 'fecha': e['cerrada_en'], 'detalle': e['observacion']})
        if venta['estado'] == 'pendiente':
            linea.append({'evento': '⏳ Esperando la confirmación de caja', 'fecha': None})
        elif venta['estado'] == 'confirmado':
            linea.append({'evento': '📦 Bodega está preparando su pedido', 'fecha': None})
        elif venta['estado'] == 'preparado':
            linea.append({'evento': '✅ Listo: el repartidor saldrá en breve', 'fecha': None})
        if venta['estado'] == 'en_camino':
            if venta.get('observacion_entrega') == 'Repartidor en el lugar de entrega':
                linea.append({'evento': '📍 ¡El repartidor ya llegó a su ubicación!', 'fecha': None})
            else:
                linea.append({'evento': '🛵 En camino hacia su dirección', 'fecha': None})
        return {'id': vid, 'estado': venta['estado'], 'estado_pago': venta['estado_pago'], 'metodo_pago': venta['metodo_pago'], 'repartidor': venta['repartidor'], 'total': float(venta['total']),
                'direccion_entrega': venta['direccion_entrega'], 'linea_tiempo': linea}
