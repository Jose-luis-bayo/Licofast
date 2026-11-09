-- =====================================================================
-- LicoFast · Base de datos (SDD v1.0, anexo B)  ·  compatible MySQL 8 / MariaDB 10.4+ (XAMPP)
-- Importar con phpMyAdmin (pestaña Importar) o:  python backend/scripts/init_db.py
-- Usuarios de demostración: clave de TODOS = Admin1234
-- =====================================================================
CREATE DATABASE IF NOT EXISTS licofast CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE licofast;

CREATE TABLE IF NOT EXISTS usuarios (
 id INT AUTO_INCREMENT PRIMARY KEY,
 nombre VARCHAR(80) NOT NULL,
 apellido VARCHAR(80) NOT NULL,
 ci VARCHAR(30) NOT NULL UNIQUE,
 fecha_nacimiento DATE NULL,
 edad INT NOT NULL DEFAULT 18,
 usuario VARCHAR(50) NOT NULL UNIQUE,
 password VARCHAR(255) NOT NULL,
 rol ENUM('cliente','administrador','cajero','repartidor','empleado') NOT NULL DEFAULT 'cliente',
 cargo VARCHAR(100) NULL,
 telefono VARCHAR(30) NULL,
 acepta_terminos TINYINT(1) NOT NULL DEFAULT 0,
 activo TINYINT(1) NOT NULL DEFAULT 1,
 intentos_fallidos INT NOT NULL DEFAULT 0,
 bloqueado_hasta DATETIME NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS categorias (
 id INT AUTO_INCREMENT PRIMARY KEY,
 nombre VARCHAR(80) NOT NULL UNIQUE,
 activo TINYINT(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS productos (
 id INT AUTO_INCREMENT PRIMARY KEY,
 nombre VARCHAR(120) NOT NULL,
 descripcion TEXT,
 precio DECIMAL(10,2) NOT NULL DEFAULT 0,
 stock INT NOT NULL DEFAULT 0,
 stock_minimo INT NOT NULL DEFAULT 5,
 imagen_url VARCHAR(255) NULL,
 categoria_id INT NULL,
 activo TINYINT(1) NOT NULL DEFAULT 1,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT ck_stock CHECK (stock >= 0),
 FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS promociones (
 id INT AUTO_INCREMENT PRIMARY KEY,
 nombre VARCHAR(100) NOT NULL,
 tipo ENUM('porcentaje','monto') NOT NULL,
 valor DECIMAL(10,2) NOT NULL,
 producto_id INT NULL,
 categoria_id INT NULL,
 desde DATE NOT NULL,
 hasta DATE NOT NULL,
 activo TINYINT(1) NOT NULL DEFAULT 1,
 FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE,
 FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ventas (
 id INT AUTO_INCREMENT PRIMARY KEY,
 usuario_id INT NULL,
 cajero_id INT NULL,
 repartidor_id INT NULL,
 tipo_venta ENUM('mostrador','delivery') NOT NULL DEFAULT 'delivery',
 canal ENUM('web','mostrador','whatsapp') NOT NULL DEFAULT 'web',
 total DECIMAL(10,2) NOT NULL DEFAULT 0,
 descuento DECIMAL(10,2) NOT NULL DEFAULT 0,
 monto_cobrado DECIMAL(10,2) NOT NULL DEFAULT 0,
 estado ENUM('pendiente','pagada','en_camino','entregada','no_entregado') NOT NULL DEFAULT 'pendiente',
 estado_pago ENUM('pendiente','pagado','anulado') NOT NULL DEFAULT 'pendiente',
 direccion_entrega VARCHAR(255) NULL,
 referencia_entrega VARCHAR(255) NULL,
 telefono_contacto VARCHAR(30) NULL,
 observacion_entrega VARCHAR(255) NULL,
 fecha_entrega DATETIME NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 KEY ix_ventas_estado (estado, estado_pago),
 KEY ix_ventas_usuario (usuario_id),
 FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL,
 FOREIGN KEY (cajero_id) REFERENCES usuarios(id) ON DELETE SET NULL,
 FOREIGN KEY (repartidor_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS detalle_venta (
 id INT AUTO_INCREMENT PRIMARY KEY,
 venta_id INT NOT NULL,
 producto_id INT NOT NULL,
 cantidad INT NOT NULL,
 precio_unitario DECIMAL(10,2) NOT NULL,
 FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
 FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS movimientos_stock (
 id INT AUTO_INCREMENT PRIMARY KEY,
 producto_id INT NOT NULL,
 tipo ENUM('inicial','entrada','ajuste','venta','reposicion') NOT NULL,
 cantidad INT NOT NULL,
 motivo VARCHAR(200) NULL,
 venta_id INT NULL,
 usuario_id INT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (producto_id) REFERENCES productos(id) ON DELETE CASCADE,
 FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE SET NULL,
 FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cajas (
 id INT AUTO_INCREMENT PRIMARY KEY,
 cajero_id INT NOT NULL,
 monto_inicial DECIMAL(10,2) NOT NULL,
 monto_esperado DECIMAL(10,2) NULL,
 monto_contado DECIMAL(10,2) NULL,
 abierta_en DATETIME NOT NULL,
 cerrada_en DATETIME NULL,
 FOREIGN KEY (cajero_id) REFERENCES usuarios(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pagos (
 id INT AUTO_INCREMENT PRIMARY KEY,
 venta_id INT NOT NULL,
 metodo ENUM('efectivo','qr') NOT NULL,
 monto DECIMAL(10,2) NOT NULL,
 estado ENUM('pendiente','confirmado','vencido','anulado') NOT NULL,
 referencia VARCHAR(60) NULL UNIQUE,
 id_transaccion VARCHAR(80) NULL,
 qr_payload VARCHAR(500) NULL,
 qr_expira_en DATETIME NULL,
 confirmado_en DATETIME NULL,
 motivo_anulacion VARCHAR(200) NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 KEY ix_pagos_venta (venta_id),
 FOREIGN KEY (venta_id) REFERENCES ventas(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS movimientos_caja (
 id INT AUTO_INCREMENT PRIMARY KEY,
 caja_id INT NOT NULL,
 pago_id INT NULL,
 tipo ENUM('ingreso','egreso') NOT NULL,
 monto DECIMAL(10,2) NOT NULL,
 concepto VARCHAR(200) NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (caja_id) REFERENCES cajas(id),
 FOREIGN KEY (pago_id) REFERENCES pagos(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS comprobantes (
 id INT AUTO_INCREMENT PRIMARY KEY,
 venta_id INT NOT NULL UNIQUE,
 numero VARCHAR(20) NOT NULL UNIQUE,
 emitido_en DATETIME NOT NULL,
 FOREIGN KEY (venta_id) REFERENCES ventas(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS auditoria (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 usuario_id INT NULL,
 accion VARCHAR(60) NOT NULL,
 entidad VARCHAR(40) NOT NULL,
 entidad_id INT NULL,
 detalle TEXT NULL,
 ip VARCHAR(45) NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 KEY ix_aud_fecha (created_at),
 FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS entregas (
 id INT AUTO_INCREMENT PRIMARY KEY,
 venta_id INT NOT NULL,
 repartidor_id INT NOT NULL,
 resultado ENUM('entregado','no_entregado') NULL,
 observacion VARCHAR(255) NULL,
 asignada_en DATETIME NOT NULL,
 cerrada_en DATETIME NULL,
 FOREIGN KEY (venta_id) REFERENCES ventas(id),
 FOREIGN KEY (repartidor_id) REFERENCES usuarios(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS idempotencia (
 clave VARCHAR(80) NOT NULL,
 usuario_id INT NOT NULL,
 ruta VARCHAR(120) NOT NULL,
 status INT NOT NULL DEFAULT 0,
 respuesta MEDIUMTEXT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (clave, usuario_id)
) ENGINE=InnoDB;

-- ---------------------------- Datos de demostración ----------------------------
INSERT IGNORE INTO usuarios (id,nombre,apellido,ci,fecha_nacimiento,edad,usuario,password,rol,cargo,telefono,acepta_terminos,activo) VALUES
(1,'Administrador','LicoFast','ADMIN-001','1990-01-01',TIMESTAMPDIFF(YEAR,'1990-01-01',CURDATE()),'admin_api','PBKDF2-SHA256$120000$3FZU7gRDy0qNo26e/+cpsw==$bYrwsPxna6jjZLC+U6zsq6sGW1Ted6enYiSTp3FMN3k=','administrador','Administrador general','70000001',1,1),
(2,'Carla','Perez','CAJA-001','1998-05-12',TIMESTAMPDIFF(YEAR,'1998-05-12',CURDATE()),'cajero1','PBKDF2-SHA256$120000$AJwgbEDpPq0UUKkGQHF7PQ==$1GFXna3gxC1JPwWZvTACUw9lFKf1tJfTyugf8tmj5/w=','cajero','Cajero de mostrador','70000002',1,1),
(3,'Luis','Mamani','REPA-001','1997-09-03',TIMESTAMPDIFF(YEAR,'1997-09-03',CURDATE()),'repartidor1','PBKDF2-SHA256$120000$Nyt37dNviW0K9GOXXEnhsg==$zriu7KLsmRuN0R+EgwmMyPwF6Jl4kO6KSZ1GzVPjB8s=','repartidor','Repartidor','70000003',1,1),
(4,'Marcos','Quispe','BODE-001','1995-11-20',TIMESTAMPDIFF(YEAR,'1995-11-20',CURDATE()),'bodega1','PBKDF2-SHA256$120000$98PiDlsfdXLjbf6rKM36ow==$bT33gC46DDBFBGi3xsdCbMSXAABYEjjiqUC4dlLSA6w=','empleado','Encargado de bodega','70000004',1,1),
(5,'Ana','Rojas','CLIE-001','1995-03-10',TIMESTAMPDIFF(YEAR,'1995-03-10',CURDATE()),'cliente1','PBKDF2-SHA256$120000$+priM+ldCXvHzPHcsLLPAA==$9PJGL+T65TKVUd9Hrk1wPDIH1KdL33CXUsHYpaolB1o=','cliente','Cliente','70000005',1,1);

INSERT IGNORE INTO categorias (id,nombre) VALUES (1,'Ron'),(2,'Vodka'),(3,'Whisky'),(4,'Cerveza'),(5,'Vino'),(6,'Singani'),(7,'Combos y Promociones');

INSERT IGNORE INTO productos (id,nombre,descripcion,precio,stock,stock_minimo,imagen_url,categoria_id,activo) VALUES
(1,'Ron añejo 750 ml','Ron añejo botella 750 ml',45.00,20,5,'img/carrusel1.webp',1,1),
(2,'Vodka premium 700 ml','Vodka premium botella 700 ml',55.00,20,5,NULL,2,1),
(3,'Whisky Buchanan\'s De Luxe 12 Años 750 ml','Whisky escocés de malta Buchanan\'s 12 años 750 ml',220.00,15,4,'img/buckanan.jpg',3,1),
(4,'Cerveza Paceña Six Pack 330 ml','Six pack de cerveza Paceña en botella de 330 ml',36.00,40,10,'img/cerveza1.jpg',4,1),
(5,'Vino tinto reserva 750 ml','Vino tinto reserva Kohlberg de Tarija 750 ml',60.00,18,4,'img/kolberg.jpeg',5,1),
(6,'Singani Casa Real Tradicional 750 ml','Singani boliviano de altura etiqueta negra 750 ml',85.00,20,4,'img/combo1.jpg',6,1),
(7,'Vino Valle de la Concepción Blanco 750 ml','Vino blanco joven Campos de Solana 750 ml',48.00,15,4,'img/valle.jpeg',5,1),
(8,'Cerveza Cordillera Lata 355 ml','Cerveza Cordillera lata individual 355 ml',9.00,60,12,'img/nuevo.jpg',4,1),
(9,'Whisky Johnnie Walker Black Label 750 ml','Whisky escocés 12 años etiqueta negra 750 ml',195.00,18,5,'img/blacklabel.jpeg',3,1),
(10,'Whisky Johnnie Walker Red Label 750 ml','Whisky escocés etiqueta roja 750 ml',115.00,22,5,'img/jhony.jpg',3,1),
(11,'Whisky Chivas Regal 12 Años 750 ml','Blended Scotch Whisky 12 años 750 ml',210.00,14,4,'img/chivas.jpeg',3,1),
(12,'Whisky Jack Daniel\'s Old No. 7 750 ml','Tennessee Whiskey original 750 ml',185.00,16,4,'img/jackd.jpg',3,1),
(13,'Whisky Royal Salute 21 Años 700 ml','The Signature Blend botella de porcelana de colección 700 ml',980.00,6,2,'img/3.jpeg',3,1),
(14,'Vino Aranjuez Tannat 750 ml','Vino tinto varietal Aranjuez de Tarija 750 ml',58.00,30,6,'img/aranjues.jpeg',5,1),
(15,'Vino Kohlberg Don Enzo Gran Reserva 750 ml','Vino tinto ícono de altura Kohlberg Don Enzo 750 ml',95.00,16,4,'img/images.jpeg',5,1),
(16,'Vino Navarro Correas Los Árboles 750 ml','Vino tinto Malbec Los Árboles 750 ml',65.00,20,5,'img/navar1.jpeg',5,1),
(17,'Vino 1750 Uvairenda Syrah 750 ml','Vino de valles cruceños Samaipata 750 ml',82.00,18,4,'img/uvairenda.jpeg',5,1),
(18,'Vino TRI Gran Reserva Campos de Solana 750 ml','Vino tinto trivarietal Gran Reserva 750 ml',145.00,12,3,'img/4.jpeg',5,1),
(19,'Cerveza Paceña Pilsener 620 ml','Cerveza Paceña botella retornable 620 ml',15.00,50,12,'img/pilsener.jpeg',4,1),
(20,'Cerveza Huari Tradicional 330 ml','Cerveza Huari botella de vidrio 330 ml',14.00,45,10,'img/huari.jpeg',4,1),
(21,'Cerveza Taquiña Export 330 ml','Cerveza cochabambina Taquiña 330 ml',12.00,40,10,'img/taquiña.jpeg',4,1),
(22,'Cerveza Potosina Especial 330 ml','Cerveza pilsener potosina de altura 330 ml',13.00,35,10,'img/potosina.jpeg',4,1),
(23,'Cerveza Sureña Especial 330 ml','Cerveza chuquisaqueña Sureña 330 ml',12.00,35,10,'img/sureña.jpeg',4,1),
(24,'Cerveza Ducal 330 ml','Cerveza Ducal botella 330 ml',11.00,30,8,'img/ducal.jpeg',4,1),
(25,'Singani San Pedro de Yunchará Sausini 750 ml','Singani tradicional destilado de uva de altura Sausini 750 ml',135.00,15,3,'img/sausini.jpeg',6,1),
(26,'Combo Chuflay Casa Real + Sprite + Hielo','1 Botella Casa Real + 1 Sprite 2L + bolsa de hielo + limones',95.00,20,5,'img/combo1.jpg',7,1),
(27,'Combo Johnnie Walker Red Label + Topo Chico + Hielo','1 Botella Red Label 750 ml + 1 Topo Chico 1.5L + bolsa de hielo',135.00,15,4,'img/combo2.jpeg',7,1),
(28,'Combo Chuflay Singani Rujero + 2 Ginger Ale','1 Botella Singani Rujero Colección + 2 botellas Ginger Ale',120.00,18,4,'img/promocion2.jpeg',7,1),
(29,'Pack Trilogía de Vinos Tintos Selección','Caja degustación 3 botellas de vinos tintos seleccionados',220.00,10,3,'img/promocion1.jpg',7,1),
(30,'Set de Lujo Whisky con Vasos y Balas de Acero','Caja de madera con 2 vasos de cristal y balas enfriadoras',260.00,8,2,'img/promo3.jpg',7,1);

INSERT IGNORE INTO movimientos_stock (producto_id,tipo,cantidad,motivo)
 SELECT p.id,'inicial',p.stock,'Stock inicial (carga de demostración)' FROM productos p
 WHERE NOT EXISTS (SELECT 1 FROM movimientos_stock m WHERE m.producto_id=p.id);

INSERT INTO promociones (nombre,tipo,valor,producto_id,categoria_id,desde,hasta,activo)
 SELECT 'Semana del vino -10%','porcentaje',10,NULL,5,CURDATE(),DATE_ADD(CURDATE(),INTERVAL 1 YEAR),1 FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM promociones);
