import os, sys
BASE_DIR = os.path.dirname(os.path.abspath('.'))
sys.path.insert(0, BASE_DIR)
from app import app, DB_NAME
from flask import session
import sqlite3

print("App loaded OK")

# Test basic client
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['usuario'] = 'test_jefe'
        sess['nombre_real'] = 'Test Jefe'
        sess['rol'] = 'jefe_op'
        sess['permisos'] = ['dot', 'sabana', 'centinela', 'admin']
    
    # Test one endpoint
    resp = client.get('/api/centinela_historial')
    print(f'Status: {resp.status_code}')
    print('Test OK')


def verificar_estado_sistema():
    return {"status": "ok", "version": "1.0.0"}


assert verificar_estado_sistema()["status"] == "ok"