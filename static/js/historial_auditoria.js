/* ========================================================
   GRUPO FNG - MÓDULO DE HISTORIAL Y AUDITORÍA INTEGRAL
   Filtros 48h, Inspector de Novedades, Galería y Exportación
   ======================================================== */

// 1. INICIALIZACIÓN Y EVENTOS
window.addEventListener('DOMContentLoaded', () => {
    const inputBuscador = document.getElementById('buscadorHistorial');
    if (inputBuscador) {
        inputBuscador.addEventListener('input', filtrarHistorial);
    }
});

// 2. CONMUTADOR DE PESTAÑAS Y MÓDULOS
function cambiarModuloHistorial(moduloId, btn) {
    document.querySelectorAll('.modulo-app').forEach(m => m.classList.remove('active'));
    document.querySelectorAll('.tab-historial-btn').forEach(b => b.classList.remove('active'));

    const target = document.getElementById(moduloId);
    if (target) target.classList.add('active');
    if (btn) btn.classList.add('active');
}

// 3. FILTRADO DINÁMICO EN TIEMPO REAL
function filtrarHistorial() {
    const termino = (document.getElementById('buscadorHistorial')?.value || '').toLowerCase().trim();
    const filtroTipo = document.getElementById('filtroTipoActivo')?.value || 'TODOS';
    const filas = document.querySelectorAll('.fila-historial');

    filas.forEach(fila => {
        const texto = fila.textContent.toLowerCase();
        const tipoFila = fila.getAttribute('data-tipo') || '';

        const coincideTexto = texto.includes(termino);
        const coincideTipo = (filtroTipo === 'TODOS' || tipoFila === filtroTipo);

        fila.style.display = (coincideTexto && coincideTipo) ? '' : 'none';
    });
}

function filtrarPorRango48h() {
    const fechaActual = new Date();
    const hace48h = new Date(fechaActual.getTime() - (48 * 60 * 60 * 1000));
    const filas = document.querySelectorAll('.fila-historial');

    filas.forEach(fila => {
        const fechaFilaStr = fila.getAttribute('data-timestamp');
        if (!fechaFilaStr) return;
        const fechaFila = new Date(fechaFilaStr);
        fila.style.display = (fechaFila >= hace48h) ? '' : 'none';
    });
    showToast("Filtrado: Últimas 48 horas de operación", "info");
}

function reestablecerFiltroTiempo() {
    document.querySelectorAll('.fila-historial').forEach(f => f.style.display = '');
    const inputBuscador = document.getElementById('buscadorHistorial');
    if (inputBuscador) inputBuscador.value = '';
    showToast("Filtros reestablecidos", "success");
}

// 4. INSPECTOR MODAL DE DETALLE Y NOVEDADES
function abrirDetalleHistorial(idRegistro, jsonDetalles) {
    let datos = {};
    try {
        datos = typeof jsonDetalles === 'string' ? JSON.parse(jsonDetalles) : jsonDetalles;
    } catch (e) {
        datos = {};
    }

    const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = val || '--';
    };

    setText('detFolio', datos.folio || idRegistro);
    setText('detFecha', datos.fecha || '--');
    setText('detTipo', datos.tipo || '--');
    setText('detUsuario', datos.usuario || 'Sistema');
    setText('detObservaciones', datos.observaciones || 'Sin incidencias reportadas');

    const contEvidencias = document.getElementById('detContenedorEvidencias');
    if (contEvidencias) {
        contEvidencias.innerHTML = '';
        const fotos = datos.fotos || [];

        if (fotos.length > 0) {
            fotos.forEach(fotoUrl => {
                const img = document.createElement('img');
                img.src = fotoUrl;
                img.className = 'preview-box';
                img.style.cursor = 'pointer';
                img.onclick = () => verEvidenciaAmpliada(fotoUrl);
                contEvidencias.appendChild(img);
            });
        } else {
            contEvidencias.innerHTML = '<span style="font-size:12px; color:var(--text-muted);">Sin evidencia fotográfica</span>';
        }
    }

    const modal = document.getElementById('modalDetalleHistorial');
    if (modal) modal.style.display = 'flex';
}

function cerrarDetalleHistorial() {
    const modal = document.getElementById('modalDetalleHistorial');
    if (modal) modal.style.display = 'none';
}

// 5. VISOR FLOTANTE DE EVIDENCIAS (FOTO-GALERÍA)
function verEvidenciaAmpliada(urlFoto) {
    const visor = document.getElementById('imgFotoGaleria');
    const modal = document.getElementById('modalGaleriaFoto');
    if (visor && modal) {
        visor.src = urlFoto;
        modal.style.display = 'flex';
    }
}

function cerrarGaleriaFoto() {
    const modal = document.getElementById('modalGaleriaFoto');
    if (modal) modal.style.display = 'none';
}

// 6. EXPORTACIÓN MASIVA (ZIP / PDF)
async function exportarReporteHistorial(tipoFormato) {
    const fInicio = document.getElementById('fecha_inicio_export')?.value;
    const fFin = document.getElementById('fecha_fin_export')?.value;

    if (!fInicio || !fFin) {
        showToast("⚠️ Define el rango de fechas para exportar", "warning");
        return;
    }

    showToast(`Preparando paquete ${tipoFormato.toUpperCase()}...`, "info");

    try {
        const endpoint = tipoFormato === 'zip' ? '/api/exportar_zip_evidencias' : '/api/exportar_pdf_auditoria';
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fecha_inicio: fInicio, fecha_fin: fFin })
        });

        if (res.ok) {
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Auditoria_${fInicio}_al_${fFin}.${tipoFormato}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            showToast("Descarga masiva generada exitosamente", "success");
        } else {
            showToast("No se encontraron registros en el rango seleccionado", "warning");
        }
    } catch (e) {
        showToast("Error de conexión durante la exportación", "warning");
    }
}