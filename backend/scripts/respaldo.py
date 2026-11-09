"""Respaldo manual (o desde el programador de tareas / cron):  python scripts/respaldo.py"""
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.modules.seguridad.respaldo import respaldar  # noqa: E402

if __name__ == '__main__':
    print(respaldar())
