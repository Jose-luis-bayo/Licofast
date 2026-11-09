import os
import pathlib
import sys

os.environ['LICOFAST_TESTING'] = '1'
os.environ['DB_NAME'] = 'licofast_test'
os.environ['RATE_LOGIN_POR_MIN'] = '10000'
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import mysql.connector  # noqa: E402
import pytest  # noqa: E402
from app.config import Config, ROOT  # noqa: E402
from scripts.init_db import sentencias  # noqa: E402


@pytest.fixture(scope='session', autouse=True)
def base_de_datos():
    conn = mysql.connector.connect(host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER, password=Config.DB_PASSWORD)
    cur = conn.cursor()
    cur.execute('DROP DATABASE IF EXISTS licofast_test')
    sql = (ROOT / 'database' / 'licofast.sql').read_text(encoding='utf-8').replace('licofast', 'licofast_test')
    for s in sentencias(sql):
        cur.execute(s)
    conn.commit(); cur.close(); conn.close()
    yield


@pytest.fixture(scope='session')
def app(base_de_datos):
    from app import create_app
    return create_app()


@pytest.fixture()
def c(app):
    return app.test_client()


def login(c, usuario, password='Admin1234'):
    r = c.post('/api/v1/auth/login', json={'usuario': usuario, 'password': password})
    assert r.status_code == 200, r.get_json()
    return {'Authorization': 'Bearer ' + r.get_json()['token']}


@pytest.fixture(scope='session')
def H(app):
    cl = app.test_client()
    return {u: login(cl, u) for u in ('admin_api', 'cajero1', 'repartidor1', 'bodega1', 'cliente1')}


def sql(consulta, args=()):
    from app.db import transaction, all_
    with transaction() as cur:
        cur.execute(consulta, args)
        try:
            return cur.fetchall()
        except Exception:
            return None
