"""Verifica las notificaciones de WhatsApp para 'En camino' y 'Llegó a la ubicación'."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app import create_app
from tests.test_licofast import login as login_user, pedido, nuevo_producto

def main():
    app = create_app()
    c = app.test_client()

    H = {u: {'Authorization': f'Bearer {login_user(c, u)}'} for u in ['admin_api', 'repartidor1', 'cliente1']}

    # 1. Crear producto y pedido
    pid = nuevo_producto(c, H, 10, 50, nombre='Vino Test WhatsApp')
    r_ped = pedido(c, H, pid, 2).get_json()
    vid = r_ped['id']
    print(f"1. Pedido #{vid} creado (Total: Bs {r_ped['total']})")

    # 2. Asignar al repartidor1
    r_asig = c.put(f'/api/v1/pedidos/{vid}/asignacion', json={'repartidor_id': 3}, headers=H['admin_api'])
    assert r_asig.status_code == 200
    print(f"2. Pedido #{vid} asignado al repartidor")

    # 3. Repartidor pone en camino
    r_cam = c.put(f'/api/v1/entregas/{vid}/en-camino', headers=H['repartidor1']).get_json()
    print("3. Respuesta en-camino:", r_cam)
    assert 'whatsapp_url' in r_cam
    assert 'wa.me' in r_cam['whatsapp_url']

    # 4. Repartidor avisa que llegó a la ubicación
    r_des = c.put(f'/api/v1/entregas/{vid}/en-destino', headers=H['repartidor1']).get_json()
    print("4. Respuesta en-destino:", r_des)
    assert 'whatsapp_url' in r_des
    assert 'wa.me' in r_des['whatsapp_url']

    # 5. Seguimiento del cliente
    seg = c.get(f'/api/v1/pedidos/{vid}/seguimiento', headers=H['cliente1']).get_json()
    print("5. Etapas de seguimiento:")
    for ev in seg['linea_tiempo']:
        print("  -", ev['evento'])
    assert any('ya llegó a su ubicación' in ev['evento'] for ev in seg['linea_tiempo'])

    # 6. Inspeccionar el log de WhatsApp simulado
    log_file = pathlib.Path('backend/logs/whatsapp.log')
    print("\n=== CONTENIDO RECIENTE DE backend/logs/whatsapp.log ===")
    lineas = log_file.read_text(encoding='utf-8').strip().splitlines()
    print("\n".join(lineas[-25:]))

    print("\n¡TODAS LAS PRUEBAS DE NOTIFICACIÓN WHATSAPP Y LLEGADA PASARON EXITOSAMENTE!")

if __name__ == '__main__':
    main()

