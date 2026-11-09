"""Pruebas de los escenarios de calidad del SDD (sección 7.15) y de los hallazgos de 7.17."""
import json
import threading
import jwt
import pytest
from app.config import Config
from app.core.security import firmar_hmac
from .conftest import login, sql


def nuevo_producto(c, H, stock, precio=10, nombre='Producto prueba'):
    r = c.post('/api/v1/productos', json={'nombre': nombre, 'precio': precio, 'stock': stock, 'stock_minimo': 1}, headers=H['admin_api'])
    assert r.status_code == 201, r.get_json()
    return r.get_json()['id']


def stock_de(pid): return sql('SELECT stock FROM productos WHERE id=%s', (pid,))[0]['stock']


def pedido(c, H, pid, cant=1, user='cliente1', **extra):
    body = {'items': [{'producto_id': pid, 'cantidad': cant}], 'direccion_entrega': 'Calle Bolívar 123', 'telefono_contacto': '70000010', **extra}
    return c.post('/api/v1/pedidos', json=body, headers=H[user])


# ------------------------------------------------------------------ Seguridad
def test_login_y_token_firmado(c):
    r = c.post('/api/v1/auth/login', json={'usuario': 'cajero1', 'password': 'Admin1234'})
    d = r.get_json()
    assert r.status_code == 200 and 'password' not in d['usuario']
    datos = jwt.decode(d['token'], Config.JWT_SECRET, algorithms=['HS256'])
    assert datos['rol'] == 'cajero' and 'exp' in datos and 'jti' in datos


def test_EC1_token_manipulado_es_rechazado(c, H):
    falso = jwt.encode({'sub': '5', 'rol': 'administrador', 'exp': 9999999999}, 'otro-secreto', algorithm='HS256')
    assert c.get('/api/v1/usuarios', headers={'Authorization': 'Bearer ' + falso}).status_code == 401
    assert c.get('/api/v1/usuarios', headers={'Authorization': 'Bearer 1|administrador'}).status_code == 401   # token del prototipo (H-01)
    assert c.get('/api/v1/usuarios').status_code == 401


def test_rbac_y_propiedad(c, H):
    assert c.get('/api/v1/usuarios', headers=H['cliente1']).status_code == 403
    assert c.post('/api/v1/productos', json={}, headers=H['cajero1']).status_code == 403          # H-10: el cajero ya no mantiene el catálogo
    assert c.delete('/api/v1/productos/1', headers=H['cajero1']).status_code == 403
    assert c.get('/api/v1/auditoria', headers=H['repartidor1']).status_code == 403


def test_login_incorrecto_generico_y_bloqueo(c, H):
    c.post('/api/v1/usuarios', json={'nombre': 'Blo', 'apellido': 'Queo', 'ci': 'BLQ-1', 'usuario': 'bloqueable', 'password': 'Correcta123', 'rol': 'cajero'}, headers=H['admin_api'])
    msgs = set()
    for _ in range(5):
        r = c.post('/api/v1/auth/login', json={'usuario': 'bloqueable', 'password': 'mala'})
        assert r.status_code == 401
        msgs.add(r.get_json()['error']['mensaje'])
    r = c.post('/api/v1/auth/login', json={'usuario': 'noexiste', 'password': 'mala'})
    msgs.add(r.get_json()['error']['mensaje'])
    assert len(msgs) == 1                                             # mismo mensaje exista o no la cuenta
    r = c.post('/api/v1/auth/login', json={'usuario': 'bloqueable', 'password': 'Correcta123'})
    assert r.status_code == 423 and r.get_json()['error']['codigo'] == 'CUENTA_BLOQUEADA'


def test_registro_edad_exacta_y_duplicados(c):
    base = {'nombre': 'Nuevo', 'apellido': 'Cliente', 'ci': 'REG-1', 'usuario': 'nuevo1', 'password': 'Clave12345', 'terminos': True, 'fecha_nacimiento': '2010-01-01'}
    r = c.post('/api/v1/auth/register', json=base)
    assert r.status_code == 422 and r.get_json()['error']['codigo'] == 'MENOR_DE_EDAD'
    base['fecha_nacimiento'] = '1990-05-05'
    assert c.post('/api/v1/auth/register', json=base).status_code == 201
    assert c.post('/api/v1/auth/register', json=base).status_code == 409
    assert c.post('/api/v1/auth/register', json={**base, 'ci': 'REG-2', 'usuario': 'nuevo2', 'password': 'corta'}).status_code == 422
    assert c.post('/api/v1/auth/register', json={**base, 'ci': 'REG-3', 'usuario': 'nuevo3', 'terminos': False}).status_code == 422


def test_admin_no_crea_usuario_sin_password(c, H):
    r = c.post('/api/v1/usuarios', json={'nombre': 'A', 'apellido': 'B', 'ci': 'X-1', 'usuario': 'sinpass', 'rol': 'cajero'}, headers=H['admin_api'])
    assert r.status_code == 422                                       # H-06: sin contraseña por defecto


def test_logout_invalida_token(c):
    h = login(c, 'bodega1')
    assert c.get('/api/v1/auth/me', headers=h).status_code == 200
    assert c.post('/api/v1/auth/logout', headers=h).status_code == 200
    assert c.get('/api/v1/auth/me', headers=h).status_code == 401


def test_baja_logica_con_historial(c, H):
    r = c.delete('/api/v1/usuarios/5', headers=H['admin_api'])         # cliente1 con pedidos (o sin): el servicio decide
    assert r.status_code == 200 and r.get_json()['modo'] in ('eliminado', 'desactivado')
    assert c.delete('/api/v1/usuarios/1', headers=H['admin_api']).status_code == 409   # no puede borrarse a sí mismo
    sql("INSERT IGNORE INTO usuarios(id,nombre,apellido,ci,fecha_nacimiento,edad,usuario,password,rol,activo) SELECT 5,'Ana','Rojas','CLIE-001','1995-03-10',31,'cliente1',password,'cliente',1 FROM usuarios WHERE id=1")


# ------------------------------------------------------------------ E-commerce
def test_catalogo_publico_con_promocion(c):
    prods = c.get('/api/v1/productos').get_json()
    vino = next(p for p in prods if p['nombre'].startswith('Vino tinto'))
    assert vino['precio_final'] == pytest.approx(54.0) and vino['promocion']
    assert next(p for p in prods if p['nombre'].startswith('Ron'))['precio_final'] == 45.0
    assert c.get('/api/v1/productos?todos=1').status_code == 403


def test_checkout_descuenta_stock_y_aplica_promocion(c, H):
    pid = nuevo_producto(c, H, 10, 100)
    r = pedido(c, H, pid, 3)
    d = r.get_json()
    assert r.status_code == 201 and d['total'] == 300 and d['estado'] == 'pendiente' and d['estado_pago'] == 'pendiente' and d['tipo_venta'] == 'delivery'
    assert stock_de(pid) == 7
    r = pedido(c, H, 5, 1)                                            # vino tinto con -10 %
    assert r.get_json()['total'] == 54.0 and r.get_json()['descuento'] == 6.0


def test_checkout_ignora_cliente_id_enviado_por_el_cliente(c, H):
    pid = nuevo_producto(c, H, 5)
    r = pedido(c, H, pid, 1, cliente_id=1)                             # H-02
    assert r.get_json()['usuario_id'] == 5


def test_stock_insuficiente_revierte_todo(c, H):
    a, b = nuevo_producto(c, H, 5, nombre='A'), nuevo_producto(c, H, 1, nombre='B')
    r = c.post('/api/v1/pedidos', json={'items': [{'producto_id': a, 'cantidad': 2}, {'producto_id': b, 'cantidad': 2}], 'direccion_entrega': 'x', 'telefono_contacto': '1'}, headers=H['cliente1'])
    assert r.status_code == 422 and r.get_json()['error']['codigo'] == 'STOCK_INSUFICIENTE'
    assert stock_de(a) == 5 and stock_de(b) == 1


def test_menor_de_edad_no_compra(c, H):
    sql("UPDATE usuarios SET fecha_nacimiento='2012-01-01' WHERE id=5")
    try:
        pid = nuevo_producto(c, H, 5)
        r = pedido(c, H, pid)
        assert r.status_code == 422 and r.get_json()['error']['codigo'] == 'MENOR_DE_EDAD'
        assert stock_de(pid) == 5
    finally:
        sql("UPDATE usuarios SET fecha_nacimiento='1995-03-10' WHERE id=5")


def test_EC2_ultima_botella_concurrente(app, H):
    cl = app.test_client()
    pid = nuevo_producto(cl, H, 1)
    res = []

    def comprar():
        res.append(pedido(app.test_client(), H, pid).status_code)
    hilos = [threading.Thread(target=comprar) for _ in range(4)]
    [h.start() for h in hilos]; [h.join() for h in hilos]
    assert sorted(res) == [201, 422, 422, 422]
    assert stock_de(pid) == 0


def test_propiedad_de_pedidos(c, H):
    pid = nuevo_producto(c, H, 5)
    vid = pedido(c, H, pid).get_json()['id']
    c.post('/api/v1/auth/register', json={'nombre': 'Otro', 'apellido': 'Cliente', 'ci': 'OTR-1', 'usuario': 'otro_cli', 'password': 'Clave12345', 'terminos': True, 'fecha_nacimiento': '1990-01-01'})
    h2 = login(c, 'otro_cli', 'Clave12345')
    assert c.get(f'/api/v1/pedidos/{vid}', headers=h2).status_code == 404
    assert c.get(f'/api/v1/pedidos/{vid}', headers=H['cliente1']).status_code == 200
    assert vid not in [p['id'] for p in c.get('/api/v1/pedidos', headers=h2).get_json()['items']]


def test_idempotency_key_en_pedidos(c, H):
    pid = nuevo_producto(c, H, 5)
    h = {**H['cliente1'], 'Idempotency-Key': 'clave-abc-1'}
    r1 = c.post('/api/v1/pedidos', json={'items': [{'producto_id': pid, 'cantidad': 1}], 'direccion_entrega': 'x', 'telefono_contacto': '1'}, headers=h)
    r2 = c.post('/api/v1/pedidos', json={'items': [{'producto_id': pid, 'cantidad': 1}], 'direccion_entrega': 'x', 'telefono_contacto': '1'}, headers=h)
    assert r1.status_code == r2.status_code == 201 and r1.get_json()['id'] == r2.get_json()['id']
    assert r2.headers.get('Idempotent-Replay') == 'true' and stock_de(pid) == 4


def test_inventario_y_alertas(c, H):
    pid = nuevo_producto(c, H, 3, nombre='Poco stock')
    assert c.post('/api/v1/inventario/movimientos', json={'producto_id': pid, 'tipo': 'entrada', 'cantidad': 10}, headers=H['cliente1']).status_code == 403
    r = c.post('/api/v1/inventario/movimientos', json={'producto_id': pid, 'tipo': 'entrada', 'cantidad': 10}, headers=H['bodega1'])
    assert r.status_code == 201 and r.get_json()['stock'] == 13
    assert c.post('/api/v1/inventario/movimientos', json={'producto_id': pid, 'tipo': 'ajuste', 'cantidad': -20, 'motivo': 'rotura'}, headers=H['bodega1']).status_code == 422
    assert c.post('/api/v1/inventario/movimientos', json={'producto_id': pid, 'tipo': 'ajuste', 'cantidad': -12, 'motivo': 'rotura'}, headers=H['bodega1']).get_json()['bajo_minimo'] is True
    assert pid in [p['id'] for p in c.get('/api/v1/inventario/alertas', headers=H['bodega1']).get_json()]


def test_producto_con_ventas_se_desactiva(c, H):
    pid = nuevo_producto(c, H, 5)
    pedido(c, H, pid)
    assert c.delete(f'/api/v1/productos/{pid}', headers=H['admin_api']).get_json()['modo'] == 'desactivado'
    libre = nuevo_producto(c, H, 5, nombre='sin ventas')
    assert c.delete(f'/api/v1/productos/{libre}', headers=H['admin_api']).get_json()['modo'] == 'eliminado'


# ------------------------------------------------------------------ Distribución
def test_entrega_no_entregado_repone_una_sola_vez(c, H):
    pid = nuevo_producto(c, H, 5)
    vid = pedido(c, H, pid, 2).get_json()['id']
    assert stock_de(pid) == 3
    assert c.put(f'/api/v1/entregas/{vid}', json={}, headers=H['repartidor1']).status_code == 422          # acción obligatoria
    r = c.put(f'/api/v1/entregas/{vid}', json={'accion': 'no_entregado', 'observacion': 'no contestó'}, headers=H['repartidor1'])
    assert r.status_code == 200 and r.get_json()['stock_repuesto'] and stock_de(pid) == 5
    r = c.put(f'/api/v1/entregas/{vid}', json={'accion': 'no_entregado'}, headers=H['repartidor1'])
    assert r.status_code == 409 and r.get_json()['error']['codigo'] == 'PEDIDO_YA_PROCESADO'
    assert stock_de(pid) == 5                                         # H-03: no se repone dos veces
    v = c.get(f'/api/v1/pedidos/{vid}', headers=H['cliente1']).get_json()
    assert v['estado'] == 'no_entregado' and v['estado_pago'] == 'anulado' and v['monto_cobrado'] == 0


def test_entrega_conforme_cobra_el_total(c, H):
    pid = nuevo_producto(c, H, 5, 20)
    vid = pedido(c, H, pid, 2).get_json()['id']
    assert c.put(f'/api/v1/entregas/{vid}/en-camino', headers=H['repartidor1']).status_code == 200
    assert any(e['id'] == vid and e['estado'] == 'en_camino' for e in c.get('/api/v1/entregas', headers=H['repartidor1']).get_json())
    r = c.put(f'/api/v1/entregas/{vid}', json={'accion': 'entregado'}, headers=H['repartidor1'])
    assert r.status_code == 200 and r.get_json()['cobrado'] == 40
    v = c.get(f'/api/v1/pedidos/{vid}', headers=H['cliente1']).get_json()
    assert v['estado'] == 'entregada' and v['estado_pago'] == 'pagado' and v['monto_cobrado'] == 40
    assert c.put(f'/api/v1/entregas/{vid}', json={'accion': 'entregado'}, headers=H['repartidor1']).status_code == 409
    assert c.get(f'/api/v1/comprobantes?venta_id={vid}', headers=H['cliente1']).status_code == 200
    seg = c.get(f'/api/v1/pedidos/{vid}/seguimiento', headers=H['cliente1']).get_json()
    assert seg['estado'] == 'entregada' and seg['linea_tiempo']


def test_asignacion_por_admin(c, H):
    pid = nuevo_producto(c, H, 5)
    vid = pedido(c, H, pid).get_json()['id']
    assert c.put(f'/api/v1/pedidos/{vid}/asignacion', json={'repartidor_id': 3}, headers=H['cajero1']).status_code == 403
    assert c.put(f'/api/v1/pedidos/{vid}/asignacion', json={'repartidor_id': 5}, headers=H['admin_api']).status_code == 422   # no es repartidor
    assert c.put(f'/api/v1/pedidos/{vid}/asignacion', json={'repartidor_id': 3}, headers=H['admin_api']).status_code == 200


def test_pedido_vencido_libera_stock(c, H):
    from app.modules.ecommerce.service import PedidoService
    pid = nuevo_producto(c, H, 5)
    vid = pedido(c, H, pid, 2).get_json()['id']
    sql('UPDATE ventas SET created_at=DATE_SUB(NOW(), INTERVAL 2 DAY) WHERE id=%s', (vid,))
    assert PedidoService.cancelar_vencidos() >= 1 and stock_de(pid) == 5                      # H-08
    assert c.get(f'/api/v1/pedidos/{vid}', headers=H['cliente1']).get_json()['estado'] == 'no_entregado'


# ------------------------------------------------------------------ Pagos / caja
def abrir_caja(c, H, monto=100):
    if c.get('/api/v1/cajas/actual', headers=H['cajero1']).get_json() is None:
        assert c.post('/api/v1/cajas/apertura', json={'monto_inicial': monto}, headers=H['cajero1']).status_code == 201


def test_venta_mostrador_exige_caja_y_cobra_efectivo(c, H):
    pid = nuevo_producto(c, H, 10, 25)
    cuerpo = {'items': [{'producto_id': pid, 'cantidad': 2}], 'metodo': 'efectivo'}
    sql('UPDATE cajas SET cerrada_en=NOW() WHERE cerrada_en IS NULL')
    r = c.post('/api/v1/ventas', json=cuerpo, headers=H['cajero1'])
    assert r.status_code == 409 and r.get_json()['error']['codigo'] == 'CAJA_CERRADA' and stock_de(pid) == 10
    abrir_caja(c, H, 100)
    r = c.post('/api/v1/ventas', json=cuerpo, headers=H['cajero1'])
    d = r.get_json()
    assert r.status_code == 201 and d['estado'] == 'pagada' and d['estado_pago'] == 'pagado' and d['tipo_venta'] == 'mostrador'
    assert stock_de(pid) == 8
    caja = c.get('/api/v1/cajas/actual', headers=H['cajero1']).get_json()
    assert caja['esperado'] == 150 and caja['ingresos'] == 50
    cierre = c.post(f"/api/v1/cajas/{caja['id']}/cierre", json={'monto_contado': 140}, headers=H['cajero1']).get_json()
    assert cierre['diferencia'] == -10 and cierre['resultado'] == 'faltante'
    assert c.get(f"/api/v1/comprobantes?venta_id={d['id']}", headers=H['cajero1']).get_json()['comprobante']['numero'].startswith('C-')


def firmar(d): 
    cuerpo = json.dumps(d).encode()
    return cuerpo, firmar_hmac(cuerpo, Config.QR_SECRETO)


def test_EC3_pago_qr_webhook_firmado_e_idempotente(c, H):
    pid = nuevo_producto(c, H, 10, 30)
    sql('UPDATE cajas SET cerrada_en=NOW() WHERE cerrada_en IS NULL'); abrir_caja(c, H)
    r = c.post('/api/v1/ventas', json={'items': [{'producto_id': pid, 'cantidad': 2}], 'metodo': 'qr'}, headers=H['cajero1'])
    d = r.get_json()
    assert r.status_code == 201 and d['estado'] == 'pendiente' and d['pago']['estado'] == 'pendiente'
    ref, monto = d['pago']['referencia'], d['pago']['monto']
    assert monto == 60 and d['pago']['qr_payload'].startswith('LICOFAST-SAS|')
    cuerpo, firma = firmar({'referencia': ref, 'monto': '60.00', 'estado': 'PAGADO', 'id_transaccion': 'TX1'})
    assert c.post('/api/v1/pagos/webhook/qr', data=cuerpo, headers={'X-Firma': 'mala'}).status_code == 401
    assert c.post('/api/v1/pagos/webhook/qr', data=cuerpo).status_code == 401
    cb, fb = firmar({'referencia': ref, 'monto': '10.00', 'estado': 'PAGADO'})
    r = c.post('/api/v1/pagos/webhook/qr', data=cb, headers={'X-Firma': fb})
    assert r.status_code == 422 and r.get_json()['error']['codigo'] == 'MONTO_INCORRECTO'
    assert c.get(f"/api/v1/pedidos/{d['id']}", headers=H['cajero1']).get_json()['estado_pago'] == 'pendiente'
    assert c.post('/api/v1/pagos/webhook/qr', data=cuerpo, headers={'X-Firma': firma}).status_code == 200
    r2 = c.post('/api/v1/pagos/webhook/qr', data=cuerpo, headers={'X-Firma': firma})
    assert r2.status_code == 200 and r2.get_json()['idempotente'] is True
    v = c.get(f"/api/v1/pedidos/{d['id']}", headers=H['cajero1']).get_json()
    assert v['estado'] == 'pagada' and v['estado_pago'] == 'pagado' and v['pago']['estado'] == 'confirmado'
    assert sql('SELECT COUNT(*) n FROM pagos WHERE venta_id=%s AND estado="confirmado"', (d['id'],))[0]['n'] == 1       # un solo cobro
    assert sql('SELECT COUNT(*) n FROM comprobantes WHERE venta_id=%s', (d['id'],))[0]['n'] == 1


def test_qr_vencido_cancela_venta_de_mostrador(c, H):
    from app.modules.pagos.facade import PagosFacade
    pid = nuevo_producto(c, H, 10, 30)
    sql('UPDATE cajas SET cerrada_en=NOW() WHERE cerrada_en IS NULL'); abrir_caja(c, H)
    d = c.post('/api/v1/ventas', json={'items': [{'producto_id': pid, 'cantidad': 3}], 'metodo': 'qr'}, headers=H['cajero1']).get_json()
    assert stock_de(pid) == 7
    sql('UPDATE pagos SET qr_expira_en=DATE_SUB(NOW(), INTERVAL 1 MINUTE) WHERE id=%s', (d['pago']['id'],))
    assert PagosFacade.expirar_vencidos() >= 1 and stock_de(pid) == 10
    v = c.get(f"/api/v1/pedidos/{d['id']}", headers=H['cajero1']).get_json()
    assert v['estado'] == 'no_entregado' and v['estado_pago'] == 'anulado'
    cuerpo, firma = firmar({'referencia': d['pago']['referencia'], 'monto': '90.00', 'estado': 'PAGADO'})
    assert c.post('/api/v1/pagos/webhook/qr', data=cuerpo, headers={'X-Firma': firma}).status_code == 409   # pago tardío → revisión manual


def test_cliente_paga_su_pedido_delivery_por_qr_y_luego_se_entrega_sin_doble_cobro(c, H):
    pid = nuevo_producto(c, H, 5, 40)
    vid = pedido(c, H, pid).get_json()['id']
    r = c.post('/api/v1/pagos', json={'venta_id': vid, 'metodo': 'qr'}, headers=H['cliente1'])
    assert r.status_code == 201
    assert c.post('/api/v1/pagos', json={'venta_id': vid, 'metodo': 'efectivo'}, headers=H['cliente1']).status_code == 403
    r2 = c.post('/api/v1/pagos', json={'venta_id': vid, 'metodo': 'qr'}, headers=H['cliente1'])
    assert r2.get_json()['id'] == r.get_json()['id']                    # reutiliza el QR vigente
    assert c.post(f"/api/v1/pagos/simulador/qr/{r.get_json()['referencia']}/pagar", headers=H['cliente1']).status_code == 200
    v = c.get(f'/api/v1/pedidos/{vid}', headers=H['cliente1']).get_json()
    assert v['estado'] == 'pendiente' and v['estado_pago'] == 'pagado'
    assert next(e for e in c.get('/api/v1/entregas', headers=H['repartidor1']).get_json() if e['id'] == vid)['a_cobrar'] == 0
    assert c.put(f'/api/v1/entregas/{vid}', json={'accion': 'entregado'}, headers=H['repartidor1']).status_code == 200
    assert sql('SELECT COUNT(*) n FROM pagos WHERE venta_id=%s AND estado="confirmado"', (vid,))[0]['n'] == 1


def test_anular_pago_de_mostrador(c, H):
    pid = nuevo_producto(c, H, 5, 10)
    sql('UPDATE cajas SET cerrada_en=NOW() WHERE cerrada_en IS NULL'); abrir_caja(c, H)
    d = c.post('/api/v1/ventas', json={'items': [{'producto_id': pid, 'cantidad': 2}], 'metodo': 'efectivo'}, headers=H['cajero1']).get_json()
    pago = sql('SELECT id FROM pagos WHERE venta_id=%s', (d['id'],))[0]['id']
    assert c.post(f'/api/v1/pagos/{pago}/anular', json={'motivo': 'x'}, headers=H['cajero1']).status_code == 403
    assert c.post(f'/api/v1/pagos/{pago}/anular', json={'motivo': 'error de digitación'}, headers=H['admin_api']).status_code == 200
    assert stock_de(pid) == 5
    assert c.post(f'/api/v1/pagos/{pago}/anular', json={'motivo': 'otra vez'}, headers=H['admin_api']).status_code == 409


# ------------------------------------------------------------------ Transversales
def test_I8_movimientos_explican_el_stock(c, H):
    desfases = sql('SELECT p.id FROM productos p LEFT JOIN (SELECT producto_id, SUM(cantidad) s FROM movimientos_stock GROUP BY producto_id) m ON m.producto_id=p.id WHERE p.stock <> COALESCE(m.s,0)')
    assert desfases == []


def test_auditoria_y_resumen(c, H):
    r = c.get('/api/v1/auditoria?accion=LoginExitoso', headers=H['admin_api']).get_json()
    assert r['total'] >= 1
    acciones = {x['accion'] for x in c.get('/api/v1/auditoria?size=100', headers=H['admin_api']).get_json()['items']}
    assert {'PedidoCreado', 'PedidoNoEntregado', 'ProductoCreado'} <= acciones
    res = c.get('/api/v1/reportes/resumen', headers=H['admin_api']).get_json()
    assert 'hoy' in res and 'stock_bajo' in res
    assert c.get('/api/v1/pagos', headers=H['admin_api']).status_code == 200


def test_errores_con_formato_uniforme(c):
    r = c.get('/api/v1/no-existe')
    assert r.status_code == 404 and set(r.get_json()['error']) == {'codigo', 'mensaje', 'detalle', 'traza'}
    assert c.get('/api/v1/health').get_json()['ok'] is True
