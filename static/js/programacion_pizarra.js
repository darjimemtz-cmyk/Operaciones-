/* ========================================================
   GRUPO FNG - MÓDULO PIZARRA DE DESPACHO (DISPATCH)
   Corte Operativo 08:15 AM, Historial, Escalas,
   Semáforos C/V, Importación y Exportación PDF
   ======================================================== */

let modoHistorialActivo = false;
let currentRowAccion = null;

// 1. FECHA LOCAL EXACTA RESPETANDO EL CORTE OPERATIVO DE LAS 08:15 AM
function getFechaOperativaHoy() {
    const d = new Date();
    if (d.getHours() < 8 || (d.getHours() === 8 && d.getMinutes() < 15)) {
        d.setDate(d.getDate() - 1);
    }
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const dia = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${dia}`;
}

// 2. INICIALIZACIÓN
window.addEventListener('DOMContentLoaded', () => {
    salirHistorial();
});

// 3. CONTROL DEL SELECTOR DE FECHA E HISTORIAL
async function cambiarFechaOperativa(fechaSeleccionada) {
    if (!fechaSeleccionada) return;
    const hoyOperativo = getFechaOperativaHoy();

    if (fechaSeleccionada >= hoyOperativo) {
        salirHistorial();
    } else {
        modoHistorialActivo = true;
        showToast("⏳ Consultando auditoría: " + fechaSeleccionada.split('-').reverse().join('/'), "warning");
        await cargarProgramacionBD(fechaSeleccionada);
        bloquearPizarraEnVivo(true);
    }
}

function salirHistorial() {
    modoHistorialActivo = false;
    const hoyOperativo = getFechaOperativaHoy();
    const inputFecha = document.getElementById('selectorFechaOperativa');
    
    if (inputFecha) {
        inputFecha.value = hoyOperativo;
        inputFecha.max = hoyOperativo;
    }

    bloquearPizarraEnVivo(false);
    cargarProgramacionBD(null);
}

async function cargarProgramacionBD(fechaConsulta = null) {
    const endpoint = fechaConsulta ? `/api/cargar_programacion?fecha=${fechaConsulta}` : '/api/cargar_programacion';
    try {
        const res = await fetch(endpoint);
        if (res.ok) {
            const json = await res.json();
            const data = json.data || {};
            
            ['LOX', 'LIN', 'LAR', 'CO2'].forEach(prod => {
                const tableId = `table-${prod.toLowerCase()}`;
                const tbody = document.querySelector(`#${tableId} tbody`);
                if (tbody) tbody.innerHTML = '';
                
                if (data[prod] && data[prod].length > 0) {
                    data[prod].forEach(viaje => agregarViajeGuardado(tableId, viaje));
                } else if (!modoHistorialActivo) {
                    agregarViajeNuevo(tableId);
                }
            });
        }
    } catch (e) {
        console.error("Error al cargar programación:", e);
    }
}

// 4. MODO EDICIÓN VS BLOQUEO DE FILA
function toggleEditarFila(btn) {
    if (modoHistorialActivo) return;
    const tr = btn.closest('tr');
    const icon = btn.querySelector('i');
    const estaBloqueada = tr.classList.contains('fila-bloqueada');
    
    if (estaBloqueada) {
        tr.classList.remove('fila-bloqueada');
        tr.classList.add('fila-editando');
        if (icon) icon.className = 'fas fa-check';
        btn.classList.add('editing');
        btn.title = 'Guardar y Bloquear Fila';
        showToast("✏️ Fila en modo edición", "warning");
    } else {
        tr.classList.remove('fila-editando');
        tr.classList.add('fila-bloqueada');
        if (icon) icon.className = 'fas fa-pencil-alt';
        btn.classList.remove('editing');
        btn.title = 'Editar Fila';
        guardarPizarra();
    }
}

// 5. INSERCIÓN DE VIAJES
function agregarViajeNuevo(tableId) {
    if (modoHistorialActivo) return;
    const tbody = document.querySelector(`#${tableId} tbody`); 
    if (!tbody) return;
    const numViajes = tbody.querySelectorAll('tr').length + 1;
    const hoy = getFechaOperativaHoy();

    const trHtml = `
        <tr class="fila-editando">
            <td><input type="text" class="cell-input" value="${numViajes}" style="font-weight:900; font-size:14px;"></td>
            <td><input type="text" class="cell-input"></td>
            <td><input type="text" class="cell-input"></td>
            <td><input type="text" class="cell-input"></td>
            <td><input type="text" class="cell-input text-left" list="listaOperadores" oninput="verificarDiaOperativo(this)" onblur="verificarDiaOperativo(this)"></td>
            <td><input type="time" class="cell-input"></td>
            <td><input type="text" class="cell-input" value="PROX"></td>
            <td><input type="text" class="cell-input" list="listaBases"></td>
            <td><input type="text" class="cell-input col-dia-laboral" readonly tabindex="-1" title="Campo automático protegido"></td>
            <td style="padding:0;"><button class="cv-indicator cv-gray" onclick="toggleCV(this)"></button></td>
            <td class="col-apilada col-cliente"><div class="escala-item"><input type="text" class="cell-input text-left" placeholder="Destino Principal" style="font-weight:800;"><button class="btn-row add" onclick="agregarEscala(this)" title="Añadir Escala"><i class="fas fa-plus-circle"></i></button></div></td>
            <td class="col-apilada col-dl"><div class="escala-item"><input type="text" class="cell-input"></div></td>
            <td class="col-apilada col-ubicacion"><div class="escala-item"><input type="text" class="cell-input text-left samsara-location"></div></td>
            <td class="col-apilada col-obs"><div class="escala-item"><input type="text" class="cell-input text-left" style="color: var(--fng-blue);"></div></td>
            <td class="col-apilada col-fecha"><div class="escala-item"><input type="date" class="cell-input" value="${hoy}" oninput="verificarDiaOperativo(this)" onblur="verificarDiaOperativo(this)"></div></td>
            <td class="col-apilada col-factura"><div class="escala-item"><input type="text" class="cell-input" value="PENDIENTE" style="color:#f59e0b; font-weight:800;"></div></td>
            
            <td class="col-acciones" style="text-align: center; vertical-align: middle; white-space: nowrap;">
                <button class="btn-row btn-edit-row editing" onclick="toggleEditarFila(this)" title="Guardar y Bloquear Fila"><i class="fas fa-check"></i></button>
                <button class="btn-row pending" onclick="confirmarPendiente(this)" title="Alerta Nocturna / Pendiente"><i class="fas fa-clock"></i></button>
                <button class="btn-row action-menu" onclick="abrirModalAccionViaje(this)" title="Opciones del Viaje"><i class="fas fa-cog"></i></button>
            </td>
        </tr>
    `;
    tbody.insertAdjacentHTML('beforeend', trHtml);
}

function agregarViajeGuardado(tableId, v) {
    const tbody = document.querySelector(`#${tableId} tbody`); 
    if (!tbody) return;
    let escalasHtml_cliente = '', escalasHtml_dl = '', escalasHtml_ubi = '', escalasHtml_obs = '', escalasHtml_fch = '', escalasHtml_fac = '';
    
    (v.escalas || []).forEach((esc, idx) => {
        const btnAddMinus = idx === 0 
            ? `<button class="btn-row add" onclick="agregarEscala(this)" title="Añadir Escala"><i class="fas fa-plus-circle"></i></button>`
            : `<button class="btn-row minus" onclick="eliminarEscala(this)" title="Quitar Escala"><i class="fas fa-minus-circle"></i></button>`;
        
        escalasHtml_cliente += `<div class="escala-item"><input type="text" class="cell-input text-left" value="${esc.cliente || ''}" style="font-weight:800;">${btnAddMinus}</div>`;
        escalasHtml_dl += `<div class="escala-item"><input type="text" class="cell-input" value="${esc.dl || ''}"></div>`;
        escalasHtml_ubi += `<div class="escala-item"><input type="text" class="cell-input text-left samsara-location" value="${esc.ubicacion || ''}"></div>`;
        escalasHtml_obs += `<div class="escala-item"><input type="text" class="cell-input text-left" value="${esc.obs || ''}" style="color: var(--fng-blue);"></div>`;
        escalasHtml_fch += `<div class="escala-item"><input type="date" class="cell-input" value="${esc.fecha || ''}" oninput="verificarDiaOperativo(this)" onblur="verificarDiaOperativo(this)"></div>`;
        escalasHtml_fac += `<div class="escala-item"><input type="text" class="cell-input" value="${esc.factura || ''}" ${esc.factura === 'PENDIENTE' ? 'style="color:#f59e0b; font-weight:800;"' : ''}></div>`;
    });
    
    const trHtml = `
        <tr class="${v.isPending ? 'row-pending ' : ''}fila-bloqueada">
            <td><input type="text" class="cell-input" value="${v.num || ''}" style="font-weight:900; font-size:14px;"></td>
            <td><input type="text" class="cell-input" value="${v.tr || ''}"></td>
            <td><input type="text" class="cell-input" value="${v.pipa || ''}"></td>
            <td><input type="text" class="cell-input" value="${v.dly || ''}"></td>
            <td><input type="text" class="cell-input text-left" list="listaOperadores" value="${v.operador || ''}" oninput="verificarDiaOperativo(this)" onblur="verificarDiaOperativo(this)"></td>
            <td><input type="time" class="cell-input" value="${v.sprog || ''}"></td>
            <td><input type="text" class="cell-input" value="${v.tmpocond || ''}"></td>
            <td><input type="text" class="cell-input" list="listaBases" value="${v.cc || ''}"></td>
            <td><input type="text" class="cell-input col-dia-laboral" value="${v.dia || ''}" readonly tabindex="-1" title="Campo automático protegido"></td>
            <td style="padding:0;"><button class="${v.cv || 'cv-indicator cv-gray'}" onclick="toggleCV(this)"></button></td>
            <td class="col-apilada col-cliente">${escalasHtml_cliente}</td>
            <td class="col-apilada col-dl">${escalasHtml_dl}</td>
            <td class="col-apilada col-ubicacion">${escalasHtml_ubi}</td>
            <td class="col-apilada col-obs">${escalasHtml_obs}</td>
            <td class="col-apilada col-fecha">${escalasHtml_fch}</td>
            <td class="col-apilada col-factura">${escalasHtml_fac}</td>
            <td class="col-acciones" style="text-align: center; vertical-align: middle; white-space: nowrap;">
                <button class="btn-row btn-edit-row" onclick="toggleEditarFila(this)" title="Editar / Bloquear Fila"><i class="fas fa-pencil-alt"></i></button>
                <button class="btn-row pending" onclick="confirmarPendiente(this)" title="Alerta Nocturna / Pendiente"><i class="fas fa-clock"></i></button>
                <button class="btn-row action-menu" onclick="abrirModalAccionViaje(this)" title="Opciones del Viaje"><i class="fas fa-cog"></i></button>
            </td>
        </tr>
    `;
    tbody.insertAdjacentHTML('beforeend', trHtml);
}

// 6. BLOQUEO DE CONTROLES EN HISTORIAL
function bloquearPizarraEnVivo(bloquear) {
    const inputs = document.querySelectorAll('.prog-table input');
    const boxAsignar = document.querySelectorAll('.box-asignar-viaje');
    const colAcciones = document.querySelectorAll('.col-acciones');
    const botonesSumaResta = document.querySelectorAll('.btn-row.add, .btn-row.minus');
    const btnGuardarMaster = document.querySelector('.btn-guardar-live');
    const cvButtons = document.querySelectorAll('.cv-indicator');

    inputs.forEach(i => {
        if (bloquear) { i.setAttribute('readonly', 'true'); } 
        else { i.removeAttribute('readonly'); }
    });

    boxAsignar.forEach(b => b.style.display = bloquear ? 'none' : 'block');
    colAcciones.forEach(c => c.style.display = bloquear ? 'none' : '');
    botonesSumaResta.forEach(b => b.style.display = bloquear ? 'none' : 'inline-flex');
    cvButtons.forEach(b => b.style.pointerEvents = bloquear ? 'none' : 'auto');
    
    if (btnGuardarMaster) {
        btnGuardarMaster.style.display = bloquear ? 'none' : 'inline-flex';
    }
}

// 7. PERSISTENCIA DE LA PIZARRA COMPLETA
async function guardarPizarra() {
    if (modoHistorialActivo) return;

    const activeTab = document.querySelector('.product-tab[style*="display: block"]') || document.querySelector('#tab-lox');
    const productName = activeTab.id.replace('tab-', '').toUpperCase();
    const table = activeTab.querySelector('table');
    const rows = table.querySelectorAll('tbody tr');
    let dataToSave = [];
    
    rows.forEach(tr => {
        let rowData = extraerFilaViaje(tr);
        dataToSave.push(rowData);
    });
    
    try {
        const res = await fetch('/api/guardar_programacion', {
            method: 'POST', 
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({producto: productName, datos: dataToSave})
        });
        
        if (res.ok) { 
            showToast("✅ " + productName + " Guardado correctamente.", "success"); 
        } else { 
            showToast("⚠️ Error al guardar.", "warning"); 
        }
    } catch (e) {
        showToast("Error de conexión al guardar", "warning");
    }
}

// 8. NAVEGACIÓN ENTRE PRODUCTOS (DOCK SLIM)
function switchProductTab(tabId, btn) {
    document.querySelectorAll('.product-tab').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.mac-dock-btn').forEach(b => b.classList.remove('active'));
    
    const target = document.getElementById(tabId);
    if (target) target.style.display = 'block';
    if (btn) btn.classList.add('active');
    
    const tbody = document.querySelector(`#${tabId} tbody`);
    if (!modoHistorialActivo && tbody && tbody.children.length === 0) {
        agregarViajeNuevo(tabId.replace('tab-', 'table-'));
    }
}

// 9. GESTIÓN DE ACCIONES Y MODAL DE VIAJE
function abrirModalAccionViaje(btn) {
    if (modoHistorialActivo) return;
    currentRowAccion = btn.closest('tr');
    let num = currentRowAccion.cells[0].querySelector('input')?.value || '-';
    let op = currentRowAccion.cells[4].querySelector('input')?.value || 'Sin asignar';
    
    const detalleEl = document.getElementById('accionViajeDetalle');
    if (detalleEl) detalleEl.innerText = `Viaje #${num} • Operador: ${op}`;
    
    const modal = document.getElementById('modalAccionViaje');
    if (modal) modal.style.display = 'flex';
}

function cerrarModalAccion() {
    const modal = document.getElementById('modalAccionViaje');
    if (modal) modal.style.display = 'none';
    currentRowAccion = null;
}

function extraerFilaViaje(tr) {
    let rowData = {
        num: tr.cells[0].querySelector('input') ? tr.cells[0].querySelector('input').value : '',
        tr: tr.cells[1].querySelector('input') ? tr.cells[1].querySelector('input').value : '',
        pipa: tr.cells[2].querySelector('input') ? tr.cells[2].querySelector('input').value : '',
        dly: tr.cells[3].querySelector('input') ? tr.cells[3].querySelector('input').value : '',
        operador: tr.querySelector('input[list="listaOperadores"]') ? tr.querySelector('input[list="listaOperadores"]').value : '',
        sprog: tr.cells[5].querySelector('input') ? tr.cells[5].querySelector('input').value : '',
        tmpocond: tr.cells[6].querySelector('input') ? tr.cells[6].querySelector('input').value : '',
        cc: tr.querySelector('input[list="listaBases"]') ? tr.querySelector('input[list="listaBases"]').value : '',
        dia: tr.querySelector('.col-dia-laboral') ? tr.querySelector('.col-dia-laboral').value : '',
        cv: tr.querySelector('.cv-indicator') ? tr.querySelector('.cv-indicator').className : 'cv-indicator cv-gray',
        isPending: tr.classList.contains('row-pending'),
        escalas: []
    };
    
    const clientes = tr.querySelectorAll('.col-cliente input');
    const dls = tr.querySelectorAll('.col-dl input');
    const ubicaciones = tr.querySelectorAll('.col-ubicacion input');
    const obss = tr.querySelectorAll('.col-obs input');
    const fechas = tr.querySelectorAll('.col-fecha input');
    const facturas = tr.querySelectorAll('.col-factura input');
    
    for (let i = 0; i < clientes.length; i++) {
        rowData.escalas.push({
            cliente: clientes[i] ? clientes[i].value : '', 
            dl: dls[i] ? dls[i].value : '',
            ubicacion: ubicaciones[i] ? ubicaciones[i].value : '', 
            obs: obss[i] ? obss[i].value : '',
            fecha: fechas[i] ? fechas[i].value : '', 
            factura: facturas[i] ? facturas[i].value : ''
        });
    }
    return rowData;
}

async function finalizarViaje() {
    if (!currentRowAccion) return;
    const activeTab = document.querySelector('.product-tab[style*="display: block"]') || document.querySelector('#tab-lox');
    const payload = {
        producto: activeTab.id.replace('tab-', '').toUpperCase(),
        estatus: 'FINALIZADO',
        viaje: extraerFilaViaje(currentRowAccion)
    };
    try {
        const res = await fetch('/api/gestionar_viaje_pizarra', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify(payload) 
        });
        if (res.ok) {
            currentRowAccion.remove(); 
            cerrarModalAccion();
            showToast("✅ Viaje finalizado y archivado", "success");
        }
    } catch(e) {
        showToast("Error de conexión al finalizar viaje", "warning");
    }
}

async function cancelarViaje() {
    if (!currentRowAccion) return;
    let motivo = prompt("Motivo breve de la cancelación:");
    if (motivo !== null && motivo.trim() !== "") {
        const activeTab = document.querySelector('.product-tab[style*="display: block"]') || document.querySelector('#tab-lox');
        const payload = {
            producto: activeTab.id.replace('tab-', '').toUpperCase(),
            estatus: 'CANCELADO', 
            motivo: motivo,
            viaje: extraerFilaViaje(currentRowAccion)
        };
        try {
            const res = await fetch('/api/gestionar_viaje_pizarra', { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify(payload) 
            });
            if (res.ok) {
                currentRowAccion.remove();
                cerrarModalAccion();
                showToast("🔴 Viaje cancelado por incidencia", "warning");
            }
        } catch(e) {
            showToast("Error de conexión al cancelar viaje", "warning");
        }
    }
}

function confirmarPendiente(btn) {
    if (modoHistorialActivo) return;
    currentRowAccion = btn.closest('tr');
    let isPending = currentRowAccion.classList.contains('row-pending');
    
    const textoEl = document.getElementById('textoPendiente');
    const btnConfirm = document.getElementById('btnConfirmarPendiente');
    
    if (textoEl) {
        textoEl.innerText = isPending 
            ? "¿Reactivar viaje a estatus normal? La alerta visual se retirará de la pizarra." 
            : "¿Marcar este viaje como Pendiente / Guardia Nocturna? Se resaltará en azul.";
    }
    if (btnConfirm) btnConfirm.innerText = isPending ? "Quitar Alerta" : "Activar Alerta";
    
    const modal = document.getElementById('modalPendiente');
    if (modal) modal.style.display = 'flex';
}

function ejecutarPendiente() {
    if (currentRowAccion) {
        currentRowAccion.classList.toggle('row-pending');
    }
    const modal = document.getElementById('modalPendiente');
    if (modal) modal.style.display = 'none';
    guardarPizarra();
}

// 10. GENERACIÓN LIMPIA DE REPORTE PDF HORIZONTAL
function descargarPDFPizarraLimpio() {
    const activeTab = document.querySelector('.product-tab[style*="display: block"]') || document.querySelector('#tab-lox');
    const productName = activeTab.id.replace('tab-', '').toUpperCase();
    const rows = activeTab.querySelectorAll('tbody tr');
    
    const inputVal = document.getElementById('selectorFechaOperativa')?.value;
    const fchOperativa = inputVal ? inputVal.split('-').reverse().join('/') : new Date().toLocaleDateString('es-MX');
    
    const elFecha = document.getElementById('pdfProgFecha');
    const elLinea = document.getElementById('pdfProgLinea');
    if (elFecha) elFecha.innerText = fchOperativa;
    if (elLinea) elLinea.innerText = productName;
    
    const tbodyPDF = document.getElementById('plantillaPDFProgTablaBody');
    if (!tbodyPDF) return;
    tbodyPDF.innerHTML = '';
    
    rows.forEach(tr => {
        let isPending = tr.classList.contains('row-pending');
        let bgRow = isPending ? '#e0f2fe' : '#ffffff';
        
        let v_num = tr.cells[0].querySelector('input')?.value || '';
        let v_tr = tr.cells[1].querySelector('input')?.value || '';
        let v_pipa = tr.cells[2].querySelector('input')?.value || '';
        let v_dly = tr.cells[3].querySelector('input')?.value || '';
        let v_op = tr.cells[4].querySelector('input')?.value || '';
        let v_sprog = tr.cells[5].querySelector('input')?.value || '';
        let v_cc = tr.cells[7].querySelector('input')?.value || '';
        
        let cvClass = tr.querySelector('.cv-indicator')?.className || '';
        let cvText = cvClass.includes('green') ? 'V' : (cvClass.includes('red') ? 'C' : '');
        let cvBg = cvClass.includes('green') ? '#10b981' : (cvClass.includes('red') ? '#ef4444' : 'transparent');
        
        let escs_cli = Array.from(tr.querySelectorAll('.col-cliente input')).map(i => i.value).join('<br>');
        let escs_dl = Array.from(tr.querySelectorAll('.col-dl input')).map(i => i.value).join('<br>');
        let escs_ubi = Array.from(tr.querySelectorAll('.col-ubicacion input')).map(i => i.value).join('<br>');
        let escs_obs = Array.from(tr.querySelectorAll('.col-obs input')).map(i => i.value).join('<br>');
        let escs_fac = Array.from(tr.querySelectorAll('.col-factura input')).map(i => i.value).join('<br>');
        
        let html = `
            <tr style="background-color: ${bgRow};">
                <td style="padding: 6px; border: 1px solid #cbd5e1;"><b>${v_num}</b></td>
                <td style="padding: 6px; border: 1px solid #cbd5e1;">${v_tr}</td>
                <td style="padding: 6px; border: 1px solid #cbd5e1;">${v_pipa}</td>
                <td style="padding: 6px; border: 1px solid #cbd5e1;">${v_dly}</td>
                <td style="padding: 6px; border: 1px solid #cbd5e1; text-align: left;"><b>${v_op}</b></td>
                <td style="padding: 6px; border: 1px solid #cbd5e1;">${v_sprog}</td>
                <td style="padding: 6px; border: 1px solid #cbd5e1;">${v_cc}</td>
                <td style="padding: 6px; border: 1px solid #cbd5e1; background-color:${cvBg}; color:white; font-weight:bold;">${cvText}</td>
                <td style="padding: 6px; border: 1px solid #cbd5e1; text-align: left; font-weight:bold;">${escs_cli}</td>
                <td style="padding: 6px; border: 1px solid #cbd5e1;">${escs_dl}</td>
                <td style="padding: 6px; border: 1px solid #cbd5e1; text-align: left;">${escs_ubi}</td>
                <td style="padding: 6px; border: 1px solid #cbd5e1; text-align: left; color:#002d5a;">${escs_obs}</td>
                <td style="padding: 6px; border: 1px solid #cbd5e1; font-weight:bold; color:#d97706;">${escs_fac}</td>
            </tr>
        `;
        tbodyPDF.insertAdjacentHTML('beforeend', html);
    });

    showToast("⏳ Generando PDF Limpio...", "warning");
    
    const element = document.getElementById('plantillaPDFProg');
    html2pdf().set({
        margin: 0.3,
        filename: `Pizarra_${productName}_${fchOperativa.replace(/\//g, '-')}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, letterRendering: true },
        jsPDF: { unit: 'in', format: 'legal', orientation: 'landscape' }
    }).from(element).save().then(() => {
        showToast("✅ Reporte Exportado Correctamente.", "success");
    });
}

// 11. VALIDACIÓN DINÁMICA DE DÍAS OPERATIVOS Y ESCALAS
async function verificarDiaOperativo(el) {
    if (modoHistorialActivo) return;
    const tr = el.closest('tr');
    if (!tr) return;
    const operadorInput = tr.querySelector('input[list="listaOperadores"]');
    const fechasInputs = tr.querySelectorAll('.col-fecha .cell-input');
    
    if (!operadorInput || fechasInputs.length === 0) return;
    
    const operador = operadorInput.value.trim();
    const fecha = fechasInputs[0].value; 
    const diaInput = tr.querySelector('.col-dia-laboral');

    if (!operador || !fecha) { 
        if (diaInput) diaInput.value = ''; 
        return; 
    }
    
    try {
        const res = await fetch('/api/obtener_dia_operador', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify({nombre: operador, fecha: fecha}) 
        });
        if (res.ok) {
            const data = await res.json();
            if (diaInput) {
                const nuevoDia = data.dia || "-";
                if (diaInput.value !== nuevoDia) {
                    diaInput.value = nuevoDia;
                    diaInput.style.backgroundColor = '#10b981'; 
                    diaInput.style.color = 'white';
                    setTimeout(() => { 
                        diaInput.style.backgroundColor = 'transparent'; 
                        diaInput.style.color = 'var(--text-muted)'; 
                    }, 1000);
                }
            }
        }
    } catch (err) {}
}

function toggleCV(btn) {
    if (modoHistorialActivo) return;
    if (btn.classList.contains('cv-gray')) { 
        btn.className = 'cv-indicator cv-green'; 
    } else if (btn.classList.contains('cv-green')) { 
        btn.className = 'cv-indicator cv-red'; 
    } else { 
        btn.className = 'cv-indicator cv-gray'; 
    }
}

function agregarEscala(btn) {
    if (modoHistorialActivo) return;
    const tr = btn.closest('tr');
    if (!tr) return;
    const hoy = getFechaOperativaHoy();
    const inputsFechas = tr.querySelectorAll('.col-fecha .cell-input');
    const fechaPrevia = inputsFechas.length > 0 ? inputsFechas[inputsFechas.length - 1].value : hoy;

    tr.querySelector('.col-cliente')?.insertAdjacentHTML('beforeend', `<div class="escala-item"><input type="text" class="cell-input text-left" placeholder="Nuevo destino..." style="font-weight: 800; color: var(--fng-blue);"><button class="btn-row minus" onclick="eliminarEscala(this)" title="Quitar Escala"><i class="fas fa-minus-circle"></i></button></div>`);
    tr.querySelector('.col-dl')?.insertAdjacentHTML('beforeend', `<div class="escala-item"><input type="text" class="cell-input" placeholder="DL"></div>`);
    tr.querySelector('.col-ubicacion')?.insertAdjacentHTML('beforeend', `<div class="escala-item"><input type="text" class="cell-input text-left samsara-location"></div>`);
    tr.querySelector('.col-obs')?.insertAdjacentHTML('beforeend', `<div class="escala-item"><input type="text" class="cell-input text-left" style="color: var(--fng-blue);"></div>`);
    tr.querySelector('.col-fecha')?.insertAdjacentHTML('beforeend', `<div class="escala-item"><input type="date" class="cell-input" value="${fechaPrevia}" oninput="verificarDiaOperativo(this)" onblur="verificarDiaOperativo(this)"></div>`);
    tr.querySelector('.col-factura')?.insertAdjacentHTML('beforeend', `<div class="escala-item"><input type="text" class="cell-input" value="PENDIENTE" style="color:#f59e0b; font-weight:800;"></div>`);
}

function eliminarEscala(btn) {
    if (modoHistorialActivo) return;
    const item = btn.closest('.escala-item'); 
    if (!item) return;
    const td = item.parentNode; 
    const tr = td.parentNode;
    const index = Array.from(td.children).indexOf(item);
    
    ['.col-cliente', '.col-dl', '.col-ubicacion', '.col-obs', '.col-fecha', '.col-factura'].forEach(selector => {
        const columna = tr.querySelector(selector);
        if (columna && columna.children[index]) { 
            columna.removeChild(columna.children[index]); 
        }
    });
}

// 12. PROCESAMIENTO DE DESPACHO PDF CRYOINFRA
function procesarPdfCryoinfra(input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    showToast(`📄 Subiendo y analizando orden: ${file.name}...`, "warning");
    
    const formData = new FormData();
    formData.append('pdf_despacho', file);

    fetch('/api/importar_pdf_despacho', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            showToast("✅ " + data.msg, "success");
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showToast("⚠️ " + (data.msg || "Error al procesar"), "warning");
        }
    })
    .catch(() => showToast("Error de conexión al subir PDF", "warning"));

    input.value = '';
}