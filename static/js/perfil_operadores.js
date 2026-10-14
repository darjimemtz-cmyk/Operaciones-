/* ========================================================
   GRUPO FNG - MÓDULO PERFIL DE OPERADORES Y EXPEDIENTES RH
   Gestión F-OPE-01, Expediente Digital, Amonestaciones,
   Carga Masiva Excel, Altas en Cascada y Bajas
   ======================================================== */

let expActual = null;
let calendarioDataGlobal = [];
let operadorExpedienteActualId = null;

// 1. CONTROL DE PESTAÑAS (ACTIVOS VS BAJAS)
function cambiarVistaOperadores(vista) {
    const btnAct = document.getElementById('btnTabActivos');
    const btnBaj = document.getElementById('btnTabBajas');
    const tAct = document.getElementById('vistaTablaActivos');
    const tBaj = document.getElementById('vistaTablaBajas');
    const contador = document.getElementById('contadorFilas');

    if (btnAct) { btnAct.style.background = ''; btnAct.style.color = ''; }
    if (btnBaj) { btnBaj.style.background = ''; btnBaj.style.color = ''; }

    const totalActivos = document.querySelectorAll('#tablaRH tbody tr').length;
    const totalBajas = document.querySelectorAll('#tablaBajas tbody tr').length;

    if (vista === 'activos') {
        if (btnAct) btnAct.classList.add('active');
        if (btnBaj) btnBaj.classList.remove('active');
        if (tAct) tAct.style.display = 'block';
        if (tBaj) tBaj.style.display = 'none';
        if (contador) contador.innerText = totalActivos;
    } else {
        if (btnBaj) btnBaj.classList.add('active');
        if (btnAct) btnAct.classList.remove('active');
        if (tBaj) tBaj.style.display = 'block';
        if (tAct) tAct.style.display = 'none';
        if (contador) contador.innerText = totalBajas;
    }
    const inputBuscador = document.getElementById('buscadorRH');
    if (inputBuscador) inputBuscador.value = '';
}

// 2. BUSCADOR EXPANSIBLE Y FILTRADO MULTIVARIABLE
function expandirBuscadorRH() {
    const bar = document.getElementById('searchBarContainerRH');
    const input = document.getElementById('buscadorRH');
    if (bar && !bar.classList.contains('active')) {
        bar.classList.add('active');
        if (input) input.focus();
    }
}

function limpiarYColapsarBuscadorRH(e) {
    if (e) e.stopPropagation();
    const input = document.getElementById('buscadorRH');
    const bar = document.getElementById('searchBarContainerRH');
    if (input) {
        input.value = '';
        input.blur();
    }
    if (bar) bar.classList.remove('active');
    filtrarRH();
}

window.addEventListener('click', function(e) {
    const bar = document.getElementById('searchBarContainerRH');
    const input = document.getElementById('buscadorRH');
    if (bar && !bar.contains(e.target) && input && input.value.trim() === '') {
        bar.classList.remove('active');
    }
});

function filtrarRH() {
    const texto = (document.getElementById('buscadorRH')?.value || '').toLowerCase().trim();
    const btnActivos = document.getElementById('btnTabActivos');
    const esVistaActivos = btnActivos ? btnActivos.classList.contains('active') : true;
    const selector = esVistaActivos ? '#tablaRH tbody tr' : '#tablaBajas tbody tr';
    const filas = document.querySelectorAll(selector);
    let contadorVisibles = 0;
    
    filas.forEach(fila => {
        const contenido = fila.textContent.toLowerCase();
        if (contenido.includes(texto)) {
            fila.style.display = '';
            contadorVisibles++;
        } else {
            fila.style.display = 'none';
        }
    });
    
    const contador = document.getElementById('contadorFilas');
    if (contador) contador.innerText = contadorVisibles;
}

// 3. EXPEDIENTE DIGITAL DEL OPERADOR
function abrirExpediente(element) {
    try {
        expActual = JSON.parse(element.getAttribute('data-op') || '{}');
    } catch (e) {
        expActual = {};
    }
    
    operadorExpedienteActualId = expActual.id;
    const elNombre = document.getElementById('expNombre');
    const elIdBD = document.getElementById('expIdBD');
    const elFoto = document.getElementById('expFotoPerfil');
    const elUser = document.getElementById('disp_usuario_app');
    const elPass = document.getElementById('disp_pass_app');
    const elImp = document.getElementById('disp_imp');
    const elImei = document.getElementById('disp_imei');
    const elVac = document.getElementById('disp_vacaciones');

    if (elNombre) elNombre.innerText = expActual.nombre || '--';
    if (elIdBD) elIdBD.value = expActual.id || '';
    
    const fotoPerfil = expActual.foto && expActual.foto !== 'N/A' 
        ? `/static/fotos_perfil/${expActual.foto}` 
        : `/static/fotos_perfil/default.png`;
    if (elFoto) elFoto.src = fotoPerfil;

    if (elUser) elUser.innerText = expActual.usuario_app || 'N/A';
    if (elPass) elPass.innerText = expActual.no_empleado || 'N/A';
    if (elImp) elImp.innerText = expActual.imp || '--';
    if (elImei) elImei.innerText = expActual.imei || '--';
    if (elVac) elVac.innerText = expActual.vacaciones ? `${expActual.vacaciones} días acumulados` : '0 días';

    const modal = document.getElementById('modalExpediente');
    if (modal) modal.style.display = 'flex';

    if (expActual.id) {
        cargarHistorialOperativo(expActual.id);
        cargarAmonestaciones(expActual.id);
    }
}

function cerrarExpediente() { 
    const modal = document.getElementById('modalExpediente');
    if (modal) modal.style.display = 'none'; 
}

async function subirFotoDirecta(input) {
    if (!input.files || !input.files[0]) return;
    const formData = new FormData();
    const idVal = document.getElementById('expIdBD')?.value;
    formData.append('id', idVal);
    formData.append('foto_perfil', input.files[0]);

    try {
        const res = await fetch('/api/actualizar_expediente', { method: 'POST', body: formData });
        if (res.ok) {
            showToast("✅ Fotografía actualizada", "success");
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast("Error al subir la fotografía", "warning");
        }
    } catch(e) {
        showToast("Error de conexión", "warning");
    }
}

// 4. HISTORIAL OPERATIVO Y FATIGA (NOM-087)
async function cargarHistorialOperativo(op_id) {
    try {
        const res = await fetch('/api/expediente_historial', {
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify({operador_id: op_id})
        });
        const data = await res.json();
        if (data.status === 'success') {
            const elDesc = document.getElementById('disp_ult_descanso');
            const elHoy = document.getElementById('disp_estatus_hoy');
            const elHoras = document.getElementById('disp_horas_dot');

            if (elDesc) elDesc.innerText = data.ultimo_descanso || '--';
            
            let estHoy = data.estatus_hoy || '--';
            let colorHoy = estHoy.startsWith('TR') ? '#10b981' : (estHoy === 'DE' ? '#8b5cf6' : '#f59e0b');
            if (elHoy) elHoy.innerHTML = `<span style="background: ${colorHoy}; color: white; padding: 2px 7px; border-radius: 6px; font-size: 11px; font-weight:800;">${estHoy}</span>`;
            if (elHoras) elHoras.innerText = `${data.horas_dot || 0} hrs`;
            
            calendarioDataGlobal = data.calendario || [];
        }
    } catch(e) {
        console.error("Error cargando historial de fatiga", e);
    }
}

function abrirCalendario30Dias() {
    const grid = document.getElementById('cal_30_grid');
    if (!grid) return;
    grid.innerHTML = '';
    let c_tr = 0, c_de = 0, c_va = 0;

    calendarioDataGlobal.forEach(dia => {
        let est = dia.estatus || '';
        let bgEstatus = 'var(--bg-surface-2)', colorEstatus = 'var(--text-main)';
        if (est.startsWith('TR') || est.startsWith('CB')) { 
            bgEstatus = '#10b981'; colorEstatus = 'white'; c_tr++; 
        } else if (est === 'DE') { 
            bgEstatus = '#8b5cf6'; colorEstatus = 'white'; c_de++; 
        } else if (['VA', 'IN', 'PER', 'MED'].includes(est)) { 
            bgEstatus = '#3b82f6'; colorEstatus = 'white'; c_va++; 
        }

        grid.innerHTML += `
            <div style="border: 1px solid var(--border-subtle); border-radius: 8px; padding: 6px; background: var(--bg-surface); text-align: center;">
                <div style="font-size: 11px; font-weight: bold; color: var(--text-main);">${dia.dia_str}</div>
                <div style="background: ${bgEstatus}; color: ${colorEstatus}; border-radius: 6px; font-size: 11px; font-weight: 800; padding: 2px; margin-top: 3px;">${est}</div>
            </div>
        `;
    });

    const elTr = document.getElementById('cal_count_tr');
    const elDe = document.getElementById('cal_count_de');
    const elVa = document.getElementById('cal_count_va');
    if (elTr) elTr.innerText = c_tr;
    if (elDe) elDe.innerText = c_de;
    if (elVa) elVa.innerText = c_va;

    const modal = document.getElementById('modalCalendario30');
    if (modal) modal.style.display = 'flex';
}

// 5. REGISTRO DISCIPLINARIO Y AMONESTACIONES
function abrirModalNuevaAmonestacion() {
    if (!operadorExpedienteActualId) return;
    const inputFecha = document.getElementById('amon_fecha');
    const form = document.getElementById('formAmonestacion');
    if (form) form.reset();
    if (inputFecha) inputFecha.value = new Date().toISOString().split('T')[0];
    const modal = document.getElementById('modalNuevaAmonestacion');
    if (modal) modal.style.display = 'flex';
}

function cerrarModalNuevaAmonestacion() { 
    const modal = document.getElementById('modalNuevaAmonestacion');
    if (modal) modal.style.display = 'none'; 
}

async function cargarAmonestaciones(operadorId) {
    const tbody = document.getElementById('tablaAmonestacionesCuerpo');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:15px; color:#94a3b8;"><i class="fas fa-spinner fa-spin"></i> Cargando...</td></tr>`;
    
    try {
        const res = await fetch('/api/obtener_amonestaciones', {
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({ operador_id: operadorId })
        });
        const data = await res.json();
        if (data.status === 'success') {
            const setKpi = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
            setKpi('kpi_actas', data.kpis.actas);
            setKpi('kpi_combustible', data.kpis.combustible);
            setKpi('kpi_danos', data.kpis.danos);
            setKpi('kpi_retardos', data.kpis.retardos);
            setKpi('kpi_incidentes', data.kpis.incidentes);

            tbody.innerHTML = '';
            if (data.historial.length === 0) {
                tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:15px; color:#10b981; font-weight:600;"><i class="fas fa-check-circle"></i> Sin amonestaciones registradas.</td></tr>`;
                return;
            }
            data.historial.forEach(reg => {
                let f = reg.fecha.split('-');
                tbody.innerHTML += `
                    <tr style="border-bottom: 1px solid var(--border-subtle); font-size: 11px;">
                        <td style="padding: 6px; text-align: center; font-weight: 700; color: var(--text-muted);">${f[2]}/${f[1]}/${f[0]}</td>
                        <td style="padding: 6px; text-align: left; font-weight: 700; color: var(--text-main);">${reg.tipo}</td>
                        <td style="padding: 6px; text-align: left; color: var(--text-muted);">${reg.descripcion}</td>
                        <td style="padding: 6px; text-align: center;"><span style="font-size: 10px; font-weight: 800; padding: 2px 6px; border-radius: 4px; background:var(--bg-surface-2); color:var(--text-main);">${reg.estatus}</span></td>
                    </tr>
                `;
            });
        }
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:15px; color:#ef4444;">Error al cargar.</td></tr>`;
    }
}

async function enviarNuevaAmonestacion(event) {
    event.preventDefault();
    const payload = {
        operador_id: operadorExpedienteActualId,
        fecha: document.getElementById('amon_fecha')?.value,
        tipo: document.getElementById('amon_tipo')?.value,
        descripcion: document.getElementById('amon_descripcion')?.value,
        estatus: document.getElementById('amon_estatus')?.value
    };
    try {
        const res = await fetch('/api/guardar_amonestacion', {
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            cerrarModalNuevaAmonestacion();
            cargarAmonestaciones(operadorExpedienteActualId);
            showToast("✅ Amonestación registrada con éxito", "success");
        } else {
            showToast("Error al registrar amonestación", "warning");
        }
    } catch(e) {
        showToast("Error de conexión", "warning");
    }
}

// 6. CÁPSULAS INTERACTIVAS Y EDICIÓN COMPLETA
function toggleCapsulaProducto(btn) {
    btn.classList.toggle('active');
    actualizarProductosSeleccionados();
}

function actualizarProductosSeleccionados() {
    const activas = Array.from(document.querySelectorAll('#grupoProductosCapsulas .capsule-btn.active'))
                         .map(b => b.getAttribute('data-prod'));
    const inputProds = document.getElementById('editFull_prods');
    if (inputProds) inputProds.value = activas.join('-') || 'NINGUNO';
}

function abrirModalEditarCompleto(op) {
    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val !== undefined && val !== null ? val : ''; };
    
    setVal('editFull_id', op.id);
    setVal('editFull_nombre', op.nombre || '');
    setVal('editFull_ingreso', op.fecha_alta !== '--' ? op.fecha_alta : '');
    setVal('editFull_nac', op.fecha_nacimiento !== '--' ? op.fecha_nacimiento : '');
    setVal('editFull_expDesde', op.experiencia_desde !== '--' ? op.experiencia_desde : '');
    setVal('editFull_noEmp', op.no_empleado !== '--' ? op.no_empleado : '');
    setVal('editFull_tipoUnidad', op.tipo_unidad || 'FULL');
    setVal('editFull_tel', op.tel || '');
    setVal('editFull_tipoLic', op.tipo_licencia !== '--' ? op.tipo_licencia : 'E');
    setVal('editFull_noLic', op.no_licencia !== '--' ? op.no_licencia : '');
    setVal('editFull_lic', op.lic !== '--' ? op.lic : '');
    setVal('editFull_med', op.med !== '--' ? op.med : '');
    setVal('editFull_cryo', op.liberacion_cryo !== '--' ? op.liberacion_cryo : '');
    setVal('editFull_imp', op.imp !== '--' ? op.imp : '');
    setVal('editFull_imei', op.imei !== '--' ? op.imei : '');

    setVal('editFull_libOp', op.liberado_operativamente || 'CLIENTES');
    setVal('editFull_esquema', op.esquema || 'Arrastre');

    const prods = (op.productos_descarga || 'LIN-LOX-LAR').toUpperCase();
    document.querySelectorAll('#grupoProductosCapsulas .capsule-btn').forEach(b => {
        const p = b.getAttribute('data-prod');
        if (prods.includes(p)) b.classList.add('active');
        else b.classList.remove('active');
    });
    actualizarProductosSeleccionados();

    const modal = document.getElementById('modalEditarCompleto');
    if (modal) modal.style.display = 'flex';
}

async function guardarEdicionCompleta(e) {
    e.preventDefault();
    const formData = new FormData();
    const getVal = (id, def = 'N/A') => document.getElementById(id)?.value || def;

    formData.append('id', getVal('editFull_id'));
    formData.append('nombre', getVal('editFull_nombre'));
    formData.append('fecha_alta', getVal('editFull_ingreso'));
    formData.append('fecha_nacimiento', getVal('editFull_nac'));
    formData.append('experiencia_desde', getVal('editFull_expDesde'));
    formData.append('no_empleado', getVal('editFull_noEmp'));
    formData.append('tel', getVal('editFull_tel'));
    formData.append('tipo_licencia', getVal('editFull_tipoLic', 'E'));
    formData.append('no_licencia', getVal('editFull_noLic'));
    formData.append('lic', getVal('editFull_lic'));
    formData.append('med', getVal('editFull_med'));
    formData.append('tipo_unidad', getVal('editFull_tipoUnidad', 'FULL'));
    formData.append('liberacion_cryo', getVal('editFull_cryo'));
    formData.append('liberado_operativamente', getVal('editFull_libOp', 'CLIENTES'));
    formData.append('productos_descarga', getVal('editFull_prods', 'LIN-LOX-LAR'));
    formData.append('esquema', getVal('editFull_esquema', 'Arrastre'));
    formData.append('imp', getVal('editFull_imp'));
    formData.append('imei', getVal('editFull_imei'));

    try {
        const res = await fetch('/api/actualizar_expediente', { method: 'POST', body: formData });
        if (res.ok) {
            showToast("✅ Operador actualizado", "success");
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast("Error al guardar cambios", "warning");
        }
    } catch(e) {
        showToast("Error de conexión con el servidor", "warning");
    }
}

// 7. GESTIÓN DE BAJAS Y DISPOSITIVOS
function confirmarBaja(id, nombre) { 
    const elNom = document.getElementById('bajaNombreVisual');
    const elId = document.getElementById('bajaIdOculto');
    if (elNom) elNom.innerText = nombre; 
    if (elId) elId.value = id; 
    const modal = document.getElementById('modalBajaGlobal');
    if (modal) modal.style.display = 'flex'; 
}

async function ejecutarBajaFinal() {
    const id = document.getElementById('bajaIdOculto')?.value; 
    const nombre = document.getElementById('bajaNombreVisual')?.innerText; 
    const modal = document.getElementById('modalBajaGlobal');
    if (modal) modal.style.display = 'none';

    try {
        const res = await fetch('/api/baja_operador', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({id: id}) 
        }); 
        if (res.ok) { 
            showToast(`🗑️ ${nombre} archivado en bajas`, "success"); 
            setTimeout(() => window.location.reload(), 1200); 
        } else {
            showToast("Error al procesar la baja", "warning");
        }
    } catch(e) {
        showToast("Error de conexión", "warning");
    }
}

async function reactivarOperador(id, nombre) {
    if (confirm(`¿Deseas reactivar al operador ${nombre} a la plantilla activa?`)) {
        try {
            const res = await fetch('/api/reactivar_operador', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({id: id}) 
            });
            if (res.ok) { 
                showToast(`♻️ ${nombre} reactivado con éxito`, "success"); 
                setTimeout(() => window.location.reload(), 1200); 
            }
        } catch(e) {
            showToast("Error de conexión", "warning");
        }
    }
}

async function liberarDispositivo() {
    const id = document.getElementById('expIdBD')?.value;
    if (confirm("¿Seguro que deseas liberar el teléfono del operador?")) {
        try {
            const res = await fetch('/api/liberar_dispositivo', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({id: id}) 
            });
            if (res.ok) showToast("✅ Celular liberado", "success");
        } catch(e) {
            showToast("Error de conexión", "warning");
        }
    }
}

async function generarPIN() {
    const id = document.getElementById('expIdBD')?.value;
    try {
        const res = await fetch('/api/generar_pin', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({id: id}) 
        });
        if (res.ok) { 
            const data = await res.json();
            alert("🚨 PIN TEMPORAL (15 MIN):\n\n" + data.pin);
        }
    } catch(e) {
        showToast("Error de conexión al generar PIN", "warning");
    }
}

// 8. CARGA MASIVA DE EXCEL CON SHEETJS
function abrirModalCargaMasiva() {
    const input = document.getElementById('excel-input');
    const dropzone = document.getElementById('excel-dropzone');
    const loading = document.getElementById('excel-loading');
    if (input) input.value = "";
    if (dropzone) dropzone.style.display = 'block';
    if (loading) loading.style.display = 'none';
    const modal = document.getElementById('modalCargaMasiva');
    if (modal) modal.style.display = 'flex';
}

function procesarArchivoExcel(input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    const dropzone = document.getElementById('excel-dropzone');
    const loading = document.getElementById('excel-loading');
    if (dropzone) dropzone.style.display = 'none'; 
    if (loading) loading.style.display = 'block';

    const reader = new FileReader();
    reader.onload = async function(e) {
        try {
            const data = new Uint8Array(e.target.result);
            const workbook = XLSX.read(data, {type: 'array', cellDates: true});
            let sheetName = workbook.SheetNames.find(s => s.toLowerCase().includes('plantilla')) || workbook.SheetNames[0];
            const sheet = workbook.Sheets[sheetName];
            const rawJson = XLSX.utils.sheet_to_json(sheet, {header: 1, raw: false, dateNF: 'yyyy-mm-dd'});
            
            let headerIdx = -1;
            for (let i = 0; i < Math.min(10, rawJson.length); i++) { 
                if (rawJson[i] && rawJson[i].some(cell => typeof cell === 'string' && cell.includes("No. Empleado"))) { 
                    headerIdx = i; 
                    break; 
                } 
            }
            if (headerIdx === -1) { 
                alert("❌ Formato inválido: Falta columna 'No. Empleado'."); 
                abrirModalCargaMasiva(); 
                return; 
            }

            const jsonFinal = XLSX.utils.sheet_to_json(sheet, {range: headerIdx, raw: false, dateNF: 'yyyy-mm-dd'});
            const operadoresMapeados = jsonFinal.map(row => ({
                no_empleado: row["No. Empleado"] || 'N/A', 
                nombre: row["CONDUCTOR"] || '', 
                estatus: row["ESTATUS"] || 'Activo',
                base: row["BASE"] || 'San Luis Potosí',
                fecha_alta: row["FECHA DE \r\nINGRESO"] || row["FECHA DE \nINGRESO"] || 'N/A', 
                fecha_nacimiento: row["FECHA DE NACIMIENTO"] || 'N/A',
                edad: row["EDAD\r\n(AÑOS)"] || row["EDAD\n(AÑOS)"] || 'N/A', 
                tipo_licencia: row["TIPO DE LICENCIA"] || 'N/A',
                vigencia_licencia: row["FECHA DE VENCIMIENTO DE LICENCIA"] || 'N/A', 
                no_licencia: row["NO. LICENCIA"] || 'N/A',
                vigencia_medica: row["FECHA DE APTITUD PSICOFISICA"] || 'N/A', 
                liberacion_cryo: row["LIBERACIÓN POR \r\nCRYOINFRA"] || row["LIBERACIÓN POR \nCRYOINFRA"] || 'N/A',
                productos_descarga: row["PRODUCTOS\r\nQUE DESCARGA"] || row["PRODUCTOS\nQUE DESCARGA"] || 'N/A',
                liberado_operativamente: row["LIBERADO OPERATIVAMENTE EN:"] || 'N/A',
                experiencia_desde: row["EXPERIENCIA\r\nEN MANEJO DESDE"] || row["EXPERIENCIA\nEN MANEJO DESDE"] || 'N/A',
                tipo_unidad: row["LIBERADO EN TIPO DE UNIDAD"] || 'FULL', 
                telefono_red: row["TELÉFONO CELULAR DE CONTACTO"] || 'N/A'
            })).filter(op => op.nombre.trim() !== '' && op.no_empleado !== 'N/A');

            const res = await fetch('/api/carga_masiva_rh', { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify(operadoresMapeados) 
            });
            const result = await res.json();
            
            if (res.ok) { 
                showToast(`✅ Matriz Procesada: ${result.actualizados} Actualizados | ${result.nuevos} Nuevos`, "success"); 
                const modal = document.getElementById('modalCargaMasiva');
                if (modal) modal.style.display = 'none'; 
                setTimeout(() => window.location.reload(), 2000);
            }
        } catch (error) { 
            alert("❌ Error al procesar el archivo Excel."); 
            abrirModalCargaMasiva(); 
        }
    };
    reader.readAsArrayBuffer(file);
}

// 9. ALTA MANUAL DE NUEVO INGRESO
function abrirModalAlta() { 
    const inputIngreso = document.getElementById('alta_ingreso');
    if (inputIngreso) inputIngreso.value = new Date().toISOString().split('T')[0];
    const modal = document.getElementById('modalAlta');
    if (modal) modal.style.display = 'flex'; 
}

function toggleAltaCapsula(btn) {
    btn.classList.toggle('active');
    const activas = Array.from(document.querySelectorAll('#grupoAltaProductosCapsulas .capsule-btn.active'))
                         .map(b => b.getAttribute('data-prod'));
    const inputProds = document.getElementById('alta_prods');
    if (inputProds) inputProds.value = activas.join('-') || 'NINGUNO';
    
    const tieneCryo = activas.some(p => ['LIN', 'LOX', 'LAR'].includes(p));
    const caja = document.getElementById('cajaAltaBloqueCriogenico');
    if (caja) caja.style.display = tieneCryo ? 'block' : 'none';
}

function seleccionarAltaRol(btn, valor) {
    document.querySelectorAll('#grupoAltaRolOperativo .capsule-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const elLib = document.getElementById('alta_libOp');
    if (elLib) elLib.value = valor;
    evaluarCascadaAlta();
}

function evaluarCascadaAlta() {
    const rol = document.getElementById('alta_libOp')?.value;
    const prodBase = document.getElementById('alta_producto_base')?.value;
    const cajaProd = document.getElementById('cajaAltaProductoBase');
    const cajaBloque = document.getElementById('cajaAltaBloqueCriogenico');

    if (rol === 'MOVEDOR' || rol === 'INSTRUCTOR') {
        if (cajaProd) cajaProd.style.display = 'none';
        if (cajaBloque) cajaBloque.style.display = 'none';
    } else {
        if (cajaProd) cajaProd.style.display = 'block';
        if (prodBase === 'CO2') {
            if (cajaBloque) cajaBloque.style.display = 'none';
        } else {
            if (cajaBloque) cajaBloque.style.display = 'block';
        }
    }
}

function seleccionarAltaEsquema(btn, valor) {
    document.querySelectorAll('#grupoAltaEsquemaCapsulas .capsule-btn').forEach(b => b.classList.remove('active-orange'));
    btn.classList.add('active-orange');
    const elEsq = document.getElementById('alta_esquema');
    if (elEsq) elEsq.value = valor;
}

async function guardarAltaCompleta(e) {
    e.preventDefault();
    const rolOp = document.getElementById('alta_libOp')?.value || 'OPERADOR';
    const prodBase = document.getElementById('alta_producto_base')?.value || 'NITROGENO';
    const esquemaElegido = document.getElementById('alta_esquema')?.value || '1. Tercias';

    let productoFinal = 'NITROGENO';
    let esquemaFinal = '1. Tercias';

    if (rolOp === 'MOVEDOR' || rolOp === 'INSTRUCTOR') {
        productoFinal = 'VARIOS';
        esquemaFinal = 'Varios';
    } else if (prodBase === 'CO2') {
        productoFinal = 'CO2';
        esquemaFinal = 'CO2';
    } else {
        productoFinal = prodBase;
        esquemaFinal = esquemaElegido;
    }

    const formData = new FormData();
    const getVal = (id, def = 'N/A') => document.getElementById(id)?.value || def;

    formData.append('no_empleado', getVal('alta_noEmp'));
    formData.append('nombre', getVal('alta_nombre'));
    formData.append('fecha_alta', getVal('alta_ingreso'));
    formData.append('fecha_nacimiento', getVal('alta_nac'));
    formData.append('tel', getVal('alta_tel'));
    formData.append('tipo_licencia', getVal('alta_tipoLic', 'E'));
    formData.append('no_licencia', getVal('alta_noLic'));
    formData.append('lic', getVal('alta_vigLic'));
    formData.append('med', getVal('alta_vigMed'));
    formData.append('liberacion_cryo', getVal('alta_libCryo'));
    formData.append('tipo_unidad', getVal('alta_tipoUnidad', 'FULL'));
    formData.append('experiencia_desde', getVal('alta_expDesde'));
    
    formData.append('productos_descarga', getVal('alta_prods', 'LIN-LOX-LAR'));
    formData.append('liberado_operativamente', rolOp);
    formData.append('producto', productoFinal);
    formData.append('esquema', esquemaFinal);

    formData.append('imp', getVal('alta_imp'));
    formData.append('imei', getVal('alta_imei'));

    const fotoFile = document.getElementById('alta_foto')?.files[0];
    if (fotoFile) formData.append('foto_perfil', fotoFile);

    try {
        const res = await fetch('/api/agregar_operador', { method: 'POST', body: formData });
        if (res.ok) {
            showToast("✅ Operador agregado y asignado a su bloque", "success");
            const modal = document.getElementById('modalAlta');
            if (modal) modal.style.display = 'none';
            setTimeout(() => window.location.reload(), 1200);
        } else {
            showToast("Error al dar de alta el operador", "warning");
        }
    } catch(e) {
        showToast("Error de conexión", "warning");
    }
}