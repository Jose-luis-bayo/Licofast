import datetime
from decimal import Decimal, InvalidOperation
from .errors import invalido


def texto(d, campo, obligatorio=True, max_len=255):
    v = d.get(campo)
    v = v.strip() if isinstance(v, str) else v
    if v in (None, ''):
        if obligatorio:
            raise invalido(f'El campo «{campo}» es obligatorio', {'campo': campo})
        return None
    if not isinstance(v, str):
        v = str(v)
    if len(v) > max_len:
        raise invalido(f'«{campo}» supera {max_len} caracteres', {'campo': campo})
    return v


def entero(d, campo, minimo=None, obligatorio=True):
    v = d.get(campo)
    if v in (None, ''):
        if obligatorio:
            raise invalido(f'El campo «{campo}» es obligatorio', {'campo': campo})
        return None
    try:
        if isinstance(v, bool) or (isinstance(v, float) and v != int(v)):
            raise ValueError
        n = int(v)
    except (ValueError, TypeError):
        raise invalido(f'«{campo}» debe ser un número entero', {'campo': campo})
    if minimo is not None and n < minimo:
        raise invalido(f'«{campo}» debe ser al menos {minimo}', {'campo': campo})
    return n


def decimal(d, campo, minimo=None, obligatorio=True):
    v = d.get(campo)
    if v in (None, ''):
        if obligatorio:
            raise invalido(f'El campo «{campo}» es obligatorio', {'campo': campo})
        return None
    try:
        n = Decimal(str(v))
    except InvalidOperation:
        raise invalido(f'«{campo}» debe ser un número', {'campo': campo})
    if minimo is not None and n < Decimal(str(minimo)):
        raise invalido(f'«{campo}» debe ser al menos {minimo}', {'campo': campo})
    return n.quantize(Decimal('0.01'))


def fecha(valor, campo='fecha'):
    try:
        return datetime.date.fromisoformat(str(valor))
    except (ValueError, TypeError):
        raise invalido(f'«{campo}» debe tener formato AAAA-MM-DD', {'campo': campo})


def edad_exacta(nacimiento, hoy=None):
    """Años cumplidos reales (corrige el error días//365 del prototipo, H-09)."""
    hoy = hoy or datetime.date.today()
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def pagina(args, max_size=100):
    try:
        page = max(1, int(args.get('page', 1)))
        size = min(max_size, max(1, int(args.get('size', 20))))
    except ValueError:
        raise invalido('page y size deben ser enteros')
    return page, size, (page - 1) * size
