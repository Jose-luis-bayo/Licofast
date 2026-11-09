# LicoFast — versión final (SDD v1.0)

Sistema web de **e-commerce + punto de venta (POS)** para una licorería, con inventario, pagos (efectivo y QR) y delivery.
Esta carpeta contiene **el código que implementa el documento de diseño (SDD)**: un **servicio web REST** (`/api/v1`) con **4 módulos**
— **Seguridad, E-commerce, Pagos y Distribución** — organizado en el **modelo de 5 capas** del curso, más una aplicación web (SPA) para cada rol.

> Documento de diseño: [`docs/SDD_LicoFast.pdf`](docs/SDD_LicoFast.pdf) · Grupo N1 — USFX, Ingeniería de Sistemas.

---

## 1. Qué incluye

```
LicoFastFinal/
├── INICIAR.bat / iniciar.sh      ← arranque con un clic (Windows / Linux-macOS)
├── database/licofast.sql         ← esquema completo (14 tablas) + datos de demostración
├── backend/                      ← servicio REST (Python 3 + Flask + MySQL)
│   ├── run.py                    ← punto de entrada
│   ├── app/
│   │   ├── core/                 ← JWT, RBAC, errores, eventos (Observer), idempotencia, validadores
│   │   └── modules/
│   │       ├── seguridad/        ← controller · service · repository · facade   (Capas 2·3·4)
│   │       ├── ecommerce/        ← catálogo, promociones, inventario, pedidos, POS, State (EstadoPedido)
│   │       ├── pagos/            ← Strategy (efectivo/QR), Adapter (QrSasAdapter), caja, comprobantes
│   │       └── distribucion/     ← asignación, entregas, notificaciones (WhatsApp simulado)
│   ├── scripts/init_db.py        ← crea la BD sin necesitar el cliente mysql
│   ├── scripts/respaldo.py       ← respaldo con mysqldump
│   └── tests/                    ← 30 pruebas automáticas (escenarios del SDD)
├── frontend/                     ← aplicación web (HTML + CSS + JS), servida por el mismo servidor
└── docs/                         ← SDD en PDF
```

**Pantallas por rol:** visitante/cliente (catálogo, carrito, pedidos con seguimiento, pago por QR), cajero (POS, caja con arqueo, ventas, pedidos por WhatsApp),
bodega (inventario, entradas/ajustes, alertas), repartidor (entregas, historial), administrador (panel, usuarios y roles, productos, promociones,
asignación de pedidos, cobranzas, auditoría, respaldos).

---

## 2. Requisitos (en tu laptop)

| Herramienta | Para qué | Notas |
|---|---|---|
| **XAMPP** (MySQL/MariaDB) | Base de datos | Solo se usa **MySQL**. *Apache no es necesario* (el backend ya sirve la web). |
| **Python 3.11 o superior** | Backend | Al instalar en Windows marque **«Add Python to PATH»**. |
| **Git** | Clonar el repositorio | |
| **Antigravity** (o VS Code) | Editor | Cualquier editor sirve; las instrucciones son las mismas. |

---

## 3. Puesta en marcha paso a paso (XAMPP + Antigravity)

### Paso 1 — Clonar el repositorio
```bash
git clone https://github.com/FCCASTROCH/Licofast.git
cd Licofast/LicoFastFinal
```

### Paso 2 — Abrir el proyecto en Antigravity
`File ▸ Open Folder…` y elija la carpeta **`LicoFastFinal`**. Abra la terminal integrada (**Ctrl + `**).
*(Si usa el agente de Antigravity, puede pedirle: «ejecuta los pasos 3 a 6 del README». Los comandos son los mismos.)*

### Paso 3 — Iniciar MySQL en XAMPP
Abra el **Panel de control de XAMPP** y presione **Start** en **MySQL** (debe quedar en verde, puerto 3306).

### Paso 4 — Crear la base de datos (elija UNA opción)
* **Opción A (automática, recomendada):** el script del paso 6 la crea solo.
* **Opción B (phpMyAdmin):** abra <http://localhost/phpmyadmin> ▸ pestaña **Importar** ▸ seleccione `database/licofast.sql` ▸ **Continuar**.

### Paso 5 — Preparar Python
```bash
cd backend
python -m venv .venv
# Windows (PowerShell):   .venv\Scripts\Activate.ps1
# Windows (cmd):          .venv\Scripts\activate.bat
# Linux / macOS:          source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # Linux/macOS:  cp .env.example .env
```
> Si PowerShell bloquea el script de activación: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Paso 6 — Crear la base de datos y arrancar
```bash
python scripts/init_db.py      # crea la BD «licofast» con tablas y datos de demostración (puede repetirse sin riesgo)
python run.py
```
Abra **<http://localhost:5000>**.

> **Atajo:** en Windows basta con hacer doble clic en **`INICIAR.bat`** (con MySQL ya iniciado en XAMPP). Hace los pasos 5 y 6 por usted.

### Usuarios de demostración (clave de todos: `Admin1234`)

| Usuario | Rol | Entra a |
|---|---|---|
| `admin_api` | Administrador | Panel, usuarios, productos, promociones, pedidos, cobranzas, auditoría, respaldos |
| `cajero1` | Cajero | Punto de venta, caja, ventas, pedidos por WhatsApp |
| `bodega1` | Encargado de bodega (`empleado`) | Inventario |
| `repartidor1` | Repartidor | Entregas |
| `cliente1` | Cliente | Catálogo, carrito, pedidos |

---

## 4. Guion de demostración (≈ 6 minutos)

1. **Cliente (`cliente1`)**: en el catálogo agregue 2 vinos (verá la promoción −10 %) y una cerveza ▸ *Carrito* ▸ dirección, marcar «mayor de 18» ▸ **Confirmar pedido**.
2. En el detalle del pedido pulse **Pagar con QR** ▸ aparece el QR con monto y referencia ▸ pulse **«Demo: simular pago del banco»** → el sistema recibe el *webhook firmado* y marca el pedido como **pagado** (comprobante emitido).
3. **Cajero (`cajero1`)**: *Caja* ▸ abrir con Bs 100 ▸ *Punto de venta* ▸ agregar 2 productos ▸ **Cobrar** en efectivo ▸ se muestra el comprobante. Repita con **QR**. Luego cierre la caja con el arqueo.
4. **Administrador**: *Pedidos* ▸ asigne el pedido del cliente al repartidor. Revise *Panel*, *Cobranzas* y *Auditoría* (todo quedó registrado).
5. **Repartidor (`repartidor1`)**: *Entregas* ▸ **Salí a entregar** ▸ **Entregado** (o **No entregado**: el stock vuelve al inventario **una sola vez**).
6. **Bodega (`bodega1`)**: *Inventario* ▸ registre una **entrada** de stock y vea las alertas de stock bajo.
7. **Administrador ▸ Respaldos**: cree un respaldo de la base de datos.

---

## 5. Cómo se corresponde con el SDD

| SDD | Dónde está en el código |
|---|---|
| Capa 1 · Presentación | `frontend/` |
| Capa 2 · Interfaz / API (Front Controller, JWT, RBAC) | `app/modules/*/controller.py`, `app/core/auth.py` |
| Capa 3 · Lógica de aplicación (Service Layer, State, Strategy, Facade) | `app/modules/*/service.py`, `estado.py`, `strategies.py`, `facade.py` |
| Capa 4 · Acceso a datos (Repository) | `app/modules/*/repository.py`, `app/db.py` |
| Capa 5 · Almacén de datos | MySQL — `database/licofast.sql` |
| Observer (auditoría, notificaciones) | `app/core/events.py`, `AuditoriaService`, `notificacion.py` |
| Adapter del banco | `app/modules/pagos/adapter.py` |
| ADR-04 JWT · ADR-05 PBKDF2 · ADR-07 transacciones `FOR UPDATE` · ADR-10 baja lógica | `core/security.py`, `core/auth.py`, `InventarioService`, `UsuarioService` |

### Endpoints (todos bajo `/api/v1`)
| Módulo | Endpoints |
|---|---|
| Seguridad | `POST auth/login` · `POST auth/register` · `GET/PUT auth/me` · `POST auth/logout` · `GET/POST/PUT/DELETE usuarios` · `GET auditoria` · `POST admin/respaldo` · `GET admin/respaldos` |
| E-commerce | `GET/POST/PUT/DELETE productos` · `GET/POST/PUT categorias` · `GET/POST/PUT/DELETE promociones` · `POST carrito/cotizar` · `POST/GET pedidos` · `GET pedidos/{id}` · `POST pedidos/whatsapp` · `POST/GET ventas` · `GET clientes` · `GET/POST inventario/movimientos` · `GET inventario/alertas` · `GET reportes/resumen` |
| Pagos | `POST/GET pagos` · `GET pagos/{id}` · `POST pagos/webhook/qr` · `POST pagos/{id}/anular` · `POST cajas/apertura` · `GET cajas/actual` · `GET cajas` · `POST cajas/{id}/movimientos` · `POST cajas/{id}/cierre` · `GET comprobantes/{id}` · `GET comprobantes?venta_id=` |
| Distribución | `GET entregas` · `GET entregas/historial` · `PUT entregas/{id}/en-camino` · `PUT entregas/{id}` · `PUT pedidos/{id}/asignacion` · `GET pedidos/{id}/seguimiento` |

Formato de error uniforme: `{"error": {"codigo", "mensaje", "detalle", "traza"}}`. Los `POST /pedidos` y `POST /pagos` aceptan la cabecera `Idempotency-Key`.

---

## 6. Pagos QR y WhatsApp en modo demostración

* **QR (`QR_MODO=simulado`)**: el sistema genera una referencia y un QR reales (se dibuja en el navegador), y el botón *«Demo: simular pago del banco»* reproduce lo que haría el Banco Económico: un *webhook* firmado (HMAC-SHA256) que se valida por **firma, monto y referencia** y es **idempotente**.
  Cuando exista el contrato técnico del servicio SAS, solo hay que implementar `QrSasAdapter` (un archivo) y poner `QR_MODO=sas`.
* **WhatsApp**: las notificaciones se *simulan* y quedan en `backend/logs/whatsapp.log`. Para producción se reemplaza `WhatsAppClient.enviar` por la API de WhatsApp Business.

---

## 7. Pruebas automáticas
Con MySQL iniciado:
```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests -q
```
Las pruebas crean y borran su propia base `licofast_test` (no tocan `licofast`). Cubren, entre otros: token manipulado rechazado (EC-1), última botella con 4 compras simultáneas (EC-2), webhook de pago duplicado/firma inválida/monto incorrecto (EC-3), cierre doble de entrega sin duplicar stock, bloqueo de cuenta, edad exacta y propiedad de pedidos.

---

## 8. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `No se pudo conectar a MySQL` / `Can't connect to MySQL server` | Inicie **MySQL** en el panel de XAMPP. Si usa otro puerto (p. ej. 3307) ponga `DB_PORT=3307` en `backend/.env`. |
| `Access denied for user 'root'` | Si definió contraseña de root en XAMPP, póngala en `DB_PASSWORD=` del `.env`. |
| `python` no se reconoce | Reinstale Python marcando **Add to PATH**, o use `py -m venv .venv`. |
| El puerto 5000 está ocupado | En `backend/.env` ponga `PORT=5001` y abra `http://localhost:5001`. |
| La página dice «No se pudo conectar con el servidor» | El backend no está corriendo: ejecute `python run.py`. |
| Quiero empezar con datos limpios | `python scripts/init_db.py --reset` (borra y recrea la base). |
| Respaldos: «No se encontró mysqldump» | Ajuste `MYSQLDUMP_PATH` en `.env` (XAMPP: `C:\xampp\mysql\bin\mysqldump.exe`). |

---

## 9. Para pasar a producción (resumen)
Ver SDD §8.4: Nginx con TLS + Gunicorn (`pip install -r requirements-prod.txt`; `gunicorn -w 3 -b 127.0.0.1:8000 run:app`), MySQL 8 administrado (RDS), `JWT_SECRET` y `QR_SECRETO` propios y largos, `CORS_ORIGINS` con el dominio real, **cambiar o eliminar los usuarios de demostración**, respaldos diarios (`scripts/respaldo.py` con cron) y `QR_MODO=sas` cuando exista el contrato del banco.
> Nota: XAMPP incluye **MariaDB**, 100 % compatible con el esquema; en producción se recomienda MySQL 8 como indica el SDD.
