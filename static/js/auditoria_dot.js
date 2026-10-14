/* ========================================================
   GRUPO FNG - MÓDULO DE AUDITORÍA DOT (NOM-087)
   Cálculo de fatiga, acordeón, OCR y exportación PDF
   ======================================================== */

let todosOperadoresData = [];
let todosNombresBD = [];

// Conversor decimal a formato HH:MM
function decimalToTime(decimal) {
    if (!decimal || isNaN(decimal)) return "00:00";
    let h = Math.floor(decimal);
    let m = Math.round((decimal - h) * 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

// 1. INICIALIZACIÓN
window.addEventListener('DOMContentLoaded', () => {
    todosOperadoresData = window.DOT_OPERADORES || [];
    todosNombresBD = window.DOT_NOMBRES_OCR || [];
    calcularKPIDOT('');

    // Listener para cerrar popover y buscador al dar clic fuera
    window.addEventListener('click', function(e) {
        const bar = document.getElementById('searchBarContainerRH');
        const input = document.getElementById('buscadorRH');
        if (bar && !bar.contains(e.target) && input && input.value.trim() === '') {
            bar.classList.remove('active');
        }

        const pop = document.getElementById('dotPopover');
        if (pop && pop.style.display === 'block' && !pop.contains(e.target)) {
            pop.style.display = 'none';
        }
    });
});

// 2. CÁLCULO DINÁMICO DE KPIS DOT (NOM-087)
function calcularKPIDOT(filtro = '') {
    filtro = filtro.trim().toUpperCase();
    
    const opsFiltrados = todosOperadoresData.filter(op => {
        if (!filtro) return true;
        return op.nombre.toUpperCase().includes(filtro);
    });

    let sobregiros = 0;
    let diasLaborados = 0;
    let sumaHorasDecimal = 0;
    let sobretrabajo14 = 0;
    let sobretrabajo8 = 0;
    let descansos = 0;
    let descansosIncompletos = 0;
    let diasEstimados = 0;
    let plantilla = opsFiltrados.length;

    opsFiltrados.forEach(op => {
        let rachaTrabajo = 0;
        
        if (op.restantes <= 0 && op.total > 0) {
            sobregiros++;
        }

        (op.horas_diarias || []).forEach(dia => {
            if (!dia) return;

            let h = parseFloat(dia.horas) || 0;
            let est = (dia.estatus || dia.estatus_dia || '').toUpperCase();
            let esDescanso = ['D', 'DESCANSO', 'V', 'VACACIONES', 'I', 'INCAPACIDAD', 'B', 'BAJA', 'P', 'PERMISO'].includes(est);

            if (dia.auditado === 0 || dia.auditado === false || dia.tipo_registro === 'Estimado') {
                diasEstimados++;
            }

            if (esDescanso) {
                descansos++;
                rachaTrabajo = 0;
            } else {
                diasLaborados++;
                sumaHorasDecimal += h;
                rachaTrabajo++;

                if (h > 14.0) sobretrabajo14++;
                if (rachaTrabajo > 8) sobretrabajo8++;
                if (rachaTrabajo > 6) descansosIncompletos++;
            }
        });
    });

    let penalizacion = (sobregiros * 15) + (sobretrabajo14 * 10) + (sobretrabajo8 * 10);
    let calificacion = Math.max(0, 100 - penalizacion);

    let dias_del_mes = opsFiltrados.length > 0 && opsFiltrados[0].horas_diarias ? opsFiltrados[0].horas_diarias.length : 30;
    let maxCapacidadHoras = plantilla * (dias_del_mes / 8) * 70;
    let utilizacion = maxCapacidadHoras > 0 ? ((sumaHorasDecimal / maxCapacidadHoras) * 100).toFixed(2) : "0.00";

    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
    setVal('kpiSobregiros', sobregiros);
    setVal('kpiDiasLaborados', diasLaborados);
    setVal('kpiHorasAcumuladas', decimalToTime(sumaHorasDecimal));
    setVal('kpiSobretrabajo14', sobretrabajo14);
    setVal('kpiSobretrabajo8', sobretrabajo8);
    setVal('kpiDescansos', descansos);
    setVal('kpiDescansosIncompletos', descansosIncompletos);
    setVal('kpiDiasEstimados', diasEstimados);
    setVal('kpiPlantilla', plantilla);
    setVal('kpiCalificacion', calificacion + " %");
    setVal('kpiUtilizacion', utilizacion + " %");
}

// 3. ACORDEÓN TIPO KARDEX
function toggleAccordion(opId) {
    const row = document.getElementById('row-' + opId);
    if (!row) return;
    let subrows = document.querySelectorAll('.subrow-' + opId);
    
    if (subrows.length > 0) {
        const isCurrentlyOpen = subrows[0].style.display !== 'none';
        subrows.forEach(r => r.style.display = isCurrentlyOpen ? 'none' : 'table-row');
        row.classList.toggle('row-expanded', !isCurrentlyOpen);
        return;
    }
    
    const btn = row.querySelector('.btn-action');
    if (!btn) return;
    const dataHoras = JSON.parse(btn.getAttribute('data-horas') || '[]');
    
    renderNativeSubrows(opId, row, dataHoras);
    row.classList.add('row-expanded');
}

function renderNativeSubrows(opId, parentRow, data) {
    const labels = [
        { key: 'tipo', label: 'Tipo' },
        { key: 'estatus', label: 'Estatus' },
        { key: 'equipo', label: 'Tractor / Pipa' },
        { key: 'servicio', label: 'Horas de Servicio' },
        { key: 'dot', label: 'Horas D.O.T.' },
        { key: 'acumulado', label: 'Acumulado' },
        { key: 'dias', label: 'Días Trabajados' }
    ];

    let cells = { tipo: [], estatus: [], equipo: [], servicio: [], dot: [], acumulado: [], dias: [] };
    let acumHoras = 0;
    let diasTrab = 0;
    let dotSum = 0;

    data.forEach(dia => {
        if (!dia) {
            cells.tipo.push('-'); cells.estatus.push('-'); cells.equipo.push('/');
            cells.servicio.push('00:00'); cells.dot.push('-'); cells.acumulado.push('-'); cells.dias.push('0');
            return;
        }

        let rawEst = (dia.estatus || dia.estatus_dia || 'EN VIAJE').toUpperCase();
        let isRest = ['D', 'DESCANSO', 'V', 'VACACIONES', 'I', 'INCAPACIDAD', 'B', 'BAJA', 'P', 'PERMISO'].includes(rawEst);
        
        let tipo = (dia.auditado === 1 || dia.auditado === true) ? 'R' : 'E';
        cells.tipo.push(tipo);

        let estPill = rawEst;
        if (rawEst === 'D' || rawEst === 'DESCANSO') estPill = '<span class="pill-estatus pill-d">D</span>';
        else if (rawEst === 'V' || rawEst === 'VACACIONES') estPill = '<span class="pill-estatus pill-v">V</span>';
        else if (rawEst === 'EN VIAJE') estPill = 'EN VIAJE';
        else estPill = `<span class="pill-estatus">${rawEst.charAt(0)}</span>`;
        cells.estatus.push(estPill);

        let tractor = dia.unidad && dia.unidad !== 'N/A' ? dia.unidad : '';
        let pipa = dia.pipas && dia.pipas !== 'N/A' ? dia.pipas : '';
        let eq = (tractor || pipa) && !isRest ? `${tractor} / ${pipa}` : '/';
        cells.equipo.push(eq);

        let hDec = parseFloat(dia.horas) || 0;
        cells.servicio.push(decimalToTime(hDec));

        if (isRest) {
            acumHoras = 0; diasTrab = 0;
        } else {
            acumHoras += hDec; diasTrab += 1;
        }
        dotSum += hDec;

        cells.dot.push(dotSum > 0 ? decimalToTime(dotSum) : '-');
        cells.acumulado.push(acumHoras > 0 ? decimalToTime(acumHoras) : '-');
        cells.dias.push(diasTrab);
    });

    let createdRows = [];
    labels.forEach(l => {
        const tr = document.createElement('tr');
        tr.className = `subrow-${opId} accordion-subrow`;
        
        let html = `<td class="sticky-col-1 nested-header">${l.label}</td>`;
        html += `<td class="sticky-col-2 nested-sub">-</td>`;
        
        cells[l.key].forEach(val => {
            html += `<td class="col-dia">${val}</td>`;
        });

        html += `<td class="col-total">-</td>`;
        if (document.querySelector('th.col-accion')) {
            html += `<td class="col-accion">-</td>`;
        }

        tr.innerHTML = html;
        createdRows.push(tr);
    });

    let lastNode = parentRow;
    createdRows.forEach(tr => {
        lastNode.after(tr);
        lastNode = tr;
    });
}

// 4. POPOVER RÁPIDO
function mostrarPopover(e, est, uni, pipas, mane, mani, fecha) {
    e.stopPropagation();
    const pop = document.getElementById('dotPopover');
    if (!pop) return;

    document.getElementById('popTitle').innerHTML = `<i class="far fa-calendar-alt"></i> ${fecha}`;
    
    let catMap = {'En Viaje':'EN VIAJE', 'EN VIAJE':'EN VIAJE', 'Descanso':'D', 'D':'D', 'Guardia':'G', 'Permiso':'P', 'Incapacidad':'I', 'Vacaciones':'V', 'Baja':'B', 'Capacitación':'C', 'Nuevo':'N', 'Otro':'OTRO'};
    document.getElementById('popEstatus').innerText = catMap[est] || est;
    
    if (['D', 'Descanso', 'Vacaciones', 'Incapacidad', 'Capacitación', 'Permiso', 'Baja'].includes(est)) {
        document.getElementById('popVehiculos').style.display = 'none';
    } else {
        document.getElementById('popVehiculos').style.display = 'block';
        document.getElementById('popUni').innerText = uni && uni !== 'N/A' ? uni : 'N/A';
        document.getElementById('popPipas').innerText = pipas && pipas !== 'N/A' ? pipas : 'N/A';
        document.getElementById('popManejo').innerText = mane || '0.0';
        document.getElementById('popManiobra').innerText = mani || '0.0';
    }

    pop.style.left = (e.pageX + 15) + 'px';
    pop.style.top = (e.pageY + 15) + 'px';
    pop.style.display = 'block';
}

// 5. MOTOR OCR (TESSERACT)
function encontrarOperadorSimilar(textoLeido) {
    textoLeido = textoLeido.toUpperCase();
    for (let nombreBD of todosNombresBD) {
        if (textoLeido.includes(nombreBD)) return nombreBD;
        let partes = nombreBD.split(" ");
        if (partes.length > 2 && textoLeido.includes(partes[0]) && textoLeido.includes(partes[1])) return nombreBD;
    }
    return null;
}

async function procesarImagenOCR(input) {
    if (!input.files || !input.files[0]) return;
    const imagen = input.files[0];
    
    document.getElementById('ocr-dropzone').style.display = 'none';
    document.getElementById('ocr-loading').style.display = 'block';
    
    try {
        const resultado = await Tesseract.recognize(imagen, 'spa', { 
            logger: m => console.log(m.status + ": " + Math.round(m.progress * 100) + "%") 
        });
        const textoLimpio = resultado.data.text.toUpperCase();
        
        let nombreAsignado = encontrarOperadorSimilar(textoLimpio);
        if (!nombreAsignado) { 
            alert("❌ OCR: No detecté a qué operador pertenece. Confirma legibilidad de la imagen."); 
            cancelarOCR(); 
            return; 
        }

        let folio_bhs = '';
        let folioMatch = textoLimpio.match(/FOLIO:?\s*(\d+)/);
        if (folioMatch) folio_bhs = folioMatch[1];

        let estatus = 'EN VIAJE';
        let manejo = 0.0;
        let maniobra = 0.0;
        let esDescanso = textoLimpio.includes("24:00") && (!textoLimpio.includes("CONDUCIENDO") || !textoLimpio.includes("08:00"));

        if (esDescanso) {
            estatus = 'D';
        } else {
            estatus = 'EN VIAJE';
            manejo = 8.0;
            maniobra = 3.0;
        }

        let fechaFormateada = new Date().toISOString().split('T')[0];

        let mockDia = {
            fecha: fechaFormateada,
            horas: manejo + maniobra,
            estatus_dia: estatus,
            eco_unidad: '',
            eco_pipas: '',
            horas_manejo: manejo,
            horas_maniobra: maniobra,
            auditado: 0,
            folio_bhs: folio_bhs,
            tipo_registro: 'Estimado'
        };

        const op = todosOperadoresData.find(o => o.nombre.toUpperCase() === nombreAsignado);
        
        if (op) {
            let tempBtn = document.createElement('button');
            tempBtn.setAttribute('data-horas', JSON.stringify([mockDia]));
            
            showToast(`🤖 OCR: Lectura completada para ${nombreAsignado}`, "success");
            abrirModalEditorDatoUnico(op.id, op.nombre_credencial || nombreAsignado, tempBtn);
        }

        cancelarOCR();
    } catch(error) { 
        console.error(error); 
        alert("❌ Fallo en el motor OCR. Revisa consola."); 
        cancelarOCR(); 
    }
}

function cancelarOCR() { 
    document.getElementById('ocr-input').value = ""; 
    document.getElementById('ocr-dropzone').style.display = 'flex'; 
    document.getElementById('ocr-loading').style.display = 'none'; 
}

// 6. MODAL DE EDICIÓN INDIVIDUAL
function abrirModalEditorDatoUnico(id, nombre, btnEl) {
    document.body.style.overflow = 'hidden'; 
    
    document.getElementById('dotIdOp').value = id;
    document.getElementById('modalNombreCredencial').innerText = nombre;
    
    const jsonStr = btnEl.getAttribute('data-horas') || '[]';
    document.getElementById('jsonHorasOcultas').value = jsonStr; 
    
    let select = document.getElementById('editDotFecha');
    select.selectedIndex = 0; 
    cargarDatosDiaSeleccionado();
    
    document.getElementById('modalEditarDOT').style.display = 'flex';
}

function cerrarModalDOT() {
    document.body.style.overflow = ''; 
    document.getElementById('modalEditarDOT').style.display = 'none';
}

function cargarDatosDiaSeleccionado() {
    let arrayStr = document.getElementById('jsonHorasOcultas').value;
    let objSemana = JSON.parse(arrayStr || '[]');
    let idx = document.getElementById('editDotFecha').selectedIndex;
    let objDia = objSemana[idx];

    if (objDia) {
        document.getElementById('editTipoRegistro').value = (objDia.auditado === 1 || objDia.auditado === true) ? 'Real' : 'Estimado';
        
        let catMap = {'En Viaje':'EN VIAJE', 'EN VIAJE':'EN VIAJE', 'Descanso':'D', 'D':'D', 'Guardia':'G', 'Permiso':'P', 'Incapacidad':'I', 'Vacaciones':'V', 'Baja':'B', 'Capacitación':'C', 'Nuevo':'N', 'Otro':'OTRO'};
        document.getElementById('editDotEstatus').value = catMap[objDia.estatus || objDia.estatus_dia] || 'EN VIAJE';
        
        document.getElementById('editDotUnidad').value = objDia.unidad && objDia.unidad !== 'N/A' ? objDia.unidad : '';
        document.getElementById('editDotPipas').value = objDia.pipas && objDia.pipas !== 'N/A' ? objDia.pipas : '';
        document.getElementById('editNoBitacora').value = objDia.no_bitacora || '';
        document.getElementById('editFolioBHS').value = objDia.folio_bhs || '';
        document.getElementById('editClaveNocturna').value = objDia.clave_nocturna || '';
        document.getElementById('editViajeMina').value = objDia.viaje_mina || 'NO';
        
        document.getElementById('editDotManejo').value = objDia.manejo || objDia.horas_manejo || 0.0;
        document.getElementById('editDotManiobra').value = objDia.maniobra || objDia.horas_maniobra || 0.0;
        document.getElementById('editObservaciones').value = objDia.observaciones || '';
        
        if (objDia.evidencia_foto && objDia.evidencia_foto !== 'N/A') {
            document.getElementById('visorEvidencia').src = '/evidencias/' + objDia.evidencia_foto;
            document.getElementById('visorEvidencia').style.display = 'block';
            document.getElementById('noEvidenciaTexto').style.display = 'none';
            document.getElementById('linkAmpliarImg').href = '/evidencias/' + objDia.evidencia_foto;
            document.getElementById('linkAmpliarImg').style.display = 'inline-block';
        } else {
            document.getElementById('visorEvidencia').style.display = 'none';
            document.getElementById('noEvidenciaTexto').style.display = 'block';
            document.getElementById('linkAmpliarImg').style.display = 'none';
        }
    } else {
        document.getElementById('editTipoRegistro').value = 'Estimado';
        document.getElementById('editDotEstatus').value = 'EN VIAJE';
        document.getElementById('editDotUnidad').value = '';
        document.getElementById('editDotPipas').value = '';
        document.getElementById('editNoBitacora').value = '';
        document.getElementById('editFolioBHS').value = '';
        document.getElementById('editClaveNocturna').value = '';
        document.getElementById('editViajeMina').value = 'NO';
        document.getElementById('editDotManejo').value = 0.0;
        document.getElementById('editDotManiobra').value = 0.0;
        document.getElementById('editObservaciones').value = '';
        
        document.getElementById('visorEvidencia').style.display = 'none';
        document.getElementById('noEvidenciaTexto').style.display = 'block';
        document.getElementById('linkAmpliarImg').style.display = 'none';
    }
    toggleCamposVehiculos();
}

function toggleCamposVehiculos() {
    const sel = document.getElementById('editDotEstatus').value;
    const cont = document.getElementById('camposVehiculosDOT');
    if (['D', 'V', 'I', 'B', 'P', 'C'].includes(sel)) {
        cont.style.display = 'none';
        document.getElementById('editDotManejo').value = 0.0;
        document.getElementById('editDotManiobra').value = 0.0;
    } else {
        cont.style.display = 'block';
    }
    calcularTotalModal();
}

function calcularTotalModal() {
    let man = parseFloat(document.getElementById('editDotManejo').value) || 0.0;
    let manb = parseFloat(document.getElementById('editDotManiobra').value) || 0.0;
    let tot = man + manb;
    
    let displayStr = decimalToTime(tot);
    let el = document.getElementById('suma_modal_dot');
    el.innerText = displayStr;
    el.style.color = tot > 14 ? '#ef4444' : '#10b981';
}

async function guardarUnSoloDia() {
    const id = document.getElementById('dotIdOp').value;
    const fecha = document.getElementById('editDotFecha').value;
    const estatus = document.getElementById('editDotEstatus').value;
    const tipoReg = document.getElementById('editTipoRegistro').value;
    
    let uniVal = document.getElementById('editDotUnidad').value;
    let pipaVal = document.getElementById('editDotPipas').value;
    let noBit = document.getElementById('editNoBitacora').value;
    let folBHS = document.getElementById('editFolioBHS').value;
    let claNoc = document.getElementById('editClaveNocturna').value;
    let viaMin = document.getElementById('editViajeMina').value;
    let obs = document.getElementById('editObservaciones').value;

    if (document.getElementById('camposVehiculosDOT').style.display !== 'none') {
        if (uniVal && !/^\d{4}$/.test(uniVal)) { 
            document.getElementById('editDotUnidad').classList.add('input-error'); 
            showToast("Unidad debe tener 4 dígitos exactos.", "warning"); 
            return; 
        } else { 
            document.getElementById('editDotUnidad').classList.remove('input-error'); 
        }
    }

    let manejo = parseFloat(document.getElementById('editDotManejo').value) || 0.0;
    let maniobra = parseFloat(document.getElementById('editDotManiobra').value) || 0.0;
    let totalHoras = manejo + maniobra;

    if (totalHoras > 24) { 
        showToast("⚠️ No puedes registrar más de 24h en un solo día.", "warning"); 
        return; 
    }

    let objDia = {
        fecha: fecha, 
        horas: totalHoras, 
        estatus_dia: estatus,
        eco_unidad: uniVal || 'N/A', 
        eco_pipas: pipaVal || 'N/A',
        horas_manejo: manejo, 
        horas_maniobra: maniobra,
        no_bitacora: noBit,
        folio_bhs: folBHS,
        clave_nocturna: claNoc,
        viaje_mina: viaMin,
        observaciones: obs,
        auditado: (tipoReg === 'Real' ? 1 : 0)
    };

    try {
        const res = await fetch('/api/actualizar_dot', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify({id: id, origen: 'manual', horas_diarias: [objDia]}) 
        });

        if (res.ok) { 
            showToast("✅ Registro Actualizado Exitosamente", "success"); 
            setTimeout(() => window.location.reload(), 1000); 
        } else { 
            showToast("⚠️ Error al actualizar", "warning"); 
        }
    } catch(e) {
        showToast("Error de conexión al guardar", "warning");
    }
}

// 7. EXPORTACIÓN PDF CON JSPDF
function descargarReporteDOT(textoMes, mesActualStr, diasMesLabels) {
    showToast("⏳ Imprimiendo Reporte de Alta Calidad...", "warning");
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ orientation: 'landscape', format: 'letter' });
    
    const fngBlue = [0, 45, 90]; 
    const fngOrange = [255, 140, 0];
    
    doc.setFont('helvetica', 'bold'); 
    doc.setFontSize(20); 
    doc.setTextColor(fngBlue[0], fngBlue[1], fngBlue[2]);
    doc.text("REPORTE DE AUDITORÍA DOT (FATIGA)", doc.internal.pageSize.getWidth() / 2, 20, { align: 'center' });
    
    doc.setFontSize(12); 
    doc.setTextColor(fngOrange[0], fngOrange[1], fngOrange[2]);
    doc.text(`KARDEX MENSUAL: ${textoMes.toUpperCase()}`, doc.internal.pageSize.getWidth() / 2, 28, { align: 'center' });
    
    const head = [['Operador', 'Rest.', ...diasMesLabels, 'TOTAL']];
    const body = [];
    
    todosOperadoresData.forEach(op => {
        const fila = [op.nombre, op.restantes + 'h'];
        (op.horas_diarias || []).forEach(h => fila.push(h ? h.horas : '-'));
        fila.push(op.total + 'h');
        body.push(fila);
    });
    
    doc.autoTable({
        head: head, body: body, startY: 38, theme: 'grid',
        styles: { fontSize: 6, halign: 'center', valign: 'middle', cellPadding: 1, overflow: 'linebreak' },
        headStyles: { fillColor: fngBlue, textColor: 255 },
        bodyStyles: { textColor: [50, 50, 50] },
        columnStyles: { 0: { halign: 'left', fontStyle: 'bold', textColor: fngBlue, cellWidth: 40 }, 1: { fontStyle: 'bold', cellWidth: 15 } },
        horizontalPageBreak: true,
        didParseCell: function(data) {
            if (data.section === 'body' && data.column.index === 1) {
                const rest = parseFloat(data.cell.raw);
                if (rest < 10) { data.cell.styles.textColor = [220, 53, 69]; } 
                else { data.cell.styles.textColor = [25, 135, 84]; }
            }
        }
    });
    doc.save(`Auditoria_DOT_${mesActualStr}.pdf`);
    showToast("✅ Reporte Generado Exitosamente.", "success");
}

// 8. BUSCADOR Y FILTRADO
function expandirBuscadorRH() {
    const bar = document.getElementById('searchBarContainerRH');
    if (bar && !bar.classList.contains('active')) {
        bar.classList.add('active');
        document.getElementById('buscadorRH').focus();
    }
}

function limpiarYColapsarBuscadorRH(e) {
    if (e) e.stopPropagation();
    const input = document.getElementById('buscadorRH');
    const bar = document.getElementById('searchBarContainerRH');
    if (input) input.value = '';
    if (input) input.blur();
    if (bar) bar.classList.remove('active');
    filtrarTablaAuditoria();
}

function filtrarTablaAuditoria() {
    const inputEl = document.getElementById('buscadorRH');
    const input = inputEl ? inputEl.value.toUpperCase().trim() : '';
    const filas = document.querySelectorAll('.fila-auditoria');

    filas.forEach(fila => {
        const nombreCelda = fila.querySelector('.col-nombre');
        if (nombreCelda) {
            const nombre = nombreCelda.innerText.toUpperCase();
            const opId = fila.id.replace('row-', '');
            const subrows = document.querySelectorAll('.subrow-' + opId);

            if (nombre.indexOf(input) > -1) {
                fila.style.display = "";
                if (fila.classList.contains('row-expanded')) {
                    subrows.forEach(sr => sr.style.display = 'table-row');
                }
            } else {
                fila.style.display = "none";
                subrows.forEach(sr => sr.style.display = 'none');
            }
        }
    });

    calcularKPIDOT(input);
}