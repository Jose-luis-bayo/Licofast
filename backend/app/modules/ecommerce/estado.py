"""Patrón State: transiciones válidas de ventas.estado y ventas.estado_pago (SDD figuras 22 y 23)."""
from ...core.errors import conflicto


class EstadoPedido:
    TRANSICIONES = {
        'pendiente': {'pagada', 'en_camino', 'entregada', 'no_entregado'},
        'en_camino': {'entregada', 'no_entregado'},
        'pagada': set(), 'entregada': set(), 'no_entregado': set(),
    }
    PAGO = {'pendiente': {'pagado', 'anulado'}, 'pagado': {'anulado'}, 'anulado': set()}

    @classmethod
    def validar(cls, actual, nuevo, tipo_venta='delivery'):
        if nuevo == 'pagada' and tipo_venta != 'mostrador':
            raise conflicto('TRANSICION_INVALIDA', 'Solo una venta de mostrador pasa a «pagada»')
        if nuevo not in cls.TRANSICIONES.get(actual, set()):
            raise conflicto('PEDIDO_YA_PROCESADO', 'El pedido ya fue procesado', {'estado_actual': actual, 'estado_pedido': nuevo})

    @classmethod
    def validar_pago(cls, actual, nuevo):
        if nuevo not in cls.PAGO.get(actual, set()):
            raise conflicto('PAGO_TRANSICION_INVALIDA', f'El pago no puede pasar de «{actual}» a «{nuevo}»')

    @classmethod
    def esta_abierto(cls, estado): return bool(cls.TRANSICIONES.get(estado))
