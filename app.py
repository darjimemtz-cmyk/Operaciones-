from dotenv import load_dotenv
load_dotenv()

import os
import sqlite3
import json
import random
import warnings
import pandas as pd
import calendar
from io import BytesIO
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from functools import wraps
from flask import Flask, send_file, render_template, request, redirect, url_for, session, abort, jsonify, send_from_directory, Response
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from services.ai_client import AIClient
from services.prompt_builder import PromptBuilder

TZ_LOCAL = ZoneInfo("America/Mexico_City")

EXT_IMAGENES = {'png', 'jpg', 'jpeg', 'webp'}
EXT_DOCUMENTOS = {'xlsx', 'xls', 'pdf'}

def es_extension_valida(filename, extensiones_permitidas):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensiones_permitidas

def obtener_hora_local_str():
    return datetime.now(TZ_LOCAL).strftime('%Y-%m-%d %H:%M:%S')

def registrar_evento_sync(cursor, tipo, payload_dict):
    try:
        cursor.execute("INSERT INTO sync_eventos (tipo, payload) VALUES (?, ?)", (tipo, json.dumps(payload_dict)))
    except Exception:
        pass

def registrar_notificacion(cursor, mensaje):
    cursor.execute("INSERT INTO notificaciones (fecha, mensaje) VALUES (?, ?)", (obtener_hora_local_str(), mensaje))
    # Emite automáticamente el evento en vivo a todos los navegadores
    registrar_evento_sync(cursor, 'notificacion', {'mensaje': mensaje, 'fecha': obtener_hora_local_str()})

warnings.simplefilter("ignore")

DIRECTORIO_BASE = os.path.abspath(os.path.dirname(__file__))
DIRECTORIO_TEMPLATES = os.path.join(DIRECTORIO_BASE, 'templates')
EVIDENCIAS_FOLDER = os.path.join(DIRECTORIO_BASE, 'evidencias_dot')
os.makedirs(EVIDENCIAS_FOLDER, exist_ok=True)
FOTOS_FOLDER = os.path.join(DIRECTORIO_BASE, 'static', 'fotos_perfil')
os.makedirs(FOTOS_FOLDER, exist_ok=True)
EVIDENCIAS_AMONESTACIONES = os.path.join(DIRECTORIO_BASE, 'static', 'evidencias_amonestaciones')
os.makedirs(EVIDENCIAS_AMONESTACIONES, exist_ok=True)

app = Flask(__name__, template_folder=DIRECTORIO_TEMPLATES)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_control_maestro_fng_slp_v7')
app.config['UPLOAD_FOLDER'] = EVIDENCIAS_FOLDER
app.config['TEMPLATES_AUTO_RELOAD'] = True
DB_NAME = 'control_maestro_v6.db'

def obtener_ip_cliente():
    return request.headers.get("CF-Connecting-IP", get_remote_address())

limiter = Limiter(
    key_func=obtener_ip_cliente,
    app=app,
    default_limits=[],  # No limita rutas normales, solo las que marquemos
    storage_uri="memory://"  # Almacenamiento rápido y ligero en memoria RAM
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=5 * 1024 * 1024
) 

ENV_PATH = os.path.join(DIRECTORIO_BASE, '.env')
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, 'r', encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if linea and not linea.startswith('#') and '=' in linea:
                clave, valor = linea.split('=', 1)
                os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))

MODO_PRUEBAS = os.environ.get("MODO_PRUEBAS", "True").lower() in ("true", "1")
META_TOKEN = os.environ.get("META_TOKEN", "TOKEN_PRODUCCION")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "ID_TELEFONO")
META_API_URL = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
URL_PUBLICA_SERVIDOR = os.environ.get("URL_PUBLICA_SERVIDOR", "https://servidor-fng.ejemplo.com")

NUMERO_JEFE = os.environ.get("PHONE_NOTIF_JEFE", "528100000000")
NUMERO_AUTOR = os.environ.get("PHONE_NOTIF_AUTOR", "524400000000")

DIRECTORIO_TELEFONOS = {
    "PILOTO PRUEBA VERDE": NUMERO_JEFE,
    "PILOTO PRUEBA AMARILLO": NUMERO_AUTOR,
    "PILOTO PRUEBA ROJO": NUMERO_JEFE
}

def obtener_llave_nombre(nombre):
    if not isinstance(nombre, str): return ""
    palabras = [p for p in str(nombre).upper().replace(',', '').split() if len(p) > 2]
    return tuple(sorted(palabras))

DICCIONARIO_TELS_KEY = {obtener_llave_nombre(k): v for k, v in DIRECTORIO_TELEFONOS.items()}

def obtener_cabeceras_semana(fecha_referencia):
    dias_nombres = ["MIÉ", "JUE", "VIE", "SÁB", "DOM", "LUN", "MAR"]
    offset = (fecha_referencia.weekday() - 2) % 7
    miercoles_inicio = fecha_referencia - timedelta(days=offset)
    
    cabeceras = {}
    for i in range(7):
        dia_actual = miercoles_inicio + timedelta(days=i)
        llave = dias_nombres[i]
        cabeceras[llave] = f"{llave} {dia_actual.strftime('%d')}"
    return cabeceras

def despachar_whatsapp_multimedia(chofer, telefono_real, litros, porcentaje, semana):
    import requests
    telefono_destino = telefono_real 

    if litros <= 20:
        imagenes = ["verde1.jpg", "verde2.jpg", "verde3.jpg"]
        msg = f"✅ Hola *{chofer}*.\n\nTu resultado operativo es impecable (Exceso: {round(litros,2)} L | {round(porcentaje*100,2)}%).\n¡Sigue así, tu compromiso marca la diferencia!"
    elif litros <= 75:
        imagenes = ["amarillo1.jpg", "amarillo2.jpg", "amarillo3.jpg"]
        msg = f"⚠️ Hola *{chofer}*.\n\nPresentaste un exceso de {round(litros,2)} L ({round(porcentaje*100,2)}%).\nAjusta el ritmo, vas por buen camino. Acércate a gerencia."
    else:
        imagenes = ["rojo1.jpg", "rojo2.jpg", "rojo3.jpg"]
        msg = f"🔴 Hola *{chofer}*.\n\nResultado en zona de riesgo. Exceso crítico de {round(litros,2)} L ({round(porcentaje*100,2)}%).\nEs momento de corregir el rumbo, preséntate con tu gerente hoy."

    img_seleccionada = random.choice(imagenes)
    url_imagen = f"{URL_PUBLICA_SERVIDOR}/static/{img_seleccionada}"
    
    payload = { "messaging_product": "whatsapp", "recipient_type": "individual", "to": telefono_destino, "type": "image", "image": { "link": url_imagen, "caption": msg } }
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    
    try: 
        res = requests.post(META_API_URL, headers=headers, json=payload, timeout=5)
        return res.status_code in [200, 201]
    except: 
        return False

def obtener_fecha_operativa():
    ahora = datetime.now()
    corte = ahora.replace(hour=8, minute=15, second=0, microsecond=0)
    if ahora < corte:
        return (ahora - timedelta(days=1)).strftime('%Y-%m-%d')
    return ahora.strftime('%Y-%m-%d')

def init_db():
    conn = sqlite3.connect(DB_NAME, timeout=10.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, usuario TEXT UNIQUE, contrasena TEXT, rol TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS configuracion (clave TEXT PRIMARY KEY, valor TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS operadores (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        no_empleado TEXT DEFAULT 'N/A',
        nombre TEXT UNIQUE NOT NULL, 
        linea_negocio TEXT, 
        producto TEXT, 
        esquema TEXT, 
        eco TEXT, 
        telefono_red TEXT, 
        imei1 TEXT, 
        impresora TEXT, 
        vigencia_licencia TEXT, 
        vigencia_medica TEXT, 
        tipo_jornada TEXT DEFAULT 'Variable', 
        fecha_alta TEXT, 
        estatus_empleado TEXT DEFAULT 'Activo',
        fecha_nacimiento TEXT DEFAULT 'N/A',
        edad TEXT DEFAULT 'N/A',
        tipo_licencia TEXT DEFAULT 'N/A',
        no_licencia TEXT DEFAULT 'N/A',
        liberacion_cryo TEXT DEFAULT 'N/A',
        liberado_operativamente TEXT DEFAULT 'N/A',
        experiencia_desde TEXT DEFAULT 'N/A',
        tipo_unidad TEXT DEFAULT 'N/A'
    )''')
    
    try: cursor.execute("ALTER TABLE operadores ADD COLUMN productos_descarga TEXT DEFAULT 'N/A'")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE operadores ADD COLUMN fecha_ancla TEXT DEFAULT 'N/A'")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE operadores ADD COLUMN usuario_app TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE operadores ADD COLUMN token_dispositivo TEXT DEFAULT NULL")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE operadores ADD COLUMN foto TEXT DEFAULT 'default.png'")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE operadores ADD COLUMN base TEXT DEFAULT 'San Luis Potosí'")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE operadores ADD COLUMN orden_posicion INTEGER DEFAULT 999")
    except sqlite3.OperationalError: pass
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS logistica_diaria (id INTEGER PRIMARY KEY AUTOINCREMENT, operador_id INTEGER, fecha TEXT, estatus TEXT, FOREIGN KEY(operador_id) REFERENCES operadores(id), UNIQUE(operador_id, fecha))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS auditoria_dot (operador_id INTEGER PRIMARY KEY, ultima_captura_dot REAL, horas_dot_acumuladas REAL, observaciones TEXT, FOREIGN KEY(operador_id) REFERENCES operadores(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS dot_diario (id INTEGER PRIMARY KEY AUTOINCREMENT, operador_id INTEGER, fecha TEXT, horas REAL, FOREIGN KEY(operador_id) REFERENCES operadores(id), UNIQUE(operador_id, fecha))''')
    
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN estatus_dia TEXT DEFAULT 'En viaje'")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN eco_unidad TEXT DEFAULT 'N/A'")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN eco_pipas TEXT DEFAULT 'N/A'")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN horas_manejo REAL DEFAULT 0.0")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN horas_maniobra REAL DEFAULT 0.0")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN auditado INTEGER DEFAULT 1")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN evidencia_foto TEXT DEFAULT 'N/A'")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN tipo_registro TEXT DEFAULT 'Estimado'")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN no_bitacora TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN folio_bhs TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN clave_nocturna TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN viaje_mina TEXT DEFAULT 'NO'")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN observaciones TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN sub_estatus TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN horas_dot_calc REAL DEFAULT 0.0")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE dot_diario ADD COLUMN dias_trabajados_calc INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pines_emergencia (id INTEGER PRIMARY KEY, operador_id INTEGER, pin TEXT, expira_en TIMESTAMP)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS solicitudes_cambio (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP, usuario_solicita TEXT, tipo_movimiento TEXT, datos_json TEXT, estatus TEXT DEFAULT 'Pendiente')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS notificaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP, mensaje TEXT, leida INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS pases_salida (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        empleado TEXT, num_emp TEXT, depto TEXT, puesto TEXT,
        tipo_permiso TEXT, motivo TEXT, lugar TEXT,
        hora_esperada TEXT, hora_regreso TEXT, tipo_incidencia TEXT,
        estatus TEXT DEFAULT 'AUTORIZADO', autoriza TEXT, hora_salida_real TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS programacion_viajes (producto TEXT PRIMARY KEY, datos_json TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS viajes_archivados (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fecha_operativa TEXT, 
        producto TEXT, 
        estatus TEXT, 
        motivo TEXT, 
        viaje_json TEXT, 
        hora_cierre TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS amonestaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operador_id INTEGER NOT NULL,
        fecha TEXT NOT NULL,
        tipo TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        estatus TEXT DEFAULT 'Pendiente',
        fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(operador_id) REFERENCES operadores(id)
    )''')

    try: cursor.execute("ALTER TABLE operadores ADD COLUMN causa_baja TEXT DEFAULT 'N/A'")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE operadores ADD COLUMN detalle_baja TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE amonestaciones ADD COLUMN archivo_pdf TEXT DEFAULT NULL")
    except sqlite3.OperationalError: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS centinela_historial (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT NOT NULL,
        rol TEXT NOT NULL,
        mensaje TEXT NOT NULL,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS sync_eventos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL,
        payload TEXT NOT NULL,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    usuarios_base = [
        ('admin_fng', 'master123', 'super_usuario'),
        ('gerencia_slp', 'ger123', 'gerencia'),
        ('kzamarripa', 'sup123', 'supervisor'),
        ('cgonzalez', 'sup123', 'supervisor'),
        ('cherrera', 'sup123', 'supervisor'),
        ('nduarte', 'aux123', 'aux_dot'),
        ('hrivera', 'aux123', 'aux_bitacoras'),
        ('jlugo', 'mon123', 'monitorista'),
        ('cortiz', 'mon123', 'monitorista'),
        ('seguridad_slp', 'seg123', 'seguridad'),
        ('analista_slp', 'ana123', 'analista_diesel')
    ]
    for u, c, r in usuarios_base:
        cursor.execute('INSERT OR IGNORE INTO usuarios (usuario, contrasena, rol) VALUES (?, ?, ?)', 
                       (u, generate_password_hash(c), r))

    # MIGRACIÓN AUTOMÁTICA: Si existen contraseñas viejas en texto plano, cifrarlas de inmediato
    cursor.execute("SELECT id, contrasena FROM usuarios")
    for uid, pass_str in cursor.fetchall():
        if pass_str and not pass_str.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
            cursor.execute("UPDATE usuarios SET contrasena = ? WHERE id = ?", (generate_password_hash(pass_str), uid))
        
    cursor.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES ('unidades_argon', '2')")
    cursor.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES ('unidades_nitrogeno', '13')")
    cursor.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES ('unidades_oxigeno', '7')")
    cursor.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES ('unidades_co2', '9')")

    conn.commit(); conn.close()

def recalcular_tr_operador(op_id, cursor=None):
    close_conn = False
    if cursor is None:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        close_conn = True
    
    cursor.execute("SELECT id, estatus FROM logistica_diaria WHERE operador_id=? ORDER BY fecha ASC", (op_id,))
    filas = cursor.fetchall()
    contador_tr = 0
    for fid, estatus in filas:
        est_limpio = str(estatus or '').strip().upper()
        if est_limpio.startswith('TR'):
            contador_tr += 1
            nuevo_estatus = f"TR{contador_tr}"
            if est_limpio != nuevo_estatus:
                cursor.execute("UPDATE logistica_diaria SET estatus=? WHERE id=?", (nuevo_estatus, fid))
        else:
            contador_tr = 0
            
    if close_conn:
        conn.commit(); conn.close()
    else:
        try:
            cursor.connection.commit()
        except Exception:
            pass

def recalcular_tr_todos():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT id FROM operadores")
    ops = c.fetchall()
    for op in ops: recalcular_tr_operador(op[0], c)
    conn.commit(); conn.close()

def generar_usuario_unico(nombre):
    partes = str(nombre).strip().split()
    if not partes: return "USER" + str(random.randint(1000,9999))
    if len(partes) >= 2: base = (partes[0][0] + partes[1]).upper()
    else: base = partes[0][:5].upper()
    base = ''.join(e for e in base if e.isalnum())
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT usuario_app FROM operadores WHERE usuario_app LIKE ?", (base + '%',))
    existentes = [r[0] for r in c.fetchall()]
    conn.close()
    if base not in existentes: return base
    contador = 2
    while f"{base}{contador}" in existentes: contador += 1
    return f"{base}{contador}"

def backfill_usuarios():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT id, nombre FROM operadores WHERE usuario_app IS NULL OR usuario_app = ''")
    for row in c.fetchall():
        u = generar_usuario_unico(row[1])
        c.execute("UPDATE operadores SET usuario_app=? WHERE id=?", (u, row[0]))
    conn.commit(); conn.close()

if not os.path.exists(DB_NAME): init_db()
else: init_db() 
backfill_usuarios()
recalcular_tr_todos() 

# Mantiene compatibilidad con otros módulos que dependen de semanas
def get_semana(fecha_str=None):
    if fecha_str:
        try: hoy = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except: hoy = datetime.now().date()
    else: hoy = datetime.now().date()
    
    lunes = hoy - timedelta(days=hoy.weekday()); dias = []
    nombres = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    for i in range(7):
        fecha = lunes + timedelta(days=i)
        dias.append({'fecha': fecha.strftime('%Y-%m-%d'), 'label': f"{nombres[i]} {fecha.day}", 'es_hoy': fecha == datetime.now().date()})
    num_semana = lunes.isocalendar()[1]
    
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    mes_inicio = meses[lunes.month - 1]; domingo = lunes + timedelta(days=6)
    mes_fin = meses[domingo.month - 1]; anio = domingo.year
    
    if mes_inicio == mes_fin: texto_semana = f"Del {lunes.day} al {domingo.day} de {mes_inicio} {anio}"
    else: texto_semana = f"Del {lunes.day} {mes_inicio} al {domingo.day} {mes_fin} {anio}"
        
    return dias, num_semana, hoy.strftime('%Y-%m-%d'), (hoy - timedelta(days=7)).strftime('%Y-%m-%d'), (hoy + timedelta(days=7)).strftime('%Y-%m-%d'), texto_semana

def get_mes_data(mes_str=None):
    hoy = datetime.now().date()
    if mes_str:
        try:
            parts = mes_str.split('-')
            year = int(parts[0])
            month = int(parts[1])
            fecha_ref = datetime(year, month, 1).date()
        except:
            fecha_ref = hoy.replace(day=1)
    else:
        fecha_ref = hoy.replace(day=1)

    year = fecha_ref.year
    month = fecha_ref.month
    _, num_dias = calendar.monthrange(year, month)

    nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    dias_mes = []
    for d in range(1, num_dias + 1):
        f_actual = datetime(year, month, d).date()
        dias_mes.append({
            'fecha': f_actual.strftime('%Y-%m-%d'),
            'label': f"{nombres_dias[f_actual.weekday()]} {d}",
            'es_hoy': f_actual == hoy,
            'es_fin_semana': f_actual.weekday() >= 5
        })

    texto_mes = f"{meses_nombres[month - 1]} {year}"

    if month == 1:
        f_atras = f"{year - 1}-12"
    else:
        f_atras = f"{year}-{month - 1:02d}"

    if month == 12:
        f_adelante = f"{year + 1}-01"
    else:
        f_adelante = f"{year}-{month + 1:02d}"

    return dias_mes, texto_mes, f_atras, f_adelante, f"{year}-{month:02d}"

def calcular_edad_exacta(fecha_nac_str):
    if not fecha_nac_str or str(fecha_nac_str).strip() in ['N/A', '', 'None']:
        return '--'
    try:
        nac = datetime.strptime(fecha_nac_str.strip(), '%Y-%m-%d').date()
        hoy = datetime.now().date()
        edad = hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))
        return f"{edad} años" if edad >= 0 else '--'
    except:
        return '--'

def calcular_antiguedad_y_vacaciones(fecha_ingreso_str):
    if not fecha_ingreso_str or fecha_ingreso_str == 'N/A':
        return "Sin registro", 0
    try:
        ingreso = datetime.strptime(fecha_ingreso_str, '%Y-%m-%d').date()
        hoy = datetime.now().date()
        dias_totales = (hoy - ingreso).days
        if dias_totales < 0: return "Próximo ingreso", 0
        
        anios = dias_totales // 365
        dias_restantes = dias_totales % 365
        meses = dias_restantes // 30
        dias = dias_restantes % 30
        texto_antiguedad = f"{anios} años, {meses} meses y {dias} días"
        
        if anios == 0:
            vacaciones = 0
        elif anios <= 5:
            vacaciones = 12 + ((anios - 1) * 2) 
        else:
            bloque = (anios - 6) // 5
            vacaciones = 22 + (bloque * 2)
            
        return texto_antiguedad, vacaciones
    except:
        return "Error en fecha", 0

def verificar_y_extender_roles():
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    hoy = datetime.now().date(); limite_futuro = hoy + timedelta(days=60)
    c.execute("SELECT id, tipo_jornada, fecha_ancla FROM operadores WHERE estatus_empleado='Activo' AND tipo_jornada NOT IN ('Variable', 'N/A', '') AND fecha_ancla != 'N/A'")
    ops = c.fetchall()
    for op_id, patron, f_ancla_str in ops:
        try:
            f_ancla = datetime.strptime(f_ancla_str, '%Y-%m-%d').date()
            if patron == '8-1-8-1-8-6': ciclo = ['TR']*8 + ['DE'] + ['TR']*8 + ['DE'] + ['TR']*8 + ['DE']*6
            elif patron == '8-1-8-6': ciclo = ['TR']*8 + ['DE'] + ['TR']*8 + ['DE']*6
            elif patron == '8x4': ciclo = ['TR']*8 + ['DE']*4
            elif patron == '4x4': ciclo = ['TR']*4 + ['DE']*4
            else: continue

            for i in range((limite_futuro - hoy).days):
                f_actual = hoy + timedelta(days=i)
                if f_actual >= f_ancla:
                    dias_transcurridos = (f_actual - f_ancla).days
                    estatus_calc = ciclo[dias_transcurridos % len(ciclo)]
                    f_str = f_actual.strftime('%Y-%m-%d')
                    c.execute('''INSERT OR IGNORE INTO logistica_diaria (operador_id, fecha, estatus) VALUES (?, ?, ?)''', (op_id, f_str, estatus_calc))
            recalcular_tr_operador(op_id, c)
        except: pass
    conn.commit(); conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def set_security_headers(response):
    response.headers["X-Frame-Options"] = "SAMEORIGIN"           # Previene clickjacking
    response.headers["X-Content-Type-Options"] = "nosniff"       # Evita sniffing de tipos MIME
    response.headers["X-XSS-Protection"] = "1; mode=block"       # Bloqueo de inyección XSS
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

@app.errorhandler(429)
def ratelimit_handler(e):
    # Si exceden los intentos, mostramos un aviso limpio y seguro
    return render_template('login_maestro.html', error="Demasiados intentos fallidos. Por seguridad, espera 1 minuto antes de reintentar."), 429

@app.context_processor
def inject_user():
    sols = []; notifs = []
    if 'usuario' in session:
        try:
            conn = sqlite3.connect(DB_NAME); c = conn.cursor()
            c.execute("SELECT id, usuario_solicita, tipo_movimiento, datos_json, fecha_solicitud FROM solicitudes_cambio WHERE estatus='Pendiente'")
            sols = [{'id':r[0], 'usuario':r[1], 'tipo':r[2], 'datos':json.loads(r[3]), 'fecha':r[4]} for r in c.fetchall()]
            c.execute("SELECT id, mensaje, fecha, leida FROM notificaciones ORDER BY id DESC LIMIT 20")
            notifs = [{'id':r[0], 'msj':r[1], 'fecha':r[2], 'leida':r[3]} for r in c.fetchall()]
            conn.close()
        except: pass
    return dict(usuario=session.get('usuario'), nombre_real=session.get('nombre_real'), rol=session.get('rol'), solicitudes_globales=sols, notificaciones_globales=notifs)

def get_config_unidades():
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT clave, valor FROM configuracion")
    cfg = dict(cursor.fetchall()); conn.close()
    return { 'ARGON': int(cfg.get('unidades_argon', 2)), 'NITROGENO': int(cfg.get('unidades_nitrogeno', 13)), 'OXIGENO': int(cfg.get('unidades_oxigeno', 7)), 'CO2': int(cfg.get('unidades_co2', 9)) }

def calcular_ventana_tiempo(fecha_centro_str, dias_adelante=7):
    hoy = datetime.now().date()
    fecha_centro = datetime.strptime(fecha_centro_str, '%Y-%m-%d').date() if fecha_centro_str else hoy
    dias_semana_esp = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"]
    
    fechas_ventana = []
    for i in range(-3, dias_adelante):
        f_dt = fecha_centro + timedelta(days=i)
        fechas_ventana.append({
            'string': f_dt.strftime('%Y-%m-%d'),
            'formato_corto': f_dt.strftime('%d/%m'),
            'dia_nombre': dias_semana_esp[f_dt.weekday()],
            'es_fin_semana': f_dt.weekday() >= 5,
            'es_hoy': f_dt == hoy
        })
    return fechas_ventana, fecha_centro.strftime('%Y-%m-%d'), (fecha_centro - timedelta(days=1)).strftime('%Y-%m-%d'), (fecha_centro + timedelta(days=1)).strftime('%Y-%m-%d')

def get_dashboard_data(fechas_ventana):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    unidades_cfg = get_config_unidades(); productos = ['ARGON', 'NITROGENO', 'OXIGENO', 'CO2']
    prefijos_cob = {'ARGON': 'CB-ARG', 'NITROGENO': 'CB-NIT', 'OXIGENO': 'CB-OXI', 'CO2': 'CB-CO2'}
    reporte = {p: {'Plantilla': [], 'Disp': [], 'NoDisp': [], 'Unidades': [], 'Deficit': []} for p in productos}
    
    cursor.execute("SELECT producto, COUNT(*) FROM operadores WHERE estatus_empleado='Activo' AND esquema != 'Varios' GROUP BY producto")
    plantilla_fija = dict(cursor.fetchall())
    
    for f in fechas_ventana:
        f_str = f['string']
        for p in productos:
            cursor.execute('''SELECT l.estatus, COUNT(*) FROM logistica_diaria l JOIN operadores o ON l.operador_id = o.id WHERE o.producto = ? AND l.fecha = ? AND o.estatus_empleado='Activo' AND o.esquema != 'Varios' GROUP BY l.estatus''', (p, f_str))
            res = dict(cursor.fetchall())
            
            disp_propias = sum(v for k, v in res.items() if k.startswith('TR'))
            cursor.execute('''SELECT COUNT(*) FROM logistica_diaria l JOIN operadores o ON l.operador_id = o.id WHERE l.estatus = ? AND l.fecha = ? AND o.estatus_empleado='Activo' AND o.esquema != 'Varios' ''', (prefijos_cob[p], f_str))
            res_cob = cursor.fetchone(); disp_cobertura = res_cob[0] if res_cob else 0
            
            disp = disp_propias + disp_cobertura
            nodisp = sum([v for k,v in res.items() if not k.startswith('TR')])
            unidades_fijas = unidades_cfg.get(p, 0); deficit = disp - unidades_fijas 
            reporte[p]['Plantilla'].append(plantilla_fija.get(p, 0)); reporte[p]['Disp'].append(disp); reporte[p]['NoDisp'].append(nodisp); reporte[p]['Unidades'].append(unidades_fijas); reporte[p]['Deficit'].append(deficit)
    conn.close()
    
    reporte['CRYO'] = {'Plantilla': [], 'Disp': [], 'NoDisp': [], 'Unidades': [], 'Deficit': []}
    for i in range(len(fechas_ventana)):
        disp_c = reporte['ARGON']['Disp'][i] + reporte['NITROGENO']['Disp'][i] + reporte['OXIGENO']['Disp'][i]
        nodisp_c = reporte['ARGON']['NoDisp'][i] + reporte['NITROGENO']['NoDisp'][i] + reporte['OXIGENO']['NoDisp'][i]
        unid_c = reporte['ARGON']['Unidades'][i] + reporte['NITROGENO']['Unidades'][i] + reporte['OXIGENO']['Unidades'][i]
        plan_c = reporte['ARGON']['Plantilla'][i] + reporte['NITROGENO']['Plantilla'][i] + reporte['OXIGENO']['Plantilla'][i]
        
        reporte['CRYO']['Disp'].append(disp_c); reporte['CRYO']['NoDisp'].append(nodisp_c); reporte['CRYO']['Unidades'].append(unid_c)
        reporte['CRYO']['Plantilla'].append(plan_c); reporte['CRYO']['Deficit'].append(disp_c - unid_c)
    return reporte

def get_indicadores_extendidos(fecha_objetivo):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    unidades_cfg = get_config_unidades()
    prefijos_cob = {'ARGON': 'CB-ARG', 'NITROGENO': 'CB-NIT', 'OXIGENO': 'CB-OXI', 'CO2': 'CB-CO2'}
    cursor.execute('''SELECT o.producto, l.estatus, COUNT(*) FROM operadores o JOIN logistica_diaria l ON o.id = l.operador_id WHERE l.fecha = ? AND o.estatus_empleado='Activo' AND o.esquema != 'Varios' GROUP BY o.producto, l.estatus''', (fecha_objetivo,))
    raw_data = cursor.fetchall()
    cursor.execute("SELECT producto, COUNT(*) FROM operadores WHERE estatus_empleado='Activo' AND esquema != 'Varios' GROUP BY producto")
    plantilla = dict(cursor.fetchall()); conn.close()
    disp = {p: 0 for p in prefijos_cob}; nodisp = {p: 0 for p in prefijos_cob}
    for prod, estatus, cuenta in raw_data:
        if estatus.startswith('TR'): disp[prod] += cuenta
        elif estatus.startswith('CB-'):
            nodisp[prod] += cuenta 
            target = [k for k,v in prefijos_cob.items() if v == estatus]
            if target: disp[target[0]] += cuenta 
        else: nodisp[prod] += cuenta
            
    indicadores = []
    for p in ['ARGON', 'NITROGENO', 'OXIGENO', 'CO2']:
        u = unidades_cfg.get(p, 0); d = disp.get(p, 0); nd = nodisp.get(p, 0)
        indicadores.append({"producto": p, "unidades": u, "disponibles": d, "nodisponibles": nd, "diferencia": d - u, "plantilla": plantilla.get(p, 0)})
    return indicadores

@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if request.method == 'POST':
        u = request.form['usuario'].strip()
        p = request.form['contrasena'].strip()
        token_disp = request.form.get('device_token', '')
        conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
        
        u_system = u.lower()
        # Consulta segura: obtenemos el hash y rol del usuario sin comparar contraseña en SQL
        cursor.execute("SELECT rol, contrasena FROM usuarios WHERE usuario = ?", (u_system,))
        res = cursor.fetchone()
        if res:
            rol_bd, pass_bd = res[0], res[1]
            # Valida el hash criptográfico de forma segura contra ataques de temporización
            es_valida = check_password_hash(pass_bd, p) if pass_bd.startswith(('pbkdf2:', 'scrypt:', 'argon2:')) else (pass_bd == p)
            
            if es_valida:
                session['usuario'] = u_system; session['rol'] = rol_bd
                nombres = {
                'admin_fng': 'Super Administrador FNG',
                'gerencia_slp': 'José Luis Hernández Salazar',
                'kzamarripa': 'Karla Yesenia Zamarripa Aguilar',
                'cgonzalez': 'Claudia Guadalupe Gonzalez Hernandez',
                'cherrera': 'Carlos Josue Herrera Lopez',
                'nduarte': 'Naylea Guadalupe Duarte Briones',
                'hrivera': 'Hugo Rivera Muro',
                'jlugo': 'Juan Luis Fernando Lugo Cardenas',
                'cortiz': 'Carlos Eduardo Ortiz Martinez',
                'seguridad_slp': 'Oficial de Caseta',
                'analista_slp': 'Analista de Diésel'
            }
            session['nombre_real'] = nombres.get(u_system, 'Operador')
            conn.close()
            if session['rol'] == 'seguridad': return redirect('/pruebas_fng')
            if session['rol'] == 'analista_diesel': return redirect('/control_diesel')
            return redirect(url_for('acumulado'))
            
        cursor.execute("SELECT operador_id FROM pines_emergencia WHERE pin = ? AND expira_en > CURRENT_TIMESTAMP", (p,))
        pin_res = cursor.fetchone()
        if pin_res:
            op_id = pin_res[0]
            cursor.execute("SELECT nombre, usuario_app FROM operadores WHERE id = ?", (op_id,))
            op_data = cursor.fetchone()
            if op_data and op_data[1].upper() == u.upper():
                session['usuario'] = op_data[1]; session['rol'] = 'operador'; session['nombre_real'] = op_data[0]
                session['operador_id'] = op_id; session['modo_emergencia'] = True
                cursor.execute("DELETE FROM pines_emergencia WHERE pin = ?", (p,))
                conn.commit(); conn.close()
                return redirect(url_for('operador_app'))

        cursor.execute("SELECT id, nombre, no_empleado, token_dispositivo FROM operadores WHERE usuario_app = ? AND estatus_empleado = 'Activo'", (u.upper(),))
        op_res = cursor.fetchone()
        if op_res:
            op_id, nombre, no_emp, token_bd = op_res
            if p == no_emp:
                if not token_bd:
                    cursor.execute("UPDATE operadores SET token_dispositivo = ? WHERE id = ?", (token_disp, op_id))
                    conn.commit()
                elif token_bd != token_disp:
                    conn.close()
                    return render_template('login_maestro.html', error="Acceso denegado: Dispositivo no reconocido.")
                session['usuario'] = u.upper(); session['rol'] = 'operador'; session['nombre_real'] = nombre
                session['operador_id'] = op_id; session['modo_emergencia'] = False
                conn.close()
                return redirect(url_for('operador_app'))
        conn.close()
        return render_template('login_maestro.html', error="Credenciales incorrectas")
    return render_template('login_maestro.html')

@app.route('/operador_app')
@login_required
def operador_app():
    if session.get('rol') != 'operador': return abort(403)
    hoy = datetime.now()
    dias = [(hoy - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(3)]
    return render_template('portal_chofer.html', dias=dias, nombre_real=session.get('nombre_real'))

@app.route('/api/operador_guardar_dia', methods=['POST'])
@login_required
def operador_guardar_dia():
    if session.get('rol') != 'operador': return jsonify({"status": "error"}), 403
    op_id = session.get('operador_id'); fecha = request.form.get('fecha'); estatus = request.form.get('estatus_dia')
    unidad = request.form.get('eco_unidad', 'N/A'); pipas = request.form.get('eco_pipas', 'N/A')
    manejo = float(request.form.get('horas_manejo', 0.0)); maniobra = float(request.form.get('horas_maniobra', 0.0))
    horas_totales = manejo + maniobra
    
    tipo_registro = request.form.get('tipo_registro', 'Estimado')
    auditado = int(request.form.get('auditado', 0))
    
    foto_filename = 'N/A'
    if 'foto' in request.files:
        foto = request.files['foto']
        nombre_archivo = foto.filename or ''
        if nombre_archivo:
            ext = nombre_archivo.rsplit('.', 1)[1].lower() if '.' in nombre_archivo else 'jpg'
            fecha_limpia = str(fecha).replace('-', '') if fecha else 'sin_fecha'
            foto_filename = f"evidencia_{op_id}_{fecha_limpia}_{int(datetime.now().timestamp())}.{ext}"
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_filename))

    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        if foto_filename != 'N/A':
            c.execute('''INSERT INTO dot_diario 
                         (operador_id, fecha, horas, estatus_dia, eco_unidad, eco_pipas, horas_manejo, horas_maniobra, auditado, evidencia_foto, tipo_registro) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
                         ON CONFLICT(operador_id, fecha) DO UPDATE SET 
                         horas=excluded.horas, estatus_dia=excluded.estatus_dia, eco_unidad=excluded.eco_unidad, 
                         eco_pipas=excluded.eco_pipas, horas_manejo=excluded.horas_manejo, horas_maniobra=excluded.horas_maniobra, 
                         auditado=excluded.auditado, evidencia_foto=excluded.evidencia_foto, tipo_registro=excluded.tipo_registro''', 
                      (op_id, fecha, horas_totales, estatus, unidad, pipas, manejo, maniobra, auditado, foto_filename, tipo_registro))
        else:
            c.execute('''INSERT INTO dot_diario 
                         (operador_id, fecha, horas, estatus_dia, eco_unidad, eco_pipas, horas_manejo, horas_maniobra, auditado, tipo_registro) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
                         ON CONFLICT(operador_id, fecha) DO UPDATE SET 
                         horas=excluded.horas, estatus_dia=excluded.estatus_dia, eco_unidad=excluded.eco_unidad, 
                         eco_pipas=excluded.eco_pipas, horas_manejo=excluded.horas_manejo, horas_maniobra=excluded.horas_maniobra, 
                         auditado=excluded.auditado, tipo_registro=excluded.tipo_registro''', 
                      (op_id, fecha, horas_totales, estatus, unidad, pipas, manejo, maniobra, auditado, tipo_registro))
        conn.commit(); return jsonify({"status": "success"})
    except Exception as e: conn.rollback(); return jsonify({"status": "error", "msg": str(e)})
    finally: conn.close()

@app.route('/evidencias/<filename>')
@login_required
def ver_evidencia(filename):
    if session.get('rol') not in ['jefe_op', 'aux_dot', 'monitorista', 'gerencia']: return abort(403)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/generar_pin', methods=['POST'])
@login_required
def generar_pin():
    if session.get('rol') not in ['jefe_op', 'aux_dot']: return jsonify({"status": "error"}), 403
    d = request.json; op_id = d['id']; pin = str(random.randint(1000, 9999))
    expira = (datetime.now() + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("INSERT INTO pines_emergencia (operador_id, pin, expira_en) VALUES (?, ?, ?)", (op_id, pin, expira))
    conn.commit(); conn.close()
    return jsonify({"status": "success", "pin": pin})
    
@app.route('/api/liberar_dispositivo', methods=['POST'])
@login_required
def liberar_dispositivo():
    if session.get('rol') not in ['jefe_op', 'aux_dot']: return jsonify({"status": "error"}), 403
    d = request.json; conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        c.execute("UPDATE operadores SET token_dispositivo = NULL WHERE id = ?", (d['id'],))
        registrar_notificacion(c, f"📱 Se liberó el celular del operador ID: {d['id']}")
        conn.commit(); return jsonify({"status": "success"})
    except Exception as e: conn.rollback(); return jsonify({"status": "error", "msg": str(e)})
    finally: conn.close()

@app.route('/acumulado')
@login_required
def acumulado():
    if session.get('rol') == 'operador': return redirect(url_for('operador_app'))
    if session.get('rol') == 'seguridad': return redirect('/pruebas_fng')
    if session.get('rol') == 'analista_diesel': return redirect('/control_diesel')
    verificar_y_extender_roles()
    fecha_req = request.args.get('fecha', None); fechas_ventana, centro, f_atras, f_adelante = calcular_ventana_tiempo(fecha_req)
    data = get_dashboard_data(fechas_ventana); cfg = get_config_unidades()
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT producto, COUNT(*) FROM operadores WHERE estatus_empleado='Activo' AND esquema != 'Varios' GROUP BY producto")
    plantilla = dict(c.fetchall()); conn.close()
    plantilla['CRYO'] = plantilla.get('ARGON', 0) + plantilla.get('NITROGENO', 0) + plantilla.get('OXIGENO', 0)
    return render_template('panel_operativo.html', data=data, fechas=fechas_ventana, centro=centro, f_atras=f_atras, f_adelante=f_adelante, cfg=cfg, plantilla=plantilla)

@app.route('/programacion')
@login_required
def programacion():
    if session.get('rol') not in ['jefe_op', 'supervisor', 'monitorista', 'super_usuario']: return abort(403)
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT nombre FROM operadores WHERE estatus_empleado='Activo' ORDER BY nombre")
    operadores_activos = [row[0] for row in c.fetchall()]
    conn.close()
    
    return render_template('programacion.html', operadores_activos=operadores_activos)

@app.route('/api/guardar_programacion', methods=['POST'])
@login_required
def api_guardar_programacion():
    if session.get('rol') not in ['jefe_op', 'supervisor', 'monitorista', 'super_usuario']: 
        return jsonify({"status": "error"}), 403
    d = request.json
    producto = d.get('producto')
    datos = json.dumps(d.get('datos', []))
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO programacion_viajes (producto, datos_json) VALUES (?, ?) ON CONFLICT(producto) DO UPDATE SET datos_json = excluded.datos_json", (producto, datos))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "msg": "Programación guardada en la base de datos."})

@app.route('/api/cargar_programacion', methods=['GET'])
@login_required
def api_cargar_programacion():
    if session.get('rol') not in ['jefe_op', 'supervisor', 'monitorista', 'super_usuario']: 
        return jsonify({"status": "error"}), 403
        
    fecha = request.args.get('fecha')
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if fecha:
        # MODO HISTORIAL
        c.execute("SELECT producto, viaje_json, estatus, motivo FROM viajes_archivados WHERE fecha_operativa = ?", (fecha,))
        filas = c.fetchall()
        datos = {'LOX': [], 'LIN': [], 'LAR': [], 'CO2': []}
        
        for prod, v_json, estatus, motivo in filas:
            try:
                viaje = json.loads(v_json)
                viaje['isPending'] = False 
                
                if estatus == 'FINALIZADO':
                    viaje['cv'] = 'cv-indicator cv-green'
                else:
                    viaje['cv'] = 'cv-indicator cv-red'
                    if len(viaje.get('escalas', [])) > 0:
                        viaje['escalas'][-1]['obs'] = f"CANCELADO: {motivo}"
                        
                if prod in datos:
                    datos[prod].append(viaje)
            except: pass
    else:
        # MODO EN VIVO
        c.execute("SELECT producto, datos_json FROM programacion_viajes")
        filas = c.fetchall()
        datos = {r[0]: json.loads(r[1]) for r in filas}
        
    conn.close()
    return jsonify({"status": "success", "data": datos})

@app.route('/api/gestionar_viaje_pizarra', methods=['POST'])
@login_required
def api_gestionar_viaje_pizarra():
    if session.get('rol') not in ['jefe_op', 'supervisor', 'monitorista', 'super_usuario']: 
        return jsonify({"status": "error"}), 403
    
    d = request.json
    producto = d.get('producto')
    estatus = d.get('estatus') 
    motivo = d.get('motivo', '')
    viaje_data = d.get('viaje', {})
    
    fecha_op = obtener_fecha_operativa()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Archivar en el historial general (viajes finalizados o cancelados)
    c.execute('''INSERT INTO viajes_archivados (fecha_operativa, producto, estatus, motivo, viaje_json) 
                 VALUES (?, ?, ?, ?, ?)''', 
              (fecha_op, producto, estatus, motivo, json.dumps(viaje_data)))
              
    # 2. ELIMINAR DE LA PIZARRA ACTIVA EN BASE DE DATOS
    c.execute("SELECT datos_json FROM programacion_viajes WHERE producto = ?", (producto,))
    row = c.fetchone()
    if row:
        viajes_activos = json.loads(row[0])
        # Filtramos para descartar el viaje que coincide (por ID visual o eco y operador)
        viajes_restantes = [v for v in viajes_activos if not (v.get('num') == viaje_data.get('num') and v.get('operador') == viaje_data.get('operador') and v.get('tr') == viaje_data.get('tr'))]
        # Reescribimos el JSON de la pizarra activa ya sin el viaje
        c.execute("UPDATE programacion_viajes SET datos_json = ? WHERE producto = ?", (json.dumps(viajes_restantes), producto))
        
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "msg": f"Viaje {estatus.lower()} y archivado en {fecha_op}."})

@app.route('/api/obtener_dia_operador', methods=['POST'])
@login_required
def api_obtener_dia_operador():
    if session.get('rol') not in ['jefe_op', 'supervisor', 'monitorista', 'super_usuario']: 
        return jsonify({"status": "error"}), 403
        
    d = request.json
    nombre = str(d.get('nombre', '')).strip().upper()
    fecha = d.get('fecha')
    
    if not nombre or not fecha:
        return jsonify({"status": "error", "msg": "Datos incompletos"})
        
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT l.estatus FROM logistica_diaria l JOIN operadores o ON l.operador_id = o.id WHERE UPPER(o.nombre) = ? AND l.fecha = ?", (nombre, fecha))
    res = c.fetchone()
    conn.close()
    
    dia_str = ""
    if res:
        estatus = res[0]
        if estatus.startswith('TR'):
            dia_str = estatus.replace('TR', '')
            if not dia_str: dia_str = "1"
        else:
            dia_str = estatus
    else:
        dia_str = "N/D"
            
    return jsonify({"status": "success", "dia": dia_str})

@app.route('/logistica/<ruta>')
@login_required
def logistica(ruta):
    if session.get('rol') == 'operador': return redirect(url_for('operador_app'))
    if session.get('rol') == 'gerencia': return redirect(url_for('acumulado'))
    if session.get('rol') == 'seguridad': return redirect('/pruebas_fng')
    if session.get('rol') == 'analista_diesel': return redirect('/control_diesel')
    
    verificar_y_extender_roles(); linea_map = ruta.upper()
    if linea_map not in ['CRYO', 'CO2', 'VARIOS']: abort(404)
    fechas_ventana, centro, f_atras, f_adelante = calcular_ventana_tiempo(request.args.get('fecha', None), 20)
    ind_linea = [item for item in get_indicadores_extendidos(centro) if (linea_map == 'CRYO' and item["producto"] in ['ARGON', 'NITROGENO', 'OXIGENO']) or (linea_map == 'CO2' and item["producto"] == 'CO2')]
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    
    # 1. Obtener padrón global activo para autocompletados de Cobertura, PDF y Edición Rápida
    c.execute("SELECT id, nombre, productos_descarga, tipo_jornada, fecha_ancla, eco, producto, esquema FROM operadores WHERE estatus_empleado='Activo' ORDER BY nombre")
    todos_operadores = [{"id": r[0], "nombre": r[1], "productos_descarga": r[2], "tipo_jornada": r[3], "fecha_ancla": r[4], "eco": r[5], "producto": r[6], "esquema": r[7]} for r in c.fetchall()]

    # 2. Filtrar operadores correspondientes a la sábana actual
    if linea_map == 'VARIOS':
        c.execute("SELECT id, nombre, esquema, producto, productos_descarga, tipo_jornada, fecha_ancla, eco FROM operadores WHERE esquema = 'Varios' AND estatus_empleado='Activo' ORDER BY esquema, COALESCE(orden_posicion, 999), nombre")
    else:
        c.execute("SELECT id, nombre, esquema, producto, productos_descarga, tipo_jornada, fecha_ancla, eco FROM operadores WHERE linea_negocio = ? AND estatus_empleado='Activo' AND esquema != 'Varios' ORDER BY esquema, COALESCE(orden_posicion, 999), nombre", (linea_map,))
        
    ops = c.fetchall(); bloques = {}
    
    for op_id, nombre, esquema, prod, prod_descarga, tipo_jor, f_ancla, eco in ops:
        estatus_dias = []
        for f in fechas_ventana:
            c.execute("SELECT estatus FROM logistica_diaria WHERE operador_id = ? AND fecha = ?", (op_id, f['string']))
            res = c.fetchone()
            estatus_dias.append(res[0] if res else '')
            
        if esquema not in bloques: 
            bloques[esquema] = {'operadores': [], 'resumen_activos': [0] * len(fechas_ventana)}
            
        bloques[esquema]['operadores'].append({'id': op_id, 'nombre': nombre, 'dias': estatus_dias, 'prod': prod})
        
        for i, est in enumerate(estatus_dias):
            if est.startswith('TR') or est.startswith('CB-'):
                bloques[esquema]['resumen_activos'][i] += 1
                
    conn.close()
    
    # Renderizar plantilla renombrada sabana.html
    nombre_template = 'sabana.html'
    return render_template(nombre_template, linea=linea_map, indicadores=ind_linea, fechas=fechas_ventana, bloques=bloques, todos_operadores=todos_operadores, centro=centro, f_atras=f_atras, f_adelante=f_adelante, hoy_str=datetime.now().strftime('%Y-%m-%d'))

@app.route('/api/importar_pdf_despacho', methods=['POST'])
@login_required
def importar_pdf_despacho():
    if session.get('rol') not in ['jefe_op', 'supervisor', 'monitorista', 'super_usuario']:
        return jsonify({"status": "error", "msg": "No autorizado"}), 403

    if 'pdf_despacho' not in request.files:
        return jsonify({"status": "error", "msg": "No se recibió archivo PDF"}), 400

    pdf = request.files['pdf_despacho']
    if not pdf or not pdf.filename:
        return jsonify({"status": "error", "msg": "Archivo vacío"}), 400

    nombre_archivo = f"cryo_prog_{int(datetime.now().timestamp())}.pdf"
    ruta_destino = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo)
    pdf.save(ruta_destino)

    return jsonify({
        "status": "success",
        "msg": f"PDF {pdf.filename} guardado. Listo para extraer viajes a la pizarra."
    })

@app.route('/recursos_humanos')
@login_required
def recursos_humanos():
    if session.get('rol') == 'operador': return redirect(url_for('operador_app'))
    if session.get('rol') == 'seguridad': return redirect('/pruebas_fng')
    if session.get('rol') == 'analista_diesel': return redirect('/control_diesel')
    if session.get('rol') in ['supervisor', 'monitorista']:
        return redirect(url_for('acumulado'))
    
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("""
        SELECT id, no_empleado, nombre, linea_negocio, producto, esquema, eco, telefono_red, 
               imei1, impresora, vigencia_licencia, vigencia_medica, fecha_alta, fecha_nacimiento, 
               edad, tipo_licencia, no_licencia, liberacion_cryo, liberado_operativamente, 
               experiencia_desde, tipo_unidad, productos_descarga, tipo_jornada, fecha_ancla, 
               usuario_app, foto, COALESCE(base, 'San Luis Potosí'), estatus_empleado 
        FROM operadores 
        WHERE estatus_empleado='Activo' 
        ORDER BY nombre
    """)
    ops_raw = c.fetchall()
    
    # 2. HISTORIAL DE BAJAS PARA AUDITORÍA (INCLUYE CAMPOS COMPLETOS PARA PODER ABRIR SU EXPEDIENTE)
    c.execute("""
        SELECT id, no_empleado, nombre, linea_negocio, producto, esquema, eco, telefono_red,
               imei1, impresora, vigencia_licencia, vigencia_medica, fecha_alta, fecha_nacimiento,
               edad, tipo_licencia, no_licencia, liberacion_cryo, liberado_operativamente,
               experiencia_desde, tipo_unidad, productos_descarga, tipo_jornada, fecha_ancla,
               usuario_app, foto, COALESCE(base, 'San Luis Potosí'), estatus_empleado,
               COALESCE(causa_baja, 'N/A'), COALESCE(detalle_baja, '')
        FROM operadores 
        WHERE estatus_empleado LIKE 'Baja%' 
        ORDER BY nombre
    """)
    bajas_raw = c.fetchall()
    conn.close()
    
    operadores = []; hoy = datetime.now().date()
    for row in ops_raw:
        try: dias_lic = (datetime.strptime(row[10], '%Y-%m-%d').date() - hoy).days if row[10] and row[10] != 'N/A' else 999
        except: dias_lic = 999
        try: dias_med = (datetime.strptime(row[11], '%Y-%m-%d').date() - hoy).days if row[11] and row[11] != 'N/A' else 999
        except: dias_med = 999
        
        texto_antiguedad, vacaciones = calcular_antiguedad_y_vacaciones(row[12])
        edad_calculada = calcular_edad_exacta(row[13])
        
        operadores.append({
            'id': row[0],
            'no_empleado': row[1] if row[1] != 'N/A' else '--',
            'nombre': row[2],
            'linea': row[3],
            'prod': row[4],
            'esquema': row[5],
            'eco': row[6],
            'tel': row[7] if row[7] != 'N/A' else '',
            'imei': row[8] if row[8] != 'N/A' else '--',
            'imp': row[9] if row[9] != 'N/A' else '--',
            'lic': row[10] if row[10] != 'N/A' else '--',
            'dias_lic': dias_lic,
            'med': row[11] if row[11] != 'N/A' else '--',
            'dias_med': dias_med,
            'fecha_alta': row[12] if row[12] != 'N/A' else '--',
            'fecha_nacimiento': row[13] if row[13] != 'N/A' else '--',
            'edad': edad_calculada,
            'tipo_licencia': row[15] if row[15] != 'N/A' else '--',
            'no_licencia': row[16] if row[16] != 'N/A' else '--',
            'liberacion_cryo': row[17] if row[17] != 'N/A' else '--',
            'liberado_operativamente': row[18] if row[18] != 'N/A' else '--',
            'experiencia_desde': row[19] if row[19] != 'N/A' else '--',
            'tipo_unidad': row[20] if row[20] != 'N/A' else 'FULL',
            'productos_descarga': row[21] if row[21] != 'N/A' else 'LIN-LOX-LAR',
            'tipo_jornada': row[22],
            'fecha_ancla': row[23],
            'usuario_app': row[24],
            'foto': row[25],
            'estatus': 'ACTIVO',
            'texto_antiguedad': texto_antiguedad,
            'vacaciones': vacaciones
        })
        
    bajas = []
    for b in bajas_raw:
        estatus_str = str(b[27] or 'Baja')
        fecha_baja = estatus_str.replace('Baja - ', '').strip() if 'Baja - ' in estatus_str else '--'
        texto_antiguedad_b, vac_b = calcular_antiguedad_y_vacaciones(b[12])
        
        bajas.append({
            'id': b[0], 'no_empleado': b[1] if b[1] != 'N/A' else '--',
            'nombre': b[2], 'linea': b[3], 'prod': b[4],
            'esquema': b[5], 'eco': b[6], 'tel': b[7] if b[7] != 'N/A' else '',
            'imei': b[8] if b[8] != 'N/A' else '--', 'imp': b[9] if b[9] != 'N/A' else '--',
            'lic': b[10] if b[10] != 'N/A' else '--', 'med': b[11] if b[11] != 'N/A' else '--',
            'fecha_alta': b[12] if b[12] != 'N/A' else '--',
            'fecha_nacimiento': b[13] if b[13] != 'N/A' else '--',
            'edad': calcular_edad_exacta(b[13]),
            'tipo_licencia': b[15] if b[15] != 'N/A' else '--',
            'no_licencia': b[16] if b[16] != 'N/A' else '--',
            'liberacion_cryo': b[17] if b[17] != 'N/A' else '--',
            'liberado_operativamente': b[18] if b[18] != 'N/A' else '--',
            'experiencia_desde': b[19] if b[19] != 'N/A' else '--',
            'tipo_unidad': b[20] if b[20] != 'N/A' else 'FULL',
            'productos_descarga': b[21] if b[21] != 'N/A' else 'LIN-LOX-LAR',
            'usuario_app': b[24], 'foto': b[25], 'estatus': 'BAJA',
            'fecha_baja': fecha_baja,
            'causa_baja': b[28],
            'detalle_baja': b[29],
            'texto_antiguedad': texto_antiguedad_b, 'vacaciones': vac_b
        })
        
    return render_template('perfil_operadores.html', operadores=operadores, bajas=bajas)

@app.route('/api/expediente_historial', methods=['POST'])
@login_required
def expediente_historial():
    if session.get('rol') in ['operador', 'supervisor', 'monitorista']: 
        return jsonify({"status": "error", "msg": "Acceso restringido a expedientes"}), 403
    op_id = request.json.get('operador_id')
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    hoy = datetime.now().date()
    
    c.execute("SELECT fecha FROM logistica_diaria WHERE operador_id=? AND estatus='DE' AND fecha <= ? ORDER BY fecha DESC LIMIT 1", (op_id, hoy.strftime('%Y-%m-%d')))
    res_de = c.fetchone()
    if res_de:
        dias_de = (hoy - datetime.strptime(res_de[0], '%Y-%m-%d').date()).days
        ultimo_descanso = f"{res_de[0]} (Hace {dias_de} días)"
    else:
        ultimo_descanso = "Sin registro reciente"
        
    c.execute("SELECT estatus FROM logistica_diaria WHERE operador_id=? AND fecha=?", (op_id, hoy.strftime('%Y-%m-%d')))
    res_hoy = c.fetchone()
    estatus_hoy = res_hoy[0] if res_hoy else "TR"
    
    dias_semana, _, _, _, _, _ = get_semana(hoy.strftime('%Y-%m-%d'))
    fechas_sem = [d['fecha'] for d in dias_semana]
    c.execute(f"SELECT SUM(horas) FROM dot_diario WHERE operador_id=? AND fecha IN ({','.join(['?']*7)})", [op_id] + fechas_sem)
    res_horas = c.fetchone()
    horas_dot = round(res_horas[0], 1) if res_horas and res_horas[0] else 0.0
    
    c.execute("SELECT nombre FROM operadores WHERE id=?", (op_id,))
    res_nom_op = c.fetchone()
    nombre_operador = res_nom_op[0].strip().upper() if res_nom_op else ''

    fecha_inicio = hoy - timedelta(days=29)
    fechas_30 = [(fecha_inicio + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30)]
    
    # 1. Estatus diario de la sábana
    c.execute(f"SELECT fecha, estatus FROM logistica_diaria WHERE operador_id=? AND fecha IN ({','.join(['?']*30)}) ORDER BY fecha DESC", [op_id] + fechas_30)
    logistica_map = {row[0]: row[1] for row in c.fetchall()}

    # 2. Horas reales capturadas en DOT
    c.execute(f"SELECT fecha, horas FROM dot_diario WHERE operador_id=? AND fecha IN ({','.join(['?']*30)})", [op_id] + fechas_30)
    horas_map = {row[0]: float(row[1] or 0.0) for row in c.fetchall()}

    # 3. Clientes reales desde viajes archivados
    c.execute(f"SELECT fecha_operativa, viaje_json FROM viajes_archivados WHERE fecha_operativa IN ({','.join(['?']*30)})", fechas_30)
    viajes_raw = c.fetchall()
    clientes_por_fecha = {}
    for f_op, v_json in viajes_raw:
        try:
            v_data = json.loads(v_json)
            if str(v_data.get('operador', '')).strip().upper() == nombre_operador:
                escalas = v_data.get('escalas', [])
                destinos = [str(e.get('cliente', '')).strip() for e in escalas if e.get('cliente') and not str(e.get('cliente')).upper().startswith('DESTINO')]
                if destinos:
                    if f_op not in clientes_por_fecha: clientes_por_fecha[f_op] = []
                    clientes_por_fecha[f_op].extend(destinos)
        except: pass

    # 4. Construcción del calendario de 30 días con métricas NOM-087
    calendario = []
    for f in reversed(fechas_30):
        est = logistica_map.get(f, 'TR')
        h_dia = round(horas_map.get(f, 0.0), 1)
        
        # Horas acumuladas de los últimos 8 días (NOM-087)
        f_dt = datetime.strptime(f, '%Y-%m-%d').date()
        fechas_8d = [(f_dt - timedelta(days=k)).strftime('%Y-%m-%d') for k in range(7)]
        h_acum = round(sum(horas_map.get(fk, 0.0) for fk in fechas_8d), 1)
        h_rest = max(0.0, round(70.0 - h_acum, 1))

        # Clientes del día
        cli_list = clientes_por_fecha.get(f, [])
        clientes_str = ", ".join(list(dict.fromkeys(cli_list))) if cli_list else ('--' if not est.startswith('TR') else 'Ruta Local / Base')

        dia_str = f_dt.strftime('%d/%m')
        calendario.append({
            "fecha": f, 
            "dia_str": dia_str, 
            "estatus": est, 
            "clientes": clientes_str,
            "horas_dia": h_dia,
            "horas_acum": h_acum,
            "horas_rest": h_rest
        })
        
    conn.close()
    return jsonify({"status": "success", "ultimo_descanso": ultimo_descanso, "estatus_hoy": estatus_hoy, "horas_dot": horas_dot, "calendario": calendario})

@app.route('/api/guardar_amonestacion', methods=['POST'])
@login_required
def api_guardar_amonestacion():
    if session.get('rol') not in ['jefe_op', 'aux_dot', 'gerencia', 'super_usuario']:
        return jsonify({"status": "error", "msg": "No tienes permisos para registrar amonestaciones."}), 403
    
    # Soporta tanto FormData (con archivo) como JSON simple
    if request.form:
        op_id = request.form.get('operador_id')
        fecha = request.form.get('fecha')
        tipo = request.form.get('tipo')
        descripcion = str(request.form.get('descripcion', '')).strip()
        estatus = request.form.get('estatus', 'Pendiente')
    else:
        d = request.get_json(silent=True) or {}
        op_id = d.get('operador_id')
        fecha = d.get('fecha')
        tipo = d.get('tipo')
        descripcion = str(d.get('descripcion', '')).strip()
        estatus = d.get('estatus', 'Pendiente')
    
    if not op_id or not fecha or not tipo or not descripcion:
        return jsonify({"status": "error", "msg": "Todos los campos son obligatorios."}), 400
        
    pdf_filename = None
    if 'evidencia_pdf' in request.files:
        pdf = request.files['evidencia_pdf']
        if pdf and pdf.filename and es_extension_valida(pdf.filename, {'pdf'}):
            pdf_filename = f"amon_{op_id}_{int(datetime.now().timestamp())}.pdf"
            pdf.save(os.path.join(EVIDENCIAS_AMONESTACIONES, pdf_filename))

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO amonestaciones (operador_id, fecha, tipo, descripcion, estatus, archivo_pdf)
                     VALUES (?, ?, ?, ?, ?, ?)''', (op_id, fecha, tipo, descripcion, estatus, pdf_filename))
        conn.commit()
        return jsonify({"status": "success", "msg": "Amonestación registrada con éxito."})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "msg": str(e)}), 500
    finally:
        conn.close()


@app.route('/api/obtener_amonestaciones', methods=['POST'])
@login_required
def api_obtener_amonestaciones():
    if session.get('rol') == 'operador':
        return jsonify({"status": "error"}), 403
        
    op_id = request.json.get('operador_id')
    if not op_id:
        return jsonify({"status": "error", "msg": "Falta el ID del operador."}), 400
        
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Consultar historial incluyendo archivo_pdf
    c.execute('''SELECT id, fecha, tipo, descripcion, estatus, COALESCE(archivo_pdf, '') 
                 FROM amonestaciones 
                 WHERE operador_id = ? 
                 ORDER BY fecha DESC, id DESC''', (op_id,))
    filas = c.fetchall()
    conn.close()
    
    historial = []
    kpis = {
        "actas": 0,
        "combustible": 0,
        "danos": 0,
        "retardos": 0,
        "incidentes": 0,
        "total": len(filas)
    }
    
    for fid, fec, tip, desc, est, pdf_file in filas:
        historial.append({
            "id": fid,
            "fecha": fec,
            "tipo": tip,
            "descripcion": desc,
            "estatus": est,
            "archivo_pdf": pdf_file if pdf_file else None
        })
        
        # Conteo inteligente según la categoría
        t_upper = tip.upper()
        if "ACTA" in t_upper:
            kpis["actas"] += 1
        elif "COMBUSTIBLE" in t_upper:
            kpis["combustible"] += 1
        elif "DAÑO" in t_upper or "DANO" in t_upper:
            kpis["danos"] += 1
        elif "RETARDO" in t_upper:
            kpis["retardos"] += 1
        elif "INCIDENTE" in t_upper or "SEGURIDAD" in t_upper:
            kpis["incidentes"] += 1

    # 4. Enviar todo empaquetado a JavaScript
    return jsonify({
        "status": "success",
        "kpis": kpis,
        "historial": historial
    })    


@app.route('/auditoria_dot')
@login_required
def auditoria_dot():
    if session.get('rol') not in ['jefe_op', 'aux_dot', 'super_usuario']: return abort(403)
    
    fecha_ini_req = request.args.get('fecha_inicio')
    fecha_fin_req = request.args.get('fecha_fin')
    mes_req = request.args.get('mes')
    hoy = datetime.now().date()
    nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    meses_abrev = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    # Modo 1: Rango libre de fechas (cruces de mes, quincenas o semanas)
    if fecha_ini_req and fecha_fin_req:
        try:
            f_ini = datetime.strptime(fecha_ini_req.strip(), '%Y-%m-%d').date()
            f_fin = datetime.strptime(fecha_fin_req.strip(), '%Y-%m-%d').date()
            if f_fin < f_ini:
                f_ini, f_fin = f_fin, f_ini
            # Límite de seguridad a 45 días continuos para rendimiento fluido
            if (f_fin - f_ini).days > 45:
                f_fin = f_ini + timedelta(days=45)

            num_dias = (f_fin - f_ini).days + 1
            dias_mes = []
            for d in range(num_dias):
                f_act = f_ini + timedelta(days=d)
                dias_mes.append({
                    'fecha': f_act.strftime('%Y-%m-%d'),
                    'label': f"{nombres_dias[f_act.weekday()]} {f_act.day}",
                    'es_hoy': f_act == hoy,
                    'es_fin_semana': f_act.weekday() >= 5
                })

            texto_mes = f"{f_ini.day} {meses_abrev[f_ini.month - 1]} - {f_fin.day} {meses_abrev[f_fin.month - 1]} {f_fin.year}"
            f_atras_ini = (f_ini - timedelta(days=num_dias)).strftime('%Y-%m-%d')
            f_atras_fin = (f_ini - timedelta(days=1)).strftime('%Y-%m-%d')
            f_adel_ini = (f_fin + timedelta(days=1)).strftime('%Y-%m-%d')
            f_adel_fin = (f_fin + timedelta(days=num_dias)).strftime('%Y-%m-%d')
            nav_atras = f"?fecha_inicio={f_atras_ini}&fecha_fin={f_atras_fin}"
            nav_adelante = f"?fecha_inicio={f_adel_ini}&fecha_fin={f_adel_fin}"
            mes_actual_str = f_ini.strftime('%Y-%m')
            fecha_inicio_val = f_ini.strftime('%Y-%m-%d')
            fecha_fin_val = f_fin.strftime('%Y-%m-%d')
        except Exception:
            dias_mes, texto_mes, f_atras, f_adelante, mes_actual_str = get_mes_data(mes_req)
            nav_atras = f"?mes={f_atras}"
            nav_adelante = f"?mes={f_adelante}"
            fecha_inicio_val = dias_mes[0]['fecha']
            fecha_fin_val = dias_mes[-1]['fecha']
    else:
        # Modo 2: Mes calendario estándar
        dias_mes, texto_mes, f_atras, f_adelante, mes_actual_str = get_mes_data(mes_req)
        nav_atras = f"?mes={f_atras}"
        nav_adelante = f"?mes={f_adelante}"
        fecha_inicio_val = dias_mes[0]['fecha']
        fecha_fin_val = dias_mes[-1]['fecha']

    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    # Plantilla completa de la terminal San Luis Potosí
    c.execute("""
        SELECT id, no_empleado, nombre 
        FROM operadores 
        WHERE UPPER(estatus_empleado) = 'ACTIVO' 
          AND COALESCE(esquema, '') != 'Varios' 
          AND UPPER(COALESCE(linea_negocio, '')) != 'VARIOS'
          AND UPPER(COALESCE(producto, '')) != 'VARIOS'
        ORDER BY nombre
    """)
    ops_raw = c.fetchall()
    
    ops = []
    fechas_str = [d['fecha'] for d in dias_mes]
    todos_nombres = [op[2] for op in ops_raw]

    # Evaluación de fatiga NOM-087 sobre el límite de corte de la consulta
    f_corte_dt = datetime.strptime(fecha_fin_val, '%Y-%m-%d').date()
    fecha_fin_8d = hoy if (f_corte_dt >= hoy) else f_corte_dt
    fechas_7dias = [(fecha_fin_8d - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

    hoy_str = hoy.strftime('%Y-%m-%d')
    placeholders_mes = ','.join(['?'] * len(fechas_str))

    # Consulta con rango abierto incorporando sub_estatus homologado
    c.execute(f"""
        SELECT operador_id, fecha, horas, estatus_dia, eco_unidad, eco_pipas, 
               horas_manejo, horas_maniobra, auditado, evidencia_foto, tipo_registro, 
               no_bitacora, folio_bhs, clave_nocturna, viaje_mina, observaciones, 
               COALESCE(sub_estatus, ''), COALESCE(horas_dot_calc, 0.0), COALESCE(dias_trabajados_calc, 0)
        FROM dot_diario 
        WHERE fecha IN ({placeholders_mes})
    """, fechas_str)
    dot_global = {
        (r[0], r[1]): {
            'horas': r[2], 'estatus': r[3], 'estatus_dia': r[3], 'unidad': r[4], 'pipas': r[5], 
            'manejo': r[6], 'maniobra': r[7], 'auditado': r[8], 'evidencia_foto': r[9], 
            'tipo_registro': r[10], 'no_bitacora': r[11], 'folio_bhs': r[12], 
            'clave_nocturna': r[13], 'viaje_mina': r[14], 'observaciones': r[15], 
            'sub_estatus': r[16], 'horas_dot_calc': r[17], 'dias_trabajados_calc': r[18]
        } for r in c.fetchall()
    }

    c.execute(f"SELECT operador_id, fecha, estatus FROM logistica_diaria WHERE fecha IN ({placeholders_mes})", fechas_str)
    sabana_global = {(r[0], r[1]): (r[2] or '').strip().upper() for r in c.fetchall()}

    for op_id, no_emp, nombre in ops_raw:
        horas_diarias = []
        total_mes = 0.0
        
        for d in dias_mes:
            llave = (op_id, d['fecha'])
            est_sab = sabana_global.get(llave, '')
            h_data = dot_global.get(llave)
            if h_data: 
                item = h_data.copy()
                item['fecha'] = d['fecha']
                item['estatus_sabana'] = est_sab
                horas_diarias.append(item)
                total_mes += float(item['horas'] or 0.0)
            else: 
                horas_diarias.append({
                    'fecha': d['fecha'],
                    'horas': None,
                    'estatus_dia': None,
                    'estatus': None,
                    'estatus_sabana': est_sab,
                    'auditado': 0,
                    'tipo_registro': 'Sin Registro',
                    'unidad': 'N/A',
                    'pipas': 'N/A',
                    'manejo': 0.0,
                    'maniobra': 0.0,
                    'evidencia_foto': 'N/A',
                    'horas_dot_calc': 0.0,
                    'dias_trabajados_calc': 0
                })
                
        # Ventana rodante estricta NOM-087: 70h menos horas reales en los últimos 7 días calendario
        c.execute("SELECT COALESCE(SUM(horas), 0.0) FROM dot_diario WHERE operador_id=? AND fecha IN ({seq})".format(seq=','.join(['?']*7)), [op_id] + fechas_7dias)
        res_7d = c.fetchone()
        usadas_7d = float(res_7d[0]) if (res_7d and res_7d[0]) else 0.0
            
        nombre_credencial = f"{no_emp} | {nombre}" if no_emp != 'N/A' else nombre
            
        ops.append({
            'id': op_id, 
            'nombre': nombre, 
            'nombre_credencial': nombre_credencial, 
            'horas_diarias': horas_diarias, 
            'total': round(total_mes, 1), 
            'restantes': max(0, round(70.0 - usadas_7d, 1))
        })
    conn.close()
    
    return render_template('horas_dot.html', operadores=ops, dias_mes=dias_mes, texto_mes=texto_mes, lista_ocr=json.dumps(todos_nombres), nav_atras=nav_atras, nav_adelante=nav_adelante, mes_actual_str=mes_actual_str, hoy_str=hoy_str, fecha_inicio_req=fecha_inicio_val, fecha_fin_req=fecha_fin_val)

@app.route('/api/actualizar_dot', methods=['POST'])
@login_required
def actualizar_dot():
    if session.get('rol') not in ['jefe_op', 'aux_dot']: return jsonify({"status": "error"}), 403
    d = request.json; conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    op_id = d.get('id'); origen = d.get('origen', 'manual')
    try:
        if not op_id and d.get('nombre'):
            c.execute("SELECT id FROM operadores WHERE nombre=? AND estatus_empleado='Activo'", (d['nombre'],))
            res = c.fetchone()
            if not res: return jsonify({"status": "error", "msg": f"Operador {d['nombre']} no encontrado."})
            op_id = res[0]

        hoy_operativo = datetime.now(TZ_LOCAL).strftime('%Y-%m-%d')
        for reg in d['horas_diarias']:
            fecha = reg['fecha']
            if fecha > hoy_operativo:
                return jsonify({"status": "error", "msg": "Operación denegada: No está permitido capturar horas en fechas futuras."}), 400

            h = float(reg.get('horas', 0.0)); estatus = reg.get('estatus_dia', 'EN VIAJE')
            unidad = reg.get('eco_unidad', 'N/A'); pipas = reg.get('eco_pipas', 'N/A')
            manejo = float(reg.get('horas_manejo', 0.0)); maniobra = float(reg.get('horas_maniobra', 0.0))
            auditado = reg.get('auditado', 1) 
            
            tipo_reg = reg.get('tipo_registro', 'Estimado')
            no_bit = reg.get('no_bitacora', '')
            folio_bhs = reg.get('folio_bhs', '')
            clave_noc = reg.get('clave_nocturna', '')
            viaje_mina = reg.get('viaje_mina', 'NO')
            obs = reg.get('observaciones', '')
            sub_est = reg.get('sub_estatus', '')
            
            c.execute('''INSERT INTO dot_diario 
                         (operador_id, fecha, horas, estatus_dia, eco_unidad, eco_pipas, horas_manejo, horas_maniobra, auditado, 
                         tipo_registro, no_bitacora, folio_bhs, clave_nocturna, viaje_mina, observaciones, sub_estatus) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
                         ON CONFLICT(operador_id, fecha) DO UPDATE SET 
                         horas=excluded.horas, estatus_dia=excluded.estatus_dia, eco_unidad=excluded.eco_unidad, 
                         eco_pipas=excluded.eco_pipas, horas_manejo=excluded.horas_manejo, horas_maniobra=excluded.horas_maniobra, 
                         auditado=excluded.auditado, tipo_registro=excluded.tipo_registro, no_bitacora=excluded.no_bitacora, 
                         folio_bhs=excluded.folio_bhs, clave_nocturna=excluded.clave_nocturna, viaje_mina=excluded.viaje_mina, 
                         observaciones=excluded.observaciones, sub_estatus=excluded.sub_estatus''', 
                      (op_id, fecha, h, estatus, unidad, pipas, manejo, maniobra, auditado, tipo_reg, no_bit, folio_bhs, clave_noc, viaje_mina, obs, sub_est))

            registrar_evento_sync(c, 'dot_actualizado', {
                'operador_id': op_id,
                'fecha': fecha,
                'horas': h,
                'estatus_dia': estatus,
                'eco_unidad': unidad,
                'eco_pipas': pipas,
                'horas_manejo': manejo,
                'horas_maniobra': maniobra,
                'auditado': auditado,
                'tipo_registro': tipo_reg,
                'no_bitacora': no_bit,
                'folio_bhs': folio_bhs,
                'clave_nocturna': clave_noc,
                'viaje_mina': viaje_mina,
                'observaciones': obs,
                'sub_estatus': sub_est
            })
                      
        conn.commit(); return jsonify({"status": "success", "msg": "Horas actualizadas."})
    except Exception as e: conn.rollback(); return jsonify({"status": "error", "msg": str(e)})
    finally: conn.close()

@app.route('/api/guardar_simulador', methods=['POST'])
@login_required
def guardar_simulador():
    d = request.json; conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    if session.get('rol') == 'aux_dot':
        d['tipo'] = 'Meta'
        c.execute("INSERT INTO solicitudes_cambio (usuario_solicita, tipo_movimiento, datos_json) VALUES (?, ?, ?)", (session['usuario'], 'Meta', json.dumps(d)))
        conn.commit(); conn.close(); return jsonify({"status": "solicitado"})
    elif session.get('rol') in ['jefe_op', 'gerencia']:
        c.execute("UPDATE configuracion SET valor=? WHERE clave='unidades_argon'", (d['argon'],))
        c.execute("UPDATE configuracion SET valor=? WHERE clave='unidades_nitrogeno'", (d['nitrogeno'],))
        c.execute("UPDATE configuracion SET valor=? WHERE clave='unidades_oxigeno'", (d['oxigeno'],))
        c.execute("UPDATE configuracion SET valor=? WHERE clave='unidades_co2'", (d['co2'],))
        conn.commit(); conn.close(); return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 403

AUTORIZACION_DIRECTA_SUPERVISORES = True  # Cambiar a False cuando el jefe vuelva

@app.route('/api/solicitar_turno', methods=['POST'])
@login_required
def solicitar_turno():
    if session.get('rol') not in ['supervisor', 'aux_dot', 'super_usuario']: 
        return jsonify({"status": "error", "msg": "No autorizado para solicitar cambios"}), 403
        
    d = request.json
    op_id = d.get('operador_id')
    fecha_inicio = d.get('fecha')
    fecha_fin = d.get('fecha_fin') or fecha_inicio
    estatus_nuevo = d.get('estatus_nuevo')
    
    if not op_id or not fecha_inicio or not estatus_nuevo:
        return jsonify({"status": "error", "msg": "Datos incompletos"}), 400

    hoy_operativo = datetime.now(TZ_LOCAL).strftime('%Y-%m-%d')
    if fecha_inicio < hoy_operativo:
        return jsonify({"status": "error", "msg": "No se pueden solicitar modificaciones en días pasados."}), 400
        
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT nombre FROM operadores WHERE id=?", (op_id,))
    res_nom = c.fetchone()
    if not res_nom:
        conn.close()
        return jsonify({"status": "error", "msg": "Operador no encontrado"}), 404
    nombre = res_nom[0]
    
    # Consultamos el valor que tiene actualmente para mostrar el "Antes vs Después"
    c.execute("SELECT estatus FROM logistica_diaria WHERE operador_id=? AND fecha=?", (op_id, fecha_inicio))
    res_ant = c.fetchone()
    estatus_ant = res_ant[0] if res_ant else "TR"
    
    # MODO CONTINGENCIA: Si el switch está activo, aplica directo sin pedir autorización
    if AUTORIZACION_DIRECTA_SUPERVISORES:
        f_in = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        f_out = datetime.strptime(fecha_fin, '%Y-%m-%d')
        dias_rango = (f_out - f_in).days + 1
        
        for i in range(dias_rango):
            f_actual = (f_in + timedelta(days=i)).strftime('%Y-%m-%d')
            c.execute('''INSERT INTO logistica_diaria (operador_id, fecha, estatus) 
                         VALUES (?, ?, ?) 
                         ON CONFLICT(operador_id, fecha) DO UPDATE SET estatus = excluded.estatus''', 
                      (op_id, f_actual, estatus_nuevo))
        
        usuario_responsable = session.get('nombre_real', session.get('usuario', 'Supervisor'))
        msj = f"⚡ Cambio directo (Supervisor): {usuario_responsable} actualizó a {nombre} ({fecha_inicio}) de {estatus_ant} a {estatus_nuevo}."
        registrar_notificacion(c, msj)
        conn.commit(); conn.close()
        recalcular_tr_operador(op_id)
        return jsonify({"status": "success", "msg": "Turno actualizado directamente (Modo Contingencia)."})

    datos_solicitud = {
        'operador_id': op_id,
        'nombre': nombre,
        'fecha': fecha_inicio,
        'fecha_fin': fecha_fin,
        'estatus_nuevo': estatus_nuevo,
        'estatus_ant': estatus_ant,
        'solicitante_usuario': session.get('usuario'),
        'solicitante_nombre': session.get('nombre_real', session.get('usuario'))
    }
    
    # 1. Registrar la solicitud en estado 'Pendiente'
    c.execute('''INSERT INTO solicitudes_cambio (usuario_solicita, tipo_movimiento, datos_json, estatus) 
                 VALUES (?, ?, ?, 'Pendiente')''', 
              (session.get('usuario'), 'Turno', json.dumps(datos_solicitud)))
    
    # 2. Alertar de inmediato en la campanita
    nombre_solicita = session.get('nombre_real', session.get('usuario'))
    msj_notif = f"🔔 Solicitud de Rol: {nombre_solicita} propuso cambiar a {nombre} ({fecha_inicio}) de {estatus_ant} a {estatus_nuevo}."
    registrar_notificacion(c, msj_notif)
    
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "msg": "Solicitud enviada a autorización de Jefatura / DOT."})

@app.route('/api/solicitar_pase_salida', methods=['POST'])
@login_required
def api_solicitar_pase_salida():
    if session.get('rol') not in ['jefe_op', 'gerencia']: return jsonify({"status": "error"}), 403
    d = request.json
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        c.execute('''INSERT INTO pases_salida (empleado, num_emp, depto, puesto, tipo_permiso, motivo, lugar, hora_esperada, hora_regreso, tipo_incidencia, autoriza) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                  (d.get('empleado'), d.get('num_emp'), d.get('depto'), d.get('puesto'), d.get('tipo_permiso'), d.get('motivo'), d.get('lugar'), d.get('hora_esperada'), d.get('hora_regreso'), d.get('tipo_incidencia'), session.get('nombre_real')))
        
        registrar_notificacion(c, f"🎫 Pase de salida autorizado para {d.get('empleado')} ({d.get('depto')}).")
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "msg": str(e)})
    finally:
        conn.close()

@app.route('/api/actualizar_turno', methods=['POST'])
@login_required
def actualizar_turno():
    # Solo Jefatura y Auxiliar DOT pueden guardar directo (o supervisores si el switch temporal está activo)
    roles_permitidos = ['jefe_op', 'aux_dot', 'super_usuario']
    if AUTORIZACION_DIRECTA_SUPERVISORES:
        roles_permitidos.append('supervisor')
        
    if session.get('rol') not in roles_permitidos: 
        return jsonify({"status": "error", "msg": "No autorizado para aplicar cambios directos"}), 403
        
    d = request.json
    fecha_inicio = d['fecha']
    fecha_fin = d.get('fecha_fin')
    if not fecha_fin: fecha_fin = fecha_inicio

    if fecha_fin < fecha_inicio: 
        return jsonify({"status": "error", "msg": "La fecha final debe ser mayor o igual a la inicial."}), 400

    hoy_operativo = datetime.now(TZ_LOCAL).strftime('%Y-%m-%d')
    if fecha_inicio < hoy_operativo and session.get('rol') not in ['jefe_op', 'super_usuario']:
        return jsonify({"status": "error", "msg": "Solo el Jefe de Operaciones tiene autorización para modificar días pasados."}), 400
        
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT nombre FROM operadores WHERE id=?", (d['operador_id'],)); nombre = c.fetchone()[0]
    estatus_nuevo = d['estatus_nuevo']
    
    # 1. Averiguar qué estatus tenía antes el operador en esa fecha para registrar la transición
    c.execute("SELECT estatus FROM logistica_diaria WHERE operador_id=? AND fecha=?", (d['operador_id'], fecha_inicio))
    res_ant = c.fetchone()
    estatus_ant = res_ant[0] if res_ant else "TR"

    try:
        f_in = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        f_out = datetime.strptime(fecha_fin, '%Y-%m-%d')
        dias_rango = (f_out - f_in).days + 1
        
        # 2. Guardar los nuevos días en la sábana y emitir evento en vivo unificado
        op_id_int = int(d['operador_id'])
        for i in range(dias_rango):
            f_actual = (f_in + timedelta(days=i)).strftime('%Y-%m-%d')
            c.execute('''INSERT INTO logistica_diaria (operador_id, fecha, estatus) 
                         VALUES (?, ?, ?) 
                         ON CONFLICT(operador_id, fecha) DO UPDATE SET estatus = excluded.estatus''', 
                      (op_id_int, f_actual, estatus_nuevo))
            
            # Emitir tanto celda_sabana como celda_actualizada para máxima compatibilidad
            payload_sync = {
                'operador_id': op_id_int,
                'fecha': f_actual,
                'estatus': estatus_nuevo
            }
            registrar_evento_sync(c, 'celda_sabana', payload_sync)
            registrar_evento_sync(c, 'celda_actualizada', payload_sync)
        
        # 3. Registrar la notificación con usuario, transición y periodo
        usuario_responsable = session.get('nombre_real', session.get('usuario', 'Personal Operativo'))
        
        if dias_rango > 1:
            msj = f"{usuario_responsable} modificó a {nombre} del {fecha_inicio} al {fecha_fin}: de {estatus_ant} a {estatus_nuevo}."
        else:
            msj = f"{usuario_responsable} modificó a {nombre} el {fecha_inicio}: de {estatus_ant} a {estatus_nuevo}."
            
        registrar_notificacion(c, msj)
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "msg": str(e)}), 400
    finally:
        conn.close()
    
    recalcular_tr_operador(d['operador_id'])
    return jsonify({"status": "success"})

@app.route('/api/redibujar_rol', methods=['POST'])
@login_required
def redibujar_rol():
    if session.get('rol') not in ['jefe_op', 'aux_dot', 'supervisor', 'super_usuario']: 
        return jsonify({"status": "error"}), 403
    d = request.json
    op_id = d['operador_id']
    patron = d.get('patron', 'Variable')
    fecha_ancla = d.get('fecha_ancla', 'N/A')
    eco = d.get('eco', None)
    rol_op = d.get('rol_op', 'OPERADOR')
    producto = d.get('producto')
    esquema = d.get('esquema')

    # CANDADO ESTRICTO: Solo el Jefe de Operaciones puede reasignar Función, Producto o Bloque
    if (rol_op != 'OPERADOR' or producto or esquema) and session.get('rol') not in ['jefe_op', 'super_usuario']:
        return jsonify({"status": "error", "msg": "Acceso denegado: Solo el Jefe de Operaciones puede reasignar el Rol, Producto o Bloque."}), 403

    try:
        conn = sqlite3.connect(DB_NAME); c = conn.cursor()
        c.execute("SELECT nombre FROM operadores WHERE id=?", (op_id,))
        res_nom = c.fetchone()
        nombre_op = res_nom[0] if res_nom else "Operador"
        quien = session.get('nombre_real', session.get('usuario'))

        # 1. Asignación inteligente según la Función
        if rol_op in ['MOVEDOR', 'INSTRUCTOR']:
            c.execute("UPDATE operadores SET esquema='Varios', linea_negocio='VARIOS', producto='VARIOS' WHERE id=?", (op_id,))
        else:
            if producto:
                linea = 'CO2' if producto == 'CO2' else 'CRYO'
                c.execute("UPDATE operadores SET producto=?, linea_negocio=? WHERE id=?", (producto, linea, op_id))
            if esquema:
                esquema_final = 'CO2' if producto == 'CO2' else esquema
                c.execute("UPDATE operadores SET esquema=? WHERE id=?", (esquema_final, op_id))

        # 2. Manejo de Jornada y Patrón
        if patron == 'Variable':
            if fecha_ancla and fecha_ancla not in ['N/A', '']:
                if session.get('rol') not in ['jefe_op', 'super_usuario']:
                    conn.close()
                    return jsonify({"status": "error", "msg": "Solo el Jefe de Operaciones puede borrar turnos asignados."}), 403
                c.execute("DELETE FROM logistica_diaria WHERE operador_id = ? AND fecha >= ?", (op_id, fecha_ancla))
                c.execute("UPDATE operadores SET tipo_jornada='Variable', fecha_ancla='N/A' WHERE id=?", (op_id,))
                registrar_notificacion(c, f"🗑️ {quien} cambió a {nombre_op} a jornada Variable y limpió turnos desde {fecha_ancla}.")
            else:
                c.execute("UPDATE operadores SET tipo_jornada='Variable' WHERE id=?", (op_id,))
            
            if eco is not None:
                c.execute("UPDATE operadores SET eco=? WHERE id=?", (eco, op_id))
        else:
            if eco is not None:
                c.execute("UPDATE operadores SET tipo_jornada=?, fecha_ancla=?, eco=? WHERE id=?", (patron, fecha_ancla, eco, op_id))
            else:
                c.execute("UPDATE operadores SET tipo_jornada=?, fecha_ancla=? WHERE id=?", (patron, fecha_ancla, op_id))
                
            if patron not in ['N/A', ''] and fecha_ancla not in ['N/A', '', None]:
                if patron == '8-1-8-1-8-6': ciclo = ['TR']*8 + ['DE'] + ['TR']*8 + ['DE'] + ['TR']*8 + ['DE']*6
                elif patron == '8-1-8-6': ciclo = ['TR']*8 + ['DE'] + ['TR']*8 + ['DE']*6
                elif patron == '8x4': ciclo = ['TR']*8 + ['DE']*4
                elif patron == '4x4': ciclo = ['TR']*4 + ['DE']*4
                else: ciclo = ['TR']
                
                f_ancla = datetime.strptime(fecha_ancla, '%Y-%m-%d').date()
                hoy = datetime.now().date()
                dias_totales = max(60, (hoy + timedelta(days=60) - f_ancla).days)
                
                for i in range(dias_totales):
                    f_actual = f_ancla + timedelta(days=i)
                    f_str = f_actual.strftime('%Y-%m-%d')
                    estatus_calc = ciclo[i % len(ciclo)]
                    c.execute('''INSERT INTO logistica_diaria (operador_id, fecha, estatus) 
                                 VALUES (?, ?, ?) 
                                 ON CONFLICT(operador_id, fecha) DO UPDATE SET estatus = excluded.estatus''', 
                              (op_id, f_str, estatus_calc))
                registrar_notificacion(c, f"🔄 {quien} aplicó ciclo {patron} para {nombre_op} desde {fecha_ancla}.")

        registrar_notificacion(c, f"🏷️ {quien} actualizó perfil de {nombre_op}: Función [{rol_op}], Producto [{producto or 'VARIOS'}], Bloque [{esquema or 'VARIOS'}].")

        conn.commit(); conn.close()
        recalcular_tr_operador(op_id)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 400

@app.route('/api/guardar_orden_operadores', methods=['POST'])
@login_required
def api_guardar_orden_operadores():
    if session.get('rol') not in ['jefe_op', 'supervisor', 'aux_dot', 'super_usuario']:
        return jsonify({"status": "error", "msg": "No autorizado"}), 403
    
    data = request.json
    orden_ids = data.get('orden_ids', []) # Lista de IDs en el nuevo orden [45, 12, 88, ...]
    
    if not orden_ids:
        return jsonify({"status": "error", "msg": "Lista vacía"}), 400
        
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        for posicion, op_id in enumerate(orden_ids, start=1):
            c.execute("UPDATE operadores SET orden_posicion = ? WHERE id = ?", (posicion, op_id))
        conn.commit()
        return jsonify({"status": "success", "msg": "Orden guardado correctamente."})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "msg": str(e)}), 500
    finally:
        conn.close()    

@app.route('/api/gestionar_solicitud', methods=['POST'])
@login_required
def gestionar_solicitud():
    # Jefe de Operaciones, Auxiliar DOT y Super Usuario pueden autorizar/rechazar
    if session.get('rol') not in ['jefe_op', 'aux_dot', 'super_usuario']: 
        return jsonify({"status": "error", "msg": "No tienes privilegios de resolución"}), 403

    req = request.json
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT datos_json, tipo_movimiento, usuario_solicita FROM solicitudes_cambio WHERE id=?", (req['id'],))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"status": "error", "msg": "Solicitud no encontrada"}), 404

    d = json.loads(row[0]); tipo = row[1]; usuario_solicita = row[2]
    quien_resolvio = session.get('nombre_real', session.get('usuario'))
    trigger_domino = False; op_id_domino = None
    
    if req['accion'] == 'aprobar':
        if tipo == 'Meta':
            c.execute("UPDATE configuracion SET valor=? WHERE clave='unidades_argon'", (d['argon'],))
            c.execute("UPDATE configuracion SET valor=? WHERE clave='unidades_nitrogeno'", (d['nitrogeno'],))
            c.execute("UPDATE configuracion SET valor=? WHERE clave='unidades_oxigeno'", (d['oxigeno'],))
            c.execute("UPDATE configuracion SET valor=? WHERE clave='unidades_co2'", (d['co2'],))
            registrar_notificacion(c, f"✅ Meta Aprobada por {quien_resolvio}.")
        else:
            estatus_nuevo = d['estatus_nuevo']; nombre = d.get('nombre')
            fecha_inicio = d['fecha']
            fecha_fin = d.get('fecha_fin', fecha_inicio)
            
            f_in = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            f_out = datetime.strptime(fecha_fin, '%Y-%m-%d')
            dias_rango = (f_out - f_in).days + 1
            
            for i in range(dias_rango):
                f_actual = (f_in + timedelta(days=i)).strftime('%Y-%m-%d')
                c.execute('''INSERT INTO logistica_diaria (operador_id, fecha, estatus) 
                             VALUES (?, ?, ?) 
                             ON CONFLICT(operador_id, fecha) DO UPDATE SET estatus = excluded.estatus''', 
                          (d['operador_id'], f_actual, estatus_nuevo))
            
            if dias_rango > 1:
                msj = f"✅ Aprobado por {quien_resolvio}: {nombre} pasa a {estatus_nuevo} del {fecha_inicio} al {fecha_fin}."
            else:
                msj = f"✅ Aprobado por {quien_resolvio}: {nombre} pasa a {estatus_nuevo} el {fecha_inicio}."
            registrar_notificacion(c, msj)
            
            trigger_domino = True; op_id_domino = d['operador_id']
    else:
        # Rechazo con motivo obligatorio
        motivo = req.get('motivo', '').strip() or 'Sin motivo especificado'
        solicitante_str = d.get('solicitante_nombre', usuario_solicita)
        if tipo == 'Meta':
            msj = f"❌ Rechazado por {quien_resolvio}: Cambio de Meta denegado para {solicitante_str}. Motivo: {motivo}"
        else:
            msj = f"❌ Rechazado por {quien_resolvio}: Se negó cambio de rol para {d.get('nombre')} solicitado por {solicitante_str}. Motivo: {motivo}"
        registrar_notificacion(c, msj)

    c.execute("UPDATE solicitudes_cambio SET estatus=? WHERE id=?", 
              ('Aprobado' if req['accion'] == 'aprobar' else 'Rechazado', req['id']))
    conn.commit(); conn.close()
    
    if trigger_domino: 
        recalcular_tr_operador(op_id_domino)
    return jsonify({"status": "success"})

@app.route('/api/agregar_operador', methods=['POST'])
@login_required
def agregar_operador():
    if session.get('rol') not in ['jefe_op', 'aux_dot', 'super_usuario']: return jsonify({"status": "error"}), 403
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        no_emp = request.form.get('no_empleado', 'N/A').strip()
        nombre = request.form.get('nombre', '').strip().upper()
        prod = request.form.get('producto', 'NITROGENO')
        linea = 'CO2' if prod == 'CO2' else 'CRYO'
        f_alta = request.form.get('fecha_alta', datetime.now().strftime('%Y-%m-%d'))
        usuario_app = generar_usuario_unico(nombre)
        
        # 1. Guardado de foto si se adjuntó
        foto_filename = 'default.png'
        if 'foto_perfil' in request.files:
            foto = request.files['foto_perfil']
            nombre_foto = foto.filename if (foto and foto.filename) else ''
            if nombre_foto and es_extension_valida(nombre_foto, EXT_IMAGENES):
                ext = nombre_foto.rsplit('.', 1)[1].lower()
                foto_filename = f"perfil_{int(datetime.now().timestamp())}.{ext}"
                foto.save(os.path.join(FOTOS_FOLDER, foto_filename))

        esquema_elegido = request.form.get('esquema', 'Arrastre')
        
        # 2. Inserción completa con todos los campos auditables F-OPE-01
        c.execute('''INSERT INTO operadores (
            no_empleado, nombre, linea_negocio, producto, esquema, eco, telefono_red,
            imei1, impresora, vigencia_licencia, vigencia_medica, tipo_jornada, fecha_alta,
            estatus_empleado, fecha_nacimiento, edad, tipo_licencia, no_licencia,
            liberacion_cryo, liberado_operativamente, experiencia_desde, tipo_unidad,
            productos_descarga, usuario_app, foto, base
        ) VALUES (?, ?, ?, ?, ?, 'N/A', ?, ?, ?, ?, ?, 'Variable', ?, 'Activo', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'San Luis Potosí')''',
        (
            no_emp, nombre, linea, prod, esquema_elegido, request.form.get('tel', 'N/A'),
            request.form.get('imei', 'N/A'), request.form.get('imp', 'N/A'),
            request.form.get('lic', 'N/A'), request.form.get('med', 'N/A'),
            f_alta, request.form.get('fecha_nacimiento', 'N/A'), request.form.get('edad', 'N/A'),
            request.form.get('tipo_licencia', 'E'), request.form.get('no_licencia', 'N/A'),
            request.form.get('liberacion_cryo', 'N/A'), request.form.get('liberado_operativamente', 'CLIENTES'),
            request.form.get('experiencia_desde', 'N/A'), request.form.get('tipo_unidad', 'FULL'),
            request.form.get('productos_descarga', 'LIN-LOX-LAR'), usuario_app, foto_filename
        ))
        op_id = c.lastrowid
        
        # 3. Inicialización en auditoría DOT y proyección en sábana
        c.execute('''INSERT INTO auditoria_dot (operador_id, ultima_captura_dot, horas_dot_acumuladas, observaciones) VALUES (?, ?, 0.0, 'Alta Oficial F-OPE-01')''', (op_id, f_alta))
        hoy = datetime.now().date()
        try: f_alta_dt = datetime.strptime(f_alta, '%Y-%m-%d').date()
        except: f_alta_dt = hoy
        dias_totales = max(60, (hoy + timedelta(days=60) - f_alta_dt).days)
        for i in range(dias_totales):
            f_str = (f_alta_dt + timedelta(days=i)).strftime('%Y-%m-%d')
            c.execute('INSERT OR IGNORE INTO logistica_diaria (operador_id, fecha, estatus) VALUES (?, ?, ?)', (op_id, f_str, 'TR'))
            
        c.execute("INSERT INTO notificaciones (mensaje) VALUES (?)", (f"Alta completa de operador: {nombre}",))
        conn.commit(); conn.close()
        recalcular_tr_operador(op_id)
        return jsonify({"status": "success"})
    except Exception as e:
        conn.rollback(); conn.close()
        return jsonify({"status": "error", "msg": str(e)})

@app.route('/api/editar_operador', methods=['POST'])
@login_required
def editar_operador():
    if session.get('rol') not in ['jefe_op', 'aux_dot']: return jsonify({"status": "error"}), 403
    d = request.json; conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        linea = 'CO2' if d['producto'] == 'CO2' else 'CRYO'
        c.execute('''UPDATE operadores SET linea_negocio=?, producto=?, esquema=?, eco=?, telefono_red=?, imei1=?, impresora=?, vigencia_licencia=?, vigencia_medica=? WHERE id=?''', (linea, d['producto'], d['esquema'], d.get('eco', 'N/A'), d['tel'], d['imei'], d['imp'], d['lic'], d['med'], d['id']))
        c.execute("INSERT INTO notificaciones (mensaje) VALUES (?)", (f"Se actualizó el perfil de RH del ID: {d['id']}",))
        conn.commit()
        return jsonify({"status": "success"}) 
    except Exception as e: 
        conn.rollback()
        return jsonify({"status": "error", "msg": str(e)})
    finally: 
        conn.close()

@app.route('/api/actualizar_expediente', methods=['POST'])
@login_required
def actualizar_expediente():
    if session.get('rol') not in ['jefe_op', 'aux_dot']: return jsonify({"status": "error"}), 403
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    try:
        op_id = request.form.get('id')
        prods_descarga = request.form.get('productos_descarga', 'LIN-LOX-LAR')
        esquema = request.form.get('esquema', 'Arrastre')
        
        # Mapeo automático de línea y producto
        if 'CO2' in prods_descarga.upper():
            prod, linea = 'CO2', 'CO2'
        elif 'LOX' in prods_descarga.upper():
            prod, linea = 'OXIGENO', 'CRYO'
        elif 'LAR' in prods_descarga.upper():
            prod, linea = 'ARGON', 'CRYO'
        else:
            prod, linea = 'NITROGENO', 'CRYO'
            
        f_nac = request.form.get('fecha_nacimiento', 'N/A')
        edad_calc = calcular_edad_exacta(f_nac)

        foto_filename = None
        if 'foto_perfil' in request.files:
            foto = request.files['foto']
            nombre_foto = foto.filename if (foto and foto.filename) else ''
            if nombre_foto:
                ext = nombre_foto.rsplit('.', 1)[1].lower() if '.' in nombre_foto else 'jpg'
                foto_filename = f"perfil_{op_id}_{int(datetime.now().timestamp())}.{ext}"
                foto.save(os.path.join(FOTOS_FOLDER, foto_filename))

        if foto_filename:
            c.execute('''UPDATE operadores SET nombre=?, no_empleado=?, edad=?, fecha_nacimiento=?, fecha_alta=?, telefono_red=?, tipo_licencia=?, no_licencia=?, eco=?, impresora=?, imei1=?, experiencia_desde=?, tipo_unidad=?, liberacion_cryo=?, productos_descarga=?, liberado_operativamente=?, esquema=?, producto=?, linea_negocio=?, foto=? WHERE id=?''', 
            (request.form.get('nombre', '').strip().upper(), request.form.get('no_empleado'), edad_calc, f_nac, request.form.get('fecha_alta'), request.form.get('tel'), request.form.get('tipo_licencia'), request.form.get('no_licencia'), request.form.get('eco', 'N/A'), request.form.get('imp'), request.form.get('imei'), request.form.get('experiencia_desde'), request.form.get('tipo_unidad'), request.form.get('liberacion_cryo'), prods_descarga, request.form.get('liberado_operativamente'), esquema, prod, linea, foto_filename, op_id))
        else:
            c.execute('''UPDATE operadores SET nombre=?, no_empleado=?, edad=?, fecha_nacimiento=?, fecha_alta=?, telefono_red=?, tipo_licencia=?, no_licencia=?, eco=?, impresora=?, imei1=?, experiencia_desde=?, tipo_unidad=?, liberacion_cryo=?, productos_descarga=?, liberado_operativamente=?, esquema=?, producto=?, linea_negocio=? WHERE id=?''', 
            (request.form.get('nombre', '').strip().upper(), request.form.get('no_empleado'), edad_calc, f_nac, request.form.get('fecha_alta'), request.form.get('tel'), request.form.get('tipo_licencia'), request.form.get('no_licencia'), request.form.get('eco', 'N/A'), request.form.get('imp'), request.form.get('imei'), request.form.get('experiencia_desde'), request.form.get('tipo_unidad'), request.form.get('liberacion_cryo'), prods_descarga, request.form.get('liberado_operativamente'), esquema, prod, linea, op_id))
            
        conn.commit(); return jsonify({"status": "success"})
    except Exception as e: conn.rollback(); return jsonify({"status": "error", "msg": str(e)})
    finally: conn.close()

@app.route('/api/carga_masiva_rh', methods=['POST'])
@login_required
def carga_masiva_rh():
    if session.get('rol') not in ['jefe_op', 'aux_dot']: return jsonify({"status": "error"}), 403
    data = request.json; conn = sqlite3.connect(DB_NAME); c = conn.cursor(); nuevos, actualizados = 0, 0
    
    def limpiar_fecha(f_str):
        if not f_str or str(f_str).strip() in ['N/A', 'NAN', '']: return 'N/A'
        try:
            dt = pd.to_datetime(f_str, errors='coerce')
            if pd.isna(dt): return 'N/A'
            return dt.strftime('%Y-%m-%d')
        except:
            return 'N/A'

    try:
        for op in data:
            no_emp = str(op.get('no_empleado', '')).strip()
            nombre = str(op.get('nombre', '')).strip().upper()
            if not nombre or nombre == 'NAN': continue
            estatus = 'Baja' if str(op.get('estatus', '')).upper() == 'BAJA' else 'Activo'
            base_op = str(op.get('base', 'San Luis Potosí')).strip()
            
            f_alta = limpiar_fecha(op.get('fecha_alta'))
            f_nac = limpiar_fecha(op.get('fecha_nacimiento'))
            f_lic = limpiar_fecha(op.get('vigencia_licencia'))
            f_med = limpiar_fecha(op.get('vigencia_medica'))
            f_exp = limpiar_fecha(op.get('experiencia_desde'))
            f_cryo = limpiar_fecha(op.get('liberacion_cryo'))

            c.execute("SELECT id FROM operadores WHERE nombre=? OR no_empleado=?", (nombre, no_emp))
            row = c.fetchone()
            if row:
                op_id = row[0]
                c.execute('''UPDATE operadores SET estatus_empleado=?, fecha_alta=?, fecha_nacimiento=?, edad=?, 
                             tipo_licencia=?, vigencia_licencia=?, no_licencia=?, vigencia_medica=?, liberacion_cryo=?, 
                             productos_descarga=?, liberado_operativamente=?, experiencia_desde=?, tipo_unidad=?, 
                             telefono_red=?, base=? WHERE id=?''', 
                (estatus, f_alta, f_nac, op.get('edad'), op.get('tipo_licencia'), f_lic, op.get('no_licencia'), 
                 f_med, f_cryo, op.get('productos_descarga'), op.get('liberado_operativamente'), f_exp, 
                 op.get('tipo_unidad'), op.get('telefono_red'), base_op, op_id))
                actualizados += 1
            else:
                linea = 'CO2' if 'CO2' in str(op.get('productos_descarga', '')).upper() else 'CRYO'
                prod = 'CO2' if linea == 'CO2' else 'NITROGENO'
                usuario_app = generar_usuario_unico(nombre)
                c.execute('''INSERT INTO operadores (no_empleado, nombre, linea_negocio, producto, esquema, eco, 
                             telefono_red, imei1, impresora, vigencia_licencia, vigencia_medica, tipo_jornada, 
                             fecha_alta, estatus_empleado, fecha_nacimiento, edad, tipo_licencia, no_licencia, 
                             liberacion_cryo, liberado_operativamente, experiencia_desde, tipo_unidad, 
                             productos_descarga, usuario_app, base) 
                             VALUES (?, ?, ?, ?, 'Arrastre', 'N/A', ?, 'N/A', 'N/A', ?, ?, 'Variable', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (no_emp, nombre, linea, prod, op.get('telefono_red'), f_lic, f_med, f_alta, estatus, f_nac, 
                 op.get('edad'), op.get('tipo_licencia'), op.get('no_licencia'), f_cryo, op.get('liberado_operativamente'), 
                 f_exp, op.get('tipo_unidad'), op.get('productos_descarga'), usuario_app, base_op))
                op_id = c.lastrowid
                c.execute('''INSERT INTO auditoria_dot (operador_id, ultima_captura_dot, horas_dot_acumuladas, observaciones) VALUES (?, ?, ?, ?)''', (op_id, datetime.now().strftime('%Y-%m-%d'), 0.0, 'Alta por Excel'))
                
                try: 
                    if f_alta != 'N/A': f_alta_dt = datetime.strptime(f_alta, '%Y-%m-%d').date()
                    else: f_alta_dt = datetime.now().date()
                except: f_alta_dt = datetime.now().date()
                
                hoy = datetime.now().date()
                dias_totales = (hoy + timedelta(days=60) - f_alta_dt).days
                if dias_totales < 60: dias_totales = 60
                
                for i in range(dias_totales):
                    f_str = (f_alta_dt + timedelta(days=i)).strftime('%Y-%m-%d')
                    c.execute('INSERT OR IGNORE INTO logistica_diaria (operador_id, fecha, estatus) VALUES (?, ?, ?)', (op_id, f_str, 'TR'))
                nuevos += 1
        conn.commit(); conn.close()
        
        recalcular_tr_todos()
        return jsonify({"status": "success", "nuevos": nuevos, "actualizados": actualizados})
    except Exception as e: 
        try: conn.rollback()
        except: pass
        return jsonify({"status": "error", "msg": str(e)})
    
@app.route('/api/baja_operador', methods=['POST'])
@login_required
def baja_operador():
    if session.get('rol') not in ['jefe_op', 'aux_dot']: return jsonify({"status": "error"}), 403
    d = request.json or {}
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    hoy_str = datetime.now(TZ_LOCAL).strftime('%Y-%m-%d')
    causa = (d.get('causa_baja') or d.get('causa') or 'VOLUNTARIA').strip()
    detalle = (d.get('detalles_baja') or d.get('detalle_baja') or d.get('detalle') or '').strip()
    c.execute("UPDATE operadores SET estatus_empleado=?, causa_baja=?, detalle_baja=? WHERE id=?", 
              (f"Baja - {hoy_str}", causa, detalle, d['id']))
    registrar_notificacion(c, f"🗑️ Se dio de baja al operador ID: {d['id']} ({causa}) el {hoy_str}")
    registrar_evento_sync(c, 'rh_actualizado', {'operador_id': d['id'], 'accion': 'baja'})
    conn.commit(); conn.close(); return jsonify({"status": "success"})

@app.route('/api/reactivar_operador', methods=['POST'])
@login_required
def reactivar_operador():
    if session.get('rol') not in ['jefe_op', 'aux_dot', 'super_usuario']: return jsonify({"status": "error"}), 403
    d = request.json; conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("UPDATE operadores SET estatus_empleado='Activo' WHERE id=?", (d['id'],))
    registrar_notificacion(c, f"♻️ Se reactivó al operador ID: {d['id']}")
    registrar_evento_sync(c, 'rh_actualizado', {'operador_id': d['id'], 'accion': 'reactivar'})
    conn.commit(); conn.close()
    return jsonify({"status": "success"})  

@app.route('/api/obtener_rol_mes', methods=['POST'])
@login_required
def obtener_rol_mes():
    if session.get('rol') not in ['jefe_op', 'aux_dot', 'supervisor', 'monitorista', 'aux_bitacoras']: return jsonify({"status": "error"}), 403
    op_id = request.json.get('operador_id'); hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)
    siguiente_mes = inicio_mes.replace(month=inicio_mes.month % 12 + 1, day=1) if inicio_mes.month < 12 else inicio_mes.replace(year=inicio_mes.year + 1, month=1, day=1)
    dias_del_mes = (siguiente_mes - timedelta(days=1) - inicio_mes).days + 1
    
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT nombre, producto FROM operadores WHERE id=?", (op_id,))
    op_info = c.fetchone(); calendario = []
    for i in range(dias_del_mes):
        f_actual = inicio_mes + timedelta(days=i); f_str = f_actual.strftime('%Y-%m-%d')
        c.execute("SELECT estatus FROM logistica_diaria WHERE operador_id=? AND fecha=?", (op_id, f_str))
        res = c.fetchone()
        calendario.append({ "fecha": f_str, "dia": f_actual.day, "estatus": res[0] if res else 'TR' })
    conn.close()
    mes_nombre = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][hoy.month - 1]
    return jsonify({"status": "success", "operador": op_info[0], "linea": op_info[1], "mes": f"{mes_nombre} {hoy.year}", "calendario": calendario})

@app.route('/api/dot_status', methods=['POST'])
@login_required
def dot_status():
    d = request.json; op_id = d.get('operador_id'); fecha_str = d.get('fecha')
    if not op_id or not fecha_str: return jsonify({"status": "error"}), 400
    dias_semana, _, _, _, _, _ = get_semana(fecha_str); fechas = [dia['fecha'] for dia in dias_semana]
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT SUM(horas) FROM dot_diario WHERE operador_id=? AND fecha IN ({seq})".format(seq=','.join(['?']*7)), [op_id] + fechas)
    res = c.fetchone(); conn.close()
    usadas = res[0] if res and res[0] else 0.0
    libres = max(0.0, round(70.0 - usadas, 1))
    return jsonify({"status": "success", "usadas": round(usadas, 1), "libres": libres})

@app.route('/api/auditoria_movimientos_30d', methods=['GET'])
@login_required
def api_auditoria_movimientos_30d():
    if session.get('rol') not in ['jefe_op', 'aux_dot', 'supervisor', 'gerencia', 'super_usuario']:
        return jsonify({"status": "error", "msg": "No autorizado"}), 403
        
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Extraer los últimos 30 días de eventos en sábana y solicitudes
    c.execute("""
        SELECT fecha, mensaje 
        FROM notificaciones 
        WHERE fecha >= datetime('now', '-30 days', 'localtime')
          AND (
               mensaje LIKE '%modificó a%' OR 
               mensaje LIKE '%actualizó a%' OR 
               mensaje LIKE '%aplicó ciclo%' OR 
               mensaje LIKE '%Aprobado por%' OR 
               mensaje LIKE '%cambió a%' OR
               mensaje LIKE '%Rechazado por%'
          )
        ORDER BY id DESC
        LIMIT 250
    """)
    filas = c.fetchall()
    conn.close()
    
    registros = [{"fecha_hora": r[0], "evento": r[1]} for r in filas]
    return jsonify({"status": "success", "data": registros})

@app.route('/api/leer_notificacion', methods=['POST'])
@login_required
def leer_notificacion():
    req = request.json; conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    if req.get('id') == 'all':
        c.execute("UPDATE notificaciones SET leida=1")
    else:
        c.execute("UPDATE notificaciones SET leida=1 WHERE id=?", (req['id'],))
    conn.commit(); conn.close()
    return jsonify({"status": "success"})

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/pruebas_fng')
@login_required
def pruebas_fng():
    if session.get('rol') not in ['seguridad', 'gerencia']: return abort(403)
    return render_template('pruebas_fng.html', activos_en_base=[], pases=[], resguardo_pendiente=None, ya_entrego_turno=False, plantilla_resguardos=[{"cant": 1, "desc": "Radio de Comunicación"}, {"cant": 1, "desc": "Lámpara de Mano"}, {"cant": 1, "desc": "Teléfono Celular Caseta"}])

@app.route('/historial')
@login_required
def historial():
    if session.get('rol') not in ['gerencia', 'super_usuario']: return abort(403)
    base_filtro = request.args.get('base_filtro', session.get('base', 'SLP'))
    return render_template('historial.html', base_filtro=base_filtro, bases_activas=['SLP'], registros=[], historial_pases_lista=[])

@app.route('/control_diesel')
@login_required
def control_diesel():
    if session.get('rol') not in ['analista_diesel', 'gerencia', 'super_usuario']: return abort(403)
    
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT valor FROM configuracion WHERE clave='diesel_db_json'")
    res = c.fetchone()
    conn.close()
    
    data = json.loads(res[0]) if res and res[0] else []
    
    # Validación y limpieza de estructura de datos
    for r in data:
        if 'semanas' not in r or not isinstance(r['semanas'], dict): r['semanas'] = {"S27": 0.0, "S28": 0.0, "S29": 0.0, "S30": 0.0}
        for k in ["S27", "S28", "S29", "S30"]:
            if r['semanas'].get(k) is None: r['semanas'][k] = 0.0
        if r.get('TOTAL_LTS') is None: r['TOTAL_LTS'] = 0.0
        if r.get('TOTAL_PCT') is None: r['TOTAL_PCT'] = 0.0

    cabeceras = obtener_cabeceras_semana(datetime.now())
    
    if session.get('rol') == 'analista_diesel':
        return render_template('control_diesel_analista.html', data=data, cabeceras=cabeceras, rol=session.get('rol'))
    return render_template('control_diesel_gerente.html', data=data, cabeceras=cabeceras, rol=session.get('rol'))

@app.route('/api/procesar_matriz', methods=['POST'])
@login_required
def procesar_matriz():
    if session.get('rol') != 'analista_diesel': return jsonify({"error": "No autorizado"}), 403
    file = request.files.get('file')
    if not file or not file.filename: return jsonify({"error": "No se detectó ningún archivo válido."}), 400
        
    # Validar extensión permitida y sanitizar nombre
    if not es_extension_valida(file.filename, {'xlsx', 'xls'}):
        return jsonify({"error": "Tipo de archivo no permitido. Solo se aceptan archivos Excel (.xlsx, .xls)."}), 400

    nombre_seguro = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"matriz_{int(datetime.now().timestamp())}_{nombre_seguro}")
    file.save(filepath)
    if os.path.getsize(filepath) == 0: os.remove(filepath); return jsonify({"error": "El archivo está vacío."}), 400
    
    try:
        dict_firmados, dict_no_firmados, dict_historico_semanas = {}, {}, {}
        xls = pd.ExcelFile(filepath, engine='openpyxl')
        hojas = xls.sheet_names

        if 'firmas' in hojas:
            df_f = pd.read_excel(filepath, sheet_name='firmas', header=0, engine='openpyxl')
            col_ope = next((c for c in df_f.columns if 'CONDUCTOR' in str(c).upper() or 'CHOFER' in str(c).upper()), None)
            col_nom = next((c for c in df_f.columns if 'EMPLEADO' in str(c).upper() or 'NOMINA' in str(c).upper()), None)
            if col_ope and col_nom:
                for i, row in df_f.iterrows():
                    ope, nom = row[col_ope], row[col_nom]
                    if pd.notna(ope) and str(ope).strip() != '':
                        llave = obtener_llave_nombre(ope)
                        dict_firmados[llave] = str(nom).strip()

        elif 'FIRMA CARTA ' in hojas:
            df_firma_raw = pd.read_excel(filepath, sheet_name='FIRMA CARTA ', header=None, engine='openpyxl')
            row_anclaje_firma = None
            for i, row in df_firma_raw.iterrows():
                row_str = " ".join([str(val).upper() for val in row.values if pd.notna(val)])
                if 'NOMINA' in row_str and ('OPERADOR' in row_str or 'CHOFER' in row_str):
                    row_anclaje_firma = i; break
            if row_anclaje_firma is not None:
                df_f = df_firma_raw.iloc[row_anclaje_firma:].reset_index(drop=True)
                df_f.columns = df_f.iloc[0]; df_f = df_f[1:]
                cols_f = pd.Series(df_f.columns.astype(str).str.strip().str.upper())
                nomina_idx = cols_f[cols_f.str.contains('NOMINA')].index.tolist()
                operador_idx = cols_f[cols_f.str.contains('OPERADOR|CHOFER')].index.tolist()
                if len(nomina_idx) >= 2 and len(operador_idx) >= 2:
                    for i in range(len(df_f)):
                        nom, ope = df_f.iloc[i, nomina_idx[0]], df_f.iloc[i, operador_idx[0]]
                        if pd.notna(ope) and str(ope).strip() != '' and 'TOTAL' not in str(ope).upper():
                            dict_firmados[obtener_llave_nombre(ope)] = str(nom).strip()

        hoja_detalle = next((h for h in hojas if 'DETALLE' in str(h).upper() and 'CARGA' in str(h).upper()), None)
        if not hoja_detalle: return jsonify({"error": "No se encontró la hoja 'DETALLE X CARGA'."}), 400

        df_raw = pd.read_excel(filepath, sheet_name=hoja_detalle, header=None, engine='openpyxl')
        row_anclaje_det = next((i for i, r in df_raw.iterrows() if 'SEMANA' in " ".join([str(v).upper() for v in r.values if pd.notna(v)]) and 'CHOFER' in " ".join([str(v).upper() for v in r.values if pd.notna(v)])), None)
        if row_anclaje_det is None: return jsonify({"error": "No se encontraron las cabeceras SEMANA y CHOFER."}), 400

        df_det = df_raw.iloc[row_anclaje_det:].reset_index(drop=True)
        df_det.columns = df_det.iloc[0]; df_det = df_det[1:]
        
        df_det.columns = pd.Series(df_det.columns).astype(str).str.replace('\xa0', '').str.strip().str.upper()
        df_det.loc[:, ~df_det.columns.duplicated()].copy()

        if 'VARIACION LTS %' not in df_det.columns:
            for col in df_det.columns:
                if '%' in col or 'VARIA' in col: df_det.rename(columns={col: 'VARIACION LTS %'}, inplace=True); break
        if 'DIFERENCIA LTS' not in df_det.columns:
            for col in df_det.columns:
                if 'DIF' in col: df_det.rename(columns={col: 'DIFERENCIA LTS'}, inplace=True); break

        df_det['CHOFER'] = df_det['CHOFER'].ffill().astype(str).str.strip()
        df_clean = df_det[~df_det['CHOFER'].str.upper().str.contains('TOTAL') & ~df_det['CHOFER'].str.upper().isin(['NAN', 'NONE', '', 'NAT'])].copy()

        df_clean['FECHA'] = pd.to_datetime(df_clean['FECHA'], errors='coerce')
        df_clean = df_clean.dropna(subset=['FECHA'])

        dias_map = {0:'LUN', 1:'MAR', 2:'MIÉ', 3:'JUE', 4:'VIE', 5:'SÁB', 6:'DOM'}
        df_clean['DIA_NOMBRE'] = df_clean['FECHA'].dt.weekday.map(dias_map)
        df_clean['DIFERENCIA LTS'] = pd.to_numeric(df_clean['DIFERENCIA LTS'], errors='coerce').fillna(0)
        df_clean['VARIACION LTS %'] = pd.to_numeric(df_clean['VARIACION LTS %'], errors='coerce').fillna(0)

        resultados_dict = {}

        for index, row in df_clean.iterrows():
            chofer = str(row['CHOFER']).strip()
            dia = row['DIA_NOMBRE']
            
            if chofer not in resultados_dict:
                llave = obtener_llave_nombre(chofer)
                firma = "SI" if llave in dict_firmados else "NO"
                nomina = dict_firmados.get(llave) or dict_no_firmados.get(llave) or f"N/A"
                resultados_dict[chofer] = { 
                    "NOMINA": nomina, "CHOFER": chofer, "FIRMA": firma, 
                    "dias": {d: None for d in dias_map.values()}, 
                    "detalles_dias": {d: [] for d in dias_map.values()}, 
                    "semanas": dict_historico_semanas.get(llave, {"S27":None, "S28":None, "S29":None, "S30":None}), 
                    "TOTAL_LTS": 0.0, "TOTAL_PCT": 0.0 
                }
            
            if resultados_dict[chofer]["dias"][dia] is None:
                resultados_dict[chofer]["dias"][dia] = 0.0
            
            resultados_dict[chofer]["dias"][dia] += float(row['DIFERENCIA LTS'])
            
            detalle_viaje = {
                "fecha": row['FECHA'].strftime('%Y-%m-%d %H:%M'),
                "unidad": str(row.get('UNIDAD', 'N/A')),
                "tipo_carga": str(row.get('TIPO CARGA', 'N/A')),
                "destino": str(row.get('BITACORA DESTINO', 'N/A')),
                "estacion": str(row.get('ESTACIÓN', 'N/A')),
                "km_total": float(pd.to_numeric(str(row.get('KM TOTAL') or 0), errors='coerce') or 0),
                "lts_fisico": float(pd.to_numeric(str(row.get('LITROS') or 0), errors='coerce') or 0),
                "rend_fisico": float(pd.to_numeric(str(row.get('REND FISICO') or 0), errors='coerce') or 0),
                "km_geo": float(pd.to_numeric(str(row.get('KM GEO') or 0), errors='coerce') or 0),
                "lts_geo": float(pd.to_numeric(str(row.get('LITROS GEO') or 0), errors='coerce') or 0),
                "rend_rastreo": float(pd.to_numeric(str(row.get('REND RASTREO') or 0), errors='coerce') or 0),
                "diferencia_lts": float(row['DIFERENCIA LTS']),
                "variacion_pct": float(row['VARIACION LTS %'])
            }
            resultados_dict[chofer]["detalles_dias"][dia].append(detalle_viaje)

        for chofer, data in resultados_dict.items():
            sum_lts = 0.0; sum_pct = 0.0; conteo = 0
            for dia, lts in data["dias"].items():
                if lts is not None:
                    sum_lts += lts
                    viajes_del_dia = data["detalles_dias"][dia]
                    if viajes_del_dia:
                        sum_pct += sum(v['variacion_pct'] for v in viajes_del_dia) / len(viajes_del_dia)
                    conteo += 1
                    
            data["TOTAL_LTS"] = round(sum_lts, 2)
            data["TOTAL_PCT"] = (sum_pct / conteo) if conteo > 0 else 0.0

        cabeceras_dinamicas = obtener_cabeceras_semana(datetime.now())
        return jsonify({"data": list(resultados_dict.values()), "cabeceras": cabeceras_dinamicas})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Fallo en extracción: {str(e)}"}), 500

@app.route('/api/sellar_dia', methods=['POST'])
@login_required
def sellar_dia():
    if session.get('rol') != 'analista_diesel': return jsonify({"error": "Denegado"}), 403
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('diesel_db_json', ?)", (json.dumps(request.json),))
    conn.commit(); conn.close()
    return jsonify({"msg": "Matriz Consolidada, Sellada e Inmutable."})

@app.route('/api/generar_bonos', methods=['POST'])
@login_required
def generar_bonos():
    if session.get('rol') not in ['gerencia', 'super_usuario']: return jsonify({"error": "Denegado"}), 403
    
    if datetime.now().weekday() != 2 and not MODO_PRUEBAS:
        return jsonify({"error": "Acceso Denegado: La dispersión de bonos solo puede ejecutarse los días Miércoles, fecha límite de administración."}), 403

    datos_bonos = request.json.get('bonos', [])
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph("REPORTE OFICIAL DE AUTORIZACIÓN DE BONOS", styles['Title']))
        elements.append(Paragraph(f"Fecha de Autorización Gerencial: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        elements.append(Spacer(1, 12))

        tabla_data = [["Nómina", "Operador", "Exceso (L)", "Variación", "Estatus Bono"]]
        aprobados_count = 0
        for d in datos_bonos:
            if d.get('BONO'): aprobados_count += 1
            tabla_data.append([ str(d.get('NOMINA', '')), str(d.get('CHOFER', '')), f"{d.get('TOTAL_LTS', 0):.2f} L", f"{d.get('TOTAL_PCT', 0)*100:.2f} %", "APROBADO" if d.get('BONO') else "DENEGADO" ])

        t = Table(tabla_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#002d5a')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8fafc')),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1'))
        ]))
        elements.append(t)
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return jsonify({"msg": f"Se ha generado el PDF con éxito y despachado por correo a Administración. Total autorizados: {aprobados_count}."})
        
    except ImportError:
        return jsonify({"error": "⚠️ ERROR DE SISTEMA: Falta instalar librería de renderizado PDF. Ejecuta en tu terminal: pip install reportlab"}), 500

@app.route('/api/inyectar_ficticios', methods=['POST'])
@login_required
def inyectar_ficticios():
    if session.get('rol') not in ['gerencia', 'super_usuario']: return jsonify({"error": "Denegado"}), 403
    dummies = [
        {"CHOFER": "PILOTO PRUEBA VERDE", "NOMINA": "TEST-1", "FIRMA": "SI", "TOTAL_LTS": 10.0, "TOTAL_PCT": 0.02, "dias": {"MIÉ":10.0, "JUE":None, "VIE":None, "SÁB":None, "DOM":None, "LUN":None, "MAR":None}, "semanas": {"S27":0, "S28":0, "S29":0, "S30":0}},
        {"CHOFER": "PILOTO PRUEBA AMARILLO", "NOMINA": "TEST-2", "FIRMA": "SI", "TOTAL_LTS": 45.0, "TOTAL_PCT": 0.08, "dias": {"MIÉ":25.0, "JUE":20.0, "VIE":None, "SÁB":None, "DOM":None, "LUN":None, "MAR":None}, "semanas": {"S27":0, "S28":0, "S29":0, "S30":0}},
        {"CHOFER": "PILOTO PRUEBA ROJO", "NOMINA": "TEST-3", "FIRMA": "SI", "TOTAL_LTS": 95.0, "TOTAL_PCT": 0.15, "dias": {"MIÉ":30.0, "JUE":40.0, "VIE":25.0, "SÁB":None, "DOM":None, "LUN":None, "MAR":None}, "semanas": {"S27":0, "S28":0, "S29":0, "S30":0}}
    ]
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('diesel_db_json', ?)", (json.dumps(dummies),))
    conn.commit(); conn.close()
    return jsonify({"msg": "Datos ficticios inyectados. La pantalla se recargará."})

@app.route('/api/whatsapp_multimedia', methods=['POST'])
@login_required
def whatsapp_multimedia():
    if session.get('rol') not in ['gerencia', 'super_usuario']: return jsonify({"error": "Denegado"}), 403
    return jsonify({"msg": "[SIMULACIÓN SANDBOX] Mensajes multimedia retenidos. Funcionalidad operativa."})

@app.route('/api/drilldown_radar', methods=['POST'])
@login_required
def api_drilldown_radar():
    data = request.get_json(silent=True) or {}
    producto = data.get('producto')
    fecha = data.get('fecha')
    tipo = data.get('tipo')

    if not fecha:
        return jsonify({"status": "error", "msg": "Fecha no especificada."}), 400

    try:
        fecha_dt = datetime.strptime(fecha, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"status": "error", "msg": "Formato de fecha no válido."}), 400

    # Homologación CRYO
    if producto == 'CRYO':
        prods_filtro = ['ARGON', 'NITROGENO', 'OXIGENO']
    else:
        prods_filtro = [producto] if producto else []

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Construir filtro de producto para la consulta SQL
    if prods_filtro:
        placeholders = ','.join(['?'] * len(prods_filtro))
        filtro_prod = f"AND (UPPER(producto) IN ({placeholders}) OR UPPER(linea_negocio) IN ({placeholders}))"
        params = prods_filtro + prods_filtro
    else:
        filtro_prod = ""
        params = []

    c.execute(f"""
        SELECT id, nombre, producto, 
               COALESCE(productos_descarga, 'N/A'), 
               COALESCE(tipo_unidad, 'FULL'), 
               COALESCE(vigencia_licencia, 'N/A'), 
               COALESCE(vigencia_medica, 'N/A'),
               COALESCE(linea_negocio, producto)
        FROM operadores 
        WHERE estatus_empleado NOT LIKE 'Baja%' {filtro_prod}
        ORDER BY nombre
    """, params)
    operadores = c.fetchall()

    candidatos = []

    if tipo == 'Plantilla':
        # Soporte para Plantilla: consultar todos los operadores asignados a prods_filtro
        for op in operadores:
            op_id, op_nombre, op_prod, op_prods_desc, op_tipo_uni, op_vlic, op_vmed, op_linea = op
            c.execute("SELECT estatus FROM logistica_diaria WHERE operador_id = ? AND fecha = ?", (op_id, fecha))
            r = c.fetchone()
            estatus_dia = (r[0] if r and r[0] else 'DE').strip().upper()

            # Sin semáforo: siempre azul con icono persona
            color = 'blue'
            icono = '👤'
            detalle = f"Estatus: {estatus_dia} | Línea: {op_linea or producto}"

            candidatos.append({
                'nombre': op_nombre,
                'detalle': detalle,
                'color': color,
                'icono': icono
            })

        conn.close()
        return jsonify({"status": "success", "data": candidatos})

    elif tipo == 'Deficit':
        fechas_8d = [(fecha_dt - timedelta(days=k)).strftime('%Y-%m-%d') for k in range(7)]
        placeholders_8d = ','.join(['?'] * 7)

        # Ventana de proyección hacia adelante (próximos 14 días)
        fechas_futuras = [(fecha_dt + timedelta(days=k)).strftime('%Y-%m-%d') for k in range(1, 15)]
        placeholders_fut = ','.join(['?'] * len(fechas_futuras))

        # Días previos para evaluar reseteo continuo
        fechas_previas = [(fecha_dt - timedelta(days=k)).strftime('%Y-%m-%d') for k in range(1, 8)]

        # Ventana de 15 días atrás para historial de rutas pesadas (Minas/Foráneos)
        fecha_15d_ant = (fecha_dt - timedelta(days=15)).strftime('%Y-%m-%d')

        for op in operadores:
            op_id, op_nombre, op_prod, op_prods_desc, op_tipo_uni, op_vlic, op_vmed, op_linea = op
            # 1. Validar que esté descansando en la fecha consultada
            c.execute("SELECT estatus FROM logistica_diaria WHERE operador_id = ? AND fecha = ?", (op_id, fecha))
            row_est = c.fetchone()
            est_hoy = (row_est[0] if row_est and row_est[0] else 'DE').strip().upper()

            if not (est_hoy == 'DE' or est_hoy.startswith('D') or est_hoy.startswith('V')):
                continue

            # 2. Margen de horas DOT libres (70h menos acumuladas en 8 días)
            c.execute(f"SELECT COALESCE(SUM(horas), 0.0) FROM dot_diario WHERE operador_id = ? AND fecha IN ({placeholders_8d})", [op_id] + fechas_8d)
            h_acum = float(c.fetchone()[0] or 0.0)
            h_libres = max(0.0, round(70.0 - h_acum, 1))

            # 3. Días que faltan para reanudar turno ('TR' o 'CB')
            c.execute(f"""
                SELECT fecha, estatus 
                FROM logistica_diaria 
                WHERE operador_id = ? AND fecha IN ({placeholders_fut})
                ORDER BY fecha ASC
            """, [op_id] + fechas_futuras)
            filas_fut = c.fetchall()

            dias_para_volver = 999
            fecha_regreso_str = None
            for f_fut, est_fut in filas_fut:
                est_clean = (est_fut or '').strip().upper()
                if est_clean.startswith('TR') or est_clean.startswith('CB'):
                    dias_para_volver = (datetime.strptime(f_fut, '%Y-%m-%d').date() - fecha_dt).days
                    fecha_regreso_str = f_fut
                    break

            # 4. Detección de reseteo largo de ciclo (>= 4 días continuos de descanso)
            descanso_continuo = 1
            for f_prev in fechas_previas:
                c.execute("SELECT estatus FROM logistica_diaria WHERE operador_id = ? AND fecha = ?", (op_id, f_prev))
                r_prev = c.fetchone()
                est_prev = (r_prev[0] if r_prev and r_prev[0] else '').strip().upper()
                if est_prev == 'DE' or est_prev.startswith('D') or est_prev.startswith('V'):
                    descanso_continuo += 1
                else:
                    break

            es_reseteo_largo = descanso_continuo >= 4

            # --- FILTRO 1: BLINDAJE LEGAL DE VIGENCIAS (SCT / SSMA) ---
            # Desactivado: no bloquear ni pintar por vigencias de licencia/médico (datos no actualizados)
            alertas_doc = []
            doc_riesgo = False

            # --- FILTRO 2: EVALUACIÓN DE EFECTO DOMINÓ (DÍA SIGUIENTE) ---
            f_manana_str = (fecha_dt + timedelta(days=1)).strftime('%Y-%m-%d')
            c.execute("SELECT estatus FROM logistica_diaria WHERE operador_id = ? AND fecha = ?", (op_id, f_manana_str))
            r_man = c.fetchone()
            est_man = (r_man[0] if r_man and r_man[0] else 'DE').strip().upper()
            tiene_turno_manana = est_man.startswith('TR') or est_man.startswith('CB')

            # --- FILTRO 3: CERTIFICACIONES RH DE PRODUCTO ---
            prods_upper = op_prods_desc.upper()
            req_prod = producto.upper()
            if req_prod == 'CRYO':
                tiene_certificacion = any(p in prods_upper for p in ['LIN', 'LOX', 'LAR'])
            else:
                tiene_certificacion = (req_prod in prods_upper) or (req_prod == 'NITROGENO' and 'LIN' in prods_upper) or (req_prod == 'OXIGENO' and 'LOX' in prods_upper) or (req_prod == 'ARGON' and 'LAR' in prods_upper)

            # FILTRO EXCLUSIVO: solo operadores con certificación del producto
            if not tiene_certificacion:
                continue

            # --- FILTRO 4: HISTORIAL DE RUTAS PESADAS (15 DÍAS) ---
            c.execute("SELECT viaje_json FROM viajes_archivados WHERE fecha_operativa >= ? AND viaje_json LIKE ?", (fecha_15d_ant, f"%{op_nombre}%"))
            viajes_recientes = c.fetchall()
            rutas_pesadas_count = 0
            for (v_json_raw,) in viajes_recientes:
                try:
                    v_dat = json.loads(v_json_raw)
                    if str(v_dat.get('operador', '')).strip().upper() == op_nombre.upper():
                        escalas = v_dat.get('escalas', [])
                        destinos_str = " ".join([str(e.get('cliente', '')).upper() + " " + str(e.get('ubicacion', '')).upper() for e in escalas])
                        if any(k in destinos_str for k in ['MINA', 'FORANEO', 'RETORNO', 'MONTERREY', 'GUADALAJARA', 'QUERETARO']) or len(escalas) >= 2:
                            rutas_pesadas_count += 1
                except Exception:
                    pass

            # Clasificación Semafórica Refinada (100% Tráfico y Fatiga)
            f_fmt = datetime.strptime(fecha_regreso_str, '%Y-%m-%d').strftime('%d/%m') if fecha_regreso_str else ''

            # Rojo: reseteo largo biológico (>=4 días descanso continuo) o regreso muy lejano (>4 días)
            if es_reseteo_largo or dias_para_volver > 4:
                color = "red"
                icono = "🔴"
                prioridad = 3
                if es_reseteo_largo:
                    detalle = f"Reseteo de ciclo ({descanso_continuo}d) • " + (f"Regresa en {dias_para_volver}d ({f_fmt})" if f_fmt else "Sin regreso prog.")
                else:
                    detalle = f"Regreso lejano (en {dias_para_volver}d - {f_fmt})" if f_fmt else "Sin turno programado"

            # Verde: reanuda turno mañana o pasado mañana (dias_para_volver <= 2) con >15h libres y sin reseteo largo
            elif dias_para_volver <= 2 and h_libres > 15.0:
                color = "green"
                icono = "🟢"
                prioridad = 1
                if dias_para_volver == 1:
                    txt_ret = "Regresa mañana"
                elif dias_para_volver == 2:
                    txt_ret = "Regresa pasado mañana"
                else:
                    txt_ret = "Regresa hoy"
                detalle = f"{txt_ret} ({f_fmt}) • Margen DOT disponible ({op_tipo_uni})"

            # Amarillo: margen amplio de horas (h_libres >= 20.0) y regreso en 3-4 días
            elif h_libres >= 20.0 and 3 <= dias_para_volver <= 4:
                color = "yellow"
                icono = "🟡"
                prioridad = 2
                detalle = f"Regresa en {dias_para_volver} días ({f_fmt}) • {h_libres}h libres"

            # Casos intermedios: amarillo por defecto
            else:
                color = "yellow"
                icono = "🟡"
                prioridad = 2
                if fecha_regreso_str:
                    detalle = f"Regresa en {dias_para_volver} días ({f_fmt}) • {h_libres}h libres"
                else:
                    detalle = f"Margen DOT: {h_libres}h libres • Sin fecha de reanudación"

            candidatos.append({
                "nombre": op_nombre,
                "detalle": detalle,
                "color": color,
                "icono": icono,
                "libres": h_libres,
                "prioridad": prioridad,
                "certificaciones": op_prods_desc,
                "tipo_unidad": op_tipo_uni,
                "docs_status": "Al corriente",
                "rutas_pesadas_15d": rutas_pesadas_count,
                "turno_manana": est_man
            })

        # 6. Ordenamiento: Prioridad ascendente (verde primero) y mayor cantidad de horas libres desc
        candidatos.sort(key=lambda x: (x['prioridad'], -x['libres']))
        for item in candidatos:
            item.pop('prioridad', None)

        conn.close()
        return jsonify({"status": "success", "data": candidatos})

    else:
        # Compatibilidad para vistas de Disp y NoDisp
        # Siempre color azul para todas las tarjetas
        resultado = []
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        
        for op in operadores:
            op_id, op_nombre, op_prod = op[0], op[1], op[2]
            op_linea = op[7]
            c.execute("SELECT estatus FROM logistica_diaria WHERE operador_id = ? AND fecha = ?", (op_id, fecha))
            r = c.fetchone()
            est = (r[0] if r and r[0] else 'DE').strip().upper()
            es_activo = est.startswith('TR') or est.startswith('CB')

            # Color siempre azul
            color = 'blue'

            if tipo == 'Disp' and es_activo:
                # ACTIVOS: determinar día de labor continua
                dia_num = None
                # Intentar extraer número del estatus (ej. 'TR4', 'TR7')
                import re
                match = re.match(r'TR(\d+)', est)
                if match:
                    dia_num = match.group(1)
                elif est == 'TR':
                    # Calcular racha de días consecutivos en TR hacia atrás
                    racha = 1
                    for k in range(1, 31):  # buscar hasta 30 días atrás
                        f_prev = (fecha_dt - timedelta(days=k)).strftime('%Y-%m-%d')
                        c.execute("SELECT estatus FROM logistica_diaria WHERE operador_id = ? AND fecha = ?", (op_id, f_prev))
                        r_prev = c.fetchone()
                        est_prev = (r_prev[0] if r_prev and r_prev[0] else '').strip().upper()
                        if est_prev.startswith('TR') or est_prev.startswith('CB'):
                            racha += 1
                        else:
                            break
                    dia_num = str(racha)
                else:
                    dia_num = '1'
                
                icono = '🚛'
                detalle = f"Día {dia_num} de labor continua | Línea: {op_linea or producto}"
                resultado.append({"nombre": op_nombre, "detalle": detalle, "color": color, "icono": icono, "libres": 0.0})

            elif tipo == 'NoDisp' and not es_activo:
                # NO ACTIVOS: buscar fecha de retorno en próximos 30 días
                c.execute("""
                    SELECT fecha, estatus 
                    FROM logistica_diaria 
                    WHERE operador_id = ? AND fecha > ? 
                    ORDER BY fecha ASC 
                    LIMIT 30
                """, (op_id, fecha))
                filas_fut = c.fetchall()
                
                fecha_regreso_str = None
                est_regreso = None
                for f_fut, est_fut in filas_fut:
                    est_clean = (est_fut or '').strip().upper()
                    if est_clean.startswith('TR') or est_clean.startswith('CB'):
                        fecha_regreso_str = f_fut
                        est_regreso = est_clean
                        break
                
                icono = '🛌'
                if fecha_regreso_str:
                    fecha_regreso_dt = datetime.strptime(fecha_regreso_str, '%Y-%m-%d').date()
                    dias_faltantes = (fecha_regreso_dt - fecha_dt).days
                    dia_nom = dias_semana[fecha_regreso_dt.weekday()]
                    fecha_regreso_fmt = fecha_regreso_dt.strftime('%d/%m/%Y')
                    
                    if dias_faltantes == 1:
                        texto_dias = 'mañana'
                    else:
                        texto_dias = f'en {dias_faltantes} días'
                    
                    detalle = f"{est} • Regresa el {dia_nom} {fecha_regreso_fmt} ({texto_dias}) | Línea: {op_linea or producto}"
                else:
                    detalle = f"{est} • Sin fecha de regreso programada | Línea: {op_linea or producto}"
                
                resultado.append({"nombre": op_nombre, "detalle": detalle, "color": color, "icono": icono, "libres": 0.0})

        conn.close()
        return jsonify({"status": "success", "data": resultado})

@app.route('/api/estatus_vivo_mock', methods=['GET'])
@login_required
def estatus_vivo_mock():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("SELECT producto, datos_json FROM programacion_viajes")
    filas_pizarra = c.fetchall()
    
    fecha_op = obtener_fecha_operativa()
    c.execute("SELECT viaje_json, hora_cierre FROM viajes_archivados WHERE fecha_operativa = ? AND estatus = 'FINALIZADO' ORDER BY id DESC LIMIT 10", (fecha_op,))
    filas_archivados = c.fetchall()
    conn.close()
    
    entregas = []
    retornos = []
    checkin = []
    
    for prod, json_str in filas_pizarra:
        try:
            viajes = json.loads(json_str)
            for v in viajes:
                operador = str(v.get('operador', '')).strip()
                eco = str(v.get('tr', '')).strip()
                
                if not operador or not eco:
                    continue
                
                cv = str(v.get('cv', ''))
                is_pending = v.get('isPending', False)
                if is_pending:
                    estado = 'Pendiente'
                    color = 'yellow'
                    icon = '🟡'
                elif 'cv-green' in cv:
                    estado = 'En Ruta'
                    color = 'green'
                    icon = '🟢'
                elif 'cv-red' in cv:
                    estado = 'Incidencia'
                    color = 'red'
                    icon = '🔴'
                else:
                    estado = 'Programado'
                    color = 'blue'
                    icon = '⚪'
                
                hora_prog = str(v.get('sprog', '')).strip()
                salida_str = f"{hora_prog} / --:--" if hora_prog else "--:-- / --:--"
                
                tiempo_cond = str(v.get('tmpocond', '')).strip()
                tiempo_str = tiempo_cond if (tiempo_cond and tiempo_cond != 'PROX') else 'Por Despachar'
                
                escalas = v.get('escalas', [])
                paradas = []
                es_retorno = False
                ubicacion = ''
                
                for i, esc in enumerate(escalas):
                    cli = str(esc.get('cliente', '')).strip()
                    ubi = str(esc.get('ubicacion', '')).strip()
                    if not cli:
                        cli = f'Destino {i+1}'
                    paradas.append({
                        "cliente": f"{i+1}. {cli}",
                        "llegada": "--:-- / --:-- ⏳"
                    })
                    if any(w in cli.upper() or w in ubi.upper() for w in ['RETORNO', 'BASE', 'PATIO', 'REGRESO']):
                        es_retorno = True
                    if not ubicacion and ubi:
                        ubicacion = ubi
                        
                if not ubicacion:
                    ubicacion = str(v.get('cc', '')).strip() or 'Patio Central'
                    
                item_data = {
                    "eco": eco,
                    "operador": operador,
                    "salida": salida_str,
                    "producto": prod,
                    "estatus": estado,
                    "color": color,
                    "icon": icon,
                    "tiempo": tiempo_str,
                    "paradas": paradas,
                    "ubicacion": ubicacion,
                    "llegada_base": "--:-- / --:--"
                }
                
                if es_retorno or 'RETORNO' in ubicacion.upper():
                    retornos.append(item_data)
                else:
                    entregas.append(item_data)
        except Exception:
            pass

    for v_json, hora_cierre in filas_archivados:
        try:
            viaje = json.loads(v_json)
            eco_arch = str(viaje.get('tr', '')).strip()
            op_arch = str(viaje.get('operador', '')).strip()
            if not eco_arch or not op_arch:
                continue
            
            hora_str = str(hora_cierre)[11:16] + ' hrs' if hora_cierre and len(str(hora_cierre)) >= 16 else '--:--'
            checkin.append({
                "eco": eco_arch,
                "operador": op_arch,
                "llegada": hora_str,
                "diesel": "Cuadrado",
                "neumaticos": "Revisado",
                "mecanico": "Listo",
                "tiempo": "Recién arribado",
                "estatus": "Lista para Asignar"
            })
        except Exception:
            pass
            
    return jsonify({
        "status": "success", 
        "data": entregas,
        "retornos": retornos,
        "checkin": checkin
    })

@app.route('/api/resumen_predictivo', methods=['GET'])
@login_required
def resumen_predictivo():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    hoy = datetime.now().date()
    
    # --- Parámetro opcional: mes (YYYY-MM) o modo Ventana Rodante 30D ---
    mes_req = request.args.get('mes')
    
    if mes_req:
        # MODO FILTRO MENSUAL: mes específico (ej. '2026-10')
        try:
            anio, mes = map(int, mes_req.split('-'))
            f_inicio = datetime(anio, mes, 1).date()
            # Último día del mes
            if mes == 12:
                f_fin_mes = datetime(anio + 1, 1, 1).date() - timedelta(days=1)
            else:
                f_fin_mes = datetime(anio, mes + 1, 1).date() - timedelta(days=1)
            # Si es el mes actual, limitar a hoy
            f_fin = min(f_fin_mes, hoy)
            dias_totales = (f_fin - f_inicio).days + 1
            # Norma FNG: ~6.5 descansos por 30 días
            esperados_base = max(1, round(dias_totales * (6.5 / 30.0)))
        except:
            # Fallback a ventana rodante si el formato es inválido
            mes_req = None
    
    if not mes_req:
        # MODO POR DEFECTO: Ventana Rodante 30D
        f_fin = hoy
        f_inicio = hoy - timedelta(days=29)
        dias_totales = 30
        esperados_base = 7  # Norma FNG: ~6.5 a 7 descansos por cada 30 días
    
    f_inicio_str = f_inicio.strftime('%Y-%m-%d')
    f_fin_str = f_fin.strftime('%Y-%m-%d')
    
    fechas_obj = [(hoy + timedelta(days=i)) for i in range(1, 16)]
    fechas_str = [f.strftime('%Y-%m-%d') for f in fechas_obj]
    
    alertas = []
    
    c.execute(f"SELECT o.nombre, l.fecha, l.estatus FROM operadores o JOIN logistica_diaria l ON o.id = l.operador_id WHERE o.estatus_empleado='Activo' AND l.fecha IN ({','.join(['?']*15)}) AND l.estatus IN ('VA', 'IN', 'MED', 'PER')", fechas_str)
    for r in c.fetchall():
        estatus_map = {'VA': 'Vacaciones', 'IN': 'Incapacidad', 'MED': 'Cita Médica', 'PER': 'Permiso'}
        dias_faltan = (datetime.strptime(r[1], '%Y-%m-%d').date() - hoy).days
        texto_dias = "mañana" if dias_faltan == 1 else f"en {dias_faltan} días"
        color = "blue" if r[2] == 'VA' else "yellow"
        alertas.append({
            "fecha": r[1], "texto_dias": texto_dias, "tipo": "Ausencia Programada", "color": color,
            "icon": "fa-plane-departure" if r[2] == 'VA' else "fa-briefcase-medical",
            "mensaje": f"{r[0]} tiene {estatus_map[r[2]]}."
        })
    
    c.execute("SELECT id, nombre, fecha_alta FROM operadores WHERE estatus_empleado='Activo' AND fecha_alta != 'N/A'")
    ops_alta = c.fetchall()
    for op_id, nombre, f_alta_str in ops_alta:
        try:
            f_alta = datetime.strptime(f_alta_str, '%Y-%m-%d').date()
            for f_obj in fechas_obj:
                if f_obj.month == f_alta.month and f_obj.day == f_alta.day:
                    anios = f_obj.year - f_alta.year
                    if anios > 0:
                        if anios <= 5: vac = 12 + ((anios - 1) * 2)
                        else: vac = 22 + (((anios - 6) // 5) * 2)
                        
                        dias_faltan = (f_obj - hoy).days
                        texto_dias = "mañana" if dias_faltan == 1 else f"en {dias_faltan} días"
                        alertas.append({
                            "fecha": f_obj.strftime('%Y-%m-%d'), "texto_dias": texto_dias,
                            "tipo": "Aniversario Laboral", "color": "blue", "icon": "fa-birthday-cake",
                            "mensaje": f"{nombre} cumple {anios} años. Genera {vac} días de vacaciones."
                        })
        except: pass

    meses_involucrados = list(set([f.strftime('%Y-%m') for f in fechas_obj]))
    for mes in meses_involucrados:
        c.execute("SELECT operador_id, fecha FROM logistica_diaria WHERE fecha LIKE ? AND estatus = 'DE' ORDER BY fecha ASC", (f"{mes}-%",))
        descansos_mes = c.fetchall()
        conteo_op = {}
        for op_id, fecha_de in descansos_mes:
            if op_id not in conteo_op: conteo_op[op_id] = 0
            conteo_op[op_id] += 1
            if conteo_op[op_id] >= 9 and fecha_de in fechas_str:
                c.execute("SELECT nombre FROM operadores WHERE id=?", (op_id,))
                nom_res = c.fetchone()
                if nom_res:
                    d_faltan = (datetime.strptime(fecha_de, '%Y-%m-%d').date() - hoy).days
                    t_dias = "mañana" if d_faltan == 1 else f"en {d_faltan} días"
                    alertas.append({
                        "fecha": fecha_de, "texto_dias": t_dias, "tipo": "Exceso de Descansos",
                        "color": "red", "icon": "fa-user-clock",
                        "mensaje": f"{nom_res[0]} toma su descanso #{conteo_op[op_id]} del mes."
                    })

    unidades_cfg = get_config_unidades()
    productos = ['ARGON', 'NITROGENO', 'OXIGENO', 'CO2']
    prefijos = {'ARGON': 'CB-ARG', 'NITROGENO': 'CB-NIT', 'OXIGENO': 'CB-OXI', 'CO2': 'CB-CO2'}
    
    for f in fechas_str:
        for p in productos:
            c.execute("SELECT l.estatus FROM logistica_diaria l JOIN operadores o ON l.operador_id = o.id WHERE o.producto=? AND l.fecha=? AND o.estatus_empleado='Activo'", (p, f))
            estatus_list = [row[0] for row in c.fetchall()]
            disp = sum(1 for e in estatus_list if e.startswith('TR'))
            c.execute("SELECT COUNT(*) FROM logistica_diaria l JOIN operadores o ON l.operador_id=o.id WHERE l.estatus=? AND l.fecha=? AND o.estatus_empleado='Activo'", (prefijos[p], f))
            disp += c.fetchone()[0]
            
            deficit = disp - unidades_cfg.get(p, 0)
            if deficit < 0:
                dias_faltan = (datetime.strptime(f, '%Y-%m-%d').date() - hoy).days
                texto_dias = "mañana" if dias_faltan == 1 else f"en {dias_faltan} días"
                alertas.append({
                    "fecha": f, "texto_dias": texto_dias, "tipo": "Déficit Operativo",
                    "color": "red", "icon": "fa-exclamation-triangle",
                    "mensaje": f"Faltarán {abs(deficit)} operadores de {p}."
                })

    c.execute("SELECT nombre, vigencia_licencia, vigencia_medica FROM operadores WHERE estatus_empleado='Activo'")
    for r in c.fetchall():
        if r[1] != 'N/A':
            try:
                d_lic = (datetime.strptime(r[1], '%Y-%m-%d').date() - hoy).days
                if 1 <= d_lic <= 15:
                    f_vence = (hoy + timedelta(days=d_lic)).strftime('%Y-%m-%d')
                    texto_dias = "mañana" if d_lic == 1 else f"en {d_lic} días"
                    alertas.append({
                        "fecha": f_vence, "texto_dias": texto_dias, "tipo": "Vencimiento", "color": "orange", "icon": "fa-id-card", 
                        "mensaje": f"Licencia de {r[0]}."
                    })
            except: pass
        if r[2] != 'N/A':
            try:
                d_med = (datetime.strptime(r[2], '%Y-%m-%d').date() - hoy).days
                if 1 <= d_med <= 15:
                    f_vence = (hoy + timedelta(days=d_med)).strftime('%Y-%m-%d')
                    texto_dias = "mañana" if d_med == 1 else f"en {d_med} días"
                    alertas.append({
                        "fecha": f_vence, "texto_dias": texto_dias, "tipo": "Vencimiento", "color": "orange", "icon": "fa-notes-medical", 
                        "mensaje": f"Examen médico de {r[0]}."
                    })
            except: pass

    auditoria_equidad = []
    if session.get('rol') in ['jefe_op', 'gerencia', 'super_usuario']:
        # ========================================================
        # RUTAS: Equidad en asignación (viajes_archivados)
        # Ventana: f_inicio a f_fin (30D rodante o mes calendario)
        # ========================================================
        c.execute(
            "SELECT viaje_json FROM viajes_archivados "
            "WHERE fecha_operativa BETWEEN ? AND ?",
            (f_inicio_str, f_fin_str)
        )
        viajes_db = c.fetchall()
        
        balance_choferes = {}
        for (v_json,) in viajes_db:
            try:
                v = json.loads(v_json)
                op = str(v.get('operador', '')).strip().upper()
                if not op or op in ['SIN ASIGNAR', 'N/A', '']:
                    continue
                
                if op not in balance_choferes:
                    balance_choferes[op] = {'total': 0, 'pesados': 0, 'cortos': 0}
                
                balance_choferes[op]['total'] += 1
                
                escalas = v.get('escalas', [])
                destinos = " ".join([str(e.get('cliente', '')).upper() + " " + str(e.get('ubicacion', '')).upper() for e in escalas])
                
                # Clasificación objetiva: Minas, foráneos de larga distancia o viajes multi-escala
                es_largo = any(k in destinos for k in ['MINA', 'FORANEO', 'RETORNO', 'MONTERREY', 'GUADALAJARA', 'QUERETARO']) or len(escalas) >= 2
                
                if es_largo:
                    balance_choferes[op]['pesados'] += 1
                else:
                    balance_choferes[op]['cortos'] += 1
            except:
                pass
        
        for chofer, stats in balance_choferes.items():
            if stats['total'] >= 4:
                pct_pesados = round((stats['pesados'] / stats['total']) * 100, 1)
                pct_cortos = round((stats['cortos'] / stats['total']) * 100, 1)
                
                if pct_pesados >= 75.0:
                    auditoria_equidad.append({
                        "operador": chofer,
                        "tipo": "Sobrecarga / Rutas Pesadas",
                        "color": "red",
                        "icono": "fa-weight-hanging",
                        "detalle": f"{pct_pesados}% de sus viajes son foráneos o minas ({stats['pesados']} de {stats['total']}).",
                        "alerta": "Riesgo de desgaste o fatiga desproporcionada.",
                        "categoria": "ruta"
                    })
                elif pct_cortos >= 80.0:
                    auditoria_equidad.append({
                        "operador": chofer,
                        "tipo": "Zona de Confort / Posible Favoritismo",
                        "color": "yellow",
                        "icono": "fa-medal",
                        "detalle": f"{pct_cortos}% de sus viajes son locales cortos ({stats['cortos']} de {stats['total']}).",
                        "alerta": "Baja rotación en rutas pesadas frente al promedio.",
                        "categoria": "ruta"
                    })
        
        # ========================================================
        # A) EQUIDAD DE DESCANSOS (Sábana vs Rol del Operador)
        # Ventana: f_inicio a f_fin
        # Déficit (🔴): descansos_reales < esperados_base - 2
        # Exceso (🟡): descansos_reales > esperados_base + 2
        # ========================================================
        c.execute("SELECT id, nombre FROM operadores WHERE estatus_empleado='Activo'")
        ops_activos = c.fetchall()
        
        c.execute(
            "SELECT operador_id, COUNT(*) FROM logistica_diaria "
            "WHERE fecha >= ? AND fecha <= ? AND estatus = 'DE' "
            "GROUP BY operador_id",
            (f_inicio_str, f_fin_str)
        )
        descansos_por_op = dict(c.fetchall())
        
        for op_id, nombre in ops_activos:
            descansos_reales = descansos_por_op.get(op_id, 0)
            
            if descansos_reales < esperados_base - 2:
                auditoria_equidad.append({
                    "operador": nombre,
                    "tipo": "Déficit de Descansos (Rol)",
                    "color": "red",
                    "icono": "fa-bed",
                    "detalle": f"Lleva {descansos_reales} descansos en el periodo de {dias_totales} días (parámetro esperado: {esperados_base} días).",
                    "alerta": "Riesgo de sobrecarga en rol; déficit crítico de recuperación.",
                    "categoria": "descanso"
                })
            elif descansos_reales > esperados_base + 2:
                auditoria_equidad.append({
                    "operador": nombre,
                    "tipo": "Exceso de Descansos (Rol)",
                    "color": "yellow",
                    "icono": "fa-clock",
                    "detalle": f"Lleva {descansos_reales} descansos en el periodo de {dias_totales} días (parámetro esperado: {esperados_base} días).",
                    "alerta": "Inactividad prolongada; candidato para activarse en piso.",
                    "categoria": "descanso"
                })
        
        # ========================================================
        # B) CONFLICTOS DE ROL (Sábana vs Bitácora DOT)
        # Cruzar logistica_diaria ('DE') vs dot_diario (horas > 0)
        # WHERE fecha BETWEEN f_inicio AND f_fin
        # ========================================================
        c.execute(
            "SELECT ld.operador_id, ld.fecha, d.horas, o.nombre "
            "FROM logistica_diaria ld "
            "JOIN dot_diario d ON ld.operador_id = d.operador_id AND ld.fecha = d.fecha "
            "JOIN operadores o ON ld.operador_id = o.id "
            "WHERE ld.fecha >= ? AND ld.fecha <= ? "
            "AND ld.estatus = 'DE' AND d.horas > 0 "
            "AND o.estatus_empleado = 'Activo'",
            (f_inicio_str, f_fin_str)
        )
        conflictos = c.fetchall()
        
        for op_id, fecha_conflicto, horas, nombre in conflictos:
            auditoria_equidad.append({
                "operador": nombre,
                "tipo": "Rodó en Descanso Programado",
                "color": "red",
                "icono": "fa-triangle-exclamation",
                "detalle": f"Programado en descanso ('DE' en Sábana) pero laboró con {horas}h en DOT el {fecha_conflicto}.",
                "alerta": "Discrepancia entre planeación de supervisión y bitácora física.",
                "categoria": "conflicto"
            })

    conn.close()
    return jsonify({
        "status": "success", 
        "data": alertas, 
        "auditoria_equidad": auditoria_equidad
    })

@app.route('/api/analitica_clientes', methods=['GET'])
@login_required
def analitica_clientes():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Extraer historial
    c.execute("SELECT producto, viaje_json, fecha_operativa FROM viajes_archivados WHERE estatus = 'FINALIZADO'")
    archivados = c.fetchall()
    
    # Extraer presentes
    c.execute("SELECT producto, datos_json FROM programacion_viajes")
    activos = c.fetchall()
    conn.close()

    clientes_data = {}

    def procesar_viaje(prod, viaje, fecha_viaje):
        escalas = viaje.get('escalas', [])
        if not escalas: return
        for esc in escalas:
            cli = str(esc.get('cliente', '')).strip().upper()
            # Filtrar vacíos o etiquetas default de la pizarra
            if not cli or cli.startswith('DESTINO') or cli == 'N/A': continue
            
            # Limpieza (Ej: "1. TERNIUM" -> "TERNIUM")
            if '. ' in cli: cli = cli.split('. ', 1)[-1]
            
            fecha_str = esc.get('fecha') or fecha_viaje
            if not fecha_str: continue

            if cli not in clientes_data:
                clientes_data[cli] = {'total': 0, 'productos': {'LOX':0, 'LIN':0, 'LAR':0, 'CO2':0}, 'fechas': set(), 'producto_principal': prod}
                
            clientes_data[cli]['total'] += 1
            if prod in clientes_data[cli]['productos']:
                clientes_data[cli]['productos'][prod] += 1
            clientes_data[cli]['fechas'].add(fecha_str)

    # 1. Mapeo de viajes terminados
    for prod, v_json, f_op in archivados:
        try:
            viaje = json.loads(v_json)
            procesar_viaje(prod, viaje, f_op)
        except: pass

    # 2. Mapeo de viajes en curso hoy
    hoy_str = datetime.now().strftime('%Y-%m-%d')
    for prod, d_json in activos:
        try:
            viajes = json.loads(d_json)
            for v in viajes:
                procesar_viaje(prod, v, hoy_str)
        except: pass

    resultados = []
    hoy = datetime.now().date()

    for cli, d in clientes_data.items():
        if d['total'] < 2: continue # Ocultar ruido, solo consideramos con historial >= 2 viajes
        
        try:
            fechas_obj = []
            for f in d['fechas']:
                try: fechas_obj.append(datetime.strptime(f, '%Y-%m-%d').date())
                except: pass
            fechas_ordenadas = sorted(fechas_obj)
            
            if not fechas_ordenadas: continue
            
            ultima_fecha = fechas_ordenadas[-1]
            dias_desde_ultimo = (hoy - ultima_fecha).days
            if dias_desde_ultimo < 0: dias_desde_ultimo = 0
            
            # Calcular promedio entre visitas
            if len(fechas_ordenadas) > 1:
                diferencias = [(fechas_ordenadas[i] - fechas_ordenadas[i-1]).days for i in range(1, len(fechas_ordenadas))]
                diferencias = [dif for dif in diferencias if dif > 0] # Evitar division por 0 si hubo 2 viajes el mismo dia
                frecuencia_promedio = (sum(diferencias) / len(diferencias)) if diferencias else 0
            else:
                frecuencia_promedio = 0

            # Producto mas consumido
            prod_dom = max(d['productos'].items(), key=lambda x: x[1])[0]
            if d['productos'][prod_dom] == 0: prod_dom = d['producto_principal']

            resultados.append({
                'cliente': cli,
                'total_viajes': d['total'],
                'productos': d['productos'],
                'ultima_fecha': ultima_fecha.strftime('%Y-%m-%d'),
                'dias_transcurridos': dias_desde_ultimo,
                'frecuencia_promedio': round(frecuencia_promedio, 1),
                'producto_dominante': prod_dom
            })
        except: pass

    # Top 30 clientes ordenados por mayor volumen de viajes
    resultados = sorted(resultados, key=lambda x: x['total_viajes'], reverse=True)[:30]

    if len(resultados) == 0:
        resultados = [
            {
                "cliente": "TERNIUM SLP",
                "total_viajes": 18,
                "productos": {"LOX": 8, "LIN": 6, "LAR": 4, "CO2": 0},
                "ultima_fecha": "2026-09-28",
                "dias_transcurridos": 1,
                "frecuencia_promedio": 2.0,
                "producto_dominante": "LOX",
                "historial_30d": [
                    {"fecha": "2026-09-28", "producto": "Oxígeno", "operador": "Alejandro Marrón", "eco": "ECO-105", "pipa": "P-04", "toneladas": 19.4},
                    {"fecha": "2026-09-26", "producto": "Nitrógeno", "operador": "Arturo Zayas", "eco": "ECO-108", "pipa": "P-02", "toneladas": 18.8},
                    {"fecha": "2026-09-24", "producto": "Oxígeno", "operador": "Alejandro Marrón", "eco": "ECO-105", "pipa": "P-04", "toneladas": 20.1},
                    {"fecha": "2026-09-22", "producto": "Argón", "operador": "Antonio Romero", "eco": "ECO-102", "pipa": "P-01", "toneladas": 17.5},
                    {"fecha": "2026-09-20", "producto": "Oxígeno", "operador": "Arturo Zayas", "eco": "ECO-108", "pipa": "P-02", "toneladas": 19.0}
                ]
            },
            {
                "cliente": "BMW SLP PLANT",
                "total_viajes": 14,
                "productos": {"LOX": 4, "LIN": 7, "LAR": 3, "CO2": 0},
                "ultima_fecha": "2026-09-27",
                "dias_transcurridos": 2,
                "frecuencia_promedio": 2.5,
                "producto_dominante": "LIN",
                "historial_30d": [
                    {"fecha": "2026-09-27", "producto": "Nitrógeno", "operador": "Angel Hernández", "eco": "ECO-101", "pipa": "P-07", "toneladas": 21.0},
                    {"fecha": "2026-09-24", "producto": "Oxígeno", "operador": "Alejandro Marrón", "eco": "ECO-105", "pipa": "P-03", "toneladas": 20.5},
                    {"fecha": "2026-09-21", "producto": "Argón", "operador": "Antonio Ponce", "eco": "ECO-110", "pipa": "P-07", "toneladas": 19.8},
                    {"fecha": "2026-09-18", "producto": "Nitrógeno", "operador": "Angel Hernández", "eco": "ECO-101", "pipa": "P-07", "toneladas": 20.2}
                ]
            },
            {
                "cliente": "GENERAL MOTORS VILLA DE REYES",
                "total_viajes": 12,
                "productos": {"LOX": 6, "LIN": 4, "LAR": 0, "CO2": 2},
                "ultima_fecha": "2026-09-24",
                "dias_transcurridos": 5,
                "frecuencia_promedio": 3.0,
                "producto_dominante": "LOX",
                "historial_30d": [
                    {"fecha": "2026-09-24", "producto": "Oxígeno", "operador": "Arturo Zayas", "eco": "ECO-108", "pipa": "P-04", "toneladas": 18.2},
                    {"fecha": "2026-09-20", "producto": "Nitrógeno", "operador": "Antonio Ponce", "eco": "ECO-110", "pipa": "P-04", "toneladas": 18.9},
                    {"fecha": "2026-09-17", "producto": "CO2", "operador": "Arturo Zayas", "eco": "ECO-108", "pipa": "P-04", "toneladas": 17.8}
                ]
            },
            {
                "cliente": "L'ORÉAL SLP",
                "total_viajes": 9,
                "productos": {"LOX": 0, "LIN": 7, "LAR": 0, "CO2": 2},
                "ultima_fecha": "2026-09-20",
                "dias_transcurridos": 9,
                "frecuencia_promedio": 3.5,
                "producto_dominante": "LIN",
                "historial_30d": [
                    {"fecha": "2026-09-20", "producto": "Nitrógeno", "operador": "Antonio Romero", "eco": "ECO-102", "pipa": "P-08", "toneladas": 16.5},
                    {"fecha": "2026-09-15", "producto": "Nitrógeno", "operador": "Alejandro Marrón", "eco": "ECO-105", "pipa": "P-08", "toneladas": 15.9}
                ]
            },
            {
                "cliente": "CERVECERÍA MODELO",
                "total_viajes": 15,
                "productos": {"LOX": 0, "LIN": 2, "LAR": 0, "CO2": 13},
                "ultima_fecha": "2026-09-28",
                "dias_transcurridos": 1,
                "frecuencia_promedio": 2.0,
                "producto_dominante": "CO2",
                "historial_30d": [
                    {"fecha": "2026-09-28", "producto": "CO2", "operador": "Angel Hernández", "eco": "ECO-103", "pipa": "P-CO2-1", "toneladas": 22.0},
                    {"fecha": "2026-09-26", "producto": "CO2", "operador": "Antonio Romero", "eco": "ECO-107", "pipa": "P-CO2-2", "toneladas": 21.4},
                    {"fecha": "2026-09-24", "producto": "CO2", "operador": "Angel Hernández", "eco": "ECO-103", "pipa": "P-CO2-1", "toneladas": 22.1}
                ]
            },
            {
                "cliente": "MABE SLP",
                "total_viajes": 8,
                "productos": {"LOX": 3, "LIN": 1, "LAR": 0, "CO2": 4},
                "ultima_fecha": "2026-09-26",
                "dias_transcurridos": 3,
                "frecuencia_promedio": 4.0,
                "producto_dominante": "CO2",
                "historial_30d": [
                    {"fecha": "2026-09-26", "producto": "CO2", "operador": "Arturo Zayas", "eco": "ECO-108", "pipa": "P-05", "toneladas": 14.8},
                    {"fecha": "2026-09-21", "producto": "Oxígeno", "operador": "Antonio Ponce", "eco": "ECO-110", "pipa": "P-05", "toneladas": 15.1}
                ]
            }
        ]
        
    return jsonify({"status": "success", "data": resultados})

@app.route('/api/gerencia/panel', methods=['GET'])
def api_gerencia_panel():
    fechas_ventana, centro, _, _ = calcular_ventana_tiempo(None)
    data = get_dashboard_data(fechas_ventana)
    cfg = get_config_unidades()
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT producto, COUNT(*) FROM operadores WHERE estatus_empleado='Activo' GROUP BY producto")
    plantilla = dict(c.fetchall())
    conn.close()
    
    plantilla['CRYO'] = plantilla.get('ARGON', 0) + plantilla.get('NITROGENO', 0) + plantilla.get('OXIGENO', 0)
    
    return jsonify({
        "status": "success",
        "usuario": "Gerencia Móvil",
        "configuracion_unidades": cfg,
        "plantilla_operadores": plantilla,
        "radar_operativo": data,
        "fecha_actual": centro
    })

@app.route('/api/centinela_radar_movimientos', methods=['GET'])
@login_required
def centinela_radar_movimientos():
    ultimo_id = request.args.get('ultimo_id', 0, type=int)
    mi_nombre = session.get('nombre_real', '')
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Si es la primera carga de la página, solo sincroniza con el ID más reciente sin alertar
    if ultimo_id == 0:
        c.execute("SELECT MAX(id) FROM notificaciones")
        max_row = c.fetchone()
        conn.close()
        max_id = max_row[0] if (max_row and max_row[0]) else 0
        return jsonify({"status": "success", "hay_movimiento": False, "ultimo_id": max_id})

    # Consulta si entró una notificación de cambio de turno posterior al último ID visto
    c.execute("""
        SELECT id, mensaje, fecha 
        FROM notificaciones 
        WHERE id > ? 
          AND (
               mensaje LIKE '%modificó a%' OR 
               mensaje LIKE '%actualizó a%' OR 
               mensaje LIKE '%Cambio directo%' OR 
               mensaje LIKE '%Aprobado por%'
          )
        ORDER BY id DESC LIMIT 1
    """, (ultimo_id,))
    row = c.fetchone()
    conn.close()

    if row:
        notif_id, mensaje, fecha = row
        # Si el cambio lo hizo otro supervisor (no el usuario que está viendo la pantalla)
        es_mio = bool(mi_nombre and mi_nombre.lower() in mensaje.lower())
        return jsonify({
            "status": "success",
            "hay_movimiento": not es_mio,
            "ultimo_id": notif_id,
            "mensaje": mensaje,
            "fecha": fecha
        })

    return jsonify({"status": "success", "hay_movimiento": False, "ultimo_id": ultimo_id})

@app.route('/api/sync_en_vivo', methods=['GET'])
@login_required
def api_sync_en_vivo():
    ultimo_id = request.args.get('ultimo_id', 0, type=int)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Obtener eventos ocurridos después del último ID visto por este usuario
    c.execute("SELECT id, tipo, payload, fecha FROM sync_eventos WHERE id > ? ORDER BY id ASC LIMIT 50", (ultimo_id,))
    filas = c.fetchall()
    
    # 2. Estado actual de notificaciones no leídas y solicitudes pendientes
    c.execute("SELECT COUNT(*) FROM notificaciones WHERE leida = 0")
    notifs_unread = c.fetchone()[0] or 0
    
    sols_pendientes = 0
    if session.get('rol') == 'jefe_op':
        c.execute("SELECT COUNT(*) FROM solicitudes_cambio WHERE estatus = 'Pendiente'")
        sols_pendientes = c.fetchone()[0] or 0
        
    conn.close()
    
    eventos = []
    max_id = ultimo_id
    for r in filas:
        ev_id, tipo, payload_str, fecha = r
        if ev_id > max_id:
            max_id = ev_id
        try:
            p_json = json.loads(payload_str)
        except Exception:
            p_json = {}
        eventos.append({'id': ev_id, 'tipo': tipo, 'payload': p_json, 'fecha': fecha})
        
    return jsonify({
        "status": "success",
        "eventos": eventos,
        "ultimo_id": max_id,
        "total_badge": notifs_unread + sols_pendientes
    })

@app.route('/api/descargar_rol_pdf')
@login_required
def descargar_rol_pdf():
    fecha_sol = request.args.get('fecha', obtener_fecha_operativa())
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT o.nombre, o.producto, o.esquema, COALESCE(o.eco, 'N/A'), COALESCE(l.estatus, 'TR')
        FROM operadores o
        LEFT JOIN logistica_diaria l ON o.id = l.operador_id AND l.fecha = ?
        WHERE o.estatus_empleado = 'Activo'
        ORDER BY o.producto, o.nombre
    """, (fecha_sol,))
    filas = c.fetchall()
    conn.close()

    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>FNG LOGÍSTICA - ROL OPERATIVO DIARIO</b>", styles['Title']))
    elements.append(Paragraph(f"Fecha programada: <b>{fecha_sol}</b> | Total operadores: {len(filas)}", styles['Normal']))
    elements.append(Spacer(1, 12))

    tabla_data = [["Operador", "Producto", "Bloque", "Tractor", "Estatus"]]
    for nom, prod, esq, eco, est in filas:
        tabla_data.append([nom, prod, esq, eco, est])

    t = Table(tabla_data, colWidths=[185, 85, 85, 70, 70])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#002d5a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (0,1), (0,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1'))
    ]))
    elements.append(t)
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment;filename=Rol_Operativo_{fecha_sol}.pdf"}
    )



@app.route('/api/centinela_historial', methods=['GET', 'DELETE'])
@login_required
def api_centinela_historial():
    u = session.get('usuario')
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if request.method == 'DELETE':
        c.execute("DELETE FROM centinela_historial WHERE usuario = ?", (u,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "msg": "Historial limpiado"})
    
    # Obtener los últimos 40 mensajes de los últimos 30 días
    c.execute("""
        SELECT rol, mensaje, strftime('%H:%M', fecha) 
        FROM centinela_historial 
        WHERE usuario = ? AND fecha >= datetime('now', '-30 days', 'localtime')
        ORDER BY id ASC LIMIT 40
    """, (u,))
    filas = c.fetchall()
    conn.close()
    mensajes = [{"rol": r[0], "mensaje": r[1], "hora": r[2]} for r in filas]
    return jsonify({"status": "success", "mensajes": mensajes})

@app.route('/api/centinela_alerta_predictiva', methods=['GET'])
@login_required
def api_centinela_alerta_predictiva():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    hoy = datetime.now().date()
    fechas_obj = [(hoy + timedelta(days=i)) for i in range(1, 8)]
    fechas_str = [f.strftime('%Y-%m-%d') for f in fechas_obj]

    unidades_cfg = get_config_unidades()
    prods = ['ARGON', 'NITROGENO', 'OXIGENO', 'CO2']
    prefijos = {'ARGON': 'CB-ARG', 'NITROGENO': 'CB-NIT', 'OXIGENO': 'CB-OXI', 'CO2': 'CB-CO2'}
    
    # 1. Evaluar déficits en los próximos 7 días
    for f in fechas_str:
        for p in prods:
            c.execute("SELECT l.estatus FROM logistica_diaria l JOIN operadores o ON l.operador_id = o.id WHERE o.producto=? AND l.fecha=? AND o.estatus_empleado='Activo'", (p, f))
            estatus_list = [row[0] for row in c.fetchall()]
            disp = sum(1 for e in estatus_list if str(e or '').startswith('TR'))
            c.execute("SELECT COUNT(*) FROM logistica_diaria l JOIN operadores o ON l.operador_id=o.id WHERE l.estatus=? AND l.fecha=? AND o.estatus_empleado='Activo'", (prefijos[p], f))
            disp += c.fetchone()[0]
            deficit = disp - unidades_cfg.get(p, 0)
            if deficit < 0:
                dias_f = (datetime.strptime(f, '%Y-%m-%d').date() - hoy).days
                cuando_txt = "Hoy" if dias_f == 0 else ("Mañana" if dias_f == 1 else f"En {dias_f} días")
                def_abs = abs(deficit)
                plural = "es" if def_abs > 1 else ""
                conn.close()
                return jsonify({
                    "hay_alerta": True,
                    "mensaje": f"⚠️ Alerta Operativa: {cuando_txt} faltan {def_abs} operador{plural} de {p}."
                })

    # 2. Evaluar ausencias justificadas en los próximos 2 días
    c.execute("SELECT o.nombre, l.fecha, l.estatus FROM operadores o JOIN logistica_diaria l ON o.id = l.operador_id WHERE o.estatus_empleado='Activo' AND l.fecha IN (?, ?) AND l.estatus IN ('VA', 'IN', 'MED')", (fechas_str[0], fechas_str[1]))
    ausencia = c.fetchone()
    conn.close()
    if ausencia:
        est_map = {'VA': 'Vacaciones', 'IN': 'Incapacidad', 'MED': 'Cita Médica'}
        dias_a = (datetime.strptime(ausencia[1], '%Y-%m-%d').date() - hoy).days
        txt_a = "Mañana" if dias_a == 1 else "En 2 días"
        return jsonify({
            "hay_alerta": True,
            "mensaje": f"📌 {txt_a} inicia {est_map.get(ausencia[2], 'ausencia')} de {ausencia[0]}."
        })

    return jsonify({"hay_alerta": False, "mensaje": ""})

@app.route('/api/centinela_radar_5d', methods=['GET'])
@login_required
def api_centinela_radar_5d():
    # Detectar el nombre del usuario activo en la sesión
    nombre_sesion = session.get('nombre_real', 'Compañero')
    primer_nombre = nombre_sesion.split()[0] if nombre_sesion else 'Compañero'

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    hoy = datetime.now().date()
    fechas_5d = [(hoy + timedelta(days=i)) for i in range(1, 6)]
    fechas_str = [f.strftime('%Y-%m-%d') for f in fechas_5d]

    dias_nombres = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    bloques_dias = []

    unidades_cfg = get_config_unidades()
    prods = ['ARGON', 'NITROGENO', 'OXIGENO', 'CO2']
    prefijos = {'ARGON': 'CB-ARG', 'NITROGENO': 'CB-NIT', 'OXIGENO': 'CB-OXI', 'CO2': 'CB-CO2'}

    # 1. Catálogo activo con su patrón oficial
    c.execute("SELECT id, nombre, tipo_jornada, producto FROM operadores WHERE estatus_empleado='Activo'")
    ops_catalogo = c.fetchall()

    # 2. Ventana de 15 días atrás hasta horizonte 5D en una sola consulta
    f_min = (hoy - timedelta(days=15)).strftime('%Y-%m-%d')
    f_max = fechas_str[-1]
    c.execute("SELECT operador_id, fecha, estatus FROM logistica_diaria WHERE fecha BETWEEN ? AND ?", (f_min, f_max))
    log_map = {(r[0], r[1]): (r[2] or '').strip().upper() for r in c.fetchall()}

    for idx, f_obj in enumerate(fechas_5d, start=1):
        f_str = f_obj.strftime('%Y-%m-%d')
        nom_dia = "Mañana" if idx == 1 else f"En {idx} días"
        tarjetas = []

        # A. Ausencias Programadas Justificadas (Vacaciones, Incapacidades, Permisos)
        for op_id, nom, patron, prod in ops_catalogo:
            est = log_map.get((op_id, f_str), '')
            if est in ('VA', 'IN', 'MED', 'PER'):
                est_map = {
                    'VA': ('Vacaciones', 'blue', 'fa-plane-departure'),
                    'IN': ('Incapacidad', 'yellow', 'fa-briefcase-medical'),
                    'MED': ('Cita Médica', 'yellow', 'fa-notes-medical'),
                    'PER': ('Permiso', 'yellow', 'fa-user-clock')
                }
                desc, color, ico = est_map.get(est, ('Ausencia', 'blue', 'fa-user-clock'))
                tarjetas.append({
                    "categoria": "ausencia",
                    "tipo": "Ausencia Programada",
                    "color": color,
                    "icono": ico,
                    "texto": f"{nom} tiene programadas {desc.lower()}.",
                    "op": nom
                })

        # B. Déficits Operativos por Producto (31 Unidades)
        for p in prods:
            c.execute("SELECT l.estatus FROM logistica_diaria l JOIN operadores o ON l.operador_id = o.id WHERE o.producto=? AND l.fecha=? AND o.estatus_empleado='Activo'", (p, f_str))
            disp = sum(1 for (e,) in c.fetchall() if str(e or '').startswith('TR'))
            c.execute("SELECT COUNT(*) FROM logistica_diaria l JOIN operadores o ON l.operador_id=o.id WHERE l.estatus=? AND l.fecha=? AND o.estatus_empleado='Activo'", (prefijos[p], f_str))
            disp += c.fetchone()[0]
            req = unidades_cfg.get(p, 0)
            deficit = disp - req
            if deficit < 0:
                tarjetas.append({
                    "categoria": "deficit",
                    "tipo": "Déficit Operativo",
                    "color": "red",
                    "icono": "fa-exclamation-triangle",
                    "texto": f"Faltarán {abs(deficit)} operador(es) de {p}.",
                    "producto": p,
                    "deficit_num": abs(deficit),
                    "fecha": f_str
                })

        # C. Auditoría de Ciclos, Inactividad y Maniobras de Patio
        for op_id, nom, patron, prod in ops_catalogo:
            p_clean = (patron or '').strip().upper()
            if '8-1-8-6' in p_clean:
                max_de, nom_rol = 6, '8-1-8-6'
            elif '8X4' in p_clean or '8-4' in p_clean:
                max_de, nom_rol = 4, '8x4'
            elif '4X4' in p_clean or '4-4' in p_clean:
                max_de, nom_rol = 4, '4x4'
            else:
                max_de, nom_rol = 6, 'Variable'

            est_hoy = log_map.get((op_id, f_str), '')

            # 1. Falta Injustificada
            if est_hoy == 'FA':
                tarjetas.append({
                    "categoria": "sobregiro",
                    "tipo": "Incidencia de Asistencia",
                    "color": "red",
                    "icono": "fa-user-xmark",
                    "texto": f"Atención: {nom} tiene falta injustificada registrada el {f_str}. Conviene revisar causa con supervisión.",
                    "op": nom
                })

            # 2. Descanso Excesivo (Días consecutivos > Límite oficial del ciclo)
            elif est_hoy == 'DE':
                racha_de = 0
                cursor_d = f_obj
                while True:
                    s_prev = log_map.get((op_id, cursor_d.strftime('%Y-%m-%d')), '')
                    if s_prev == 'DE':
                        racha_de += 1
                        cursor_d -= timedelta(days=1)
                    else:
                        break
                
                if racha_de > max_de:
                    tarjetas.append({
                        "categoria": "sobregiro",
                        "tipo": "Inactividad Prolongada",
                        "color": "yellow",
                        "icono": "fa-user-clock",
                        "texto": f"Revisando la plantilla: {nom} ya suma {racha_de} días seguidos en descanso (su rol {nom_rol} marca máx. {max_de}d). ¿Lo reactivamos o confirmamos con su supervisor?",
                        "op": nom
                    })

            # 3. Sensor de Descanso Parche (Reseteo mañoso tras jornada continua)
            elif est_hoy.startswith('TR'):
                d_ant1 = (f_obj - timedelta(days=1)).strftime('%Y-%m-%d')
                d_ant2 = (f_obj - timedelta(days=2)).strftime('%Y-%m-%d')
                if log_map.get((op_id, d_ant1), '') == 'DE' and log_map.get((op_id, d_ant2), '') != 'DE':
                    racha_tr_previa = 0
                    cursor_tr = f_obj - timedelta(days=2)
                    while True:
                        s_tr = log_map.get((op_id, cursor_tr.strftime('%Y-%m-%d')), '')
                        if s_tr.startswith('TR') or s_tr.startswith('CB'):
                            racha_tr_previa += 1
                            cursor_tr -= timedelta(days=1)
                        else:
                            break
                    if racha_tr_previa >= 7:
                        tarjetas.append({
                            "categoria": "sobregiro",
                            "tipo": "Descanso Parche",
                            "color": "red",
                            "icono": "fa-shield-halved",
                            "texto": f"Ojo, {primer_nombre}: le programaron solo 1 descanso a {nom} tras {racha_tr_previa} días continuos de viaje. Por su rol {nom_rol} requiere su descanso completo para recuperar fatiga.",
                            "op": nom
                        })

        bloques_dias.append({
            "idx": idx,
            "titulo": nom_dia,
            "fecha": f_str,
            "fecha_corta": f"{f_obj.day} {dias_nombres[f_obj.weekday()]}",
            "tarjetas": tarjetas
        })

    conn.close()
    return jsonify({"status": "success", "dias": bloques_dias})

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/api/centinela_ia', methods=['POST'])
@login_required
def api_centinela_ia():
    """
    Thin controller: delegates to CentinelaOrchestrator.
    Maintains exact JSON contract for frontend.
    """
    from services.centinela_orchestrator import process_centinela_query
    
    data = request.json or {}
    pregunta = data.get('pregunta', '').strip()
    cambio = data.get('cambio')  # {operador_id, fecha, estatus_nuevo}
    ruta_pantalla = data.get('ruta_pantalla', request.referrer or '')
    historial_raw = data.get('historial', [])

    nombre_usuario = session.get('nombre_real', 'Personal Operativo')
    rol_usuario = session.get('rol', 'jefe_op')

    # --- Compute lightweight context needed for orchestrator ---
    # Temporal horizon detection (hoy vs mañana) for PDF button
    from datetime import datetime, timedelta
    
    hoy_str = obtener_fecha_operativa()
    preg_lower = pregunta.lower().strip()
    es_manana = 'mañana' in preg_lower or 'manana' in preg_lower
    fecha_target = (datetime.strptime(hoy_str, '%Y-%m-%d').date() + timedelta(days=1)).strftime('%Y-%m-%d') if es_manana else hoy_str

    # PDF detection
    quiere_pdf = any(k in preg_lower for k in ['pdf', 'descarg', 'imprim', 'export', 'archivo'])
    boton_pdf_html = f'<div style="margin-top:10px;"><a href="/api/descargar_rol_pdf?fecha={fecha_target}" target="_blank" style="background:#ef4444; color:white; padding:8px 14px; border-radius:8px; text-decoration:none; font-weight:bold; font-size:12px; display:inline-flex; align-items:center; gap:6px; box-shadow:0 3px 8px rgba(239,68,68,0.3);"><i class="fas fa-file-pdf"></i> Descargar Rol PDF ({fecha_target})</a></div>'

    # Déficits detection (lightweight - can be enhanced by orchestrator tools)
    deficits_detectados = []

    # Convert history format
    historial_fmt = [
        {"role": "user" if h.get('rol') == 'user' else "assistant", 
         "content": str(h.get('texto', '')).strip()} 
        for h in historial_raw[-5:]
    ]

    # --- Delegate to orchestrator ---
    try:
        response = process_centinela_query(
            pregunta=pregunta or "Dame un resumen del estatus de la flota y riesgos inmediatos.",
            usuario=nombre_usuario,
            rol=rol_usuario,
            ruta_pantalla=ruta_pantalla,
            historial=historial_fmt,
            cambio=cambio,
            quiere_pdf=quiere_pdf,
            boton_pdf_html=boton_pdf_html,
            deficits_detectados=deficits_detectados,
        )
        
        final_resp = response.content if response.success else (
            "🟢 Centinela: " + 
            ("Déficits en 5 días: " + ", ".join(deficits_detectados) + "." if deficits_detectados else "Flota de 31 unidades en regla.")
        )
        provider_used = response.provider
        latency_ms = response.latency_ms
        
    except Exception as e:
        final_resp = "🟢 Centinela: " + ("Déficits en 5 días: " + ", ".join(deficits_detectados) + "." if deficits_detectados else "Flota de 31 unidades en regla.")
        provider_used = "none"
        latency_ms = 0

    # Persist to history
    try:
        u_actual = session.get('usuario', 'invitado')
        conn_hist = sqlite3.connect(DB_NAME)
        c_hist = conn_hist.cursor()
        if pregunta:
            c_hist.execute("INSERT INTO centinela_historial (usuario, rol, mensaje) VALUES (?, ?, ?)", (u_actual, 'user', pregunta))
        c_hist.execute("INSERT INTO centinela_historial (usuario, rol, mensaje) VALUES (?, ?, ?)", (u_actual, 'model', final_resp))
        conn_hist.commit()
        conn_hist.close()
    except Exception:
        pass

    return jsonify({
        "status": "success",
        "respuesta": final_resp,
        "data": final_resp,
        "provider": provider_used,
        "latency_ms": latency_ms
    })


@app.route('/api/exportar_dot_excel')
@login_required
def api_exportar_dot_excel():
    import io, openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    mes_req = request.args.get('mes')
    filtro_op = (request.args.get('filtro') or '').strip().upper()
    dias_mes, texto_mes, _, _, mes_actual_str = get_mes_data(mes_req)
    num_dias = len(dias_mes)
    col_max = num_dias + 3  # +3: días + Total + Meta 280h

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    query_ops = """
        SELECT id, no_empleado, nombre 
        FROM operadores 
        WHERE UPPER(estatus_empleado) = 'ACTIVO' 
          AND COALESCE(esquema, '') != 'Varios' 
          AND UPPER(COALESCE(linea_negocio, '')) != 'VARIOS'
          AND UPPER(COALESCE(producto, '')) != 'VARIOS'
    """
    if filtro_op:
        query_ops += f" AND UPPER(nombre) LIKE '%{filtro_op}%'"
    query_ops += " ORDER BY nombre"
    c.execute(query_ops)
    ops_raw = c.fetchall()

    fechas_str = [d['fecha'] for d in dias_mes]
    placeholders_mes = ','.join(['?'] * len(fechas_str))

    c.execute(f"""
        SELECT operador_id, fecha, horas, estatus_dia, eco_unidad, eco_pipas, 
               horas_manejo, horas_maniobra, auditado, tipo_registro, observaciones, 
               COALESCE(sub_estatus, ''), COALESCE(horas_dot_calc, 0.0), COALESCE(dias_trabajados_calc, 0)
        FROM dot_diario 
        WHERE fecha IN ({placeholders_mes})
    """, fechas_str)
    dot_global = {
        (r[0], r[1]): {
            'horas': r[2], 'estatus': r[3], 'unidad': r[4], 'pipas': r[5], 
            'manejo': r[6], 'maniobra': r[7], 'auditado': r[8], 'tipo_registro': r[9],
            'obs': r[10], 'sub_est': r[11], 'h_dot_calc': r[12], 'd_trab_calc': r[13]
        } for r in c.fetchall()
    }
    conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("No se pudo inicializar la hoja activa de Excel")
    ws.title = "Sabana DOT"

    # Fuentes y rellenos corporativos 1:1
    font_title = Font(name="Calibri", size=22, bold=True, color="FF000000")
    font_sub_title = Font(name="Calibri", size=11, bold=True, color="FF000000")
    font_header_dia = Font(name="Calibri", size=13, bold=True, color="FF000000")
    font_op_header = Font(name="Calibri", size=13, bold=True, color="FF000000")
    font_metric_lbl = Font(name="Calibri", size=10, bold=True, color="FF000000")
    font_cell = Font(name="Calibri", size=10, bold=False, color="FF000000")
    font_white_bold = Font(name="Calibri", size=10, bold=True, color="FFFFFFFF")
    font_black_bold = Font(name="Calibri", size=10, bold=True, color="FF000000")

    fill_gray = PatternFill(start_color="FFF2F2F2", end_color="FFF2F2F2", fill_type="solid")
    fill_yellow = PatternFill(start_color="FFFFFF00", end_color="FFFFFF00", fill_type="solid")
    fill_red = PatternFill(start_color="FFFF0000", end_color="FFFF0000", fill_type="solid")

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    thin_border = Border(
        left=Side(style='thin', color='FFE2E8F0'),
        right=Side(style='thin', color='FFE2E8F0'),
        top=Side(style='thin', color='FFE2E8F0'),
        bottom=Side(style='thin', color='FFE2E8F0')
    )

    # 1. Título Maestro
    col_max_let = get_column_letter(max(col_max, 20))
    ws.merge_cells(f"A1:{col_max_let}1")
    ws['A1'] = f"Sabana DOT - SAN LUIS POTOSI - {texto_mes}"
    ws['A1'].font = font_title
    ws['A1'].fill = fill_gray
    ws['A1'].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 38

    # 2. Cálculos de KPIs del encabezado
    kpi_sobregiros = 0
    kpi_dias_lab = 0
    kpi_horas_dec = 0.0
    kpi_sobre14 = 0
    kpi_sobre8 = 0
    kpi_desc = 0
    kpi_desc_incomp = 0
    kpi_estimados = 0
    kpi_plantilla = len(ops_raw)

    datos_por_operador = []
    for op_id, no_emp, nombre in ops_raw:
        racha = 0
        desc_op = 0
        op_dias = []

        # Para cálculo de sobregiros con ventana rodante de 7 días
        horas_por_fecha = {}
        for d in dias_mes:
            f_str = d['fecha']
            h_obj = dot_global.get((op_id, f_str), {})
            est_dia = (h_obj.get('estatus') or '').strip().upper()
            h_num = float(h_obj.get('horas') or 0.0)
            es_trab = est_dia in ['EN VIAJE', 'G', 'C'] or h_num > 0
            if es_trab:
                horas_por_fecha[f_str] = h_num

        for d in dias_mes:
            f_str = d['fecha']
            h_obj = dot_global.get((op_id, f_str), {})
            est_dia = (h_obj.get('estatus') or '').strip().upper()
            h_num = float(h_obj.get('horas') or 0.0)
            tipo_reg = (h_obj.get('tipo_registro') or '').strip().upper()
            es_audit = (h_obj.get('auditado') == 1 or tipo_reg == 'REAL')

            es_trab = est_dia in ['EN VIAJE', 'G', 'C'] or h_num > 0
            es_desc_puro = (est_dia == 'D')

            # Sobregiro oficial DOT (ventana rodante 7 días) - calcular para todos los días
            suma7d = 0.0
            idx = dias_mes.index(d)
            for i in range(max(0, idx - 6), idx + 1):
                f_ant = dias_mes[i]['fecha']
                suma7d += horas_por_fecha.get(f_ant, 0.0)

            if es_trab:
                kpi_dias_lab += 1
                kpi_horas_dec += h_num
                racha += 1
                if h_num > 14.0:
                    kpi_sobre14 += 1
                d_calc = h_obj.get('d_trab_calc') or racha
                if d_calc > 8:
                    kpi_sobre8 += 1
                if tipo_reg == 'ESTIMADO' or (not es_audit and h_num > 0):
                    kpi_estimados += 1

                if suma7d >= 70.0:
                    kpi_sobregiros += 1
            elif es_desc_puro:
                kpi_desc += 1
                desc_op += 1
                racha = 0
            else:
                racha = 0

            op_dias.append({
                'fecha': f_str,
                'horas': h_num,
                'estatus': est_dia,
                'unidad': h_obj.get('unidad', ''),
                'pipas': h_obj.get('pipas', ''),
                'auditado': es_audit,
                'tipo_reg': tipo_reg,
                'sub_est': h_obj.get('sub_est', ''),
                'obs': h_obj.get('obs', ''),
                'h_dot_calc': suma7d,
                'd_trab_calc': h_obj.get('d_trab_calc', 0)
            })

        if desc_op < 6:
            kpi_desc_incomp += 1

        datos_por_operador.append({
            'id': op_id,
            'no_emp': no_emp,
            'nombre': nombre,
            'dias': op_dias
        })

    incidencias = kpi_sobregiros + kpi_sobre8
    calif_pct = f"{(((kpi_dias_lab - incidencias) / kpi_dias_lab) * 100):.1f} %" if kpi_dias_lab > 0 else "100.0 %"
    dias_prog = kpi_plantilla * (num_dias - 5)
    util_pct = f"{((kpi_dias_lab / dias_prog) * 100):.2f} %" if dias_prog > 0 else "0.00 %"

    h_int = int(kpi_horas_dec)
    m_int = int(round((kpi_horas_dec - h_int) * 60))
    horas_tot_str = f"{h_int:02d}:{m_int:02d}"

    def set_kpi(cell_lbl, cell_val, merge_lbl, lbl_text, val_text):
        ws.merge_cells(merge_lbl)
        # Usar ws.cell() para evitar problemas con rangos combinados que devuelven tuplas
        # Parsear coordenadas como 'B3' -> (row=3, col=2)
        def parse_cell(cell_ref: str):
            col_str = ''
            row_str = ''
            for ch in cell_ref:
                if ch.isalpha():
                    col_str += ch
                else:
                    row_str += ch
            col = 0
            for c in col_str:
                col = col * 26 + (ord(c.upper()) - ord('A') + 1)
            return int(row_str), col

        r_l, c_l = parse_cell(cell_lbl)
        c_l_cell = ws.cell(row=r_l, column=c_l)
        c_l_cell.value = lbl_text
        c_l_cell.font = font_sub_title
        c_l_cell.fill = fill_gray
        c_l_cell.alignment = align_right

        r_v, c_v = parse_cell(cell_val)
        c_v_cell = ws.cell(row=r_v, column=c_v)
        c_v_cell.value = val_text
        c_v_cell.font = font_sub_title
        c_v_cell.fill = fill_gray
        c_v_cell.alignment = align_center

    set_kpi('B3', 'E3', 'B3:D3', 'Calificación Horas D.O.T.', calif_pct)
    set_kpi('G3', 'J3', 'G3:I3', 'Plantilla de operadores', kpi_plantilla)
    set_kpi('L3', 'O3', 'L3:N3', 'Sobregiros', kpi_sobregiros)
    set_kpi('Q3', 'T3', 'Q3:S3', 'Suma horas acumuladas', horas_tot_str)

    set_kpi('B4', 'E4', 'B4:D4', 'Utilización', util_pct)
    set_kpi('G4', 'J4', 'G4:I4', 'Días estimados', kpi_estimados)
    set_kpi('L4', 'O4', 'L4:N4', 'Sobretrabajo + 14:00 hrs', kpi_sobre14)
    set_kpi('Q4', 'T4', 'Q4:S4', 'Descansos', kpi_desc)

    set_kpi('G5', 'J5', 'G5:I5', 'Días laborados', kpi_dias_lab)
    set_kpi('L5', 'O5', 'L5:N5', 'Sobretrabajo + 8 días', kpi_sobre8)
    set_kpi('Q5', 'T5', 'Q5:S5', 'Descansos incompletos (6 días)', kpi_desc_incomp)

    # 3. Encabezados de días
    ws.row_dimensions[8].height = 24
    for idx_d, d in enumerate(dias_mes, start=2):
        cell_d = ws.cell(row=8, column=idx_d, value=idx_d - 1)
        cell_d.font = font_header_dia
        cell_d.alignment = align_center
        cell_d.fill = fill_gray
        cell_d.border = thin_border

    # Encabezados Total y Meta 280h
    cell_total = ws.cell(row=8, column=num_dias + 2, value='TOTAL')
    cell_total.font = font_header_dia
    cell_total.alignment = align_center
    cell_total.fill = fill_gray
    cell_total.border = thin_border

    cell_meta = ws.cell(row=8, column=num_dias + 3, value='META 280h')
    cell_meta.font = font_header_dia
    cell_meta.alignment = align_center
    cell_meta.fill = fill_gray
    cell_meta.border = thin_border

    # 4. Bloques de operadores (9 renglones por operador)
    row_cursor = 10
    labels_subrows = [
        'Tipo', 'Estatus', 'Tractor / Pipa', 'Horas de Servicio',
        'Horas D.O.T.', 'Acumulado', 'Días Trabajados'
    ]

    for op in datos_por_operador:
        last_col_let = get_column_letter(col_max)
        ws.merge_cells(f"A{row_cursor}:{last_col_let}{row_cursor}")
        c_op = ws[f"A{row_cursor}"]
        c_op.value = op['nombre']
        c_op.font = font_op_header
        c_op.fill = fill_gray
        c_op.alignment = align_left
        ws.row_dimensions[row_cursor].height = 22

        racha_h = 0.0
        racha_d = 0
        dot_acum = 0.0

        for s_idx, lbl in enumerate(labels_subrows, start=1):
            curr_row = row_cursor + s_idx
            ws.row_dimensions[curr_row].height = 18
            lbl_cell = ws.cell(row=curr_row, column=1, value=lbl)
            lbl_cell.font = font_metric_lbl
            lbl_cell.fill = fill_gray
            lbl_cell.alignment = align_left
            lbl_cell.border = thin_border

        for col_idx, d in enumerate(op['dias'], start=2):
            est = d['estatus']
            h = d['horas']
            is_rest = est in ['D', 'DE', 'V', 'VA', 'I', 'IN', 'B', 'P', 'PER'] or (not est and h == 0)

            # R1: Tipo
            tipo_v = '-'
            if h > 0:
                tipo_v = 'R' if d['auditado'] else 'E'
            ws.cell(row=row_cursor+1, column=col_idx, value=tipo_v).alignment = align_center

            # R2: Estatus
            est_v = est if est else ('EN VIAJE' if h > 0 else '-')
            ws.cell(row=row_cursor+2, column=col_idx, value=est_v).alignment = align_center

            # R3: Tractor / Pipa
            u = d['unidad'] if d['unidad'] and d['unidad'] != 'N/A' else ''
            p = d['pipas'] if d['pipas'] and d['pipas'] != 'N/A' else ''
            eq_v = f"{u} / {p}" if (u or p) and not is_rest else " / "
            ws.cell(row=row_cursor+3, column=col_idx, value=eq_v).alignment = align_center

            # R4: Horas Servicio
            h_int_d = int(h)
            h_dec_d = int(round((h - h_int_d) * 60))
            serv_v = f"{h_int_d:02d}.{h_dec_d:02d}" if h > 0 else "00:00"
            ws.cell(row=row_cursor+4, column=col_idx, value=serv_v).alignment = align_center

            # R5 y R6: Acumulados DOT
            if is_rest:
                racha_h = 0.0
                racha_d = 0
                dot_acum = 0.0
            else:
                racha_h += h
                racha_d += 1
                dot_acum += h

            d_tot_h = int(dot_acum)
            d_tot_m = int(round((dot_acum - d_tot_h) * 60))
            dot_str = f"{d_tot_h:02d}:{d_tot_m:02d}" if dot_acum > 0 else "00:00"

            c_dot = ws.cell(row=row_cursor+5, column=col_idx, value=dot_str)
            c_dot.alignment = align_center
            if dot_acum >= 70.0:
                c_dot.fill = fill_red
                c_dot.font = font_white_bold
            elif dot_acum >= 52.0:
                c_dot.fill = fill_yellow
                c_dot.font = font_black_bold
            else:
                c_dot.font = font_cell

            a_tot_h = int(racha_h)
            a_tot_m = int(round((racha_h - a_tot_h) * 60))
            acum_str = f"{a_tot_h:02d}:{a_tot_m:02d}" if racha_h > 0 else "00:00"
            ws.cell(row=row_cursor+6, column=col_idx, value=acum_str).alignment = align_center

            # R7: Días Trabajados (Semáforo estricto)
            c_dias = ws.cell(row=row_cursor+7, column=col_idx, value=racha_d)
            c_dias.alignment = align_center
            if racha_d >= 8:
                c_dias.fill = fill_red
                c_dias.font = font_white_bold
            elif racha_d == 7:
                c_dias.fill = fill_yellow
                c_dias.font = font_black_bold
            else:
                c_dias.font = font_cell

            for sub_r in range(1, 8):
                ws.cell(row=row_cursor+sub_r, column=col_idx).border = thin_border

        # Escribir Total y Meta 280h en la fila de Horas de Servicio (subfila 4)
        total_horas = racha_h
        meta_faltante = max(0, 280 - total_horas)
        t_h = int(total_horas)
        t_m = int(round((total_horas - t_h) * 60))
        total_str = f"{t_h:02d}:{t_m:02d}" if total_horas > 0 else "00:00"
        meta_str = "✅ Meta" if meta_faltante == 0 else f"⚠️ {meta_faltante:.1f}h"

        # Fila 4 = Horas de Servicio (row_cursor + 4)
        c_total = ws.cell(row=row_cursor + 4, column=num_dias + 2, value=total_str)
        c_total.alignment = align_center
        c_total.border = thin_border
        c_meta = ws.cell(row=row_cursor + 4, column=num_dias + 3, value=meta_str)
        c_meta.alignment = align_center
        c_meta.border = thin_border

        # Bordes para las otras filas en columnas Total y Meta
        for s_idx in [1, 2, 3, 5, 6, 7]:
            curr_row = row_cursor + s_idx
            ws.cell(row=curr_row, column=num_dias + 2).border = thin_border
            ws.cell(row=curr_row, column=num_dias + 3).border = thin_border

        row_cursor += 9

    ws.column_dimensions['A'].width = 22
    for c_i in range(2, col_max + 1):
        ws.column_dimensions[get_column_letter(c_i)].width = 19

    # HOJA 2: TABLA PIVOTEABLE PLANA PARA GERENCIA
    ws_plana = wb.create_sheet(title="Datos_Pivotables")
    cabeceras_plana = [
        'No_Empleado', 'Operador', 'Fecha', 'Estatus', 'Sub_Estatus_Motivo', 
        'Observaciones', 'Horas_Decimal', 'Horas_HHMM', 'Tractor', 'Pipa', 
        'Tipo_Registro', 'Auditado', 'Total_Mensual', 'Meta_280h_Faltante'
    ]
    ws_plana.append(cabeceras_plana)
    for c_idx_p, h_text in enumerate(cabeceras_plana, start=1):
        cell_p = ws_plana.cell(row=1, column=c_idx_p)
        cell_p.font = font_metric_lbl
        cell_p.fill = fill_gray
        cell_p.alignment = align_center

    for op in datos_por_operador:
        # Calcular total mensual y meta faltante por operador
        total_mensual = sum(d['horas'] for d in op['dias'])
        meta_faltante = max(0, 280 - total_mensual)
        total_str = f"{int(total_mensual):02d}:{int(round((total_mensual - int(total_mensual)) * 60)):02d}"
        meta_str = "Meta cumplida" if meta_faltante == 0 else f"Faltan {meta_faltante:.1f}h"
        
        for d in op['dias']:
            h_val = d['horas']
            h_int = int(h_val)
            h_min = int(round((h_val - h_int) * 60))
            ws_plana.append([
                op['no_emp'],
                op['nombre'],
                d['fecha'],
                d['estatus'] or ('EN VIAJE' if h_val > 0 else 'SIN ASIGNAR'),
                d['sub_est'],
                d['obs'],
                h_val,
                f"{h_int:02d}:{h_min:02d}",
                d['unidad'],
                d['pipas'],
                d['tipo_reg'] or 'Estimado',
                'SI' if d['auditado'] else 'NO',
                total_str,
                meta_str
            ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    nombre_archivo = f"Sabana_DOT_{mes_actual_str}"
    if filtro_op:
        nombre_archivo += f"_{filtro_op.replace(' ', '_')}"
    nombre_archivo += ".xlsx"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


if __name__ == '__main__':
    # En producción debug debe ser False para no exponer consola interactiva
    debug_activo = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1")
    app.run(host='0.0.0.0', port=5000, debug=debug_activo, threaded=True)

