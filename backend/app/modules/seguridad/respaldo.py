"""CU-S07: respaldo de la base de datos con mysqldump (XAMPP incluye mysqldump)."""
import datetime
import os
import shutil
import subprocess
from ...config import Config, BASE
from ...core.errors import AppError

DIR = BASE / 'respaldos'


def _exe():
    ruta = Config.MYSQLDUMP_PATH
    if os.path.isabs(ruta) and os.path.exists(ruta):
        return ruta
    return shutil.which(ruta) or shutil.which('mysqldump') or shutil.which('mariadb-dump')


def respaldar():
    exe = _exe()
    if not exe:
        raise AppError('MYSQLDUMP_NO_ENCONTRADO', 'No se encontró mysqldump. Configure MYSQLDUMP_PATH en el archivo .env', 501)
    DIR.mkdir(exist_ok=True)
    nombre = f"licofast_{datetime.datetime.now():%Y%m%d_%H%M%S}.sql"
    ruta = DIR / nombre
    cmd = [exe, f'--host={Config.DB_HOST}', f'--port={Config.DB_PORT}', f'--user={Config.DB_USER}', '--single-transaction', '--routines', f'--result-file={ruta}', Config.DB_NAME]
    entorno = dict(os.environ, **({'MYSQL_PWD': Config.DB_PASSWORD} if Config.DB_PASSWORD else {}))
    r = subprocess.run(cmd, capture_output=True, text=True, env=entorno, timeout=120)
    if r.returncode != 0:
        raise AppError('RESPALDO_FALLIDO', 'El respaldo falló', 500, {'stderr': r.stderr[-300:]})
    return {'archivo': nombre, 'bytes': ruta.stat().st_size}


def listar():
    if not DIR.exists():
        return []
    return [{'archivo': f.name, 'bytes': f.stat().st_size} for f in sorted(DIR.glob('licofast_*.sql'), reverse=True)[:30]]
