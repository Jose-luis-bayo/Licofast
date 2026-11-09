"""Punto de entrada: python run.py  →  http://localhost:5000"""
import logging
from app import create_app
from app.config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
app = create_app()

if __name__ == '__main__':
    if Config.JWT_SECRET.startswith('dev-secret'):
        logging.warning('Usando JWT_SECRET de desarrollo. Defina JWT_SECRET en el archivo .env antes de producción.')
    app.run(host='127.0.0.1', port=Config.PORT, debug=Config.DEBUG, use_reloader=False, threaded=True)
