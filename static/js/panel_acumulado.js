/* ========================================================
   GRUPO FNG - MÓDULO TORRE DE CONTROL Y RADAR SLP
   Simulador, Gráficas Chart.js, Predictivo y Estatus en Vivo
   ======================================================== */

let myChart = null;
let clientesChartInstance = null;
let isGerencial = true;

// 1. INICIALIZACIÓN
window.addEventListener('DOMContentLoaded', () => {
    // Scroll suave si venimos navegando con fecha específica
    if (window.location.search.includes('fecha=')) {
        const radar = document.getElementById('seccion-radar');
        if (radar) {
            radar.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    // Desactivar cursor interactivo en fechas pasadas
    const hoy = new Date().toISOString().split('T')[0];
    document.querySelectorAll('.cell-interactive').forEach(cell => {
        const onclickAttr = cell.getAttribute('onclick') || '';
        const match = onclickAttr.match(/'(\d{4}-\d{2}-\d{2})'/);
        if (match && match[1] && match[1] < hoy) {
            cell.classList.remove('cell-interactive');
            cell.style.cursor = 'default';
        }
    });

    // Inicializar Gráfica del Simulador
    const canvasSim = document.getElementById('simuladorChart');
    if (canvasSim) {
        const ctx = canvasSim.getContext('2d');
        myChart = new Chart(ctx, { 
            type: 'bar', 
            data: { 
                labels: [], 
                datasets: [ 
                    { label: 'Unidades', data: [], backgroundColor: '#3b82f6' }, 
                    { label: 'Operadores Reales', data: [], backgroundColor: '#22c55e' }, 
                    { label: 'Op. Necesarios', data: [], backgroundColor: '#eab308' } 
                ] 
            }, 
            options: { 
                responsive: true, 
                maintainAspectRatio: false, 
                scales: { y: { beginAtZero: true } }, 
                plugins: { legend: { position: 'bottom' } } 
            } 
        });
    }

    // Restaurar vista gerencial guardada en navegador
    let vistaGuardada = localStorage.getItem('fng_vista_gerencial');
    isGerencial = (vistaGuardada !== null) ? (vistaGuardada === 'true') : true; 
    toggleVista(isGerencial ? 'gerencial' : 'detallada'); 
});

// 2. NAVEGACIÓN PRINCIPAL ENTRE MODOS (PANEL, ESTATUS, PREDICTIVO)
function cambiarModoPrincipal(modo) {
    const btnPanel = document.getElementById('btnModoPanel');
    const btnEstatus = document.getElementById('btnModoEstatus');
    const btnPredictivo = document.getElementById('btnModoPredictivo');
    
    const contenedorPanel = document.getElementById('modoPanelContenedor');
    const contenedorEstatus = document.getElementById('modoEstatusContenedor');
    const contenedorPredictivo = document.getElementById('modoPredictivoContenedor');
    const selectorGerencial = document.getElementById('selectorGerencial');

    if (btnPanel) btnPanel.classList.remove('active-blue');
    if (btnEstatus) btnEstatus.classList.remove('active-blue');
    if (btnPredictivo) btnPredictivo.classList.remove('active-blue');
    if (contenedorPanel) contenedorPanel.style.display = 'none';
    if (contenedorEstatus) contenedorEstatus.style.display = 'none';
    if (contenedorPredictivo) contenedorPredictivo.style.display = 'none';
    if (selectorGerencial) selectorGerencial.style.display = 'none';

    if (modo === 'panel') {
        if (btnPanel) btnPanel.classList.add('active-blue');
        if (contenedorPanel) contenedorPanel.style.display = 'block';
        if (selectorGerencial) selectorGerencial.style.display = 'inline-flex';
    } else if (modo === 'estatus') {
        if (btnEstatus) btnEstatus.classList.add('active-blue');
        if (contenedorEstatus) contenedorEstatus.style.display = 'block';
        cargarEstatusVivo(); 
    } else if (modo === 'predictivo') {
        if (btnPredictivo) btnPredictivo.classList.add('active-blue');
        if (contenedorPredictivo) contenedorPredictivo.style.display = 'block';
        cargarPredictivo(); 
        cargarAnaliticaClientes();
    }
}

// 3. ALTERNANCIA VISTA UNIFICADA / DETALLADA
function toggleVista(modo) {
    const btnG = document.getElementById('btnGerencial');
    const btnD = document.getElementById('btnDetallada');
    if (modo) {
        isGerencial = (modo === 'gerencial');
        localStorage.setItem('fng_vista_gerencial', isGerencial);
    }
    if (isGerencial) {
        if (btnG) btnG.classList.add('active'); 
        if (btnD) btnD.classList.remove('active');
        document.querySelectorAll('.col-gerencial').forEach(el => el.style.display = 'table-cell');
        document.querySelectorAll('.col-detallada').forEach(el => el.style.display = 'none');
        const tg = document.getElementById('tablasGerenciales'); if (tg) tg.style.display = 'block';
        const td = document.getElementById('tablasDetalladas'); if (td) td.style.display = 'none';
    } else {
        if (btnD) btnD.classList.add('active'); 
        if (btnG) btnG.classList.remove('active');
        document.querySelectorAll('.col-gerencial').forEach(el => el.style.display = 'none');
        document.querySelectorAll('.col-detallada').forEach(el => el.style.display = 'table-cell');
        const tg = document.getElementById('tablasGerenciales'); if (tg) tg.style.display = 'none';
        const td = document.getElementById('tablasDetalladas'); if (td) td.style.display = 'block';
    }
    calcularSimulador();
}

// 4. MOTOR DE CÁLCULO DEL SIMULADOR
function calcularSimulador() {
    let cols = ['arg', 'nit', 'oxi', 'co2'];
    let tot_u = 0, tot_o = 0, tot_r = 0;
    let u_cryo = 0, o_cryo = 0, r_cryo = 0;

    cols.forEach(c => {
        let elU = document.getElementById('u_' + c);
        let elO = document.getElementById('o_' + c);
        let u = elU ? (parseInt(elU.value) || 0) : 0;
        let o = elO ? (parseInt(elO.innerText) || 0) : 0;
        let r = Math.round(u * 1.8);
        let d = o - r; 
        let f = u > 0 ? (o / u).toFixed(2) : "0.00";
        
        const elR = document.getElementById('r_' + c); if (elR) elR.innerText = r;
        const elD = document.getElementById('d_' + c);
        if (elD) {
            elD.innerText = (d > 0 ? "+" : "") + d; 
            elD.classList.remove('negativo', 'positivo'); 
            elD.classList.add(d < 0 ? 'negativo' : 'positivo');
        }
        const elF = document.getElementById('f_' + c); if (elF) elF.innerText = f;
        
        tot_u += u; tot_o += o; tot_r += r;
        if (c !== 'co2') { u_cryo += u; o_cryo += o; r_cryo += r; }
    });

    const elUCryo = document.getElementById('u_cryo'); if (elUCryo) elUCryo.value = u_cryo;
    const elOCryo = document.getElementById('o_cryo'); if (elOCryo) elOCryo.innerText = o_cryo;
    const elRCryo = document.getElementById('r_cryo'); if (elRCryo) elRCryo.innerText = r_cryo;
    
    let d_cryo = o_cryo - r_cryo;
    let elD_cryo = document.getElementById('d_cryo');
    if (elD_cryo) {
        elD_cryo.innerText = (d_cryo > 0 ? "+" : "") + d_cryo; 
        elD_cryo.classList.remove('negativo', 'positivo'); 
        elD_cryo.classList.add(d_cryo < 0 ? 'negativo' : 'positivo');
    }
    const elFCryo = document.getElementById('f_cryo');
    if (elFCryo) elFCryo.innerText = u_cryo > 0 ? (o_cryo / u_cryo).toFixed(2) : "0.00";

    const elUTot = document.getElementById('u_tot'); if (elUTot) elUTot.innerText = tot_u; 
    const elOTot = document.getElementById('o_tot'); if (elOTot) elOTot.innerText = tot_o; 
    const elRTot = document.getElementById('r_tot'); if (elRTot) elRTot.innerText = tot_r;
    
    let d_tot = tot_o - tot_r; 
    let f_tot = tot_u > 0 ? (tot_o / tot_u).toFixed(2) : "0.00";
    let elDtot = document.getElementById('d_tot'); 
    if (elDtot) {
        elDtot.innerText = (d_tot > 0 ? "+" : "") + d_tot; 
        elDtot.classList.remove('negativo', 'positivo'); 
        elDtot.classList.add(d_tot < 0 ? 'negativo' : 'positivo');
    }
    const elFTot = document.getElementById('f_tot'); if (elFTot) elFTot.innerText = f_tot;

    if (myChart) {
        const uCo2 = parseInt(document.getElementById('u_co2')?.value) || 0;
        const oCo2 = parseInt(document.getElementById('o_co2')?.innerText) || 0;

        if (isGerencial) {
            myChart.data.labels = ['LÍNEA CRYO', 'LÍNEA CO2', 'TOTAL'];
            myChart.data.datasets[0].data = [u_cryo, uCo2, tot_u];
            myChart.data.datasets[1].data = [o_cryo, oCo2, tot_o];
            myChart.data.datasets[2].data = [r_cryo, Math.round(uCo2 * 1.8), tot_r];
        } else {
            const uArg = parseInt(document.getElementById('u_arg')?.value) || 0;
            const uNit = parseInt(document.getElementById('u_nit')?.value) || 0;
            const uOxi = parseInt(document.getElementById('u_oxi')?.value) || 0;
            const oArg = parseInt(document.getElementById('o_arg')?.innerText) || 0;
            const oNit = parseInt(document.getElementById('o_nit')?.innerText) || 0;
            const oOxi = parseInt(document.getElementById('o_oxi')?.innerText) || 0;

            myChart.data.labels = ['ARGÓN', 'NITRÓGENO', 'OXÍGENO', 'CO2', 'TOTAL'];
            myChart.data.datasets[0].data = [uArg, uNit, uOxi, uCo2, tot_u];
            myChart.data.datasets[1].data = [oArg, oNit, oOxi, oCo2, tot_o];
            myChart.data.datasets[2].data = [Math.round(uArg * 1.8), Math.round(uNit * 1.8), Math.round(uOxi * 1.8), Math.round(uCo2 * 1.8), tot_r];
        }
        myChart.update();
    }
}

async function guardarBD() {
    let req = { 
        argon: document.getElementById('u_arg')?.value, 
        nitrogeno: document.getElementById('u_nit')?.value, 
        oxigeno: document.getElementById('u_oxi')?.value, 
        co2: document.getElementById('u_co2')?.value 
    };
    try {
        const res = await fetch('/api/guardar_simulador', { 
            method: 'POST', 
            headers: {'Content-Type': 'application/json'}, 
            body: JSON.stringify(req) 
        });
        const result = await res.json();
        if (result.status === 'solicitado') showToast("⏳ Solicitud enviada al Jefe Op.", "warning");
        else showToast("✅ Metas Fijas configuradas.", "success");
        setTimeout(() => window.location.reload(), 1500); 
    } catch(e) {
        showToast("Error de conexión al guardar simulador", "warning");
    }
}

// 5. MODAL DRILLDOWN (DESGLOSE DE OPERADORES)
async function abrirDrilldown(producto, fecha, tipo) {
    const hoy = new Date().toISOString().split('T')[0];
    if (fecha < hoy) return;

    const modal = document.getElementById('modalDrilldown');
    if (modal) modal.style.display = 'flex';
    
    const titulo = document.getElementById('drillTitulo');
    const sub = document.getElementById('drillSubtitulo');
    const cont = document.getElementById('drillContenido');
    
    let nomTipo = tipo === 'Disp' ? 'Operadores Activos' : 
                  tipo === 'NoDisp' ? 'Operadores No Activos' : 
                  tipo === 'Deficit' ? 'Candidatos Inteligentes (Faltantes)' : 'Plantilla Total';
    
    if (titulo) titulo.innerHTML = `<i class="fas fa-${tipo === 'Deficit' ? 'magic' : 'users'}"></i> ${nomTipo}`;
    if (sub) sub.innerText = `Línea: ${producto} | Fecha: ${fecha}`;
    if (cont) cont.innerHTML = '<div style="text-align:center; padding:20px; color:#94a3b8;"><i class="fas fa-spinner fa-spin"></i> Analizando datos...</div>';

    try {
        const res = await fetch('/api/drilldown_radar', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            body: JSON.stringify({ producto: producto, fecha: fecha, tipo: tipo }) 
        });
        const data = await res.json();
        
        if (data.status === 'success' && cont) {
            cont.innerHTML = '';
            if (data.data.length === 0) {
                cont.innerHTML = `<div style="text-align:center; padding:20px; color:#94a3b8; font-size: 13px;">No hay registros para mostrar en esta categoría.</div>`; 
                return;
            }
            data.data.forEach(item => {
                const isSmart = tipo === 'Deficit' ? 'smart' : '';
                let textoDetalle = item.detalle;
                if (item.estatus === 'DE' && item.fecha_regreso) {
                    let partesFecha = item.fecha_regreso.split('-'); 
                    textoDetalle = `DE • Regresa ${partesFecha[2]}/${partesFecha[1]}`;
                } else if (item.estatus === 'DE') {
                    textoDetalle = `DE • Sin turno prog.`;
                }

                cont.innerHTML += `
                    <div class="drill-item ${isSmart}">
                        <div style="font-weight: 700; font-size: 13px; color: var(--text-main);">${item.nombre}</div>
                        <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); text-align: right;">${textoDetalle}</div>
                    </div>
                `;
            });
        } else if (cont) { 
            cont.innerHTML = `<div style="text-align:center; padding:20px; color:#ef4444;">Error al cargar datos.</div>`; 
        }
    } catch (e) { 
        if (cont) cont.innerHTML = `<div style="text-align:center; padding:20px; color:#ef4444;">Error de conexión.</div>`; 
    }
}

// 6. ESTATUS EN VIVO (GPS / PIZARRA)
function switchSubTab(subId, btn) {
    document.querySelectorAll('.sub-view-section').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.sub-dock-btn:not(.pred-btn)').forEach(b => b.classList.remove('active'));
    const target = document.getElementById(subId);
    if (target) target.style.display = 'block';
    if (btn) btn.classList.add('active');
}

async function cargarEstatusVivo() {
    const tbodyEntregas = document.getElementById('bodyEstatusVivo');
    const tbodyRetornos = document.getElementById('bodyRetornos');
    const tbodyCheckin = document.getElementById('bodyCheckin');

    if (tbodyEntregas) tbodyEntregas.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:20px; color:#94a3b8;"><i class="fas fa-spinner fa-spin"></i> Sincronizando entregas...</td></tr>';
    
    try {
        const res = await fetch('/api/estatus_vivo_mock');
        const json = await res.json();
        
        if (json.status === 'success') {
            // Entregas
            if (tbodyEntregas) {
                tbodyEntregas.innerHTML = '';
                if (!json.data || json.data.length === 0) {
                    tbodyEntregas.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:30px; color:var(--text-muted); font-weight:600;"><i class="fas fa-clipboard-check" style="font-size:24px; display:block; margin-bottom:10px;"></i>No hay viajes de entrega activos en la Pizarra.</td></tr>';
                } else {
                    const ordenColores = { 'red': 1, 'yellow': 2, 'green': 3, 'blue': 4 };
                    json.data.sort((a, b) => (ordenColores[a.color] || 5) - (ordenColores[b.color] || 5));
                    
                    json.data.forEach(item => {
                        let colorBase = item.color === 'green' ? '#10b981' : item.color === 'yellow' ? '#f59e0b' : item.color === 'blue' ? '#3b82f6' : '#ef4444';
                        let htmlClientes = item.paradas.map(p => `<div class="item-lista">${p.cliente}</div>`).join('');
                        let htmlLlegadas = item.paradas.map(p => `<div class="item-lista">${p.llegada}</div>`).join('');

                        tbodyEntregas.innerHTML += `
                            <tr style="border-bottom: 1px solid var(--border-subtle); background: var(--bg-surface);">
                                <td style="font-weight:bold; color:var(--fng-blue);">${item.eco}</td>
                                <td style="text-align:left; font-weight:600;">${item.operador}</td>
                                <td style="font-weight:bold; color:var(--text-muted);">${item.salida}</td>
                                <td>${item.producto}</td>
                                <td style="font-weight:bold; color:${colorBase};">${item.icon} ${item.estatus}</td>
                                <td>${item.tiempo}</td>
                                <td style="text-align:left; font-size:12px; font-weight:600; color:var(--text-muted);"><div class="lista-celda">${htmlClientes}</div></td>
                                <td style="text-align:left; font-size:12px; font-weight:bold; color:var(--text-muted);"><div class="lista-celda">${htmlLlegadas}</div></td>
                                <td style="text-align:left; font-size:12px; font-weight:600; color:#0284c7;">${item.ubicacion}</td>
                            </tr>
                        `;
                    });
                }
            }

            // Retornos
            if (tbodyRetornos) {
                tbodyRetornos.innerHTML = '';
                if (!json.retornos || json.retornos.length === 0) {
                    tbodyRetornos.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:30px; color:var(--text-muted); font-weight:600;"><i class="fas fa-undo" style="font-size:24px; display:block; margin-bottom:10px;"></i>Sin unidades en ruta de retorno.</td></tr>';
                } else {
                    json.retornos.forEach(item => {
                        let colorBase = item.color === 'green' ? '#10b981' : item.color === 'yellow' ? '#f59e0b' : '#ef4444';
                        tbodyRetornos.innerHTML += `
                            <tr style="border-bottom: 1px solid var(--border-subtle); background: var(--bg-surface);">
                                <td style="font-weight:bold; color:var(--fng-blue);">${item.eco}</td>
                                <td style="text-align:left; font-weight:600;">${item.operador}</td>
                                <td>${item.producto}</td>
                                <td style="font-weight:bold; color:var(--text-muted);">${item.salida}</td>
                                <td style="font-weight:bold; color:var(--text-muted);">${item.llegada_base}</td>
                                <td><span class="badge-status" style="background:${colorBase};">${item.icon} ${item.estatus}</span></td>
                                <td style="text-align:left; font-size:12px; font-weight:600; color:#0284c7;">${item.ubicacion}</td>
                            </tr>
                        `;
                    });
                }
            }

            // Check-in
            if (tbodyCheckin) {
                tbodyCheckin.innerHTML = '';
                if (!json.checkin || json.checkin.length === 0) {
                    tbodyCheckin.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:30px; color:var(--text-muted); font-weight:600;"><i class="fas fa-warehouse" style="font-size:24px; display:block; margin-bottom:10px;"></i>Patio despejado / Sin unidades en inspección.</td></tr>';
                } else {
                    json.checkin.forEach(item => {
                        tbodyCheckin.innerHTML += `
                            <tr style="border-bottom: 1px solid var(--border-subtle); background: var(--bg-surface);">
                                <td style="font-weight:bold; color:var(--fng-blue);">${item.eco}</td>
                                <td style="text-align:left; font-weight:600;">${item.operador}</td>
                                <td style="font-weight:bold; color:var(--text-muted);">${item.llegada}</td>
                                <td><i class="fas fa-check-circle" style="color:#10b981;"></i> ${item.diesel}</td>
                                <td><i class="fas fa-check-circle" style="color:#10b981;"></i> ${item.neumaticos}</td>
                                <td><i class="fas fa-check-circle" style="color:#10b981;"></i> ${item.mecanico}</td>
                                <td style="color:var(--text-muted); font-weight:600;">${item.tiempo}</td>
                                <td><span class="badge-status bg-green">${item.estatus}</span></td>
                            </tr>
                        `;
                    });
                }
            }
        }
    } catch(e) {
        if (tbodyEntregas) tbodyEntregas.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:20px; color:#ef4444;">Error de conexión con el radar.</td></tr>';
    }
}

// 7. PREDICTIVO, CLIENTES Y EQUIDAD
function switchPredictivoTab(tabId, btn) {
    document.querySelectorAll('.sub-pred-section').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.sub-dock-btn.pred-btn').forEach(b => b.classList.remove('active'));
    const target = document.getElementById(tabId);
    if (target) target.style.display = 'block';
    if (btn) btn.classList.add('active');
    if (tabId === 'sub-pred-clientes') {
        cargarAnaliticaClientes();
    }
}

async function cargarPredictivo() {
    const grid = document.getElementById('gridPredictivo');
    const gridEquidad = document.getElementById('gridEquidadDespacho');
    if (grid) grid.innerHTML = '<div style="text-align:center; padding:20px; color:#94a3b8;"><i class="fas fa-spinner fa-spin"></i> Generando proyecciones a 15 días...</div>';
    if (gridEquidad) gridEquidad.innerHTML = '<div style="grid-column: 1 / -1; text-align:center; padding:20px; color:#94a3b8;"><i class="fas fa-spinner fa-spin"></i> Auditando asignaciones de viajes...</div>';

    try {
        const res = await fetch('/api/resumen_predictivo');
        const json = await res.json();
        
        if (json.status === 'success') {
            if (grid) {
                grid.innerHTML = '';
                if (json.data.length === 0) {
                    grid.innerHTML = '<div style="text-align:center; padding:30px; color:#10b981; font-weight:bold; font-size: 16px;"><i class="fas fa-check-circle" style="font-size:30px; display:block; margin-bottom:10px;"></i> Todo despejado. No hay alertas críticas planificadas a 15 días.</div>';
                } else {
                    let agrupado = {};
                    json.data.forEach(item => {
                        if (!agrupado[item.fecha]) {
                            agrupado[item.fecha] = { titulo: item.texto_dias, items: [] };
                        }
                        agrupado[item.fecha].items.push(item);
                    });

                    let fechasOrdenadas = Object.keys(agrupado).sort();
                    grid.style.display = 'flex';
                    grid.style.overflowX = 'auto';
                    grid.style.gap = '15px';
                    grid.style.paddingBottom = '15px';

                    fechasOrdenadas.forEach(fecha => {
                        let col = document.createElement('div');
                        col.style.minWidth = '220px';
                        col.style.maxWidth = '240px';
                        col.style.flex = '1';
                        col.style.background = 'var(--bg-surface-2)';
                        col.style.padding = '12px';
                        col.style.borderRadius = '12px';
                        col.style.border = '1px solid var(--border-subtle)';
                        
                        let formatFecha = fecha.split('-').reverse().join('/'); 
                        let tituloDia = agrupado[fecha].titulo.toUpperCase();
                        
                        let html = `
                            <div style="font-weight:800; color:var(--text-main); font-size:13px; margin-bottom:12px; border-bottom:2px solid var(--border-subtle); padding-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
                                <span>${tituloDia}</span> 
                                <span style="font-size:10px; color:var(--text-muted); font-weight:600; background:var(--input-bg); padding:2px 6px; border-radius:8px;">${formatFecha}</span>
                            </div>
                        `;
                        
                        agrupado[fecha].items.forEach(item => {
                            html += `
                                <div class="predictivo-card ${item.color}" style="margin-bottom: 10px;">
                                    <div style="font-size: 16px; color: var(--fng-blue); opacity: 0.8; width: 25px; text-align:center;"><i class="fas ${item.icon}"></i></div>
                                    <div>
                                        <div style="font-size: 9px; font-weight: 800; text-transform: uppercase; color: var(--text-muted); margin-bottom: 3px;">${item.tipo}</div>
                                        <div style="font-size: 12px; font-weight: 600; color: var(--text-main); line-height: 1.3;">${item.mensaje}</div>
                                    </div>
                                </div>
                            `;
                        });
                        
                        col.innerHTML = html;
                        grid.appendChild(col);
                    });
                }
            }

            // Auditoría de Equidad (Gerencia)
            if (gridEquidad && json.auditoria_equidad) {
                gridEquidad.innerHTML = '';
                if (json.auditoria_equidad.length === 0) {
                    gridEquidad.innerHTML = `
                        <div style="grid-column: 1 / -1; text-align:center; padding:35px; background:var(--bg-surface); border-radius:12px; border:1px solid var(--border-subtle);">
                            <i class="fas fa-check-circle" style="font-size:36px; color:#10b981; margin-bottom:10px; display:block;"></i>
                            <h4 style="margin:0; color:var(--text-main);">Distribución Equitativa Confirmada</h4>
                            <p style="margin:5px 0 0 0; color:var(--text-muted); font-size:13px;">No se registran desviaciones anormales de sobrecarga pesada ni privilegios en los últimos 45 días.</p>
                        </div>
                    `;
                } else {
                    json.auditoria_equidad.forEach(eq => {
                        let borderHex = eq.color === 'red' ? '#ef4444' : '#f59e0b';
                        let bgTag = eq.color === 'red' ? '#fee2e2' : '#fef3c7';
                        let textTag = eq.color === 'red' ? '#b91c1c' : '#b45309';

                        gridEquidad.innerHTML += `
                            <div style="background: var(--bg-surface); border: 1px solid var(--border-subtle); border-left: 6px solid ${borderHex}; border-radius: 12px; padding: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.03);">
                                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                                    <h4 style="margin:0; font-size:15px; color:var(--text-main); font-weight:800;">${eq.operador}</h4>
                                    <span style="font-size:10.5px; font-weight:800; background:${bgTag}; color:${textTag}; padding:3px 8px; border-radius:6px;">
                                        <i class="fas ${eq.icono}"></i> ${eq.tipo}
                                    </span>
                                </div>
                                <p style="margin:6px 0; font-size:13px; font-weight:600; color:var(--text-muted);">${eq.detalle}</p>
                                <div style="margin-top:10px; padding-top:8px; border-top:1px dashed var(--border-subtle); font-size:11px; color:var(--text-muted); font-weight:600;">
                                    <i class="fas fa-info-circle"></i> ${eq.alerta}
                                </div>
                            </div>
                        `;
                    });
                }
            }
        }
    } catch(e) {
        if (grid) grid.innerHTML = '<div style="text-align:center; padding:20px; color:#ef4444;">Error al cargar predicciones</div>';
    }
}

async function cargarAnaliticaClientes() {
    try {
        const res = await fetch('/api/analitica_clientes');
        const json = await res.json();
        if (json.status === 'success') {
            const labels = json.data.map(d => d.cliente);
            const loxData = json.data.map(d => d.productos.LOX);
            const linData = json.data.map(d => d.productos.LIN);
            const larData = json.data.map(d => d.productos.LAR);
            const co2Data = json.data.map(d => d.productos.CO2);
            
            if (clientesChartInstance) clientesChartInstance.destroy();
            const canvasCli = document.getElementById('clientesChart');
            if (canvasCli) {
                const ctx = canvasCli.getContext('2d');
                clientesChartInstance = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [
                            { label: 'Oxígeno', data: loxData, backgroundColor: '#3b82f6' },
                            { label: 'Nitrógeno', data: linData, backgroundColor: '#8b5cf6' },
                            { label: 'Argón', data: larData, backgroundColor: '#0ea5e9' },
                            { label: 'CO2', data: co2Data, backgroundColor: '#64748b' }
                        ]
                    },
                    options: { 
                        responsive: true, 
                        maintainAspectRatio: false, 
                        scales: { x: { stacked: true }, y: { stacked: true } }, 
                        plugins: { legend: { position: 'bottom' } } 
                    }
                });
            }
            
            const grid = document.getElementById('gridClientesPredictivo');
            if (!grid) return;
            grid.innerHTML = '';
            
            if (json.data.length === 0) {
                grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:20px;">Esperando registro de viajes para generar analítica.</div>';
                return;
            }

            const nombreProducto = { 'LOX': 'Oxígeno', 'LIN': 'Nitrógeno', 'LAR': 'Argón', 'CO2': 'CO2' };
            window.datosClientesAnalitica = json.data;

            json.data.forEach((item, idx) => {
                let estadoColor = 'green';
                let estadoIcon = 'check-circle';
                let estadoTexto = 'Abastecido';
                
                if (item.frecuencia_promedio > 0) {
                    if (item.dias_transcurridos > item.frecuencia_promedio + 1) {
                        estadoColor = 'red'; estadoIcon = 'exclamation-triangle'; estadoTexto = 'Riesgo de Desabasto';
                    } else if (item.dias_transcurridos >= item.frecuencia_promedio - 1) {
                        estadoColor = 'yellow'; estadoIcon = 'clock'; estadoTexto = 'Ventana de Pedido';
                    }
                }
                
                let cardColorHex = estadoColor === 'green' ? '#10b981' : estadoColor === 'yellow' ? '#f59e0b' : '#ef4444';
                let prodColor = item.producto_dominante === 'CO2' ? '#64748b' : 'var(--fng-blue)';
                let formatFecha = item.ultima_fecha.split('-').reverse().join('/');
                let textoHace = item.dias_transcurridos === 0 ? 'Hoy' : `Hace ${item.dias_transcurridos} días`;
                let frecStr = item.frecuencia_promedio > 0 ? `Cada ${item.frecuencia_promedio} días` : 'Variable';

                let html = `
                    <div style="background: var(--bg-surface); border-radius: 12px; border: 1px solid var(--border-subtle); border-left: 5px solid ${cardColorHex}; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); cursor: pointer; transition: transform 0.2s;" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'" onclick="abrirHistorialCliente(${idx})">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 10px;">
                            <h5 style="margin: 0; font-size: 14px; color: var(--text-main); line-height: 1.2; word-break: break-word; padding-right:10px;">${item.cliente}</h5>
                            <span style="font-size: 11px; font-weight: bold; background: var(--bg-surface-2); color: ${prodColor}; padding: 3px 8px; border-radius: 10px;">${nombreProducto[item.producto_dominante] || item.producto_dominante}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom: 8px;">
                            <span style="font-size: 12px; color: var(--text-muted);"><i class="fas fa-calendar-check"></i> Última: <b>${formatFecha}</b></span>
                            <span style="font-size: 12px; font-weight: 700; color: var(--text-main);">${textoHace}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items: center;">
                            <span style="font-size: 12px; color: var(--text-muted);"><i class="fas fa-sync-alt"></i> Ritmo: <b>${frecStr}</b></span>
                            <span style="font-size: 11px; font-weight: 800; color: ${cardColorHex};"><i class="fas fa-${estadoIcon}"></i> ${estadoTexto}</span>
                        </div>
                    </div>
                `;
                grid.insertAdjacentHTML('beforeend', html);
            });
        }
    } catch(e) {
        const grid = document.getElementById('gridClientesPredictivo');
        if (grid) grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:20px; color:#ef4444;">Error al cargar analítica de clientes.</div>';
    }
}

function abrirHistorialCliente(index) {
    const cliente = (window.datosClientesAnalitica || [])[index];
    if (!cliente) return;

    const nombreProd = { 'LOX': 'Oxígeno', 'LIN': 'Nitrógeno', 'LAR': 'Argón', 'CO2': 'CO2' };
    const colorBadges = {
        'Oxígeno': 'background: #e0f2fe; color: #0284c7;',
        'Nitrógeno': 'background: #f3e8ff; color: #7e22ce;',
        'Argón': 'background: #e0f7fa; color: #00838f;',
        'CO2': 'background: #f1f5f9; color: #475569;'
    };

    const elNombre = document.getElementById('histClienteNombre');
    const elSub = document.getElementById('histClienteSub');
    if (elNombre) elNombre.innerHTML = `<i class="fas fa-industry" style="color: var(--fng-orange);"></i> ${cliente.cliente}`;
    if (elSub) elSub.innerText = `Línea Principal: ${nombreProd[cliente.producto_dominante] || cliente.producto_dominante} | Frecuencia: Cada ${cliente.frecuencia_promedio} días`;

    const tbody = document.getElementById('histTablaCuerpo');
    if (!tbody) return;
    tbody.innerHTML = '';

    let sumaTon = 0;
    const historial = cliente.historial_30d || [];

    if (historial.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:15px; color:var(--text-muted);">No hay viajes detallados en el periodo.</td></tr>';
    } else {
        historial.forEach(v => {
            sumaTon += parseFloat(v.toneladas || 0);
            let fPartes = v.fecha.split('-');
            let fFormato = `${fPartes[2]}/${fPartes[1]}/${fPartes[0]}`;
            let estiloBadge = colorBadges[v.producto] || 'background: var(--bg-surface-2); color: var(--text-main);';

            tbody.innerHTML += `
                <tr style="border-bottom: 1px solid var(--border-subtle); font-size: 12px;">
                    <td style="padding: 7px; font-weight: 700; color: var(--text-muted);">${fFormato}</td>
                    <td style="padding: 7px;">
                        <span style="font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px; ${estiloBadge}">
                            ${v.producto}
                        </span>
                    </td>
                    <td style="padding: 7px; text-align: left; font-weight: 600; color: var(--fng-blue);">${v.operador}</td>
                    <td style="padding: 7px;">${v.eco} / ${v.pipa}</td>
                    <td style="padding: 7px; font-weight: 800; color: #10b981;">${(parseFloat(v.toneladas) || 0).toFixed(1)} Ton</td>
                </tr>
            `;
        });
    }

    const elTotal = document.getElementById('histTotalTon');
    if (elTotal) elTotal.innerText = `${sumaTon.toFixed(1)} Ton`;
    const modal = document.getElementById('modalClienteHistorial');
    if (modal) modal.style.display = 'flex';
}