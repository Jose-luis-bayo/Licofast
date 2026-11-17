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


class PayPalAdapter:
    """Adapter de PayPal Orders API v2 (https://developer.paypal.com). PayPal cobra en dólares: se convierte con PAYPAL_TASA_BOB.
    PAYPAL_MODO=simulado  → no sale a internet: genera una página de aprobación local para probar el flujo completo.
    PAYPAL_MODO=sandbox   → cuentas de prueba de PayPal (sin dinero real).   PAYPAL_MODO=live → dinero real."""

    @staticmethod
    def _base():
        return 'https://api-m.paypal.com' if Config.PAYPAL_MODO == 'live' else 'https://api-m.sandbox.paypal.com'

    @staticmethod
    def usd(monto_bob):
        from decimal import Decimal, ROUND_HALF_UP
        return (Decimal(str(monto_bob)) / Decimal(str(Config.PAYPAL_TASA_BOB))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def _token():
        import requests
        if not Config.PAYPAL_CLIENT_ID or not Config.PAYPAL_SECRET:
            raise AppError('PASARELA_NO_DISPONIBLE', 'PayPal no está configurado en el servidor (faltan PAYPAL_CLIENT_ID / PAYPAL_SECRET).', 503)
        try:
            r = requests.post(PayPalAdapter._base() + '/v1/oauth2/token', auth=(Config.PAYPAL_CLIENT_ID, Config.PAYPAL_SECRET),
                              data={'grant_type': 'client_credentials'}, timeout=20)
        except requests.RequestException:
            raise AppError('PASARELA_NO_DISPONIBLE', 'No se pudo contactar a PayPal. Intente más tarde o pague en efectivo.', 503)
        if r.status_code != 200:
            raise AppError('PASARELA_NO_DISPONIBLE', 'PayPal rechazó las credenciales del comercio. Revise PAYPAL_CLIENT_ID y PAYPAL_SECRET.', 503)
        return r.json()['access_token']

    @staticmethod
    def crear_orden(venta_id, monto_bob, base_url):
        usd = PayPalAdapter.usd(monto_bob)
        if Config.PAYPAL_MODO == 'simulado':
            ref = 'PP' + uuid.uuid4().hex[:14].upper()
            return {'id': ref, 'approve_url': f'{base_url}/api/v1/pagos/simulador/paypal/{ref}', 'usd': float(usd)}
        import requests
        tok = PayPalAdapter._token()
        cuerpo = {'intent': 'CAPTURE',
                  'purchase_units': [{'reference_id': f'VENTA{venta_id}', 'description': f'LicoFast - pedido #{venta_id}',
                                      'amount': {'currency_code': 'USD', 'value': str(usd)}}],
                  'application_context': {'brand_name': 'LicoFast', 'user_action': 'PAY_NOW', 'shipping_preference': 'NO_SHIPPING',
                                          'return_url': f'{base_url}/api/v1/pagos/paypal/retorno?venta={venta_id}',
                                          'cancel_url': f'{base_url}/api/v1/pagos/paypal/cancelado?venta={venta_id}'}}
        try:
            r = requests.post(PayPalAdapter._base() + '/v2/checkout/orders', json=cuerpo, timeout=25,
                              headers={'Authorization': 'Bearer ' + tok, 'PayPal-Request-Id': f'LF-{venta_id}-{uuid.uuid4().hex[:8]}'})
        except requests.RequestException:
            raise AppError('PASARELA_NO_DISPONIBLE', 'No se pudo contactar a PayPal. Intente más tarde o pague en efectivo.', 503)
        if r.status_code not in (200, 201):
            raise AppError('PASARELA_NO_DISPONIBLE', 'PayPal no pudo crear la orden de pago.', 503)
        d = r.json()
        link = next((x['href'] for x in d.get('links', []) if x.get('rel') in ('payer-action', 'approve')), None)
        if not link:
            raise AppError('PASARELA_NO_DISPONIBLE', 'PayPal no devolvió el enlace de aprobación.', 503)
        return {'id': d['id'], 'approve_url': link, 'usd': float(usd)}

    @staticmethod
    def capturar(order_id, monto_bob):
        """Cobra la orden ya aprobada por el cliente. Devuelve {'ok': bool, 'tx': id de la captura}."""
        if Config.PAYPAL_MODO == 'simulado':
            return {'ok': True, 'tx': 'SIM-' + uuid.uuid4().hex[:10].upper()}
        import requests
        tok = PayPalAdapter._token()
        try:
            r = requests.post(f'{PayPalAdapter._base()}/v2/checkout/orders/{order_id}/capture', timeout=25,
                              headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'}, data='{}')
        except requests.RequestException:
            raise AppError('PASARELA_NO_DISPONIBLE', 'No se pudo contactar a PayPal para confirmar el pago.', 503)
        d = r.json() if r.content else {}
        if r.status_code not in (200, 201) or d.get('status') != 'COMPLETED':
            return {'ok': False, 'tx': None, 'estado': d.get('status')}
        cap = (((d.get('purchase_units') or [{}])[0].get('payments') or {}).get('captures') or [{}])[0]
        valor = (cap.get('amount') or {}).get('value')
        if valor and abs(float(valor) - float(PayPalAdapter.usd(monto_bob))) > 0.01:
            return {'ok': False, 'tx': cap.get('id'), 'estado': 'MONTO_INCORRECTO'}
        return {'ok': True, 'tx': cap.get('id') or order_id}
