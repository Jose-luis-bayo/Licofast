"""Generador mínimo de PDF (sin dependencias): un comprobante de una página con tipografía estándar Helvetica."""
import re

_ANCHO = {**{str(d): 556 for d in range(10)}, '.': 278, ',': 278, ' ': 278, 'B': 667, 's': 500, '-': 333, ':': 278}


def _esc(t):
    b = t.encode('cp1252', 'replace').decode('cp1252')
    return b.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _ancho(t, size):
    return sum(_ANCHO.get(c, 500) for c in t) * size / 1000


class Pdf:
    def __init__(self, ancho=420, alto=595):          # A5 vertical (puntos)
        self.w, self.h, self.ops = ancho, alto, []

    def texto(self, x, y, t, size=11, negrita=False, derecha=False, gris=None, color=None):
        if derecha:
            x -= _ancho(t, size)
        if color:
            self.ops.append(f'{color[0]} {color[1]} {color[2]} rg')
        elif gris is not None:
            self.ops.append(f'{gris} g')
        else:
            self.ops.append('0.06 0.12 0.24 rg')
        self.ops.append(f"BT /{'F2' if negrita else 'F1'} {size} Tf {x:.1f} {self.h - y:.1f} Td ({_esc(t)}) Tj ET")

    def linea(self, x1, y1, x2, y2, grosor=0.8):
        self.ops.append(f'0.82 0.89 0.96 RG {grosor} w {x1:.1f} {self.h - y1:.1f} m {x2:.1f} {self.h - y2:.1f} l S')

    def rect(self, x, y, w, h, color):
        self.ops.append(f'{color[0]} {color[1]} {color[2]} rg {x:.1f} {self.h - y - h:.1f} {w:.1f} {h:.1f} re f')

    def bytes(self):
        contenido = '\n'.join(self.ops).encode('cp1252', 'replace')
        objs = [
            b'<< /Type /Catalog /Pages 2 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.w} {self.h}] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>'.encode(),
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>',
            b'<< /Length ' + str(len(contenido)).encode() + b' >>\nstream\n' + contenido + b'\nendstream',
        ]
        out, pos = bytearray(b'%PDF-1.4\n'), []
        for i, o in enumerate(objs, 1):
            pos.append(len(out))
            out += f'{i} 0 obj\n'.encode() + o + b'\nendobj\n'
        xref = len(out)
        out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode()
        for p in pos:
            out += f'{p:010d} 00000 n \n'.encode()
        out += f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
        return bytes(out)


def _recortar(t, maxpts, size):
    t = re.sub(r'\s+', ' ', str(t))
    while _ancho(t, size) > maxpts and len(t) > 4:
        t = t[:-2]
    return t if _ancho(t, size) <= maxpts else t


def comprobante_pdf(venta, items, numero=None):
    p = Pdf()
    p.rect(0, 0, p.w, 78, (0.043, 0.122, 0.294))
    p.texto(30, 40, 'LicoFast', 26, True, color=(1, 1, 1))
    p.texto(30, 60, 'Licores y bebidas · Sucre, Bolivia', 10, color=(0.58, 0.77, 0.99))
    p.texto(p.w - 30, 38, 'COMPROBANTE DE VENTA', 11, True, derecha=True, color=(1, 1, 1))
    p.texto(p.w - 30, 56, numero or f"Pedido #{venta['id']}", 11, derecha=True, color=(0.58, 0.77, 0.99))
    y = 108
    for etiqueta, valor in (('Cliente', venta.get('factura_nombre')), ('NIT / CI', venta.get('factura_nit')),
                            ('Teléfono', venta.get('factura_telefono')), ('Pedido', f"#{venta['id']}"),
                            ('Fecha', str(venta.get('created_at') or '')[:16])):
        p.texto(30, y, etiqueta, 10, gris=0.45)
        p.texto(110, y, _recortar(valor or '-', 270, 11), 11, True)
        y += 18
    y += 8
    p.rect(30, y - 12, p.w - 60, 20, (0.86, 0.92, 1.0))
    p.texto(36, y + 2, 'Cant.', 10, True)
    p.texto(80, y + 2, 'Producto', 10, True)
    p.texto(300, y + 2, 'P. unit.', 10, True, derecha=True)
    p.texto(p.w - 36, y + 2, 'Subtotal', 10, True, derecha=True)
    y += 24
    for i in items:
        if y > 470:
            p.texto(36, y, '... (ver detalle completo en el sistema)', 9, gris=0.45)
            break
        cant = i.get('cantidad', 1)
        sub = float(i.get('subtotal') if i.get('subtotal') is not None else float(i.get('precio_unitario', 0)) * cant)
        p.texto(36, y, str(cant), 11)
        p.texto(80, y, _recortar(i.get('nombre', 'Producto'), 175, 11), 11)
        p.texto(300, y, f"Bs {float(i.get('precio_unitario', 0)):.2f}", 10, derecha=True)
        p.texto(p.w - 36, y, f'Bs {sub:.2f}', 11, True, derecha=True)
        p.linea(30, y + 7, p.w - 30, y + 7, 0.5)
        y += 20
    y += 6
    if float(venta.get('descuento') or 0) > 0:
        p.texto(p.w - 150, y, 'Descuento', 10, gris=0.45)
        p.texto(p.w - 36, y, f"- Bs {float(venta['descuento']):.2f}", 10, derecha=True)
        y += 18
    p.texto(p.w - 150, y + 4, 'TOTAL', 13, True)
    p.texto(p.w - 36, y + 4, f"Bs {float(venta['total']):.2f}", 16, True, derecha=True, color=(0.114, 0.306, 0.847))
    pagado = venta.get('estado_pago') == 'pagado'
    p.texto(p.w - 36, y + 22, 'PAGADO' if pagado else 'PENDIENTE DE PAGO', 10, True, derecha=True, color=(0.08, 0.5, 0.24) if pagado else (0.7, 0.2, 0.1))
    y = max(y + 56, 440)
    p.rect(30, y, p.w - 60, 70, (0.86, 0.92, 1.0))
    p.texto(p.w / 2 - _ancho('Su código de retiro en bodega', 11) / 2, y + 20, 'Su código de retiro en bodega', 11, gris=0.35)
    cod = str(venta.get('codigo_retiro') or '----')
    p.texto(p.w / 2 - _ancho(cod, 34) / 2, y + 56, cod, 34, True, color=(0.114, 0.306, 0.847))
    p.texto(30, p.h - 34, 'Presente este código y su documento de identidad (mayores de 18 años) al retirar su pedido.', 8, gris=0.45)
    p.texto(30, p.h - 22, 'Este es un comprobante de venta, no una factura fiscal (SIN).', 8, gris=0.45)
    return p.bytes()
