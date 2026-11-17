"""Patrón State: transiciones válidas de ventas.estado y ventas.estado_pago (SDD figuras 22 y 23).

Flujo de un pedido delivery (cada paso lo hace un rol distinto):
  pendiente --(cajero confirma)--> confirmado --(bodega prepara y libera)--> preparado
  preparado --(repartidor sale)--> en_camino --(repartidor cierra)--> entregada | no_entregado
Cualquier etapa anterior a la entrega puede terminar en no_entregado (rechazo o cancelación).
"""
from ...core.errors import conflicto


class EstadoPedido:
    TRANSICIONES = {
        'pendiente': {'confirmado', 'pagada', 'no_entregado'},
        'confirmado': {'preparado', 'no_entregado'},
        'preparado': {'en_camino', 'no_entregado'},
        'en_camino': {'entregada', 'no_entregado'},
        'pagada': set(), 'entregada': set(), 'no_entregado': set(),
    }
    PAGO = {'pendiente': {'pagado', 'anulado'}, 'pagado': {'anulado'}, 'anulado': set()}
    ABIERTOS = ('pendiente', 'confirmado', 'preparado', 'en_camino')
    ETIQUETA = {'pendiente': 'Recibido (espera al cajero)', 'confirmado': 'Confirmado por caja', 'preparado': 'Preparado por bodega',
                'en_camino': 'En camino', 'entregada': 'Entregado', 'no_entregado': 'No entregado', 'pagada': 'Pagada'}

    @classmethod
    def validar(cls, actual, nuevo, tipo_venta='delivery'):
        if nuevo == 'pagada' and tipo_venta != 'mostrador':
            raise conflicto('TRANSICION_INVALIDA', 'Solo una venta de mostrador pasa a «pagada»')
        if nuevo not in cls.TRANSICIONES.get(actual, set()):
            if actual in ('entregada', 'no_entregado', 'pagada'):
                raise conflicto('PEDIDO_YA_PROCESADO', 'El pedido ya fue procesado', {'estado_actual': actual, 'estado_pedido': nuevo})
            raise conflicto('ETAPA_INVALIDA', f'El pedido está «{cls.ETIQUETA.get(actual, actual)}»: no puede pasar a «{cls.ETIQUETA.get(nuevo, nuevo)}» todavía',
                            {'estado_actual': actual, 'estado_pedido': nuevo})

    @classmethod
    def validar_pago(cls, actual, nuevo):
        if nuevo not in cls.PAGO.get(actual, set()):
            raise conflicto('PAGO_TRANSICION_INVALIDA', f'El pago no puede pasar de «{actual}» a «{nuevo}»')

    @classmethod
    def esta_abierto(cls, estado): return bool(cls.TRANSICIONES.get(estado))
