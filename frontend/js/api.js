// Cliente de la API REST /api/v1 (SDD 7.10). Maneja el JWT y el formato de error uniforme.
window.LF = window.LF || {};
LF.base = (window.LF_API_BASE || '') + '/api/v1';
LF.token = localStorage.getItem('lf_token') || null;
LF.user = null;

LF.setToken = t => { LF.token = t; t ? localStorage.setItem('lf_token', t) : localStorage.removeItem('lf_token'); };
LF.uuid = () => (crypto.randomUUID ? crypto.randomUUID() : 'k' + Date.now() + Math.random().toString(16).slice(2));

LF.api = async (metodo, ruta, cuerpo, cabeceras = {}) => {
  const h = { 'Content-Type': 'application/json', ...cabeceras };
  if (LF.token) h.Authorization = 'Bearer ' + LF.token;
  let r;
  try {
    r = await fetch(LF.base + ruta, { method: metodo, headers: h, body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo) });
  } catch (e) {
    throw { codigo: 'SIN_CONEXION', mensaje: 'No se pudo conectar con el backend (' + LF.base + '). Asegúrese de que el servidor Flask esté corriendo (python run.py o INICIAR.bat).', status: 0 };
  }
  let d = null;
  try { d = await r.json(); } catch (e) {}
  if (!r.ok) {
    const er = (d && d.error) || {
      codigo: 'ERROR_' + r.status,
      mensaje: r.status === 404
        ? 'Error 404: No se encontró la ruta en ' + LF.base + ruta + '. Verifique que el backend de LicoFast esté iniciado en el puerto 5000.'
        : 'Error ' + r.status
    };
    if (r.status === 401 && LF.token && !ruta.startsWith('/auth/login')) {
      LF.setToken(null); LF.user = null; LF.sesionVencida && LF.sesionVencida();
    }
    throw { ...er, status: r.status };
  }
  return d;
};
LF.get = (r) => LF.api('GET', r);
LF.post = (r, b, h) => LF.api('POST', r, b || {}, h);
LF.put = (r, b) => LF.api('PUT', r, b || {});
LF.del = (r) => LF.api('DELETE', r);
