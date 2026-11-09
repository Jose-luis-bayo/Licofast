"""Crea la base de datos y carga el esquema + datos de demostración usando mysql-connector
(no requiere el cliente mysql). Uso:  python scripts/init_db.py [--reset]"""
import pathlib
import sys
import mysql.connector

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.config import Config, ROOT  # noqa: E402
from app.db import ssl_args  # noqa: E402

SQL = ROOT / 'database' / 'licofast.sql'


def sentencias(texto):
    buf = []
    for linea in texto.splitlines():
        if linea.strip().startswith('--') or not linea.strip():
            continue
        buf.append(linea)
        if linea.rstrip().endswith(';'):
            yield '\n'.join(buf)
            buf = []


def main():
    conn = mysql.connector.connect(host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER, password=Config.DB_PASSWORD, charset='utf8mb4', **ssl_args())
    cur = conn.cursor()
    if '--reset' in sys.argv:
        cur.execute(f'DROP DATABASE IF EXISTS `{Config.DB_NAME}`')
        print('Base de datos eliminada.')
    n = 0
    for s in sentencias(SQL.read_text(encoding='utf-8').replace('licofast', Config.DB_NAME) if Config.DB_NAME != 'licofast' else SQL.read_text(encoding='utf-8')):
        cur.execute(s)
        n += 1
    conn.commit()
    print(f'Listo: {n} sentencias ejecutadas en la base «{Config.DB_NAME}».')
    cur.close(); conn.close()


if __name__ == '__main__':
    main()
