/* ========================================================
   GRUPO FNG - MÓDULO PERFIL DE OPERADORES Y EXPEDIENTES RH
   Filtros, Tabs (Activos/Bajas), Cápsulas y Exportación Excel
   ======================================================== */

let operadoresData = [];

// 1. INICIALIZACIÓN
window.addEventListener('DOMContentLoaded', () => {
    operadoresData = window.OPERADORES_DATA || [];
    
    // Configurar buscador
    const inputBuscador = document.getElementById('buscadorOperadores');
    if (inputBuscador) {
        inputBuscador.addEventListener('input', filtrarTablaOperadores);
    }
});

// 2. ALTERNANCIA DE PESTAÑAS (ACTIVOS VS BAJAS)
function switchTabOperadores(tipo, btn) {
    document.querySelectorAll('.tab-pill-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');

    const filas = document.querySelectorAll('.fila-operador');
    filas.forEach(f => {
        const estatus = f.getAttribute('data-estatus-rh') || 'ACTIVO';
        if (tipo === 'TODOS' || estatus === tipo) {
            f.style.display = '';
        } else {
            f.style.display = 'none';
        }
    });
}

// 3. BUSCADOR EN TIEMPO REAL
function filtrarTablaOperadores() {
    const term = (document.getElementById('buscadorOperadores')?.value || '').toLowerCase().trim();
    const filas = document.querySelectorAll('.fila-operador');

    filas.forEach(f => {
        const nombre = (f.querySelector('.col-nombre')?.textContent || '').toLowerCase();
        const nomina = (f.querySelector('.col-nomina')?.textContent || '').toLowerCase();
        const coincide = nombre.includes(term) || nomina.includes(term);
        f.style.display = coincide ? '' : 'none';
    });
}

// 4. CÁPSULAS INTERACTIVAS (PRODUCTOS Y CERTIFICACIONES)
function toggleCapsula(btn, inputHiddenId) {
    btn.classList.toggle('active');
    const contenedor = btn.closest('.capsule-group');
    if (!contenedor) return;

    const activas = Array.from(contenedor.querySelectorAll('.capsule-btn.active'))
                         .map(b => b.getAttribute('data-val'));
    
    const inputHidden = document.getElementById(inputHiddenId);
    if (inputHidden) {
        inputHidden.value = activas.join(',');
    }
}

// 5. MODAL EXPEDIENTE DIGITAL
function abrirModalExpediente(idOp) {
    const op = operadoresData.find(o => String(o.id) === String(idOp));
    if (!op) {
        showToast("No se encontró el registro del operador", "warning");
        return;
    }

    const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.value = val !== undefined && val !== null ? val : '';
    };
    const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = val || '--';
    };

    setText('expNombreHeader', op.nombre);
    setText('expNominaHeader', `Nómina: ${op.num_empleado || op.id}`);
    
    setVal('expOpId', op.id);
    setVal('expNombre', op.nombre);
    setVal('expTelefono', op.telefono);
    setVal('expLicenciaVenc', op.licencia_vigencia);
    setVal('expAptoVenc', op.apto_medico_vigencia);
    setVal('expEsquema', op.esquema);

    // Sincronizar cápsulas de producto
    const prods = (op.productos_descarga || '').split(',').map(p => p.trim());
    document.querySelectorAll('#grupoCapsulasProductos .capsule-btn').forEach(btn => {
        const val = btn.getAttribute('data-val');
        btn.classList.toggle('active', prods.includes(val));
    });

    const modal = document.getElementById('modalExpediente');
    if (modal) modal.style.display = 'flex';
}

function cerrarModalExpediente() {
    const modal = document.getElementById('modalExpediente');
    if (modal) modal.style.display = 'none';
}

// 6. GUARDAR ACTUALIZACIÓN DE EXPEDIENTE
async function guardarExpediente() {
    const id = document.getElementById('expOpId')?.value;
    if (!id) return;

    const prodsActivos = Array.from(document.querySelectorAll('#grupoCapsulasProductos .capsule-btn.active'))
                              .map(b => b.getAttribute('data-val')).join(',');

    const payload = {
        id: id,
        telefono: document.getElementById('expTelefono')?.value,
        licencia_vigencia: document.getElementById('expLicenciaVenc')?.value,
        apto_medico_vigencia: document.getElementById('expAptoVenc')?.value,
        esquema: document.getElementById('expEsquema')?.value,
        productos_descarga: prodsActivos
    };

    try {
        const res = await fetch('/api/actualizar_operador', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            cerrarModalExpediente();
            showToast("Expediente actualizado exitosamente", "success");
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast("Error al guardar cambios", "warning");
        }
    } catch (e) {
        showToast("Error de conexión con el servidor", "warning");
    }
}

// 7. EXPORTACIÓN A EXCEL (SHEETJS)
function exportarExcelRH() {
    showToast("Generando libro Excel...", "info");
    const tabla = document.getElementById('tablaOperadoresMaster');
    if (!tabla) return;

    const wb = XLSX.utils.table_to_book(tabla, { sheet: "Operadores F-OPE" });
    const fecha = new Date().toISOString().split('T')[0];
    XLSX.writeFile(wb, `Plantilla_Operadores_${fecha}.xlsx`);
    showToast("Descarga completada", "success");
}