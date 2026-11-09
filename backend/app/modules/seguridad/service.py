"""Capa 3: reglas del módulo Seguridad (AuthService, UsuarioService, AuditoriaService)."""
import json
import secrets
import mysql.connector
from ...config import Config
from ...db import read, transaction
from ...core.errors import AppError, conflicto, invalido, no_autenticado, no_encontrado, prohibido
from ...core.events import bus
from ...core.security import crear_token, hash_password, verify_password, verify_dummy, leer_token, revocar_token
from ...core import validators as v
from .repository import UsuarioRepository as U, AuditoriaRepository as A

ROLES = ('cliente', 'administrador', 'cajero', 'repartidor', 'empleado')
MENSAJE_LOGIN = 'Usuario o contraseña incorrectos'


def _limpio(u):
    if not u:
        return u
    u = dict(u)
    for k in ('password', 'intentos_fallidos', 'bloqueado_hasta', 'acepta_terminos'):
        u.pop(k, None)
    # Cuentas creadas con Google: faltan fecha de nacimiento y CI reales para vender alcohol
    u['perfil_incompleto'] = bool(u.get('rol') == 'cliente' and not u.get('fecha_nacimiento'))
    return u


def _password(d, campo='password', obligatorio=True):
    p = d.get(campo)
    if not p:
        if obligatorio:
            raise invalido('La contraseña es obligatoria (mínimo 8 caracteres)', {'campo': campo})
        return None
    if not isinstance(p, str) or len(p) < 8:
        raise invalido('La contraseña debe tener al menos 8 caracteres', {'campo': campo})
    return p


class AuthService:
    @staticmethod
    def login(usuario, password):
        if not usuario or not password:
            raise no_autenticado(MENSAJE_LOGIN)
        with transaction() as cur:
            u = U.por_usuario(cur, usuario)
            if not u:
                verify_dummy(password)
                bus.publish('LoginFallido', usuario_id=None, entidad='usuario', entidad_id=None, detalle={'usuario': usuario[:50]})
                raise no_autenticado(MENSAJE_LOGIN)
            if U.bloqueado(cur, u['id']):
                raise AppError('CUENTA_BLOQUEADA', 'Cuenta bloqueada temporalmente por intentos fallidos. Intente más tarde.', 423)
            if not u['activo'] or not verify_password(password, u['password']):
                bloqueada = U.fallo_login(cur, u['id'], Config.LOGIN_MAX_INTENTOS, Config.LOGIN_BLOQUEO_MIN) if u['activo'] else False
                uid = u['id']
            else:
                U.reset_login(cur, u['id'])
                uid = None
        if uid is not None:
            bus.publish('LoginFallido', usuario_id=uid, entidad='usuario', entidad_id=uid, detalle={'bloqueada': bloqueada})
            raise no_autenticado(MENSAJE_LOGIN)
        bus.publish('LoginExitoso', usuario_id=u['id'], entidad='usuario', entidad_id=u['id'], detalle=None)
        return {'token': crear_token(u['id'], u['rol']), 'usuario': _limpio(u)}

    @staticmethod
    def login_google(credential):
        """Inicio de sesión con Google: valida el ID token firmado por Google y crea la cuenta cliente si es la primera vez."""
        if not Config.GOOGLE_CLIENT_ID:
            raise AppError('GOOGLE_NO_CONFIGURADO', 'El inicio de sesión con Google no está configurado', 503)
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as greq
            info = id_token.verify_oauth2_token(credential or '', greq.Request(), Config.GOOGLE_CLIENT_ID)
        except Exception:
            raise no_autenticado('No se pudo validar la cuenta de Google')
        if not info.get('email_verified', True) or not info.get('sub'):
            raise no_autenticado('La cuenta de Google no tiene el correo verificado')
        sub = str(info['sub'])
        usuario = 'g_' + sub
        nuevo = False
        with transaction() as cur:
            u = U.por_usuario(cur, usuario)
            if not u:
                nombre = (info.get('given_name') or info.get('name') or 'Cliente')[:80]
                apellido = (info.get('family_name') or 'Google')[:80]
                uid = U.insertar(cur, dict(nombre=nombre, apellido=apellido, ci='G-' + sub[:20], fecha_nacimiento=None, edad=18, usuario=usuario,
                                           password=hash_password(secrets.token_urlsafe(24)), rol='cliente', cargo='Cliente (Google)', telefono=None, acepta_terminos=0, activo=1))
                u = U.por_id(cur, uid)
                nuevo = True
        if not u['activo']:
            raise no_autenticado(MENSAJE_LOGIN)
        bus.publish('UsuarioCreado' if nuevo else 'LoginExitoso', usuario_id=u['id'], entidad='usuario', entidad_id=u['id'],
                    detalle={'rol': 'cliente', 'google': True} if nuevo else {'google': True})
        return {'token': crear_token(u['id'], u['rol']), 'usuario': _limpio(u)}

    @staticmethod
    def logout(token_data, usuario_id):
        revocar_token(token_data)
        bus.publish('Logout', usuario_id=usuario_id, entidad='usuario', entidad_id=usuario_id, detalle=None)

    @staticmethod
    def registrar(d):
        nombre, apellido = v.texto(d, 'nombre', max_len=80), v.texto(d, 'apellido', max_len=80)
        ci, usuario = v.texto(d, 'ci', max_len=30), v.texto(d, 'usuario', max_len=50)
        password = _password(d)
        telefono = v.texto(d, 'telefono', obligatorio=False, max_len=30)
        if not d.get('terminos'):
            raise invalido('Debe aceptar los términos y condiciones', {'campo': 'terminos'})
        nac = v.fecha(d.get('fecha_nacimiento'), 'fecha_nacimiento')
        edad = v.edad_exacta(nac)
        if edad < 18:
            raise invalido('Solo pueden registrarse personas de 18 años o más', codigo='MENOR_DE_EDAD')
        with transaction() as cur:
            if U.duplicado(cur, usuario, ci):
                raise conflicto('USUARIO_DUPLICADO', 'El usuario o el CI ya están registrados')
            uid = U.insertar(cur, dict(nombre=nombre, apellido=apellido, ci=ci, fecha_nacimiento=nac, edad=edad, usuario=usuario,
                                       password=hash_password(password), rol='cliente', cargo='Cliente', telefono=telefono, acepta_terminos=1, activo=1))
        bus.publish('UsuarioCreado', usuario_id=uid, entidad='usuario', entidad_id=uid, detalle={'rol': 'cliente', 'autoregistro': True})
        return {'id': uid, 'mensaje': 'Cuenta creada'}

    @staticmethod
    def perfil(uid):
        with read() as cur:
            u = U.por_id(cur, uid)
        if not u:
            raise no_encontrado()
        return _limpio(u)

    @staticmethod
    def actualizar_perfil(uid, d):
        campos = {}
        for c in ('nombre', 'apellido'):
            if d.get(c):
                campos[c] = v.texto(d, c, max_len=80)
        if 'telefono' in d:
            campos['telefono'] = v.texto(d, 'telefono', obligatorio=False, max_len=30)
        nueva = _password(d, 'password_nueva', obligatorio=False)
        with transaction() as cur:
            u = U.por_id(cur, uid, lock=True)
            if u['rol'] == 'cliente' and not u.get('fecha_nacimiento') and d.get('fecha_nacimiento'):
                # Completar datos de una cuenta de Google: la fecha de nacimiento solo se puede fijar una vez
                nac = v.fecha(d.get('fecha_nacimiento'), 'fecha_nacimiento')
                edad = v.edad_exacta(nac)
                if edad < 18:
                    raise invalido('Solo pueden comprar personas de 18 años o más', codigo='MENOR_DE_EDAD')
                ci = v.texto(d, 'ci', max_len=30)
                if U.ci_en_uso(cur, ci, uid):
                    raise conflicto('USUARIO_DUPLICADO', 'Ese CI ya está registrado')
                if not d.get('terminos'):
                    raise invalido('Debe aceptar los términos y condiciones', {'campo': 'terminos'})
                campos.update(fecha_nacimiento=nac, edad=edad, ci=ci, acepta_terminos=1)
            if nueva:
                if not verify_password(d.get('password_actual') or '', u['password']):
                    raise invalido('La contraseña actual no es correcta', codigo='PASSWORD_ACTUAL_INCORRECTA')
                campos['password'] = hash_password(nueva)
            U.actualizar(cur, uid, campos)
        bus.publish('PerfilActualizado', usuario_id=uid, entidad='usuario', entidad_id=uid, detalle={'campos': [k for k in campos if k != 'password'], 'cambio_password': bool(nueva)})
        return AuthService.perfil(uid)


class UsuarioService:
    @staticmethod
    def listar(rol=None):
        if rol and rol not in ROLES:
            raise invalido('Rol inválido')
        with read() as cur:
            return U.listar(cur, rol)

    @staticmethod
    def _datos(d, parcial=False):
        out = {}
        out['nombre'] = v.texto(d, 'nombre', max_len=80)
        out['apellido'] = v.texto(d, 'apellido', max_len=80)
        out['ci'] = v.texto(d, 'ci', max_len=30)
        out['usuario'] = v.texto(d, 'usuario', max_len=50)
        rol = d.get('rol') or 'cliente'
        if rol not in ROLES:
            raise invalido('Rol inválido', {'roles': list(ROLES)})
        out['rol'] = rol
        out['cargo'] = v.texto(d, 'cargo', obligatorio=False, max_len=100) or rol.capitalize()
        out['telefono'] = v.texto(d, 'telefono', obligatorio=False, max_len=30)
        out['activo'] = 1 if str(d.get('activo', 1)) in ('1', 'True', 'true') else 0
        if d.get('fecha_nacimiento'):
            nac = v.fecha(d['fecha_nacimiento'], 'fecha_nacimiento')
            out['fecha_nacimiento'], out['edad'] = nac, v.edad_exacta(nac)
            if rol == 'cliente' and out['edad'] < 18:
                raise invalido('Un cliente debe tener 18 años o más', codigo='MENOR_DE_EDAD')
        elif rol == 'cliente':
            raise invalido('La fecha de nacimiento es obligatoria para clientes', {'campo': 'fecha_nacimiento'})
        return out

    @staticmethod
    def crear(d, admin_id):
        datos = UsuarioService._datos(d)
        datos['password'] = hash_password(_password(d))  # sin contraseña por defecto (H-06)
        datos['acepta_terminos'] = 1
        with transaction() as cur:
            if U.duplicado(cur, datos['usuario'], datos['ci']):
                raise conflicto('USUARIO_DUPLICADO', 'El usuario o el CI ya están registrados')
            uid = U.insertar(cur, datos)
        bus.publish('UsuarioCreado', usuario_id=admin_id, entidad='usuario', entidad_id=uid, detalle={'rol': datos['rol']})
        return {'id': uid, 'mensaje': 'Usuario creado'}

    @staticmethod
    def actualizar(uid, d, admin_id):
        datos = UsuarioService._datos(d)
        p = _password(d, obligatorio=False)
        if p:
            datos['password'] = hash_password(p)
        if uid == admin_id and (datos['rol'] != 'administrador' or not datos['activo']):
            raise conflicto('AUTO_MODIFICACION', 'No puede quitarse el rol de administrador ni desactivarse a sí mismo')
        with transaction() as cur:
            ant = U.por_id(cur, uid, lock=True)
            if not ant:
                raise no_encontrado('Usuario no encontrado')
            if U.duplicado(cur, datos['usuario'], datos['ci'], excluir=uid):
                raise conflicto('USUARIO_DUPLICADO', 'El usuario o el CI ya pertenecen a otra cuenta')
            U.actualizar(cur, uid, datos)
            if datos['activo']:
                U.reset_login(cur, uid)
        bus.publish('UsuarioModificado', usuario_id=admin_id, entidad='usuario', entidad_id=uid,
                    detalle={'rol_anterior': ant['rol'], 'rol_nuevo': datos['rol'], 'activo': datos['activo'], 'cambio_password': bool(p)})
        return {'mensaje': 'Usuario actualizado'}

    @staticmethod
    def eliminar(uid, admin_id):
        """Baja: física si no tiene historial; si lo tiene, baja lógica (ADR-10)."""
        if uid == admin_id:
            raise conflicto('AUTO_MODIFICACION', 'No puede eliminar su propia cuenta')
        with transaction() as cur:
            if not U.por_id(cur, uid, lock=True):
                raise no_encontrado('Usuario no encontrado')
            try:
                cur.execute('SAVEPOINT baja')
                U.eliminar(cur, uid)
                modo = 'eliminado'
            except mysql.connector.IntegrityError:
                cur.execute('ROLLBACK TO SAVEPOINT baja')
                U.actualizar(cur, uid, {'activo': 0})
                modo = 'desactivado'
        bus.publish('UsuarioEliminado', usuario_id=admin_id, entidad='usuario', entidad_id=uid, detalle={'modo': modo})
        return {'mensaje': 'Usuario eliminado' if modo == 'eliminado' else 'El usuario tiene historial; fue desactivado en su lugar', 'modo': modo}


class AuditoriaService:
    @staticmethod
    def registrar(evento, datos):
        """Observador universal: guarda en la bitácora los eventos que traen entidad."""
        if 'entidad' not in datos:
            return
        det = datos.get('detalle')
        with transaction() as cur:
            A.insertar(cur, datos.get('usuario_id'), evento, datos['entidad'], datos.get('entidad_id'),
                       json.dumps(det, ensure_ascii=False, default=str) if det is not None else None, datos.get('ip'))

    @staticmethod
    def listar(filtros, limit, offset):
        with read() as cur:
            total, filas = A.listar(cur, filtros, limit, offset)
        return {'total': total, 'items': filas}


bus.subscribe_all(AuditoriaService.registrar)
