"""Escritura "de cirujano" de Ago-26 en una plantilla .xlsx editando sólo el XML necesario:
- hoja Ppto27: celda U de filas existentes + filas nuevas (amarillas) al final de Tabla1
- styles.xml: relleno amarillo y variantes de estilos para las filas nuevas
- tabla de la hoja: ref / autoFilter; workbook.xml: fullCalcOnLoad; se quita calcChain
Todas las demás partes del zip se copian byte a byte."""
import zipfile, re, copy, posixpath
from lxml import etree
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
RNS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PNS = 'http://schemas.openxmlformats.org/package/2006/relationships'
q = lambda t: f'{{{NS}}}{t}'
COL = 'U'
COLS_TXT = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M']

def col_idx(c):
    n = 0
    for ch in c: n = n * 26 + ord(ch) - 64
    return n

def split_ref(r):
    m = re.match(r'([A-Z]+)(\d+)$', r); return m.group(1), int(m.group(2))

def _rels(z, part):
    d, b = posixpath.split(part)
    p = posixpath.join(d, '_rels', b + '.rels')
    return p, etree.fromstring(z.read(p))

def _target(base, t):
    return posixpath.normpath(posixpath.join(posixpath.dirname(base), t)) if not t.startswith('/') else t.lstrip('/')

def partes(z):
    wb = etree.fromstring(z.read('xl/workbook.xml'))
    rid = [s for s in wb.find(q('sheets')) if s.get('name') == 'Ppto27'][0].get(f'{{{RNS}}}id')
    _, wr = _rels(z, 'xl/workbook.xml')
    sheet = _target('xl/workbook.xml', [r for r in wr if r.get('Id') == rid][0].get('Target'))
    sr_path, sr = _rels(z, sheet)
    tables = [_target(sheet, r.get('Target')) for r in sr if r.get('Type', '').endswith('/table')]
    return sheet, tables

def escribir(src, dst, valores, nuevas, amarillo=False):
    """valores: {fila: monto} para filas existentes; nuevas: lista de dicts {'A':..,'M':.., 'U': monto} (texto por columna A–M)."""
    zin = zipfile.ZipFile(src)
    sheet, tables = partes(zin)
    S = etree.fromstring(zin.read(sheet))
    sd = S.find(q('sheetData'))
    rows = {int(r.get('r')): r for r in sd.findall(q('row'))}
    # tabla de la hoja que contiene la columna U
    tab_path, T = None, None
    for tp in tables:
        t = etree.fromstring(zin.read(tp))
        a, b = t.get('ref').split(':')
        if col_idx(split_ref(a)[0]) <= col_idx(COL) <= col_idx(split_ref(b)[0]): tab_path, T = tp, t; break
    a, b = T.get('ref').split(':'); c0, r0 = split_ref(a); c1, r1 = split_ref(b)
    hdr = r0
    # --- filas existentes: celda U
    for fila, v in valores.items():
        if abs(v) < 1e-12: continue
        row = rows[fila]
        cells = {split_ref(c.get('r'))[0]: c for c in row.findall(q('c'))}
        c = cells.get(COL)
        if c is None:
            ref_style = cells.get('T')
            c = etree.Element(q('c')); c.set('r', f'{COL}{fila}')
            if ref_style is not None and ref_style.get('s'): c.set('s', ref_style.get('s'))
            despues = [x for x in row.findall(q('c')) if col_idx(split_ref(x.get('r'))[0]) > col_idx(COL)]
            (despues[0].addprevious(c) if despues else row.append(c))
        for ch in list(c): c.remove(ch)
        if 't' in c.attrib: del c.attrib['t']
        ve = etree.SubElement(c, q('v')); ve.text = repr(float(v))
    # --- filas nuevas
    nuevas_filas = []
    if nuevas:
        bajo = [r for r in rows if r > r1]
        con_dato = [r for r in bajo if any(c.find(q('v')) is not None or c.find(q('is')) is not None or c.find(q('f')) is not None
                                              for c in rows[r].findall(q('c')))]
        if con_dato:
            raise RuntimeError(f'{src}: hay filas con contenido bajo la tabla ({con_dato[:5]}); no se agregan filas nuevas sin revisar')
        for r in bajo:                                   # filas vacías (sólo formato) bajo la tabla: se reemplazan
            if r <= r1 + len(nuevas): sd.remove(rows.pop(r))
        restantes = [rows[r] for r in sorted(rows) if r > r1 + len(nuevas)]
        base = rows[r1]
        # fórmulas por columna (texto) desde cualquier fila de datos que tenga el texto
        form = {}
        for rr in range(r0 + 1, r1 + 1):
            if rr not in rows: continue
            for c in rows[rr].findall(q('c')):
                f = c.find(q('f'))
                col = split_ref(c.get('r'))[0]
                if f is not None and f.text and col not in form: form[col] = (f.text, rr)
        # estilos amarillos
        st_zip = 'xl/styles.xml'
        ST = etree.fromstring(zin.read(st_zip))
        fills = ST.find(q('fills'))
        fe = etree.SubElement(fills, q('fill')); pf = etree.SubElement(fe, q('patternFill')); pf.set('patternType', 'solid')
        fg = etree.SubElement(pf, q('fgColor')); fg.set('rgb', 'FFFFFF00'); bg = etree.SubElement(pf, q('bgColor')); bg.set('indexed', '64')
        fid = len(fills) - 1; fills.set('count', str(len(fills)))
        xfs = ST.find(q('cellXfs')); mapa = {}
        def amarillo_de(s):
            if s not in mapa:
                x = copy.deepcopy(xfs[int(s)]); x.set('fillId', str(fid)); x.set('applyFill', '1')
                xfs.append(x); mapa[s] = str(len(xfs) - 1); xfs.set('count', str(len(xfs)))
            return mapa[s]
        for i, nv in enumerate(nuevas, 1):
            rn = r1 + i
            row = copy.deepcopy(base); row.set('r', str(rn))
            for c in row.findall(q('c')):
                col = split_ref(c.get('r'))[0]; c.set('r', f'{col}{rn}')
                for ch in list(c): c.remove(ch)
                for at in ('t', 'cm', 'vm'):
                    if at in c.attrib: del c.attrib[at]
                if amarillo: c.set('s', amarillo_de(c.get('s', '0')))
                if col in form:
                    txt, src_r = form[col]
                    txt = re.sub(r'(?<![A-Za-z\[])(\$?[A-Z]{1,3}\$?)' + str(src_r) + r'(?!\d)', lambda m: m.group(1) + str(rn), txt)
                    f = etree.SubElement(c, q('f')); f.text = txt
                elif col in COLS_TXT and nv.get(col) not in (None, ''):
                    c.set('t', 'inlineStr'); is_ = etree.SubElement(c, q('is')); t = etree.SubElement(is_, q('t')); t.text = str(nv[col])
                    if t.text != t.text.strip(): t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                elif col == COL:
                    ve = etree.SubElement(c, q('v')); ve.text = repr(float(nv['U']))
            # garantizar celdas A–M y U aunque la fila base no las tuviera
            present = {split_ref(c.get('r'))[0] for c in row.findall(q('c'))}
            for col in COLS_TXT + [COL]:
                val = nv.get(col) if col != COL else nv['U']
                if col in present or val in (None, ''): continue
                c = etree.Element(q('c')); c.set('r', f'{col}{rn}')
                if col == COL: ve = etree.SubElement(c, q('v')); ve.text = repr(float(val))
                else:
                    c.set('t', 'inlineStr'); is_ = etree.SubElement(c, q('is')); t = etree.SubElement(is_, q('t')); t.text = str(val)
                despues = [x for x in row.findall(q('c')) if col_idx(split_ref(x.get('r'))[0]) > col_idx(col)]
                (despues[0].addprevious(c) if despues else row.append(c))
            base.addnext(row) if i == 1 else nuevas_filas[-1].addnext(row)
            nuevas_filas.append(row)
        r1n = r1 + len(nuevas)
        T.set('ref', f'{c0}{r0}:{c1}{r1n}')
        af = T.find(q('autoFilter'))
        if af is not None: af.set('ref', f'{c0}{r0}:{c1}{r1n}')
        dim = S.find(q('dimension'))
        if dim is not None:
            da, db = dim.get('ref').split(':') if ':' in dim.get('ref') else (dim.get('ref'), dim.get('ref'))
            cc, rr = split_ref(db); dim.set('ref', f'{da}:{cc}{max(rr, r1n)}')
    # --- fórmulas: quitar valores cacheados de columnas con fórmula en filas tocadas no es necesario: fullCalcOnLoad
    WB = etree.fromstring(zin.read('xl/workbook.xml'))
    cp = WB.find(q('calcPr'))
    if cp is None: cp = etree.SubElement(WB, q('calcPr'))
    cp.set('fullCalcOnLoad', '1')
    nuevos = {sheet: S, 'xl/workbook.xml': WB}
    if nuevas: nuevos[tab_path] = T; nuevos['xl/styles.xml'] = ST
    quitar = {'xl/calcChain.xml'}
    zout = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
    for it in zin.infolist():
        if it.filename in quitar: continue
        data = zin.read(it.filename)
        if it.filename in nuevos:
            data = etree.tostring(nuevos[it.filename], xml_declaration=True, encoding='UTF-8', standalone=True)
        elif it.filename == 'xl/_rels/workbook.xml.rels':
            R = etree.fromstring(data)
            for r in list(R):
                if r.get('Target', '').endswith('calcChain.xml'): R.remove(r)
            data = etree.tostring(R, xml_declaration=True, encoding='UTF-8', standalone=True)
        elif it.filename == '[Content_Types].xml':
            C = etree.fromstring(data)
            for o in list(C):
                if o.get('PartName', '') == '/xl/calcChain.xml': C.remove(o)
            data = etree.tostring(C, xml_declaration=True, encoding='UTF-8', standalone=True)
        zi = zipfile.ZipInfo(it.filename, date_time=it.date_time); zi.compress_type = zipfile.ZIP_DEFLATED; zi.external_attr = it.external_attr
        zout.writestr(zi, data)
    zout.close()
    return dict(hoja=sheet, tabla=tab_path, filas_ago=len([v for v in valores.values() if abs(v) >= 1e-12]), filas_nuevas=len(nuevas))
