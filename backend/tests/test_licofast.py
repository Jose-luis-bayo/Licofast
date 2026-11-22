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


def liberar(c, H, vid, repartidor=3):
    """Recorre las etapas internas: caja confirma → bodega prepara → (se fuerza el repartidor de la prueba)."""
    r = c.put(f'/api/v1/pedidos/{vid}/confirmar', headers=H['cajero1'])
    assert r.status_code == 200, r.get_json()
    r = c.put(f'/api/v1/pedidos/{vid}/preparar', headers=H['bodega1'])
    assert r.status_code == 200, r.get_json()
    if sql('SELECT repartidor_id FROM ventas WHERE id=%s', (vid,))[0]['repartidor_id'] != repartidor:
        assert c.put(f'/api/v1/pedidos/{vid}/asignacion', json={'repartidor_id': repartidor}, headers=H['bodega1']).status_code == 200


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
    liberar(c, H, vid)
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
    assert c.put(f'/api/v1/entregas/{vid}/en-camino', headers=H['repartidor1']).status_code in (403, 409)   # aún no pasó por caja y bodega
    liberar(c, H, vid)
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
    liberar(c, H, vid)
    assert c.put(f'/api/v1/pedidos/{vid}/asignacion', json={'repartidor_id': 3}, headers=H['cajero1']).status_code == 403
    assert c.put(f'/api/v1/pedidos/{vid}/asignacion', json={'repartidor_id': 3}, headers=H['repartidor1']).status_code == 403
    assert c.put(f'/api/v1/pedidos/{vid}/asignacion', json={'repartidor_id': 5}, headers=H['admin_api']).status_code == 422   # no es repartidor
    assert c.put(f'/api/v1/pedidos/{vid}/asignacion', json={'repartidor_id': 3}, headers=H['admin_api']).status_code == 200
    assert c.put(f'/api/v1/pedidos/{vid}/asignacion', json={'repartidor_id': 3}, headers=H['bodega1']).status_code == 200      # bodega también puede


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
    assert v['estado'] == 'pendiente' and v['estado_pago'] == 'pagado' and v['metodo_pago'] == 'qr'
    liberar(c, H, vid)
    assert next(e for e in c.get('/api/v1/entregas', headers=H['repartidor1']).get_json() if e['id'] == vid)['a_cobrar'] == 0
    assert c.put(f'/api/v1/entregas/{vid}', json={'accion': 'entregado'}, headers=H['repartidor1']).status_code == 409   # primero debe salir (en camino)
    assert c.put(f'/api/v1/entregas/{vid}/en-camino', headers=H['repartidor1']).status_code == 200
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
    assert {'PedidoCreado', 'PedidoNoEntregado', 'ProductoCreado', 'PedidoConfirmado', 'PedidoPreparado'} <= acciones
    res = c.get('/api/v1/reportes/resumen', headers=H['admin_api']).get_json()
    assert 'hoy' in res and 'stock_bajo' in res
    assert c.get('/api/v1/pagos', headers=H['admin_api']).status_code == 200


def test_errores_con_formato_uniforme(c):
    r = c.get('/api/v1/no-existe')
    assert r.status_code == 404 and set(r.get_json()['error']) == {'codigo', 'mensaje', 'detalle', 'traza'}
    assert c.get('/api/v1/health').get_json()['ok'] is True


# ------------------------------------------------------------------ Google
def test_google_login_crea_cliente_y_exige_completar_perfil(c, monkeypatch):
    from app.config import Config
    from google.oauth2 import id_token
    monkeypatch.setattr(Config, 'GOOGLE_CLIENT_ID', 'cliente-de-prueba')
    monkeypatch.setattr(id_token, 'verify_oauth2_token', lambda cred, req, aud: {'sub': '1234567890', 'email': 'a@b.com', 'email_verified': True, 'given_name': 'Ana', 'family_name': 'Pérez'} if cred == 'ok' else (_ for _ in ()).throw(ValueError('malo')))
    assert c.post('/api/v1/auth/google', json={'credential': 'falso'}).status_code == 401
    d = c.post('/api/v1/auth/google', json={'credential': 'ok'}).get_json()
    assert d['usuario']['rol'] == 'cliente' and d['usuario']['perfil_incompleto'] is True
    h = {'Authorization': 'Bearer ' + d['token']}
    # sin fecha de nacimiento no puede comprar alcohol
    r = c.post('/api/v1/pedidos', json={'items': [{'producto_id': 1, 'cantidad': 1}], 'direccion': 'Calle 1', 'telefono': '70000000'}, headers=h)
    assert r.status_code == 422 and r.get_json()['error']['codigo'] == 'EDAD_NO_VERIFICADA'
    # menor de edad rechazado; mayor completa el perfil
    r = c.put('/api/v1/auth/me', json={'fecha_nacimiento': '2015-01-01', 'ci': '999111', 'terminos': True}, headers=h)
    assert r.status_code == 422 and r.get_json()['error']['codigo'] == 'MENOR_DE_EDAD'
    r = c.put('/api/v1/auth/me', json={'fecha_nacimiento': '1990-05-05', 'ci': '999111', 'terminos': True}, headers=h)
    assert r.status_code == 200 and r.get_json()['perfil_incompleto'] is False
    # el segundo ingreso reutiliza la misma cuenta
    d2 = c.post('/api/v1/auth/google', json={'credential': 'ok'}).get_json()
    assert d2['usuario']['id'] == d['usuario']['id']
    # la fecha de nacimiento ya no puede cambiarse
    c.put('/api/v1/auth/me', json={'fecha_nacimiento': '2000-01-01', 'ci': '999111', 'terminos': True}, headers=h)
    assert sql('SELECT fecha_nacimiento FROM usuarios WHERE id=%s', (d['usuario']['id'],))[0]['fecha_nacimiento'].year == 1990


def test_google_sin_configurar_responde_503(c):
    assert c.post('/api/v1/auth/google', json={'credential': 'x'}).status_code == 503


# ------------------------------------------------------------------ Ubicación en vivo
def test_ubicacion_en_vivo_del_repartidor(c, H):
    pid = nuevo_producto(c, H, 5, 20)
    vid = pedido(c, H, pid, 1).get_json()['id']
    ub = f'/api/v1/entregas/{vid}/ubicacion'
    liberar(c, H, vid)
    assert c.put(ub, json={'lat': -19.03, 'lng': -65.26}, headers=H['repartidor1']).status_code == 409      # ya es suyo pero aún no salió (no está en camino)
    assert c.get(f'/api/v1/pedidos/{vid}/ubicacion', headers=H['cliente1']).get_json()['disponible'] is False
    c.put(f'/api/v1/entregas/{vid}/en-camino', headers=H['repartidor1'])
    assert c.put(ub, json={'lat': 'x', 'lng': 1}, headers=H['repartidor1']).status_code == 422
    assert c.put(ub, json={'lat': 99, 'lng': 1}, headers=H['repartidor1']).status_code == 422
    assert c.put(ub, json={'lat': -19.0333, 'lng': -65.2627}, headers=H['repartidor1']).status_code == 200
    assert c.put(ub, json={'lat': -19.0340, 'lng': -65.2630}, headers=H['repartidor1']).status_code == 200  # actualiza
    assert c.put(ub, json={'lat': 1, 'lng': 1}, headers=H['cliente1']).status_code == 403                  # el cliente no puede reportar
    r = c.get(f'/api/v1/pedidos/{vid}/ubicacion', headers=H['cliente1']).get_json()
    assert r['disponible'] is True and abs(r['lat'] + 19.034) < 1e-6 and abs(r['lng'] + 65.263) < 1e-6
    assert c.get(f'/api/v1/pedidos/{vid}/ubicacion', headers=H['admin_api']).status_code == 200
    c.put(f'/api/v1/entregas/{vid}', json={'accion': 'entregado'}, headers=H['repartidor1'])
    assert c.get(f'/api/v1/pedidos/{vid}/ubicacion', headers=H['cliente1']).get_json()['disponible'] is False


# ------------------------------------------------------------------ Nuevo flujo: caja → bodega → repartidor, pagos y ubicación del cliente
def test_flujo_completo_caja_bodega_repartidor(c, H):
    pid = nuevo_producto(c, H, 10, 30)
    d = pedido(c, H, pid, 2, metodo_pago='efectivo', lat=-19.0333, lng=-65.2627).get_json()
    vid = d['id']
    assert d['estado'] == 'pendiente' and d['metodo_pago'] == 'efectivo' and d['lat_entrega'] == -19.0333
    # cada rol solo puede hacer lo suyo
    assert c.put(f'/api/v1/pedidos/{vid}/preparar', headers=H['bodega1']).status_code == 409        # bodega no puede saltarse a caja
    assert c.put(f'/api/v1/pedidos/{vid}/confirmar', headers=H['bodega1']).status_code == 403
    assert c.put(f'/api/v1/pedidos/{vid}/confirmar', headers=H['cliente1']).status_code == 403
    assert c.put(f'/api/v1/entregas/{vid}/en-camino', headers=H['repartidor1']).status_code in (403, 409)
    assert c.get(f'/api/v1/pedidos/{vid}', headers=H['repartidor1']).status_code == 404               # el repartidor aún no lo ve
    cola = c.get('/api/v1/pedidos/online', headers=H['cajero1']).get_json()
    assert any(x['id'] == vid and x['estado'] == 'pendiente' and x['items'] for x in cola)
    assert c.put(f'/api/v1/pedidos/{vid}/confirmar', headers=H['cajero1']).status_code == 200
    assert c.put(f'/api/v1/pedidos/{vid}/confirmar', headers=H['cajero1']).status_code == 409        # ya no está pendiente
    assert not any(e['id'] == vid for e in c.get('/api/v1/entregas', headers=H['repartidor1']).get_json())
    r = c.put(f'/api/v1/pedidos/{vid}/preparar', headers=H['bodega1'])
    assert r.status_code == 200 and r.get_json()['repartidor_id']
    rep = r.get_json()['repartidor_id']
    mio = {3: 'repartidor1'}.get(rep)
    assert mio, 'solo existe el repartidor1 en la base de pruebas'
    assert any(e['id'] == vid and e['estado'] == 'preparado' for e in c.get('/api/v1/entregas', headers=H['repartidor1']).get_json())
    seg = c.get(f'/api/v1/pedidos/{vid}/seguimiento', headers=H['cliente1']).get_json()
    assert [e['evento'] for e in seg['linea_tiempo']][:3] == ['Pedido recibido', 'Confirmado por caja', 'Preparado en bodega']
    assert c.put(f'/api/v1/entregas/{vid}/en-camino', headers=H['repartidor1']).status_code == 200
    ub = c.get(f'/api/v1/pedidos/{vid}/ubicacion', headers=H['cliente1']).get_json()
    assert ub['destino_lat'] == -19.0333 and ub['destino_lng'] == -65.2627
    assert c.put(f'/api/v1/entregas/{vid}', json={'accion': 'entregado'}, headers=H['repartidor1']).status_code == 200


def test_reparto_equitativo_al_repartidor_con_menos_carga(c, H):
    nuevo = c.post('/api/v1/usuarios', json={'nombre': 'Rapi', 'apellido': 'Dos', 'ci': 'REPA-002', 'usuario': 'repartidor2', 'password': 'Admin1234', 'rol': 'repartidor'}, headers=H['admin_api'])
    assert nuevo.status_code == 201, nuevo.get_json()
    rep2 = nuevo.get_json()['id']
    sql("UPDATE ventas SET estado='no_entregado' WHERE tipo_venta='delivery' AND estado IN ('preparado','en_camino')")   # limpia cargas de otras pruebas
    pid = nuevo_producto(c, H, 20, 10)
    asignados = []
    for _ in range(4):
        vid = pedido(c, H, pid).get_json()['id']
        assert c.put(f'/api/v1/pedidos/{vid}/confirmar', headers=H['cajero1']).status_code == 200
        asignados.append(c.put(f'/api/v1/pedidos/{vid}/preparar', headers=H['bodega1']).get_json()['repartidor_id'])
    assert sorted(asignados.count(x) for x in set(asignados)) == [2, 2] and set(asignados) == {3, rep2}      # 2 y 2: carga pareja
    assert asignados[0] != asignados[1]                                                                          # alterna
    carga = {r['id']: r['por_salir'] for r in c.get('/api/v1/repartidores', headers=H['bodega1']).get_json()}
    assert carga[3] == 2 and carga[rep2] == 2
    assert c.get('/api/v1/repartidores', headers=H['cajero1']).status_code == 403
    sql("UPDATE usuarios SET activo=0 WHERE id=%s", (rep2,))
    vid = pedido(c, H, pid).get_json()['id']
    c.put(f'/api/v1/pedidos/{vid}/confirmar', headers=H['cajero1'])
    assert c.put(f'/api/v1/pedidos/{vid}/preparar', headers=H['bodega1']).get_json()['repartidor_id'] == 3   # un repartidor inactivo no recibe pedidos


def test_rechazo_de_caja_repone_stock(c, H):
    pid = nuevo_producto(c, H, 5, 10)
    vid = pedido(c, H, pid, 3).get_json()['id']
    assert stock_de(pid) == 2
    assert c.put(f'/api/v1/pedidos/{vid}/rechazar', json={}, headers=H['cajero1']).status_code == 422       # motivo obligatorio
    r = c.put(f'/api/v1/pedidos/{vid}/rechazar', json={'motivo': 'dirección fuera de zona'}, headers=H['cajero1'])
    assert r.status_code == 200 and stock_de(pid) == 5
    assert c.put(f'/api/v1/pedidos/{vid}/confirmar', headers=H['cajero1']).status_code == 409


def test_pago_en_linea_debe_estar_pagado_para_confirmar(c, H):
    pid = nuevo_producto(c, H, 5, 50)
    d = pedido(c, H, pid, 1, metodo_pago='qr').get_json()
    vid = d['id']
    r = c.put(f'/api/v1/pedidos/{vid}/confirmar', headers=H['cajero1'])
    assert r.status_code == 409 and r.get_json()['error']['codigo'] == 'PAGO_PENDIENTE'
    p = c.post('/api/v1/pagos', json={'venta_id': vid, 'metodo': 'qr'}, headers=H['cliente1']).get_json()
    assert c.post(f"/api/v1/pagos/simulador/qr/{p['referencia']}/pagar", headers=H['cliente1']).status_code == 200
    assert c.put(f'/api/v1/pedidos/{vid}/confirmar', headers=H['cajero1']).status_code == 200


def test_pago_paypal_simulado(c, H):
    pid = nuevo_producto(c, H, 5, 69.6)
    vid = pedido(c, H, pid, 1, metodo_pago='paypal').get_json()['id']
    assert c.post('/api/v1/pagos', json={'venta_id': vid, 'metodo': 'paypal'}, headers=H['cajero1']).status_code == 403
    r = c.post('/api/v1/pagos', json={'venta_id': vid, 'metodo': 'paypal'}, headers=H['cliente1'])
    p = r.get_json()
    assert r.status_code == 201 and p['metodo'] == 'paypal' and p['estado'] == 'pendiente' and '/pagos/simulador/paypal/' in p['qr_payload']
    assert c.post('/api/v1/pagos', json={'venta_id': vid, 'metodo': 'paypal'}, headers=H['cliente1']).get_json()['id'] == p['id']   # reutiliza la orden
    from app.modules.pagos.adapter import PayPalAdapter
    assert float(PayPalAdapter.usd(69.6)) == 10.0                                                                   # 69.6 Bs / 6.96 = 10 USD
    pag = c.get(f"/api/v1/pagos/simulador/paypal/{p['referencia']}")
    assert pag.status_code == 200 and b'PayPal' in pag.data
    ret = c.get(f"/api/v1/pagos/paypal/retorno?token={p['referencia']}")
    assert ret.status_code == 200 and 'Pago recibido' in ret.get_data(as_text=True)
    assert c.get(f"/api/v1/pagos/paypal/retorno?token={p['referencia']}").status_code == 200                       # idempotente
    v = c.get(f'/api/v1/pedidos/{vid}', headers=H['cliente1']).get_json()
    assert v['estado_pago'] == 'pagado' and v['pago']['metodo'] == 'paypal'
    assert sql('SELECT COUNT(*) n FROM pagos WHERE venta_id=%s AND estado="confirmado"', (vid,))[0]['n'] == 1
    assert 'No se pudo' in c.get('/api/v1/pagos/paypal/retorno?token=PPINEXISTENTE').get_data(as_text=True)


def test_paypal_real_sin_credenciales_responde_503(c, H, monkeypatch):
    monkeypatch.setattr(Config, 'PAYPAL_MODO', 'sandbox'); monkeypatch.setattr(Config, 'PAYPAL_CLIENT_ID', '')
    pid = nuevo_producto(c, H, 5, 20)
    vid = pedido(c, H, pid, 1, metodo_pago='paypal').get_json()['id']
    r = c.post('/api/v1/pagos', json={'venta_id': vid, 'metodo': 'paypal'}, headers=H['cliente1'])
    assert r.status_code == 503 and r.get_json()['error']['codigo'] == 'PASARELA_NO_DISPONIBLE'


def test_pedido_valida_metodo_y_ubicacion(c, H):
    pid = nuevo_producto(c, H, 5)
    assert pedido(c, H, pid, 1, metodo_pago='bitcoin').status_code == 422
    assert pedido(c, H, pid, 1, lat='x', lng=1).status_code == 422
    assert pedido(c, H, pid, 1, lat=95, lng=1).status_code == 422
    assert pedido(c, H, pid, 1, lat=-19.03, lng=-65.26, metodo_pago='efectivo').status_code == 201


# ------------------------------------------------------------------ Cupones y vales
def test_cupon_porcentaje_se_aplica_y_se_consume(c, H):
    pid = nuevo_producto(c, H, 10, 100)
    r = c.post('/api/v1/cupones', json={'codigo': 'hola10', 'tipo': 'porcentaje', 'valor': 10, 'usos_por_cliente': 1}, headers=H['admin_api'])
    assert r.status_code == 201 and r.get_json()['codigo'] == 'HOLA10'
    assert c.post('/api/v1/cupones', json={'codigo': 'HOLA10', 'tipo': 'monto', 'valor': 5}, headers=H['admin_api']).status_code == 409
    assert c.post('/api/v1/cupones', json={'codigo': 'X', 'tipo': 'monto', 'valor': 5}, headers=H['cliente1']).status_code == 403
    v = c.post('/api/v1/cupones/validar', json={'codigo': 'hola10', 'items': [{'producto_id': pid, 'cantidad': 2}]}, headers=H['cliente1']).get_json()
    assert v['descuento_cupon'] == 20 and v['total'] == 180
    d = pedido(c, H, pid, 2, cupon='HOLA10').get_json()
    assert d['total'] == 180
    assert sql('SELECT cupon_codigo FROM ventas WHERE id=%s', (d['id'],))[0]['cupon_codigo'] == 'HOLA10'
    r = pedido(c, H, pid, 1, cupon='HOLA10')                                # ya lo usó
    assert r.status_code == 422 and 'Ya usó' in r.get_json()['error']['mensaje']
    assert stock_de(pid) == 8                                                # el pedido rechazado no descontó stock
    assert pedido(c, H, pid, 1, cupon='NOEXISTE').status_code == 422


def test_cupon_monto_minimo_vigencia_y_vale_personal(c, H):
    pid = nuevo_producto(c, H, 10, 50)
    c.post('/api/v1/cupones', json={'codigo': 'MIN200', 'tipo': 'monto', 'valor': 30, 'minimo_compra': 200}, headers=H['admin_api'])
    assert pedido(c, H, pid, 1, cupon='MIN200').status_code == 422           # 50 < 200
    assert pedido(c, H, pid, 4, cupon='MIN200').get_json()['total'] == 170
    c.post('/api/v1/cupones', json={'codigo': 'VIEJO', 'tipo': 'monto', 'valor': 5, 'vigente_hasta': '2020-01-01'}, headers=H['admin_api'])
    assert 'venció' in pedido(c, H, pid, 1, cupon='VIEJO').get_json()['error']['mensaje']
    cli = sql("SELECT id FROM usuarios WHERE usuario='cliente1'")[0]['id']
    v = c.post('/api/v1/cupones/asignar', json={'usuario_id': cli, 'tipo': 'monto', 'valor': 15}, headers=H['admin_api']).get_json()
    assert v['codigo'].startswith('VALE-')
    assert any(x['codigo'] == v['codigo'] and x['usable'] for x in c.get('/api/v1/mis-cupones', headers=H['cliente1']).get_json())
    assert pedido(c, H, pid, 1, cupon=v['codigo']).get_json()['total'] == 35


def test_cupon_se_devuelve_si_el_pedido_no_se_entrega_y_descuento_no_supera_total(c, H):
    pid = nuevo_producto(c, H, 10, 20)
    c.post('/api/v1/cupones', json={'codigo': 'GRANDE', 'tipo': 'monto', 'valor': 500}, headers=H['admin_api'])
    d = pedido(c, H, pid, 1, cupon='GRANDE').get_json()
    assert d['total'] == 0
    c.put(f"/api/v1/pedidos/{d['id']}/rechazar", json={'motivo': 'prueba'}, headers=H['cajero1'])
    assert pedido(c, H, pid, 1, cupon='GRANDE').status_code == 201           # el uso se liberó


def test_recompensa_cliente_frecuente(c, H):
    sql("DELETE FROM cupones WHERE regla='frecuente'")          # otras pruebas ya pudieron premiar a este cliente en el mes
    pid = nuevo_producto(c, H, 20, 10)
    premios = []
    for _ in range(3):
        vid = pedido(c, H, pid, 1).get_json()['id']
        liberar(c, H, vid)
        c.put(f'/api/v1/entregas/{vid}/en-camino', headers=H['repartidor1'])
        r = c.put(f'/api/v1/entregas/{vid}', json={'accion': 'entregado'}, headers=H['repartidor1']).get_json()
        premios += r.get('recompensa_cliente', [])
    assert len(premios) == 1 and premios[0].startswith('GRACIAS-')      # solo un premio por periodo
    mis = c.get('/api/v1/mis-cupones', headers=H['cliente1']).get_json()
    assert any(x['origen'] == 'recompensa' and x['valor'] == 10 for x in mis)
    assert c.post('/api/v1/cupones/recompensas', headers=H['admin_api']).get_json()['emitidos'] == []   # un premio por periodo


# ------------------------------------------------------------------ Cliente cancela / edita; bodega cancela
def test_cliente_cancela_qr_pendiente_y_repone_stock(c, H):
    pid = nuevo_producto(c, H, 10, 50)
    d = pedido(c, H, pid, 2, metodo_pago='qr').get_json()
    assert d['puede_cancelar'] is True and d['puede_editar'] is True
    assert stock_de(pid) == 8
    assert c.put(f"/api/v1/pedidos/{d['id']}/cancelar", headers=H['cliente1']).status_code == 200
    assert stock_de(pid) == 10
    assert c.put(f"/api/v1/pedidos/{d['id']}/cancelar", headers=H['cliente1']).status_code == 409   # ya procesado
    assert c.put(f"/api/v1/pedidos/{d['id']}/cancelar", headers=H['cajero1']).status_code == 403    # solo el cliente


def test_cliente_no_cancela_efectivo_ni_pagado(c, H):
    pid = nuevo_producto(c, H, 10, 50)
    ef = pedido(c, H, pid, 1, metodo_pago='efectivo').get_json()
    assert ef['puede_cancelar'] is False
    r = c.put(f"/api/v1/pedidos/{ef['id']}/cancelar", headers=H['cliente1'])
    assert r.status_code == 409 and r.get_json()['error']['codigo'] == 'NO_CANCELABLE' and 'wa.me' in r.get_json()['error']['detalle']['whatsapp_url']
    qr = pedido(c, H, pid, 1, metodo_pago='qr').get_json()
    pg = c.post('/api/v1/pagos', json={'venta_id': qr['id'], 'metodo': 'qr'}, headers={**H['cliente1'], 'Idempotency-Key': 'k' + str(qr['id'])}).get_json()
    assert c.post(f"/api/v1/pagos/simulador/qr/{pg['referencia']}/pagar", headers=H['cliente1']).status_code == 200
    r = c.put(f"/api/v1/pedidos/{qr['id']}/cancelar", headers=H['cliente1'])
    assert r.status_code == 409 and r.get_json()['error']['codigo'] == 'NO_CANCELABLE'
    otro = c.get(f"/api/v1/pedidos/{qr['id']}", headers=H['cliente1']).get_json()
    assert otro['puede_cancelar'] is False and 'wa.me' in otro['whatsapp_url']


def test_cliente_edita_pedido_pendiente(c, H):
    p1, p2 = nuevo_producto(c, H, 10, 10), nuevo_producto(c, H, 10, 20)
    d = pedido(c, H, p1, 2, metodo_pago='qr', lat=-19.03, lng=-65.26).get_json()
    n = c.put(f"/api/v1/pedidos/{d['id']}", json={'items': [{'producto_id': p1, 'cantidad': 1}, {'producto_id': p2, 'cantidad': 3}]}, headers=H['cliente1']).get_json()
    assert n['id'] != d['id'] and n['total'] == 70 and n['metodo_pago'] == 'qr' and n['lat_entrega'] == -19.03
    assert stock_de(p1) == 9 and stock_de(p2) == 7                              # stock repuesto y vuelto a reservar
    assert sql('SELECT estado FROM ventas WHERE id=%s', (d['id'],))[0]['estado'] == 'no_entregado'
    assert c.put(f"/api/v1/pedidos/{d['id']}", json={'items': [{'producto_id': p1, 'cantidad': 1}]}, headers=H['cliente1']).status_code == 409
    # confirmado por caja ya no se edita
    e = pedido(c, H, p1, 1).get_json()
    c.put(f"/api/v1/pedidos/{e['id']}/confirmar", headers=H['cajero1'])
    assert c.put(f"/api/v1/pedidos/{e['id']}", json={'items': [{'producto_id': p1, 'cantidad': 1}]}, headers=H['cliente1']).status_code == 409


def test_bodega_cancela_pedido_y_cliente_ve_devolucion(c, H):
    pid = nuevo_producto(c, H, 10, 40)
    qr = pedido(c, H, pid, 1, metodo_pago='qr').get_json()
    pg = c.post('/api/v1/pagos', json={'venta_id': qr['id'], 'metodo': 'qr'}, headers={**H['cliente1'], 'Idempotency-Key': 'b' + str(qr['id'])}).get_json()
    c.post(f"/api/v1/pagos/simulador/qr/{pg['referencia']}/pagar", headers=H['cliente1'])
    assert c.put(f"/api/v1/pedidos/{qr['id']}/confirmar", headers=H['cajero1']).status_code == 200
    r = c.put(f"/api/v1/pedidos/{qr['id']}/rechazar", json={'motivo': 'No hay repartidores'}, headers=H['bodega1'])
    assert r.status_code == 200 and r.get_json()['requiere_reembolso'] is True and 'WhatsApp' in r.get_json()['mensaje']
    v = c.get(f"/api/v1/pedidos/{qr['id']}", headers=H['cliente1']).get_json()
    assert v['estado'] == 'no_entregado' and v['devolucion_pendiente'] is True and 'wa.me' in v['whatsapp_url']


# ------------------------------------------------------------------ Promociones avanzadas
def promo(c, H, **d):
    hoy = __import__('datetime').date.today()
    base = {'nombre': 'Promo test', 'desde': str(hoy - __import__('datetime').timedelta(days=1)), 'hasta': str(hoy + __import__('datetime').timedelta(days=30))}
    r = c.post('/api/v1/promociones', json={**base, **d}, headers=H['admin_api'])
    assert r.status_code == 201, r.get_json()
    return r.get_json()['id']


def cotiza(c, items):
    return c.post('/api/v1/carrito/cotizar', json={'items': items}).get_json()


def test_promo_2x1_lleva_paga_y_se_cobra_bien(c, H):
    pid = nuevo_producto(c, H, 20, 50)
    pr = promo(c, H, nombre='2x1 test', tipo='llevapaga', lleva=2, paga=1, producto_id=pid)
    q = cotiza(c, [{'producto_id': pid, 'cantidad': 3}])           # 3 unidades: una pareja gratis
    assert q['total'] == 100 and q['descuento'] == 50 and q['lineas'][0]['promocion'] == '2x1 test'
    assert cotiza(c, [{'producto_id': pid, 'cantidad': 1}])['total'] == 50          # con 1 unidad no aplica
    d = pedido(c, H, pid, 4).get_json()                                              # 4 unidades → paga 2
    assert d['total'] == 100 and d['descuento'] == 100
    assert d['items'][0]['subtotal'] == 100 and stock_de(pid) == 16
    c.put(f'/api/v1/promociones/{pr}/estado', json={'activo': False}, headers=H['admin_api'])   # desactivada: precio normal
    assert cotiza(c, [{'producto_id': pid, 'cantidad': 4}])['total'] == 200
    assert c.put(f'/api/v1/promociones/{pr}/estado', json={'activo': True}, headers=H['admin_api']).status_code == 200
    assert cotiza(c, [{'producto_id': pid, 'cantidad': 4}])['total'] == 100


def test_promo_segunda_unidad_y_volumen(c, H):
    a, b = nuevo_producto(c, H, 20, 40), nuevo_producto(c, H, 20, 100)
    promo(c, H, nombre='Segunda 50', tipo='segunda', valor=50, producto_id=a)
    assert cotiza(c, [{'producto_id': a, 'cantidad': 2}])['total'] == 60
    promo(c, H, nombre='Desde 3 -20%', tipo='porcentaje', valor=20, min_cantidad=3, producto_id=b)
    assert cotiza(c, [{'producto_id': b, 'cantidad': 2}])['total'] == 200          # aún no llega a 3
    assert cotiza(c, [{'producto_id': b, 'cantidad': 3}])['total'] == 240


def test_promo_por_categoria_y_total_del_pedido(c, H):
    pid = nuevo_producto(c, H, 20, 100)
    cat = c.post('/api/v1/categorias', json={'nombre': 'Cat promo ' + str(pid)}, headers=H['admin_api']).get_json()['id']
    sql('UPDATE productos SET categoria_id=%s WHERE id=%s', (cat, pid))
    promo(c, H, nombre='Categoría -30%', tipo='porcentaje', valor=30, categoria_id=cat)
    assert cotiza(c, [{'producto_id': pid, 'cantidad': 1}])['total'] == 70
    ped = promo(c, H, nombre='Compra mayor', tipo='pedido_pct', valor=10, minimo_pedido=200)
    q = cotiza(c, [{'producto_id': pid, 'cantidad': 4}])                            # 4×70=280 ≥ 200 → −10 %
    assert q['total'] == 252 and q['promocion_pedido'] == 'Compra mayor' and q['descuento_pedido'] == 28
    assert cotiza(c, [{'producto_id': pid, 'cantidad': 2}])['total'] == 140         # 140 < 200: sin descuento de pedido
    assert pedido(c, H, pid, 4).get_json()['total'] == 252
    c.delete(f'/api/v1/promociones/{ped}', headers=H['admin_api'])


def test_promo_dias_y_horario_y_validaciones(c, H):
    import datetime
    pid = nuevo_producto(c, H, 20, 100)
    hoy = (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4)))).isoweekday()
    otro = (hoy % 7) + 1
    promo(c, H, nombre='Solo otro día', tipo='porcentaje', valor=50, producto_id=pid, dias=str(otro))
    assert cotiza(c, [{'producto_id': pid, 'cantidad': 1}])['total'] == 100
    promo(c, H, nombre='Hoy', tipo='porcentaje', valor=50, producto_id=pid, dias=f'{hoy},{otro}')
    assert cotiza(c, [{'producto_id': pid, 'cantidad': 1}])['total'] == 50
    ayer = {'nombre': 'x', 'desde': '2026-01-01', 'hasta': '2026-12-31'}
    for malo in ({'tipo': 'llevapaga', 'lleva': 2, 'paga': 2}, {'tipo': 'porcentaje', 'valor': 150}, {'tipo': 'raro', 'valor': 5},
                 {'tipo': 'porcentaje', 'valor': 5, 'dias': '9'}, {'tipo': 'porcentaje', 'valor': 5, 'hora_desde': '18:00'}):
        assert c.post('/api/v1/promociones', json={**ayer, **malo}, headers=H['admin_api']).status_code == 422, malo
    lst = c.get('/api/v1/promociones', headers=H['admin_api']).get_json()
    assert any(x['nombre'] == 'Hoy' and x['dias'] for x in lst)
    assert c.put('/api/v1/promociones/999999/estado', json={'activo': 1}, headers=H['admin_api']).status_code == 404
    assert c.put('/api/v1/promociones/1/estado', json={'activo': 1}, headers=H['cliente1']).status_code == 403


# ------------------------------------------------------------------ Quiosco de autoservicio
CLI = {'nombre': 'María Gómez', 'nit_ci': '1234567', 'telefono': '71234567'}


@pytest.fixture()
def K(monkeypatch):
    monkeypatch.setattr(Config, 'KIOSKO_CLAVE', 'clave-kiosko-prueba')
    return {'X-Kiosko-Clave': 'clave-kiosko-prueba'}


def kpedido(c, K, pid, cant=1, metodo='qr', **extra):
    cuerpo = {'items': [{'producto_id': pid, 'cantidad': cant}], 'metodo_pago': metodo, 'cliente': CLI, 'mayor_edad': True}
    cuerpo.update(extra)
    return c.post('/api/v1/kiosko/pedidos', json=cuerpo, headers=K)


def test_kiosko_desactivado_y_clave(c, monkeypatch):
    monkeypatch.setattr(Config, 'KIOSKO_CLAVE', '')
    assert c.post('/api/v1/kiosko/pedidos', json={}).status_code == 503
    monkeypatch.setattr(Config, 'KIOSKO_CLAVE', 'abc')
    assert c.post('/api/v1/kiosko/pedidos', json={}, headers={'X-Kiosko-Clave': 'mala'}).status_code == 401


def test_kiosko_validaciones(c, H, K):
    pid = nuevo_producto(c, H, 20, 10)
    assert kpedido(c, K, pid, mayor_edad=False).status_code == 422
    assert kpedido(c, K, pid, metodo='efectivo').status_code == 422
    assert kpedido(c, K, pid, cliente={**CLI, 'telefono': '123'}).status_code == 422
    assert kpedido(c, K, pid, cliente={**CLI, 'nombre': ''}).status_code == 422
    assert kpedido(c, K, pid, cliente={**CLI, 'nit_ci': '1'}).status_code == 422
    assert kpedido(c, K, pid, cant=999).status_code in (409, 422)


@pytest.mark.parametrize('metodo', ['qr', 'tarjeta', 'paypal'])
def test_kiosko_flujo_completo(c, H, K, metodo):
    pid = nuevo_producto(c, H, 20, 10)
    r = kpedido(c, K, pid, 2, metodo)
    assert r.status_code == 201, r.get_json()
    p = r.get_json(); vid = p['id']
    assert p['estado'] == 'pendiente' and p['estado_pago'] == 'pendiente' and len(p['codigo_retiro']) == 4
    A = {**K, 'X-Kiosko-Acceso': p['acceso']}
    assert c.get(f'/api/v1/kiosko/pedidos/{vid}', headers=K).status_code == 404                 # sin token de acceso
    pago = c.post(f'/api/v1/kiosko/pedidos/{vid}/pago', json={'metodo': metodo}, headers=A)
    assert pago.status_code == 201 and pago.get_json()['simulable'] is True
    if metodo != 'tarjeta':
        assert pago.get_json()['pago']['qr_payload']
    # todavía no llega a bodega
    assert vid not in [x['id'] for x in c.get('/api/v1/pedidos/online', headers=H['bodega1']).get_json()]
    assert c.post(f'/api/v1/kiosko/pedidos/{vid}/simular', headers=A).status_code == 200
    d = c.get(f'/api/v1/kiosko/pedidos/{vid}', headers=A).get_json()
    assert d['estado'] == 'confirmado' and d['estado_pago'] == 'pagado'                         # pagado → pasa solo a bodega
    cola = c.get('/api/v1/pedidos/online', headers=H['bodega1']).get_json()
    fila = next(x for x in cola if x['id'] == vid)
    assert fila['tipo_venta'] == 'retiro' and 'codigo_retiro' not in fila and fila['whatsapp_factura_url'].startswith('https://wa.me/59171234567')
    assert vid not in [x['id'] for x in c.get('/api/v1/pedidos/online', headers=H['cajero1']).get_json()]   # caja no lo ve
    assert c.put(f'/api/v1/pedidos/{vid}/entregar-retiro', json={'codigo': p['codigo_retiro']}, headers=H['bodega1']).status_code == 409   # aún no preparado
    assert c.put(f'/api/v1/pedidos/{vid}/preparar', headers=H['bodega1']).status_code == 200
    mal = c.put(f'/api/v1/pedidos/{vid}/entregar-retiro', json={'codigo': '0000' if p['codigo_retiro'] != '0000' else '1111'}, headers=H['bodega1'])
    assert mal.status_code == 422 and mal.get_json()['error']['codigo'] == 'CODIGO_INCORRECTO'
    ok = c.put(f'/api/v1/pedidos/{vid}/entregar-retiro', json={'codigo': p['codigo_retiro']}, headers=H['bodega1'])
    assert ok.status_code == 200 and ok.get_json()['estado'] == 'entregada'
    assert sql('SELECT estado, repartidor_id FROM ventas WHERE id=%s', (vid,))[0] == {'estado': 'entregada', 'repartidor_id': None}
    assert c.put(f'/api/v1/pedidos/{vid}/entregar-retiro', json={'codigo': p['codigo_retiro']}, headers=H['bodega1']).status_code == 409


def test_kiosko_cancelar_sin_pagar_repone_stock(c, H, K):
    pid = nuevo_producto(c, H, 20, 10)
    p = kpedido(c, K, pid, 3).get_json(); A = {**K, 'X-Kiosko-Acceso': p['acceso']}
    assert sql('SELECT stock FROM productos WHERE id=%s', (pid,))[0]['stock'] == 17
    assert c.post(f"/api/v1/kiosko/pedidos/{p['id']}/pago", json={'metodo': 'qr'}, headers=A).status_code == 201
    assert c.post(f"/api/v1/kiosko/pedidos/{p['id']}/cancelar", headers=A).status_code == 200
    assert sql('SELECT stock FROM productos WHERE id=%s', (pid,))[0]['stock'] == 20
    assert c.post(f"/api/v1/kiosko/pedidos/{p['id']}/simular", headers=A).status_code == 409


def test_kiosko_no_cancela_pagado_y_bodega_puede_rechazar(c, H, K):
    pid = nuevo_producto(c, H, 20, 10)
    p = kpedido(c, K, pid, 1, 'tarjeta').get_json(); A = {**K, 'X-Kiosko-Acceso': p['acceso']}
    c.post(f"/api/v1/kiosko/pedidos/{p['id']}/pago", json={'metodo': 'tarjeta'}, headers=A)
    c.post(f"/api/v1/kiosko/pedidos/{p['id']}/simular", headers=A)
    assert c.post(f"/api/v1/kiosko/pedidos/{p['id']}/cancelar", headers=A).status_code == 409
    assert c.put(f"/api/v1/pedidos/{p['id']}/rechazar", json={'motivo': 'Sin stock real'}, headers=H['cajero1']).status_code == 403
    r = c.put(f"/api/v1/pedidos/{p['id']}/rechazar", json={'motivo': 'Sin stock real'}, headers=H['bodega1'])
    assert r.status_code == 200 and r.get_json().get('requiere_reembolso') is True
    assert sql('SELECT stock FROM productos WHERE id=%s', (pid,))[0]['stock'] == 20


def test_kiosko_tarjeta_real_no_disponible(c, H, K, monkeypatch):
    monkeypatch.setattr(Config, 'TARJETA_MODO', 'real')
    pid = nuevo_producto(c, H, 20, 10)
    p = kpedido(c, K, pid, 1, 'tarjeta').get_json(); A = {**K, 'X-Kiosko-Acceso': p['acceso']}
    r = c.post(f"/api/v1/kiosko/pedidos/{p['id']}/pago", json={'metodo': 'tarjeta'}, headers=A)
    assert r.status_code == 503 and r.get_json()['error']['codigo'] == 'TARJETA_NO_DISPONIBLE'


def test_kiosko_pedido_sin_pagar_vence(c, H, K, monkeypatch):
    monkeypatch.setattr(Config, 'KIOSKO_TTL_MIN', 0)
    pid = nuevo_producto(c, H, 20, 10)
    p = kpedido(c, K, pid, 2).get_json(); A = {**K, 'X-Kiosko-Acceso': p['acceso']}
    sql("UPDATE ventas SET created_at = DATE_SUB(NOW(), INTERVAL 5 MINUTE) WHERE id=%s", (p['id'],))
    d = c.get(f"/api/v1/kiosko/pedidos/{p['id']}", headers=A).get_json()
    assert d['estado'] == 'no_entregado'
    assert sql('SELECT stock FROM productos WHERE id=%s', (pid,))[0]['stock'] == 20
