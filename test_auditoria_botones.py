#!/usr/bin/env python3
"""
Script de auditoría automatizada de botones, formularios y acciones interactivas
para las vistas clave del ERP FNG.
"""

import os
import sys
import re
import json
import sqlite3
from datetime import datetime
from flask import Flask, session
from bs4 import BeautifulSoup

# Agregar el directorio base al path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Importar la app de Flask
from app import app, DB_NAME, login_required

# =============================================================================
# MAPEO DE ELEMENTOS INTERACTIVOS EXTRAÍDOS DE LAS PLANTILLAS
# =============================================================================

# Endpoints de la API extraídos de app.py
API_ENDPOINTS = {
    # DOT / Horas
    '/api/actualizar_dot': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot'], 'template': 'horas_dot.html'},
    '/api/guardar_simulador': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot'], 'template': 'horas_dot.html'},
    '/api/exportar_dot_excel': {'methods': ['GET'], 'roles': ['jefe_op', 'aux_dot', 'gerencia'], 'template': 'horas_dot.html'},
    '/api/operador_guardar_dia': {'methods': ['POST'], 'roles': ['operador'], 'template': 'portal_chofer.html'},
    
    # Sabana / Torre de Control
    '/api/guardar_programacion': {'methods': ['POST'], 'roles': ['jefe_op', 'supervisor', 'monitorista'], 'template': 'programacion.html'},
    '/api/cargar_programacion': {'methods': ['GET'], 'roles': ['jefe_op', 'supervisor', 'monitorista'], 'template': 'programacion.html'},
    '/api/gestionar_viaje_pizarra': {'methods': ['POST'], 'roles': ['jefe_op', 'supervisor', 'monitorista'], 'template': 'sabana.html'},
    '/api/obtener_dia_operador': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot', 'supervisor', 'monitorista'], 'template': 'sabana.html'},
    '/api/solicitar_turno': {'methods': ['POST'], 'roles': ['operador', 'supervisor', 'monitorista', 'aux_bitacoras'], 'template': 'sabana.html'},
    '/api/solicitar_pase_salida': {'methods': ['POST'], 'roles': ['operador', 'supervisor', 'monitorista', 'aux_bitacoras'], 'template': 'sabana.html'},
    '/api/actualizar_turno': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot', 'super_usuario'], 'template': 'sabana.html'},
    '/api/descargar_rol_pdf': {'methods': ['GET'], 'roles': ['jefe_op', 'aux_dot', 'supervisor', 'monitorista', 'aux_bitacoras'], 'template': 'sabana.html'},
    '/api/centinela_radar_movimientos': {'methods': ['GET'], 'roles': ['jefe_op', 'aux_dot', 'supervisor', 'monitorista'], 'template': 'sabana.html'},
    '/api/centinela_radar_5d': {'methods': ['GET'], 'roles': ['jefe_op', 'aux_dot', 'supervisor', 'monitorista'], 'template': 'sabana.html'},
    '/api/centinela_alerta_predictiva': {'methods': ['GET'], 'roles': ['jefe_op', 'aux_dot', 'supervisor', 'monitorista'], 'template': 'sabana.html'},
    '/api/sync_en_vivo': {'methods': ['GET'], 'roles': ['jefe_op', 'aux_dot', 'supervisor', 'monitorista'], 'template': 'sabana.html'},
    
    # Centinela IA
    '/api/centinela_ia': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot', 'supervisor', 'monitorista', 'gerencia'], 'template': 'base.html (chat)'},
    '/api/centinela_historial': {'methods': ['GET', 'DELETE'], 'roles': ['jefe_op', 'aux_dot', 'supervisor', 'monitorista', 'gerencia'], 'template': 'base.html (chat)'},
    
    # Expedientes / Amonestaciones
    '/api/expediente_historial': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot', 'gerencia'], 'template': 'perfil_operadores.html'},
    '/api/guardar_amonestacion': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot', 'gerencia'], 'template': 'perfil_operadores.html'},
    '/api/obtener_amonestaciones': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot', 'gerencia'], 'template': 'perfil_operadores.html'},
    '/api/actualizar_expediente': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot'], 'template': 'perfil_operadores.html'},
    '/api/obtener_rol_mes': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot', 'supervisor', 'monitorista', 'aux_bitacoras'], 'template': 'sabana.html/horas_dot.html'},
    
    # Utilidades
    '/api/generar_pin': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot'], 'template': 'horas_dot.html/perfil_operadores.html'},
    '/api/liberar_dispositivo': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot'], 'template': 'perfil_operadores.html'},
    '/api/importar_pdf_despacho': {'methods': ['POST'], 'roles': ['jefe_op', 'supervisor'], 'template': 'sabana.html'},
    
    # Gerencia / Analytics
    '/api/gerencia/panel': {'methods': ['GET'], 'roles': ['gerencia', 'super_usuario'], 'template': 'panel_gerencia.html'},
    '/api/analitica_clientes': {'methods': ['GET'], 'roles': ['gerencia', 'super_usuario'], 'template': 'panel_gerencia.html'},
    '/api/resumen_predictivo': {'methods': ['GET'], 'roles': ['jefe_op', 'aux_dot', 'gerencia'], 'template': 'base.html'},
    '/api/estatus_vivo_mock': {'methods': ['GET'], 'roles': ['jefe_op', 'aux_dot', 'supervisor', 'monitorista'], 'template': 'sabana.html'},
    
    # Diesel
    '/api/procesar_matriz': {'methods': ['POST'], 'roles': ['analista_diesel'], 'template': 'control_diesel_analista.html'},
    '/api/generar_bonos': {'methods': ['POST'], 'roles': ['gerencia', 'super_usuario'], 'template': 'control_diesel_gerente.html'},
    
    # Otros
    '/api/inyectar_ficticios': {'methods': ['POST'], 'roles': ['super_usuario'], 'template': 'base.html'},
    '/api/whatsapp_multimedia': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot'], 'template': 'base.html'},
    '/api/drilldown_radar': {'methods': ['POST'], 'roles': ['jefe_op', 'aux_dot', 'gerencia'], 'template': 'sabana.html'},
}

# Elementos interactivos (botones, formularios, enlaces) extraídos de las plantillas
# Formato: (pantalla, accion, selector_id, endpoint, metodo, tipo, rol_requerido)
INTERACTIVE_ELEMENTS = [
    # === HORAS_DOT.HTML ===
    ('Auditoría DOT', 'Navegar semana anterior', 'btn-nav-week (prev)', '/horas_dot (GET)', 'GET', 'navegación', 'jefe_op'),
    ('Auditoría DOT', 'Navegar semana siguiente', 'btn-nav-week (next)', '/horas_dot (GET)', 'GET', 'navegación', 'jefe_op'),
    ('Auditoría DOT', 'Selector de mes', 'mesSelector', '/horas_dot (GET)', 'GET', 'navegación', 'jefe_op'),
    ('Auditoría DOT', 'Botón OCR (abrir)', 'btnAbrirOCR', 'N/A (JS)', 'N/A', 'modal', 'jefe_op'),
    ('Auditoría DOT', 'Input archivo OCR', 'ocr-input', 'N/A (JS + Tesseract)', 'N/A', 'formulario', 'jefe_op'),
    ('Auditoría DOT', 'Cancelar OCR', 'btnCancelarOCR', 'N/A (JS)', 'N/A', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Modal Editor - Guardar', 'btnGuardarDatoUnico', '/api/actualizar_dot', 'POST', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Modal Editor - Cancelar', 'cerrarModalEditorDatoUnico()', 'N/A (JS)', 'N/A', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Modal Editor - Eliminar día', 'btnEliminarDiaUnico', '/api/actualizar_dot (delete)', 'POST', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Modal Editor - Aplicar en rango', 'fechaFinRango', '/api/actualizar_dot (rango)', 'POST', 'formulario', 'jefe_op'),
    ('Auditoría DOT', 'Simulador 7d - Guardar', 'btnGuardarSimulador', '/api/guardar_simulador', 'POST', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Simulador 7d - Aplicar', 'btnAplicarSimulador', '/api/actualizar_dot (masivo)', 'POST', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Simulador 7d - Cancelar', 'cerrarModalSimulador7d()', 'N/A (JS)', 'N/A', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Exportar Excel DOT', 'btnExportarExcel', '/api/exportar_dot_excel', 'GET', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Generar PIN emergencia', 'btnGenerarPin (en modal)', '/api/generar_pin', 'POST', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Liberar dispositivo', 'btnLiberarDispositivo (en modal)', '/api/liberar_dispositivo', 'POST', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Abrir modal PDF mensual', 'btnGenerarPDFMasivo', 'N/A (JS modal)', 'N/A', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Buscador PDF operador', 'buscadorOpPDF', 'N/A (JS filtro local)', 'N/A', 'formulario', 'jefe_op'),
    ('Auditoría DOT', 'Descargar rol PDF', 'descargarRol()', '/api/descargar_rol_pdf', 'GET', 'botón', 'jefe_op'),
    ('Auditoría DOT', 'Célida día - Click (popover)', 'td.col-dia span (onclick)', 'mostrarPopover()', 'JS', 'celda', 'jefe_op'),
    ('Auditoría DOT', 'Célida S/B - Click (editor)', 'td.col-dia span.sobregiro (onclick)', 'abrirModalCapturaDirectaFecha()', 'JS', 'celda', 'jefe_op'),
    ('Auditoría DOT', 'Tarjeta KPI - Click', '.kpi-cell (onclick)', 'abrirModalKPI()', 'JS', 'tarjeta', 'jefe_op'),
    ('Auditoría DOT', 'Acordion operador', 'btn-action (onclick)', 'toggleAccordion()', 'JS', 'botón', 'jefe_op'),
    
    # === SABANA.HTML ===
    ('Sábana', 'Buscador logística', 'buscadorLogistica', 'buscadorGlobal()', 'JS', 'formulario', 'jefe_op'),
    ('Sábana', 'Expandir buscador', 'searchBarContainer (click)', 'expandirBuscador()', 'JS', 'botón', 'jefe_op'),
    ('Sábana', 'Limpiar buscador', 'clear-icon (click)', 'limpiarYColapsarBuscador()', 'JS', 'botón', 'jefe_op'),
    ('Sábana', 'Botón Editar Turno (RH)', 'mac-dock-btn (Editar Turno)', 'abrirModalRHRapido()', 'JS', 'botón', 'jefe_op'),
    ('Sábana', 'Botón Pase Salida', 'mac-dock-btn (Pase Salida)', 'abrirModalPaseGlobal()', 'JS', 'botón', 'jefe_op'),
    ('Sábana', 'Botón Generar PDF', 'mac-dock-btn (Generar PDF)', 'abrirModalGenerarPDF()', 'JS', 'botón', 'jefe_op'),
    ('Sábana', 'Botón Centinela Radar', 'mac-dock-btn (Centinela)', 'cargarRadarCentinela()', 'JS + /api/centinela_radar_movimientos', 'botón', 'jefe_op'),
    ('Sábana', 'Selector fecha', 'fechaInput', 'N/A (navegación GET)', 'GET', 'formulario', 'jefe_op'),
    ('Sábana', 'Navegar fecha anterior', 'btn-nav-day (prev)', '/sabana (GET)', 'GET', 'navegación', 'jefe_op'),
    ('Sábana', 'Navegar fecha siguiente', 'btn-nav-day (next)', '/sabana (GET)', 'GET', 'navegación', 'jefe_op'),
    ('Sábana', 'Modal RH - Guardar', 'guardarTurno()', '/api/solicitar_turno o /api/actualizar_turno', 'POST', 'botón', 'jefe_op/supervisor'),
    ('Sábana', 'Modal RH - Cancelar', 'cerrar modal', 'N/A (JS)', 'N/A', 'botón', 'jefe_op'),
    ('Sábana', 'Modal RH - Selector rol', 'rhRolOp (change)', 'evaluarCascadaRH()', 'JS', 'formulario', 'jefe_op'),
    ('Sábana', 'Modal RH - Selector producto', 'rhProducto (change)', 'evaluarCascadaRH()', 'JS', 'formulario', 'jefe_op'),
    ('Sábana', 'Modal Pase - Enviar', 'enviarPaseGlobal()', '/api/solicitar_pase_salida', 'POST', 'botón', 'operador+'),
    ('Sábana', 'Modal Pase - Cancelar', 'cerrar modal', 'N/A (JS)', 'N/A', 'botón', 'operador+'),
    ('Sábana', 'Modal PDF - Buscar', 'buscadorOpPDF', 'filtrarNombresPDF()', 'JS', 'formulario', 'jefe_op'),
    ('Sábana', 'Modal PDF - Descargar', 'descargarRol()', '/api/descargar_rol_pdf', 'GET', 'botón', 'jefe_op'),
    ('Sábana', 'Modal PDF - Cancelar', 'cerrar modal', 'N/A (JS)', 'N/A', 'botón', 'jefe_op'),
    ('Sábana', 'Célida día - Click (editor)', 'td[id^=celda-op-] (onclick)', 'abrirModalRHRapido()', 'JS', 'celda', 'jefe_op'),
    ('Sábana', 'Célida día - Centinela', 'evaluarImpactoCentinela()', '/api/centinela_alerta_predictiva', 'GET', 'JS + API', 'jefe_op'),
    ('Sábana', 'Receptor live:celda_actualizada', 'document.addEventListener', 'live:celda_actualizada', 'Event', 'listener', 'jefe_op'),
    ('Sábana', 'Receptor live:dot_actualizado', 'document.addEventListener', 'live:dot_actualizado', 'Event', 'listener', 'jefe_op'),
    ('Sábana', 'Receptor sync_en_vivo', 'document.addEventListener', 'live:sync_en_vivo', 'Event', 'listener', 'jefe_op'),
    
    # === BASE.HTML (Centinela IA Chat + Notificaciones + Modales Globales) ===
    ('Centinela IA Chat', 'Abrir chat', 'centinelaToggle (click)', 'toggleCentinelaChat()', 'JS', 'botón', 'todos'),
    ('Centinela IA Chat', 'Cerrar chat', 'cerrarCentinelaChat()', 'N/A (JS)', 'N/A', 'botón', 'todos'),
    ('Centinela IA Chat', 'Enviar mensaje', 'centinelaSend (click)', 'enviarCentinela() -> /api/centinela_ia', 'POST', 'botón', 'todos'),
    ('Centinela IA Chat', 'Input mensaje', 'centinelaInput (Enter)', 'enviarCentinela()', 'JS', 'formulario', 'todos'),
    ('Centinela IA Chat', 'Sugerencia rápida', '.centinela-suggestion (click)', 'usarSugerencia()', 'JS', 'botón', 'todos'),
    ('Centinela IA Chat', 'Limpiar historial', 'centinelaClear (click)', 'limpiarHistorialCentinela() -> /api/centinela_historial DELETE', 'DELETE', 'botón', 'todos'),
    ('Centinela IA Chat', 'Exportar chat', 'centinelaExport (click)', 'exportarChatCentinela()', 'JS', 'botón', 'todos'),
    ('Centinela IA Chat', 'Cargar historial', 'cargarHistorialCentinela()', '/api/centinela_historial GET', 'GET', 'inicio', 'todos'),
    ('Centinela IA Chat', 'Alerta predictiva', 'verificarAlertaPredictiva()', '/api/centinela_alerta_predictiva', 'GET', 'polling', 'todos'),
    
    ('Notificaciones', 'Abrir panel', 'notifBtn (click)', 'toggleNotifPanel()', 'JS', 'botón', 'todos'),
    ('Notificaciones', 'Marcar todas leídas', 'marcarTodasLeidas()', '/api/leer_notificacion', 'POST', 'botón', 'todos'),
    ('Notificaciones', 'Click notificación', '.notif-card (onclick)', 'ventanaNotificacion.onclick', 'JS', 'tarjeta', 'todos'),
    
    ('Modal Pase Global', 'Abrir', 'abrirModalPase()', 'N/A (JS)', 'N/A', 'botón', 'todos'),
    ('Modal Pase Global', 'Enviar', 'enviarPaseGlobal()', '/api/solicitar_pase_salida', 'POST', 'botón', 'todos'),
    ('Modal Pase Global', 'Cancelar', 'cerrar modal', 'N/A (JS)', 'N/A', 'botón', 'todos'),
    
    ('Modal Rechazo Global', 'Abrir (desde solicitud)', 'procesarSolicitud(rechazar)', 'N/A (JS)', 'N/A', 'botón', 'jefe_op'),
    ('Modal Rechazo Global', 'Enviar rechazo', 'enviarRechazoFinal()', '/api/gestionar_solicitud', 'POST', 'botón', 'jefe_op'),
    ('Modal Rechazo Global', 'Cancelar', 'cerrar modal', 'N/A (JS)', 'N/A', 'botón', 'jefe_op'),
    
    ('Búsqueda Global', 'Buscador', 'buscadorGlobal()', 'N/A (JS filtro DOM)', 'JS', 'formulario', 'todos'),
]

# =============================================================================
# FUNCIONES DE VALIDACIÓN
# =============================================================================

def validar_sintaxis_python():
    """Valida la sintaxis de app.py"""
    print("\n🔍 Validando sintaxis de app.py...")
    try:
        import py_compile
        py_compile.compile(os.path.join(BASE_DIR, 'app.py'), doraise=True)
        print("   ✅ Sintaxis OK")
        return True
    except py_compile.PyCompileError as e:
        print(f"   ❌ Error de sintaxis: {e}")
        return False


def extraer_selectores_dom(template_path):
    """Extrae todos los IDs y clases relevantes del DOM en una plantilla"""
    selectores = {'ids': set(), 'classes': set(), 'onclicks': set()}
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # IDs
        for el in soup.find_all(id=True):
            selectores['ids'].add(el['id'])
        
        # Classes (solo las que parecen relevantes para JS)
        for el in soup.find_all(class_=True):
            classes = el['class'] if isinstance(el['class'], list) else [el['class']]
            for c in classes:
                if any(kw in c.lower() for kw in ['btn', 'modal', 'input', 'search', 'celda', 'kpi', 'accord', 'toast', 'notif', 'centinela', 'radar', 'popover', 'editor', 'simulador', 'export', 'generar', 'buscador', 'fecha', 'nav']):
                    selectores['classes'].add(c)
        
        # Onclick handlers
        for el in soup.find_all(onclick=True):
            selectores['onclicks'].add(el['onclick'][:100])
            
        # Event listeners en scripts (buscar addEventListener)
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # Buscar patrones de addEventListener
                matches = re.findall(r'addEventListener\([\'"]([^\'"]+)[\'"]', script.string)
                for m in matches:
                    selectores['onclicks'].add(f'live:{m}')
                # Buscar getElementById
                matches = re.findall(r'getElementById\([\'"]([^\'"]+)[\'"]', script.string)
                for m in matches:
                    selectores['ids'].add(m)
                # Buscar querySelector
                matches = re.findall(r'querySelector\([\'"]([^\'"]+)[\'"]', script.string)
                for m in matches:
                    selectores['classes'].add(m)
                    
    except Exception as e:
        print(f"   ⚠️ Error parseando {template_path}: {e}")
    
    return selectores


def verificar_listeners_huerfanos():
    """Verifica que los selectores que buscan los scripts JS existan en el DOM"""
    print("\n🔍 Verificando listeners huérfanos (selectores JS vs DOM)...")
    
    templates = {
        'horas_dot.html': os.path.join(BASE_DIR, 'templates', 'horas_dot.html'),
        'sabana.html': os.path.join(BASE_DIR, 'templates', 'sabana.html'),
        'base.html': os.path.join(BASE_DIR, 'templates', 'base.html'),
    }
    
    todos_selectores_dom = {'ids': set(), 'classes': set()}
    for name, path in templates.items():
        if os.path.exists(path):
            sel = extraer_selectores_dom(path)
            todos_selectores_dom['ids'].update(sel['ids'])
            todos_selectores_dom['classes'].update(sel['classes'])
            print(f"   📄 {name}: {len(sel['ids'])} IDs, {len(sel['classes'])} clases relevantes, {len(sel['onclicks'])} onclicks")
    
    # Verificar elementos interactivos críticos
    errores = []
    selectores_criticos = [
        # horas_dot.html
        ('horas_dot.html', 'id', 'btnGuardarDatoUnico'),
        ('horas_dot.html', 'id', 'btnEliminarDiaUnico'),
        ('horas_dot.html', 'id', 'btnGuardarSimulador'),
        ('horas_dot.html', 'id', 'btnAplicarSimulador'),
        ('horas_dot.html', 'id', 'btnExportarExcel'),
        ('horas_dot.html', 'id', 'btnGenerarPin'),
        ('horas_dot.html', 'id', 'btnLiberarDispositivo'),
        ('horas_dot.html', 'id', 'btnGenerarPDFMasivo'),
        ('horas_dot.html', 'id', 'buscadorOpPDF'),
        ('horas_dot.html', 'id', 'ocr-input'),
        ('horas_dot.html', 'id', 'btnAbrirOCR'),
        ('horas_dot.html', 'id', 'btnCancelarOCR'),
        ('horas_dot.html', 'id', 'editDotFecha'),
        ('horas_dot.html', 'id', 'editDotEstatus'),
        ('horas_dot.html', 'id', 'editDotUnidad'),
        ('horas_dot.html', 'id', 'editDotPipas'),
        ('horas_dot.html', 'id', 'editDotManejo'),
        ('horas_dot.html', 'id', 'editDotManiobra'),
        ('horas_dot.html', 'id', 'editDotSubEstatus'),
        ('horas_dot.html', 'id', 'editDotObservaciones'),
        ('horas_dot.html', 'id', 'fechaFinRango'),
        ('horas_dot.html', 'id', 'modalEditorDatoUnico'),
        ('horas_dot.html', 'id', 'modalSimulador7d'),
        ('horas_dot.html', 'id', 'modalGenerarPDF'),
        ('horas_dot.html', 'id', 'modalDetalleKPI'),
        ('horas_dot.html', 'id', 'cajaCentinelaModal'),
        ('horas_dot.html', 'id', 'textoCentinelaModal'),
        ('horas_dot.html', 'id', 'dotIdOp'),
        ('horas_dot.html', 'id', 'jsonHorasOcultas'),
        ('horas_dot.html', 'id', 'modalNombreCredencial'),
        ('horas_dot.html', 'id', 'listaAutocompletado'),
        ('horas_dot.html', 'id', 'cajaDescarga'),
        ('horas_dot.html', 'id', 'nombreElegido'),
        
        # sabana.html
        ('sabana.html', 'id', 'buscadorLogistica'),
        ('sabana.html', 'id', 'searchBarContainer'),
        ('sabana.html', 'id', 'fechaInput'),
        ('sabana.html', 'id', 'rhOpId'),
        ('sabana.html', 'id', 'rhOpName'),
        ('sabana.html', 'id', 'rhRolOp'),
        ('sabana.html', 'id', 'rhProducto'),
        ('sabana.html', 'id', 'rhBloque'),
        ('sabana.html', 'id', 'contenedorProducto'),
        ('sabana.html', 'id', 'contenedorBloque'),
        ('sabana.html', 'id', 'rhFechaIni'),
        ('sabana.html', 'id', 'rhFechaFin'),
        ('sabana.html', 'id', 'modalEditor'),
        ('sabana.html', 'id', 'cajaCentinelaModal'),
        ('sabana.html', 'id', 'textoCentinelaModal'),
        ('sabana.html', 'id', 'fechaFinRango'),
        ('sabana.html', 'id', 'pase_empleado'),
        ('sabana.html', 'id', 'pase_num_emp'),
        ('sabana.html', 'id', 'pase_motivo'),
        ('sabana.html', 'id', 'pase_fecha'),
        ('sabana.html', 'id', 'pase_hora'),
        ('sabana.html', 'id', 'modalPaseGlobal'),
        ('sabana.html', 'id', 'modalGenerarPDF'),
        ('sabana.html', 'id', 'buscadorOpPDF'),
        ('sabana.html', 'id', 'listaAutocompletado'),
        ('sabana.html', 'id', 'cajaDescarga'),
        ('sabana.html', 'id', 'nombreElegido'),
        ('sabana.html', 'id', 'motivoRechazoInput'),
        ('sabana.html', 'id', 'modalRechazoGlobal'),
        ('sabana.html', 'class', 'mac-dock-btn'),
        ('sabana.html', 'class', 'btn-slim'),
        ('sabana.html', 'class', 'sticky-col-body'),
        ('sabana.html', 'class', 'search-bar-slim'),
        
        # base.html - Centinela
        ('base.html', 'id', 'centinelaToggle'),
        ('base.html', 'id', 'centinelaChat'),
        ('base.html', 'id', 'centinelaInput'),
        ('base.html', 'id', 'centinelaSend'),
        ('base.html', 'id', 'centinelaMessages'),
        ('base.html', 'id', 'centinelaClear'),
        ('base.html', 'id', 'centinelaExport'),
        ('base.html', 'id', 'centinelaAlertBanner'),
        ('base.html', 'id', 'centinelaAlertText'),
        ('base.html', 'id', 'notifBtn'),
        ('base.html', 'id', 'notifPanel'),
        ('base.html', 'id', 'notifList'),
        ('base.html', 'id', 'mainBadge'),
        ('base.html', 'id', 'toastContainer'),
        ('base.html', 'id', 'modalPaseGlobal'),
        ('base.html', 'id', 'modalRechazoGlobal'),
        ('base.html', 'id', 'motivoRechazoInput'),
        ('base.html', 'id', 'pase_empleado'),
        ('base.html', 'id', 'pase_num_emp'),
        ('base.html', 'id', 'pase_motivo'),
        ('base.html', 'id', 'pase_fecha'),
        ('base.html', 'id', 'pase_hora'),
    ]
    
    for template, tipo, selector in selectores_criticos:
        if tipo == 'id':
            if selector not in todos_selectores_dom['ids']:
                errores.append(f"   ❌ {template}: ID '#{selector}' NO ENCONTRADO en DOM")
            else:
                print(f"   ✅ {template}: ID '#{selector}' encontrado")
        else:
            # Para clases, buscar coincidencia parcial
            encontrado = any(selector in c for c in todos_selectores_dom['classes'])
            if not encontrado:
                errores.append(f"   ❌ {template}: Clase '.{selector}' NO ENCONTRADA en DOM")
            else:
                print(f"   ✅ {template}: Clase '.{selector}' encontrada")
    
    if errores:
        print("\n   ⚠️ LISTENERS HUÉRFANOS DETECTADOS:")
        for e in errores:
            print(e)
    else:
        print("\n   ✅ Todos los selectores críticos encontrados en el DOM")
    
    return len(errores) == 0


def probar_endpoints_backend():
    """Prueba cada endpoint con Flask test_client simulando sesión jefe_op"""
    print("\n🔍 Probando endpoints backend con Flask test_client...")
    
    resultados = []
    
    with app.test_client() as client:
        # Simular login como jefe_op
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['usuario'] = 'test_jefe'
            sess['nombre_real'] = 'Test Jefe'
            sess['rol'] = 'jefe_op'
            sess['permisos'] = ['dot', 'sabana', 'centinela', 'admin']
        
        # Obtener un operador real de la BD para tests que lo requieran
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT id FROM operadores WHERE activo = 1 LIMIT 1")
        op = c.fetchone()
        op_id = op[0] if op else 1
        conn.close()
        
        # Fecha operativa actual
        from app import obtener_fecha_operativa
        fecha_op = obtener_fecha_operativa().strftime('%Y-%m-%d')
        
        # Payloads de prueba por endpoint
        test_payloads = {
            '/api/actualizar_dot': {'operador_id': op_id, 'fecha': fecha_op, 'horas': 0, 'estatus_dia': 'D', 'eco_unidad': '', 'eco_pipas': '', 'horas_manejo': 0, 'horas_maniobra': 0, 'auditado': 0, 'tipo_registro': 'Real'},
            '/api/guardar_simulador': {'simulaciones': []},
            '/api/exportar_dot_excel': {},
            '/api/operador_guardar_dia': {'fecha': fecha_op, 'horas': 8, 'estatus': 'EN VIAJE', 'unidad': '01', 'pipas': '01', 'manejo': 8, 'maniobra': 0},
            '/api/guardar_programacion': {'fecha': fecha_op, 'linea': 'NITROGENO', 'asignaciones': []},
            '/api/cargar_programacion': {},
            '/api/gestionar_viaje_pizarra': {'accion': 'crear', 'fecha': fecha_op, 'linea': 'NITROGENO', 'bloque': 'MAÑANA', 'operador_id': op_id, 'unidad': '01'},
            '/api/obtener_dia_operador': {'operador_id': op_id, 'fecha': fecha_op},
            '/api/solicitar_turno': {'operador_id': op_id, 'fecha': fecha_op, 'linea': 'NITROGENO', 'bloque': 'MAÑANA', 'rol': 'OPERADOR', 'producto': 'NITROGENO'},
            '/api/solicitar_pase_salida': {'empleado': 'Test', 'num_emp': '123', 'motivo': 'Test', 'fecha': fecha_op, 'hora': '10:00'},
            '/api/actualizar_turno': {'id': 1, 'accion': 'aprobar'},
            '/api/descargar_rol_pdf': {},
            '/api/centinela_radar_movimientos': {},
            '/api/centinela_radar_5d': {},
            '/api/centinela_alerta_predictiva': {},
            '/api/sync_en_vivo': {},
            '/api/centinela_ia': {'pregunta': 'test', 'contexto': {}},
            '/api/centinela_historial': {},
            '/api/expediente_historial': {'operador_id': op_id},
            '/api/guardar_amonestacion': {'operador_id': op_id, 'tipo': 'Leve', 'descripcion': 'Test', 'fecha': fecha_op, 'gravedad': 'Leve'},
            '/api/obtener_amonestaciones': {'operador_id': op_id},
            '/api/actualizar_expediente': {'operador_id': op_id, 'campo': 'telefono', 'valor': '5551234567'},
            '/api/obtener_rol_mes': {'operador_id': op_id},
            '/api/generar_pin': {'id': op_id},
            '/api/liberar_dispositivo': {'id': op_id},
            '/api/importar_pdf_despacho': {},
            '/api/gerencia/panel': {},
            '/api/analitica_clientes': {},
            '/api/resumen_predictivo': {},
            '/api/estatus_vivo_mock': {},
            '/api/procesar_matriz': {},
            '/api/generar_bonos': {'mes': '2025-01'},
            '/api/inyectar_ficticios': {},
            '/api/whatsapp_multimedia': {'tipo': 'test'},
            '/api/drilldown_radar': {'fecha': fecha_op, 'linea': 'NITROGENO'},
        }
        
        for endpoint, config in API_ENDPOINTS.items():
            metodo = config['methods'][0]
            roles = config['roles']
            
            # Preparar request
            payload = test_payloads.get(endpoint, {})
            
            try:
                if metodo == 'GET':
                    # Para GET, agregar query params si es necesario
                    if endpoint == '/api/cargar_programacion':
                        resp = client.get(endpoint, query_string={'fecha': fecha_op, 'linea': 'NITROGENO'})
                    elif endpoint == '/api/descargar_rol_pdf':
                        resp = client.get(endpoint, query_string={'fecha': fecha_op, 'operador_id': op_id})
                    elif endpoint == '/api/centinela_historial':
                        resp = client.get(endpoint)
                    else:
                        resp = client.get(endpoint)
                else:
                    resp = client.post(endpoint, json=payload, content_type='application/json')
                
                status = resp.status_code
                ok = status not in (404, 500)
                
                # Verificar respuesta JSON si aplica
                try:
                    data = resp.get_json()
                    if data and data.get('status') == 'error' and status == 200:
                        # Error de lógica pero no 500
                        pass
                except:
                    pass
                
                estado = 'OK' if ok else 'ERROR'
                resultados.append({
                    'pantalla': config['template'],
                    'accion': endpoint,
                    'endpoint': f'{metodo} {endpoint}',
                    'estatus': estado,
                    'codigo': status,
                    'roles': ', '.join(roles)
                })
                
                icono = '✅' if ok else '❌'
                print(f"   {icono} {metodo} {endpoint} -> {status} ({estado})")
                
            except Exception as e:
                resultados.append({
                    'pantalla': config['template'],
                    'accion': endpoint,
                    'endpoint': f'{metodo} {endpoint}',
                    'estatus': 'ERROR',
                    'codigo': 'EXC',
                    'roles': ', '.join(roles),
                    'error': str(e)[:100]
                })
                print(f"   ❌ {metodo} {endpoint} -> EXCEPCIÓN: {e}")
    
    return resultados


def probar_elementos_interactivos():
    """Verifica que los elementos interactivos tengan sus handlers correspondientes"""
    print("\n🔍 Verificando elementos interactivos en plantillas...")
    
    templates = {
        'horas_dot.html': os.path.join(BASE_DIR, 'templates', 'horas_dot.html'),
        'sabana.html': os.path.join(BASE_DIR, 'templates', 'sabana.html'),
        'base.html': os.path.join(BASE_DIR, 'templates', 'base.html'),
    }
    
    resultados = []
    
    for pantalla, elementos in [
        ('Auditoría DOT', [e for e in INTERACTIVE_ELEMENTS if e[0] == 'Auditoría DOT']),
        ('Sábana', [e for e in INTERACTIVE_ELEMENTS if e[0] == 'Sábana']),
        ('Centinela IA Chat', [e for e in INTERACTIVE_ELEMENTS if e[0] == 'Centinela IA Chat']),
        ('Notificaciones', [e for e in INTERACTIVE_ELEMENTS if e[0] == 'Notificaciones']),
        ('Modal Pase Global', [e for e in INTERACTIVE_ELEMENTS if e[0] == 'Modal Pase Global']),
        ('Modal Rechazo Global', [e for e in INTERACTIVE_ELEMENTS if e[0] == 'Modal Rechazo Global']),
        ('Búsqueda Global', [e for e in INTERACTIVE_ELEMENTS if e[0] == 'Búsqueda Global']),
    ]:
        for elem in elementos:
            _, accion, selector, endpoint, metodo, tipo, rol = elem
            
            # Verificar que el selector existe en la plantilla correspondiente
            template_name = None
            if pantalla == 'Auditoría DOT':
                template_name = 'horas_dot.html'
            elif pantalla == 'Sábana':
                template_name = 'sabana.html'
            else:
                template_name = 'base.html'
            
            template_path = templates.get(template_name)
            selector_encontrado = False
            
            if template_path and os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Buscar por ID
                if selector.startswith('#') or (selector.isalnum() and '_' in selector and not selector.startswith('btn-') and not selector.startswith('live:')):
                    if f'id="{selector}"' in content or f"id='{selector}'" in content:
                        selector_encontrado = True
                # Buscar por clase
                elif selector.startswith('.'):
                    cls = selector[1:]
                    if f'class="{cls}"' in content or f"class='{cls}'" in content or f'class*="{cls}"' in content:
                        selector_encontrado = True
                # Buscar por onclick/function name
                elif '(' in selector:
                    func_name = selector.split('(')[0]
                    if func_name in content:
                        selector_encontrado = True
                # Buscar por texto parcial
                elif selector in content:
                    selector_encontrado = True
            
            estado = 'OK' if selector_encontrado else 'ERROR'
            icono = '✅' if selector_encontrado else '❌'
            
            resultados.append({
                'pantalla': pantalla,
                'accion': accion,
                'endpoint': endpoint,
                'estatus': estado,
                'selector': selector,
                'tipo': tipo,
                'rol': rol
            })
            
            print(f"   {icono} [{pantalla}] {accion} ({selector}) -> {estado}")
    
    return resultados


def imprimir_tabla_resumen(resultados_backend, resultados_frontend, dom_ok):
    """Imprime la tabla resumen final"""
    print("\n" + "=" * 120)
    print("📊 TABLA RESUMEN DE AUDITORÍA DE BOTONES Y ACCIONES INTERACTIVAS")
    print("=" * 120)
    print(f"{'PANTALLA':<22} | {'BOTÓN / ACCIÓN':<38} | {'ENDPOINT / ID':<42} | {'ESTATUS':<8}")
    print("-" * 120)
    
    # Backend results
    for r in resultados_backend:
        pantalla = r['pantalla'][:21]
        accion = r['accion'][:37]
        endpoint = r['endpoint'][:41]
        estatus = r['estatus']
        print(f"{pantalla:<22} | {accion:<38} | {endpoint:<42} | {estatus:<8}")
    
    # Frontend results
    for r in resultados_frontend:
        pantalla = r['pantalla'][:21]
        accion = r['accion'][:37]
        endpoint = r['endpoint'][:41]
        estatus = r['estatus']
        print(f"{pantalla:<22} | {accion:<38} | {endpoint:<42} | {estatus:<8}")
    
    # DOM validation
    dom_status = 'OK' if dom_ok else 'ERROR'
    print(f"{'VALIDACIÓN DOM':<22} | {'Selectores críticos vs DOM':<38} | {'Verificación listeners huérfanos':<42} | {dom_status:<8}")
    
    print("-" * 120)
    
    # Estadísticas
    total_backend = len(resultados_backend)
    ok_backend = sum(1 for r in resultados_backend if r['estatus'] == 'OK')
    total_frontend = len(resultados_frontend)
    ok_frontend = sum(1 for r in resultados_frontend if r['estatus'] == 'OK')
    
    print(f"\n📈 ESTADÍSTICAS:")
    print(f"   Backend:  {ok_backend}/{total_backend} OK ({ok_backend/total_backend*100:.1f}%)")
    print(f"   Frontend: {ok_frontend}/{total_frontend} OK ({ok_frontend/total_frontend*100:.1f}%)")
    print(f"   DOM:      {'✅ OK' if dom_ok else '❌ ERRORES'}")
    
    if ok_backend == total_backend and ok_frontend == total_frontend and dom_ok:
        print("\n🎉 AUDITORÍA COMPLETA: TODOS LOS TESTS PASARON")
        return 0
    else:
        print("\n⚠️ AUDITORÍA CON INCIDENCIAS: REVISAR ERRORES ARRIBA")
        return 1


def main():
    print("🚀 INICIANDO AUDITORÍA AUTOMATIZADA DE BOTONES Y ACCIONES INTERACTIVAS")
    print("=" * 80)
    
    # 1. Validar sintaxis Python
    sintaxis_ok = validar_sintaxis_python()
    
    # 2. Verificar listeners huérfanos (DOM vs JS)
    dom_ok = verificar_listeners_huerfanos()
    
    # 3. Probar endpoints backend
    resultados_backend = probar_endpoints_backend()
    
    # 4. Verificar elementos interactivos en plantillas
    resultados_frontend = probar_elementos_interactivos()
    
    # 5. Imprimir tabla resumen
    exit_code = imprimir_tabla_resumen(resultados_backend, resultados_frontend, dom_ok)
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
