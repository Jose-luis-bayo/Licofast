"""Migraciones automáticas e idempotentes: ponen al día una base ya creada (p. ej. TiDB en la nube)
sin tener que ejecutar SQL a mano. Se llaman al iniciar la aplicación y se pueden repetir sin riesgo."""
import logging
from .db import transaction, run, one

log = logging.getLogger('licofast.migraciones')


DDL_CUPONES = '''CREATE TABLE IF NOT EXISTS cupones (
 id INT AUTO_INCREMENT PRIMARY KEY,
 codigo VARCHAR(30) NOT NULL UNIQUE,
 descripcion VARCHAR(160) NULL,
 tipo ENUM('porcentaje','monto') NOT NULL,
 valor DECIMAL(10,2) NOT NULL,
 minimo_compra DECIMAL(10,2) NOT NULL DEFAULT 0,
 usos_max INT NULL,
 usos_por_cliente INT NOT NULL DEFAULT 1,
 usuario_id INT NULL,
 vigente_desde DATETIME NULL,
 vigente_hasta DATETIME NULL,
 activo TINYINT(1) NOT NULL DEFAULT 1,
 origen ENUM('manual','recompensa') NOT NULL DEFAULT 'manual',
 regla VARCHAR(20) NULL,
 periodo VARCHAR(12) NULL,
 creado_por INT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_recompensa (usuario_id, regla, periodo),
 KEY ix_cupon_usuario (usuario_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cupon_usos (
 id INT AUTO_INCREMENT PRIMARY KEY,
 cupon_id INT NOT NULL,
 usuario_id INT NOT NULL,
 venta_id INT NOT NULL,
 descuento DECIMAL(10,2) NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 KEY ix_uso_cupon (cupon_id), KEY ix_uso_venta (venta_id),
 FOREIGN KEY (cupon_id) REFERENCES cupones(id)
) ENGINE=InnoDB;
'''


def _columna(cur, tabla, col):
    return one(cur, 'SELECT 1 AS x FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s AND column_name=%s', (tabla, col))


def _tipo(cur, tabla, col):
    r = one(cur, 'SELECT column_type AS t FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s AND column_name=%s', (tabla, col))
    return (r or {}).get('t', '')


def migrar():
    with transaction() as cur:
        # --- ventas: ubicación GPS del cliente, método de pago elegido y sellos de cada etapa
        for col, ddl in (
            ('lat_entrega', 'DECIMAL(9,6) NULL'), ('lng_entrega', 'DECIMAL(9,6) NULL'),
            ('metodo_pago', "VARCHAR(10) NOT NULL DEFAULT 'efectivo'"),
            ('confirmado_en', 'DATETIME NULL'), ('confirmado_por', 'INT NULL'),
            ('preparado_en', 'DATETIME NULL'), ('preparado_por', 'INT NULL'), ('cupon_codigo', 'VARCHAR(30) NULL'),
        ):
            if not _columna(cur, 'ventas', col):
                run(cur, f'ALTER TABLE ventas ADD COLUMN {col} {ddl}')
        t = _tipo(cur, 'ventas', 'estado')
        if 'preparado' not in t:
            run(cur, "ALTER TABLE ventas MODIFY COLUMN estado ENUM('pendiente','pagada','en_camino','entregada','no_entregado','confirmado','preparado') NOT NULL DEFAULT 'pendiente'")
        # --- pagos: nuevo método PayPal
        if 'paypal' not in _tipo(cur, 'pagos', 'metodo'):
            run(cur, "ALTER TABLE pagos MODIFY COLUMN metodo ENUM('efectivo','qr','paypal') NOT NULL")
        # --- promociones avanzadas (2x1, segunda unidad, por cantidad, al total del pedido, días y horario)
        if 'llevapaga' not in _tipo(cur, 'promociones', 'tipo'):
            run(cur, "ALTER TABLE promociones MODIFY COLUMN tipo ENUM('porcentaje','monto','llevapaga','segunda','pedido_pct','pedido_monto') NOT NULL")
        run(cur, 'ALTER TABLE promociones MODIFY COLUMN valor DECIMAL(10,2) NOT NULL DEFAULT 0')     # el «lleva N paga M» no usa valor
        for col, ddl in (('lleva', 'INT NULL'), ('paga', 'INT NULL'), ('min_cantidad', 'INT NOT NULL DEFAULT 1'), ('minimo_pedido', 'DECIMAL(10,2) NOT NULL DEFAULT 0'),
                         ('dias', 'VARCHAR(20) NULL'), ('hora_desde', 'TIME NULL'), ('hora_hasta', 'TIME NULL'), ('descripcion', 'VARCHAR(160) NULL')):
            if not _columna(cur, 'promociones', col):
                run(cur, f'ALTER TABLE promociones ADD COLUMN {col} {ddl}')
        if not _columna(cur, 'detalle_venta', 'descuento'):
            run(cur, 'ALTER TABLE detalle_venta ADD COLUMN descuento DECIMAL(10,2) NOT NULL DEFAULT 0')
        # --- cupones de descuento, vales personales y recompensas
        for ddl in DDL_CUPONES.split(';'):
            if ddl.strip():
                run(cur, ddl)
    log.info('Esquema verificado')
