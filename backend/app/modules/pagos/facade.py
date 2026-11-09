"""Facade del módulo Pagos."""
from ...db import all_
from .service import PagoService
from .repository import CajaRepository, PagoRepository


class PagosFacade:
    @staticmethod
    def caja_abierta(cur, cajero_id): return CajaRepository.abierta(cur, cajero_id)

    @staticmethod
    def cobrar_efectivo_mostrador(cur, venta_id, monto, caja_id, usuario_id): return PagoService.cobrar_efectivo_mostrador(cur, venta_id, monto, caja_id, usuario_id)

    @staticmethod
    def iniciar_qr(venta_id, usuario_id): return PagoService.iniciar_qr_sistema(venta_id, usuario_id)

    @staticmethod
    def registrar_cobro_entrega(cur, venta_id, monto, repartidor_id): return PagoService.registrar_cobro_entrega(cur, venta_id, monto, repartidor_id)

    @staticmethod
    def anular_pagos_de_venta(cur, venta_id, motivo): return PagoService.anular_pagos_de_venta(cur, venta_id, motivo)

    @staticmethod
    def ultimo_pago(cur, venta_id):
        p = PagoRepository.ultimo(cur, venta_id)
        if not p:
            return None
        return {k: (float(x) if hasattr(x, 'quantize') else x) for k, x in p.items()}

    @staticmethod
    def expirar_vencidos(): return PagoService.expirar_vencidos()
