"""
Điểm vào WSGI: `python app.py` hoặc `gunicorn app:app`.
Logic chính nằm trong package `backend`.
"""
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.app import app

__all__ = ['app']

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    host = os.environ.get('APP_HOST', '127.0.0.1')
    logger.info('Chạy cục bộ: http://%s:%s (LAN: đặt APP_HOST=0.0.0.0)', host, port)
    app.run(host=host, port=port, debug=False)
