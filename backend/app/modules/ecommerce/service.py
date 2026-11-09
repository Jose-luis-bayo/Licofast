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


class PromocionService:
    @staticmethod
    def precio_efectivo(prod, promos):
        """Menor precio entre las promociones vigentes aplicables a un producto."""
        base, mejor, nombre = Decimal(prod['precio']), Decimal(prod['precio']), None
        for p in promos:
            aplica = (p['producto_id'] == prod['id']) or (p['categoria_id'] is not None and p['categoria_id'] == prod.get('categoria_id')) \
                or (p['producto_id'] is None and p['categoria_id'] is None)
            if not aplica:
                continue
            nuevo = base * (1 - Decimal(p['valor']) / 100) if p['tipo'] == 'porcentaje' else base - Decimal(p['valor'])
            nuevo = max(_q(nuevo), Decimal('0.00'))
            if nuevo < mejor:
                mejor, nombre = nuevo, p['nombre']
        return _q(mejor), nombre

    @staticmethod
    def _datos(d):
        tipo = d.get('tipo')
        if tipo not in ('porcentaje', 'monto'):
            raise invalido('El tipo debe ser «porcentaje» o «monto»')
        valor = v.decimal(d, 'valor', minimo=0.01)
        if tipo == 'porcentaje' and valor > 100:
            raise invalido('El porcentaje no puede superar 100')
        desde, hasta = v.fecha(d.get('desde'), 'desde'), v.fecha(d.get('hasta'), 'hasta')
        if hasta < desde:
            raise invalido('«hasta» no puede ser anterior a «desde»')
        return dict(nombre=v.texto(d, 'nombre', max_len=100), tipo=tipo, valor=valor, producto_id=v.entero(d, 'producto_id', 1, False),
                    categoria_id=v.entero(d, 'categoria_id', 1, False), desde=desde, hasta=hasta, activo=0 if str(d.get('activo', 1)) in ('0', 'False', 'false') else 1)

    @staticmethod
    def listar():
        with read() as cur:
            return [_num(r) for r in PR.todas(cur)]

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
            prods, promos = P.publico(cur, q, categoria_id), PR.vigentes(cur)
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
    def _crear(cur, *, cliente_id, cajero_id, tipo, canal, items, creador_id, entrega=None):
        lineas = InventarioService.reservar(cur, items)
        promos = PR.vigentes(cur)
        total, desc, detalle = Decimal('0'), Decimal('0'), []
        for p, cant in lineas:
            precio, _ = PromocionService.precio_efectivo(p, promos)
            total += precio * cant
            desc += (Decimal(p['precio']) - precio) * cant
            detalle.append((p, cant, precio))
        datos = dict(usuario_id=cliente_id, cajero_id=cajero_id, tipo_venta=tipo, canal=canal, total=_q(total), descuento=_q(desc), estado='pendiente', estado_pago='pendiente')
        if entrega:
            datos.update(direccion_entrega=entrega['direccion'], referencia_entrega=entrega['referencia'], telefono_contacto=entrega['telefono'])
        vid = V.insertar(cur, datos)
        for p, cant, precio in detalle:
            V.insertar_detalle(cur, vid, p['id'], cant, precio)
        InventarioService.descontar(cur, vid, lineas, creador_id)
        return vid, _q(total), _q(desc)

    @staticmethod
    def _entrega(d, telefono_defecto):
        direccion = v.texto(d, 'direccion_entrega', max_len=255)
        tel = v.texto(d, 'telefono_contacto', obligatorio=False, max_len=30) or telefono_defecto
        if not tel:
            raise invalido('El teléfono de contacto es obligatorio', {'campo': 'telefono_contacto'})
        return {'direccion': direccion, 'telefono': tel, 'referencia': v.texto(d, 'referencia_entrega', obligatorio=False, max_len=255)}

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
            promos, lineas, total, desc = PR.vigentes(cur), [], Decimal('0'), Decimal('0')
            for pid, cant in fusion.items():
                p = P.por_id(cur, pid)
                if not p or not p['activo']:
                    raise invalido(f'El producto {pid} no está disponible', codigo='PRODUCTO_NO_DISPONIBLE')
                precio, promo = PromocionService.precio_efectivo(p, promos)
                total += precio * cant
                desc += (Decimal(p['precio']) - precio) * cant
                lineas.append({'producto_id': pid, 'nombre': p['nombre'], 'cantidad': cant, 'precio_unitario': float(precio), 'subtotal': float(precio * cant),
                               'promocion': promo, 'stock_suficiente': p['stock'] >= cant})
        return {'lineas': lineas, 'total': float(_q(total)), 'descuento': float(_q(desc))}

    @staticmethod
    def crear_pedido(user, d, canal='web', cliente=None):
        """CU-E03: checkout de delivery. cliente=None → el propio usuario autenticado."""
        cli = cliente or user
        PedidoService._exigir_mayor(cli.get('fecha_nacimiento'))
        entrega = PedidoService._entrega(d, cli.get('telefono'))
        with transaction() as cur:
            vid, total, desc = PedidoService._crear(cur, cliente_id=cli['id'], cajero_id=user['id'] if cliente else None, tipo='delivery', canal=canal,
                                                    items=d.get('items') or [], creador_id=user['id'], entrega=entrega)
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
        if r == 'repartidor':
            return venta['tipo_venta'] == 'delivery' and venta['repartidor_id'] in (None, user['id'])
        return False

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
        return venta

    @staticmethod
    def listar(user, f, limit, offset):
        PedidoService.cancelar_vencidos()
        f = dict(f)
        if user['rol'] == 'cliente':
            f['usuario_id'] = user['id']
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
            hay = one(cur, "SELECT 1 AS x FROM ventas WHERE tipo_venta='delivery' AND estado='pendiente' AND estado_pago='pendiente' AND repartidor_id IS NULL "
                           "AND created_at < DATE_SUB(NOW(), INTERVAL %s MINUTE) LIMIT 1", (Config.PEDIDO_TTL_MIN,))
        if not hay:
            return 0
        n = 0
        with transaction() as cur:
            for r in V.delivery_vencidos(cur, Config.PEDIDO_TTL_MIN):
                PedidoService.cancelar_venta(cur, r['id'], 'Cancelado por falta de atención dentro del plazo', None)
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
            pendientes = one(cur, "SELECT COUNT(*) AS n FROM ventas WHERE tipo_venta='delivery' AND estado IN ('pendiente','en_camino')")['n']
        return {'hoy': {'ventas': hoy['ventas'], 'monto': float(hoy['monto'])}, 'por_estado': estados, 'cobros_hoy': [_num(m) for m in metodos],
                'top_productos': [_num(t) for t in top], 'stock_bajo': bajos, 'deliveries_abiertos': pendientes}
