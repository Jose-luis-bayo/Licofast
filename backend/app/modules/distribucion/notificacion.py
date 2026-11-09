"""NotificacionService: avisa al cliente por WhatsApp (modo simulado: registra el mensaje y arma el enlace wa.me).
Para producción se reemplaza WhatsAppClient.enviar por una llamada a la WhatsApp Business Cloud API."""
import datetime
import logging
import re
from urllib.parse import quote
from ...config import BASE
from ...core.events import bus

log = logging.getLogger('licofast.whatsapp')
LOG_DIR = BASE / 'logs'


class WhatsAppClient:
    @staticmethod
    def normalizar_telefono(telefono):
        tel = re.sub(r'\D', '', str(telefono or ''))
        if len(tel) == 8 and tel.startswith(('6', '7')):
            tel = '591' + tel
        return tel

    @staticmethod
    def enviar(telefono, mensaje):
        tel = WhatsAppClient.normalizar_telefono(telefono)
        if not tel:
            return None
        LOG_DIR.mkdir(exist_ok=True)
        with open(LOG_DIR / 'whatsapp.log', 'a', encoding='utf-8') as f:
            f.write(f'{datetime.datetime.now():%Y-%m-%d %H:%M:%S} [SIMULADO] +{tel}:\n{mensaje}\n{"-"*50}\n')
        return f'https://wa.me/{tel}?text={quote(mensaje)}'


class NotificacionService:
    @staticmethod
    def en_camino(entidad_id=None, telefono=None, items=None, total=None, estado_pago=None, direccion=None, **_):
        lineas = [
            "🍾 *LicoFast - Su pedido va en camino* 🛵",
            f"¡Hola! Su pedido #{entidad_id} ya salió con nuestro repartidor hacia su dirección."
        ]
        if direccion:
            lineas.append(f"📍 *Dirección de entrega:* {direccion}")
        if items:
            lineas.append("\n📋 *Detalle de lo que pidió:*")
            for i in items:
                cant = i.get('cantidad', 1)
                nom = i.get('nombre', 'Producto')
                subt = i.get('subtotal') or (float(i.get('precio_unitario', 0)) * cant)
                lineas.append(f" • {cant} × {nom} (Bs {float(subt):.2f})")
        if total is not None:
            if estado_pago == 'pagado':
                lineas.append(f"\n💰 *Total:* Bs {float(total):.2f} (✅ Ya pagado)")
            else:
                lineas.append(f"\n💰 *Total a pagar:* Bs {float(total):.2f} (💵 en efectivo al recibir)")
        lineas.append("\nPor favor tenga listo su documento de identidad (mayores de 18 años). ¡Muchas gracias por su preferencia!")
        msg = "\n".join(lineas)
        return WhatsAppClient.enviar(telefono, msg)

    @staticmethod
    def en_destino(entidad_id=None, telefono=None, total=None, estado_pago=None, **_):
        lineas = [
            "🍾 *LicoFast - ¡Su repartidor ha llegado!* 📍",
            f"¡Hola! Nuestro repartidor ya se encuentra en su ubicación afuera con su pedido #{entidad_id}."
        ]
        if estado_pago == 'pagado':
            lineas.append("✅ *Estado:* Ya pagado. Solo debe recibirlo.")
        elif total is not None:
            lineas.append(f"💵 *Monto a cancelar en efectivo:* Bs {float(total):.2f}")
        lineas.append("Por favor salga a recibir su pedido con su documento de identidad. ¡Muchas gracias!")
        msg = "\n".join(lineas)
        return WhatsAppClient.enviar(telefono, msg)

    @staticmethod
    def entregado(entidad_id=None, telefono=None, **_):
        return WhatsAppClient.enviar(telefono, f'🍾 LicoFast: Su pedido #{entidad_id} fue entregado con éxito. ¡Gracias por su compra!')

    @staticmethod
    def no_entregado(entidad_id=None, telefono=None, **_):
        return WhatsAppClient.enviar(telefono, f'⚠️ LicoFast: No pudimos entregar su pedido #{entidad_id}. Comuníquese con nosotros para reprogramar la entrega.')


bus.subscribe('PedidoEnCamino', NotificacionService.en_camino)
bus.subscribe('PedidoEnDestino', NotificacionService.en_destino)
bus.subscribe('PedidoEntregado', NotificacionService.entregado)
bus.subscribe('PedidoNoEntregado', NotificacionService.no_entregado)
