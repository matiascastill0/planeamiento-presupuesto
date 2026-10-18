"""Plantilla de intercompanies (Entregable 3): Contable + Intercom = Gestión, en USD.

Regla (definida por Planeamiento):
- Intercom USA = lo que USA traslada en la TD (vehículos INTERCOM_USA_*, y en agosto INTERCOM_CHILE/COLOMBIA/PERU; lado USA), por Nivel 1/2 y mes.
- Cada país receptor recibe -% final x ese monto en todos los meses; % final = peso de cada destino en el mes de corte (agosto):
  Chile = USA_CHILE_WM (+ INTERCOM_CHILE) · Colombia = USA_COL_MDK + USA_COL_WM (+ INTERCOM_COLOMBIA) · Perú = USA_PERU_WM (+ INTERCOM_PERU).
  Los % suman 100 %, así que cada fila Intercom neta 0 entre países (efecto 0 siempre).
- Contable = TD oficial (Real 2026, Vista 1 y 3, sin INTERCOM/ELIM, sin IPC, con ajustes), por país y Nivel 1/2.
- Columna D (Tipo) = Contable / Intercom. Ppto 2027: los receptores llevan fórmula = -% x fila USA.

Uso:  python3 intercom_plantilla.py
"""
import pandas as pd, zipfile, os, re
from lxml import etree
from td_filter import VISTAS, NO_CONTABLES, sin_ipc
from agosto_escribir import partes, q, split_ref, col_idx
import ruta_v2

BASE = ruta_v2.BASE + '05. Databricks/04. Entregable 3 - Gestión con intercompanies/'
SRC = BASE + 'plantilla intercompanies - yaco.xlsx'
DST = BASE + 'Ppto27 - Intercompanies - Real Ene-Ago.xlsx'
MESES = ruta_v2.MESES
CORTE = MESES[-1]          # mes de corte (agosto): sus % se aplican a todos los meses
MCOL = ruta_v2.MCOL
P27 = ['AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH', 'AI', 'AJ', 'AK', 'AL']
PAISES = [('USA', 'USA'), ('CHILE', 'Chile'), ('COLOMBIA', 'Colombia'), ('PERU', 'Perú')]
# en agosto la TD trae el lado USA como INTERCOM_CHILE / _COLOMBIA / _PERU (mismo traslado, otro nombre)
DESTINO = {'CHILE': ['INTERCOM_USA_CHILE_WM', 'INTERCOM_CHILE'], 'COLOMBIA': ['INTERCOM_USA_COL_MDK', 'INTERCOM_USA_COL_WM', 'INTERCOM_COLOMBIA'],
           'PERU': ['INTERCOM_USA_PERU_WM', 'INTERCOM_PERU']}
GLOSA_IC = {'USA': 'INTERCOM_USA (traslado a Chile, Colombia y Perú)', 'CHILE': 'INTERCOM_USA_CHILE_WM',
            'COLOMBIA': 'INTERCOM_USA_COL_MDK + INTERCOM_USA_COL_WM', 'PERU': 'INTERCOM_USA_PERU_WM'}


def datos(df):
    r = df[(df.Datos == 'Real 2026') & df.Vista.isin(VISTAS) & sin_ipc(df)].copy()
    r['Mes'] = r['Mes'].astype(int)
    comp = r['Compañía'].astype(str)
    ic = r[(r.Pais == 'USA') & comp.isin(sum(DESTINO.values(), []))]
    tot = ic.groupby(ic['Compañía'].astype(str)).Monto_USD_Oficial.sum()
    corte = ic[ic.Mes == CORTE].groupby(ic['Compañía'].astype(str)).Monto_USD_Oficial.sum()      # % final = peso del mes de corte
    pct = {p: corte.reindex(v).fillna(0).sum() / corte.sum() for p, v in DESTINO.items()}
    pct['PERU'] = 1 - pct['CHILE'] - pct['COLOMBIA']          # suma exacta 100 %
    base = ic.groupby(['Nivel_1', 'Nivel_2', 'Mes'], observed=True).Monto_USD_Oficial.sum().unstack('Mes').reindex(columns=MESES).fillna(0)
    ct = r[~comp.str.contains('INTERCOM') & ~comp.isin(NO_CONTABLES) & r.Pais.isin([p for p, _ in PAISES])]
    cont = ct.groupby(['Pais', 'Nivel_1', 'Nivel_2', 'Mes'], observed=True).Monto_USD_Oficial.sum().unstack('Mes').reindex(columns=MESES).fillna(0)
    return base, cont, pct, tot


def lineas(base, cont, pct):
    L = []
    for p, ptxt in PAISES:
        claves = sorted(set(base.index) | {k[1:] for k in cont.index if k[0] == p})
        for n1, n2 in claves:
            fila = dict(A=ptxt, F=n1, G=n2, M='USD', J='')
            if (p, n1, n2) in cont.index:
                v = cont.loc[(p, n1, n2)]
                if (v.abs() >= 0.005).any():
                    L.append({**fila, 'D': 'Contable', 'K': 'Contable TD (sin INTERCOM / ELIM)', **{MCOL[m]: v[m] for m in MESES}, '_p': p, '_t': 'C'})
            if (n1, n2) in base.index:
                v = base.loc[(n1, n2)] * (1 if p == 'USA' else -pct[p])
                if (v.abs() >= 0.005).any():
                    L.append({**fila, 'D': 'Intercom', 'K': GLOSA_IC[p], **{MCOL[m]: v[m] for m in MESES}, '_p': p, '_t': 'I'})
    return pd.DataFrame(L)


def post(dst, L, r0, pct):
    """Encabezado D = Tipo y fórmulas Ppto 2027 de los receptores (= -% x fila USA del mismo Nivel 2)."""
    usa = {(d['F'], d['G']): r0 + 1 + i for i, d in enumerate(L.to_dict('records')) if d['_p'] == 'USA' and d['_t'] == 'I'}
    zin = zipfile.ZipFile(dst); sheet, tabs = partes(zin)
    S = etree.fromstring(zin.read(sheet)); sd = S.find(q('sheetData'))
    rows = {int(r.get('r')): r for r in sd.findall(q('row'))}
    for c in rows[r0].findall(q('c')):
        if split_ref(c.get('r'))[0] == 'D':
            for ch in list(c): c.remove(ch)
            c.set('t', 'inlineStr'); etree.SubElement(etree.SubElement(c, q('is')), q('t')).text = 'Tipo'
    nuevos = {sheet: S}
    for tp in tabs:
        T = etree.fromstring(zin.read(tp))
        tc = T.find(q('tableColumns'))
        if tc is not None and len(tc) > 3 and tc[3].get('name') == 'Sede':
            tc[3].set('name', 'Tipo'); nuevos[tp] = T
    n = 0
    for i, d in enumerate(L.to_dict('records')):
        if d['_t'] != 'I' or d['_p'] == 'USA': continue
        rn = r0 + 1 + i; ru = usa[(d['F'], d['G'])]
        celdas = {split_ref(c.get('r'))[0]: c for c in rows[rn].findall(q('c'))}
        for col in P27:
            c = celdas[col]
            for ch in list(c): c.remove(ch)
            etree.SubElement(c, q('f')).text = f'-{col}{ru}*{pct[d["_p"]]:.10f}'; n += 1
    zout = zipfile.ZipFile(dst + '.tmp', 'w', zipfile.ZIP_DEFLATED)
    for it in zin.infolist():
        data = zin.read(it.filename)
        if it.filename in nuevos: data = etree.tostring(nuevos[it.filename], xml_declaration=True, encoding='UTF-8', standalone=True)
        zi = zipfile.ZipInfo(it.filename, date_time=it.date_time); zi.compress_type = zipfile.ZIP_DEFLATED; zi.external_attr = it.external_attr
        zout.writestr(zi, data)
    zout.close(); zin.close(); os.replace(dst + '.tmp', dst)
    return n


if __name__ == '__main__':
    df = pd.read_pickle('cache_full.pkl')
    base, cont, pct, tot = datos(df)
    L = lineas(base, cont, pct)
    res = ruta_v2.escribir(SRC, DST, L.drop(columns=['_p', '_t']))
    nf = post(DST, L, res['r0'], pct)
    print('Vehículos USA (USD):', tot.round(2).to_dict(), '| total', round(tot.sum(), 2))
    print('% final:', {k: round(v * 100, 4) for k, v in pct.items()})
    print(f'Filas: {len(L)} (Contable {sum(L._t == "C")}, Intercom {sum(L._t == "I")}) · fórmulas P27: {nf}')
    pd.to_pickle(L, 'intercom_lineas.pkl')
