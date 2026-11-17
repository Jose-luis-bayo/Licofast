"""Cupones y vales de descuento: códigos públicos, vales personales que da el administrador y recompensas automáticas
por cliente frecuente o antigüedad. Un cupón se canjea al crear el pedido (CU nuevo: «Aplicar cupón»)."""
import datetime
import secrets
from decimal import Decimal
from ...db import read, transaction, one, all_, run
from ...core.errors import conflicto, invalido, no_encontrado
from ...core.events import bus
from ...core import validators as v

# ---- Reglas de recompensa (se pueden ajustar aquí) ----
FRECUENTE = {'pedidos': 3, 'dias': 30, 'porcentaje': 10, 'validez_dias': 30}     # 3 pedidos entregados en 30 días → 10 %
ANTIGUEDAD = {'dias': 180, 'porcentaje': 5, 'validez_dias': 60}                    # cuenta de 6+ meses → 5 % cada semestre


def _q(x): return Decimal(x).quantize(Decimal('0.01'))


def _norm(codigo):
    c = (codigo or '').strip().upper().replace(' ', '')
    if not c:
        raise invalido('Escriba el código del cupón', {'campo': 'cupon'}, codigo='CUPON_INVALIDO')
    return c


class CuponRepository:
    @staticmethod
    def por_codigo(cur, codigo, lock=False):
        return one(cur, 'SELECT * FROM cupones WHERE codigo=%s' + (' FOR UPDATE' if lock else ''), (codigo,))

    @staticmethod
    def por_id(cur, cid): return one(cur, 'SELECT * FROM cupones WHERE id=%s', (cid,))

    @staticmethod
    def usos(cur, cid, uid=None):
        # un pedido cancelado/rechazado devuelve el uso del cupón
        w, a = "u.cupon_id=%s AND v.estado<>'no_entregado'", [cid]
        if uid:
            w += ' AND u.usuario_id=%s'; a.append(uid)
        return one(cur, f'SELECT COUNT(*) AS n FROM cupon_usos u JOIN ventas v ON v.id=u.venta_id WHERE {w}', a)['n']

    @staticmethod
    def registrar_uso(cur, cid, uid, vid, desc): run(cur, 'INSERT INTO cupon_usos(cupon_id,usuario_id,venta_id,descuento) VALUES(%s,%s,%s,%s)', (cid, uid, vid, desc))

    @staticmethod
    def insertar(cur, d):
        cols = list(d)
        return run(cur, f"INSERT INTO cupones({','.join(cols)}) VALUES({','.join(['%s'] * len(cols))})", list(d.values()))

    @staticmethod
    def actualizar(cur, cid, d): run(cur, f"UPDATE cupones SET {','.join(k + '=%s' for k in d)} WHERE id=%s", [*d.values(), cid])

    @staticmethod
    def listar(cur):
        return all_(cur, "SELECT c.*, CONCAT(u.nombre,' ',u.apellido) AS cliente, "
                         "(SELECT COUNT(*) FROM cupon_usos x JOIN ventas v ON v.id=x.venta_id WHERE x.cupon_id=c.id AND v.estado<>'no_entregado') AS usos "
                         "FROM cupones c LEFT JOIN usuarios u ON u.id=c.usuario_id ORDER BY c.id DESC LIMIT 300")

    @staticmethod
    def disponibles_para(cur, uid):
        return all_(cur, 'SELECT * FROM cupones WHERE activo=1 AND (usuario_id=%s OR usuario_id IS NULL) ORDER BY usuario_id IS NULL, id DESC', (uid,))

    @staticmethod
    def recompensa_existe(cur, uid, regla, periodo):
        return one(cur, 'SELECT 1 AS x FROM cupones WHERE usuario_id=%s AND regla=%s AND periodo=%s', (uid, regla, periodo))


def _num(c):
    out = dict(c)
    for k in ('valor', 'minimo_compra'):
        if out.get(k) is not None: out[k] = float(out[k])
    for k in ('vigente_desde', 'vigente_hasta', 'created_at'):
        if out.get(k) is not None: out[k] = str(out[k])
    return out


class CuponService:
    @staticmethod
    def _motivo_no_usable(cur, c, uid, base):
        """None si el cupón sirve para este cliente y esta compra; si no, el motivo en palabras."""
        ahora = datetime.datetime.now()
        if not c['activo']: return 'El cupón está desactivado'
        if c['usuario_id'] and c['usuario_id'] != uid: return 'Este cupón es personal de otro cliente'
        if c['vigente_desde'] and ahora < c['vigente_desde']: return f"El cupón empieza el {c['vigente_desde']:%d/%m/%Y}"
        if c['vigente_hasta'] and ahora > c['vigente_hasta']: return 'El cupón ya venció'
        if base is not None and base < c['minimo_compra']: return f"La compra mínima para este cupón es Bs {c['minimo_compra']:.2f}"
        if c['usos_max'] is not None and CuponRepository.usos(cur, c['id']) >= c['usos_max']: return 'El cupón ya alcanzó su límite de usos'
        if CuponRepository.usos(cur, c['id'], uid) >= c['usos_por_cliente']: return 'Ya usó este cupón'
        return None

    @staticmethod
    def descuento(c, base):
        d = base * Decimal(c['valor']) / 100 if c['tipo'] == 'porcentaje' else Decimal(c['valor'])
        return _q(min(d, base))

    @staticmethod
    def reservar(cur, codigo, uid, base):
        """Dentro de la transacción del pedido: valida con bloqueo y devuelve (cupón, descuento)."""
        c = CuponRepository.por_codigo(cur, _norm(codigo), lock=True)
        if not c:
            raise invalido('El cupón no existe', {'campo': 'cupon'}, codigo='CUPON_INVALIDO')
        motivo = CuponService._motivo_no_usable(cur, c, uid, Decimal(base))
        if motivo:
            raise invalido(motivo, {'campo': 'cupon'}, codigo='CUPON_INVALIDO')
        return c, CuponService.descuento(c, Decimal(base))

    @staticmethod
    def validar(user, d):
        """El cliente prueba un código con su carrito y ve cuánto descuenta, sin consumirlo."""
        from .service import PedidoService
        cot = PedidoService.cotizar(d.get('items'))
        base = _q(cot['total'])
        with read() as cur:
            c = CuponRepository.por_codigo(cur, _norm(d.get('codigo')))
            if not c:
                raise invalido('El cupón no existe', {'campo': 'cupon'}, codigo='CUPON_INVALIDO')
            motivo = CuponService._motivo_no_usable(cur, c, user['id'], base)
            if motivo:
                raise invalido(motivo, {'campo': 'cupon'}, codigo='CUPON_INVALIDO')
            desc = CuponService.descuento(c, base)
        return {'valido': True, 'codigo': c['codigo'], 'descripcion': c['descripcion'], 'descuento_cupon': float(desc), 'total_sin_cupon': float(base), 'total': float(base - desc)}

    @staticmethod
    def mis_cupones(user):
        with read() as cur:
            out = []
            for c in CuponRepository.disponibles_para(cur, user['id']):
                motivo = CuponService._motivo_no_usable(cur, c, user['id'], None)
                x = _num(c); x.update(usable=motivo is None, motivo=motivo, personal=bool(c['usuario_id']))
                for k in ('creado_por', 'usuario_id', 'periodo', 'regla'): x.pop(k, None)
                out.append(x)
        return out

    # ------------------------- Administración -------------------------
    @staticmethod
    def listar(user):
        with read() as cur:
            return [_num(c) for c in CuponRepository.listar(cur)]

    @staticmethod
    def _datos(d, parcial=False):
        out = {}
        if not parcial or 'tipo' in d:
            tipo = d.get('tipo')
            if tipo not in ('porcentaje', 'monto'):
                raise invalido('El tipo debe ser «porcentaje» o «monto»', {'campo': 'tipo'})
            out['tipo'] = tipo
        if not parcial or 'valor' in d:
            val = v.decimal(d, 'valor', 0.01)
            if (out.get('tipo') or d.get('tipo')) == 'porcentaje' and val > 100:
                raise invalido('Un porcentaje no puede pasar de 100', {'campo': 'valor'})
            out['valor'] = val
        if 'minimo_compra' in d: out['minimo_compra'] = v.decimal(d, 'minimo_compra', 0, obligatorio=False) or Decimal('0')
        if 'usos_max' in d: out['usos_max'] = v.entero(d, 'usos_max', 1, obligatorio=False)
        if 'usos_por_cliente' in d: out['usos_por_cliente'] = v.entero(d, 'usos_por_cliente', 1, obligatorio=False) or 1
        if 'descripcion' in d: out['descripcion'] = v.texto(d, 'descripcion', obligatorio=False, max_len=160)
        for campo in ('vigente_desde', 'vigente_hasta'):
            if campo in d:
                f = v.fecha(d[campo], campo) if d[campo] else None
                out[campo] = (datetime.datetime.combine(f, datetime.time(23, 59, 59) if campo == 'vigente_hasta' else datetime.time.min) if f else None)
        if out.get('vigente_desde') and out.get('vigente_hasta') and out['vigente_hasta'] < out['vigente_desde']:
            raise invalido('La fecha final no puede ser anterior a la inicial', {'campo': 'vigente_hasta'})
        return out

    @staticmethod
    def crear(user, d):
        codigo = _norm(d.get('codigo'))
        if len(codigo) > 30 or not codigo.replace('-', '').replace('_', '').isalnum():
            raise invalido('El código solo puede tener letras, números y guiones (máx. 30)', {'campo': 'codigo'})
        datos = CuponService._datos(d)
        datos.update(codigo=codigo, origen='manual', creado_por=user['id'])
        if d.get('usuario_id'):
            datos['usuario_id'] = v.entero(d, 'usuario_id', 1)
        with transaction() as cur:
            if CuponRepository.por_codigo(cur, codigo):
                raise conflicto('CODIGO_DUPLICADO', 'Ya existe un cupón con ese código')
            cid = CuponRepository.insertar(cur, datos)
        bus.publish('CuponCreado', usuario_id=user['id'], entidad='cupon', entidad_id=cid, detalle={'codigo': codigo})
        return {'id': cid, 'codigo': codigo}

    @staticmethod
    def editar(user, cid, d):
        with transaction() as cur:
            c = CuponRepository.por_id(cur, cid)
            if not c:
                raise no_encontrado('Cupón no encontrado')
            datos = CuponService._datos({**{'tipo': c['tipo']}, **d}, parcial=True) if any(k in d for k in ('valor', 'tipo', 'minimo_compra', 'usos_max', 'usos_por_cliente', 'descripcion', 'vigente_desde', 'vigente_hasta')) else {}
            if 'tipo' not in d: datos.pop('tipo', None)
            if 'activo' in d: datos['activo'] = 1 if d['activo'] else 0
            if datos: CuponRepository.actualizar(cur, cid, datos)
        bus.publish('CuponEditado', usuario_id=user['id'], entidad='cupon', entidad_id=cid, detalle={k: str(x) for k, x in datos.items()})
        return {'id': cid, 'mensaje': 'Cupón actualizado'}

    @staticmethod
    def _codigo_unico(cur, prefijo):
        for _ in range(10):
            cod = f'{prefijo}-{secrets.token_hex(3).upper()}'
            if not CuponRepository.por_codigo(cur, cod):
                return cod
        raise conflicto('CODIGO_DUPLICADO', 'No se pudo generar un código único')

    @staticmethod
    def asignar(user, d):
        """El administrador regala un vale personal a un cliente."""
        uid = v.entero(d, 'usuario_id', 1)
        datos = CuponService._datos(d)
        dias = v.entero(d, 'dias', 1, obligatorio=False) or 30
        with transaction() as cur:
            cli = one(cur, "SELECT id,nombre,apellido FROM usuarios WHERE id=%s AND rol='cliente' AND activo=1", (uid,))
            if not cli:
                raise no_encontrado('Cliente no encontrado')
            codigo = CuponService._codigo_unico(cur, 'VALE')
            datos.update(codigo=codigo, usuario_id=uid, usos_max=1, usos_por_cliente=1, origen='manual', creado_por=user['id'],
                         vigente_hasta=datetime.datetime.now() + datetime.timedelta(days=dias),
                         descripcion=datos.get('descripcion') or 'Vale de regalo de LicoFast')
            cid = CuponRepository.insertar(cur, datos)
        bus.publish('CuponAsignado', usuario_id=user['id'], entidad='cupon', entidad_id=cid, detalle={'cliente_id': uid, 'codigo': codigo})
        return {'id': cid, 'codigo': codigo, 'cliente': f"{cli['nombre']} {cli['apellido']}"}

    # ------------------------- Recompensas -------------------------
    @staticmethod
    def _emitir_recompensa(cur, uid, regla, periodo, porcentaje, validez, descripcion):
        if CuponRepository.recompensa_existe(cur, uid, regla, periodo):
            return None
        codigo = CuponService._codigo_unico(cur, 'GRACIAS' if regla == 'frecuente' else 'FIEL')
        CuponRepository.insertar(cur, dict(codigo=codigo, descripcion=descripcion, tipo='porcentaje', valor=porcentaje, minimo_compra=0, usos_max=1, usos_por_cliente=1,
                                           usuario_id=uid, vigente_hasta=datetime.datetime.now() + datetime.timedelta(days=validez), origen='recompensa', regla=regla, periodo=periodo))
        return codigo

    @staticmethod
    def evaluar_recompensas(uid):
        """Cliente frecuente (3 pedidos entregados en 30 días) o con antigüedad (6+ meses y al menos un pedido). Un premio por periodo."""
        nuevos, hoy = [], datetime.date.today()
        with transaction() as cur:
            cli = one(cur, "SELECT id, created_at FROM usuarios WHERE id=%s AND rol='cliente' AND activo=1", (uid,))
            if not cli:
                return nuevos
            n = one(cur, "SELECT COUNT(*) AS n FROM ventas WHERE usuario_id=%s AND tipo_venta='delivery' AND estado='entregada' AND created_at>=DATE_SUB(NOW(), INTERVAL %s DAY)", (uid, FRECUENTE['dias']))['n']
            if n >= FRECUENTE['pedidos']:
                c = CuponService._emitir_recompensa(cur, uid, 'frecuente', f'{hoy:%Y-%m}', FRECUENTE['porcentaje'], FRECUENTE['validez_dias'],
                                                    f"Gracias por ser cliente frecuente: {FRECUENTE['porcentaje']}% de descuento")
                if c: nuevos.append(c)
            total = one(cur, "SELECT COUNT(*) AS n FROM ventas WHERE usuario_id=%s AND tipo_venta='delivery' AND estado='entregada'", (uid,))['n']
            if total >= 1 and cli['created_at'] and (datetime.datetime.now() - cli['created_at']).days >= ANTIGUEDAD['dias']:
                c = CuponService._emitir_recompensa(cur, uid, 'antiguedad', f"{hoy.year}-S{1 if hoy.month <= 6 else 2}", ANTIGUEDAD['porcentaje'], ANTIGUEDAD['validez_dias'],
                                                    f"Gracias por tu fidelidad: {ANTIGUEDAD['porcentaje']}% de descuento")
                if c: nuevos.append(c)
        for c in nuevos:
            bus.publish('RecompensaEmitida', usuario_id=uid, entidad='cupon', entidad_id=uid, detalle={'codigo': c})
        return nuevos

    @staticmethod
    def generar_recompensas(user):
        with read() as cur:
            ids = [r['id'] for r in all_(cur, "SELECT DISTINCT usuario_id AS id FROM ventas WHERE tipo_venta='delivery' AND estado='entregada' AND usuario_id IS NOT NULL")]
        emitidos = []
        for uid in ids:
            emitidos += CuponService.evaluar_recompensas(uid)
        return {'revisados': len(ids), 'emitidos': emitidos, 'mensaje': f'{len(emitidos)} cupón(es) de recompensa emitido(s)'}
