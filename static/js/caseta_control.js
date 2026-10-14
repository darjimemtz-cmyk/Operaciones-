/* ========================================================
   GRUPO FNG - MÓDULO CASETA Y CONTROL DE ACCESOS
   Cámara Alcoholímetro, CTPAT, Salidas con Fotos y Mi Turno
   ======================================================== */

// 1. NAVEGACIÓN ENTRE SECCIONES DE CASETA
function abrirSeccion(id, btn) {
    document.querySelectorAll('.seccion-app').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.glass-pill-btn').forEach(b => b.classList.remove('active-blue'));
    const target = document.getElementById(id);
    if (target) target.classList.add('active');
    if (btn) btn.classList.add('active-blue');
    if (id === 'sec-turno') cargarMiTurno();
}

function abrirMenuNuevo() { 
    const modal = document.getElementById('modal-menu-nuevo');
    if (modal) modal.style.display = 'flex'; 
}

function cerrarMenuNuevo(e, force = false) {
    if (force || (e && e.target && e.target.id === 'modal-menu-nuevo')) {
        const modal = document.getElementById('modal-menu-nuevo');
        if (modal) modal.style.display = 'none';
    }
}

function cerrarModal(id) { 
    const modal = document.getElementById(id);
    if (modal) modal.style.display = 'none'; 
}

function filtrarTabla(tipo, btn) {
    const group = btn.parentElement;
    group.querySelectorAll('.glass-pill-btn').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.fila-activo').forEach(f => {
        f.style.display = (tipo === 'TODOS' || f.dataset.tipo === tipo) ? '' : 'none';
    });
}

function cambiarTipoReporte(tipo, btn) {
    const group = btn.parentElement;
    group.querySelectorAll('.glass-pill-btn').forEach(c => c.classList.remove('active', 'active-red'));
    if (tipo === 'NOVEDAD') btn.classList.add('active-red');
    else btn.classList.add('active');
    const input = document.getElementById('tipo_reporte_input');
    if (input) input.value = tipo;
}

// 2. FORMULARIO DINÁMICO DE INGRESO
function abrirFormIngreso(tipo) {
    cerrarMenuNuevo(null, true);
    const titulo = document.getElementById('titulo-ingreso');
    const inputTipo = document.getElementById('input-tipo-activo');
    if (titulo) titulo.innerText = `Registrar ${tipo}`;
    if (inputTipo) inputTipo.value = tipo;
    
    document.querySelectorAll('.campos-dinamicos').forEach(div => {
        div.style.display = 'none';
        div.querySelectorAll('input, select, textarea').forEach(inp => inp.disabled = true);
    });
    
    const activeDiv = document.getElementById(`campos-${tipo.toLowerCase()}`);
    if (activeDiv) {
        activeDiv.style.display = 'block';
        activeDiv.querySelectorAll('input, select, textarea').forEach(inp => {
            if (inp.type !== 'hidden') inp.disabled = false;
        });
    }

    const bloqueAlc = document.getElementById('bloque-alcoholimetro');
    if (bloqueAlc) {
        bloqueAlc.style.display = 'block';
        bloqueAlc.querySelectorAll('input').forEach(i => i.disabled = false);
    }

    const secEquipo = document.getElementById('seccion-equipo-compartido');
    if (tipo === 'EXTERNO' || tipo === 'EMPLEADO') {
        if (secEquipo) secEquipo.style.display = 'block';
    } else {
        if (secEquipo) secEquipo.style.display = 'none';
        toggleEquipo('NO'); 
    }

    if (tipo === 'UNIDAD' && activeDiv) {
        let b = activeDiv.querySelector('.btn-toggle');
        if (b) setConfigUnidad('TRACTO', b);
    }
    if (tipo === 'UTILITARIO' && activeDiv) {
        let b = activeDiv.querySelector('.btn-toggle');
        if (b) setMovUtilitario('ENTRADA', b);
    }
    
    const modalIngreso = document.getElementById('modal-ingreso');
    if (modalIngreso) modalIngreso.style.display = 'flex';
}

// 3. CHECKLIST CTPAT
const ctpatBase = ["1. Defensa y Cofre", "2. Motor", "3. Llantas y Rines", "4. Piso y Chasis", "5. Tanques de Aire/Diésel", "6. Cabina y Litera", "7. Baterías", "8. Quinta Rueda"];
const ctpatSencillo = ["9. R1: Pared exterior", "10. R1: Pisos y techos interiores", "11. R1: Puertas y Bisagras", "12. R1: Mecanismo de cierre", "13. R1: Sellos de Seguridad"];
const ctpatFull = ["14. Dolly: Chasis y Quinta Rueda", "15. Dolly: Líneas y Llantas", "16. R2: Pared exterior", "17. R2: Techos y Puertas", "18. R2: Sellos de Seguridad"];

function setConfigUnidad(config, btn) {
    setToggle(btn, 'config_unidad', config, 'active');
    const reqR1 = document.getElementById('eco_r1');
    const secDollyR2 = document.getElementById('seccion-dolly-r2');
    const reqDolly = document.getElementById('eco_dolly');
    const reqR2 = document.getElementById('eco_r2');
    const secRemolques = document.getElementById('seccion-remolques');
    
    if (config === 'TRACTO') {
        if (secRemolques) secRemolques.style.display = 'none';
        if (reqR1) reqR1.required = false;
        if (reqDolly) reqDolly.required = false;
        if (reqR2) reqR2.required = false;
        if (secDollyR2) secDollyR2.style.display = 'none';
    } else if (config === 'SENCILLO') {
        if (secRemolques) secRemolques.style.display = 'block';
        if (secDollyR2) secDollyR2.style.display = 'none';
        if (reqR1) reqR1.required = true;
        if (reqDolly) reqDolly.required = false;
        if (reqR2) reqR2.required = false;
    } else {
        if (secRemolques) secRemolques.style.display = 'block';
        if (secDollyR2) secDollyR2.style.display = 'block';
        if (reqR1) reqR1.required = true;
        if (reqDolly) reqDolly.required = true;
        if (reqR2) reqR2.required = true;
    }
    renderCTPAT(config);
}

function renderCTPAT(config) {
    let pts = [...ctpatBase];
    if (config === 'SENCILLO' || config === 'FULL') pts = pts.concat(ctpatSencillo);
    if (config === 'FULL') pts = pts.concat(ctpatFull);

    let html = '';
    pts.forEach((p, i) => {
        html += `
        <div class="check-item" style="display:block;">
            <label style="margin-top:0; font-size:12px; text-transform:none;"><b>${p}</b></label>
            <input type="hidden" name="ctpat_${i}" id="ctpat_val_${i}" value="BUENO">
            <div class="btn-group" style="margin-top:5px; margin-bottom:5px;">
                <div class="btn-toggle active green-text" style="padding:8px; font-size:12px;" onclick="setToggleCTPAT(this, 'ctpat_val_${i}', 'BUENO', 'active', 'green-text', ${i})">✔️ BUENO</div>
                <div class="btn-toggle" style="padding:8px; font-size:12px;" onclick="setToggleCTPAT(this, 'ctpat_val_${i}', 'MALO', 'active', 'red-text', ${i})">❌ MALO</div>
            </div>
            <div id="ctpat_obs_div_${i}" style="display:none; margin-top:5px;">
                <textarea name="ctpat_obs_${i}" id="ctpat_obs_inp_${i}" class="form-control-local" rows="1" placeholder="Detalle la anomalía..." style="font-size:12px; padding:8px;"></textarea>
            </div>
        </div>`;
    });
    const cont = document.getElementById('ctpat-container');
    if (cont) cont.innerHTML = html;
}

function setToggleCTPAT(btn, inputId, val, activeClass, textColorClass, idx) {
    const group = btn.parentElement;
    group.querySelectorAll('.btn-toggle').forEach(b => {
        b.classList.remove('active', 'green-text', 'red-text');
    });
    btn.classList.add(activeClass, textColorClass);
    const input = document.getElementById(inputId);
    if (input) input.value = val;
    
    const obsDiv = document.getElementById('ctpat_obs_div_' + idx);
    const obsInp = document.getElementById('ctpat_obs_inp_' + idx);
    if (val === 'MALO') {
        if (obsDiv) obsDiv.style.display = 'block'; 
        if (obsInp) obsInp.required = true;
    } else {
        if (obsDiv) obsDiv.style.display = 'none'; 
        if (obsInp) {
            obsInp.required = false; 
            obsInp.value = '';
        }
    }
}

function setMovUtilitario(mov, btn) {
    setToggle(btn, 'mov_utilitario', mov, 'active');
    const divAlc = document.getElementById('bloque-alcoholimetro');
    if (!divAlc) return;
    if (mov === 'ENTRADA') {
        divAlc.style.display = 'block';
        divAlc.querySelectorAll('input').forEach(i => i.disabled = false);
    } else {
        divAlc.style.display = 'none';
        divAlc.querySelectorAll('input').forEach(i => i.disabled = true);
        let toggleNO = divAlc.querySelector('.btn-toggle');
        if (toggleNO) toggleAlcIngreso(toggleNO, 'NO');
    }
}

// 4. CONTROL DE CÁMARA PARA ALCOHOLÍMETRO
let streamAlc = null;

function toggleAlcIngreso(btn, val) {
    const group = btn.parentElement;
    group.querySelectorAll('.btn-toggle').forEach(b => {
        b.classList.remove('active', 'green-text', 'red-text');
    });
    btn.classList.add('active');
    if (val === 'SI') btn.classList.add('red-text');
    else btn.classList.add('green-text');

    const divRes = document.getElementById('contenedor-res-alc-ingreso');
    const inputRes = document.getElementById('input-res-alc-ingreso');
    const btnEvi = document.getElementById('btn-evidencia-alc');
    const inputFoto = document.getElementById('input-foto-alc-b64');

    if (val === 'SI') { 
        if (divRes) divRes.style.display = 'block'; 
        if (inputRes) inputRes.value = ''; 
        if (btnEvi) {
            btnEvi.innerHTML = '<i class="fas fa-camera"></i> Evidencia fotográfica';
            btnEvi.className = 'btn-action btn-outline';
        }
    } else { 
        if (divRes) divRes.style.display = 'none'; 
        if (inputRes) inputRes.value = 'N/A'; 
        if (inputFoto) inputFoto.value = ''; 
    }
}

async function abrirCamaraAlcohol() {
    const modalCam = document.getElementById('modal-camara');
    if (modalCam) modalCam.style.display = 'flex';
    document.getElementById('btn-tomar-foto').style.display = 'block';
    document.getElementById('controles-foto').style.display = 'none';
    document.getElementById('foto-preview').style.display = 'none';
    
    const video = document.getElementById('video-alc');
    if (video) video.style.display = 'block';

    try {
        streamAlc = await navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: 'environment', aspectRatio: { exact: 0.75 } }, 
            audio: false 
        });
        if (video) video.srcObject = streamAlc;
    } catch (err) {
        try {
            streamAlc = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
            if (video) video.srcObject = streamAlc;
        } catch(e) { 
            alert("Permisos de cámara denegados o dispositivo no disponible."); 
        }
    }
}

function tomarFotoAlc() {
    const video = document.getElementById('video-alc');
    const canvas = document.getElementById('canvas-alc');
    if (!video || !canvas) return;

    canvas.width = video.videoWidth; 
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    
    const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
    const preview = document.getElementById('foto-preview');
    const inputB64 = document.getElementById('input-foto-alc-b64');
    
    if (preview) preview.src = dataUrl;
    if (inputB64) inputB64.value = dataUrl;

    video.style.display = 'none';
    if (preview) preview.style.display = 'block';
    document.getElementById('btn-tomar-foto').style.display = 'none';
    document.getElementById('controles-foto').style.display = 'flex';
}

function rechazarFotoAlc() {
    const preview = document.getElementById('foto-preview');
    const video = document.getElementById('video-alc');
    const inputB64 = document.getElementById('input-foto-alc-b64');

    if (preview) preview.style.display = 'none';
    if (video) video.style.display = 'block';
    document.getElementById('btn-tomar-foto').style.display = 'block';
    document.getElementById('controles-foto').style.display = 'none';
    if (inputB64) inputB64.value = '';
}

function confirmarFotoAlc() {
    cerrarCamara();
    const btnEvi = document.getElementById('btn-evidencia-alc');
    if (btnEvi) {
        btnEvi.innerHTML = '<i class="fas fa-check-circle"></i> Evidencia Capturada';
        btnEvi.className = 'btn-action btn-success';
    }
}

function cerrarCamara() {
    if (streamAlc) {
        streamAlc.getTracks().forEach(t => t.stop());
        streamAlc = null;
    }
    const modalCam = document.getElementById('modal-camara');
    if (modalCam) modalCam.style.display = 'none';
}

// 5. EQUIPO Y HERRAMIENTAS
function toggleEquipo(val) {
    const contSec = document.getElementById('seccion-equipo-compartido');
    if (contSec) {
        const btns = contSec.querySelectorAll('.btn-toggle');
        if (btns.length > 0) {
            btns.forEach(b => b.classList.remove('active', 'green-text'));
            let activeBtn = val === 'SI' ? btns[1] : btns[0];
            if (activeBtn) activeBtn.classList.add('active', 'green-text');
        }
    }
    
    const cont = document.getElementById('contenedor-herramientas');
    if (cont) {
        if (val === 'SI') {
            cont.style.display = 'block';
            cont.querySelectorAll('.herr-input').forEach(i => i.disabled = false);
        } else {
            cont.style.display = 'none';
            cont.querySelectorAll('.herr-input').forEach(i => i.disabled = true);
        }
    }
}

function agregarHerramientaIngreso() {
    const d = document.createElement('div'); 
    d.className = 'herramienta-row';
    d.innerHTML = '<input type="text" name="desc_herramienta[]" class="form-control-local herr-input" placeholder="Descripción del equipo..." required style="margin:0; flex:2;"><input type="number" name="cant_herramienta[]" class="form-control-local herr-input" placeholder="Cant." min="1" required style="margin:0; flex:1;">';
    const cont = document.getElementById('lista-herramientas-ingreso');
    if (cont) cont.appendChild(d);
}

function agregarFilaExterno() {
    const d = document.createElement('div'); 
    d.className = 'persona-row';
    d.style.cssText = "display:flex; gap:10px; margin-bottom:10px;";
    d.innerHTML = '<input type="text" name="nombre[]" class="form-control-local" placeholder="NOMBRE:" required style="margin:0;"><input type="text" name="gafete[]" class="form-control-local" placeholder="GAFETE:" style="margin:0;">';
    const cont = document.getElementById('lista-personas');
    if (cont) cont.appendChild(d);
}

// 6. PROCESAMIENTO DE SALIDAS Y FOTOS
let arrayB64Salida = [];
let tipoSalidaActivo = '';

function procesarFotosSalida(input) {
    if (!input.files || input.files.length === 0) return;
    Array.from(input.files).forEach(file => {
        const reader = new FileReader();
        reader.onload = function(e) {
            const img = new Image();
            img.onload = function() {
                const canvas = document.createElement('canvas');
                const MAX_WIDTH = 1280;
                let width = img.width; 
                let height = img.height;
                if (width > MAX_WIDTH) { 
                    height *= MAX_WIDTH / width; 
                    width = MAX_WIDTH; 
                }
                canvas.width = width; 
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                const dataUrl = canvas.toDataURL('image/jpeg', 0.7);
                agregarMiniaturaSalida(dataUrl);
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
    input.value = '';
}

function agregarMiniaturaSalida(b64) {
    const id = 'foto_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
    arrayB64Salida.push({id: id, data: b64});
    renderizarMiniaturasSalida();
}

function removerFotoSalida(id) {
    arrayB64Salida = arrayB64Salida.filter(f => f.id !== id);
    renderizarMiniaturasSalida();
}

function renderizarMiniaturasSalida() {
    const container = document.getElementById('preview-salida-container');
    const hiddenCont = document.getElementById('hidden-b64-container');
    if (!container || !hiddenCont) return;

    container.innerHTML = ''; 
    hiddenCont.innerHTML = '';
    
    arrayB64Salida.forEach(foto => {
        const div = document.createElement('div');
        div.className = 'preview-box';
        div.style.position = 'relative';
        div.innerHTML = `
            <img src="${foto.data}">
            <button type="button" onclick="removerFotoSalida('${foto.id}')" style="position:absolute; top:-5px; right:-5px; background:#dc3545; color:#fff; border:none; border-radius:50%; width:22px; height:22px; font-size:12px; cursor:pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">✖</button>
        `;
        container.appendChild(div);
        
        const inp = document.createElement('input');
        inp.type = 'hidden'; 
        inp.name = 'fotos_salida_b64[]'; 
        inp.value = foto.data;
        hiddenCont.appendChild(inp);
    });
    validarBotonSalida();
}

function validarBotonSalida() {
    const btnCapturar = document.getElementById('btn-capturar-salida');
    if (!btnCapturar) return;
    if (tipoSalidaActivo === 'UNIDAD' || tipoSalidaActivo === 'UTILITARIO') {
        if (arrayB64Salida.length > 0) { 
            btnCapturar.disabled = false; 
            btnCapturar.style.opacity = '1'; 
        } else { 
            btnCapturar.disabled = true; 
            btnCapturar.style.opacity = '0.5'; 
        }
    }
}

function abrirModalSalida(id, tipo, identificador, jsonStr) {
    document.getElementById('salida-id-activo').value = id;
    document.getElementById('titulo-salida').innerText = `Salida: ${identificador}`;
    
    let datos = JSON.parse(jsonStr || "{}");
    const btnCapturar = document.getElementById('btn-capturar-salida');
    
    document.getElementById('salida-bloque-unidad').style.display = 'none';
    document.getElementById('salida-bloque-personas').style.display = 'none';
    document.getElementById('salida-bloque-herramientas').style.display = 'none';
    document.getElementById('salida-bloque-evidencia').style.display = 'none';
    
    arrayB64Salida = []; 
    renderizarMiniaturasSalida(); 
    tipoSalidaActivo = tipo;

    if (btnCapturar) {
        btnCapturar.disabled = false; 
        btnCapturar.style.opacity = '1';
    }
    
    if (tipo === 'UNIDAD' || tipo === 'UTILITARIO') {
        document.getElementById('salida-bloque-evidencia').style.display = 'block';
        if (btnCapturar) {
            btnCapturar.disabled = true; 
            btnCapturar.style.opacity = '0.5'; 
        }
        
        if (tipo === 'UNIDAD') {
            document.getElementById('salida-bloque-unidad').style.display = 'block';
            const lblEstado = document.getElementById('lbl-estado-ingreso');
            if (lblEstado) lblEstado.innerText = datos['estatus_carga'] || 'N/A';
        }
    } 
    else if (tipo === 'EXTERNO' || tipo === 'EMPLEADO') {
        if (tipo === 'EXTERNO') {
            let nombres = datos['nombre[]'] || [];
            if (!Array.isArray(nombres)) nombres = [nombres];
            const contPers = document.getElementById('salida-checklist-personas');
            if (contPers) {
                contPers.innerHTML = '';
                if (nombres.length > 0 && nombres[0] !== "") {
                    document.getElementById('salida-bloque-personas').style.display = 'block';
                    nombres.forEach((n) => {
                        contPers.innerHTML += `<label class="check-item"><input type="checkbox" name="personas_check[]" value="${n}" onchange="verificarSalidaPersonas()"> <span style="font-weight:600; color:var(--text-main);">${n}</span></label>`;
                    });
                    if (btnCapturar) {
                        btnCapturar.disabled = true; 
                        btnCapturar.style.opacity = '0.5';
                    }
                }
            }
        }

        let desc = datos['desc_herramienta[]'] || [];
        let cant = datos['cant_herramienta[]'] || [];
        if (!Array.isArray(desc)) desc = [desc];
        if (!Array.isArray(cant)) cant = [cant];
        
        const contHerr = document.getElementById('salida-checklist-herramientas');
        if (contHerr) {
            contHerr.innerHTML = '';
            if (desc.length > 0 && desc[0] !== "") {
                document.getElementById('salida-bloque-herramientas').style.display = 'block';
                desc.forEach((d, i) => {
                    contHerr.innerHTML += `<label class="check-item"><input type="checkbox" name="herramientas_check[]" value="${d}"> <span style="font-weight:600; color:var(--text-main);">[${cant[i]}] ${d}</span></label>`;
                });
            }
        }
    }
    const modalSalida = document.getElementById('modal-salida');
    if (modalSalida) modalSalida.style.display = 'flex';
}

function verificarSalidaPersonas() {
    if (document.getElementById('salida-bloque-personas').style.display === 'block') {
        let pMarcadas = document.querySelectorAll('input[name="personas_check[]"]:checked').length;
        let btn = document.getElementById('btn-capturar-salida');
        if (btn) {
            if (pMarcadas > 0) { 
                btn.style.opacity = '1'; 
                btn.disabled = false; 
            } else { 
                btn.style.opacity = '0.5'; 
                btn.disabled = true; 
            }
        }
    }
}

function cerrarSalida() { 
    const modal = document.getElementById('modal-salida');
    if (modal) modal.style.display = 'none'; 
}

function setToggle(btn, inputId, val, activeClass, optTextColorClass) {
    const group = btn.parentElement;
    group.querySelectorAll('.btn-toggle').forEach(b => {
        b.classList.remove('active', 'green-text', 'red-text', 'orange-text');
    });
    btn.classList.add(activeClass);
    if (optTextColorClass) btn.classList.add(optTextColorClass);
    const input = document.getElementById(inputId);
    if (input) input.value = val;
}

function previewMultiple(inputElement, containerId) {
    const container = document.getElementById(containerId); 
    if (!container) return;
    container.innerHTML = ''; 
    if (inputElement.files) {
        Array.from(inputElement.files).forEach(file => {
            const reader = new FileReader();
            reader.onload = function(e) {
                const div = document.createElement('div'); 
                div.className = 'preview-box';
                const img = document.createElement('img'); 
                img.src = e.target.result;
                div.appendChild(img); 
                container.appendChild(div);
            };
            reader.readAsDataURL(file);
        });
    }
}

// 7. RELEVOS Y RESGUARDOS
let contResguardos = 100;

function agregarResguardoNuevo() {
    contResguardos++; 
    const id = contResguardos;
    const d = document.createElement('div');
    d.id = 'res_row_' + id; 
    d.className = 'sub-box'; 
    d.style.cssText = 'display:flex; flex-direction:column; gap:10px;';
    d.innerHTML = `
        <div style="display:flex; gap:10px;">
            <input type="number" name="res_cant[]" class="form-control-local" placeholder="Cant" style="width:70px; font-weight:bold; margin:0;" required>
            <input type="text" name="res_desc[]" class="form-control-local" placeholder="Descripción del artículo" style="flex:1; font-weight:bold; margin:0;" required>
            <button type="button" onclick="eliminarResguardo('res_row_${id}')" style="background:none; border:none; color:#dc3545; font-size:20px; cursor:pointer;"><i class="fas fa-times"></i></button>
        </div>
        <input type="hidden" name="res_estado[]" id="chk_res_${id}" value="BUENO">
        <div class="btn-group" style="margin-top:0;">
            <div class="btn-toggle active green-text" onclick="setToggleResguardo(this, 'chk_res_${id}', 'BUENO', 'active', '${id}', 'green-text')">✔️ BUENO</div>
            <div class="btn-toggle" onclick="setToggleResguardo(this, 'chk_res_${id}', 'MALO', 'active', '${id}', 'red-text')">❌ MALO</div>
        </div>
        <div id="defecto_res_${id}" style="display:none; margin-top:5px;">
            <textarea name="res_obs[]" id="obs_res_${id}" class="form-control-local" rows="2" placeholder="Especifica el daño/faltante..." style="margin:0;"></textarea>
        </div>
    `;
    const lista = document.getElementById('lista-resguardos-dinamica');
    if (lista) lista.appendChild(d);
}

function eliminarResguardo(idRow) { 
    const el = document.getElementById(idRow);
    if (el) el.remove(); 
}

function setToggleResguardo(btn, inputId, valor, claseActiva, indexId, textColorClass) {
    setToggle(btn, inputId, valor, claseActiva, textColorClass);
    const cajaDefecto = document.getElementById('defecto_res_' + indexId);
    const inputObs = document.getElementById('obs_res_' + indexId);
    if (valor === 'MALO') { 
        if (cajaDefecto) cajaDefecto.style.display = 'block'; 
        if (inputObs) {
            inputObs.required = true; 
            inputObs.value = '';
        }
    } else { 
        if (cajaDefecto) cajaDefecto.style.display = 'none'; 
        if (inputObs) {
            inputObs.required = false; 
            inputObs.value = 'N/A'; 
        }
    }
}

// 8. CONSULTA DE MI TURNO
function cargarMiTurno() {
    fetch('/api/mi_turno').then(res => res.json()).then(data => {
        if (!data.error) {
            const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
            setTxt('c_alc_tot', data.alcohol_total);
            setTxt('c_alc_pos', data.alcohol_positivos);
            
            const s = data.stats;
            if (s) {
                setTxt('u_ent', s.UNIDAD.ent);
                setTxt('u_sal', s.UNIDAD.sal);
                setTxt('ut_ent', s.UTILITARIO.ent);
                setTxt('ut_sal', s.UTILITARIO.sal);
                setTxt('em_ent', s.EMPLEADO.ent);
                setTxt('em_sal', s.EMPLEADO.sal);
            }
            
            let htmlExt = "";
            if (data.externos && data.externos.length > 0) {
                let grouped = {};
                data.externos.forEach(e => {
                    if (!grouped[e.empresa]) grouped[e.empresa] = [];
                    grouped[e.empresa].push(e);
                });

                for (let emp in grouped) {
                    let personas = grouped[emp];
                    personas.forEach((p, idx) => {
                        let badgeSalida = p.hora_salida === 'Aún en base' ? 
                            `<span style="background:#ffc107; color:#000; padding:4px 8px; border-radius:6px; font-weight:bold; font-size:11px;">Aún en base</span>` : 
                            `<span style="background:#10b981; color:#fff; padding:4px 8px; border-radius:6px; font-weight:bold; font-size:11px;">${p.hora_salida}</span>`;
                        
                        htmlExt += `<tr style="border-bottom:1px solid var(--border-subtle);">`;
                        if (idx === 0) { 
                            htmlExt += `<td rowspan="${personas.length}" style="padding:12px; font-weight:600; color:var(--text-main); vertical-align:middle; border-right:1px solid var(--border-subtle); background:var(--bg-surface-2);">${p.empresa}</td>`; 
                        }
                        htmlExt += `
                            <td style="padding:12px;">${p.nombre}</td>
                            <td style="padding:12px;">${p.motivo}</td>
                            <td style="padding:12px;">${p.area}</td>
                            <td style="padding:12px; text-align:center; font-weight:600;">${p.hora_entrada}</td>
                            <td style="padding:12px; text-align:center;">${badgeSalida}</td>
                        </tr>`;
                    });
                }
            } else {
                htmlExt = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-muted);">No hay ingresos de personal externo.</td></tr>`;
            }
            const tablaExt = document.getElementById('tabla_turno_externos');
            if (tablaExt) tablaExt.innerHTML = htmlExt;
        }
    }).catch(err => console.error("Error cargando el turno:", err));
}