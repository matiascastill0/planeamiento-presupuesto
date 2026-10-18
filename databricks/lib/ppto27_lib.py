"""Librería común del pipeline Ppto27 (Databricks y pruebas locales). Python puro: no usa Spark.

Contenido
  · Configuración: rutas del Volume, nombres de tablas, encabezado estándar de Tabla1.
  · identificar(): rubro / sub-rubro / área / país / id_plantilla a partir de la ruta de carpetas (carga "en frío").
  · leer_plantilla(): Excel → filas crudas de Tabla1 (bronze). Valor, tipo y fórmula de cada celda, sin interpretar.
  · monto(): interpreta una celda de monto (silver) y devuelve el flag si viene mal escrita.
  · Homologación de textos (silver): cuentas contables y proveedores contra los maestros + tabla de alias aprobados.

En Databricks vive en el Volume (ppto27/00_codigo) y los notebooks la importan con sys.path. Requiere openpyxl
(`%pip install openpyxl` en el primer comando del notebook).
"""
import hashlib, json, os, re, unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher

# ───────────────────────────── configuración ─────────────────────────────
CATALOGO_UC = os.environ.get('PPTO27_CATALOGO', 'catalogo_ppto')
ESQUEMA = os.environ.get('PPTO27_ESQUEMA', 'esquema_ppto')
VOLUME = os.environ.get('PPTO27_VOLUME', f'/Volumes/{CATALOGO_UC}/{ESQUEMA}/vol_administrado/ppto27')
FORMATO = os.environ.get('PPTO27_FORMATO', 'delta')                            # parquet sólo en la prueba local
CODIGO = f'{VOLUME}/00_codigo'                 # estas librerías (los notebooks las importan desde aquí)
ENTRADA = f'{VOLUME}/10_entrada'               # bandeja: se sube TODO aquí (zips de SharePoint, Excel sueltos, carpetas)
PROCESADO = f'{VOLUME}/11_procesado'           # lo recibido, ya ordenado por carga (<carga_id>/ y REF_<carga_id>/)
BI = f'{VOLUME}/30_bi'                         # zip con los CSV que lee el Power BI
MAESTROS = f'{VOLUME}/90_maestros'             # maestros, alias y drivers (xlsx, se suben a mano)
CARGAS = PROCESADO


def tabla(nombre):
    """Nombre completo de 3 niveles. Capas por prefijo (no hay permiso de CREATE SCHEMA): brz_, slv_, gld_, ctl_."""
    if CATALOGO_UC == 'local':                                                 # prueba local: base default de Spark
        return f'ppto27_{nombre}'
    return f'{CATALOGO_UC}.{ESQUEMA}.ppto27_{nombre}'


ENCABEZADO = ['País', 'Vehículo', 'Ceco - Nombre', 'Sede', 'Nom Cta Contable', 'Nivel 1', 'Nivel 2', 'Nivel 3',
              'Nivel 4\nArtículo', 'Proveedor', 'Glosa / Texto', 'Comentario de Área', 'Moneda',
              'Ene-26', 'Feb-26', 'Mar-26', 'Abr-26', 'May-26', 'Jun-26', 'Jul-26', 'Ago-26',
              'Set-26', 'Oct-26', 'Nov-26', 'Dic-26', 'F26',
              'Ene-27', 'Feb-27', 'Mar-27', 'Abr-27', 'May-27', 'Jun-27', 'Jul-27', 'Ago-27',
              'Set-27', 'Oct-27', 'Nov-27', 'Dic-27', 'P27', 'Var. %\nP27 vs F26', 'Var. #\nP27 vs F26']
# nombres de columna en las tablas (snake_case, sin tildes) en el mismo orden A..AO
COLUMNAS = ['pais', 'vehiculo', 'ceco_nombre', 'sede', 'nom_cta_contable', 'nivel_1', 'nivel_2', 'nivel_3', 'nivel_4',
            'proveedor', 'glosa', 'comentario_area', 'moneda',
            *[f'real_2026_{m:02d}' for m in range(1, 9)], *[f'fc_2026_{m:02d}' for m in range(9, 13)], 'f26',
            *[f'ppto_2027_{m:02d}' for m in range(1, 13)], 'p27', 'var_pct', 'var_abs']
NCOL = len(ENCABEZADO)                                                         # 41 (A..AO)
COL_TEXTO = COLUMNAS[:13]
COL_PPTO = [f'ppto_2027_{m:02d}' for m in range(1, 13)]
COL_REAL = [f'real_2026_{m:02d}' for m in range(1, 9)]

RUBROS = {'02': 'Gastos de Personal', '03': 'Gastos Administrativos', '04': 'Tecnología y Comunicaciones',
          '05': 'Depreciación y Amortización', '06': 'Impuestos y contribuciones'}
PAISES = {'PERU': 'Perú', 'COLOMBIA': 'Colombia', 'CHILE': 'Chile', 'PANAMA': 'Panamá', 'US': 'USA', 'USA': 'USA',
          'MEXICO': 'México'}
MONEDA_LOCAL = {'Perú': 'PEN', 'Colombia': 'COP', 'Chile': 'CLP', 'Panamá': 'USD', 'USA': 'USD', 'México': 'PEN'}
NO_PLANTILLA = re.compile(r'^(~\$|\.)|checklist|validaci[oó]n ruta', re.I)    # archivos de control de la ruta, locks


# ───────────────────────────── texto ─────────────────────────────
INVISIBLES = re.compile('[​-‏  ⁠﻿\x00-\x08\x0b\x0c\x0e-\x1f]')
MOJIBAKE = re.compile(r'Ã[\x80-\xbf¡-ÿ]|Â[\xa0-\xbf]|â€|�|╠|Ì\x81|ï¿½|\+�')


def sin_tildes(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn')


def fix_mojibake(s):
    """'CompaÃ±Ã­a' → 'Compañía' (UTF-8 leído como Latin-1). Repara tramo por tramo, así un texto que mezcla
    tildes sanas y dañadas también se corrige."""
    def rep(m):
        try:
            return m.group(0).encode('latin1').decode('utf8')
        except UnicodeError:
            return m.group(0)
    return re.sub('[\xc2-\xf4][\x80-\xbf]+', rep, s) if ('Ã' in s or 'Â' in s) else s


def limpiar(s):
    """Texto tal como debe guardarse en silver: sin invisibles, sin espacios dobles, tildes reparadas, NFC."""
    if s is None:
        return None
    s = fix_mojibake(INVISIBLES.sub('', str(s)).replace('\xa0', ' '))
    s = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', s)).strip()
    return s or None


def clave_texto(s):
    """Clave de comparación: sin tildes, mayúsculas, sólo letras y números."""
    s = sin_tildes(limpiar(s) or '').upper()
    return re.sub(r'[^A-Z0-9]+', ' ', s).strip()


def sin_prefijo(s):
    return re.sub(r'^\d+\.\s*', '', s).strip()


# ───────────────────────────── identificación de la plantilla ─────────────────────────────
def _pais_de(texto):
    toks = re.findall(r'[A-Z]+', sin_tildes(texto).upper())
    for t in toks:
        if t in PAISES:
            return PAISES[t]
    return None


def _nombre_base(archivo):
    """Nombre del archivo sin 'Ppto27 - ', '- OFICIAL', versiones ni copias: identifica la plantilla aunque el área
    le cambie el sufijo ('v2', '(1)', 'final', fecha…)."""
    s = sin_tildes(os.path.splitext(archivo)[0]).upper()
    s = re.sub(r'^PPTO\s*2?7?\s*-\s*', '', s)
    s = re.sub(r'\(\s*\d+\s*\)|\bCOPIA\b|\bCOPY\b|\bFINAL\b|\bOFICIAL\b|\bV\s*\d+\b|\bVF\b|\b\d{6,8}\b|\b\d{1,2}[-_.]\d{1,2}[-_.]\d{2,4}\b', ' ', s)
    s = re.sub(r'[^A-Z0-9]+', ' ', s)
    # el país no forma parte del nombre: lo da la carpeta (o el nombre, como respaldo) en id_plantilla.
    # Así "Remuneración fija, RV e ICP Chile - OFICIAL" = "Remuneración fija, RV e ICP" de la carpeta CHILE.
    s = ' '.join(t for t in s.split() if t not in PAISES)
    return re.sub(r'\s+', ' ', s).strip()


def identificar(ruta_relativa):
    """Ruta relativa dentro de la carga ('03. Gastos Administrativos/UDN/MDK/01. PERU/Ppto27 - MDK Peru - OFICIAL.xlsx')
    → dict con rubro, sub_rubro, tipo, area, pais, id_plantilla. Funciona con cualquier profundidad de carpetas."""
    partes = [p for p in ruta_relativa.replace('\\', '/').split('/') if p]
    archivo, carpetas = partes[-1], partes[:-1]
    i = next((k for k, p in enumerate(carpetas) if re.match(r'^0[2-6]\.', p)), None)
    cod = carpetas[i][:2] if i is not None else None
    debajo = carpetas[i + 1:] if i is not None else carpetas
    pais = next((PAISES[sin_tildes(sin_prefijo(c)).upper()] for c in debajo if sin_tildes(sin_prefijo(c)).upper() in PAISES), None)
    pais = pais or _pais_de(archivo)
    sin_pais = [c for c in debajo if sin_tildes(sin_prefijo(c)).upper() not in PAISES]
    tipo, area, sub = 'Rubro', None, None
    if sin_pais and sin_pais[0].upper() in ('UDN', 'STAFF'):
        tipo = 'UdN' if sin_pais[0].upper() == 'UDN' else 'Staff'
        area = sin_prefijo(sin_pais[1]).replace('Staff - ', '').strip() if len(sin_pais) > 1 else None
        sub = 'UDN' if tipo == 'UdN' else 'STAFF'
    elif sin_pais:
        sub = sin_pais[0]
    base = _nombre_base(archivo)
    id_plantilla = ' | '.join(x for x in [cod or '??', clave_texto(sub or ''), clave_texto(area or ''), pais or 'REGIONAL', base] if x)
    return dict(rubro_cod=cod, rubro=RUBROS.get(cod), sub_rubro=sub, tipo=tipo, area=area, pais_carpeta=pais or 'Regional',
                nombre_base=base, id_plantilla=id_plantilla)


def es_plantilla(archivo):
    return archivo.lower().endswith('.xlsx') and not NO_PLANTILLA.search(os.path.basename(archivo))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


# ───────────────────────────── lectura de la plantilla (bronze) ─────────────────────────────
ERRORES_XL = ('#REF!', '#VALUE!', '#DIV/0!', '#N/A', '#NAME?', '#NUM!', '#NULL!', '#SPILL!', '#CALC!')


def _celda(v):
    """(texto, tipo) sin interpretar. tipo: n número · s texto · d fecha · b booleano · e error de Excel."""
    if v is None:
        return None, None
    if isinstance(v, bool):
        return str(v), 'b'
    if isinstance(v, (int, float)):
        return repr(float(v)) if isinstance(v, float) else str(v), 'n'
    if isinstance(v, (datetime, date)):
        return v.isoformat(), 'd'
    s = str(v)
    return s, ('e' if s.strip().upper() in ERRORES_XL else 's')


def _num_tc(v):
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).replace('\xa0', '').replace(',', '').strip()
    try:
        return float(s)
    except ValueError:
        return None


_NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
       'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
       'pr': 'http://schemas.openxmlformats.org/package/2006/relationships'}


def _abrir(fuente):
    """Ruta en disco o contenido del archivo (bytes, como lo entrega Spark binaryFile)."""
    import io
    return io.BytesIO(fuente) if isinstance(fuente, (bytes, bytearray)) else fuente


def _tabla_de_hoja(path, hoja='Ppto27', nombre='Tabla1'):
    """(ref, filas de totales) de la tabla `nombre` en la hoja `hoja`, leyendo sólo el XML (sin abrir el libro).
    None si la hoja no existe; '' si la hoja existe pero no tiene esa tabla."""
    import posixpath, zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(_abrir(path)) as z:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rid = next((s.get(f"{{{_NS['r']}}}id") for s in wb.iterfind('.//m:sheet', _NS) if s.get('name') == hoja), None)
        if rid is None:
            return None
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        destino = next(r.get('Target') for r in rels.iterfind('pr:Relationship', _NS) if r.get('Id') == rid)
        hoja_xml = posixpath.normpath(destino.lstrip('/') if destino.startswith('/') else posixpath.join('xl', destino))
        rel_hoja = posixpath.join(posixpath.dirname(hoja_xml), '_rels', posixpath.basename(hoja_xml) + '.rels')
        if rel_hoja not in z.namelist():
            return ''
        for r in ET.fromstring(z.read(rel_hoja)).iterfind('pr:Relationship', _NS):
            if r.get('Type', '').endswith('/table'):
                tg = r.get('Target')
                tg = tg.lstrip('/') if tg.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(hoja_xml), tg))
                t = ET.fromstring(z.read(tg))
                if t.get('displayName') == nombre or t.get('name') == nombre:
                    return t.get('ref'), int(t.get('totalsRowCount') or 0)
    return ''


def leer_plantilla(path):
    """Lee una plantilla sin interpretar nada. Devuelve (archivo, lineas):
       archivo: hojas, estado, encabezado, tipo de cambio de la cabecera, celdas fuera de Tabla1, listas de la hoja Tablas.
       lineas : una por fila de Tabla1 → {fila, <41 columnas como texto>, tipos (41 letras), formulas (json)}.
    El valor de una celda con fórmula es el último valor calculado por Excel; la fórmula va aparte.
    Se abre en modo sólo lectura y se recorre únicamente la hoja Ppto27 (y el rango de listas de Tablas): las hojas
    pesadas (TD - Ppto26, BD - Ppto26) no se cargan."""
    import openpyxl
    from openpyxl.utils import range_boundaries
    wb = openpyxl.load_workbook(_abrir(path), read_only=True)                        # fórmulas
    wbv = openpyxl.load_workbook(_abrir(path), read_only=True, data_only=True)       # valores calculados por Excel
    try:
        A = dict(hojas=json.dumps(wb.sheetnames, ensure_ascii=False), tablas_oculta=None,
                 estado='OK', error=None, ref_tabla=None, encabezado=None, n_lineas=0, fila_totales=0,
                 tc=None, fuera_tabla=None, listas=None, leyenda=None)
        if 'Tablas' in wb.sheetnames:
            A['tablas_oculta'] = wb['Tablas'].sheet_state != 'visible'
        t = _tabla_de_hoja(path)
        if t is None:
            A.update(estado='RECHAZADO', error='F01')
            return A, []
        if t == '':
            A.update(estado='RECHAZADO', error='F02')
            return A, []
        ref, tot = t
        c1, r0, c2, r1 = range_boundaries(ref)
        ancho = max(c2, NCOL)
        F = list(wb['Ppto27'].iter_rows(min_row=1, max_col=ancho + 5, values_only=True))
        V = list(wbv['Ppto27'].iter_rows(min_row=1, max_col=ancho + 5, values_only=True))
        celda = lambda M, r, c: (M[r - 1][c - 1] if r - 1 < len(M) and c - 1 < len(M[r - 1]) else None)
        enc = [celda(F, r0, c) for c in range(1, ancho + 1)]
        A.update(ref_tabla=ref, encabezado=json.dumps(enc, ensure_ascii=False, default=str), fila_totales=tot)
        if c1 != 1 or c2 != NCOL:
            A.update(estado='RECHAZADO', error='F03')
            return A, []
        # tipo de cambio de la cabecera (filas 3–5, columnas AA..AL = Ene-27..Dic-27): PEN, COP, CLP por 1 USD
        A['tc'] = json.dumps({mon: [_num_tc(celda(V, r, c)) for c in range(27, 39)] for r, mon in ((3, 'PEN'), (4, 'COP'), (5, 'CLP'))})
        lineas = []
        for r in range(r0 + 1, r1 + 1 - tot):
            fila = {'fila': r}
            tipos, formulas = [], {}
            for j in range(NCOL):
                crudo, calc = celda(F, r, j + 1), celda(V, r, j + 1)
                if isinstance(crudo, str) and crudo.startswith('='):
                    formulas[COLUMNAS[j]] = crudo
                    txt, tp = _celda(calc)
                    tp = 'f' if tp is None else tp.upper()             # mayúscula = viene de fórmula
                else:
                    txt, tp = _celda(crudo)
                fila[COLUMNAS[j]] = txt
                tipos.append(tp or '-')
            fila['tipos'] = ''.join(tipos)
            fila['formulas'] = json.dumps(formulas, ensure_ascii=False) if formulas else None
            lineas.append(fila)
        A['n_lineas'] = len(lineas)
        A['leyenda'] = json.dumps({str(celda(V, r, 8)).strip(): str(celda(V, r, 9)).strip() for r in range(3, r0)
                                   if celda(V, r, 8) and celda(V, r, 9)}, ensure_ascii=False)
        fuera = [(f'{_col(c + 1)}{r + 1}', str(v)) for r in range(r0 - 1, len(F)) for c, v in enumerate(F[r])
                 if v not in (None, '') and (r + 1 > r1 or c + 1 > c2)]
        A['fuera_tabla'] = json.dumps(fuera[:200], ensure_ascii=False) if fuera else None
        listas = {}
        for n in ('Proveedor', 'Ceco_Nombre', 'Nivel_1', 'Moneda', 'País'):
            if n in wb.defined_names:
                vals = []
                for hoja, rng in wb.defined_names[n].destinations:
                    if hoja not in wbv.sheetnames:
                        continue
                    a1, f1, a2, f2 = range_boundaries(rng.replace('$', ''))
                    for row in wbv[hoja].iter_rows(min_row=f1, max_row=f2, min_col=a1, max_col=a2, values_only=True):
                        vals += [str(v).strip() for v in row if v not in (None, '')]
                listas[n] = vals
        A['listas'] = json.dumps(listas, ensure_ascii=False) if listas else None
        return A, lineas
    finally:
        wb.close()
        wbv.close()


def _col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# ───────────────────────────── montos (silver) ─────────────────────────────
def monto(txt, tipo, formula=None):
    """Celda de monto leída en bronze → (valor | None, flag | None, detalle)."""
    if txt is None or tipo in (None, '-'):
        return (None, 'M05', f'{formula} (sin valor calculado)') if formula else (None, None, '')
    t = tipo.lower()
    if t == 'n':
        v = float(txt)
        if formula:
            f = formula[1:].replace(' ', '')
            if '[' in f and '!' in f:
                return None, 'M07', formula
            return v, ('M04' if re.fullmatch(r'[\d\.\+\-\*/\(\)]+', f) else 'M08'), formula
        return v, ('M11' if v == 0 else None), ''
    if t == 'b':
        return None, 'M03', f'booleano {txt}'
    if t == 'd':
        return None, 'M06', f'fecha {txt[:10]}'
    if t == 'e':
        return None, 'M05', txt
    s = INVISIBLES.sub('', txt).replace('\xa0', ' ').strip()
    if s == '':
        return None, 'M02', repr(txt)
    x = s.replace('S/', '').replace('$', '')
    for m in ('USD', 'COP', 'CLP', 'PEN', 'MXN'):
        x = x.replace(m, '')
    x = x.strip()
    neg = x.startswith('(') and x.endswith(')')
    x = x.strip('()').replace(' ', '')
    if re.fullmatch(r'-?\d{1,3}(\.\d{3})+(,\d+)?', x):
        x = x.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'-?\d{1,3}(,\d{3})+(\.\d+)?', x):
        x = x.replace(',', '')
    elif re.fullmatch(r'-?\d+,\d{1,2}', x):
        x = x.replace(',', '.')
    try:
        v = float(x)
        return (-abs(v) if neg else v), 'M03', repr(txt)
    except ValueError:
        return None, 'M09', repr(txt)


# ───────────────────────────── homologación de cuentas y proveedores (silver) ─────────────────────────────
LEGAL = {'S', 'A', 'SA', 'SAS', 'SAC', 'SAA', 'SPA', 'SRL', 'SCRL', 'EIRL', 'LTDA', 'LIMITADA', 'LTD', 'LIMITED', 'INC', 'CORP',
         'CORPORATION', 'CORPORACION', 'LLC', 'LLP', 'LP', 'PLC', 'GMBH', 'BV', 'NV', 'AG', 'SOCIEDAD', 'ANONIMA', 'CERRADA',
         'ABIERTA', 'CIVIL', 'RESPONSABILIDAD', 'SOCIEDADES', 'COMERCIAL', 'CIA', 'COMPANIA', 'CO', 'Y', 'E', 'DE', 'DEL', 'LA',
         'EL', 'LOS', 'LAS', 'SUCURSAL', 'SC', 'SL', 'SE', 'CV', 'RL', 'R', 'L', 'C', 'P', 'SCP', 'THE'}
SIN_PROVEEDOR = {'', '(SIN PROVEEDOR)', 'SIN PROVEEDOR'}
RELLENO = re.compile(r'^(no\s*est[aá]|por\s*definir|pendiente|xxx+|n/?a|\?+|-+|\.+|tbd|sin\s*dato|otro?s?|proveedor|nuevo)$', re.I)
VARIOS = re.compile(r'^\s*\(?\s*VARIO', re.I)


def clave_proveedor(nombre):
    """Misma empresa escrita distinto → misma clave: sin tildes, sin puntuación, sin forma societaria, sin orden."""
    s = sin_tildes(fix_mojibake(str(nombre))).upper().replace('&', ' AND ')
    tk = [t for t in re.sub(r'[^A-Z0-9 ]+', ' ', s).split() if t]
    sig = [t for t in tk if t not in LEGAL] or tk
    return ' '.join(sorted(set(sig)))


def _parecido(a, b):
    return SequenceMatcher(None, a, b).ratio()


class Homologador:
    """Busca cada texto en: 1) maestro tal cual · 2) maestro por clave normalizada · 3) alias aprobados ·
    4) sugerencia por parecido (umbral) · 5) nuevo. Devuelve (oficial, método, parecido)."""

    def __init__(self, oficiales, clave, alias=None, umbral=0.92):
        self.clave = clave
        self.exacto = {o: o for o in oficiales}
        self.por_clave = {}
        for o in oficiales:
            self.por_clave.setdefault(clave(o), o)
        self.alias = {clave(a): o for a, o in (alias or {}).items()}
        self.umbral = umbral
        self._claves = list(self.por_clave)
        self._cache = {}

    def buscar(self, texto):
        if texto in self._cache:
            return self._cache[texto]
        if texto in self.exacto:
            r = (texto, 'exacto', 1.0)
        else:
            k = self.clave(texto)
            if k in self.por_clave:
                r = (self.por_clave[k], 'normalizado', 1.0)
            elif k in self.alias:
                r = (self.alias[k], 'alias aprobado', 1.0)
            else:
                cand = max(self._claves, key=lambda c: _parecido(k, c), default=None)
                p = _parecido(k, cand) if cand else 0.0
                tk = set(k.split())
                contiene = [c for c in self._claves if tk and tk < set(c.split())] if all(len(t) >= 5 for t in tk) else []
                if p >= self.umbral:
                    r = (self.por_clave[cand], 'sugerido', round(p, 3))
                elif len(contiene) == 1:                       # 'AVIATUR' ⊂ 'AGENCIA DE VIAJES Y TURISMO AVIATUR SAS'
                    r = (self.por_clave[contiene[0]], 'sugerido', round(p, 3))
                else:
                    r = (None, 'nuevo', round(p, 3))
        self._cache[texto] = r
        return r


def homologar_cuenta(h, nombre):
    """Cuenta contable → (cuenta oficial, método, flag)."""
    n = limpiar(nombre)
    if n is None or n == '(blank)':
        return n, 'vacía', None                       # Personal usa '(blank)' en líneas de provisión: permitido
    of, met, p = h.buscar(n)
    flag = {'exacto': None, 'normalizado': 'L15', 'alias aprobado': 'L15', 'sugerido': 'L16', 'nuevo': 'L17'}[met]
    return (of or n), met, flag


def homologar_proveedor(h, nombre):
    """Proveedor → (proveedor oficial, método, flag)."""
    n = limpiar(nombre)
    if n is None or n.upper() in SIN_PROVEEDOR or n.startswith('('):
        return (n or None), 'sin proveedor', None     # vacío, '(sin proveedor)', '(N proveedores menores)'
    if VARIOS.search(n):
        return n, 'varios', 'L18'
    if RELLENO.match(n):
        return n, 'relleno', 'L07'
    of, met, p = h.buscar(n)
    flag = {'exacto': None, 'normalizado': None, 'alias aprobado': None, 'sugerido': 'L19', 'nuevo': 'L08'}[met]
    return (of or n.upper()), met, flag


# ───────────────────────────── catálogo de flags ─────────────────────────────
# código: (categoría, severidad, nombre, regla, acción)
CATALOGO = {
    'F01': ('Archivo', 'BLOQUEANTE', 'Falta la hoja Ppto27', 'La hoja fue renombrada o borrada', 'Rechazar archivo y devolver al área'),
    'F02': ('Archivo', 'BLOQUEANTE', 'Falta la tabla Tabla1', 'Convirtieron la tabla en rango o la renombraron', 'Rechazar archivo'),
    'F03': ('Archivo', 'BLOQUEANTE', 'Columnas insertadas, borradas o movidas', 'El encabezado no coincide en cantidad/orden con el estándar A..AO', 'Rechazar archivo'),
    'F04': ('Archivo', 'ALERTA', 'Encabezado con caracteres dañados', 'Mismo orden y cantidad, pero el texto del título cambió (p. ej. "¿" en vez de "País")', 'Mapear por posición y registrar'),
    'F05': ('Archivo', 'ERROR', 'Datos fuera de Tabla1', 'Hay celdas con valores debajo o a la derecha de la tabla: no se consolidan', 'No se cargan; devolver para que las pasen dentro de la tabla'),
    'F06': ('Archivo', 'INFO', 'Fila de totales dentro de Tabla1', 'Activaron "Fila de totales" (SUBTOTAL): duplicaría el monto si se lee como línea', 'Excluir la fila de totales'),
    'F07': ('Archivo', 'ALERTA', 'Tipo de cambio guardado como texto', 'Filas 3–5 (TC) son texto con espacio duro: cualquier fórmula que las use da #VALUE!', 'Corregir en la plantilla base; el TC se toma de tabla maestra'),
    'F08': ('Archivo', 'ALERTA', 'Hojas distintas al estándar', 'Agregaron/borraron hojas o la hoja Tablas quedó visible', 'Registrar; validar listas'),
    'F09': ('Archivo', 'INFO', 'Nombre de archivo distinto al enviado', 'Cambió el nombre (tildes, sufijos, versión)', 'Identificar la plantilla por metadatos/tag, no por nombre'),
    'F10': ('Archivo', 'BLOQUEANTE', 'Archivo duplicado', 'Mismo contenido (hash) que otro archivo cargado', 'Cargar uno solo'),
    'F11': ('Archivo', 'ERROR', 'País de las líneas distinto al de la carpeta', 'La plantilla de un país trae líneas de otro', 'Cuarentena de esas líneas'),
    'F12': ('Archivo', 'INFO', 'Nombre no UTF-8 dentro del zip', 'El zip guardó la ruta en cp437 (p. ej. "Tesorer+�a"); se corrigió al extraer', 'Extraer forzando UTF-8'),
    'L01': ('Línea', 'ERROR', 'País vacío o fuera de lista', 'Columna A no está en la lista País', 'Cuarentena'),
    'L02': ('Línea', 'ERROR', 'Vehículo inválido para el país', 'Columna B no está en la lista del país', 'Cuarentena'),
    'L03': ('Línea', 'ERROR', 'CeCo vacío, sin número o "Varios"', 'Columna C debe ser "NNN - Nombre"', 'Cuarentena'),
    'L04': ('Línea', 'ALERTA', 'CeCo fuera de la lista del archivo', 'El CeCo no está en Ceco_Nombre (hoja Tablas)', 'Validar contra maestro de CeCos'),
    'L05': ('Línea', 'ERROR', 'Nivel 1 vacío o fuera de lista', 'Columna F no está en Nivel_1', 'Cuarentena'),
    'L06': ('Línea', 'ERROR', 'Nivel 2 no corresponde al Nivel 1', 'Columna G no está en la lista del Nivel 1', 'Cuarentena'),
    'L07': ('Línea', 'ALERTA', 'Proveedor de relleno', 'Proveedor tipo "NO ESTA", "POR DEFINIR", "XXX", "?"', 'Revisar con el área'),
    'L08': ('Línea', 'INFO', 'Proveedor nuevo (fuera de la lista)', 'Proveedor no está en la lista Proveedor del archivo', 'Homologar proveedor'),
    'L09': ('Línea', 'ERROR', 'Moneda vacía o fuera de lista', 'Columna M no es PEN/COP/CLP/USD/MXN', 'Cuarentena'),
    'L10': ('Línea', 'ALERTA', 'Moneda no habitual para el país', 'Moneda distinta a la local o USD', 'Revisar conversión'),
    'L11': ('Línea', 'ALERTA', 'Glosa vacía', 'Línea sin Glosa / Texto', 'Revisar con el área'),
    'L12': ('Línea', 'INFO', 'Línea vacía', 'Fila de la tabla sin textos ni montos', 'Ignorar'),
    'L13': ('Línea', 'ALERTA', 'Línea duplicada', 'Mismos textos A..M que otra línea del archivo', 'Revisar doble conteo'),
    'L14': ('Línea', 'ALERTA', 'CeCo de otra agrupación', 'El CeCo pertenece a una agrupación distinta a la de la plantilla (p. ej. 502 MDK en Staff - Finanzas USA)', 'Se clasifica por su CeCo; devolver al área para corregir'),
    'C01': ('Cambio vs enviado', 'ALERTA', 'Línea nueva con montos en Real 2026', 'El área escribió montos en Ene–Ago 26 de una línea que no existía. El ejercicio se enfoca en Ppto 2027: el Real se toma de la TD', 'Ignorar Real del archivo; si era presupuesto, moverlo a 2027'),
    'C02': ('Cambio vs enviado', 'ALERTA', 'Real 2026 modificado', 'Los montos Ene–Ago 26 difieren de los enviados (editados o redondeados)', 'Ignorar Real del archivo; Real = TD'),
    'C03': ('Cambio vs enviado', 'ALERTA', 'Textos de una línea del Real modificados', 'Cambiaron vehículo, proveedor, glosa, etc. de una línea con Real', 'Registrar; vehículo distinto al contable se revisa'),
    'C04': ('Cambio vs enviado', 'ALERTA', 'Línea del Real eliminada', 'Una línea enviada con Real ya no está', 'Revisar si fue intencional'),
    'M01': ('Montos', 'ERROR', 'Ppto 2027 en positivo', 'En las columnas Ppto 2027 todo monto debe ser negativo', 'Cuarentena (o invertir signo con aprobación)'),
    'M02': ('Montos', 'INFO', 'Celda de monto con espacio / espacio duro', 'Texto vacío (" " o "\\xa0") en lugar de celda vacía', 'Tratar como vacío'),
    'M03': ('Montos', 'ALERTA', 'Número guardado como texto', '"1,500", "S/ 200", "(300)", "1.500,00"', 'Convertir y registrar'),
    'M04': ('Montos', 'INFO', 'Fórmula aritmética simple', '=-2000000/12', 'Evaluar'),
    'M05': ('Montos', 'ERROR', 'Fórmula con error o sin valor', '#REF!, #VALUE!, #DIV/0! o fórmula que no se puede calcular', 'Cuarentena'),
    'M06': ('Montos', 'ERROR', 'Fecha en celda de monto', 'Excel convirtió "1-5" en fecha', 'Cuarentena'),
    'M07': ('Montos', 'ERROR', 'Fórmula con vínculo a otro libro', '=[Libro2.xlsx]Hoja1!A1', 'Cuarentena'),
    'M08': ('Montos', 'ALERTA', 'Fórmula con referencias a celdas', '=N4*1364: depende de otras celdas', 'Usar valor calculado y registrar'),
    'M09': ('Montos', 'ERROR', 'Texto no numérico en monto', '"pendiente", "n/a", "ver correo"', 'Cuarentena'),
    'M10': ('Montos', 'INFO', 'Real 2026 positivo', 'Extornos / reversiones del contable', 'Permitido en Real; no se presupuesta'),
    'M11': ('Montos', 'INFO', 'Cero escrito', 'Se escribió 0 en vez de dejar vacío', 'Tratar como vacío'),
    'M12': ('Montos', 'INFO', 'Ppto 2027 con más de 2 decimales', 'Montos con decimales largos', 'Redondear a 2'),
    'M13': ('Montos', 'ALERTA', 'Ppto anual cargado en un solo mes', 'Línea recurrente en 2026 con todo 2027 en un mes', 'Revisar mensualización'),
    'M14': ('Montos', 'ALERTA', 'Variación > ±50 % sin comentario', 'P27 vs Real anualizado fuera de rango y Comentario de Área vacío', 'Pedir sustento'),
    'M15': ('Montos', 'ALERTA', 'Posible error de escala o moneda', 'P27 ≈ ×1000 / ÷1000 del Real anualizado, o ≈ × tipo de cambio', 'Revisar unidades y moneda'),
    'M16': ('Montos', 'ALERTA', 'Columna calculada pisada', 'F26 / P27 / Var. escritos como valor en vez de fórmula', 'Recalcular en Databricks'),
    'M17': ('Montos', 'INFO', 'Forecast Set–Dic 26 ingresado', 'El área llenó Set–Dic 26', 'Cargar como F26 del área'),
    'F13': ('Archivo', 'ALERTA', 'Cabecera o tipo de cambio modificados', 'El área cambió celdas fuera de Tabla1 en filas 1–8 (leyenda, TC)', 'Ignorar: el TC se toma de tabla maestra'),
    'T01': ('Texto', 'ALERTA', 'Caracteres dañados (no UTF-8)', 'Ã©, Ã±, �, ╠, "+�": tildes mal codificadas', 'Reparar codificación'),
    'T02': ('Texto', 'INFO', 'Espacios extra, espacio duro o saltos de línea', 'Textos con espacios al inicio/fin, dobles o \\xa0', 'Limpiar (trim)'),
    'T03': ('Texto', 'ALERTA', 'Caracteres invisibles o de control', 'Zero-width, BOM, \\x00…', 'Eliminar'),
    'T04': ('Texto', 'INFO', 'Texto de más de 255 caracteres', 'Glosa o comentario muy largo', 'Truncar en reportes'),
    'T05': ('Texto', 'INFO', 'Separadores que rompen CSV', 'Textos con ; | o tabulación', 'Escapar al exportar'),
    'T06': ('Texto', 'INFO', 'Tildes o mayúsculas distintas al catálogo', '"Peru" en vez de "Perú"', 'Normalizar'),
}
SEV_ORDEN = ['BLOQUEANTE', 'ERROR', 'ALERTA', 'INFO']

FLAGS_NUEVOS = {
    'F14': ('Archivo', 'ALERTA', 'Plantilla no reconocida', 'La ruta/nombre no coincide con ninguna plantilla del maestro de plantillas', 'Asignarla a mano en alias_ppto27.xlsx (alias_plantilla)'),
    'F15': ('Archivo', 'INFO', 'Versión reemplazada', 'Llegó una versión más nueva de la misma plantilla', 'Se usa la última; la anterior queda en el historial'),
    'L15': ('Línea', 'INFO', 'Cuenta contable homologada', 'La cuenta estaba escrita distinto (tildes, mayúsculas, espacios) o figura en alias aprobados', 'Se reemplaza por el nombre oficial'),
    'L16': ('Línea', 'ALERTA', 'Cuenta contable sugerida por parecido', 'No coincide con el plan de cuentas; hay una cuenta muy parecida', 'Confirmar y agregar a alias_ppto27.xlsx (alias_cuenta)'),
    'L17': ('Línea', 'ALERTA', 'Cuenta contable no reconocida', 'No está en el plan de cuentas ni en alias', 'Revisar con el área; se reporta por su Nivel 1 / Nivel 2'),
    'L18': ('Línea', 'ERROR', 'Proveedor "Varios"', 'Prohibido usar Varios como proveedor', 'Cuarentena; pedir el proveedor real'),
    'L19': ('Línea', 'ALERTA', 'Proveedor sugerido por parecido', 'No coincide con el maestro; hay un proveedor muy parecido', 'Confirmar y agregar a alias_ppto27.xlsx (alias_proveedor)'),
    'F17': ('Archivo', 'ALERTA', 'Dos versiones en la misma subida', 'En una misma carga llegaron dos archivos distintos de la misma plantilla', 'Se usa el de fecha de modificación más reciente; confirmar con el área'),
    'F16': ('Archivo', 'BLOQUEANTE', 'Archivo ilegible', 'No se pudo abrir (dañado, con clave o no es un .xlsx real)', 'Pedir el archivo de nuevo'),
}
CATALOGO.update(FLAGS_NUEVOS)
SEVERIDAD = {k: v[1] for k, v in CATALOGO.items()}


# ───────────────────────────── Formato Perú (Nivel 1 / Nivel 2 del BI contable) ─────────────────────────────
# (n1_formato, grupo, n2_formato, nivel_1 de la plantilla, nivel_2 de la plantilla)
ESTRUCTURA = [
    ('Gastos del Personal', '', 'Remuneración Fija', 'Gastos del Personal', 'Remuneración Fija'),
    ('Gastos del Personal', '', 'Remuneración Variable', 'Gastos del Personal', 'Remuneración Variable'),
    ('Gastos del Personal', 'Otros gastos de personal', 'OGP - Bienestar/Eventos', 'Gastos del Personal', 'OGP - Bienestar/eventos'),
    ('Gastos del Personal', 'Otros gastos de personal', 'OGP - Cultura y Com. Interna', 'Gastos del Personal', 'OGP - Cultura y Com. Interna'),
    ('Gastos del Personal', 'Otros gastos de personal', 'OGP - Consultoría', 'Gastos del Personal', 'OGP - Consultoría'),
    ('Gastos del Personal', 'Otros gastos de personal', 'OGP - Seguros y Salud', 'Gastos del Personal', 'OGP - Seguros y Salud'),
    ('Gastos del Personal', 'Otros gastos de personal', 'OGP - Servicios Compensaciones', 'Gastos del Personal', 'OGP - Servicios Compensaciones'),
    ('Gastos del Personal', 'Otros gastos de personal', 'OGP - Otros Gastos Personal', 'Gastos del Personal', 'OGP - Otros Gastos Personal'),
    ('Gastos del Personal', 'Otros gastos de personal', 'OGP - Selección & On boarding', 'Gastos del Personal', 'OGP - Selección & On Boarding'),
    ('Gastos del Personal', 'Otros gastos de personal', 'OGP - Talento', 'Gastos del Personal', 'OGP - Talento'),
    ('Gastos del Personal', '', 'Capacitaciones', 'Gastos del Personal', 'Capacitaciones'),
    ('Gastos del Personal', '', 'Incentivo Corto Plazo', 'Gastos del Personal', 'Incentivo Corto Plazo'),
    ('Gastos del Personal', '', 'Incentivo Largo Plazo', 'Gastos del Personal', 'Incentivo Largo Plazo'),
    ('Gastos Administrativos', '', 'Misiones', 'Gastos Administrativos', 'Misiones'),
    ('Gastos Administrativos', 'C & CS', 'Consultorías y honorarios', 'Gastos Administrativos', 'Consultorías y Honorarios'),
    ('Gastos Administrativos', 'C & CS', 'CS Administrativo', 'Gastos Administrativos', 'CS Administrativo'),
    ('Gastos Administrativos', '', 'Marketing', 'Gastos Administrativos', 'Marketing'),
    ('Gastos Administrativos', '', 'Gastos de Representación', 'Gastos Administrativos', 'Gastos de Representación'),
    ('Gastos Administrativos', '', 'Suscripciones y servicios de información', 'Gastos Administrativos', 'Suscripciones y Servicios de Información'),
    ('Gastos Administrativos', '', 'Pagos transaccionales, bolsas y otros', 'Gastos Administrativos', 'Pagos Transaccionales, Bolsas y Otros'),
    ('Gastos Administrativos', '', 'Transporte y Mensajería', 'Gastos Administrativos', 'Transporte y Mensajería'),
    ('Gastos Administrativos', '', 'Oficinas y Suministros', 'Gastos Administrativos', 'Oficinas y Suministros'),
    ('Gastos Administrativos', 'Otros Gastos', 'Provisión de Incobrables', 'Gastos Administrativos', 'Provisión de Incobrables'),
    ('Gastos Administrativos', 'Otros Gastos', 'Donaciones', 'Gastos Administrativos', 'Donaciones'),
    ('Gastos de TI', '', 'Licencias', 'Tecnología y Comunicaciones', 'Licencias'),
    ('Gastos de TI', '', 'Aplicaciones', 'Tecnología y Comunicaciones', 'Aplicaciones'),
    ('Gastos de TI', '', 'Infraestructura', 'Tecnología y Comunicaciones', 'Infraestructura'),
    ('Gastos de TI', '', 'Comunicaciones', 'Tecnología y Comunicaciones', 'Comunicaciones'),
    ('Gastos de TI', '', 'Cloud', 'Tecnología y Comunicaciones', 'Cloud'),
    ('Gastos de TI', '', 'Consultorías', 'Tecnología y Comunicaciones', 'Consultorías'),
    ('Gastos de TI', '', 'Equipos de Usuario e Impresoras', 'Tecnología y Comunicaciones', 'Equipos de Usuario e Impresoras'),
    ('Gastos de TI', '', 'Servicio de HelpDesk', 'Tecnología y Comunicaciones', 'Servicio de HelpDesk'),
    ('Otros Gastos', '', 'Depreciación y Amortización', 'Depreciación y Amortización', 'Depreciación y Amortización'),
    ('Otros Gastos', '', 'Impuestos y Contribuciones', 'Impuestos y Contribuciones', 'Impuestos y Contribuciones'),
    ('Otros Gastos', '', 'Otros gastos', 'Otros Gastos', 'Otros Gastos'),
]
N1_ORDEN = ['Gastos del Personal', 'Gastos Administrativos', 'Gastos de TI', 'Otros Gastos']


def formato_peru():
    """dim_linea_pyg: orden del reporte y equivalencia con Nivel 1 / Nivel 2 de la plantilla (id 0 = Sin mapeo)."""
    filas = []
    for i, (n1, g, n2, p1, p2) in enumerate(ESTRUCTURA, 1):
        filas.append(dict(id_linea_pyg=i, n1_formato=n1, grupo_n2=g, n2_formato=n2, nivel_1_plantilla=p1, nivel_2_plantilla=p2,
                          orden_n1=N1_ORDEN.index(n1) + 1, orden_n2=i))
    filas.append(dict(id_linea_pyg=0, n1_formato='Sin mapeo', grupo_n2='', n2_formato='Sin mapeo', nivel_1_plantilla='',
                      nivel_2_plantilla='', orden_n1=99, orden_n2=999))
    return filas


MAPA_PYG = {(clave_texto(p1), clave_texto(p2)): i for i, (_, _, _, p1, p2) in enumerate(ESTRUCTURA, 1)}
NIVEL2_DE = {}
for _, _, _, p1, p2 in ESTRUCTURA:
    NIVEL2_DE.setdefault(clave_texto(p1), set()).add(clave_texto(p2))

# agrupación esperada de los CeCos según la carpeta de la plantilla (UdN / Staff); el resto de rubros no se valida (L14)
AGRUP_AREA = {'Riesgos': 'Staff - Riesgo', 'Operaciones COO (Servicio al Cliente)': 'Staff - Operaciones (COO)',
              'GEN IA': 'Staff - GenAI', 'COE DE_CX': 'Staff - COE DE/CX', 'Disrupción en Innovación': 'Staff - Disrupción',
              'Oficina Representación': 'Staff - Oficina de Representación'}


def agrupacion_esperada(tipo, area):
    if tipo == 'UdN':
        return area
    if tipo == 'Staff':
        return AGRUP_AREA.get(area, f'Staff - {area}')
    return None


def ceco_num(ceco_nombre):
    m = re.match(r'^\s*(\d+)', ceco_nombre or '')
    if not m:
        return None
    c = int(m.group(1))
    return c - 211000 if c > 211000 else c                                    # Panamá 211xxx = xxx


# ───────────────────────────── bronze de una carga (lo usa el notebook 10 y la prueba local) ─────────────────────────────
def bronze_carga(raiz, carga_id, ya=None, ahora=None):
    """Lee todas las plantillas bajo `raiz`. `ya` = {sha256: 'carga / ruta'} de archivos ya cargados (no se releen).
    Devuelve (archivos, lineas) como listas de dict con las columnas de ppto27_brz_archivos / ppto27_brz_lineas."""
    ya = dict(ya or {})
    ahora = ahora or datetime.now()
    rutas = sorted((os.path.join(d, f), unicodedata.normalize('NFC', os.path.relpath(os.path.join(d, f), raiz)))
                   for d, _, fs in os.walk(raiz) for f in fs if es_plantilla(f))
    A, LIN = [], []
    for p, rel in rutas:
        st = os.stat(p)
        h = sha256(p)
        a = dict(carga_id=carga_id, ruta_relativa=rel, archivo=os.path.basename(rel), sha256=h, tamano_bytes=st.st_size,
                 modificado=datetime.fromtimestamp(st.st_mtime), **identificar(rel), repetido_de=None, fecha_proceso=ahora)
        if h in ya:
            a.update(estado='REPETIDO', repetido_de=ya[h], error=None)
        else:
            try:
                info, lineas = leer_plantilla(p)
            except Exception as e:
                info, lineas = dict(estado='RECHAZADO', error=f'F16 {type(e).__name__}: {e}'[:500]), []
            a.update(info)
            ya[h] = f'{carga_id} / {rel}'
            LIN += [dict(l, carga_id=carga_id, sha256=h, id_plantilla=a['id_plantilla'], ruta_relativa=rel, fecha_proceso=ahora)
                    for l in lineas]
        A.append(a)
    return A, LIN


# ───────────────────────────── maestros (los usan los notebooks 20/30 y la prueba local) ─────────────────────────────
def cargar_maestros(carpeta=MAESTROS):
    """(M, AL, drivers): maestros_ppto27.xlsx, alias_ppto27.xlsx y la hoja Drivers de drivers_ppto27.xlsx."""
    import pandas as pd
    M = pd.read_excel(f'{carpeta}/maestros_ppto27.xlsx', sheet_name=None)
    AL = pd.read_excel(f'{carpeta}/alias_ppto27.xlsx', sheet_name=None)
    D0 = pd.read_excel(f'{carpeta}/drivers_ppto27.xlsx', 'Drivers', header=4).dropna(axis=1, how='all')
    return M, AL, D0
