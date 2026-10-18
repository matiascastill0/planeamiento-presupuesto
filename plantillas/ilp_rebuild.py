import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""Plantillas ILP (Incentivo Largo Plazo) limpias y homologadas, cuadradas con la TD (ene–jul) y los cierres (agosto).
- Filtros: Real 2026, Vista 1 y 3, sin IPC, sin INTERCOM/ELIM, con ajustes; Panamá Commision Paid/TRASLADOS -> BNK.
- Una línea por vehículo + CeCo + concepto; los tramos (T6, T7, ...) de una misma cuenta van juntos y se listan en la cuenta.
- Glosa por concepto, igual en todos los países. Sin líneas en cero. Filas sólo-agosto en amarillo.
Salida: '02. Gastos de Personal - corregido/' (copia), editando sólo la hoja Ppto27 / tabla / estilos por XML."""
import pandas as pd, numpy as np, re, os, glob, shutil, zipfile, copy
from lxml import etree
from td_filter import VISTAS, NO_CONTABLES, sin_ipc
from build_bd import fix
from agosto_lineas import Ctx, _ceco, _objetos, PAIS_TXT
from agosto_encaje import nk
from agosto_escribir import partes, q, split_ref, col_idx
BASE = RAIZ
SRC = BASE + '02. Insumos/05. Bases por área/Gastos de Personal (ILP)/'; DST = BASE + '99. Archivo/02. Gastos de Personal - corregido (eliminada)/'
MON = {'CHILE': 'CLP', 'COLOMBIA': 'COP', 'PERU': 'PEN', 'PANAMA': 'USD', 'USA': 'USD'}
MESES = list(range(1, 9))
COLM = {m: c for m, c in zip(MESES, ['N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U'])}

TRAMO = re.compile(r"\b(T ?\d{1,2}|PROGRAMA \d{1,2}|20[12]\d)\b|'(2[0-9])\b")
def familia(cta):
    s = fix(str(cta)).upper().strip()
    s = re.sub(r'BAPT(\d)', r'BAP T\1', s)
    tramos = [re.sub(r'^T ', 'T', a) if a else '20' + b for a, b in TRAMO.findall(s)]
    base = re.sub(r'\s+', ' ', TRAMO.sub(' ', s)).strip(' -')
    return base, tramos

GLOSAS = [  # (regex sobre la cuenta sin tramo, glosa)  — el orden importa
    (r'VALORIZACION.*CARGAS SOCIALES', 'Valorización cargas sociales ILP'),
    (r'VALORIZACION IR 5TA|VALORIZACION.*RENTA', 'Valorización renta de 5ta ILP'),
    (r'VALORIZACION.*(MATCHING|GENERACION DE VALOR)|VALORIZACION ILP MATCHING', 'Valorización ILP matching / generación de valor'),
    (r'VALORIZACION FFMM', 'Valorización ILP fondos mutuos'),
    (r'VALORIZACION.*BAP|VALOR RAZONABLE ACCIONES BAP', 'Valorización acciones BAP (ILP)'),
    (r'CARGAS SOCIALES.*(FFMM|FONDOS)', 'Cargas sociales ILP fondos mutuos'),
    (r'CARGAS SOCIALES.*(MATCHING|GENERACION DE VALOR)', 'Cargas sociales ILP matching / generación de valor'),
    (r'CARGAS SOCIALES', 'Cargas sociales ILP acciones BAP'),
    (r'RENTA 5TA.*(FFMM|FONDOS)', 'Renta de 5ta ILP fondos mutuos'),
    (r'RENTA 5TA.*(MATCHING|GENERACION DE VALOR)', 'Renta de 5ta ILP matching / generación de valor'),
    (r'RENTA 5TA', 'Renta de 5ta ILP acciones BAP'),
    (r'DEVENGO.*(FFMM|FONDOS MUTUOS)', 'Devengo ILP fondos mutuos'),
    (r'DEVENGO.*(MATCHING|GENERACION DE VALOR)', 'Devengo ILP matching / generación de valor'),
    (r'DEVENGO', 'Devengo ILP acciones BAP'),
    (r'BONOS? ILP BAP \(MATCHING \+ ADICIONAL\) COSTO', 'Bono ILP BAP matching + adicional (costo)'),
    (r'BONOS? ILP BAP \(MATCHING \+ ADICIONAL\) VALORACION', 'Bono ILP BAP matching + adicional (valoración)'),
    (r'BONOS? ILP DIVIDENDOS', 'Dividendos ILP'),
    (r'BONOS? ILP BAP', 'Bono ILP BAP'),
    (r'BONO MATCHING', 'Bono ILP matching (pago)'),
    (r'RECUPERACION ILP', 'Recuperación ILP'),
    (r'IMPUESTO ILP MATCHING', 'Impuesto ILP matching'),
    (r'INCENTIVOS L/P MATCHING|INCENTIVOS L P MATCHING', 'Devengo ILP matching / generación de valor'),
    (r'INCENTIVOS L/P 2|INCENTIVOS L P 2', 'Impuesto ILP acciones BAP'),
    (r'INCENTIVOS L/P|INCENTIVOS L P', 'Devengo ILP acciones BAP'),
    (r'CUOTAS DE FONDOS ILP', 'Rendimiento cuotas de fondos ILP'),
    (r'OTROS GASTOS NO OPERACIONALES', 'Provisión cuotas ILP (AGF)'),
    (r'LTI TAXES|PAYROLL TAXES|TAXES ILP', 'Impuestos ILP'),
    (r'LT INCENTIVE|PAYROLL EXP', 'Devengo ILP'),
    (r'^PAYROLL$', 'Nómina ILP'),
    (r'REAL GAINS|GAIN/LOSS|GAIN LOSS|FIN(ANCIAL)? REV', 'Resultado inversiones ILP'),
    (r'EJERCICIOS ANTERIORES', 'Ajustes de ejercicios anteriores'),
    (r'NO DEDUCIBLES', 'Gastos no deducibles'),
]
GLOSAS = [(re.compile(r), g) for r, g in GLOSAS]
def glosa(base):
    s = nk(base).replace('GENERACION', 'GENERACION')
    s2 = re.sub(r'\s+', ' ', re.sub(r'[^A-Z0-9/+() ]', ' ', fix(base).upper().replace('Ó', 'O').replace('Í', 'I'))).strip()
    for rx, g in GLOSAS:
        if rx.search(s2) or rx.search(s): return g
    return base.capitalize()

def datos():
    C = pd.read_pickle('cache_full.pkl')
    for c in ['Pais', 'Datos', 'Vista', 'Nivel_1', 'Nivel_2', 'Compañía']: C[c] = C[c].astype(str)
    m = ((C.Datos == 'Real 2026') & (C.Nivel_2 == 'Incentivo Largo Plazo') & C.Vista.isin(VISTAS) & ~C['Compañía'].str.contains('INTERCOM')
         & ~C['Compañía'].isin(NO_CONTABLES) & sin_ipc(C) & (C.Mes.astype(int) <= 7))
    T = _objetos(C[m]); T['Mes'] = T.Mes.astype(int)
    A = pd.read_pickle('ago_base.pkl'); A = _objetos(A[A.incluida & (A.Nivel_2 == 'Incentivo Largo Plazo')])
    X = pd.concat([T, A], ignore_index=True)
    X.loc[(X.Pais == 'PANAMA') & X['Compañía'].isin(['Commision Paid', 'TRASLADOS']), 'Compañía'] = 'BNK'
    X['Nom_Cta_Contable'] = X.Nom_Cta_Contable.map(lambda v: fix(v) if isinstance(v, str) else str(v))
    X['Nom_CeCo'] = X.Nom_CeCo.map(lambda v: fix(v) if isinstance(v, str) else v)
    return X

def lineas(X, pais, ctx):
    Y = X[X.Pais == pais].copy()
    Y = _ceco(Y, ctx, pais)
    fam = Y.Nom_Cta_Contable.map(familia)
    Y['fam'] = fam.map(lambda t: t[0]); Y['tramos'] = fam.map(lambda t: t[1])
    Y['famk'] = Y.fam.map(nk)
    disp = Y.groupby('famk').fam.agg(lambda s: s.value_counts().index[0])
    Y['Glosa'] = Y.famk.map(disp).map(glosa)
    k = ['Compañía', 'Ceco - Nombre', 'famk', 'Glosa']
    g = Y.groupby(k + ['Mes']).Monto.sum().unstack('Mes').reindex(columns=MESES).fillna(0.0)
    tr = Y.groupby(k).tramos.agg(lambda s: sorted({t for l in s for t in l}, key=lambda z: (z[0].isdigit(), z[0], int(re.sub(r'\D', '', z) or 0))))
    g = g[(g.abs() > 0.005).any(axis=1)].reset_index()
    g['tr'] = [tr.get(tuple(r)) for r in g[k].itertuples(index=False)]
    g['Nom Cta Contable'] = [disp[f] + (f" ({', '.join(t)})" if t else '') for f, t in zip(g.famk, g.tr)]
    g['amarilla'] = (g[list(range(1, 8))].abs() <= 0.005).all(axis=1) & (g[8].abs() > 0.005)
    g['c3'] = g['Ceco - Nombre'].str.extract(r'^(\d+)')[0].astype(int)
    g = g.sort_values(['amarilla', 'c3', 'Compañía', 'Glosa']).reset_index(drop=True)
    out = pd.DataFrame({'A': PAIS_TXT[pais], 'B': g['Compañía'], 'C': g['Ceco - Nombre'], 'E': g['Nom Cta Contable'],
                        'F': 'Gastos del Personal', 'G': 'Incentivo Largo Plazo', 'J': '(sin proveedor)', 'K': g.Glosa, 'M': MON[pais]})
    for m in MESES: out[COLM[m]] = g[m].round(6)
    out['amarilla'] = g.amarilla
    return out, Y

def reescribir(src, dst, L):
    zin = zipfile.ZipFile(src); sheet, tabs = partes(zin)
    S = etree.fromstring(zin.read(sheet)); sd = S.find(q('sheetData'))
    T = etree.fromstring(zin.read(tabs[0])); a, b = T.get('ref').split(':'); c0, r0 = split_ref(a); c1, _ = split_ref(b)
    ST = etree.fromstring(zin.read('xl/styles.xml')); xfs = ST.find(q('cellXfs')); fills = ST.find(q('fills'))
    fe = etree.SubElement(fills, q('fill')); pf = etree.SubElement(fe, q('patternFill')); pf.set('patternType', 'solid')
    etree.SubElement(pf, q('fgColor')).set('rgb', 'FFFFFF00'); etree.SubElement(pf, q('bgColor')).set('indexed', '64')
    fid = len(fills) - 1; fills.set('count', str(len(fills)))
    def nuevo_xf(base_s, fill=None, numfmt=None):
        x = copy.deepcopy(xfs[int(base_s)])
        if fill is not None: x.set('fillId', str(fill)); x.set('applyFill', '1')
        if numfmt is not None: x.set('numFmtId', str(numfmt)); x.set('applyNumberFormat', '1')
        xfs.append(x); xfs.set('count', str(len(xfs))); return str(len(xfs) - 1)
    s_num, s_tot = '15', '16'
    s_pct = nuevo_xf(s_num, numfmt=10)
    amar = {s: nuevo_xf(s, fill=fid) for s in ('0', s_num, s_tot)}; amar['pct'] = nuevo_xf(s_pct, fill=fid)
    for r in [r for r in sd.findall(q('row')) if int(r.get('r')) > r0]: sd.remove(r)
    FORM = {'Z': '+SUM(Tabla1[[#This Row],[Ene-26]:[Dic-26]])', 'AM': '+SUM(Tabla1[[#This Row],[Ene-27]:[Dic-27]])',
            'AN': 'IFERROR(AM{r}/Z{r}-1,0)', 'AO': 'Tabla1[[#This Row],[P27]]-Tabla1[[#This Row],[F26]]'}
    NUMC = ['N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH', 'AI', 'AJ', 'AK', 'AL']
    orden = sorted(set(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M'] + NUMC + list(FORM)), key=col_idx)
    for i, row in enumerate(L.itertuples(index=False), 1):
        rn = r0 + i; y = bool(row.amarilla); d = row._asdict()
        re_ = etree.SubElement(sd, q('row')); re_.set('r', str(rn)); re_.set('spans', '1:41')
        for col in orden:
            c = etree.SubElement(re_, q('c')); c.set('r', f'{col}{rn}')
            if col in FORM:
                c.set('s', amar['pct'] if (y and col == 'AN') else (s_pct if col == 'AN' else (amar[s_tot] if y else s_tot)))
                etree.SubElement(c, q('f')).text = FORM[col].format(r=rn)
            elif col in NUMC:
                c.set('s', amar[s_num] if y else s_num)
                v = d.get(col)
                if v is not None and not pd.isna(v) and abs(v) > 0.005: etree.SubElement(c, q('v')).text = repr(float(v))
            else:
                if y: c.set('s', amar['0'])
                v = d.get(col)
                if v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v) != '':
                    c.set('t', 'inlineStr'); etree.SubElement(etree.SubElement(c, q('is')), q('t')).text = str(v)
    r1 = r0 + max(len(L), 1)
    T.set('ref', f'{c0}{r0}:{c1}{r1}'); af = T.find(q('autoFilter'))
    if af is not None: af.set('ref', f'{c0}{r0}:{c1}{r1}')
    dim = S.find(q('dimension'))
    if dim is not None: dim.set('ref', f'A1:{c1}{r1}')
    dv = S.find(q('dataValidations'))
    if dv is not None:
        for v in dv: v.set('sqref', ' '.join(re.sub(r'(\D+)(\d+):(\D+)\d+', lambda m: f'{m.group(1)}{m.group(2)}:{m.group(3)}{r1}', p) for p in v.get('sqref').split()))
    WB = etree.fromstring(zin.read('xl/workbook.xml')); cp = WB.find(q('calcPr'))
    if cp is None: cp = etree.SubElement(WB, q('calcPr'))
    cp.set('fullCalcOnLoad', '1')
    nuevos = {sheet: S, tabs[0]: T, 'xl/styles.xml': ST, 'xl/workbook.xml': WB}
    zout = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
    for it in zin.infolist():
        if it.filename == 'xl/calcChain.xml': continue
        data = zin.read(it.filename)
        if it.filename in nuevos: data = etree.tostring(nuevos[it.filename], xml_declaration=True, encoding='UTF-8', standalone=True)
        elif it.filename == 'xl/_rels/workbook.xml.rels':
            R = etree.fromstring(data); [R.remove(r) for r in list(R) if r.get('Target', '').endswith('calcChain.xml')]
            data = etree.tostring(R, xml_declaration=True, encoding='UTF-8', standalone=True)
        elif it.filename == '[Content_Types].xml':
            Cx = etree.fromstring(data); [Cx.remove(o) for o in list(Cx) if o.get('PartName', '') == '/xl/calcChain.xml']
            data = etree.tostring(Cx, xml_declaration=True, encoding='UTF-8', standalone=True)
        zi = zipfile.ZipInfo(it.filename, date_time=it.date_time); zi.compress_type = zipfile.ZIP_DEFLATED; zi.external_attr = it.external_attr
        zout.writestr(zi, data)
    zout.close()

if __name__ == '__main__':
    os.makedirs(DST, exist_ok=True)
    X = datos(); ctx = Ctx()
    res = []
    for f in sorted(glob.glob(SRC + '*.xlsx')):
        pais = re.search(r'- (\w+) ILP', f).group(1)
        L, Y = lineas(X, pais, ctx)
        reescribir(f, DST + os.path.basename(f), L)
        tot = {m: float(L[COLM[m]].sum()) for m in MESES}; src = Y.groupby('Mes').Monto.sum().to_dict()
        res.append(dict(pais=pais, lineas=len(L), amarillas=int(L.amarilla.sum()), glosas=L.K.nunique(),
                        max_dif_mes=max(abs(tot[m] - src.get(m, 0)) for m in MESES), ene_jul=sum(tot[m] for m in range(1, 8)), ago=tot[8]))
        print(res[-1])
    pd.DataFrame(res).to_pickle('ilp_resultado.pkl')
