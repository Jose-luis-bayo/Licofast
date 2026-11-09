"""Facade del módulo E-commerce: contrato con Pagos y Distribución."""
from ...core.events import bus
from .service import PedidoService, InventarioService
from .repository import VentaRepository as V


class EcommerceFacade:
    @staticmethod
    def marcar_pagada(cur, venta_id): return PedidoService.marcar_pagada(cur, venta_id)

    @staticmethod
    def cancelar_venta(cur, venta_id, motivo, usuario_id): return PedidoService.cancelar_venta(cur, venta_id, motivo, usuario_id)

    @staticmethod
    def reponer_stock(cur, venta_id, usuario_id, motivo='No entregado'): return InventarioService.reponer(cur, venta_id, usuario_id, motivo)

    @staticmethod
    def bloquear_venta(cur, venta_id): return V.bloquear(cur, venta_id)

    @staticmethod
    def actualizar_venta(cur, venta_id, campos): return V.actualizar(cur, venta_id, campos)

    @staticmethod
    def venta(cur, venta_id): return V.por_id(cur, venta_id)

    @staticmethod
    def detalle(cur, venta_id): return V.detalle(cur, venta_id)


# E-commerce escucha el evento de Pagos (rompe el ciclo ECO↔PAG, SDD 7.5)
bus.subscribe('PagoConfirmado', PedidoService.al_confirmar_pago)
