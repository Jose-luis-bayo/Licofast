"""Capa 5/4: conexión y transacciones (pool de conexiones MySQL)."""
from contextlib import contextmanager
from mysql.connector import pooling
from .config import Config

_pool = None


def ssl_args():
    """Argumentos TLS para bases en la nube (DB_SSL=1). En XAMPP local no se usa."""
    if not Config.DB_SSL:
        return {}
    return {'ssl_disabled': False, 'ssl_ca': Config.DB_SSL_CA, 'ssl_verify_cert': True}


def pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name='licofast', pool_size=Config.DB_POOL, pool_reset_session=True,
            host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER, password=Config.DB_PASSWORD,
            database=Config.DB_NAME, charset='utf8mb4', collation='utf8mb4_unicode_ci', autocommit=False, **ssl_args())
    return _pool


@contextmanager
def transaction():
    """Abre una transacción; confirma al salir y revierte ante cualquier excepción."""
    conn = pool().get_connection()
    try:
        conn.rollback()
        cur = conn.cursor(dictionary=True)
        try:
            yield cur
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


@contextmanager
def read():
    """Lectura (sin cambios): cierra la instantánea al salir."""
    conn = pool().get_connection()
    try:
        conn.rollback()
        cur = conn.cursor(dictionary=True)
        try:
            yield cur
        finally:
            cur.close()
            conn.rollback()
    finally:
        conn.close()


def one(cur, sql, args=()):
    cur.execute(sql, args)
    return cur.fetchone()


def all_(cur, sql, args=()):
    cur.execute(sql, args)
    return cur.fetchall()


def run(cur, sql, args=()):
    cur.execute(sql, args)
    return cur.lastrowid
