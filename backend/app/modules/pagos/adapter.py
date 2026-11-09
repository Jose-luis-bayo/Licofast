"""Adapter: aísla el contrato del servicio SAS del Banco Económico (ADR-08).
En QR_MODO=simulado genera un QR local y acepta el webhook firmado; el modo «sas» queda
pendiente hasta tener el contrato técnico del banco (riesgo R-1 del SDD)."""
import uuid
from ...config import Config
from ...core.errors import AppError
from ...core.security import firma_valida, firmar_hmac


class QrSasAdapter:
    @staticmethod
    def generar_qr(venta_id, monto):
        if Config.QR_MODO != 'simulado':
            raise AppError('PASARELA_NO_DISPONIBLE', 'El servicio de pagos QR no está disponible. Cobre en efectivo.', 503)
        ref = 'LF' + uuid.uuid4().hex[:12].upper()
        return {'referencia': ref, 'payload': f'LICOFAST-SAS|{ref}|{monto}|BOB|VENTA{venta_id}'}

    @staticmethod
    def firma_valida(cuerpo: bytes, firma: str) -> bool:
        return firma_valida(cuerpo, firma, Config.QR_SECRETO)

    @staticmethod
    def firmar(cuerpo: bytes) -> str:
        return firmar_hmac(cuerpo, Config.QR_SECRETO)
