"""Actualiza y añade productos, categorías e imágenes reales en la base de datos."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import mysql.connector
from app.config import Config

def main():
    conn = mysql.connector.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset='utf8mb4'
    )
    cur = conn.cursor()

    # 1. Asegurar categoría Combos y Promociones
    cur.execute("INSERT IGNORE INTO categorias (id, nombre, activo) VALUES (7, 'Combos y Promociones', 1)")

    # 2. Actualizar productos existentes
    actualizaciones = [
        ('Ron añejo 750 ml', 'Ron añejo botella 750 ml', 45.00, 'img/carrusel1.webp', 1),
        ('Vodka premium 700 ml', 'Vodka premium botella 700 ml', 55.00, None, 2),
        ("Whisky Buchanan's De Luxe 12 Años 750 ml", "Whisky escocés de malta Buchanan's 12 años 750 ml", 220.00, 'img/buckanan.jpg', 3),
        ('Cerveza Paceña Six Pack 330 ml', 'Six pack de cerveza Paceña en botella de 330 ml', 36.00, 'img/cerveza1.jpg', 4),
        ('Vino tinto reserva 750 ml', 'Vino tinto reserva Kohlberg de Tarija 750 ml', 60.00, 'img/kolberg.jpeg', 5),
        ('Singani Casa Real Tradicional 750 ml', 'Singani boliviano de altura etiqueta negra 750 ml', 85.00, 'img/combo1.jpg', 6),
        ('Vino Valle de la Concepción Blanco 750 ml', 'Vino blanco joven Campos de Solana 750 ml', 48.00, 'img/valle.jpeg', 7),
        ('Cerveza Cordillera Lata 355 ml', 'Cerveza Cordillera lata individual 355 ml', 9.00, 'img/nuevo.jpg', 8),
    ]
    for nombre, desc, precio, img, pid in actualizaciones:
        cur.execute(
            "UPDATE productos SET nombre=%s, descripcion=%s, precio=%s, imagen_url=%s WHERE id=%s",
            (nombre, desc, precio, img, pid)
        )

    # 3. Nuevos productos reales
    nuevos = [
        (9, 'Whisky Johnnie Walker Black Label 750 ml', 'Whisky escocés 12 años etiqueta negra 750 ml', 195.00, 18, 5, 'img/blacklabel.jpeg', 3),
        (10, 'Whisky Johnnie Walker Red Label 750 ml', 'Whisky escocés etiqueta roja 750 ml', 115.00, 22, 5, 'img/jhony.jpg', 3),
        (11, 'Whisky Chivas Regal 12 Años 750 ml', 'Blended Scotch Whisky 12 años 750 ml', 210.00, 14, 4, 'img/chivas.jpeg', 3),
        (12, "Whisky Jack Daniel's Old No. 7 750 ml", 'Tennessee Whiskey original 750 ml', 185.00, 16, 4, 'img/jackd.jpg', 3),
        (13, 'Whisky Royal Salute 21 Años 700 ml', 'The Signature Blend botella de porcelana de colección 700 ml', 980.00, 6, 2, 'img/3.jpeg', 3),
        (14, 'Vino Aranjuez Tannat 750 ml', 'Vino tinto varietal Aranjuez de Tarija 750 ml', 58.00, 30, 6, 'img/aranjues.jpeg', 5),
        (15, 'Vino Kohlberg Don Enzo Gran Reserva 750 ml', 'Vino tinto ícono de altura Kohlberg Don Enzo 750 ml', 95.00, 16, 4, 'img/images.jpeg', 5),
        (16, 'Vino Navarro Correas Los Árboles 750 ml', 'Vino tinto Malbec Los Árboles 750 ml', 65.00, 20, 5, 'img/navar1.jpeg', 5),
        (17, 'Vino 1750 Uvairenda Syrah 750 ml', 'Vino de valles cruceños Samaipata 750 ml', 82.00, 18, 4, 'img/uvairenda.jpeg', 5),
        (18, 'Vino TRI Gran Reserva Campos de Solana 750 ml', 'Vino tinto trivarietal Gran Reserva 750 ml', 145.00, 12, 3, 'img/4.jpeg', 5),
        (19, 'Cerveza Paceña Pilsener 620 ml', 'Cerveza Paceña botella retornable 620 ml', 15.00, 50, 12, 'img/pilsener.jpeg', 4),
        (20, 'Cerveza Huari Tradicional 330 ml', 'Cerveza Huari botella de vidrio 330 ml', 14.00, 45, 10, 'img/huari.jpeg', 4),
        (21, 'Cerveza Taquiña Export 330 ml', 'Cerveza cochabambina Taquiña 330 ml', 12.00, 40, 10, 'img/taquiña.jpeg', 4),
        (22, 'Cerveza Potosina Especial 330 ml', 'Cerveza pilsener potosina de altura 330 ml', 13.00, 35, 10, 'img/potosina.jpeg', 4),
        (23, 'Cerveza Sureña Especial 330 ml', 'Cerveza chuquisaqueña Sureña 330 ml', 12.00, 35, 10, 'img/sureña.jpeg', 4),
        (24, 'Cerveza Ducal 330 ml', 'Cerveza Ducal botella 330 ml', 11.00, 30, 8, 'img/ducal.jpeg', 4),
        (25, 'Singani San Pedro de Yunchará Sausini 750 ml', 'Singani tradicional destilado de uva de altura Sausini 750 ml', 135.00, 15, 3, 'img/sausini.jpeg', 6),
        (26, 'Combo Chuflay Casa Real + Sprite + Hielo', '1 Botella Casa Real + 1 Sprite 2L + bolsa de hielo + limones', 95.00, 20, 5, 'img/combo1.jpg', 7),
        (27, 'Combo Johnnie Walker Red Label + Topo Chico + Hielo', '1 Botella Red Label 750 ml + 1 Topo Chico 1.5L + bolsa de hielo', 135.00, 15, 4, 'img/combo2.jpeg', 7),
        (28, 'Combo Chuflay Singani Rujero + 2 Ginger Ale', '1 Botella Singani Rujero Colección + 2 botellas Ginger Ale', 120.00, 18, 4, 'img/promocion2.jpeg', 7),
        (29, 'Pack Trilogía de Vinos Tintos Selección (3 botellas)', 'Caja degustación 3 botellas de vinos tintos seleccionados', 220.00, 10, 3, 'img/promocion1.jpg', 7),
        (30, 'Set de Lujo Whisky con Vasos y Balas de Acero', 'Caja de madera con 2 vasos de cristal y balas enfriadoras', 260.00, 8, 2, 'img/promo3.jpg', 7),
    ]

    for p in nuevos:
        cur.execute("""
            INSERT INTO productos (id, nombre, descripcion, precio, stock, stock_minimo, imagen_url, categoria_id, activo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE
                nombre = VALUES(nombre),
                descripcion = VALUES(descripcion),
                precio = VALUES(precio),
                imagen_url = VALUES(imagen_url),
                categoria_id = VALUES(categoria_id),
                activo = 1
        """, p)

    # 4. Asegurar movimientos de stock inicial
    cur.execute("""
        INSERT IGNORE INTO movimientos_stock (producto_id, tipo, cantidad, motivo)
        SELECT p.id, 'inicial', p.stock, 'Stock inicial (carga de demostración)'
        FROM productos p
        WHERE NOT EXISTS (SELECT 1 FROM movimientos_stock m WHERE m.producto_id = p.id)
    """)

    # 5. Promociones
    cur.execute("""
        INSERT INTO promociones (nombre, tipo, valor, producto_id, categoria_id, desde, hasta, activo)
        SELECT 'Semana del vino -10%', 'porcentaje', 10, NULL, 5, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 1 YEAR), 1
        FROM DUAL
        WHERE NOT EXISTS (SELECT 1 FROM promociones WHERE categoria_id = 5)
    """)

    conn.commit()
    print("¡Base de datos actualizada con éxito con todos los productos e imágenes!")
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
