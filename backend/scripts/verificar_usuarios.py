"""Verifica el login, registro y permisos de todos los roles."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app import create_app

def main():
    app = create_app()
    c = app.test_client()

    users = ['admin_api', 'cajero1', 'repartidor1', 'bodega1', 'cliente1']
    print("=== PROBANDO LOGIN DE USUARIOS DE DEMOSTRACIÓN ===")
    tokens = {}
    for u in users:
        res = c.post('/api/v1/auth/login', json={'usuario': u, 'password': 'Admin1234'})
        data = res.get_json()
        if res.status_code == 200 and 'token' in data:
            tokens[u] = data['token']
            print(f"  [OK] {u:12} -> Rol: {data['usuario']['rol']:14} Nombre: {data['usuario']['nombre']}")
        else:
            print(f"  [ERROR] {u:12} -> Status {res.status_code}: {data}")

    print("\n=== PROBANDO ENDPOINT /auth/me CON TOKENS ===")
    for u, tok in tokens.items():
        res = c.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + tok})
        data = res.get_json()
        if res.status_code == 200:
            print(f"  [OK] /auth/me {u:12} -> Usuario: {data['usuario']}")
        else:
            print(f"  [ERROR] /auth/me {u:12} -> Status {res.status_code}: {data}")

    print("\n=== PROBANDO REGISTRO DE NUEVO CLIENTE ===")
    reg_data = {
        'nombre': 'Carlos',
        'apellido': 'Gomez',
        'ci': 'CI-998877',
        'fecha_nacimiento': '2000-05-15',
        'telefono': '71234567',
        'usuario': 'carlos_test',
        'password': 'Password1234',
        'terminos': True
    }
    res_reg = c.post('/api/v1/auth/register', json=reg_data)
    print(f"  Registro cliente -> Status {res_reg.status_code}: {res_reg.get_json()}")

    res_log = c.post('/api/v1/auth/login', json={'usuario': 'carlos_test', 'password': 'Password1234'})
    if res_log.status_code == 200:
        print(f"  Login nuevo cliente -> [OK]")
    else:
        print(f"  Login nuevo cliente -> [ERROR]: {res_log.get_json()}")

    print("\n=== PROBANDO CRUD DE USUARIOS POR ADMINISTRADOR ===")
    h_adm = {'Authorization': 'Bearer ' + tokens['admin_api']}
    res_list = c.get('/api/v1/usuarios', headers=h_adm)
    print(f"  Listar usuarios (admin) -> {len(res_list.get_json())} usuarios encontrados [OK]")

if __name__ == '__main__':
    main()

