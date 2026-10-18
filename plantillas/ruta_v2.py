import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""Ruta Oficial v2 — reconstruye la tabla de cada plantilla con Real ene–ago 2026.
Fuentes: TD AGOSTO FINAL (rubros de personal, TyC, D&A, IyC, Marketing, UdN, Staff, ILP) y consolidados del usuario
(OyS, CS Administrativo, Consultorías y Honorarios). Reglas: sin INTERCOM, sin IPC, Vista 1 y 3, con ajustes (salvo OyS).
Homologación: cada cuenta en su fila; redondeo / ajuste al mil 1 fila por vehículo+CeCo; cuentas de ajuste contable
(ejercicios anteriores / extornos) se suman a la cuenta principal del mismo servicio; ceros = celda vacía.
Hoja Tablas: columna S = proveedores homologados usados (lista del desplegable), hoja oculta."""
import pandas as pd, numpy as np, re, os, glob, shutil, zipfile, copy, unicodedata
from lxml import etree
from td_filter import VISTAS, NO_CONTABLES, sin_ipc
from build_bd import fix
from agosto_lineas import Ctx, filtrar, lineas, _ceco, _objetos, PAIS_TXT, KEY
from agosto_escribir import partes, q, split_ref, col_idx
from agosto_encaje import nk
from prov_norm import homologar_fuerte, reparar, clave
from compactar import compactar
from ch_homolog import glosa_ch, destino_ch
from cs_homolog import glosa_cs
from oys_homolog import glosa_oys
import ilp_rebuild

BASE = RAIZ
ORIG = BASE + '01. Ruta Oficial Ppto27 (Real Ene-Ago)/'
DEST = BASE + '01. Ruta Oficial Ppto27 (Real Ene-Ago)/'
MESES = list(range(1, 9))
MCOL = dict(zip(MESES, ['N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U']))
TXT = list('ABCDEFGHIJKLM')
NUM = ['N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH', 'AI', 'AJ', 'AK', 'AL']
K2L = {'País': 'A', 'Vehículo': 'B', 'Ceco - Nombre': 'C', 'Sede': 'D', 'Nom Cta Contable': 'E', 'Nivel 1': 'F', 'Nivel 2': 'G', 'Nivel 3': 'H',
       'Nivel 4 Artículo': 'I', 'Proveedor': 'J', 'Glosa / Texto': 'K', 'Comentario de Área': 'L', 'Moneda': 'M'}
ORDEN_PAIS = ['CHILE', 'COLOMBIA', 'PERU', 'PANAMA', 'USA', 'MEXICO']
TXT2P = {'Chile': 'CHILE', 'Colombia': 'COLOMBIA', 'Perú': 'PERU', 'Panamá': 'PANAMA', 'USA': 'USA', 'México': 'MEXICO'}
STAFF = {'Staff - Oficina Representación': 'Staff - Oficina de Representación', 'Staff - Riesgos': 'Staff - Riesgo', 'Staff - Operaciones COO (Servicio al Cliente)': 'Staff - Operaciones (COO)', 'Staff - COE DE_CX': 'Staff - COE DE/CX'}
REDONDEO = re.compile(r'REDONDEO|AJUSTE AL MIL')
RESIDUO = 0.005          # filas con todos los meses bajo medio centavo = residuo (va a la fila de ajuste)
AJ_CONTABLE = re.compile(r'EJERCICIOS ANTERIORES|EXTORNO|PROVISIONES DE GASTOS')
NO_PROV = {nk(x) for x in ['Misiones', 'Gastos de Representación', 'Pagos Transaccionales, Bolsas y Otros', 'Suscripciones y Servicios de Información',
           'Transporte y Mensajería', 'Provisión de Incobrables', 'Marketing', 'Consultorías y Honorarios', 'Oficinas y Suministros', 'NA', 'N/E', 'N E',
           'OTROS', 'PTY', '0', 'SIN PROVEEDOR', 'NO APLICA', 'VARIOS', 'DIETAS', 'DIETA', '(blank)', 'BLANK', 'Varios proveedores', 'Varios clientes', 'Varios colaboradores']}
CH_CAT = {'Auditorias_V1y3': 'Auditorías Tributarias y Financieras', 'AsesoriasLegales_V1y3': 'Asesorías Legales', 'Dietas_V1y3': 'Dietas'}
CH_ARCH = {'Auditorías Tributarias y Financieras': 'Auditorías', 'Asesorías Legales': 'Asesorías Legales', 'Dietas': 'Dietas'}

def nfc(s): return unicodedata.normalize('NFC', s)
def pais_de(t):
    t = unicodedata.normalize('NFKD', nfc(t)).encode('ascii', 'ignore').decode().upper()
    for k in ORDEN_PAIS:
        if re.search(r'\b' + k + r'\b', t): return k
    if re.search(r'\bUS\b', t): return 'USA'

def clasificar(rel):
    p = nfc(rel).split('/'); f = p[-1]
    if p[0].startswith('02.'):
        if 'ILP' in f: return 'ILP', None, p[1].upper()
        return ('OGP' if 'OGP' in f else 'REM'), None, p[1].upper()
    if p[0].startswith('03.'):
        if p[1] == 'CS ADMINISTRATIVO': return 'CS', re.search(r'CS Administrativo (.*?) - OFICIAL', f).group(1), None
        if p[1].startswith('Facilities'): return 'OYS', re.search(r'Oficinas y Suministros (\w+)', f).group(1), pais_de(f)   # una plantilla por país
        if p[1] == 'Asesorías Legales': return 'CH', 'Asesorías Legales', pais_de(f)
        if p[1] == 'Asesorías Tributarias y Financieras': return 'CH', 'Auditorías Tributarias y Financieras', pais_de(f)
        if p[1] == 'Dietas': return 'CH', 'Dietas', None
        if p[1] == 'Marketing': return 'MKT', None, pais_de(f)
        if p[1] == 'Otros Gastos Administrativos': return 'OGA', None, pais_de(f)
        if p[1] == 'STAFF': return 'STAFF', STAFF.get(p[2], p[2]), pais_de(p[3])
        if p[1] == 'UDN': return 'UDN', p[2], pais_de(p[3])
    if p[0].startswith('04.'): return 'TYC', None, pais_de(f)
    if p[0].startswith('05.'): return 'DYA', None, pais_de(p[1])
    if p[0].startswith('06.'): return 'IYC', None, pais_de(p[1])
    raise ValueError(rel)

# ---------------------------------------------------------------- datos
def cargar_td():
    C = pd.read_pickle('cache_ago.pkl')
    C = C[(C.Datos.astype(str) == 'Real 2026')]
    C = _objetos(C); C['Mes'] = C.Mes.astype(int); C = C[C.Mes.between(1, 8)]
    for c in ['Pais', 'Vista', 'Compañía', 'Nivel_1', 'Nivel_2', 'Nivel_3', 'Agrupación_CeCo', 'UdN', 'Ajuste', 'Datos', 'Moneda']: C[c] = C[c].astype(str)
    C.loc[(C.Pais == 'PANAMA') & C['Compañía'].isin(['Commision Paid', 'TRASLADOS']), 'Compañía'] = 'BNK'
    H = pd.read_excel(BASE + '02. Insumos/06. Maestros/Homologación de CeCos 2026 2.xlsx', sheet_name='Homologación')
    ipc = {str(int(c)) for c in H.loc[H['Agrupación Ceco'].astype(str).eq('Invertir para Crecer'), 'Centro_Costos'].dropna()}
    c3 = C.CeCo.astype(str).str.replace(r'\.0$', '', regex=True).map(lambda s: s[-3:] if len(s) == 6 and s.startswith('211') else s)
    # EXCEPCIÓN a 'sin INTERCOM': INTERCOM_BCP de CS Administrativo / Indirecto BCP (plantilla CS Administrativo Indirecto BCP)
    global TD_INDIRECTO_BCP
    TD_INDIRECTO_BCP = C[C.Vista.isin(VISTAS) & C['Compañía'].eq('INTERCOM_BCP') & C.Nivel_2.eq('CS Administrativo') & C.Nivel_3.str.upper().eq('INDIRECTO BCP')].copy()
    C = C[C.Vista.isin(VISTAS) & ~C['Compañía'].isin(NO_CONTABLES) & ~C['Compañía'].str.contains('INTERCOM') & sin_ipc(C) & ~c3.isin(ipc)]
    C['Ajuste'] = C.Ajuste.where(~C.Ajuste.isin(['(blank)', 'nan', 'None', '']), None)
    return C

# ---------------------------------------------------------------- líneas por plantilla
UNIR_SERVICIO = ('UDN', 'STAFF', 'MKT', 'OGA', 'CS', 'CH')
def unir_por_servicio(G, ignorar_glosa=False):
    """Una fila por compañía + CeCo + Nivel 2 + proveedor + servicio (glosa): las cuentas que sólo cambian el número
    (ajustes de ejercicios anteriores, provisiones, extornos o cuentas equivalentes) se suman en la cuenta principal
    (la de mayor monto). Con ignorar_glosa (Consultorías y Honorarios) = una fila por proveedor, glosa de la principal.
    Sin proveedor: se mantiene la cuenta (es lo que identifica el gasto). Reuniones con Yaco / usuario, 2026-10-01."""
    if not len(G): return G
    G = G.copy()
    p = G.Proveedor.astype(object)
    named = p.notna() & ~p.astype(str).isin(['(sin proveedor)', 'nan', 'None', '']) & ~p.map(lambda v: nk(v) in NO_PROV if isinstance(v, str) else True)
    if not named.any(): return G
    k = ['País', 'Vehículo', 'Ceco - Nombre', 'Nivel 2', 'Proveedor', 'Moneda'] + ([] if ignorar_glosa else ['Glosa / Texto'])
    H = G[named]
    f = H[k].map(lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)).agg('|'.join, axis=1)
    peso = H.assign(_f=f, _c=H['Nom Cta Contable'].astype(str), _a=H.Monto.abs()).groupby(['_f', '_c'])._a.sum().reset_index()
    princ = peso.sort_values('_a', ascending=False).drop_duplicates('_f').set_index('_f')._c
    G.loc[named, 'Nom Cta Contable'] = f.map(princ).values
    if ignorar_glosa:
        pg = H.assign(_f=f, _g=H['Glosa / Texto'].astype(str), _a=H.Monto.abs()).groupby(['_f', '_g'])._a.sum().reset_index()
        G.loc[named, 'Glosa / Texto'] = f.map(pg.sort_values('_a', ascending=False).drop_duplicates('_f').set_index('_f')._g).values
    return G

# ---------------------------------------------------------------- sustento (trazabilidad línea -> movimientos de origen)
SUSTENTO_LINEAS, SUSTENTO_NETEO = [], []
CTX_PLANTILLA = None
def _lst(v):
    return v if isinstance(v, list) else ([] if v is None or (isinstance(v, float) and pd.isna(v)) else [v])
def _concat_src(s):
    return [x for v in s for x in _lst(v)]
def _neteo(L, motivo):
    """Movimientos de filas que no llegan a la plantilla (netean cero / residuo): quedan en el sustento."""
    if 'SRC' in L and len(L):
        for v in L.SRC: SUSTENTO_NETEO.extend({'Plantilla': CTX_PLANTILLA, 'SRC': x, 'Motivo': motivo} for x in _lst(v))

def a_mensual(G):
    """KEY + Mes + Monto -> una fila por KEY con columnas de meses."""
    if not len(G): return pd.DataFrame(columns=KEY + MESES)
    G = G.copy()
    for c in KEY:
        G[c] = G[c].map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) or str(v) in ('nan', 'None', '(sin dato)', '') else v)
    k = '|'.join
    G['Proveedor'] = G.Proveedor.map(lambda p: '(sin proveedor)' if p is None or nk(p) in NO_PROV else p)
    G['_k'] = G[KEY].map(lambda v: '' if v is None else str(v)).agg('|'.join, axis=1)
    P = G.pivot_table(index='_k', columns='Mes', values='Monto', aggfunc='sum').reindex(columns=MESES).fillna(0.0)
    first = G.drop_duplicates('_k').set_index('_k')[KEY]
    out = first.join(P)
    if 'SRC' in G: out = out.join(G.groupby('_k').SRC.agg(_concat_src))
    return out.reset_index(drop=True)

def unificar_proveedores(L):
    """Mismo proveedor escrito distinto (orden de palabras, mayúsculas, forma societaria: prov_norm.clave) -> un solo nombre
    en la plantilla (el de mayor monto) y se suman las filas que quedan con la misma llave."""
    if not len(L): return L
    p = L.Proveedor.astype(object)
    nombre = p.notna() & ~p.astype(str).isin(['(sin proveedor)', 'nan', 'None', ''])
    if not nombre.any(): return L
    ck = p[nombre].astype(str).map(clave)
    peso = L.loc[nombre, MESES].abs().sum(axis=1).groupby([ck, p[nombre].astype(str)]).sum()
    canon = {k: g.droplevel(0).idxmax() for k, g in peso.groupby(level=0) if len(g) > 1}
    if not canon: return L
    L = L.copy()
    L.loc[nombre, 'Proveedor'] = [canon.get(k, v) for k, v in zip(ck, p[nombre].astype(str))]
    k = [c for c in L.columns if c not in MESES and c != 'SRC']
    f = L[k].map(lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)).agg('|'.join, axis=1)
    S = L.groupby(f, sort=False)[MESES].sum()
    if 'SRC' in L: S = S.join(L.groupby(f, sort=False).SRC.agg(_concat_src))
    first = L.assign(_f=f).drop_duplicates('_f').set_index('_f')[k]
    return first.join(S).reset_index(drop=True)

def compresion_final(L):
    """Redondeo/ajuste al mil: 1 fila por vehículo+CeCo+Nivel 2 (cuenta más repetida). Cuentas de ajuste contable -> su
    cuenta principal (mismo vehículo, CeCo, Nivel 2, proveedor y glosa). Filas en cero fuera."""
    if not len(L): return L
    L = L.copy()
    # filas en cero fuera desde el inicio: una fila que netea 0 no debe impedir pegar '(sin proveedor)' a su único proveedor
    _neteo(L[L[MESES].abs().max(axis=1) <= 1e-9], 'movimientos que netean cero en la misma llave')
    L = L[L[MESES].abs().max(axis=1) > 1e-9]
    L = unificar_proveedores(L)
    if not len(L): return L
    L['_n'] = 1
    cta = L['Nom Cta Contable'].map(lambda s: nk(s))
    # residuos de fracciones de centavo: van a la fila única de ajuste al mil / redondeo del vehículo + CeCo
    L['_res'] = L[MESES].abs().max(axis=1) < RESIDUO
    red = cta.str.contains(REDONDEO) | L._res
    out = [L[~red]]; sueltos = []
    if red.any():
        R = L[red]; g = []
        for key, d in R.groupby(['País', 'Vehículo', 'Ceco - Nombre', 'Nivel 2', 'Moneda'], dropna=False):
            if d._res.all():                     # sin fila de ajuste real: no se crea una fila casi vacía
                sueltos.append(d); continue
            r = d[~d._res].iloc[0].copy()
            cnt = d[~d._res].groupby('Nom Cta Contable').size().sort_values(ascending=False)
            r['Nom Cta Contable'] = cnt.index[0]; r['Proveedor'] = '(sin proveedor)'
            r['Glosa / Texto'] = 'Ajuste al mil' if 'MIL' in nk(cnt.index[0]) else 'Ajuste por redondeo'
            for m in MESES: r[m] = d[m].sum()
            if 'SRC' in d: r['SRC'] = _concat_src(d.SRC)
            r['_n'] = len(d); g.append(r)
        out.append(pd.DataFrame(g))
    L = pd.concat(out, ignore_index=True)
    # cuentas de ajuste contable -> cuenta principal del mismo servicio (mismo vehículo, CeCo, Nivel 2, proveedor, glosa)
    L = L.reset_index(drop=True)
    aj = L['Nom Cta Contable'].map(nk).str.contains(AJ_CONTABLE) | L['Glosa / Texto'].astype(str).str.contains('ejercicios anteriores', case=False)
    k = ['País', 'Vehículo', 'Ceco - Nombre', 'Nivel 2', 'Moneda', 'Proveedor', 'Glosa / Texto']
    L['_kk'] = L[k].map(lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)).agg('|'.join, axis=1)
    # proveedor con nombre: el ajuste va a la fila principal del proveedor en el mismo vehículo + CeCo + Nivel 2, aunque la glosa
    # sea otra (p. ej. IMPRENTA ENCALADA: 'Ajustes de ejercicios anteriores' -> su línea de impresión). Sin proveedor: misma glosa.
    con_nombre = ~L.Proveedor.astype(str).isin(['(sin proveedor)', 'nan', 'None', ''])
    L.loc[con_nombre, '_kk'] = L.loc[con_nombre, k[:-1]].map(lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)).agg('|'.join, axis=1)
    L['_t'] = L[MESES].abs().sum(axis=1)
    principal = L[~aj].sort_values('_t', ascending=False).drop_duplicates('_kk')
    destino = dict(zip(principal._kk, principal.index))
    borrar = []
    for i in L.index[aj]:
        j = destino.get(L.at[i, '_kk'])
        if j is not None:
            L.loc[j, MESES] = L.loc[j, MESES].values + L.loc[i, MESES].values; borrar.append(i)
            if 'SRC' in L: L.at[j, 'SRC'] = _lst(L.at[j, 'SRC']) + _lst(L.at[i, 'SRC'])
    L = L.drop(index=borrar).drop(columns=['_t'])
    # '(sin proveedor)' -> único proveedor de la misma combinación (misma cuenta, CeCo, vehículo, Nivel 2/3, glosa)
    L = L.reset_index(drop=True)
    kp = ['País', 'Vehículo', 'Ceco - Nombre', 'Nom Cta Contable', 'Nivel 2', 'Nivel 3', 'Glosa / Texto', 'Moneda']
    L['_kp'] = L[kp].map(lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)).agg('|'.join, axis=1)
    sinp = L.Proveedor.astype(str).eq('(sin proveedor)')
    nombr = L[~sinp].groupby('_kp').filter(lambda g: len(g) == 1)
    dest = dict(zip(nombr._kp, nombr.index))
    borrar = []
    for i in L.index[sinp]:
        j = dest.get(L.at[i, '_kp'])
        if j is not None:
            L.loc[j, MESES] = L.loc[j, MESES].values + L.loc[i, MESES].values; borrar.append(i)
            if 'SRC' in L: L.at[j, 'SRC'] = _lst(L.at[j, 'SRC']) + _lst(L.at[i, 'SRC'])
    L = L.drop(index=borrar).drop(columns=['_kp'])
    # residuos sin fila de ajuste en su vehículo + CeCo: a la fila principal (mayor monto) del mismo vehículo + CeCo
    if sueltos:
        L = L.reset_index(drop=True)
        kv = ['País', 'Vehículo', 'Ceco - Nombre', 'Moneda']
        f = lambda X: X[kv].map(lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)).agg('|'.join, axis=1)
        aj = L['Glosa / Texto'].astype(str).isin(['Ajuste al mil', 'Ajuste por redondeo'])
        tot = L[MESES].abs().sum(axis=1) + aj * 1e18          # si el vehículo + CeCo tiene fila de ajuste (otro Nivel 2), va ahí
        dest = dict(zip(f(L.loc[tot.sort_values(ascending=False).index]).iloc[::-1], tot.sort_values(ascending=False).index[::-1]))
        for d in sueltos:
            for i, kk in zip(d.index, f(d)):
                j = dest.get(kk)
                if j is not None:
                    L.loc[j, MESES] = L.loc[j, MESES].values + d.loc[i, MESES].values.astype(float)
                    if 'SRC' in L: L.at[j, 'SRC'] = _lst(L.at[j, 'SRC']) + _lst(d.at[i, 'SRC'])
                else: _neteo(d.loc[[i]], 'residuo menor a medio centavo sin fila destino')
    _neteo(L[L[MESES].abs().max(axis=1) < RESIDUO], 'fila que netea cero / residuo menor a medio centavo')
    L = L[L[MESES].abs().max(axis=1) >= RESIDUO]
    return L.drop(columns=[c for c in ('_n', '_kk', '_res') if c in L.columns])

def consultorias_udn(sub, pais, H, ctx):
    """Consultorías de Negocio / de Staff de la base regional de Consultorías y Honorarios, por Agrupación CeCo (sin importar
    el Nivel 3), llevadas al esquema de la TD para pasar por la misma homologación de UdN / Staff."""
    X = H[(H.Cat == 'Consultorías') & (H['Agrupación_CeCo'].astype(str).str.strip() == sub) & (H.Pais == pais)].copy()
    if not len(X): return X
    X = ceco_por_nombre(X, pais, ctx)
    return pd.DataFrame({'Pais': pais, 'Compañía': X['Compañía'].astype(str), 'CeCo': X.CeCo, 'Nom_CeCo': X.Nom_CeCo,
                         'Nom_Cta_Contable': X.Nom_Cta_Contable, 'Nivel_1': '3 - Gastos Administrativos', 'Nivel_2': 'Consultorías y Honorarios',
                         'Nivel_3': X.Nivel_3.astype(str), 'Proveedor': X.Proveedor, 'Texto': X.Texto, 'Moneda': X.Moneda, 'Mes': X.Mes.astype(int),
                         'Monto': X['Monto ML'], 'Ajuste': X.Ajuste, 'SRC': 'CH:' + X.index.astype(str)})

def lineas_td(rubro, sub, pais, TD, ctx, H=None):
    R = filtrar(rubro, sub, pais, TD, sin_ajustes_oys=False)
    R = R.assign(SRC='TD:' + R.index.astype(str))              # sustento: movimiento de la TD (índice de la caché)
    if rubro in ('UDN', 'STAFF'):
        # OyS y CS Admin tienen plantilla propia; Consultorías y Honorarios sale de la base regional (no de la TD)
        R = R[~R.Nivel_2.isin(['Oficinas y Suministros', 'CS Administrativo', 'Consultorías y Honorarios'])]
        if H is not None:
            C = consultorias_udn(sub, pais, H, ctx)
            if len(C): R = pd.concat([_objetos(R), C], ignore_index=True)
    if not len(R): return pd.DataFrame(columns=KEY + MESES)
    G = lineas(rubro, sub, pais, R, ctx, compacto=True)
    if rubro in UNIR_SERVICIO: G = unir_por_servicio(G)
    L = compresion_final(a_mensual(G))
    if rubro == 'REM': L = nivel3_rem(L)
    if rubro in ('UDN', 'STAFF'): L = agrupar_ajustes(L)
    if rubro in ('UDN', 'STAFF') and len(L):
        # nunca Consultorías de Staff en una UdN ni de Negocio en un Staff: el Nivel 3 lo da la Agrupación de la plantilla
        L.loc[L['Nivel 2'].astype(str).eq('Consultorías y Honorarios'), 'Nivel 3'] = 'Consultorías de Negocio' if rubro == 'UDN' else 'Consultorías de Staff'
    return L

def agrupar_ajustes(L):
    """UdN / Staff (usuario, 2026-10-01/02): ajustes / gastos de años anteriores y gastos no deducibles -> por compañía + CeCo +
    Nivel 2 + servicio (glosa del concepto del texto), con la cuenta de mayor monto. Las PERSONAS NATURALES del grupo van juntas
    en una fila (nombres separados por '; '); cada EMPRESA queda en su propia fila (nunca empresa + persona en la misma celda)."""
    if not len(L): return L
    from agosto_lineas import es_empresa
    cta = L['Nom Cta Contable'].map(nk)
    aj = cta.str.contains(AJ_CONTABLE) | cta.str.contains('NO DEDUCIBLE') | L['Glosa / Texto'].astype(str).str.contains('ejercicios anteriores|Gastos no deducibles', case=False)
    if aj.sum() < 2: return L
    k = ['País', 'Vehículo', 'Ceco - Nombre', 'Nivel 2', 'Nivel 3', 'Glosa / Texto', 'Moneda']
    A_ = L[aj].copy()
    A_['_emp'] = A_.Proveedor.map(lambda p: es_empresa(p) and str(p) != '(sin proveedor)')
    A_['_quien'] = [str(p) if e else '' for p, e in zip(A_.Proveedor, A_._emp)]    # empresa: una fila por empresa; personas: juntas
    out = []
    for _, d in A_.groupby([A_[c].astype(str) for c in k] + [A_._quien], dropna=False):
        if len(d) == 1: out.append(d.drop(columns=['_emp', '_quien'])); continue
        r = d.iloc[0].copy()
        t = d[MESES].abs().sum(axis=1)
        r['Nom Cta Contable'] = d.assign(_t=t).groupby('Nom Cta Contable')._t.sum().idxmax()
        pv = d.assign(_t=t)[~d.Proveedor.astype(str).isin(['(sin proveedor)', 'nan', 'None', ''])].groupby('Proveedor')._t.sum().sort_values(ascending=False)
        r['Proveedor'] = '; '.join(pv.index) if len(pv) else '(sin proveedor)'
        for m in MESES: r[m] = d[m].sum()
        if 'SRC' in d: r['SRC'] = _concat_src(d.SRC)
        out.append(r.drop(labels=['_emp', '_quien']).to_frame().T)
    L = pd.concat([L[~aj]] + out, ignore_index=True)
    _neteo(L[L[MESES].abs().max(axis=1) < RESIDUO], 'ajustes / no deducibles que netean cero')
    return L[L[MESES].abs().max(axis=1) >= RESIDUO]

R_RELACIONADA = re.compile(r'CREDICORP|BANCO DE CREDITO|\bBCP\b')
REVISION_REL = []
def _tokens(s):
    return set(re.findall(r'[A-Z]{3,}', nk(str(s))))
def revisar_relacionadas(L, archivo):
    """UdN (usuario, 2026-10-02): proveedor = empresa Credicorp Capital / BCP con otra fila 'gemela' en la misma plantilla (mismo
    CeCo, cuenta, Nivel 1 y 2, glosa parecida y monto parecido) con otro proveedor -> la relacionada puede ser sólo quien pagó
    (p. ej. licencia Moody's comprada por CC Financieras y asignada a Capital Bolsa). NO se cambia nada: ambas filas se pintan de
    amarillo y el caso queda en REVISION_REL como sustento. Devuelve las posiciones (en L) a pintar."""
    if not len(L): return set()
    rel = L.Proveedor.astype(str).map(lambda p: bool(R_RELACIONADA.search(nk(p))))
    tot = L[MESES].sum(axis=1)
    pintar = set()
    k = ['Ceco - Nombre', 'Nom Cta Contable', 'Nivel 1', 'Nivel 2']
    for i in L.index[rel]:
        cand = L[(~rel) & ~L.Proveedor.astype(str).eq('(sin proveedor)')]
        for c in k: cand = cand[cand[c].astype(str) == str(L.at[i, c])]
        for j in cand.index:
            ti, tj = tot[i], tot[j]
            if ti == 0 or tj == 0 or (ti > 0) != (tj > 0): continue
            ratio = abs(tj) / abs(ti)
            gi, gj = _tokens(L.at[i, 'Glosa / Texto']), _tokens(L.at[j, 'Glosa / Texto'])
            sim = len(gi & gj) / max(len(gi | gj), 1)
            mi, mj = set(m for m in MESES if abs(L.at[i, m]) > 0.5), set(m for m in MESES if abs(L.at[j, m]) > 0.5)
            meses = len(mi & mj) / max(len(mi | mj), 1)
            if 0.75 <= ratio <= 1.33 and (sim >= 0.5 or meses >= 0.5):
                pintar |= {i, j}
                REVISION_REL.append(dict(Plantilla=archivo, _i=i, _j=j, Vehículo_rel=L.at[i, 'Vehículo'], CeCo=L.at[i, 'Ceco - Nombre'],
                                         Cuenta=L.at[i, 'Nom Cta Contable'], Nivel_2=L.at[i, 'Nivel 2'], Proveedor_relacionado=L.at[i, 'Proveedor'],
                                         Glosa_relacionado=L.at[i, 'Glosa / Texto'], Monto_relacionado=round(float(ti), 2),
                                         Posible_proveedor_real=L.at[j, 'Proveedor'], Vehículo_real=L.at[j, 'Vehículo'], Glosa_real=L.at[j, 'Glosa / Texto'],
                                         Monto_real=round(float(tj), 2), Similitud_glosa=round(sim, 2), Meses_en_común=round(meses, 2),
                                         Motivo='Proveedor relacionado (Credicorp Capital / BCP) con fila gemela de otro proveedor: posible pagador, no proveedor real'))
    return pintar

def normalizar_ceco(L):
    """Nombre del CeCo desde el maestro oficial; un mismo código con nombres escritos distinto queda con uno solo
    (p. ej. '211 - CENTRALIZADO' / '211 - Centralizado'); las filas que quedan iguales se suman."""
    if not len(L): return L
    from agosto_lineas import cecos_maestro
    m = cecos_maestro()
    cod = L['Ceco - Nombre'].astype(str).str.extract(r'^(\d+)\s*-\s*(.*)$')
    otro = {}
    for c, n in zip(cod[0], cod[1]):
        if isinstance(c, str) and c not in m and c not in otro: otro[c] = str(n).strip().upper() if str(n).strip().isupper() or True else n
    nuevo = [f'{c} - {m.get(c) or otro.get(c)}' if isinstance(c, str) else v for c, v in zip(cod[0], L['Ceco - Nombre'])]
    if list(nuevo) == list(L['Ceco - Nombre']): return L
    L = L.copy(); L['Ceco - Nombre'] = nuevo
    k = [c for c in L.columns if c not in MESES and c != 'SRC']
    f = L[k].map(lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)).agg('|'.join, axis=1)
    S = L.groupby(f, sort=False)[MESES].sum()
    if 'SRC' in L: S = S.join(L.groupby(f, sort=False).SRC.agg(_concat_src))
    return L.assign(_f=f).drop_duplicates('_f').set_index('_f')[k].join(S).reset_index(drop=True)

MUTUOS = re.compile(r'^INDEMNI|BONIFICACION DE RETIRO NO SALARIAL')
def nivel3_rem(L):
    """Remuneración Fija: cuentas que empiezan con INDEMNI y BONIFICACION DE RETIRO NO SALARIAL -> Nivel 3 'Mutuos y Signings';
    el resto de Remuneración Fija -> 'Remuneración fija neta' (regla del usuario, 2026-10-01). ICP / Variable sin cambio."""
    if not len(L): return L
    L = L.copy()
    rf = L['Nivel 2'].astype(str).eq('Remuneración Fija')
    cta = L['Nom Cta Contable'].map(lambda s: unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().upper().strip())
    L.loc[rf, 'Nivel 3'] = ['Mutuos y Signings' if MUTUOS.search(c) else 'Remuneración fija neta' for c in cta[rf]]
    return L

def lineas_ilp(pais, TD, ctx):
    X = TD[(TD.Pais == pais) & (TD.Nivel_2 == 'Incentivo Largo Plazo')].copy()
    if not len(X): return pd.DataFrame(columns=KEY + MESES)
    X['Nom_Cta_Contable'] = X.Nom_Cta_Contable.map(lambda v: fix(v) if isinstance(v, str) else str(v))
    out, _ = ilp_rebuild.lineas(X, pais, ctx)
    inv = {v: k for k, v in K2L.items()}
    L = pd.DataFrame({inv[c]: out[c] for c in out.columns if c in inv})
    for m in MESES: L[m] = out[MCOL[m]].fillna(0.0)
    for c in KEY:
        if c not in L: L[c] = None
    return L[KEY + MESES]

def _homol_base(B, prov_col, glosa_col):
    B = B.copy()
    # proveedores que no son proveedores (nombre del rubro, N/E, NA, (blank), OTROS...) -> '(sin proveedor)'
    B['Proveedor_H'] = B[prov_col].map(lambda p: '(sin proveedor)' if p is None or (isinstance(p, float) and pd.isna(p)) or nk(p) in ('', 'N E', 'NA', 'SIN PROVEEDOR', '0', 'BLANK', 'DIETAS', 'DIETA', 'OTROS', 'NO APLICA', 'N A') or nk(p) in NO_PROV else reparar(str(p)))
    m = homologar_fuerte(B.Proveedor_H.unique()); B['Proveedor_H'] = B.Proveedor_H.map(lambda v: m.get(v, v))
    B['Glosa'] = B[glosa_col].map(lambda s: re.sub(r'\s+', ' ', str(s)).strip() if s is not None and not (isinstance(s, float) and pd.isna(s)) else '(sin descripción)')
    return B

def ceco_por_nombre(X, pais, ctx):
    """Código de CeCo: el de la TD si la fila lo trae; si no, por nombre (país, luego global, Tablas, alias). Excluye filas sin CeCo que netean 0."""
    if 'CeCo' in X:
        cod = X.CeCo.astype(object).map(lambda v: (lambda s: s[-3:] if len(s) == 6 and s.startswith('211') else s)(re.sub(r'\.0$', '', str(v))) if v is not None and str(v) not in ('nan', 'None', '', '0') else None)
        if cod.notna().all():
            X = X.copy(); X['CeCo'] = cod; return X
    loc = {str(n).strip().upper(): c for n, c in ctx.nombre_ceco.get(pais, {}).items()}
    glob_ = {}
    for p_, m_ in ctx.nombre_ceco.items():
        for n, c in m_.items(): glob_.setdefault(str(n).strip().upper(), c)
    tab = {v.split(' - ', 1)[1].strip().upper(): k for k, v in ctx.tablas_ceco.items() if ' - ' in v}
    ALIAS = {'CASH MANAGEMENT': '521'}
    X['CeCo'] = [loc.get(str(n).strip().upper()) or glob_.get(str(n).strip().upper()) or tab.get(str(n).strip().upper()) or ALIAS.get(str(n).strip().upper()) for n in X.Nom_CeCo]
    sin = X.CeCo.isna()
    if sin.any():
        neto = X[sin].groupby('Nom_CeCo')['Monto ML'].sum()
        cero = set(neto[neto.abs() < 0.01].index)
        print(f'   {pais}: se excluyen filas sin CeCo que netean 0: {sorted(cero)}')
        X = X[~(sin & X.Nom_CeCo.isin(cero))]
    return X

def lineas_base(B, pais, ctx, n1, n2, n3col=None, ceco_fijo=None, key_extra=()):
    X = B[B.Pais == pais].copy()
    if not len(X): return pd.DataFrame(columns=KEY + MESES)
    if ceco_fijo: X['CeCo'] = ceco_fijo
    else: X = ceco_por_nombre(X, pais, ctx)
    X['Nivel_1'] = n1
    X = _ceco(X, ctx, pais)
    malos = X[~X['Ceco - Nombre'].astype(str).str.match(r'^\d+ - ')]
    if len(malos): raise ValueError(f'{pais}: CeCo sin número: {malos.Nom_CeCo.unique()[:8]}')
    X['Monto'] = X['Monto ML']; X['Mes'] = X.Mes.astype(int)
    G = pd.DataFrame({'País': PAIS_TXT[pais], 'Vehículo': X['Compañía'], 'Ceco - Nombre': X['Ceco - Nombre'], 'Sede': None,
                      'Nom Cta Contable': X.Nom_Cta_Contable.map(lambda v: fix(v) if isinstance(v, str) else str(v)), 'Nivel 1': X['Nivel 1'], 'Nivel 2': n2,
                      'Nivel 3': X[n3col] if n3col else None, 'Proveedor': X.Proveedor_H, 'Glosa / Texto': X.Glosa,
                      'Moneda': X.Moneda, 'Mes': X.Mes, 'Monto': X.Monto,
                      'SRC': X['SRC'] if 'SRC' in X else {'Oficinas y Suministros': 'OYS:', 'CS Administrativo': 'CS:', 'Consultorías y Honorarios': 'CH:'}.get(n2, 'B:') + X.index.astype(str)})
    if n2 == 'Consultorías y Honorarios': G = unir_por_servicio(G, ignorar_glosa=True)   # una fila por proveedor
    elif n2 == 'CS Administrativo': G = unir_por_servicio(G)
    return compresion_final(a_mensual(G))

def lineas_oys(cat, pais, B, ctx):
    X = B[(B.Pais == pais) & (B.Plantilla == cat)]
    n1 = '3 - Gastos Administrativos'
    if pais == 'CHILE':
        cen = X[X.Ajuste.astype(str).str.upper().str.strip() == 'CENTRALIZADO']
        imp = X[X.Ajuste.astype(str).str.upper().str.strip() == 'IMPUTADO']
        a = lineas_base(cen, pais, ctx, n1, 'Oficinas y Suministros', 'Nivel_3', ceco_fijo='309')
        b = lineas_base(imp, pais, ctx, n1, 'Oficinas y Suministros', 'Nivel_3')
        return pd.concat([a, b], ignore_index=True)
    X = X[X.Sin_Ajuste.astype(str).str.upper().isin(['TRUE', '1'])]
    return lineas_base(X, pais, ctx, n1, 'Oficinas y Suministros', 'Nivel_3')

def lineas_cs(cat, pais, B, ctx):
    X = B[(B.Pais == pais) & (B.Cat == cat)].copy(); X['N3'] = cat
    return lineas_base(X, pais, ctx, '3 - Gastos Administrativos', 'CS Administrativo', 'N3')

TD_INDIRECTO_BCP = None
def lineas_indirecto_bcp(pais, B, ctx):
    """Indirecto BCP (INTERCOM_BCP, excepción): meses de la base consolidada de CS; los meses que la base no trae, desde la TD.
    Formato de la plantilla validada: Contrato Soporte / BANCO DE CREDITO DEL PERU / 'Soporte BCP (indirecto)'."""
    X = B[(B.Pais == pais) & (B.Cat == 'Indirecto BCP')].copy()
    X['SRC'] = 'CS:' + X.index.astype(str)
    T = TD_INDIRECTO_BCP[TD_INDIRECTO_BCP.Pais == pais] if TD_INDIRECTO_BCP is not None else pd.DataFrame()
    T = T[~T.Mes.isin(set(X.Mes.astype(int)))]
    if len(T):
        T = pd.DataFrame({'Pais': pais, 'Compañía': T['Compañía'], 'Nom_CeCo': T.Nom_CeCo.astype(str), 'Nom_Cta_Contable': T.Nom_Cta_Contable.astype(str),
                          'Moneda': T.Moneda, 'Mes': T.Mes.astype(int), 'Monto ML': T.Monto.astype(float), 'SRC': 'TD:' + T.index.astype(str)})
        X = pd.concat([X, T], ignore_index=True)
    if not len(X): return pd.DataFrame(columns=KEY + MESES)
    vacia = X.Nom_Cta_Contable.isna() | X.Nom_Cta_Contable.astype(object).astype(str).str.strip().isin(['nan', 'None', '(blank)', ''])
    X['Nom_Cta_Contable'] = X.Nom_Cta_Contable.astype(object).where(~vacia, 'Contrato Soporte')
    X['Proveedor_H'] = 'BANCO DE CREDITO DEL PERU'; X['Glosa'] = 'Soporte BCP (indirecto)'; X['N3'] = 'Indirecto BCP'
    return lineas_base(X, pais, ctx, '3 - Gastos Administrativos', 'CS Administrativo', 'N3')

def lineas_ch(cat, pais, B, ctx):
    X = B[(B.Pais == pais) & (B.Cat == cat)].copy(); X['N3'] = cat
    return lineas_base(X, pais, ctx, '3 - Gastos Administrativos', 'Consultorías y Honorarios', 'N3')

def ordenar(L, rubro):
    if not len(L): return L
    L = L.copy()
    L['_p'] = L['País'].map(lambda t: ORDEN_PAIS.index(TXT2P.get(t, 'MEXICO')) if TXT2P.get(t) in ORDEN_PAIS else 9)
    L['_c'] = L['Ceco - Nombre'].astype(str).str.extract(r'^(\d+)')[0].astype(float)
    L['_sin'] = L.Proveedor.astype(str).eq('(sin proveedor)')
    if rubro == 'OYS':                   # Yaco: Nivel 3 > Proveedor > Compañía > Cuenta, de la Z a la A
        L = L.sort_values(['_p', 'Nivel 3', 'Proveedor', 'Vehículo', 'Nom Cta Contable', '_c'], ascending=[True, False, False, False, False, True],
                          key=lambda s: s.astype(str).map(nk) if s.dtype == object else s)
        return L.drop(columns=[c for c in L.columns if str(c).startswith('_')]).reset_index(drop=True)
    if rubro == 'OGP':
        L['_pr'] = L.Proveedor.astype(str).map(nk)
        L = L.sort_values(['_p', '_sin', '_pr', '_c', 'Vehículo', 'Nom Cta Contable', 'Glosa / Texto'], key=lambda s: s.astype(str) if s.dtype == object else s)
    else:
        L = L.sort_values(['_p', '_c', 'Vehículo', 'Nivel 2', 'Nom Cta Contable', '_sin', 'Proveedor', 'Glosa / Texto'], key=lambda s: s.astype(str) if s.dtype == object else s)
    return L.drop(columns=[c for c in L.columns if str(c).startswith('_')]).reset_index(drop=True)

# ---------------------------------------------------------------- escritura (XML)
def escribir(src, dst, L, amarillo=None):
    zin = zipfile.ZipFile(src); sheet, tabs = partes(zin)
    S = etree.fromstring(zin.read(sheet)); sd = S.find(q('sheetData'))
    rows = {int(r.get('r')): r for r in sd.findall(q('row'))}
    T = None
    for tp in tabs:
        t = etree.fromstring(zin.read(tp)); a, b = t.get('ref').split(':')
        if col_idx(split_ref(a)[0]) <= col_idx('U') <= col_idx(split_ref(b)[0]): T, tab_path = t, tp
    a, b = T.get('ref').split(':'); c0, r0 = split_ref(a); c1, r1 = split_ref(b)
    # agosto ya es real: su encabezado va con el formato de los meses reales (gris de Jul-26), no el naranja de los meses por presupuestar
    hdr = {split_ref(c.get('r'))[0]: c for c in rows[r0].findall(q('c'))}
    if 'T' in hdr and 'U' in hdr and hdr['T'].get('s'): hdr['U'].set('s', hdr['T'].get('s'))
    base = copy.deepcopy(rows.get(r0 + 1, rows[r0]))
    form = {}
    for rr in range(r0 + 1, r1 + 1):
        for c in rows.get(rr, []):
            f = c.find(q('f')); col = split_ref(c.get('r'))[0]
            if f is not None and f.text and col not in form: form[col] = (f.text, rr)
    if 'Z' not in form: form['Z'] = ('+SUM(Tabla1[[#This Row],[Ene-26]:[Dic-26]])', 0)
    if 'AM' not in form: form['AM'] = ('+SUM(Tabla1[[#This Row],[Ene-27]:[Dic-27]])', 0)
    if 'AN' not in form: form['AN'] = (f'IFERROR(AM{r0+1}/Z{r0+1}-1,0)', r0 + 1)
    if 'AO' not in form: form['AO'] = ('Tabla1[[#This Row],[P27]]-Tabla1[[#This Row],[F26]]', 0)
    bajo = [r for r in rows if r > r1 and any(c.find(q('v')) is not None or c.find(q('is')) is not None or c.find(q('f')) is not None for c in rows[r])]
    if bajo: raise RuntimeError(f'filas con datos bajo la tabla: {bajo[:5]}')
    for r in list(rows):
        if r > r0: sd.remove(rows[r])
    cols_base = {split_ref(c.get('r'))[0]: c for c in base.findall(q('c'))}
    sty = {}
    for col in set(TXT) | set(NUM) | set(form):
        s = cols_base[col].get('s') if col in cols_base else None
        if not s:
            s = {'Z': cols_base.get('Z'), 'AM': cols_base.get('AM')}.get(col)
            s = s.get('s') if s is not None else None
        if not s and col in NUM: s = (cols_base.get('N') or cols_base.get('T') or etree.Element('x')).get('s')
        sty[col] = s
    todas = sorted(set(TXT) | set(NUM) | set(form), key=col_idx)
    rec = L.to_dict('records')
    for i, d in enumerate(rec, 1):
        rn = r0 + i; row = etree.SubElement(sd, q('row')); row.set('r', str(rn))
        for k in ('spans', 'ht', 'customHeight'):
            if base.get(k): row.set(k, base.get(k))
        for col in todas:
            c = etree.SubElement(row, q('c')); c.set('r', f'{col}{rn}')
            if sty.get(col): c.set('s', sty[col])
            if col in form:
                txt, sr = form[col]
                txt = re.sub(r'(?<![A-Za-z\[])(\$?[A-Z]{1,3}\$?)' + str(sr) + r'(?!\d)', lambda m: m.group(1) + str(rn), txt) if sr else txt
                etree.SubElement(c, q('f')).text = txt
            elif col in NUM:
                v = d.get(col)
                if v is not None and not pd.isna(v) and round(float(v), 6) != 0: etree.SubElement(c, q('v')).text = repr(round(float(v), 6))
            else:
                v = d.get(col)
                if v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v) not in ('', 'nan', 'None'):
                    c.set('t', 'inlineStr'); etree.SubElement(etree.SubElement(c, q('is')), q('t')).text = str(v)
    rN = r0 + max(len(rec), 1)
    estilos = None
    if amarillo:                          # filas a revisar: mismo estilo de cada celda + relleno amarillo (revisión UdN)
        estilos = etree.fromstring(zin.read('xl/styles.xml'))
        fills = estilos.find(q('fills')); fl = etree.SubElement(fills, q('fill')); pf = etree.SubElement(fl, q('patternFill')); pf.set('patternType', 'solid')
        etree.SubElement(pf, q('fgColor')).set('rgb', 'FFFFFF00'); etree.SubElement(pf, q('bgColor')).set('indexed', '64')
        fills.set('count', str(len(fills))); fid = str(len(fills) - 1)
        xfs = estilos.find(q('cellXfs')); variante = {}
        def amar(sid):
            if sid not in variante:
                x = copy.deepcopy(xfs[int(sid or 0)]); x.set('fillId', fid); x.set('applyFill', '1'); xfs.append(x)
                xfs.set('count', str(len(xfs))); variante[sid] = str(len(xfs) - 1)
            return variante[sid]
        for pos in amarillo:
            row = [r for r in sd.findall(q('row')) if int(r.get('r')) == r0 + 1 + pos]
            for c in (row[0].findall(q('c')) if row else []): c.set('s', amar(c.get('s')))
    T.set('ref', f'{c0}{r0}:{c1}{rN}'); af = T.find(q('autoFilter'))
    if af is not None: af.set('ref', f'{c0}{r0}:{c1}{rN}')
    dim = S.find(q('dimension'))
    if dim is not None: dim.set('ref', f"A1:{c1}{rN}")
    dv = S.find(q('dataValidations'))
    if dv is not None:
        for v in dv:
            v.set('sqref', ' '.join(re.sub(r'^([A-Z]+)\d+(:([A-Z]+)\d+)?$', lambda m: f'{m.group(1)}{r0+1}:{m.group(3) or m.group(1)}{rN}', p) for p in v.get('sqref').split()))
    # ---- Tablas: columna S con proveedores homologados, hoja oculta
    WB = etree.fromstring(zin.read('xl/workbook.xml'))
    cp = WB.find(q('calcPr'))
    if cp is None: cp = etree.SubElement(WB, q('calcPr'))
    cp.set('fullCalcOnLoad', '1')
    provs = sorted({str(p) for p in L.get('J', pd.Series(dtype=object)).dropna() if str(p) not in ('', 'nan', 'None')}, key=lambda s: (s == '(sin proveedor)', nk(s)))
    nuevos = {sheet: S, tab_path: T, 'xl/workbook.xml': WB}
    if estilos is not None: nuevos['xl/styles.xml'] = estilos
    sheets = {s.get('name'): s for s in WB.find(q('sheets'))}
    tablas_ok = False
    if 'Tablas' in sheets:
        sheets['Tablas'].set('state', 'hidden')
        RNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
        wr = etree.fromstring(zin.read('xl/_rels/workbook.xml.rels'))
        tpath = 'xl/' + [r for r in wr if r.get('Id') == sheets['Tablas'].get(RNS)][0].get('Target').lstrip('/').replace('xl/', '')
        TS = etree.fromstring(zin.read(tpath)); tsd = TS.find(q('sheetData'))
        trows = {int(r.get('r')): r for r in tsd.findall(q('row'))}
        for r in trows.values():
            for c in r.findall(q('c')):
                if split_ref(c.get('r'))[0] == 'S': r.remove(c)
        for i, p in enumerate(provs, 1):
            r = trows.get(i)
            if r is None:
                r = etree.Element(q('row')); r.set('r', str(i))
                nxt = [x for x in tsd.findall(q('row')) if int(x.get('r')) > i]
                (nxt[0].addprevious(r) if nxt else tsd.append(r)); trows[i] = r
            c = etree.Element(q('c')); c.set('r', f'S{i}'); c.set('t', 'inlineStr'); etree.SubElement(etree.SubElement(c, q('is')), q('t')).text = p
            desp = [x for x in r.findall(q('c')) if col_idx(split_ref(x.get('r'))[0]) > col_idx('S')]
            (desp[0].addprevious(c) if desp else r.append(c))
        # ---- columnas H / I / J (lista de CeCo del desplegable): maestro oficial completo + CeCos de la plantilla que no estén
        from agosto_lineas import cecos_maestro
        mc = dict(cecos_maestro())
        for v in L.get('C', pd.Series(dtype=object)).dropna().astype(str):
            mm = re.match(r'^(\d+)\s*-\s*(.*)$', v)
            if mm and mm.group(1) not in mc: mc[mm.group(1)] = mm.group(2)
        for r in list(trows.values()):
            for c in r.findall(q('c')):
                if split_ref(c.get('r'))[0] in ('H', 'I', 'J'): r.remove(c)
        for i, (cod, nom) in enumerate(mc.items(), 1):
            r = trows.get(i)
            if r is None:
                r = etree.Element(q('row')); r.set('r', str(i))
                nxt = [x for x in tsd.findall(q('row')) if int(x.get('r')) > i]
                (nxt[0].addprevious(r) if nxt else tsd.append(r)); trows[i] = r
            nuevas = []
            ch = etree.Element(q('c')); ch.set('r', f'H{i}')
            if cod.isdigit(): etree.SubElement(ch, q('v')).text = cod
            else: ch.set('t', 'inlineStr'); etree.SubElement(etree.SubElement(ch, q('is')), q('t')).text = cod
            ci = etree.Element(q('c')); ci.set('r', f'I{i}'); ci.set('t', 'inlineStr'); etree.SubElement(etree.SubElement(ci, q('is')), q('t')).text = nom
            cj = etree.Element(q('c')); cj.set('r', f'J{i}'); cj.set('t', 'str')
            etree.SubElement(cj, q('f')).text = f'_xlfn.CONCAT(H{i}," - ",I{i})'; etree.SubElement(cj, q('v')).text = f'{cod} - {nom}'
            for c in (ch, ci, cj):
                desp = [x for x in r.findall(q('c')) if col_idx(split_ref(x.get('r'))[0]) > col_idx(split_ref(c.get('r'))[0])]
                (desp[0].addprevious(c) if desp else r.append(c))
        dimt = TS.find(q('dimension'))
        if dimt is not None:
            mx = max([int(x.get('r')) for x in tsd.findall(q('row'))] or [1])
            dimt.set('ref', f'A1:T{max(mx, len(provs), len(mc))}')
        nuevos[tpath] = TS
        dn = WB.find(q('definedNames'))
        if dn is not None:
            for d in dn:
                if d.get('name') == 'Proveedor': d.text = f'Tablas!$S$1:$S${max(len(provs), 1)}'
                if d.get('name') == 'Ceco_Nombre': d.text = f'Tablas!$J$1:$J${len(mc)}'
        tablas_ok = True
    zout = zipfile.ZipFile(dst + '.tmp', 'w', zipfile.ZIP_DEFLATED)
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
    zout.close(); zin.close(); os.replace(dst + '.tmp', dst)
    return dict(filas=len(rec), proveedores=len(provs), tablas=tablas_ok, r0=r0)

def a_letras(L):
    O = pd.DataFrame({K2L[c]: L[c] for c in KEY if c in L})
    for m in MESES: O[MCOL[m]] = L[m].values
    for c in TXT:
        if c not in O: O[c] = None
    return O

# ---------------------------------------------------------------- principal
CS_REGLAS = [(r'IMPORTACION DE ASIENTOS|ASIENTOS', 'Asientos entre relacionadas'),
             (r'REEMBOLSO', 'Reembolso de gastos'),
             (r'DIFERENCIA EN CAMBIO|DIFERENCIAS? PESOS', 'Diferencia en cambio'),
             (r'PROFESIONALES ESPECIALIZADOS.*VARIABLE|VARIABLE.*PROFESIONALES', 'Profesionales especializados variable'),
             (r'PROFESIONALES ESPECIALIZADOS|POFESIONALES', 'Profesionales especializados'),
             (r'OPERATIVO VARIABLE', 'Servicio operativo variable'),
             (r'SOPORTE.*VARIABLE|VARIABLE.*SOPORTE', 'Servicio de soporte variable'),
             (r'SOPORTE REGIONAL', 'Soporte regional'),
             (r'SOPORTE', 'Servicio de soporte'),
             (r'SERVICIOS? ADMINISTRATIVOS?', 'Servicios administrativos')]
CS_REGLAS = [(re.compile(r), g) for r, g in CS_REGLAS]
def servicio_cs(cat, serv, cuenta, texto):
    s = nk(serv)
    for rx, g in CS_REGLAS:
        if rx.search(s): return g
    return glosa_cs(cat, cuenta, texto)

CLASIF_CH = BASE + '02. Insumos/02. Bases consolidadas OyS-CS-Consultorías/Clasificación C&H por plantilla.xlsx'
UDN_AGR = {'AM', 'MDK', 'NNFF', 'Tesorería', 'TYBA', 'WM', 'JV CND', 'FINCORP'}
def exportar_clasificacion_ch(H):
    """Base de la clasificación: cada fila de la base Regional C&H con su plantilla destino y la regla que la decidió."""
    X = H.copy()
    X['Hoja origen'] = X.Plantilla.map(CH_CAT)
    X['Plantilla destino'] = X.Cat
    tipo = X['Agrupación_CeCo'].astype(str).str.strip().map(lambda a: 'UdN' if a in UDN_AGR else ('Staff' if a.startswith('Staff') else 'Otro'))
    X['Nivel 3 destino'] = X.Cat
    c = X.Cat.eq('Consultorías')
    X.loc[c, 'Plantilla destino'] = 'Consultorías y Honorarios en la plantilla ' + tipo[c] + ' de la Agrupación'
    X.loc[c, 'Nivel 3 destino'] = tipo[c].map({'UdN': 'Consultorías de Negocio', 'Staff': 'Consultorías de Staff'}).fillna('Consultorías (agrupación sin carpeta)')
    X['Cambia vs base'] = X['Nivel 3 destino'].astype(str) != X.Nivel_3.astype(str)
    cols = ['Pais', 'Hoja origen', 'Nivel_3', 'Plantilla destino', 'Nivel 3 destino', 'Regla', 'Campo', 'Cambia vs base', 'Compañía',
            'Agrupación_CeCo', 'Nom_CeCo', 'Nom_Cta_Contable', 'Proveedor', 'Texto', 'Mes', 'Moneda', 'Monto ML', 'Monto PEN']
    R = X.groupby(['Hoja origen', 'Nivel_3', 'Nivel 3 destino', 'Regla']).agg(filas=('Monto ML', 'size'), monto_pen=('Monto PEN', 'sum')).reset_index()
    try:
        with pd.ExcelWriter(CLASIF_CH) as w:
            R.to_excel(w, sheet_name='Resumen', index=False)
            X[cols].rename(columns={'Nivel_3': 'Nivel 3 base'}).to_excel(w, sheet_name='Detalle', index=False)
    except PermissionError:
        print('   (no se pudo escribir la clasificación C&H: archivo abierto)')

def cargar_bases(TD=None):
    V = BASE + '02. Insumos/02. Bases consolidadas OyS-CS-Consultorías/'
    if not os.path.exists('base_oys.pkl'):
        f = lambda pat: sorted(glob.glob(V + pat))[-1]
        pd.read_excel(f('Base Consolidada Oficinas y Suministros*.xlsx'), sheet_name='BD Consolidada').to_pickle('base_oys.pkl')
        pd.read_excel(f('Base Consolidada CS Administrativo*.xlsx'), sheet_name='BD Consolidada').to_pickle('base_cs.pkl')
        pd.concat([pd.read_excel(f('Regional_Consultorias_y_Honorarios*.xlsx'), sheet_name=s) for s in CH_CAT]).to_pickle('base_ch.pkl')
    O = pd.read_pickle('base_oys.pkl'); S = pd.read_pickle('base_cs.pkl'); H = pd.read_pickle('base_ch.pkl').reset_index(drop=True)
    for B in (O, S, H): B['Monto ML'] = pd.to_numeric(B['Monto ML'], errors='coerce').fillna(0.0)
    # MONTOS DE LA TD con la clasificación de las bases (usuario, 2026-10-02): todo cuadra con la TD a la perfección
    import cuadre_td
    if TD is None: TD = cargar_td()
    TDx = pd.concat([TD, TD_INDIRECTO_BCP], ignore_index=False) if TD_INDIRECTO_BCP is not None else TD
    # OyS: base del usuario tal cual (diferencias de centavos y un ajuste DIST de USA aceptados). CS: base tal cual, sólo se
    # clasifican las filas 'sin clasificar'. C&H: montos y CeCo de la TD con la clasificación de la base (usuario, 2026-10-02).
    S, _ = cuadre_td.clasificar_cs_pendientes(S)
    H = cuadre_td.ch(TDx, H).reset_index(drop=True)
    # filas sin Moneda (p. ej. OyS Perú agosto): moneda local del país, para que no queden partidas en filas aparte
    MON = {'CHILE': 'CLP', 'COLOMBIA': 'COP', 'PERU': 'PEN', 'PANAMA': 'USD', 'USA': 'USD'}
    for B in (O, S, H):
        vacia = B.Moneda.isna() | B.Moneda.astype(object).astype(str).str.strip().isin(['', 'nan', 'None'])
        B['Moneda'] = B.Moneda.astype(object).where(~vacia, B.Pais.map(MON))
    O['Glosa_raw'] = [glosa_oys(p, fix(str(a)) if isinstance(a, str) else str(a), t) for p, a, t in zip(O.Plantilla, O.Nom_Cta_Contable, O.Texto)]
    O = _homol_base(O, 'Proveedor_Homologado', 'Glosa_raw')
    # 'Plantilla Ppto 2027 - CS Administrativo BCP.xlsx' -> BCP; 'Plantilla Ppto 2027 - CS Indirecto BCP.xlsx' -> Indirecto BCP
    S['Cat'] = S.Plantilla.astype(str).str.extract(r' - CS (?:Administrativo )?(.*?)\.xlsx')[0].fillna(S.Plantilla.astype(str))
    S['Glosa_raw'] = [servicio_cs(c, v, fix(str(a)) if isinstance(a, str) else str(a), t) for c, v, a, t in zip(S.Cat, S.Servicio_Homologado, S.Nom_Cta_Contable, S.Texto)]
    S = _homol_base(S, 'Proveedor_Homologado', 'Glosa_raw')
    H = H.rename(columns={'Nom - CeCo': 'Nom_CeCo'})
    # plantilla destino de cada fila mirando texto, proveedor y cuenta (no sólo la hoja / Nivel 3 de la base):
    # Asesorías Legales / Auditorías Tributarias y Financieras / Dietas / Consultorías (-> UdN / Staff por Agrupación)
    d = [destino_ch(n3, c, t, pr, pa) for n3, c, t, pr, pa in zip(H.Nivel_3, H.Nom_Cta_Contable, H.Texto, H.Proveedor, H.Pais)]
    H['Cat'] = [x[0] for x in d]; H['Regla'] = [x[1] for x in d]; H['Campo'] = [x[2] for x in d]
    # un mismo proveedor, una misma plantilla: las filas que ninguna regla decidió (quedaron por el Nivel 3 de la base) toman
    # la plantilla donde está la mayor parte de ese proveedor en el país (p. ej. EXACT: mesa de partes y fiscalización juntas)
    pv = H.Proveedor.astype(str).str.strip()
    conpv = ~pv.str.upper().isin(['', 'NAN', 'NONE', '0', 'N/A', 'NA'])
    decide = H.Regla.ne('Nivel 3 de la base') & conpv & H.Pais.eq('PERU')          # sólo Perú prioriza el proveedor
    if decide.any():
        mayor = H[decide].assign(_a=H['Monto ML'].abs(), _p=pv).groupby(['Pais', '_p', 'Cat'])._a.sum().reset_index().sort_values('_a', ascending=False).drop_duplicates(['Pais', '_p'])
        mapa = {(a, b): c for a, b, c in zip(mayor.Pais, mayor._p, mayor.Cat)}
        m = H.Regla.eq('Nivel 3 de la base') & conpv & H.Pais.eq('PERU')
        nuevo = [mapa.get((a, b)) for a, b in zip(H.Pais[m], pv[m])]
        cambia = [n is not None and n != c for n, c in zip(nuevo, H.Cat[m])]
        idx = H.index[m][cambia]
        H.loc[idx, 'Cat'] = [n for n, c in zip(nuevo, cambia) if c]; H.loc[idx, 'Regla'] = 'mismo proveedor (mayoría de sus filas)'; H.loc[idx, 'Campo'] = 'proveedor'
    exportar_clasificacion_ch(H)
    H['Glosa_raw'] = [glosa_ch(c, fix(str(a)) if isinstance(a, str) else str(a), t) for c, a, t in zip(H.Cat, H.Nom_Cta_Contable, H.Texto)]
    H = _homol_base(H, 'Proveedor', 'Glosa_raw')
    return O, S, H

def construir_todo(filtro=None):
    TD = cargar_td(); ctx = Ctx(extra_prov=TD.Proveedor)
    O, S, H = cargar_bases(TD)
    assert os.path.exists(DEST), DEST
    res = []
    for f in sorted(glob.glob(DEST + '**/*.xlsx', recursive=True)):
        rel = os.path.relpath(f, DEST)
        if ('Validación' in rel or 'Checklist' in rel) or '~$' in rel or 'versiones-previas' in rel or (filtro and not any(x in nfc(rel) for x in filtro.split('|'))): continue   # 'a|b': varias carpetas
        rubro, sub, pais = clasificar(rel)
        global CTX_PLANTILLA; CTX_PLANTILLA = nfc(rel)
        partes_ = []
        if rubro in ('OYS', 'CS', 'CH'):
            B = {'OYS': O, 'CS': S, 'CH': H}[rubro]
            for p in ([pais] if pais else ORDEN_PAIS):
                if rubro == 'OYS': partes_.append(lineas_oys(sub, p, B, ctx))
                elif rubro == 'CS': partes_.append(lineas_indirecto_bcp(p, B, ctx) if sub == 'Indirecto BCP' else lineas_cs(sub, p, B, ctx))
                else: partes_.append(lineas_ch(sub, p, B, ctx))
        elif rubro == 'ILP': partes_.append(lineas_ilp(pais, TD, ctx))
        else: partes_.append(lineas_td(rubro, sub, pais, TD, ctx, H))
        L = ordenar(normalizar_ceco(pd.concat([x for x in partes_ if len(x)], ignore_index=True)) if any(len(x) for x in partes_) else pd.DataFrame(columns=KEY + MESES), rubro)
        amarillo = None
        if rubro == 'UDN':
            n0 = len(REVISION_REL); pos = revisar_relacionadas(L, nfc(rel))
            amarillo = None    # versión para el compartido: nada pintado; los casos quedan en la hoja 'Revisión UdN (relacionadas)'
        info = escribir(f, f, a_letras(L), amarillo)
        if rubro == 'UDN':
            for d in REVISION_REL[n0:]:
                d['Fila relacionado'] = info['r0'] + 1 + list(L.index).index(d.pop('_i')); d['Fila posible real'] = info['r0'] + 1 + list(L.index).index(d.pop('_j'))
        for pos, r in L.iterrows():          # sustento: cada línea escrita con su fila Excel y sus movimientos de origen
            SUSTENTO_LINEAS.append({'Plantilla': nfc(rel), 'Rubro': rubro, 'Fila': info['r0'] + 1 + pos, **{c: r.get(c) for c in KEY},
                                    'Total ene–ago': float(sum(r[m] for m in MESES)), 'SRC': _lst(r.get('SRC'))})
        tot = {m: float(L[m].sum()) for m in MESES} if len(L) else {}
        res.append(dict(archivo=rel, rubro=rubro, sub=sub, pais=pais, **info, **{f'm{m}': tot.get(m, 0.0) for m in MESES}))
        print(f"{nfc(rel).split('/')[-1][:55]:55s} | filas {info['filas']:5d} | proveedores {info['proveedores']:4d} | Tablas {info['tablas']}", flush=True)
    pd.DataFrame(res).to_pickle('v2_resultado.pkl' if not filtro else 'v2_piloto.pkl')
    if REVISION_REL or not filtro: pd.DataFrame(REVISION_REL).to_pickle('revision_relacionadas.pkl')
    suf = '' if not filtro else '_piloto'
    pd.to_pickle(SUSTENTO_LINEAS, f'sustento_lineas{suf}.pkl'); pd.to_pickle(SUSTENTO_NETEO, f'sustento_neteo{suf}.pkl'); H.to_pickle(f'sustento_H{suf}.pkl')

if __name__ == '__main__':
    import sys
    construir_todo(sys.argv[1] if len(sys.argv) > 1 else None)
