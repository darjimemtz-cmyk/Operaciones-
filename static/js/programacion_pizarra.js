/* ========================================================
   GRUPO FNG - MÓDULO PIZARRA DE DESPACHO (DISPATCH)
   Celdas interactivas, Escalas, Semáforos C/V y Modales
   ======================================================== */

let viajeSeleccionadoId = null;

// 1. FILTRADO POR PRODUCTO (DOCK SLIM)
function filtrarProductoPizarra(producto, btn) {
    document.querySelectorAll('.mac-dock-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');

    const filas = document.querySelectorAll('.prog-table tbody tr:not(.fila-nuevo-viaje)');
    filas.forEach(fila => {
        const prodFila = fila.getAttribute('data-producto') || '';
        if (producto === 'TODOS' || prodFila === producto) {
            fila.style.display = '';
        } else {
            fila.style.display = 'none';
        }
    });
}

// 2. SEMÁFORO C/V (CARGADO / VACÍO)
function toggleCV(btn) {
    if (btn.classList.contains('cv-gray')) {
        btn.classList.remove('cv-gray');
        btn.classList.add('cv-green');
        btn.innerText = 'C';
    } else if (btn.classList.contains('cv-green')) {
        btn.classList.remove('cv-green');
        btn.classList.add('cv-red');
        btn.innerText = 'V';
    } else {
        btn.classList.remove('cv-red');
        btn.classList.add('cv-gray');
        btn.innerText = '';
    }
}

// 3. AGREGAR Y QUITAR ESCALAS DE CLIENTE
function agregarEscala(btn) {
    const celda = btn.closest('tr').querySelector('.col-apilada');
    if (!celda) return;

    const div = document.createElement('div');
    div.className = 'escala-item';
    div.innerHTML = `
        <input type="text" class="cell-input text-left" placeholder="Cliente / Destino..." style="flex: 2;">
        <input type="text" class="cell-input" placeholder="Ton / Obs" style="flex: 1;">
        <button type="button" class="btn-row minus" onclick="eliminarEscala(this)" title="Quitar escala">
            <i class="fas fa-minus-circle"></i>
        </button>
    `;
    celda.appendChild(div);
}

function eliminarEscala(btn) {
    const item = btn.closest('.escala-item');
    if (item) item.remove();
}

// 4. MODO EDICIÓN VS BLOQUEO DE FILA
function toggleEdicionFila(btn) {
    const fila = btn.closest('tr');
    if (!fila) return;

    const estaEditando = fila.classList.contains('fila-editando');

    if (estaEditando) {
        // Guardar y bloquear fila
        fila.classList.remove('fila-editando');
        fila.classList.add('fila-bloqueada');
        btn.innerHTML = '<i class="fas fa-lock"></i>';
        btn.classList.remove('editing');
        guardarFilaIndividual(fila);
    } else {
        // Desbloquear fila para edición
        fila.classList.remove('fila-bloqueada');
        fila.classList.add('fila-editando');
        btn.innerHTML = '<i class="fas fa-check"></i>';
        btn.classList.add('editing');
        showToast("Fila desbloqueada para edición", "info");
    }
}

// 5. GUARDADO ASÍNCRONO
async function guardarFilaIndividual(fila) {
    const inputs = fila.querySelectorAll('input');
    let datosFila = {};
    inputs.forEach(inp => {
        if (inp.name) datosFila[inp.name] = inp.value;
    });

    try {
        const res = await fetch('/api/guardar_viaje_pizarra', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(datosFila)
        });
        if (res.ok) {
            showToast("Viaje guardado correctamente", "success");
        } else {
            showToast("Error al guardar viaje", "warning");
        }
    } catch (e) {
        showToast("Error de conexión al servidor", "warning");
    }
}

// 6. ACCIONES RÁPIDAS Y MODALES FLOTANTES
function abrirModalAccionViaje(idViaje) {
    viajeSeleccionadoId = idViaje;
    const modal = document.getElementById('modalGestionViaje');
    if (modal) modal.style.display = 'flex';
}

function cerrarModalAccionViaje() {
    viajeSeleccionadoId = null;
    const modal = document.getElementById('modalGestionViaje');
    if (modal) modal.style.display = 'none';
}

function abrirModalAlertaNocturna(idViaje) {
    viajeSeleccionadoId = idViaje;
    const modal = document.getElementById('modalAlertaNocturna');
    if (modal) modal.style.display = 'flex';
}

function cerrarModalAlertaNocturna() {
    viajeSeleccionadoId = null;
    const modal = document.getElementById('modalAlertaNocturna');
    if (modal) modal.style.display = 'none';
}

async function resolverViaje(estado) {
    if (!viajeSeleccionadoId) return;
    try {
        const res = await fetch('/api/actualizar_estado_viaje', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ viaje_id: viajeSeleccionadoId, estado: estado })
        });
        if (res.ok) {
            cerrarModalAccionViaje();
            showToast(`Viaje marcado como: ${estado}`, "success");
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast("No se pudo actualizar el estado", "warning");
        }
    } catch (e) {
        showToast("Error de conexión", "warning");
    }
}

async function confirmarPendienteNocturno() {
    if (!viajeSeleccionadoId) return;
    try {
        const res = await fetch('/api/marcar_pendiente_nocturno', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ viaje_id: viajeSeleccionadoId })
        });
        if (res.ok) {
            cerrarModalAlertaNocturna();
            const fila = document.getElementById(`fila-viaje-${viajeSeleccionadoId}`);
            if (fila) fila.classList.add('row-pending');
            showToast("🌙 Alerta nocturna activada", "success");
        }
    } catch (e) {
        showToast("Error de conexión", "warning");
    }
}