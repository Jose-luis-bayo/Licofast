"""Capa 4: acceso a datos del módulo Seguridad (usuarios y auditoría)."""
from ...db import one, all_, run

PUBLICOS = 'id,nombre,apellido,ci,fecha_nacimiento,edad,usuario,rol,cargo,telefono,activo,created_at'
EDITABLES = ('nombre', 'apellido', 'ci', 'fecha_nacimiento', 'edad', 'usuario', 'password', 'rol', 'cargo', 'telefono', 'activo')


class UsuarioRepository:
    @staticmethod
    def por_usuario(cur, usuario): return one(cur, 'SELECT * FROM usuarios WHERE usuario=%s', (usuario,))

    @staticmethod
    def por_id(cur, uid, lock=False):
        return one(cur, 'SELECT * FROM usuarios WHERE id=%s' + (' FOR UPDATE' if lock else ''), (uid,))

    @staticmethod
    def duplicado(cur, usuario, ci, excluir=0):
        return one(cur, 'SELECT id FROM usuarios WHERE (usuario=%s OR ci=%s) AND id<>%s LIMIT 1', (usuario, ci, excluir))

    @staticmethod
    def insertar(cur, d):
        cols = list(d)
        return run(cur, f"INSERT INTO usuarios({','.join(cols)}) VALUES({','.join(['%s'] * len(cols))})", [d[c] for c in cols])

    @staticmethod
    def actualizar(cur, uid, campos):
        campos = {k: v for k, v in campos.items() if k in EDITABLES}
        if campos:
            run(cur, f"UPDATE usuarios SET {','.join(k + '=%s' for k in campos)} WHERE id=%s", [*campos.values(), uid])

    @staticmethod
    def listar(cur, rol=None):
        if rol:
            return all_(cur, f'SELECT {PUBLICOS} FROM usuarios WHERE rol=%s ORDER BY id DESC', (rol,))
        return all_(cur, f'SELECT {PUBLICOS} FROM usuarios ORDER BY id DESC')

    @staticmethod
    def eliminar(cur, uid): run(cur, 'DELETE FROM usuarios WHERE id=%s', (uid,))

    @staticmethod
    def fallo_login(cur, uid, maximo, minutos):
        run(cur, 'UPDATE usuarios SET intentos_fallidos=intentos_fallidos+1 WHERE id=%s', (uid,))
        u = one(cur, 'SELECT intentos_fallidos FROM usuarios WHERE id=%s', (uid,))
        if u['intentos_fallidos'] >= maximo:
            run(cur, 'UPDATE usuarios SET intentos_fallidos=0, bloqueado_hasta=DATE_ADD(NOW(), INTERVAL %s MINUTE) WHERE id=%s', (minutos, uid))
            return True
        return False

    @staticmethod
    def reset_login(cur, uid): run(cur, 'UPDATE usuarios SET intentos_fallidos=0, bloqueado_hasta=NULL WHERE id=%s', (uid,))

    @staticmethod
    def bloqueado(cur, uid): return one(cur, 'SELECT 1 AS x FROM usuarios WHERE id=%s AND bloqueado_hasta IS NOT NULL AND bloqueado_hasta>NOW()', (uid,)) is not None


class AuditoriaRepository:
    @staticmethod
    def insertar(cur, usuario_id, accion, entidad, entidad_id, detalle, ip):
        run(cur, 'INSERT INTO auditoria(usuario_id,accion,entidad,entidad_id,detalle,ip) VALUES(%s,%s,%s,%s,%s,%s)',
            (usuario_id, accion, entidad, entidad_id, detalle, ip))

    @staticmethod
    def listar(cur, f, limit, offset):
        where, args = ['1=1'], []
        for campo, col in (('usuario_id', 'a.usuario_id'), ('accion', 'a.accion'), ('entidad', 'a.entidad')):
            if f.get(campo):
                where.append(f'{col}=%s'); args.append(f[campo])
        if f.get('desde'):
            where.append('a.created_at>=%s'); args.append(f['desde'])
        if f.get('hasta'):
            where.append('a.created_at<DATE_ADD(%s, INTERVAL 1 DAY)'); args.append(f['hasta'])
        w = ' AND '.join(where)
        total = one(cur, f'SELECT COUNT(*) AS n FROM auditoria a WHERE {w}', args)['n']
        filas = all_(cur, f'SELECT a.id,a.usuario_id,u.usuario,a.accion,a.entidad,a.entidad_id,a.detalle,a.ip,a.created_at FROM auditoria a '
                          f'LEFT JOIN usuarios u ON u.id=a.usuario_id WHERE {w} ORDER BY a.id DESC LIMIT %s OFFSET %s', [*args, limit, offset])
        return total, filas


def buscar_clientes(cur, q=None, limit=30):
    if q:
        like = f'%{q}%'
        return all_(cur, "SELECT id,nombre,apellido,ci,telefono,fecha_nacimiento FROM usuarios WHERE rol='cliente' AND activo=1 AND "
                         "(nombre LIKE %s OR apellido LIKE %s OR ci LIKE %s OR usuario LIKE %s OR telefono LIKE %s) ORDER BY nombre LIMIT %s", (like,) * 5 + (limit,))
    return all_(cur, "SELECT id,nombre,apellido,ci,telefono,fecha_nacimiento FROM usuarios WHERE rol='cliente' AND activo=1 ORDER BY nombre LIMIT %s", (limit,))
