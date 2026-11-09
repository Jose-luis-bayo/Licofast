"""Patrón Strategy: formas de pago intercambiables (SDD figura de patrones)."""
from abc import ABC, abstractmethod
from ...config import Config
from .adapter import QrSasAdapter
from .repository import PagoRepository as R


class PasarelaPago(ABC):
    metodo = ''

    @abstractmethod
    def iniciar(self, cur, venta_id, monto):
        """Crea el pago y devuelve su id."""


class PagoEfectivo(PasarelaPago):
    metodo = 'efectivo'

    def iniciar(self, cur, venta_id, monto):
        return R.insertar_efectivo(cur, venta_id, monto)          # confirmado de inmediato


class PagoQr(PasarelaPago):
    metodo = 'qr'

    def iniciar(self, cur, venta_id, monto):
        qr = QrSasAdapter.generar_qr(venta_id, monto)
        return R.insertar_qr(cur, venta_id, monto, qr['referencia'], qr['payload'], Config.QR_EXPIRA_MIN)  # queda pendiente hasta el webhook


ESTRATEGIAS = {'efectivo': PagoEfectivo(), 'qr': PagoQr()}
