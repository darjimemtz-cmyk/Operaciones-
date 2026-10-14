/* ========================================================
   GRUPO FNG - MÓDULO DE CONTROL Y AUDITORÍA DE DIÉSEL
   Compartido entre Analista y Gerencia
   ======================================================== */

const ordenDias = ['MIÉ', 'JUE', 'VIE', 'SÁB', 'DOM', 'LUN', 'MAR'];
const ordenSemanas = ['S27', 'S28', 'S29', 'S30'];

let datosGlobales = [];
let cabecerasDin = {};

// 1. INICIALIZACIÓN AUTOMÁTICA
window.addEventListener('DOMContentLoaded', () => {
    datosGlobales = window.DIESEL_DATA || [];
    cabecerasDin = window.CABECERAS_DIN || {};

    // Actualizar nombres de columnas con las fechas dinámicas
    actualizarCabecerasUI(cabecerasDin);

    // Detectar si estamos en la vista de Analista (tiene #tablaFirmados)
    if (document.getElementById('tablaFirmados')) {
        if (datosGlobales.length > 0) {
            renderTablas(datosGlobales);
        }
    } 
    // Detectar si estamos en la vista de Gerente (tiene #tablaGerente)
    else if (document.getElementById('tablaGerente')) {
        aplicarColoresCeldasEstaticas();
    }
});

// 2. MOTOR TÉRMICO DE CONSUMO
function getColorTermal(valor, esPorcentaje = false) {
    let val = parseFloat(valor);
    if (isNaN(val)) return '#cbd5e1'; 
    
    // Números positivos = Ahorro de combustible (Verde automático)
    if (val > 0) return '#10b981';

    // Tolerancia a pérdidas (números negativos)
    let limiteVerde = esPorcentaje ? -2.0 : -20.0;
    let limiteRojo = esPorcentaje ? -7.5 : -70.0;

    if (val >= limiteVerde) return '#10b981';
    if (val <= limiteRojo) return '#ef4444';

    // Transición gradual de amarillo a rojo
    let rango = limiteVerde - limiteRojo; 
    let progreso = (limiteVerde - val) / rango; 
    
    let hue;
    if (progreso < 0.5) { 
        hue = 45 + (1 - (progreso * 2)) * 75; // Amarillo a Verde 
    } else { 
        let factorAlerta = (progreso - 0.5) * 2; 
        hue = 45 - (factorAlerta * 45);       // Amarillo a Rojo 
    }
    return `hsl(${hue}, 85%, 45%)`;
}

// 3. CAMBIO DE VISTA (DIARIA / MENSUAL)
function switchVista(vista) {
    const btnDiario = document.getElementById('btn-diario');
    const btnMensual = document.getElementById('btn-mensual');

    if (vista === 'diaria') {
        if (btnDiario) btnDiario.classList.add('active-blue');
        if (btnMensual) btnMensual.classList.remove('active-blue');
        document.querySelectorAll('.col-diaria').forEach(el => el.style.display = 'table-cell');
        document.querySelectorAll('.col-mensual').forEach(el => el.style.display = 'none');
    } else {
        if (btnDiario) btnDiario.classList.remove('active-blue');
        if (btnMensual) btnMensual.classList.add('active-blue');
        document.querySelectorAll('.col-diaria').forEach(el => el.style.display = 'none');
        document.querySelectorAll('.col-mensual').forEach(el => el.style.display = 'table-cell');
    }
}

function actualizarCabecerasUI(cabeceras) {
    if (!cabeceras || Object.keys(cabeceras).length === 0) return;
    ['th-MIE', 'th-JUE', 'th-VIE', 'th-SÁB', 'th-DOM', 'th-LUN', 'th-MAR'].forEach((id, idx) => {
        const texto = cabeceras[ordenDias[idx]];
        const el1 = document.getElementById(id);
        const el2 = document.getElementById(id + '-2');
        if (el1 && texto) el1.innerText = texto;
        if (el2 && texto) el2.innerText = texto;
    });
}

// 4. LUPA FORENSE (DRILL-DOWN DE VIAJES)
function abrirDetalleViaje(chofer, dia) {
    let op = datosGlobales.find(r => r.CHOFER === chofer);
    if (!op || !op.detalles_dias || !op.detalles_dias[dia] || op.detalles_dias[dia].length === 0) {
        showToast("Día de descanso o sin viajes registrados.", "warning");
        return;
    }

    document.getElementById('mdlChofer').innerText = chofer;
    document.getElementById('mdlDia').innerText = cabecerasDin[dia] || dia;
    
    let tbody = document.querySelector('#tablaListaViajes tbody');
    tbody.innerHTML = '';
    
    op.detalles_dias[dia].forEach(v => {
        let colorLts = getColorTermal(v.diferencia_lts, false);
        let colorPct = getColorTermal(v.variacion_pct * 100, true);
        
        let tr = `<tr>
            <td style="font-size:11px; white-space:nowrap;">${v.fecha}</td>
            <td style="font-weight:900; color:var(--text-main);">${v.unidad}</td>
            <td style="font-size:11px;"><b>${v.tipo_carga}</b><br><span style="color:var(--text-muted);">${v.estacion}</span></td>
            <td style="font-size:11px;">${v.destino}</td>
            <td style="font-size:12px; font-weight:bold; color:var(--text-muted);">${v.km_total} <span style="font-weight:normal; opacity:0.7;">/ ${v.km_geo}</span></td>
            <td style="font-size:12px; font-weight:bold; color:var(--text-muted);">${v.lts_fisico} <span style="font-weight:normal; opacity:0.7;">/ ${v.lts_geo}</span></td>
            <td style="font-size:14px; font-weight:900; color:${colorLts}">${v.diferencia_lts.toFixed(2)} L</td>
            <td style="font-size:14px; font-weight:900; color:${colorPct}">${(v.variacion_pct * 100).toFixed(2)} %</td>
        </tr>`;
        tbody.innerHTML += tr;
    });
    
    document.getElementById('modalDetalleViajes').style.display = 'flex';
}

// 5. FUNCIONES ESPECÍFICAS DE ANALISTA
async function procesarArchivo() {
    const inputArchivo = document.getElementById('excelFile');
    const archivo = inputArchivo ? inputArchivo.files[0] : null;
    if (!archivo) return showToast("Selecciona un archivo Excel.", "warning");
    
    const formData = new FormData(); 
    formData.append("file", archivo);
    
    const btn = event.target.closest('.btn-action');
    let originalText = btn ? btn.innerHTML : '';
    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Extrayendo...';
        btn.disabled = true;
    }

    try {
        const req = await fetch('/api/procesar_matriz', { method: 'POST', body: formData });
        const res = await req.json();
        
        if (res.error) return showToast("Error: " + res.error, "warning");
        
        cabecerasDin = res.cabeceras;
        actualizarCabecerasUI(res.cabeceras);
        
        datosGlobales = res.data;
        renderTablas(datosGlobales);
        showToast("Matriz procesada y auditada correctamente.", "success");
    } catch (err) {
        showToast("Error de conexión con el servidor.", "warning");
    } finally {
        if (btn) {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }
}

function renderTablas(datos) {
    const tFirm = document.querySelector('#tablaFirmados tbody');
    const tNoFirm = document.querySelector('#tablaNoFirmados tbody');
    if (!tFirm || !tNoFirm) return;

    tFirm.innerHTML = ''; 
    tNoFirm.innerHTML = '';
    
    datos.forEach(row => {
        let html = `<tr><td class="chofer-name">${row.CHOFER}<br><span style="font-size:10px; color:var(--text-muted); font-weight:normal;">${row.NOMINA}</span></td>`;
        
        ordenDias.forEach(dia => {
            let val = (row.dias && row.dias[dia] !== undefined && row.dias[dia] !== null) ? row.dias[dia] : null;
            let displayVal = val !== null ? val.toFixed(1) : "DESCANSO";
            html += `<td class="col-diaria lts-cell cell-hover" onclick="abrirDetalleViaje('${row.CHOFER}', '${dia}')">${displayVal}</td>`;
        });
        
        ordenSemanas.forEach(sem => {
            let sVal = (row.semanas && row.semanas[sem] !== undefined && row.semanas[sem] !== null) ? row.semanas[sem] : 0.0;
            html += `<td class="col-mensual lts-cell" style="display:none;">${sVal.toFixed(1)}</td>`;
        });
        
        html += `<td class="total-lts lts-cell" style="font-size: 14px; border-left:2px solid var(--border-subtle);">${row.TOTAL_LTS.toFixed(1)}</td>
                 <td class="total-pct lts-cell" style="font-size: 14px;">${(row.TOTAL_PCT * 100).toFixed(1)}%</td></tr>`;
        
        if (row.FIRMA === 'SI') tFirm.innerHTML += html;
        else tNoFirm.innerHTML += html;
    });
    
    aplicarColoresUI();
    calcularTotalesFooter();
    
    const esMensual = document.getElementById('btn-mensual')?.classList.contains('active-blue');
    switchVista(esMensual ? 'mensual' : 'diaria');
}

function calcularTotalesFooter() {
    ['tablaFirmados', 'tablaNoFirmados'].forEach(tblId => {
        let tSum = 0; 
        let conteoDiasLaborados = 0;
        document.querySelectorAll(`#${tblId} tbody tr`).forEach(tr => {
            const elTotal = tr.querySelector('.total-lts');
            tSum += parseFloat(elTotal ? elTotal.innerText : 0) || 0;
            tr.querySelectorAll('.col-diaria').forEach(td => {
                if (td.innerText !== 'DESCANSO' && !isNaN(parseFloat(td.innerText))) { 
                    conteoDiasLaborados++; 
                }
            });
        });

        const elTotLts = document.getElementById(tblId === 'tablaFirmados' ? 'totLtsFirmados' : 'totLtsNoFirmados');
        const elTotPct = document.getElementById(tblId === 'tablaFirmados' ? 'totPctFirmados' : 'totPctNoFirmados');

        if (elTotLts) elTotLts.innerText = tSum.toFixed(1);
        let pctGlobal = conteoDiasLaborados > 0 ? (tSum / (conteoDiasLaborados * 1000)) * 100 : 0.0;
        if (elTotPct) elTotPct.innerText = pctGlobal.toFixed(1) + '%';
    });
}

function aplicarColoresUI() {
    document.querySelectorAll('tbody td.lts-cell').forEach(celda => {
        let v = celda.innerText.replace('%','').trim();
        if (v === 'DESCANSO') { 
            celda.className = celda.className + ' celda-descanso'; 
        } else { 
            celda.style.color = getColorTermal(v, celda.classList.contains('total-pct')); 
        }
    });
}

async function sellarReporte() {
    if (!confirm("¿Sellar Base de Datos de Diésel?")) return;
    try {
        const req = await fetch('/api/sellar_dia', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify(datosGlobales) 
        });
        const res = await req.json();
        
        let btn = document.getElementById('btnSellar');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-lock"></i> Matriz Sellada y Bloqueada';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-success');
        }
        showToast(res.msg || "Matriz sellada correctamente.", "success");
    } catch (e) {
        showToast("Error al sellar reporte.", "warning");
    }
}

// 6. FUNCIONES ESPECÍFICAS DE GERENCIA
function aplicarColoresCeldasEstaticas() {
    document.querySelectorAll('.lts-cell').forEach(c => {
        let valStr = c.innerText.replace('L','').replace('%','').trim();
        if (valStr === 'DESCANSO' || valStr === 'None') {
            c.innerText = 'DESCANSO';
            c.className = c.className + ' celda-descanso';
        } else {
            let val = parseFloat(valStr);
            let isPct = c.classList.contains('pct-cell');
            c.style.color = getColorTermal(val, isPct);
        }
    });
}

async function enviarBonosAdmin() {
    if (!confirm("🔐 FIREWALL FINANCIERO: ¿Estás seguro de generar el PDF oficial de bonos y enviarlo por correo a Administración? Esta acción es final y solo puede realizarse los días Miércoles.")) return;

    let btn = event.target.closest('.btn-action');
    let originalText = btn ? btn.innerHTML : '';
    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando PDF...';
        btn.disabled = true;
    }

    let aprobados = [];
    document.querySelectorAll('.bono-toggle').forEach(el => {
        aprobados.push({
            NOMINA: el.getAttribute('data-nomina'),
            CHOFER: el.getAttribute('data-chofer'),
            TOTAL_LTS: parseFloat(el.getAttribute('data-lts')),
            TOTAL_PCT: parseFloat(el.getAttribute('data-pct')),
            BONO: el.checked
        });
    });

    try {
        const req = await fetch('/api/generar_bonos', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ bonos: aprobados })
        });
        const res = await req.json();
        if (res.error) showToast("⛔ " + res.error, "warning");
        else showToast("✅ " + res.msg, "success");
    } catch(e) {
        showToast("Error de conexión con el núcleo de Bonos.", "warning");
    } finally {
        if (btn) {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }
}

async function dispararWhatsappPrueba() {
    if (!confirm("⚠️ ATENCIÓN: Se despacharán mensajes multimedia simulados a las líneas maestras registradas.")) return;
    try {
        const req = await fetch('/api/whatsapp_multimedia', { method: 'POST' });
        const res = await req.json();
        showToast(res.msg || "Alerta despachada", "success");
    } catch (e) {
        showToast("Error al enviar alerta", "warning");
    }
}