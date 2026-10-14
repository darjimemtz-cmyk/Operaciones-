/* ========================================================
   GRUPO FNG - MÓDULO SÁBANA OPERATIVA Y LOGÍSTICA
   Pincel rápido, Drag & Drop (Sortable), Coberturas y PDF
   ======================================================== */

let currId = null;
let currFch = null;
let opPDFSeleccionado = null;
let cobOpSeleccionado = null;

let modoPincelActivo = false;
let estatusPincelActual = 'DE';

let modoOrdenActivo = false;
let instanciasSortable = [];

// Getters seguros de datos inyectados
function getOperadoresBackend() {
    return window.SABANA_OPERADORES || [];
}
function getUserRole() {
    return window.USER_ROL || '';
}
function getHoyStr() {
    return window.HOY_STR || new Date().toISOString().split('T')[0];
}

// 1. INICIALIZACIÓN Y EVENTOS DE VENTANA
window.addEventListener('DOMContentLoaded', () => {
    // Cerrar buscador expansible al dar clic fuera
    window.addEventListener('click', function(e) {
        const bar = document.getElementById('searchBarContainer');
        const input = document.getElementById('buscadorLogistica');
        if (bar && !bar.contains(e.target) && input && input.value.trim() === '') {
            bar.classList.remove('active');
        }
    });
});

// 2. BUSCADOR EXPANSIBLE SLIM
function expandirBuscador() {
    const bar = document.getElementById('searchBarContainer');
    const input = document.getElementById('buscadorLogistica');
    if (bar && !bar.classList.contains('active')) {
        bar.classList.add('active');
        if (input) input.focus();
    }
}

function limpiarYColapsarBuscador(e) {
    if (e) e.stopPropagation();
    const input = document.getElementById('buscadorLogistica');
    const bar = document.getElementById('searchBarContainer');
    
    if (input) {
        input.value = '';
        input.blur();
    }
    if (bar) bar.classList.remove('active');
    
    if (typeof buscadorGlobal === 'function') {
        buscadorGlobal('buscadorLogistica', '.glass-panel table tbody tr');
    }
}

// 3. EDICIÓN RÁPIDA DE RH DESDE LOGÍSTICA
function evaluarCascadaRH() {
    const rolOp = document.getElementById('rhRolOp')?.value;
    const producto = document.getElementById('rhProducto')?.value;
    const contProd = document.getElementById('contenedorProducto');
    const contBloque = document.getElementById('contenedorBloque');

    if (rolOp === 'MOVEDOR' || rolOp === 'INSTRUCTOR') {
        if (contProd) contProd.style.display = 'none';
        if (contBloque) contBloque.style.display = 'none';
    } else {
        if (contProd) contProd.style.display = 'block';
        if (producto === 'CO2') {
            if (contBloque) contBloque.style.display = 'none';
        } else {
            if (contBloque) contBloque.style.display = 'block';
        }
    }
}

function abrirModalRHRapido(id, nombre) {
    const lista = getOperadoresBackend();
    const op = lista.find(o => o.id === id);
    
    const elId = document.getElementById('rhOpId');
    const elName = document.getElementById('rhOpName');
    if (elId) elId.value = id;
    if (elName) elName.innerText = nombre;

    if (op) {
        const elRolOp = document.getElementById('rhRolOp');
        if (elRolOp) {
            if (op.esquema === 'Varios' && (!op.producto || op.producto === 'VARIOS')) {
                elRolOp.value = 'MOVEDOR';
            } else {
                elRolOp.value = 'OPERADOR';
            }
        }

        const elProd = document.getElementById('rhProducto');
        if (elProd) elProd.value = op.producto || 'NITROGENO';
        
        const elEsq = document.getElementById('rhEsquema');
        if (elEsq) {
            const esquemaActual = (op.esquema || '').toLowerCase();
            if (esquemaActual.includes('tercia')) {
                elEsq.value = '1. Tercias';
            } else if (esquemaActual.includes('crio')) {
                elEsq.value = '2. Criogenicos';
            } else if (esquemaActual.includes('arrastre')) {
                elEsq.value = '3. Arrastre';
            } else {
                elEsq.value = '1. Tercias';
            }
        }

        const elJor = document.getElementById('rhJornada');
        if (elJor) {
            elJor.value = (op.tipo_jornada && op.tipo_jornada !== '8-1-8-1-8-6') ? op.tipo_jornada : 'Variable';
        }

        const elAncla = document.getElementById('rhFechaAncla');
        if (elAncla) {
            elAncla.value = (op.fecha_ancla && op.fecha_ancla !== 'N/A') ? op.fecha_ancla : '';
        }
    }

    evaluarCascadaRH();
    const modal = document.getElementById('modalRHRapido');
    if (modal) modal.style.display = 'flex';
}

async function guardarRHRapido() {
    const id = document.getElementById('rhOpId')?.value;
    const rolOp = document.getElementById('rhRolOp')?.value;
    const producto = document.getElementById('rhProducto')?.value;
    const esquema = document.getElementById('rhEsquema')?.value;
    const jornada = document.getElementById('rhJornada')?.value;
    const anclaInput = document.getElementById('rhFechaAncla')?.value;

    if (jornada !== 'Variable' && !anclaInput) {
        showToast("⚠️ Para esquemas con ciclo debes seleccionar una Fecha Ancla.", "warning");
        return;
    }

    const payload = {
        operador_id: id,
        rol_op: rolOp,
        producto: (rolOp === 'OPERADOR') ? producto : 'VARIOS',
        esquema: (rolOp === 'OPERADOR') ? ((producto === 'CO2') ? 'CO2' : esquema) : 'Varios',
        patron: jornada,
        fecha_ancla: anclaInput || 'N/A'
    };

    try {
        const res = await fetch('/api/redibujar_rol', {
            method: 'POST', 
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            const modal = document.getElementById('modalRHRapido');
            if (modal) modal.style.display = 'none';
            showToast("✅ Datos actualizados correctamente", "success");
            setTimeout(() => window.location.reload(), 1200);
        } else {
            const data = await res.json();
            showToast(data.msg || "⚠️ Acción no autorizada.", "warning");
        }
    } catch (e) {
        showToast("Error de conexión con el servidor", "warning");
    }
}

// 4. MODO ASIGNAR ROL RÁPIDO (PINCEL)
function toggleModoPincel() {
    modoPincelActivo = !modoPincelActivo;
    const btn = document.getElementById('btnModoPincel');
    const txt = document.getElementById('txtBtnPincel');
    const paleta = document.getElementById('paletaPincel');

    if (modoPincelActivo) {
        if (modoOrdenActivo) toggleModoReordenar();
        if (btn) {
            btn.style.background = 'var(--fng-orange)';
            btn.style.color = '#ffffff';
        }
        if (txt) txt.innerText = 'Listo / Salir';
        if (paleta) paleta.style.display = 'inline-flex';
        document.body.classList.add('modo-pincel-activo');
        showToast("🎨 Modo Asignar Rol activado: Toca las celdas para pintar directo.", "info");
    } else {
        if (btn) {
            btn.style.background = '#e2e8f0';
            btn.style.color = 'var(--fng-blue)';
        }
        if (txt) txt.innerText = 'Asignar Rol';
        if (paleta) paleta.style.display = 'none';
        document.body.classList.remove('modo-pincel-activo');
        showToast("Modo normal restaurado", "success");
    }
}

function seleccionarPildora(estatus, elementoBtn) {
    estatusPincelActual = estatus;
    document.querySelectorAll('.pildora-estatus').forEach(p => p.classList.remove('active'));
    if (elementoBtn) elementoBtn.classList.add('active');
}

function manejarClicCelda(id, nom, f, est, celdaElem) {
    if (modoPincelActivo) {
        pintarCeldaSilenciosa(id, f, celdaElem);
    } else {
        abrirEditor(id, nom, f, est);
    }
}

async function pintarCeldaSilenciosa(opId, fechaStr, celdaElem) {
    const hoy = getHoyStr();
    const userRole = getUserRole();
    if (fechaStr < hoy && !['jefe_op', 'super_usuario'].includes(userRole)) {
        showToast("⚠️ Los días pasados están bloqueados", "warning");
        return;
    }

    const estatusNuevo = estatusPincelActual;
    const spanInterno = celdaElem.querySelector('span');
    const estatusAnterior = spanInterno ? spanInterno.innerText : '';
    const clasesAnteriores = celdaElem.className;

    // Optimistic UI: actualización visual inmediata
    celdaElem.className = celdaElem.className.replace(/bg-[A-Za-z0-9-]+/g, '') + ` bg-${estatusNuevo}`;
    if (spanInterno) {
        spanInterno.innerText = estatusNuevo.startsWith('TR') ? '' : estatusNuevo;
        spanInterno.className = `status-${estatusNuevo}`;
    }

    try {
        const res = await fetch('/api/actualizar_turno', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                operador_id: opId,
                fecha: fechaStr,
                fecha_fin: fechaStr,
                estatus_nuevo: estatusNuevo
            })
        });

        if (!res.ok) {
            celdaElem.className = clasesAnteriores;
            if (spanInterno) spanInterno.innerText = estatusAnterior;
            const data = await res.json();
            showToast(data.msg || "Error al actualizar", "warning");
        }
    } catch (err) {
        celdaElem.className = clasesAnteriores;
        if (spanInterno) spanInterno.innerText = estatusAnterior;
        showToast("Error de conexión al servidor", "warning");
    }
}

// 5. MODAL DE EDICIÓN CONVENCIONAL DE TURNO
function abrirEditor(id, nom, f, est) { 
    const hoy = getHoyStr();
    const userRole = getUserRole();
    if (f < hoy && !['jefe_op', 'super_usuario'].includes(userRole)) {
        showToast("⚠️ Los días pasados están bloqueados para edición", "warning");
        return;
    }
    currId = id; 
    currFch = f; 
    
    const elName = document.getElementById('modalOpName');
    if (elName) elName.innerText = `${nom} | Inicia: ${f}`;
    
    const elSel = document.getElementById('selectEstatus');
    if (elSel) elSel.value = (!est || est.startsWith('TR')) ? 'TR' : est; 
    
    const inputFechaFin = document.getElementById('fechaFinRango');
    if (inputFechaFin) {
        inputFechaFin.value = '';
        inputFechaFin.min = (f < hoy && ['jefe_op', 'super_usuario'].includes(userRole)) ? f : (f < hoy ? hoy : f);
    }
    
    const modal = document.getElementById('modalEditor');
    if (modal) modal.style.display = 'flex'; 
}

async function guardarTurno() {
    const payload = {
        operador_id: currId, 
        fecha: currFch, 
        fecha_fin: document.getElementById('fechaFinRango')?.value,
        estatus_nuevo: document.getElementById('selectEstatus')?.value
    };

    const userRole = getUserRole();
    const esDirecto = ['jefe_op', 'aux_dot', 'super_usuario'].includes(userRole);
    
    try {
        const res = await fetch(esDirecto ? '/api/actualizar_turno' : '/api/solicitar_turno', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify(payload)
        });

        if (res.ok) { 
            const modal = document.getElementById('modalEditor');
            if (modal) modal.style.display = 'none'; 
            showToast(!esDirecto ? "⏳ Solicitud de Rango Enviada" : "✅ Turnos Guardados", "success"); 
            setTimeout(() => window.location.reload(), 1500); 
        } else {
            const data = await res.json();
            showToast(data.msg || "⚠️ Acción Bloqueada", "warning"); 
        }
    } catch (e) {
        showToast("Error de conexión al guardar turno", "warning");
    }
}

// 6. GESTIÓN DE COBERTURAS
function filtrarCob() {
    const input = document.getElementById('cobBuscador');
    const texto = input ? input.value.toLowerCase() : ''; 
    const lineaElegida = document.getElementById('cobLinea')?.value;
    const cont = document.getElementById('listaCob'); 
    if (!cont) return;
    cont.innerHTML = '';
    
    if (texto.length < 1) { 
        cont.style.display = 'none'; 
        return; 
    }
    
    const lista = getOperadoresBackend();
    const coins = lista.filter(op => {
        if (!op.nombre.toLowerCase().includes(texto)) return false;
        let p_desc = (op.productos_descarga || '').toUpperCase();
        if (lineaElegida === 'CB-CO2') { 
            return p_desc.includes('CO2'); 
        } else { 
            return p_desc.includes('LIN') || p_desc.includes('LAR') || p_desc.includes('LOX') || p_desc.includes('ARGON') || p_desc.includes('NITROGENO') || p_desc.includes('OXIGENO'); 
        }
    });

    if (coins.length > 0) { 
        cont.style.display = 'block'; 
        coins.forEach(op => { 
            let div = document.createElement('div'); 
            div.className = 'autocomplete-item'; 
            div.innerHTML = `<b>${op.nombre}</b> <span style="font-size:10px; color:#10b981;">(Certificado)</span>`; 
            
            div.onclick = async () => { 
                cobOpSeleccionado = op.id; 
                document.getElementById('cobBuscador').value = op.nombre; 
                document.getElementById('cobOpId').value = op.id;
                cont.style.display = 'none'; 
                
                const fch = document.getElementById('cobFecha')?.value || new Date().toISOString().split('T')[0];
                let displayEl = document.getElementById('cobOpNameDisplay');
                if (displayEl) {
                    displayEl.innerHTML = `✅ <b>${op.nombre}</b><br><span style="font-size:12px; color:var(--text-muted);"><i class="fas fa-spinner fa-spin"></i> Consultando auditoría DOT...</span>`; 
                    displayEl.style.display = 'block'; 
                }
                
                try {
                    const resDOT = await fetch('/api/dot_status', { 
                        method: 'POST', 
                        headers: {'Content-Type': 'application/json'}, 
                        body: JSON.stringify({operador_id: op.id, fecha: fch})
                    });
                    if (resDOT.ok) {
                        const dataDOT = await resDOT.json();
                        let colorDisp = dataDOT.libres > 10 ? '#10b981' : (dataDOT.libres > 0 ? '#FF8C00' : '#ef4444');
                        if (displayEl) {
                            displayEl.innerHTML = `✅ <b>${op.nombre}</b><br><span style="font-size:13px; color:var(--text-muted);">⏱️ Horas Usadas: <b>${dataDOT.usadas}h</b> | <span style="color:${colorDisp};">🟢 Libres esta semana: <b>${dataDOT.libres}h</b></span></span>`;
                        }
                    }
                } catch(e) {}
            }; 
            cont.appendChild(div); 
        }); 
    } else { 
        cont.style.display = 'block'; 
        let div = document.createElement('div'); 
        div.className = 'autocomplete-item'; 
        div.style.color = '#ef4444';
        div.innerText = '❌ Ningún operador certificado coincide';
        cont.appendChild(div);
    }
}

function cerrarCob() { 
    const modal = document.getElementById('modalCobertura');
    if (modal) modal.style.display = 'none'; 
    const buscador = document.getElementById('cobBuscador');
    if (buscador) buscador.value = ''; 
    const display = document.getElementById('cobOpNameDisplay');
    if (display) display.style.display = 'none'; 
    cobOpSeleccionado = null; 
}

async function guardarCobertura() {
    if (!cobOpSeleccionado) { 
        showToast("⚠️ Busca y selecciona un operador", "warning"); 
        return; 
    }
    const fch = document.getElementById('cobFecha')?.value;
    if (!fch) { 
        showToast("⚠️ Selecciona el día de la cobertura", "warning"); 
        return; 
    }
    
    const payload = { 
        operador_id: cobOpSeleccionado, 
        fecha: fch, 
        estatus_nuevo: document.getElementById('cobLinea')?.value 
    };
    const userRole = getUserRole();
    const esDirectoCob = ['jefe_op', 'aux_dot', 'super_usuario'].includes(userRole);
    
    try {
        const res = await fetch(esDirectoCob ? '/api/actualizar_turno' : '/api/solicitar_turno', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            cerrarCob(); 
            showToast(!esDirectoCob ? "⏳ Solicitud Enviada" : "✅ Cobertura Asignada", "success"); 
            setTimeout(() => window.location.reload(), 1500); 
        } else {
            const data = await res.json();
            showToast(data.msg || "⚠️ Acción Bloqueada", "warning"); 
        }
    } catch(e) {
        showToast("Error de conexión al asignar cobertura", "warning");
    }
}

// 7. GENERACIÓN DE ROL MENSUAL EN PDF
function abrirModalPDF() { 
    const buscador = document.getElementById('buscadorOpPDF');
    if (buscador) buscador.value = ''; 
    const lista = document.getElementById('listaAutocompletado');
    if (lista) lista.style.display = 'none'; 
    const caja = document.getElementById('cajaDescarga');
    if (caja) caja.style.display = 'none'; 
    opPDFSeleccionado = null; 
    const modal = document.getElementById('modalGenerarPDF');
    if (modal) modal.style.display = 'flex'; 
}

function filtrarNombresPDF() {
    const input = document.getElementById('buscadorOpPDF');
    const texto = input ? input.value.toLowerCase() : ''; 
    const cont = document.getElementById('listaAutocompletado'); 
    if (!cont) return;
    cont.innerHTML = '';
    
    if (texto.length < 1) { 
        cont.style.display = 'none'; 
        return; 
    }
    
    const lista = getOperadoresBackend();
    const coins = lista.filter(op => op.nombre.toLowerCase().includes(texto));
    
    if (coins.length > 0) { 
        cont.style.display = 'block'; 
        coins.forEach(op => { 
            let div = document.createElement('div'); 
            div.className = 'autocomplete-item'; 
            div.innerText = op.nombre; 
            div.onclick = () => { 
                opPDFSeleccionado = op.id; 
                document.getElementById('buscadorOpPDF').value = op.nombre; 
                cont.style.display = 'none'; 
                document.getElementById('nombreElegido').innerText = op.nombre; 
                document.getElementById('cajaDescarga').style.display = 'block'; 
            }; 
            cont.appendChild(div); 
        }); 
    } else { 
        cont.style.display = 'none'; 
    }
}

async function descargarRol() {
    if (!opPDFSeleccionado) return; 
    showToast("⏳ Generando Archivo...", "warning");
    
    try {
        const res = await fetch('/api/obtener_rol_mes', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify({operador_id: opPDFSeleccionado}) 
        });
        
        if (res.ok) {
            const data = await res.json(); 
            document.getElementById('pdfNombre').innerText = data.operador; 
            document.getElementById('pdfLinea').innerText = data.linea; 
            document.getElementById('pdfMes').innerText = data.mes;
            
            const tbody = document.getElementById('pdfTablaBody'); 
            tbody.innerHTML = '';
            
            let fechaInicio = new Date(data.calendario[0].fecha + 'T00:00:00'); 
            let celdasVacias = fechaInicio.getDay() === 0 ? 6 : fechaInicio.getDay() - 1;
            let fila = document.createElement('tr'); 
            let c = 0;
            
            for (let i = 0; i < celdasVacias; i++) { 
                fila.innerHTML += `<td style="border:1px solid #cbd5e1; background:#f8fafc; height:80px; box-sizing: border-box;"></td>`; 
                c++; 
            }
            
            data.calendario.forEach(dia => {
                let colorTxt = '#002d5a'; 
                let bg = 'transparent';
                let txtMostrar = dia.estatus;

                if (dia.estatus.startsWith('TR')) {
                    txtMostrar = dia.estatus.replace('TR', '');
                    let num = parseInt(txtMostrar) || 1;
                    bg = '#ffffff';
                    if (num >= 8) colorTxt = '#b91c1c'; 
                    else if (num >= 6) colorTxt = '#ea580c';
                    else if (num >= 4) colorTxt = '#eab308';
                    else colorTxt = '#10b981';
                } else if (['FA','IN'].includes(dia.estatus)) {
                    colorTxt = '#be123c'; bg = '#fecdd3';
                } else if (dia.estatus === 'DE') {
                    colorTxt = '#7e22ce'; bg = '#f3e8ff';
                } else if (dia.estatus === 'VA') {
                    colorTxt = '#0369a1'; bg = '#e0f2fe';
                } else if (dia.estatus === 'PER') {
                    colorTxt = '#ffffff'; bg = '#a855f7';
                } else if (dia.estatus === 'CAP') {
                    colorTxt = '#047857'; bg = '#d1fae5';
                } else if (['MED','LIC'].includes(dia.estatus)) {
                    colorTxt = '#a16207'; bg = '#fef9c3';
                } else {
                    bg = '#f0f9ff';
                }
                
                fila.innerHTML += `<td style="border:1px solid #cbd5e1; height:80px; vertical-align:top; padding:8px; background:${bg}; box-sizing: border-box;">
                    <div style="font-size:12px; font-weight:bold; text-align:left; color:#64748b;">${dia.dia}</div>
                    <div style="text-align:center; margin-top:10px; font-size:18px; font-weight:900; color:${colorTxt};">${txtMostrar}</div>
                </td>`;
                
                c++; 
                if (c === 7) { 
                    tbody.appendChild(fila); 
                    fila = document.createElement('tr'); 
                    c = 0; 
                }
            });
            
            if (c > 0) { 
                for (let i = c; i < 7; i++) { 
                    fila.innerHTML += `<td style="border:1px solid #cbd5e1; background:#f8fafc; height:80px; box-sizing: border-box;"></td>`; 
                } 
                tbody.appendChild(fila); 
            }
            
            let element = document.getElementById('plantillaPDF');
            html2pdf().set({
                margin: 0.3,
                filename: `Rol_${data.operador}.pdf`,
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2, useCORS: true, letterRendering: true },
                jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
            }).from(element).save().then(() => { 
                const modal = document.getElementById('modalGenerarPDF');
                if (modal) modal.style.display = 'none'; 
                showToast("✅ PDF Descargado.", "success"); 
            });
        }
    } catch (e) {
        showToast("Error al generar PDF del rol", "warning");
    }
}

// 8. REORDENAMIENTO DE FILAS CON SORTABLEJS (DRAG & DROP)
function toggleModoReordenar() {
    modoOrdenActivo = !modoOrdenActivo;
    const btn = document.getElementById('btnModoOrden');
    const txt = document.getElementById('txtBtnOrden');
    const handles = document.querySelectorAll('.drag-handle');
    const tbodies = document.querySelectorAll('.tabla-bloque-sortable');

    if (modoOrdenActivo) {
        if (btn) {
            btn.classList.remove('btn-light');
            btn.classList.add('btn-primary');
            btn.style.background = 'var(--fng-orange)';
        }
        if (txt) txt.innerText = 'Listo / Guardar';
        handles.forEach(h => h.style.display = 'inline-block');
        document.body.classList.add('modo-orden-activo');

        tbodies.forEach(tbody => {
            const sortable = new Sortable(tbody, {
                animation: 150,
                handle: '.op-name-container',
                ghostClass: 'sortable-ghost',
                onEnd: async function () {
                    const filas = Array.from(tbody.querySelectorAll('tr[data-id]'));
                    const ordenIds = filas.map(f => parseInt(f.getAttribute('data-id')));

                    try {
                        const res = await fetch('/api/guardar_orden_operadores', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ orden_ids: ordenIds })
                        });
                        if (res.ok) {
                            showToast("Posición actualizada", "success");
                        }
                    } catch (err) {
                        showToast("Error de conexión al reordenar", "warning");
                    }
                }
            });
            instanciasSortable.push(sortable);
        });
        showToast("Modo reordenar activado. Arrastra a los operadores.", "info");

    } else {
        if (btn) {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-light');
            btn.style.background = '';
        }
        if (txt) txt.innerText = 'Reordenar';
        handles.forEach(h => h.style.display = 'none');
        document.body.classList.remove('modo-orden-activo');

        instanciasSortable.forEach(inst => inst.destroy());
        instanciasSortable = [];
        showToast("Orden guardado con éxito", "success");
    }
}