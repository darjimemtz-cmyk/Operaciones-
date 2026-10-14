/* ========================================================
   GRUPO FNG - MÓDULO DE HISTORIAL Y AUDITORÍA INTEGRAL
   Control de E/S, Novedades, Galería y Filtros Reales
   ======================================================== */

// 1. NAVEGACIÓN DE MÓDULOS Y SUB-PESTAÑAS
function abrirModulo(modId, btn) {
    document.querySelectorAll('.modulo-app').forEach(m => m.classList.remove('active'));
    document.querySelectorAll('.glass-pill-btn').forEach(b => {
        if (b.closest('.glass-panel') === document.querySelector('.glass-panel')) {
            b.classList.remove('active-blue');
        }
    });
    const target = document.getElementById(modId);
    if (target) target.classList.add('active');
    if (btn) btn.classList.add('active-blue');
    window.scrollTo(0, 0);
}

function verTab(btnElement, id) {
    const modulo = btnElement.closest('.modulo-app');
    if (!modulo) return;
    modulo.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    modulo.querySelectorAll('.glass-pill-btn').forEach(b => b.classList.remove('active-blue'));
    
    const target = document.getElementById(id);
    if (target) target.classList.add('active');
    btnElement.classList.add('active-blue');
}

// 2. INSPECTOR DE DATOS (DETALLE DE REGISTRO)
function abrirDetalle(e, btn, tipo, fecha, obs, fotosStr) {
    if (e) e.stopPropagation();
    const rawData = btn.dataset.info;
    let datos = {};
    try { datos = JSON.parse(rawData); } catch (err) { console.error("Error parseando JSON", err); }
    
    const titulo = document.getElementById('det-titulo');
    const fechaEl = document.getElementById('det-fecha');
    const grid = document.getElementById('det-grid');
    if (titulo) titulo.innerHTML = `<i class="fas fa-file-invoice"></i> Reporte: ${tipo}`;
    if (fechaEl) fechaEl.innerHTML = `<i class="far fa-clock"></i> ${fecha}`;
    if (grid) grid.innerHTML = '';
    
    const ignoreKeys = ['firma_data', 'firma_guardia_data', 'tipo_formulario', 'herramientas_desc', 'herramientas_cant', 'verificaciones_salida', 'estatus_herramienta', 'fecha_salida', 'resultado', 'foto_alcoholimetro_ingreso', 'fecha_ingreso_completa', 'movimiento'];
    
    if (tipo !== 'UNIDAD') {
        ignoreKeys.push('estatus_carga', 'estatus_carga_salida', 'config_unidad', 'eco_remolque_1', 'eco_remolque_2', 'eco_dolly', 'linea');
    }
    if (tipo === 'EMPLEADO' || tipo === 'EXTERNO' || tipo === 'PERSONAL EXTERNO' || tipo === 'UTILITARIO') {
        ignoreKeys.push('identificador'); 
    }

    for (let key in datos) {
        if (ignoreKeys.includes(key)) continue;
        let val = datos[key];
        
        if (val === '' || val === 'N/A' || val === null) continue;
        if (Array.isArray(val)) {
            let validItems = val.filter(v => v !== null && String(v).trim() !== '');
            if (validItems.length === 0) continue;
            val = validItems.join(' | ');
        }
        
        let cleanKey = key.replace('[]', '').replace(/_/g, ' ').toUpperCase();
        let div = document.createElement('div');
        div.className = 'data-box';
        div.style.cssText = "display: flex; justify-content: space-between; align-items: center; padding: 12px 15px;";
        div.innerHTML = `<span style="font-size: 11px; color: var(--text-muted); font-weight: 700; width: 40%; text-transform: uppercase;">${cleanKey}</span>
                         <span style="font-size: 13px; color: var(--text-main); font-weight: 600; text-align: right; width: 60%; word-break: break-word;">${val}</span>`;
        if (grid) grid.appendChild(div);
    }
    
    const obsCont = document.getElementById('det-obs-container');
    const obsTexto = document.getElementById('det-obs');
    if (obs && obs !== 'N/A' && obs !== 'SALIDA REGISTRADA' && !obs.toLowerCase().includes('.jpg') && !obs.toLowerCase().includes('.png')) {
        if (obsCont) obsCont.style.display = 'block';
        if (obsTexto) obsTexto.innerText = obs;
    } else {
        if (obsCont) obsCont.style.display = 'none';
    }

    const mediaPane = document.getElementById('det-media-pane');
    const fotosGrid = document.getElementById('det-fotos-grid');
    if (fotosGrid) fotosGrid.innerHTML = '';
    
    let arrayFotos = [];
    if (fotosStr && fotosStr.trim() !== '') {
        arrayFotos = arrayFotos.concat(fotosStr.split(',').map(f => f.trim()));
    }
    if (datos.foto_alcoholimetro_ingreso && datos.foto_alcoholimetro_ingreso !== 'N/A') {
        arrayFotos.push(datos.foto_alcoholimetro_ingreso);
    }

    arrayFotos = [...new Set(arrayFotos.filter(f => f && f.trim() !== ''))];

    if (arrayFotos.length > 0 && mediaPane && fotosGrid) {
        mediaPane.style.display = 'flex';
        arrayFotos.forEach(f => {
            let thumb = document.createElement('img');
            thumb.src = '/static/evidencias/' + f;
            thumb.style.cssText = "width: 100px; height: 130px; object-fit: cover; border-radius: 8px; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.1); border: 1px solid var(--border-subtle); transition: 0.3s;";
            thumb.onclick = () => abrirGaleria(f); 
            thumb.onmouseover = () => thumb.style.boxShadow = "0 0 12px rgba(255,140,0,0.8)";
            thumb.onmouseout = () => thumb.style.boxShadow = "0 4px 10px rgba(0,0,0,0.1)";
            fotosGrid.appendChild(thumb);
        });
    } else if (mediaPane) {
        mediaPane.style.display = 'none';
    }
    
    const modal = document.getElementById('modal-detalle');
    if (modal) modal.style.display = 'flex';
}

function cerrarDetalle(e, force = false) {
    if (force || (e && e.target && e.target.id === 'modal-detalle')) {
        const modal = document.getElementById('modal-detalle');
        if (modal) modal.style.display = 'none';
    }
}

// 3. GALERÍA DE FOTOS
function abrirGaleria(fotosStr) {
    const cont = document.getElementById('contenedor-fotos-galeria');
    if (!cont) return;
    cont.innerHTML = '';
    fotosStr.split(',').forEach(f => {
        if (f.trim()) {
            const img = document.createElement('img');
            img.src = '/static/evidencias/' + f.trim();
            img.className = 'foto-galeria';
            cont.appendChild(img);
        }
    });
    const modal = document.getElementById('modal-galeria');
    if (modal) modal.style.display = 'flex';
}

function cerrarGaleria() { 
    const modal = document.getElementById('modal-galeria');
    if (modal) modal.style.display = 'none'; 
}

// 4. VIAJES EN EL TIEMPO Y EXPORTACIÓN
function viajarEnElTiempo(fecha) {
    if (!fecha) return;
    const urlParams = new URLSearchParams(window.location.search);
    urlParams.set('fecha_auditoria', fecha);
    window.location.href = "/historial?" + urlParams.toString();
}

function checkMovimiento(tipo) {
    const selectMov = document.getElementById('select-movimiento-pdf');
    if (!selectMov) return;
    if (tipo === 'unidades_fng') {
        selectMov.style.display = 'block'; 
        if (selectMov.value === 'TODOS') selectMov.value = 'ENTRA';
    } else {
        selectMov.style.display = 'none';
        selectMov.value = 'TODOS';
    }
}

// 5. INICIALIZADOR DE EVENTOS
window.addEventListener('DOMContentLoaded', () => {
    const inputBuscador = document.getElementById('buscador');
    if (inputBuscador) {
        inputBuscador.addEventListener('keyup', function() {
            let f = this.value.toLowerCase();
            document.querySelectorAll('#tabla-general tbody tr').forEach(row => {
                row.style.display = row.innerText.toLowerCase().includes(f) ? '' : 'none';
            });
        });
    }

    const tipoSelect = document.getElementById('select-tipo-pdf');
    if (tipoSelect) checkMovimiento(tipoSelect.value);

    const urlParams = new URLSearchParams(window.location.search);
    const fechaFiltro = urlParams.get('fecha_auditoria');
    const cal = document.getElementById('filtro-calendario');
    if (fechaFiltro && cal) cal.value = fechaFiltro;
});