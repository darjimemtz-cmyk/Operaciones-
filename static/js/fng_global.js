/* ========================================================
   GRUPO FNG - NÚCLEO GLOBAL JAVASCRIPT (UI / ACCIONES)
   ======================================================== */

// 1. MENÚ LATERAL Y DROPDOWNS
function abrirMenu() { 
    const menu = document.getElementById('floatingMenu');
    const overlay = document.getElementById('menuOverlay');
    if (menu) menu.classList.add('open'); 
    if (overlay) overlay.classList.add('open'); 
}

function cerrarMenu() { 
    const menu = document.getElementById('floatingMenu');
    const overlay = document.getElementById('menuOverlay');
    if (menu) menu.classList.remove('open'); 
    if (overlay) overlay.classList.remove('open'); 
}

function toggleDropdown(id) {
    const el = document.getElementById(id);
    if (!el) return;
    if (el.style.display === 'block') { 
        el.style.display = 'none'; 
    } else {
        document.querySelectorAll('.dropdown-panel').forEach(d => d.style.display = 'none');
        el.style.display = 'block';
    }
}

// Cierre de dropdowns al dar clic fuera
window.addEventListener('click', function(e) {
    if (!e.target.closest('.dropdown-container')) {
        document.querySelectorAll('.dropdown-panel').forEach(d => d.style.display = 'none');
    }
});

// 2. CONTROL DE APARIENCIA (LIGHT / DARK MODE)
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('fng_dark_mode', isDark);
    const ts = document.getElementById('theme-switch'); 
    if (ts) ts.checked = isDark;
}

// 3. SISTEMA DE TOASTS FLOTANTES
function showToast(msg, type = "success") {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div'); 
    toast.className = `toast ${type}`;
    const icon = type === 'success' ? '<i class="fas fa-check-circle"></i>' : '<i class="fas fa-hourglass-half"></i>';
    toast.innerHTML = `${icon} ${msg}`;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => { 
        toast.classList.remove('show'); 
        setTimeout(() => toast.remove(), 400); 
    }, 3000); 
}

// 4. GESTIÓN DE NOTIFICACIONES Y AVISOS
function actualizarBadge(restar_todo = false) {
    const badge = document.getElementById('mainBadge');
    if (!badge) return;
    if (restar_todo) { 
        badge.style.display = 'none'; 
        badge.innerText = "0"; 
        return; 
    }
    const actual = parseInt(badge.innerText) || 0;
    if (actual > 1) { 
        badge.innerText = actual - 1; 
    } else { 
        badge.style.display = 'none'; 
        badge.innerText = "0"; 
    }
}

async function marcarTodasLeidas() {
    try {
        const res = await fetch('/api/leer_notificacion', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify({id: 'all'})
        });
        if (res.ok) {
            document.querySelectorAll('.notif-card.unread').forEach(el => { 
                el.classList.remove('unread'); 
                el.onclick = null; 
            });
            actualizarBadge(true);
            showToast("Avisos marcados como leídos", "success");
        }
    } catch (e) {
        showToast("Error de conexión al marcar avisos", "warning");
    }
}

async function abrirAviso(id, fecha, msj) {
    const elFecha = document.getElementById('avisoDetalleFecha');
    const elMsj = document.getElementById('avisoDetalleMsj');
    const modal = document.getElementById('modalAvisoDetalle');
    if (elFecha) elFecha.innerHTML = `<i class="far fa-clock"></i> ${fecha}`;
    if (elMsj) elMsj.innerText = msj;
    if (modal) modal.style.display = 'flex';
    
    const card = document.getElementById('notif-' + id);
    if (card && card.classList.contains('unread')) {
        try {
            const res = await fetch('/api/leer_notificacion', { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({id: id})
            });
            if (res.ok) {
                card.classList.remove('unread');
                actualizarBadge();
            }
        } catch (e) {}
    }
}

// 5. SOLICITUDES Y PASES DE SALIDA
let idRechazoActivo = null;
let solActualData = null;

function abrirModalPase() {
    const modal = document.getElementById('modalPaseGlobal');
    if (modal) modal.style.display = 'flex';
}

async function enviarPaseGlobal(e) {
    e.preventDefault();
    const data = {
        empleado: document.getElementById('pase_empleado').value,
        num_emp: document.getElementById('pase_num_emp').value,
        depto: document.getElementById('pase_depto').value,
        puesto: document.getElementById('pase_puesto').value,
        tipo_permiso: document.getElementById('pase_tipo').value,
        motivo: document.getElementById('pase_motivo').value,
        lugar: document.getElementById('pase_lugar').value,
        hora_esperada: document.getElementById('pase_hora_salida').value,
        hora_regreso: document.getElementById('pase_hora_regreso').value,
        tipo_incidencia: document.getElementById('pase_incidencia').value
    };

    try {
        const res = await fetch('/api/solicitar_pase_salida', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const responseData = await res.json();
        if (responseData.status === 'success') {
            document.getElementById('modalPaseGlobal').style.display = 'none';
            document.getElementById('formPaseGlobal').reset();
            showToast("Pase emitido exitosamente a Caseta", "success");
        } else {
            showToast("Error al emitir el pase", "warning");
        }
    } catch (err) {
        showToast("Error de conexión al emitir pase", "warning");
    }
}

function abrirModalSolicitudDetalle(id, accion, datos, usuario, fecha) {
    solActualData = { id: id, accion: accion, datos: datos };
    const titulo = document.getElementById('modalSolTitulo');
    const cajaMotivo = document.getElementById('cajaMotivoRechazo');
    const cajaBotones = document.getElementById('cajaBotonesDecision');

    document.getElementById('modalSolUsuario').innerText = usuario || 'Personal de Turno';
    document.getElementById('modalSolFecha').innerText = fecha || '--';
    document.getElementById('modalSolOperador').innerText = datos.nombre || 'N/A';
    
    const fInicio = datos.fecha || '--';
    const fFin = datos.fecha_fin || fInicio;
    document.getElementById('modalSolCambio').innerText = `${datos.estatus_ant || 'TR'} ➔ ${datos.estatus_nuevo || 'DE'}`;
    document.getElementById('modalSolRango').innerText = fInicio === fFin ? `Día ${fInicio}` : `Del ${fInicio} al ${fFin}`;
    
    if (cajaMotivo) cajaMotivo.style.display = 'none';
    if (titulo) titulo.innerHTML = '<i class="fas fa-clipboard-check" style="color: var(--fng-orange);"></i> Revisión de Solicitud Operativa';
    
    if (cajaBotones) {
        cajaBotones.innerHTML = `
            <button type="button" onclick="document.getElementById('modalConfirmarSolicitud').style.display='none'" class="btn-light" style="padding: 10px 16px; border-radius: 8px; border: none; font-weight: bold; cursor: pointer;">Cerrar</button>
            <button type="button" onclick="prepararRechazo()" style="padding: 10px 18px; border-radius: 8px; border: none; background: #ef4444; color: white; font-weight: bold; cursor: pointer;"><i class="fas fa-times"></i> Rechazar</button>
            <button type="button" onclick="ejecutarAprobacionDirecta()" style="padding: 10px 20px; border-radius: 8px; border: none; background: #10b981; color: white; font-weight: bold; cursor: pointer;"><i class="fas fa-check"></i> Aprobar Cambio</button>
        `;
    }
    const modal = document.getElementById('modalConfirmarSolicitud');
    if (modal) modal.style.display = 'flex';
}

function prepararRechazo() {
    if (!solActualData) return;
    solActualData.accion = 'rechazar';
    document.getElementById('cajaMotivoRechazo').style.display = 'block';
    const cajaBotones = document.getElementById('cajaBotonesDecision');
    cajaBotones.innerHTML = `
        <button type="button" onclick="abrirModalSolicitudDetalle(solActualData.id, 'revisar', solActualData.datos, document.getElementById('modalSolUsuario').innerText, document.getElementById('modalSolFecha').innerText)" class="btn-light" style="padding: 10px 16px; border-radius: 8px; border: none; font-weight: bold; cursor: pointer;">Volver</button>
        <button type="button" onclick="ejecutarDecisionFinal()" style="padding: 10px 20px; border-radius: 8px; border: none; background: #ef4444; color: white; font-weight: bold; cursor: pointer;">Confirmar Rechazo</button>
    `;
}

function ejecutarAprobacionDirecta() {
    if (!solActualData) return;
    solActualData.accion = 'aprobar';
    ejecutarDecisionFinal();
}

async function ejecutarDecisionFinal() {
    if (!solActualData) return;
    let motivo = 'Sin observaciones';
    if (solActualData.accion === 'rechazar') {
        motivo = document.getElementById('inputMotivoRechazoDetalle').value.trim();
        if (!motivo) {
            showToast("⚠️ Ingresa el motivo del rechazo", "warning");
            return;
        }
    }

    document.getElementById('modalConfirmarSolicitud').style.display = 'none';
    try {
        const res = await fetch('/api/gestionar_solicitud', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: solActualData.id, accion: solActualData.accion, motivo: motivo })
        });
        if (res.ok) {
            const card = document.getElementById(`req-card-${solActualData.id}`);
            if (card) {
                card.style.opacity = '0';
                setTimeout(() => card.remove(), 300);
            }
            actualizarBadge();
            showToast(solActualData.accion === 'aprobar' ? "✅ Cambio autorizado y aplicado" : "❌ Solicitud rechazada", "success");
        } else {
            showToast("⚠️ Error al procesar solicitud", "warning");
        }
    } catch (e) {
        showToast("Error de conexión", "warning");
    }
}

// 6. BUSCADOR GENÉRICO DE TABLAS
function buscadorGlobal(inputId, selectorTabla) {
    const inputEl = document.getElementById(inputId);
    if (!inputEl) return;
    const input = inputEl.value.toLowerCase();
    const rows = document.querySelectorAll(selectorTabla);
    rows.forEach(row => {
        const nameCell = row.cells[0]; 
        if (nameCell) { 
            row.style.display = nameCell.textContent.toLowerCase().includes(input) ? '' : 'none'; 
        }
    });
}