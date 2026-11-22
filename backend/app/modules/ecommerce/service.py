"""Capa 3: reglas del módulo E-commerce (Service Layer)."""
import datetime
from decimal import Decimal, ROUND_HALF_UP
from ...config import Config
from ...db import read, transaction, one, all_
from ...core.errors import AppError, conflicto, invalido, no_encontrado, prohibido
from ...core.events import bus
from ...core import validators as v
from ..seguridad.facade import SeguridadFacade
from .estado import EstadoPedido
from .repository import (ProductoRepository as P, CategoriaRepository as C, PromocionRepository as PR,
                         VentaRepository as V, MovimientoRepository as M)

D2 = Decimal('0.01')


def _q(x): return Decimal(x).quantize(D2, rounding=ROUND_HALF_UP)


def _num(row):
    return {k: (float(x) if isinstance(x, Decimal) else x) for k, x in row.items()}


TIPOS_LINEA = ('porcentaje', 'monto', 'llevapaga', 'segunda')      # se aplican a cada producto del carrito
TIPOS_PEDIDO = ('pedido_pct', 'pedido_monto')                         # se aplican al total del pedido
TIPOS_PROMO = TIPOS_LINEA + TIPOS_PEDIDO
ZONA_BO = datetime.timezone(datetime.timedelta(hours=-4))             # Bolivia (UTC-4, sin horario de verano)


def ahora_local():
    return datetime.datetime.now(ZONA_BO).replace(tzinfo=None)


def _hhmm(t):
    if t is None:
        return None
    if isinstance(t, datetime.timedelta):
        m = int(t.total_seconds() // 60)
        return f'{m // 60:02d}:{m % 60:02d}'
    return str(t)[:5]


class PromocionService:
    @staticmethod
    def vigentes(cur):
        """Promociones activas hoy, en este día de la semana y a esta hora (hora de Bolivia)."""
        ahora = ahora_local()
        out = []
        for p in PR.vigentes(cur, ahora.date()):
            if p.get('dias') and str(ahora.isoweekday()) not in str(p['dias']).split(','):
                continue
            hd, hh = _hhmm(p.get('hora_desde')), _hhmm(p.get('hora_hasta'))
            if hd and hh:
                t = f'{ahora:%H:%M}'
                if not ((hd <= t <= hh) if hd <= hh else (t >= hd or t <= hh)):
                    continue
            out.append(p)
        return out

    @staticmethod
    def _aplica(p, prod):
        return (p['producto_id'] == prod['id']) or (p['categoria_id'] is not None and p['categoria_id'] == prod.get('categoria_id')) \
            or (p['producto_id'] is None and p['categoria_id'] is None)

    @staticmethod
    def precio_efectivo(prod, promos):
        """Precio unitario para el catálogo: la mejor promoción de porcentaje/monto. Las demás (2x1, por cantidad…) solo dan etiqueta."""
        base, mejor, nombre, etiqueta = Decimal(prod['precio']), Decimal(prod['precio']), None, None
        for p in promos:
            if p['tipo'] in TIPOS_PEDIDO or not PromocionService._aplica(p, prod):
                continue
            if p['tipo'] in ('porcentaje', 'monto') and (p.get('min_cantidad') or 1) <= 1:
                nuevo = base * (1 - Decimal(p['valor']) / 100) if p['tipo'] == 'porcentaje' else base - Decimal(p['valor'])
                nuevo = max(_q(nuevo), Decimal('0.00'))
                if nuevo < mejor:
                    mejor, nombre = nuevo, p['nombre']
            elif etiqueta is None:
                etiqueta = p['nombre']
        return _q(mejor), (nombre or etiqueta)

    @staticmethod
    def linea(prod, cant, promos):
        """Mejor promoción para esta cantidad de un producto → {precio_unitario, descuento (de la línea), nombre, total}."""
        base = Decimal(prod['precio'])
        mejor = {'precio_unitario': _q(base), 'descuento': Decimal('0.00'), 'nombre': None}
        mejor_total = _q(base) * cant
        for p in promos:
            if p['tipo'] not in TIPOS_LINEA or not PromocionService._aplica(p, prod) or cant < max(1, p.get('min_cantidad') or 1):
                continue
            pu, d, val = _q(base), Decimal('0.00'), Decimal(p['valor'] or 0)
            if p['tipo'] == 'porcentaje':
                pu = _q(base * (1 - val / 100))
            elif p['tipo'] == 'monto':
                pu = max(_q(base - val), Decimal('0.00'))
            elif p['tipo'] == 'llevapaga':
                n, m = p.get('lleva') or 0, p.get('paga') or 0
                if not (n >= 2 and 0 < m < n and cant >= n):
                    continue
                d = _q(base * ((cant // n) * (n - m)))
            elif p['tipo'] == 'segunda':
                if cant < 2:
                    continue
                d = _q(base * (cant // 2) * val / 100)
            total = pu * cant - d
            if total < mejor_total:
                mejor, mejor_total = {'precio_unitario': pu, 'descuento': d, 'nombre': p['nombre']}, total
        mejor['total'] = _q(mejor_total)
        return mejor

    @staticmethod
    def pedido(subtotal, promos):
        """Mejor promoción sobre el total del pedido → (descuento, nombre)."""
        mejor, nombre = Decimal('0.00'), None
        for p in promos:
            if p['tipo'] not in TIPOS_PEDIDO or subtotal < Decimal(p.get('minimo_pedido') or 0):
                continue
            d = _q(subtotal * Decimal(p['valor']) / 100) if p['tipo'] == 'pedido_pct' else _q(min(Decimal(p['valor']), subtotal))
            if d > mejor:
                mejor, nombre = d, p['nombre']
        return mejor, nombre

    @staticmethod
    def _datos(d):
        tipo = d.get('tipo')
        if tipo not in TIPOS_PROMO:
            raise invalido('Tipo de promoción no válido', {'campo': 'tipo'})
        valor, lleva, paga = Decimal('0'), None, None
        if tipo == 'llevapaga':
            lleva, paga = v.entero(d, 'lleva', 2), v.entero(d, 'paga', 1)
            if paga >= lleva:
                raise invalido('«Paga» debe ser menor que «Lleva» (ej.: lleva 2, paga 1)', {'campo': 'paga'})
        else:
            valor = v.decimal(d, 'valor', minimo=0.01)
            if tipo in ('porcentaje', 'segunda', 'pedido_pct') and valor > 100:
                raise invalido('El porcentaje no puede superar 100', {'campo': 'valor'})
        desde, hasta = v.fecha(d.get('desde'), 'desde'), v.fecha(d.get('hasta'), 'hasta')
        if hasta < desde:
            raise invalido('«hasta» no puede ser anterior a «desde»')
        dias = d.get('dias') or ''
        if isinstance(dias, list):
            dias = ','.join(str(x) for x in dias)
        dias = ','.join(sorted({x.strip() for x in str(dias).split(',') if x.strip()}))
        if dias and not all(x in '1234567' and len(x) == 1 for x in dias.split(',')):
            raise invalido('Los días deben ser del 1 (lunes) al 7 (domingo)', {'campo': 'dias'})
        hd, hh = (d.get('hora_desde') or None), (d.get('hora_hasta') or None)
        for h in (hd, hh):
            if h and not (len(str(h)) >= 5 and str(h)[2] == ':' and str(h)[:2].isdigit() and str(h)[3:5].isdigit() and int(str(h)[:2]) < 24 and int(str(h)[3:5]) < 60):
                raise invalido('El horario debe tener formato HH:MM', {'campo': 'hora_desde'})
        if bool(hd) != bool(hh):
            raise invalido('Indique la hora inicial y la final del horario (o ninguna)', {'campo': 'hora_desde'})
        es_pedido = tipo in TIPOS_PEDIDO
        return dict(nombre=v.texto(d, 'nombre', max_len=100), tipo=tipo, valor=valor, lleva=lleva, paga=paga,
                    min_cantidad=1 if es_pedido else (v.entero(d, 'min_cantidad', 1, False) or 1),
                    minimo_pedido=(v.decimal(d, 'minimo_pedido', 0, obligatorio=False) or Decimal('0')) if es_pedido else Decimal('0'),
                    dias=dias or None, hora_desde=(str(hd)[:5] if hd else None), hora_hasta=(str(hh)[:5] if hh else None),
                    descripcion=v.texto(d, 'descripcion', obligatorio=False, max_len=160),
                    producto_id=None if es_pedido else v.entero(d, 'producto_id', 1, False), categoria_id=None if es_pedido else v.entero(d, 'categoria_id', 1, False),
                    desde=desde, hasta=hasta, activo=0 if str(d.get('activo', 1)) in ('0', 'False', 'false') else 1)

    @staticmethod
    def activar(pid, activo, uid):
        with transaction() as cur:
            if not one(cur, 'SELECT id FROM promociones WHERE id=%s', (pid,)):
                raise no_encontrado('Promoción no encontrada')
            PR.activar(cur, pid, 1 if activo else 0)
        bus.publish('PromocionActivada' if activo else 'PromocionDesactivada', usuario_id=uid, entidad='promocion', entidad_id=pid, detalle=None)
        return {'mensaje': 'Promoción activada' if activo else 'Promoción desactivada'}

    @staticmethod
    def listar():
        with read() as cur:
            return [{**_num(r), 'hora_desde': _hhmm(r.get('hora_desde')), 'hora_hasta': _hhmm(r.get('hora_hasta'))} for r in PR.todas(cur)]

    @staticmethod
    def crear(d, uid):
        datos = PromocionService._datos(d)
        with transaction() as cur:
            pid = PR.insertar(cur, datos)
        bus.publish('PromocionCreada', usuario_id=uid, entidad='promocion', entidad_id=pid, detalle={'nombre': datos['nombre']})
        return {'id': pid}

    @staticmethod
    def actualizar(pid, d, uid):
        datos = PromocionService._datos(d)
        with transaction() as cur:
            PR.actualizar(cur, pid, datos)
        bus.publish('PromocionModificada', usuario_id=uid, entidad='promocion', entidad_id=pid, detalle={'nombre': datos['nombre']})
        return {'mensaje': 'Promoción actualizada'}

    @staticmethod
    def eliminar(pid, uid):
        with transaction() as cur:
            PR.eliminar(cur, pid)
        bus.publish('PromocionEliminada', usuario_id=uid, entidad='promocion', entidad_id=pid, detalle=None)
        return {'mensaje': 'Promoción eliminada'}


class CatalogoService:
    @staticmethod
    def listar_publico(q=None, categoria_id=None):
        with read() as cur:
            prods, promos = P.publico(cur, q, categoria_id), PromocionService.vigentes(cur)
        out = []
        for p in prods:
            precio, promo = PromocionService.precio_efectivo(p, promos)
            r = _num(p)
            r.update(precio_final=float(precio), promocion=promo, disponible=p['stock'] > 0)
            out.append(r)
        return out

    @staticmethod
    def listar_todos():
        with read() as cur:
            return [_num(p) for p in P.todos(cur)]

    @staticmethod
    def categorias():
        with read() as cur:
            return C.listar(cur)

    @staticmethod
    def _datos(d):
        return dict(nombre=v.texto(d, 'nombre', max_len=120), descripcion=v.texto(d, 'descripcion', obligatorio=False, max_len=2000) or '',
                    precio=v.decimal(d, 'precio', minimo=0), stock_minimo=v.entero(d, 'stock_minimo', 0, False) or 0,
                    imagen_url=v.texto(d, 'imagen_url', obligatorio=False, max_len=255), categoria_id=v.entero(d, 'categoria_id', 1, False),
                    activo=0 if str(d.get('activo', 1)) in ('0', 'False', 'false') else 1)

    @staticmethod
    def crear(d, uid):
        datos = CatalogoService._datos(d)
        datos['stock'] = v.entero(d, 'stock', 0, False) or 0
        with transaction() as cur:
            if datos['categoria_id'] and not C.existe(cur, datos['categoria_id']):
                raise invalido('La categoría no existe')
            pid = P.insertar(cur, datos)
            if datos['stock']:
                M.insertar(cur, pid, 'inicial', datos['stock'], 'Stock inicial al crear el producto', None, uid)
        bus.publish('ProductoCreado', usuario_id=uid, entidad='producto', entidad_id=pid, detalle={'nombre': datos['nombre'], 'precio': str(datos['precio'])})
        return {'id': pid, 'mensaje': 'Producto creado'}

    @staticmethod
    def actualizar(pid, d, uid):
        datos = CatalogoService._datos(d)
        with transaction() as cur:
            if not P.por_id(cur, pid):
                raise no_encontrado('Producto no encontrado')
            if datos['categoria_id'] and not C.existe(cur, datos['categoria_id']):
                raise invalido('La categoría no existe')
            P.actualizar(cur, pid, datos)
        bus.publish('ProductoModificado', usuario_id=uid, entidad='producto', entidad_id=pid, detalle={'precio': str(datos['precio']), 'activo': datos['activo']})
        return {'mensaje': 'Producto actualizado'}

    @staticmethod
    def eliminar(pid, uid):
        """Con ventas se desactiva (ADR-10); sin ventas se elimina."""
        with transaction() as cur:
            if not P.por_id(cur, pid):
                raise no_encontrado('Producto no encontrado')
            if P.tiene_ventas(cur, pid):
                P.desactivar(cur, pid); modo = 'desactivado'
            else:
                P.eliminar(cur, pid); modo = 'eliminado'
        bus.publish('ProductoEliminado', usuario_id=uid, entidad='producto', entidad_id=pid, detalle={'modo': modo})
        return {'modo': modo, 'mensaje': 'Producto eliminado' if modo == 'eliminado' else 'El producto tiene ventas; fue desactivado'}

    @staticmethod
    def categoria_crear(d, uid):
        nombre = v.texto(d, 'nombre', max_len=80)
        with transaction() as cur:
            try:
                cid = C.insertar(cur, nombre)
            except Exception:
                raise conflicto('CATEGORIA_DUPLICADA', 'Ya existe una categoría con ese nombre')
        bus.publish('CategoriaCreada', usuario_id=uid, entidad='categoria', entidad_id=cid, detalle={'nombre': nombre})
        return {'id': cid}

    @staticmethod
    def categoria_actualizar(cid, d, uid):
        nombre = v.texto(d, 'nombre', max_len=80)
        with transaction() as cur:
            C.actualizar(cur, cid, nombre, 0 if str(d.get('activo', 1)) in ('0', 'False', 'false') else 1)
        bus.publish('CategoriaModificada', usuario_id=uid, entidad='categoria', entidad_id=cid, detalle={'nombre': nombre})
        return {'mensaje': 'Categoría actualizada'}


class InventarioService:
    @staticmethod
    def reservar(cur, items):
        """Verifica stock con bloqueo de fila y devuelve [(producto, cantidad)]. No modifica nada."""
        fusion = {}
        for it in items:
            pid, cant = v.entero(it, 'producto_id', 1), v.entero(it, 'cantidad', 1)
            fusion[pid] = fusion.get(pid, 0) + cant
        if not fusion:
            raise invalido('Debe incluir al menos un producto', codigo='CARRITO_VACIO')
        if len(fusion) > 50:
            raise invalido('Demasiados productos distintos en una sola venta')
        filas = P.bloquear(cur, fusion.keys())
        faltan, ok = [], []
        for pid, cant in sorted(fusion.items()):
            p = filas.get(pid)
            if not p or not p['activo']:
                raise invalido(f'El producto {pid} no está disponible', {'producto_id': pid}, codigo='PRODUCTO_NO_DISPONIBLE')
            if p['stock'] < cant:
                faltan.append({'producto_id': pid, 'producto': p['nombre'], 'disponible': p['stock'], 'solicitado': cant})
            ok.append((p, cant))
        if faltan:
            nombres = ', '.join(f['producto'] for f in faltan)
            raise AppError('STOCK_INSUFICIENTE', f'No hay stock suficiente de: {nombres}', 422, faltan)
        return ok

    @staticmethod
    def descontar(cur, venta_id, lineas, usuario_id):
        for p, cant in lineas:
            P.sumar_stock(cur, p['id'], -cant)
            M.insertar(cur, p['id'], 'venta', -cant, f'Venta #{venta_id}', venta_id, usuario_id)

    @staticmethod
    def reponer(cur, venta_id, usuario_id, motivo):
        det = V.detalle(cur, venta_id)
        if not det:
            return
        P.bloquear(cur, [d['producto_id'] for d in det])
        for d in det:
            P.sumar_stock(cur, d['producto_id'], d['cantidad'])
            M.insertar(cur, d['producto_id'], 'reposicion', d['cantidad'], f'{motivo} (venta #{venta_id})', venta_id, usuario_id)

    @staticmethod
    def movimiento(d, uid):
        pid, tipo = v.entero(d, 'producto_id', 1), d.get('tipo')
        if tipo not in ('entrada', 'ajuste'):
            raise invalido('El tipo debe ser «entrada» o «ajuste»')
        cant = v.entero(d, 'cantidad')
        motivo = v.texto(d, 'motivo', obligatorio=(tipo == 'ajuste'), max_len=200)
        if tipo == 'entrada' and cant <= 0:
            raise invalido('Una entrada debe tener cantidad positiva')
        if cant == 0:
            raise invalido('La cantidad no puede ser cero')
        with transaction() as cur:
            p = P.bloquear(cur, [pid]).get(pid)
            if not p:
                raise no_encontrado('Producto no encontrado')
            if p['stock'] + cant < 0:
                raise AppError('STOCK_INSUFICIENTE', 'El ajuste dejaría el stock en negativo', 422, {'disponible': p['stock'], 'ajuste': cant})
            P.sumar_stock(cur, pid, cant)
            M.insertar(cur, pid, tipo, cant, motivo, None, uid)
            nuevo = p['stock'] + cant
        bus.publish('StockAjustado', usuario_id=uid, entidad='producto', entidad_id=pid, detalle={'tipo': tipo, 'cantidad': cant, 'stock': nuevo, 'motivo': motivo})
        return {'producto_id': pid, 'stock': nuevo, 'bajo_minimo': nuevo <= p['stock_minimo']}

    @staticmethod
    def movimientos(pid=None, limit=100):
        with read() as cur:
            return M.listar(cur, pid, min(limit, 500))

    @staticmethod
    def alertas():
        with read() as cur:
            return [_num(p) for p in P.alertas(cur)]


class PedidoService:
    @staticmethod
    def _crear(cur, *, cliente_id, cajero_id, tipo, canal, items, creador_id, entrega=None, estado_inicial=None, cupon=None, extra=None):
        lineas = InventarioService.reservar(cur, items)
        promos = PromocionService.vigentes(cur)
        total, desc, detalle = Decimal('0'), Decimal('0'), []
        for p, cant in lineas:
            ln = PromocionService.linea(p, cant, promos)
            total += ln['total']
            desc += (Decimal(p['precio']) - ln['precio_unitario']) * cant + ln['descuento']
            detalle.append((p, cant, ln['precio_unitario'], ln['descuento']))
        dped, _ = PromocionService.pedido(_q(total), promos)               # promoción sobre el total del pedido
        total, desc = total - dped, desc + dped
        cup, dcup = None, Decimal('0')
        if cupon and cliente_id and tipo == 'delivery':                  # el cupón se aplica sobre el total ya con promociones
            from .cupones import CuponService
            cup, dcup = CuponService.reservar(cur, cupon, cliente_id, total)
            total, desc = total - dcup, desc + dcup
        datos = dict(usuario_id=cliente_id, cajero_id=cajero_id, tipo_venta=tipo, canal=canal, total=_q(total), descuento=_q(desc), estado='pendiente', estado_pago='pendiente')
        if cup:
            datos['cupon_codigo'] = cup['codigo']
        if extra:
            datos.update(extra)
        if entrega:
            datos.update(direccion_entrega=entrega['direccion'], referencia_entrega=entrega['referencia'], telefono_contacto=entrega['telefono'],
                         lat_entrega=entrega['lat'], lng_entrega=entrega['lng'], metodo_pago=entrega['metodo_pago'])
            if estado_inicial:
                datos.update(estado=estado_inicial, confirmado_en=datetime.datetime.now(), confirmado_por=creador_id)
        vid = V.insertar(cur, datos)
        for p, cant, precio, dlinea in detalle:
            V.insertar_detalle(cur, vid, p['id'], cant, precio, dlinea)
        InventarioService.descontar(cur, vid, lineas, creador_id)
        if cup:
            from .cupones import CuponRepository
            CuponRepository.registrar_uso(cur, cup['id'], cliente_id, vid, _q(dcup))
        return vid, _q(total), _q(desc)

    @staticmethod
    def _entrega(d, telefono_defecto):
        direccion = v.texto(d, 'direccion_entrega', max_len=255)
        tel = v.texto(d, 'telefono_contacto', obligatorio=False, max_len=30) or telefono_defecto
        if not tel:
            raise invalido('El teléfono de contacto es obligatorio', {'campo': 'telefono_contacto'})
        metodo = d.get('metodo_pago') or 'efectivo'
        if metodo not in ('efectivo', 'qr', 'paypal'):
            raise invalido('El método de pago debe ser «efectivo», «qr» o «paypal»', {'campo': 'metodo_pago'})
        lat = lng = None
        if d.get('lat') not in (None, '') or d.get('lng') not in (None, ''):
            try:
                lat, lng = round(float(d.get('lat')), 6), round(float(d.get('lng')), 6)
            except (TypeError, ValueError):
                raise invalido('La ubicación debe tener latitud y longitud numéricas', {'campo': 'lat/lng'})
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise invalido('Coordenadas fuera de rango', {'campo': 'lat/lng'})
        return {'direccion': direccion, 'telefono': tel, 'referencia': v.texto(d, 'referencia_entrega', obligatorio=False, max_len=255),
                'metodo_pago': metodo, 'lat': lat, 'lng': lng}

    @staticmethod
    def _exigir_mayor(nacimiento):
        if not nacimiento:
            raise invalido('No se pudo verificar la mayoría de edad del cliente', codigo='EDAD_NO_VERIFICADA')
        if v.edad_exacta(nacimiento) < 18:
            raise invalido('La venta de alcohol está permitida solo a mayores de 18 años', codigo='MENOR_DE_EDAD')

    @staticmethod
    def cotizar(items):
        with read() as cur:
            fusion = {}
            for it in items or []:
                pid, cant = v.entero(it, 'producto_id', 1), v.entero(it, 'cantidad', 1)
                fusion[pid] = fusion.get(pid, 0) + cant
            if not fusion:
                raise invalido('El carrito está vacío', codigo='CARRITO_VACIO')
            promos, lineas, total, desc = PromocionService.vigentes(cur), [], Decimal('0'), Decimal('0')
            for pid, cant in fusion.items():
                p = P.por_id(cur, pid)
                if not p or not p['activo']:
                    raise invalido(f'El producto {pid} no está disponible', codigo='PRODUCTO_NO_DISPONIBLE')
                ln = PromocionService.linea(p, cant, promos)
                total += ln['total']
                desc += (Decimal(p['precio']) - ln['precio_unitario']) * cant + ln['descuento']
                lineas.append({'producto_id': pid, 'nombre': p['nombre'], 'cantidad': cant, 'precio_unitario': float(ln['precio_unitario']), 'subtotal': float(ln['total']),
                               'promocion': ln['nombre'], 'stock_suficiente': p['stock'] >= cant})
            dped, nped = PromocionService.pedido(_q(total), promos)
            total, desc = total - dped, desc + dped
        return {'lineas': lineas, 'total': float(_q(total)), 'descuento': float(_q(desc)), 'promocion_pedido': nped, 'descuento_pedido': float(dped)}

    @staticmethod
    def crear_pedido(user, d, canal='web', cliente=None):
        """CU-E03: checkout de delivery. cliente=None → el propio usuario autenticado."""
        cli = cliente or user
        PedidoService._exigir_mayor(cli.get('fecha_nacimiento'))
        entrega = PedidoService._entrega(d, cli.get('telefono'))
        with transaction() as cur:
            # un pedido cargado por el cajero (WhatsApp) ya fue revisado por él: pasa directo a bodega
            vid, total, desc = PedidoService._crear(cur, cliente_id=cli['id'], cajero_id=user['id'] if cliente else None, tipo='delivery', canal=canal,
                                                    items=d.get('items') or [], creador_id=user['id'], entrega=entrega, cupon=d.get('cupon'),
                                                    estado_inicial='confirmado' if (cliente and entrega['metodo_pago'] == 'efectivo') else None)
        bus.publish('PedidoCreado', usuario_id=user['id'], entidad='venta', entidad_id=vid, detalle={'total': str(total), 'canal': canal, 'cliente_id': cli['id']})
        return PedidoService.obtener(user, vid)

    @staticmethod
    def pedido_whatsapp(user, d):
        """CU-E11: el cajero carga un pedido recibido por WhatsApp a nombre de un cliente registrado."""
        cid = v.entero(d, 'cliente_id', 1)
        with read() as cur:
            cli = SeguridadFacade.cliente_por_id(cur, cid)
        if not cli:
            raise invalido('Seleccione un cliente registrado (se necesita verificar su edad)', codigo='CLIENTE_REQUERIDO')
        return PedidoService.crear_pedido(user, d, canal='whatsapp', cliente={'id': cli['id'], 'fecha_nacimiento': cli['fecha_nacimiento'], 'telefono': cli['telefono']})

    @staticmethod
    def venta_mostrador(user, d):
        """CU-E05: venta presencial. Efectivo se cobra en la misma transacción; QR queda pendiente y se inicia después."""
        from ..pagos.facade import PagosFacade
        metodo = d.get('metodo', 'efectivo')
        if metodo not in ('efectivo', 'qr'):
            raise invalido('El método debe ser «efectivo» o «qr»')
        cliente_id = v.entero(d, 'cliente_id', 1, False)
        with transaction() as cur:
            caja = PagosFacade.caja_abierta(cur, user['id'])
            if not caja:
                raise conflicto('CAJA_CERRADA', 'Debe abrir su caja antes de registrar ventas')
            if cliente_id:
                cli = SeguridadFacade.cliente_por_id(cur, cliente_id)
                if not cli:
                    raise invalido('El cliente indicado no existe o está inactivo')
                PedidoService._exigir_mayor(cli['fecha_nacimiento'])
            vid, total, desc = PedidoService._crear(cur, cliente_id=cliente_id, cajero_id=user['id'], tipo='mostrador', canal='mostrador',
                                                    items=d.get('items') or [], creador_id=user['id'])
            pago_id = PagosFacade.cobrar_efectivo_mostrador(cur, vid, total, caja['id'], user['id']) if metodo == 'efectivo' else None
        bus.publish('VentaRegistrada', usuario_id=user['id'], entidad='venta', entidad_id=vid, detalle={'total': str(total), 'metodo': metodo})
        pago = None
        if metodo == 'qr':
            pago = PagosFacade.iniciar_qr(vid, user['id'])
        r = PedidoService.obtener(user, vid)
        r['pago'] = pago
        return r

    @staticmethod
    def _puede_ver(user, venta):
        r = user['rol']
        if r in ('administrador', 'cajero'):
            return True
        if r == 'cliente':
            return venta['usuario_id'] == user['id']
        if r == 'empleado':
            return venta['tipo_venta'] in ('delivery', 'retiro')
        if r == 'repartidor':
            return venta['tipo_venta'] == 'delivery' and venta['repartidor_id'] == user['id']
        return False

    @staticmethod
    def _wa_url(texto):
        import urllib.parse
        return f'https://wa.me/{Config.WHATSAPP_NEGOCIO}?text=' + urllib.parse.quote(texto)

    @staticmethod
    def obtener(user, vid):
        from ..pagos.facade import PagosFacade
        with read() as cur:
            venta = V.por_id(cur, vid)
            if not venta or not PedidoService._puede_ver(user, venta):
                raise no_encontrado('Pedido no encontrado')   # no revela si existe (control de propiedad)
            venta = _num(venta)
            venta['items'] = [_num(i) for i in V.detalle(cur, vid)]
            venta['pago'] = PagosFacade.ultimo_pago(cur, vid)
            if user['rol'] == 'cliente' and venta['tipo_venta'] == 'delivery':
                # qué puede hacer el cliente: editar/cancelar solo antes de que caja lo confirme y sin pago recibido
                libre = venta['estado'] == 'pendiente' and venta['estado_pago'] == 'pendiente'
                venta['puede_editar'] = libre
                venta['puede_cancelar'] = libre and venta.get('metodo_pago') in ('qr', 'paypal')
                pago_recibido = one(cur, 'SELECT 1 AS x FROM pagos WHERE venta_id=%s AND confirmado_en IS NOT NULL LIMIT 1', (vid,))
                venta['devolucion_pendiente'] = bool(pago_recibido) and venta['estado'] == 'no_entregado'
                venta['whatsapp_url'] = PedidoService._wa_url(f'Hola, soy cliente de LicoFast. Pedido #{vid}: ' + (
                    'necesito la devolución de mi pago. Adjunto mi QR para que me devuelvan el dinero.' if venta['devolucion_pendiente'] or venta['estado_pago'] == 'pagado'
                    else 'necesito cancelarlo.'))
        return venta

    # ------------------------- Quiosco de autoservicio -------------------------
    @staticmethod
    def acceso_kiosko(vid):
        import hmac, hashlib
        return hmac.new(Config.JWT_SECRET.encode(), f'kiosko:{vid}'.encode(), hashlib.sha256).hexdigest()[:24]

    @staticmethod
    def _datos_factura(c):
        import re
        c = c if isinstance(c, dict) else {}
        nombre = v.texto(c, 'nombre', max_len=120)
        if len(nombre) < 3:
            raise invalido('Escriba su nombre completo', {'campo': 'nombre'})
        nit = re.sub(r'\s', '', v.texto(c, 'nit_ci', max_len=25))
        if not re.fullmatch(r'[0-9A-Za-z\-]{4,20}', nit):
            raise invalido('El NIT o CI debe tener entre 4 y 20 caracteres (solo letras, números y guion)', {'campo': 'nit_ci'})
        tel = re.sub(r'\D', '', v.texto(c, 'telefono', max_len=25))
        if len(tel) == 11 and tel.startswith('591'):
            tel = tel[3:]
        if not (len(tel) == 8 and tel[0] in '67'):
            raise invalido('Escriba un celular boliviano de 8 dígitos (empieza con 6 o 7) para enviarle la factura por WhatsApp', {'campo': 'telefono'})
        return nombre, nit.upper(), tel

    @staticmethod
    def crear_kiosko(d):
        """Pedido del quiosco: sin cuenta, se paga en la pantalla y se retira en bodega."""
        import secrets
        if d.get('mayor_edad') is not True:
            raise invalido('Debe confirmar que es mayor de 18 años para comprar alcohol', codigo='MENOR_DE_EDAD')
        metodo = d.get('metodo_pago')
        if metodo not in ('qr', 'tarjeta', 'paypal'):
            raise invalido('El método de pago debe ser «qr», «tarjeta» o «paypal»', {'campo': 'metodo_pago'})
        nombre, nit, tel = PedidoService._datos_factura(d.get('cliente'))
        with transaction() as cur:
            for _ in range(20):
                codigo = f'{secrets.randbelow(9000) + 1000}'
                if not V.codigo_retiro_en_uso(cur, codigo):
                    break
            extra = dict(metodo_pago=metodo, factura_nombre=nombre, factura_nit=nit, factura_telefono=tel, telefono_contacto=tel, codigo_retiro=codigo)
            vid, total, _ = PedidoService._crear(cur, cliente_id=None, cajero_id=None, tipo='retiro', canal='kiosko', items=d.get('items'), creador_id=None, extra=extra)
        bus.publish('PedidoKiosko', usuario_id=None, entidad='venta', entidad_id=vid, detalle={'total': str(total), 'metodo': metodo})
        return PedidoService.obtener_kiosko(vid)

    @staticmethod
    def obtener_kiosko(vid):
        from ..pagos.facade import PagosFacade
        PedidoService.cancelar_vencidos()
        with read() as cur:
            venta = V.por_id(cur, vid)
            if not venta or venta['tipo_venta'] != 'retiro':
                raise no_encontrado('Pedido no encontrado')
            r = {k: venta[k] for k in ('id', 'total', 'descuento', 'estado', 'estado_pago', 'metodo_pago', 'codigo_retiro', 'created_at')}
            r = _num(r)
            r['items'] = [_num(i) for i in V.detalle(cur, vid)]
            r['pago'] = PagosFacade.ultimo_pago(cur, vid)
        r['acceso'] = PedidoService.acceso_kiosko(vid)
        return r

    @staticmethod
    def comprobante_kiosko(vid, token):
        import hmac
        from ..kiosko.pdf import comprobante_pdf
        if not hmac.compare_digest(str(token), PedidoService.acceso_kiosko(vid)):
            raise no_encontrado('Comprobante no encontrado')
        with read() as cur:
            venta = V.por_id(cur, vid)
            if not venta or venta['tipo_venta'] != 'retiro':
                raise no_encontrado('Comprobante no encontrado')
            if venta['estado_pago'] != 'pagado':
                raise conflicto('SIN_PAGO', 'El comprobante estará disponible cuando el pedido esté pagado')
            items = [_num(i) for i in V.detalle(cur, vid)]
            comp = one(cur, 'SELECT numero FROM comprobantes WHERE venta_id=%s ORDER BY id DESC LIMIT 1', (vid,))
        return comprobante_pdf(_num(dict(venta)), items, comp['numero'] if comp else None)

    @staticmethod
    def cancelar_kiosko(vid):
        from ..pagos.facade import PagosFacade
        with transaction() as cur:
            venta = V.bloquear(cur, vid)
            if not venta or venta['tipo_venta'] != 'retiro':
                raise no_encontrado('Pedido no encontrado')
            if venta['estado'] != 'pendiente' or venta['estado_pago'] != 'pendiente':
                raise conflicto('NO_CANCELABLE', 'El pedido ya fue pagado o procesado; consulte en bodega')
            PagosFacade.anular_pagos_de_venta(cur, vid, 'Cancelado en el quiosco')
            PedidoService.cancelar_venta(cur, vid, 'Cancelado en el quiosco por el cliente', None)
        bus.publish('PedidoCancelado', usuario_id=None, entidad='venta', entidad_id=vid, detalle={'por': 'quiosco'})
        return {'mensaje': 'Pedido cancelado'}

    @staticmethod
    def _propio_delivery(cur, user, vid):
        venta = V.bloquear(cur, vid)
        if not venta or venta['usuario_id'] != user['id'] or venta['tipo_venta'] != 'delivery':
            raise no_encontrado('Pedido no encontrado')
        return venta

    @staticmethod
    def cancelar_cliente(user, vid):
        """El cliente solo cancela un pedido de pago en línea (QR/PayPal) que aún no pagó y que caja no confirmó.
        Si ya pagó, o es en efectivo, debe hablar con el cajero por WhatsApp (la devolución se hace por QR, fuera del sistema)."""
        from ..pagos.facade import PagosFacade
        with transaction() as cur:
            venta = PedidoService._propio_delivery(cur, user, vid)
            wa = PedidoService._wa_url(f'Hola, soy cliente de LicoFast. Pedido #{vid}: necesito cancelarlo / la devolución de mi pago. Adjunto mi QR.')
            if venta['estado'] in ('entregada', 'no_entregado'):
                raise conflicto('PEDIDO_YA_PROCESADO', 'El pedido ya fue procesado')
            if venta['estado'] != 'pendiente' or venta['estado_pago'] == 'pagado':
                raise conflicto('NO_CANCELABLE', 'Este pedido ya no se puede cancelar desde la app. Escriba por WhatsApp al cajero y envíe su QR si necesita la devolución del dinero.', {'whatsapp_url': wa})
            if venta.get('metodo_pago') not in ('qr', 'paypal'):
                raise conflicto('NO_CANCELABLE', 'Un pedido en efectivo no se cancela desde la app. Si se equivocó, escriba por WhatsApp al cajero.', {'whatsapp_url': wa})
            PagosFacade.anular_pagos_de_venta(cur, vid, 'Cancelado por el cliente')
            PedidoService.cancelar_venta(cur, vid, 'Cancelado por el cliente', user['id'])
        bus.publish('PedidoCancelado', usuario_id=user['id'], entidad='venta', entidad_id=vid, detalle={'por': 'cliente'})
        return {'mensaje': 'Pedido cancelado'}

    @staticmethod
    def editar(user, vid, d):
        """El cliente corrige su pedido mientras no esté pagado ni confirmado: se anula el anterior y se crea uno nuevo
        con los mismos datos de entrega (el stock se repone y se vuelve a reservar, y el cupón se vuelve a validar)."""
        from ..pagos.facade import PagosFacade
        if not d.get('items'):
            raise invalido('El pedido debe tener al menos un producto', {'campo': 'items'})
        PedidoService._exigir_mayor(user.get('fecha_nacimiento'))
        with transaction() as cur:
            venta = PedidoService._propio_delivery(cur, user, vid)
            if venta['estado'] != 'pendiente' or venta['estado_pago'] != 'pendiente':
                raise conflicto('NO_EDITABLE', 'Solo se puede editar un pedido que aún no fue pagado ni confirmado por caja')
            base = {'direccion_entrega': venta['direccion_entrega'], 'telefono_contacto': venta['telefono_contacto'], 'referencia_entrega': venta.get('referencia_entrega'),
                    'metodo_pago': venta.get('metodo_pago') or 'efectivo', 'lat': venta.get('lat_entrega'), 'lng': venta.get('lng_entrega')}
            base.update({k: d[k] for k in base if k in d})
            entrega = PedidoService._entrega(base, user.get('telefono'))
            cupon = d['cupon'] if 'cupon' in d else venta.get('cupon_codigo')
            PagosFacade.anular_pagos_de_venta(cur, vid, 'Pedido editado por el cliente')
            PedidoService.cancelar_venta(cur, vid, 'Reemplazado: el cliente editó el pedido', user['id'])
            nuevo, total, _ = PedidoService._crear(cur, cliente_id=user['id'], cajero_id=None, tipo='delivery', canal=venta.get('canal') or 'web', items=d['items'],
                                                   creador_id=user['id'], entrega=entrega, cupon=cupon or None, estado_inicial=None)
        bus.publish('PedidoEditado', usuario_id=user['id'], entidad='venta', entidad_id=nuevo, detalle={'reemplaza': vid, 'total': str(total)})
        return PedidoService.obtener(user, nuevo)

    @staticmethod
    def listar(user, f, limit, offset):
        PedidoService.cancelar_vencidos()
        f = dict(f)
        if user['rol'] == 'cliente':
            f['usuario_id'] = user['id']
        elif user['rol'] == 'empleado':
            f['tipo'] = 'delivery'
        elif user['rol'] == 'cajero' and f.get('alcance') != 'todos':
            f['cajero_id'] = user['id']
        with read() as cur:
            total, filas = V.listar(cur, f, limit, offset)
        return {'total': total, 'items': [_num(x) for x in filas]}

    # ---- operaciones internas para otros módulos (vía fachada) ----
    @staticmethod
    def marcar_pagada(cur, vid):
        venta = V.bloquear(cur, vid)
        if not venta:
            raise no_encontrado('Venta no encontrada')
        if venta['estado_pago'] == 'pagado':
            return venta
        EstadoPedido.validar_pago(venta['estado_pago'], 'pagado')
        campos = {'estado_pago': 'pagado', 'monto_cobrado': venta['total']}
        if venta['tipo_venta'] == 'mostrador':
            EstadoPedido.validar(venta['estado'], 'pagada', 'mostrador')
            campos['estado'] = 'pagada'
        elif venta['tipo_venta'] == 'retiro' and venta['estado'] == 'pendiente':
            campos.update(estado='confirmado', confirmado_en=datetime.datetime.now())    # el quiosco cobra en línea: pasa directo a bodega, sin caja
        V.actualizar(cur, vid, campos)
        return venta

    @staticmethod
    def cancelar_venta(cur, vid, motivo, usuario_id):
        venta = V.bloquear(cur, vid)
        if not venta:
            raise no_encontrado('Venta no encontrada')
        EstadoPedido.validar(venta['estado'], 'no_entregado', venta['tipo_venta'])
        InventarioService.reponer(cur, vid, usuario_id, 'Cancelación')
        V.actualizar(cur, vid, {'estado': 'no_entregado', 'estado_pago': 'anulado', 'monto_cobrado': 0, 'observacion_entrega': motivo[:255], 'fecha_entrega': datetime.datetime.now()})
        return venta

    @staticmethod
    def cancelar_vencidos():
        """Libera el stock de pedidos delivery sin atender pasado el plazo (H-08)."""
        with read() as cur:
            hay = one(cur, "SELECT 1 AS x FROM ventas WHERE estado='pendiente' AND estado_pago='pendiente' AND ("
                           "(tipo_venta='delivery' AND repartidor_id IS NULL AND created_at < DATE_SUB(NOW(), INTERVAL %s MINUTE)) OR "
                           "(tipo_venta='retiro' AND created_at < DATE_SUB(NOW(), INTERVAL %s MINUTE))) LIMIT 1", (Config.PEDIDO_TTL_MIN, Config.KIOSKO_TTL_MIN))
        if not hay:
            return 0
        from ..pagos.facade import PagosFacade
        n = 0
        with transaction() as cur:
            for r in V.delivery_vencidos(cur, Config.PEDIDO_TTL_MIN):
                PedidoService.cancelar_venta(cur, r['id'], 'Cancelado por falta de atención dentro del plazo', None)
                n += 1
            for r in V.retiro_vencidos(cur, Config.KIOSKO_TTL_MIN):
                PagosFacade.anular_pagos_de_venta(cur, r['id'], 'Pedido de quiosco sin pagar a tiempo')
                PedidoService.cancelar_venta(cur, r['id'], 'Quiosco: no se pagó a tiempo', None)
                n += 1
        if n:
            bus.publish('PedidosVencidos', usuario_id=None, entidad='venta', entidad_id=None, detalle={'cancelados': n})
        return n

    @staticmethod
    def al_confirmar_pago(venta_id, **_):
        with transaction() as cur:
            PedidoService.marcar_pagada(cur, venta_id)


class ReporteService:
    @staticmethod
    def resumen():
        with read() as cur:
            hoy = one(cur, "SELECT COUNT(*) AS ventas, COALESCE(SUM(total),0) AS monto FROM ventas WHERE estado_pago='pagado' AND DATE(created_at)=CURDATE()")
            estados = {r['estado']: r['n'] for r in all_(cur, 'SELECT estado, COUNT(*) AS n FROM ventas GROUP BY estado')}
            metodos = all_(cur, "SELECT metodo, COUNT(*) AS n, COALESCE(SUM(monto),0) AS monto FROM pagos WHERE estado='confirmado' AND DATE(created_at)=CURDATE() GROUP BY metodo")
            top = all_(cur, "SELECT p.nombre, SUM(d.cantidad) AS unidades FROM detalle_venta d JOIN ventas v ON v.id=d.venta_id JOIN productos p ON p.id=d.producto_id "
                                                                      "WHERE v.estado_pago='pagado' AND DATE(v.created_at)=CURDATE() GROUP BY p.id,p.nombre ORDER BY unidades DESC LIMIT 5")
            bajos = one(cur, 'SELECT COUNT(*) AS n FROM productos WHERE activo=1 AND stock<=stock_minimo')['n']
            pendientes = one(cur, "SELECT COUNT(*) AS n FROM ventas WHERE tipo_venta='delivery' AND estado IN ('pendiente','confirmado','preparado','en_camino')")['n']
        return {'hoy': {'ventas': hoy['ventas'], 'monto': float(hoy['monto'])}, 'por_estado': estados, 'cobros_hoy': [_num(m) for m in metodos],
                'top_productos': [_num(t) for t in top], 'stock_bajo': bajos, 'deliveries_abiertos': pendientes}
