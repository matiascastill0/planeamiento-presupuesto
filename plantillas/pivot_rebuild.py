import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""Regenera la tabla dinámica 'TD - Ppto26' (caché, registros y diseño) con la BD Ppto 2026 de cada unidad.

Se parte del XML original de la plantilla AM Chile, de modo que la TD conserva filtros, campos,
estilo y formato; sólo cambian los ítems, los registros y el rango de origen.
"""
import zipfile, shutil, os, math, datetime as dt, copy
from xml.sax.saxutils import escape
from lxml import etree
import pandas as pd, numpy as np

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
N = '{%s}' % NS
HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, 'tpl', 'xl')
CACHE_DEF = open(os.path.join(TPL, 'pivotCache', 'pivotCacheDefinition1.xml'), 'rb').read()
PIVOT_TBL = open(os.path.join(TPL, 'pivotTables', 'pivotTable1.xml'), 'rb').read()

SHARED = {0, 3, 11, 13, 14, 15, 21, 22, 23}          # campos usados en filtros, filas y columnas
NUMERIC = {10, 26, 27, 28, 29}
DATE = 21
ROWS = [13, 14, 15]; COLS = [11, 21]; PAGES = [23, 0, 3, 22]

def _isblank(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and v == '')

def _fmt_num(v):
    r = repr(float(v))
    return r[:-2] if r.endswith('.0') else r

def _dt(v):
    return v.strftime('%Y-%m-%dT%H:%M:%S')

def valores(P, cols):
    """Lista de filas (tuplas) tal como quedan en la hoja BD."""
    return [tuple(r) for r in P[cols].itertuples(index=False)]

def build_xml(rows, cols, ref):
    ncol = len(cols)
    colvals = list(zip(*rows)) if rows else [[None] for _ in range(ncol)]
    if not rows:
        rows = [tuple([None] * ncol)]
    # ------------------------------------------------ ítems compartidos
    items = {}
    for i in SHARED:
        vals = colvals[i]
        uniq = []
        seen = set()
        for v in vals:
            k = None if _isblank(v) else v
            if k not in seen:
                seen.add(k); uniq.append(k)
        nonblank = [u for u in uniq if u is not None]
        if i == DATE:
            nonblank = sorted(nonblank)
        else:
            nonblank = sorted(nonblank, key=lambda s: str(s))
        items[i] = nonblank + ([None] if None in seen else [])
    idx = {i: {v: k for k, v in enumerate(items[i])} for i in SHARED}

    # ------------------------------------------------ definición de caché
    root = etree.fromstring(CACHE_DEF)
    root.set('recordCount', str(len(rows)))
    root.set('refreshOnLoad', '1')
    root.find(N + 'cacheSource').find(N + 'worksheetSource').set('ref', ref)
    cfs = root.find(N + 'cacheFields').findall(N + 'cacheField')
    for i, cf in enumerate(cfs):
        old = cf.find(N + 'sharedItems')
        si = etree.Element(N + 'sharedItems')
        vals = colvals[i]
        blanks = any(_isblank(v) for v in vals)
        if i in SHARED:
            its = items[i]
            if i == DATE:
                ds = [d for d in its if d is not None]
                si.set('containsSemiMixedTypes', '0'); si.set('containsNonDate', '0'); si.set('containsDate', '1'); si.set('containsString', '0')
                if blanks: si.set('containsBlank', '1')
                if ds:
                    si.set('minDate', _dt(min(ds))); si.set('maxDate', _dt(max(ds) + dt.timedelta(days=1)))
            else:
                if blanks: si.set('containsBlank', '1')
                if not [x for x in its if x is not None]:
                    si.set('containsNonDate', '0'); si.set('containsString', '0')
            si.set('count', str(len(its)))
            for v in its:
                if v is None: etree.SubElement(si, N + 'm')
                elif i == DATE: etree.SubElement(si, N + 'd').set('v', _dt(v))
                else: etree.SubElement(si, N + 's').set('v', str(v))
        elif i in NUMERIC:
            nums = [float(v) for v in vals if not _isblank(v)]
            if nums:
                si.set('containsSemiMixedTypes', '0'); si.set('containsString', '0'); si.set('containsNumber', '1')
                if all(float(x).is_integer() for x in nums): si.set('containsInteger', '1')
                si.set('minValue', _fmt_num(min(nums))); si.set('maxValue', _fmt_num(max(nums)))
                if blanks: si.set('containsBlank', '1')
            else:
                si.set('containsNonDate', '0'); si.set('containsString', '0'); si.set('containsBlank', '1')
        else:
            if all(_isblank(v) for v in vals):
                si.set('containsNonDate', '0'); si.set('containsString', '0'); si.set('containsBlank', '1')
            elif blanks:
                si.set('containsBlank', '1')
        cf.replace(old, si)
    cache_xml = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # ------------------------------------------------ registros
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n',
           f'<pivotCacheRecords xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" count="{len(rows)}">']
    for r in rows:
        out.append('<r>')
        for i, v in enumerate(r):
            if i in SHARED:
                out.append(f'<x v="{idx[i][None if _isblank(v) else v]}"/>')
            elif _isblank(v):
                out.append('<m/>')
            elif i in NUMERIC:
                out.append(f'<n v="{_fmt_num(v)}"/>')
            else:
                out.append(f'<s v="{escape(str(v), {chr(34): "&quot;"})}"/>')
        out.append('</r>')
    out.append('</pivotCacheRecords>')
    records_xml = ''.join(out).encode('utf-8')
    return cache_xml, records_xml, items, idx

def pivot_xml(items, rows, idx, location_ref):
    root = etree.fromstring(PIVOT_TBL)
    root.find(N + 'location').set('ref', location_ref)
    pfs = root.find(N + 'pivotFields').findall(N + 'pivotField')
    orden = {}
    for i in SHARED:
        pf = pfs[i]
        old = pf.find(N + 'items')
        its = etree.Element(N + 'items')
        n = len(items[i])
        orden[i] = list(range(n))                     # ítems en el mismo orden que la caché (ya ordenados)
        sd = (i == 14)                                # Nivel_2 contraído como en la plantilla
        for k in orden[i]:
            e = etree.SubElement(its, N + 'item')
            if sd: e.set('sd', '0')
            e.set('x', str(k))
        d = etree.SubElement(its, N + 'item'); d.set('t', 'default')
        if sd: d.set('sd', '0')
        its.set('count', str(n + 1))
        if old is not None: pf.replace(old, its)
        else: pf.append(its)
    # filas: Nivel_1 > Nivel_2 (Nivel_3 contraído)
    ri = root.find(N + 'rowItems'); ri.clear()
    pares = sorted({(idx[13][None if _isblank(r[13]) else r[13]], idx[14][None if _isblank(r[14]) else r[14]]) for r in rows})
    n1s = sorted({a for a, _ in pares})
    cnt = 0
    for a in n1s:
        e = etree.SubElement(ri, N + 'i'); x = etree.SubElement(e, N + 'x')
        if a: x.set('v', str(a))
        cnt += 1
        for a2, b in pares:
            if a2 != a: continue
            e = etree.SubElement(ri, N + 'i'); e.set('r', '1'); x = etree.SubElement(e, N + 'x')
            if b: x.set('v', str(b))
            cnt += 1
    e = etree.SubElement(ri, N + 'i'); e.set('t', 'grand'); etree.SubElement(e, N + 'x'); cnt += 1
    ri.set('count', str(cnt))
    # columnas: Datos > Fecha
    ci = root.find(N + 'colItems'); ci.clear()
    nd = len(items[21]); c = 0
    datos = len(items[11])
    for a in range(datos):
        for j in range(nd):
            e = etree.SubElement(ci, N + 'i')
            if j == 0:
                x = etree.SubElement(e, N + 'x')
                if a: x.set('v', str(a))
                etree.SubElement(e, N + 'x')
            else:
                e.set('r', '1'); etree.SubElement(e, N + 'x').set('v', str(j))
            c += 1
        e = etree.SubElement(ci, N + 'i'); e.set('t', 'default'); x = etree.SubElement(e, N + 'x')
        if a: x.set('v', str(a))
        c += 1
    ci.set('count', str(c))
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

def reemplazar_partes(xlsx, partes):
    tmp = xlsx + '.tmp'
    with zipfile.ZipFile(xlsx) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            data = partes.get(it.filename, zin.read(it.filename))
            zout.writestr(it, data)
    shutil.move(tmp, xlsx)

# ------------------------------------------------------------------ logo de la plantilla
TEMPLATE_XLSX = RAIZ + 'plantillas-ejemplo/Ppto27 - AM Chile - OFICIAL 1.xlsx'
def partes_logo(xlsx):
    """openpyxl descarta el logo de Credicorp de la hoja Ppto27: se reinyecta desde la plantilla."""
    tz = zipfile.ZipFile(TEMPLATE_XLSX)
    z = zipfile.ZipFile(xlsx)
    partes = {n: tz.read(n) for n in ['xl/drawings/drawing1.xml', 'xl/drawings/_rels/drawing1.xml.rels', 'xl/media/image1.png', 'xl/media/hdphoto1.wdp']}
    sh = z.read('xl/worksheets/sheet1.xml').decode('utf-8')
    if '<drawing ' not in sh:
        sh = sh.replace('<tableParts', '<drawing xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:id="rIdLogo"/><tableParts', 1)
    partes['xl/worksheets/sheet1.xml'] = sh.encode('utf-8')
    rels = z.read('xl/worksheets/_rels/sheet1.xml.rels').decode('utf-8')
    if 'rIdLogo' not in rels:
        rels = rels.replace('</Relationships>', '<Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="/xl/drawings/drawing1.xml" Id="rIdLogo"/></Relationships>')
    partes['xl/worksheets/_rels/sheet1.xml.rels'] = rels.encode('utf-8')
    ct = z.read('[Content_Types].xml').decode('utf-8')
    add = ''
    if 'Extension="png"' not in ct: add += '<Default Extension="png" ContentType="image/png"/>'
    if 'Extension="wdp"' not in ct: add += '<Default Extension="wdp" ContentType="image/vnd.ms-photo"/>'
    if '/xl/drawings/drawing1.xml' not in ct: add += '<Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>'
    partes['[Content_Types].xml'] = ct.replace('</Types>', add + '</Types>').encode('utf-8')
    return partes

def reemplazar_partes(xlsx, partes):
    tmp = xlsx + '.tmp'
    with zipfile.ZipFile(xlsx) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        nombres = set()
        for it in zin.infolist():
            zout.writestr(it, partes.get(it.filename, zin.read(it.filename))); nombres.add(it.filename)
        for n, data in partes.items():
            if n not in nombres:
                zout.writestr(n, data)
    shutil.move(tmp, xlsx)

def pivot_xml_regional(items, rows, idx, location_ref):
    """TD regional: filas País > Nivel 3, filtros Compañía / Agrupación / Vista, sin total general (monedas distintas)."""
    root = etree.fromstring(PIVOT_TBL)
    loc = root.find(N + 'location'); loc.set('ref', location_ref); loc.set('rowPageCount', '3')
    root.set('rowGrandTotals', '0')
    pfs = root.find(N + 'pivotFields').findall(N + 'pivotField')
    ejes = {23: 'axisRow', 15: 'axisRow', 0: 'axisPage', 3: 'axisPage', 22: 'axisPage', 11: 'axisCol', 21: 'axisCol'}
    for i, pf in enumerate(pfs):
        if i in ejes: pf.set('axis', ejes[i])
        elif 'axis' in pf.attrib: del pf.attrib['axis']
        if i in SHARED:
            old = pf.find(N + 'items')
            its = etree.Element(N + 'items')
            for k in range(len(items[i])): etree.SubElement(its, N + 'item').set('x', str(k))
            etree.SubElement(its, N + 'item').set('t', 'default')
            its.set('count', str(len(items[i]) + 1))
            if old is not None: pf.replace(old, its)
            else: pf.append(its)
    rf = root.find(N + 'rowFields'); rf.clear(); rf.set('count', '2')
    for f in (23, 15): etree.SubElement(rf, N + 'field').set('x', str(f))
    pgs = root.find(N + 'pageFields'); pgs.clear(); pgs.set('count', '3')
    for f in (0, 3, 22):
        e = etree.SubElement(pgs, N + 'pageField'); e.set('fld', str(f)); e.set('hier', '-1')
    key = lambda v: None if _isblank(v) else v
    pares = sorted({(idx[23][key(r[23])], idx[15][key(r[15])]) for r in rows})
    ri = root.find(N + 'rowItems'); ri.clear(); cnt = 0
    for a in sorted({a for a, _ in pares}):
        e = etree.SubElement(ri, N + 'i'); x = etree.SubElement(e, N + 'x')
        if a: x.set('v', str(a))
        cnt += 1
        for a2, b in pares:
            if a2 != a: continue
            e = etree.SubElement(ri, N + 'i'); e.set('r', '1'); x = etree.SubElement(e, N + 'x')
            if b: x.set('v', str(b))
            cnt += 1
    ri.set('count', str(cnt))
    ci = root.find(N + 'colItems'); ci.clear(); c = 0
    nd = len(items[21])
    for j in range(nd):
        e = etree.SubElement(ci, N + 'i')
        if j == 0: etree.SubElement(e, N + 'x'); etree.SubElement(e, N + 'x')
        else: e.set('r', '1'); etree.SubElement(e, N + 'x').set('v', str(j))
        c += 1
    e = etree.SubElement(ci, N + 'i'); e.set('t', 'default'); etree.SubElement(e, N + 'x'); c += 1
    ci.set('count', str(c))
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
