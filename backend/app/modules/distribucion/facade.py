"""Facade del módulo Distribución."""
from .service import EntregaService


class DistribucionFacade:
    listar = staticmethod(EntregaService.listar)
    seguimiento = staticmethod(EntregaService.seguimiento)
