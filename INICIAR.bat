@echo off
REM LicoFast - arranque rapido en Windows (requiere XAMPP con MySQL iniciado y Python 3.11+)
cd /d "%~dp0backend"
if not exist .venv (
  echo [1/4] Creando entorno virtual...
  python -m venv .venv || (echo No se encontro Python. Instale Python 3.11+ y marque "Add to PATH". & pause & exit /b 1)
)
call .venv\Scripts\activate
echo [2/4] Instalando dependencias...
pip install -q -r requirements.txt
if not exist .env copy .env.example .env >nul
echo [3/4] Preparando la base de datos (MySQL de XAMPP debe estar iniciado)...
python scripts\init_db.py || (echo No se pudo conectar a MySQL. Inicie MySQL en el panel de XAMPP. & pause & exit /b 1)
echo [4/4] Iniciando LicoFast en http://localhost:5000
start "" http://localhost:5000
python run.py
pause
