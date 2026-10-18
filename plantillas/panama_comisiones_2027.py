"""Formato Presupuesto (BBDD Planeamiento Financiero) Panamá · comisiones e intercompanies, con Real 2026 de la TD.

Parte del formato 2025 (6.11.24) y lo reescribe por XML (formatos, validaciones y comentarios intactos):
- 'BBDD - Gastos Directos' (Tabla22): las 13 cuentas del formato 2025, Real 2026 Ene-Ago por vehículo x CeCo x cuenta.
    · Contable: Commision Paid + TRASLADOS (vehículo BNK, regla Panamá).
    · Intercom: espejo INTERCOM / INTERCOM_ASB_* en filas aparte (Glosa 'Intercom').
    · Set-Dic 26 vacíos (los llena el área). Forecast 2026 = suma. Ene-27..Dic-27 = Presupuesto 2027 / 12.
- 'BBDD - Gastos PPTO 24' -> 'BBDD - Gastos PPTO 26' (Tabla2): Ppto 2026 de la TD para las mismas cuentas.
Filtros oficiales: Vista 1 y 3, sin IPC, con ajustes. Montos en USD (moneda local de Panamá).

Uso:  python3 panama_comisiones_2027.py <formato 2025.xlsx> <salida.xlsx>
"""
import sys, re, zipfile, os, copy
import pandas as pd
from lxml import etree
from td_filter import VISTAS, sin_ipc
from agosto_escribir import q, split_ref, col_idx

CUENTAS = ['52752012', '826100', '826300', '52131701', '52131705', '52131703', '827600', '822500', '822600',
           'recla de (+) a (+)', 'recla de (-) a (+) 11', 'recla de (-) a (+) 9', 'recla de (-) a (+) bony']
CONTABLE = ['Commision Paid', 'TRASLADOS', 'BNK']          # en el Ppto 2026 el lado contable ya viene como BNK
EXCLUIR = ['INTERCOM_ASB_WM', 'INTERCOM_ASB_AM']             # pedido de Planeamiento: fuera de la plantilla
BONY = 'BBH|BB&H|BONY'                                        # Bony = 'Pago a BBH' / BB&H / BoNY (en 2026 la cuenta puede venir como 0)
UDN = {'WM': 'GdP', 'AM': 'GdA', 'MDK': 'MdK', 'TESORERIA': 'Tesorería'}     # lista DATOS!I del formato
RESPONSABLE = os.environ.get('PPTO27_RESPONSABLE_PANAMA', '')    # responsable del presupuesto (se define al correr)
ARTICULO = 'Client Commision'
MES26 = ['Ene-26', 'Feb-26', 'Mar-26', 'Abr-26', 'May-26', 'Jun-26', 'Jul-26', 'Ago-26', 'Set-26', 'Oct-26', 'Nov-26', 'Dic-26']
MES27 = [m.replace('-26', '-27') for m in MES26]


def letra(n):
    s = ''
    while n: n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s


def datos_td(datos):
    df = pd.read_pickle('cache_full.pkl')
    p = df[(df.Datos == datos) & (df.Pais == 'PANAMA') & df.Vista.isin(VISTAS) & sin_ipc(df)
           & (df.Cta_Contable.astype(str).isin(CUENTAS) | df.Nom_Cta_Contable.astype(str).str.contains(BONY, case=False))].copy()
    comp = p['Compañía'].astype(str)
    p = p[(comp.isin(CONTABLE) | comp.str.startswith('INTERCOM')) & ~comp.isin(EXCLUIR)].copy()
    p['tipo'] = p['Compañía'].astype(str).map(lambda c: 'Contable' if c in CONTABLE else 'Intercom')
    p['vehiculo'] = p['Compañía'].astype(str).map(lambda c: 'BNK' if c in CONTABLE else c)
    p['mes'] = p['Mes'].astype(int)
    for c in ('CeCo', 'Cta_Contable', 'Nom_CeCo', 'Nom_Cta_Contable', 'UdN', 'Agrupación_CeCo', 'Nivel_1', 'Nivel_2', 'Nivel_3', 'Nivel_4'):
        p[c] = p[c].astype(str)
    return p


def lineas(p, meses):
    key = ['tipo', 'vehiculo', 'CeCo', 'Cta_Contable']
    m = p.groupby(key + ['mes']).Monto.sum().unstack('mes').reindex(columns=meses).fillna(0)
    m = m[(m.abs() >= 0.005).any(axis=1)]
    moda = lambda s: next((v for v in s.value_counts().index if v not in ('0', 'nan', '(blank)', '')), '')
    attr = p.groupby(key).agg({c: moda for c in ('Nom_CeCo', 'Nom_Cta_Contable', 'UdN', 'Agrupación_CeCo', 'Nivel_1', 'Nivel_2', 'Nivel_3', 'Nivel_4')})
    out = m.join(attr).reset_index()
    out['_o'] = out.tipo.map({'Contable': 0, 'Intercom': 1})
    return out.sort_values(['_o', 'vehiculo', 'CeCo', 'Cta_Contable']).drop(columns='_o').reset_index(drop=True)


def celda(row, col, rn, s, valor=None, formula=None, cache=None):
    c = etree.SubElement(row, q('c')); c.set('r', f'{col}{rn}')
    if s is not None: c.set('s', s)
    if formula is not None:
        if isinstance(cache, str): c.set('t', 'str')
        etree.SubElement(c, q('f')).text = formula
        if cache is not None: etree.SubElement(c, q('v')).text = str(cache) if isinstance(cache, str) else repr(round(float(cache), 6))
    elif valor is None or (isinstance(valor, float) and abs(valor) < 0.005): pass
    elif isinstance(valor, (int, float)): etree.SubElement(c, q('v')).text = repr(round(float(valor), 6)) if isinstance(valor, float) else str(valor)
    else:
        c.set('t', 'inlineStr'); etree.SubElement(etree.SubElement(c, q('is')), q('t')).text = str(valor)
    return c


def num_o_texto(v):
    if str(v) in ('0', '', 'nan'): return None              # cuenta 0 / vacía (p. ej. Pago a BBH) -> celda vacía
    return int(v) if str(v).isdigit() else v


def renombrar_cabecera(S, rn, nombres):
    """nombres: {col: texto} -> celdas de cabecera como texto en línea."""
    row = [r for r in S.find(q('sheetData')) if r.get('r') == str(rn)][0]
    for c in row.findall(q('c')):
        col = split_ref(c.get('r'))[0]
        if col in nombres:
            for ch in list(c): c.remove(ch)
            c.attrib.pop('t', None); c.set('t', 'inlineStr')
            etree.SubElement(etree.SubElement(c, q('is')), q('t')).text = nombres[col]


def renombrar_tabla(T, nombres_por_pos, formulas=None):
    cols = T.find(q('tableColumns'))
    for i, tc in enumerate(cols):
        if i in nombres_por_pos: tc.set('name', nombres_por_pos[i].replace('\n', '_x000a_'))
        if formulas and i in formulas:
            f = tc.find(q('calculatedColumnFormula'))
            if formulas[i] is None:
                if f is not None: tc.remove(f)
            else:
                if f is None: f = etree.SubElement(tc, q('calculatedColumnFormula'))
                f.text = formulas[i]


def reemplazar_filas(S, desde, filas_xml):
    sd = S.find(q('sheetData'))
    for r in list(sd):
        if int(r.get('r')) >= desde: sd.remove(r)
    for r in filas_xml: sd.append(r)


def main(src, dst):
    zin = zipfile.ZipFile(src)
    leer = lambda n: etree.fromstring(zin.read(n))
    WB = leer('xl/workbook.xml'); S2 = leer('xl/worksheets/sheet2.xml'); S4 = leer('xl/worksheets/sheet4.xml')
    T1 = leer('xl/tables/table1.xml'); T2 = leer('xl/tables/table2.xml')
    # Nivel 1-3 que devuelve el VLOOKUP del formato para 'Client Commision' (valor en caché)
    aux = pd.read_excel(src, sheet_name='Aux_Artículos', dtype=str)
    a = aux[aux.iloc[:, 1] == ARTICULO].iloc[0]
    n1, n2, n3 = a.iloc[4], a.iloc[3], a.iloc[2]

    # ---------------- Gastos Directos (Real 2026) ----------------
    R = lineas(datos_td('Real 2026'), list(range(1, 9)))
    if not R.Nom_Cta_Contable.str.contains(BONY, case=False).any():
        # Bony / BBH: en el Real 2026 está en 0 -> fila sin montos para que el área la presupueste (Ppto 2026: Pago a BBH)
        bony = {**{m: 0.0 for m in range(1, 9)}, 'tipo': 'Contable', 'vehiculo': 'BNK', 'CeCo': '211805', 'Cta_Contable': '',
                'Nom_CeCo': 'Banca Privada', 'Nom_Cta_Contable': 'Bony (Pago a BBH)', 'UdN': 'WM', 'Agrupación_CeCo': '', 'Nivel_1': '',
                'Nivel_2': '', 'Nivel_3': 'Sin Real 2026 en la TD (0) · Ppto 2026 Pago a BBH: 3,499.99/mes', 'Nivel_4': ''}
        k = int((R.tipo == 'Contable').sum())
        R = pd.concat([R.iloc[:k], pd.DataFrame([bony]), R.iloc[k:]], ignore_index=True)
    base = {split_ref(c.get('r'))[0]: c.get('s') for c in [r for r in S2.find(q('sheetData')) if r.get('r') == '8'][0]}
    sty = lambda col: '120' if 20 <= col_idx(col) <= 44 and col not in ('AF',) else ('121' if col in ('AF', 'AS') else base.get(col, '1'))
    vl = 'IFERROR(VLOOKUP(Tabla22[[#This Row],[Nivel 4\nArtículo]],Aux_Artículos!$B$2:$E$432,{k},FALSE),"")'
    filas = []
    for i, d in R.iterrows():
        rn = 8 + i; row = etree.Element(q('row')); row.set('r', str(rn)); row.set('spans', '1:45')
        glosa = 'Intercom (espejo de Commision Paid)' if d.tipo == 'Intercom' else d.Nivel_3
        vals = {'A': 'Panamá', 'B': d.vehiculo, 'C': RESPONSABLE, 'D': UDN.get(d.UdN.upper(), d.UdN), 'E': 'BAU',
                'F': num_o_texto(d.CeCo), 'G': d.Nom_CeCo, 'I': num_o_texto(d.Cta_Contable), 'J': d.Nom_Cta_Contable,
                'N': ARTICULO, 'O': 'Opex', 'Q': glosa, 'S': 'USD'}
        for k in range(1, 46):
            col = letra(k)
            if col in ('K', 'L', 'M'):
                celda(row, col, rn, sty(col), formula=vl.format(k={'K': 4, 'L': 3, 'M': 2}[col]), cache={'K': n1, 'L': n2, 'M': n3}[col])
            elif 20 <= k <= 31:                                   # Ene-26 .. Dic-26
                m = k - 19; celda(row, col, rn, sty(col), valor=float(d[m]) if m <= 8 else None)
            elif col == 'AF':
                celda(row, col, rn, sty(col), formula='SUM(Tabla22[[#This Row],[Ene-26]:[Dic-26]])', cache=float(sum(d[m] for m in range(1, 9))))
            elif 33 <= k <= 44:                                   # Ene-27 .. Dic-27
                celda(row, col, rn, sty(col), formula=f'IF($AS{rn}="","",$AS{rn}/12)', cache='')
            else:
                celda(row, col, rn, sty(col), valor=vals.get(col))
        filas.append(row)
    ult = 7 + len(R)
    reemplazar_filas(S2, 8, filas)
    renombrar_cabecera(S2, 7, {**{letra(20 + i): m for i, m in enumerate(MES26)}, 'AF': 'Forecast 2026',
                               **{letra(33 + i): m for i, m in enumerate(MES27)}, 'AS': 'Presupuesto\n2027'})
    renombrar_tabla(T1, {**{19 + i: m for i, m in enumerate(MES26)}, 31: 'Forecast 2026', **{32 + i: m for i, m in enumerate(MES27)}, 44: 'Presupuesto\n2027'},
                    {31: 'SUM(Tabla22[[#This Row],[Ene-26]:[Dic-26]])', **{32 + i: 'IF($AS8="","",$AS8/12)' for i in range(12)}})
    for el in (T1, T1.find(q('autoFilter'))): el.set('ref', f'A7:AS{ult}')
    S2.find(q('dimension')).set('ref', f'A2:AS{ult}')
    XM = '{http://schemas.microsoft.com/office/excel/2006/main}'
    for sq in S2.iter(XM + 'sqref'):
        sq.text = re.sub(r'^([A-Z]+)8:([A-Z]+)\d+$', lambda m: f'{m.group(1)}8:{m.group(2)}{ult}', sq.text)

    # ---------------- PPTO 26 (referencia) ----------------
    P = lineas(datos_td('Ppto 2026'), list(range(1, 13)))
    base4 = {split_ref(c.get('r'))[0]: c.get('s') for c in [r for r in S4.find(q('sheetData')) if r.get('r') == '2'][0]}
    filas = []
    for i, d in P.iterrows():
        rn = 2 + i; row = etree.Element(q('row')); row.set('r', str(rn)); row.set('spans', '1:36')
        vals = {'A': 'Panamá', 'B': d.vehiculo, 'C': RESPONSABLE, 'D': UDN.get(d.UdN.upper(), d.UdN), 'E': 'BAU',
                'G': d['Agrupación_CeCo'], 'H': num_o_texto(d.CeCo), 'I': d.Nom_CeCo, 'K': num_o_texto(d.Cta_Contable),
                'L': d.Nom_Cta_Contable, 'M': re.sub(r'^\d+ - ', '', d.Nivel_1), 'N': d.Nivel_2, 'O': d.Nivel_3, 'P': d.Nivel_4,
                'Q': 'Opex', 'S': 'Intercom (Ppto 2026 registrado en la TD)' if d.tipo == 'Intercom' else '', 'T': 'Base', 'W': 'USD',
                'AJ': float(sum(d[m] for m in range(1, 13)))}
        for k in range(1, 37):
            col = letra(k)
            v = float(d[k - 23]) if 24 <= k <= 35 else vals.get(col)
            celda(row, col, rn, base4.get(col), valor=v)
        filas.append(row)
    ult4 = 1 + max(len(P), 1)
    reemplazar_filas(S4, 2, filas)
    renombrar_cabecera(S4, 1, {**{letra(24 + i): m for i, m in enumerate(MES26)}, 'AJ': 'Presupuesto\n2026'})
    renombrar_tabla(T2, {**{23 + i: m for i, m in enumerate(MES26)}, 35: 'Presupuesto\n2026'})
    for el in (T2, T2.find(q('autoFilter'))): el.set('ref', f'A1:AJ{ult4}')
    if S4.find(q('dimension')) is not None: S4.find(q('dimension')).set('ref', f'A1:AJ{ult4}')
    for sh in WB.find(q('sheets')):
        if sh.get('name') == 'BBDD - Gastos PPTO 24': sh.set('name', 'BBDD - Gastos PPTO 26')
    cp = WB.find(q('calcPr')); cp.set('fullCalcOnLoad', '1')

    nuevos = {'xl/workbook.xml': WB, 'xl/worksheets/sheet2.xml': S2, 'xl/worksheets/sheet4.xml': S4,
              'xl/tables/table1.xml': T1, 'xl/tables/table2.xml': T2}
    zout = zipfile.ZipFile(dst + '.tmp', 'w', zipfile.ZIP_DEFLATED)
    for it in zin.infolist():
        if it.filename == 'xl/calcChain.xml': continue
        data = zin.read(it.filename)
        if it.filename in nuevos: data = etree.tostring(nuevos[it.filename], xml_declaration=True, encoding='UTF-8', standalone=True)
        elif it.filename == 'xl/_rels/workbook.xml.rels':
            X = etree.fromstring(data); [X.remove(r) for r in list(X) if r.get('Target', '').endswith('calcChain.xml')]
            data = etree.tostring(X, xml_declaration=True, encoding='UTF-8', standalone=True)
        elif it.filename == '[Content_Types].xml':
            X = etree.fromstring(data); [X.remove(o) for o in list(X) if o.get('PartName', '') == '/xl/calcChain.xml']
            data = etree.tostring(X, xml_declaration=True, encoding='UTF-8', standalone=True)
        elif it.filename == 'docProps/app.xml':
            data = data.replace('BBDD - Gastos PPTO 24'.encode(), 'BBDD - Gastos PPTO 26'.encode())
        zi = zipfile.ZipInfo(it.filename, date_time=it.date_time); zi.compress_type = zipfile.ZIP_DEFLATED; zi.external_attr = it.external_attr
        zout.writestr(zi, data)
    zout.close(); zin.close(); os.replace(dst + '.tmp', dst)
    R.to_pickle('panama_comisiones_real.pkl'); P.to_pickle('panama_comisiones_ppto.pkl')
    print(f'Gastos Directos: {len(R)} filas (Contable {sum(R.tipo == "Contable")}, Intercom {sum(R.tipo == "Intercom")}) · PPTO 26: {len(P)} filas')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
