"""Configuración por variables de entorno (archivo .env opcional)."""
import os
import pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent
ROOT = BASE.parent


def _cargar_env():
    f = BASE / '.env'
    if not f.exists():
        return
    for linea in f.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#') or '=' not in linea:
            continue
        k, v = linea.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_cargar_env()


def env(k, d=None):
    return os.environ.get(k, d)


class Config:
    DB_HOST = env('DB_HOST', '127.0.0.1')
    DB_PORT = int(env('DB_PORT', '3306'))
    DB_USER = env('DB_USER', 'root')
    DB_PASSWORD = env('DB_PASSWORD', '')
    DB_NAME = env('DB_NAME', 'licofast')
    DB_POOL = int(env('DB_POOL', '10'))
    DB_SSL = env('DB_SSL', '0') == '1'   # 1 en la nube (TiDB Cloud, Aiven...): conexión cifrada obligatoria
    DB_SSL_CA = env('DB_SSL_CA', '/etc/ssl/certs/ca-certificates.crt')
    JWT_SECRET = env('JWT_SECRET', 'dev-secret-licofast-cambiar-en-produccion')
    JWT_HORAS = int(env('JWT_HORAS', '8'))
    CORS_ORIGINS = [o.strip() for o in env('CORS_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000,http://localhost,http://127.0.0.1,http://localhost:80,http://127.0.0.1:80').split(',') if o.strip()]
    PBKDF2_ITER = int(env('PBKDF2_ITER', '120000'))
    LOGIN_MAX_INTENTOS = int(env('LOGIN_MAX_INTENTOS', '5'))
    LOGIN_BLOQUEO_MIN = int(env('LOGIN_BLOQUEO_MIN', '15'))
    RATE_LOGIN_POR_MIN = int(env('RATE_LOGIN_POR_MIN', '30'))
    QR_MODO = env('QR_MODO', 'simulado')
    QR_SECRETO = env('QR_SECRETO', 'secreto-webhook-dev')
    QR_EXPIRA_MIN = int(env('QR_EXPIRA_MIN', '10'))
    PEDIDO_TTL_MIN = int(env('PEDIDO_TTL_MIN', '360'))
    MYSQLDUMP_PATH = env('MYSQLDUMP_PATH', 'mysqldump')
    DEBUG = env('FLASK_DEBUG', '0') == '1'
    PORT = int(env('PORT', '5000'))
    BARRIDO_SEG = int(env('BARRIDO_SEG', '60'))
    TESTING = env('LICOFAST_TESTING', '0') == '1'
    FRONTEND_DIR = str(ROOT / 'frontend')
