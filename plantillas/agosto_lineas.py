import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""Genera las líneas (llave de plantilla + Mes + Monto) de un rubro/unidad/país con los MISMOS generadores de ene–jul.
Sirve para ene–jul (calibración contra la TD) y para agosto (cierres)."""
import pandas as pd, numpy as np, openpyxl, re
from td_filter import td
from homologacion import Homologador
from build_bd import fix
from agregar import preparar, CUENTAS_CLIENTE
from compactar import compactar, agrupar_amplios
from build_plantillas import TEMPLATE, ceco_norm
from ogp_homolog import glosa_ogp, proveedor_ogp
from tyc_homolog import glosa_tyc, proveedor_tyc
from dya_homolog import glosa_dya, proveedor_dya
from iyc_homolog import glosa_iyc, proveedor_iyc
from rem_homolog import glosa_rem, proveedor_rem
from mkt_homolog import glosa_mkt, proveedor_mkt
from oys_homolog import glosa_oys, sede
from cs_homolog import glosa_cs, PROV_DEFECTO
from homologacion import es_sin_proveedor
from oys_bd import n3 as oys_n3, categoria as oys_cat
import cs_source

PAIS_TXT = {'CHILE': 'Chile', 'COLOMBIA': 'Colombia', 'PERU': 'Perú', 'PANAMA': 'Panamá', 'USA': 'USA', 'MEXICO': 'México'}
REM = ['Remuneración Fija', 'Incentivo Corto Plazo', 'Remuneración Variable']
# Gastos Administrativos sin plantilla propia en la ruta: van a 'Otros Gastos Administrativos <país>'
OTROS_GA = ['Donaciones', 'Consultorías']
N1 = {'TYC': '4 - Tecnología y Comunicaciones', 'DYA': '5 - Depreciación y Amortización', 'IYC': '6 - Impuestos y Contribuciones'}
FN = {'OGP': (glosa_ogp, proveedor_ogp), 'CAP': (glosa_ogp, proveedor_ogp), 'TYC': (glosa_tyc, proveedor_tyc), 'DYA': (glosa_dya, proveedor_dya), 'IYC': (glosa_iyc, proveedor_iyc), 'REM': (glosa_rem, proveedor_rem), 'MKT': (glosa_mkt, proveedor_mkt)}
KEY = ['País', 'Vehículo', 'Ceco - Nombre', 'Sede', 'Nom Cta Contable', 'Nivel 1', 'Nivel 2', 'Nivel 3', 'Proveedor', 'Glosa / Texto', 'Moneda']

MAESTRO_CECOS = RAIZ + '02. Insumos/06. Maestros/CeCos homologación completa.csv'
def cecos_maestro():
    """{código: nombre} del maestro oficial de CeCos (en el orden del archivo)."""
    M = pd.read_csv(MAESTRO_CECOS, sep=';', dtype=str)
    return dict(zip(M.CeCo.str.strip(), M.Nombre.str.strip()))

class Ctx:
    def __init__(self, extra_prov=None):
        t = openpyxl.load_workbook(TEMPLATE, read_only=True)['Tablas']
        self.tablas_ceco = {str(a): f'{a} - {b}' for a, b in t.iter_rows(min_row=1, max_row=159, min_col=8, max_col=9, values_only=True) if a is not None}
        # maestro oficial de CeCos (lista completa entregada por el usuario, 2026-10-01): manda sobre la hoja Tablas de la plantilla base
        self.tablas_ceco.update({c: f'{c} - {n}' for c, n in cecos_maestro().items()})
        C = pd.read_pickle('cache_full.pkl')[['CeCo', 'Nom_CeCo', 'Pais']].astype(str); C = C[~C.CeCo.isin(['nan', 'None', '', '0'])].drop_duplicates()
        C['c'] = C.CeCo.map(ceco_norm); C['Nom_CeCo'] = C.Nom_CeCo.str.strip()
        self.nombre_ceco = {p: g.groupby('Nom_CeCo').c.agg(lambda s: s.value_counts().index[0]).to_dict() for p, g in C.groupby('Pais')}
        prov = pd.read_pickle('bd_real.pkl').Proveedor.astype(object)
        if extra_prov is not None: prov = pd.concat([prov, extra_prov.astype(object)])
        self.homol = Homologador(prov.value_counts().to_dict(), pd.read_pickle('mapa_prov.pkl'))
        self.homol_vacio = Homologador({}, {})

def texto_limpio(t):
    """Servicio descrito en el texto de la TD, sin códigos de documento ni notas de sistema: 'F001-8370 - MYPE - CINTA PARA
    FOTOCHE CK {04-02-2026 Facturas de compra}' -> 'Cinta para fotoche ck'."""
    s = re.sub(r'\{.*?\}', ' ', str(t or ''))
    s = re.sub(r'\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b', ' ', s)            # fechas
    s = re.sub(r'\b\S*\d\S*\b', ' ', s)                                   # palabras con números (n° de doc, acta, op.)
    s = re.sub(r'\b(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SETIEMBRE|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE|A[NÑ]OS?)\b', ' ', s, flags=re.I)
    s = re.sub(r'\b(?:[A-Z]{1,2}\d{3}-\d+|PR[A-Z]*\d+|PRT\d+|\d{6,})\b', ' ', s)
    s = re.sub(r'\b(?:ANULADA|ANULADO|MYPE|REVIERTE.*$)\b', ' ', s, flags=re.I)
    s = re.sub(r'\s*-\s*-+\s*|^\s*[-:]+\s*|\s*[-:]+\s*$', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip(' -:')
    s = (s[:1].upper() + s[1:].lower()) if s else ''
    return s if len(s) <= 80 else s[:80].rsplit(' ', 1)[0]

GENERICAS_TXT = re.compile(r'\b(PROVISI\w*|EXTORN\w*|AJUST\w*|REVERS\w*|REGULARIZ\w*|GASTOS?|EJERCICIOS?|ANTERIOR\w*|ANOS?|PERIODOS?|'
                           r'ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SETIEMBRE|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE|'
                           r'ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SET|SEP|OCT|NOV|DIC|DE|DEL|LA|EL|LOS|LAS|POR|PARA|Y|EN|A|AL|SOLES|USD|PEN|'
                           r'CCSF|CCB|CCF|CCP|CCT|MANUAL|SAF|FACTURAS?|COMPRA|SALDO|MES|\d+)\b')
def texto_con_detalle(t):
    """True si el texto de la TD describe un servicio (no sólo 'provisión / extorno / ajuste + mes + año')."""
    from homologacion import sin_acentos
    s = GENERICAS_TXT.sub(' ', sin_acentos(texto_limpio(t)).upper())
    return len([w for w in re.findall(r'[A-Z]{3,}', s)]) >= 2

COMITES = [(re.compile(r'COMIT[EÉ]\s*(DE\s*)?INVERSI|COMIT[EÉ]\s*DEINVERSI|ASESOR COMITE INVERSIONES|\bCDI\b'), 'Comités de inversiones'),
           (re.compile(r'COMIT[EÉ]\s*(DE\s*)?CR[EÉ]DITO'), 'Comités de crédito'),
           (re.compile(r'COMIT[EÉ]\s*(DE\s*)?RIESGO'), 'Comités de riesgo'),
           (re.compile(r'COMIT[EÉ]\s*(DE\s*)?DERECHOS'), 'Comités de derechos económicos')]
def glosa_comites(X):
    """UdN / Staff (2026-10-01): texto 'Comité de inversi...' -> servicio 'Comités de inversiones' (ídem crédito, riesgo,
    derechos económicos), en vez de la glosa de la cuenta."""
    from homologacion import sin_acentos
    t = (X.Texto.astype(object).fillna('').astype(str) + ' | ' + X.Nom_Cta_Contable.astype(object).fillna('').astype(str)).map(lambda v: sin_acentos(str(v)).upper())
    X = X.copy()
    for rx, g in COMITES:
        X.loc[t.str.contains(rx) & ~X.Glosa.astype(str).str.startswith('Comités'), 'Glosa'] = g
    return X

R_EMPRESA = re.compile(r'\b(S\.?\s?A\.?C?\.?|S\.?A\.?S|SAC|SAA|S\.?R\.?L|E\.?I\.?R\.?L|LTDA?|LIMITED|LLC|INC|CORP\w*|CO\b|COMPA[NÑ]IA|BANCO|BANK|'
                       r'GROUP|GRUPO|HOLDINGS?|FONDO|ASOCIACION|SOCIEDAD|SPA|S\.?L\.?|PLC|GMBH|AG|NV|BV|MSCI|BLOOMBERG|REFINITIV|MOODY|STANDARD|CITI\w*|'
                       r'MORGAN|CAPITAL|SERVICIOS|SOLUCIONES|CONSULTOR\w*|ESTUDIO|AGENCIA|HOTEL\w*|RESTAURANT\w*|AIR\w*|AEROL\w*|LATAM|SAB|SAFI|AFP)\b')
def es_empresa(nombre):
    """True si el proveedor es una empresa (forma societaria, banco, marca conocida); False si parece persona natural."""
    from homologacion import sin_acentos
    n = sin_acentos(str(nombre or '')).upper().strip()
    if not n or n == '(SIN PROVEEDOR)': return False
    if R_EMPRESA.search(n) or re.search(r'\d', n): return True
    return not (2 <= len(re.findall(r'[A-Z]{2,}', n)) <= 6)

CONCEPTOS_TXT = [(r'TARJETA|\bTC\b|T\.C\.|TCCORPORATIVA|CORPORATE CARD|VISA|MASTERCARD|AMEX', 'Tarjeta corporativa (consumos)'),
                 (r'REEMBOLSO|REINTEGRO|RENDICION', 'Reembolso de gastos'),
                 (r'VIATICO|PER DIEM|MANUTENCION', 'Viáticos'),
                 (r'HOTEL|ALOJAMIENTO|HOSPEDAJE|AIRBNB|MARRIOTT|HILTON|HYATT|SHERATON', 'Alojamiento'),
                 (r'PASAJE|VUELO|AEREO|BOLETO|LATAM|AVIANCA|AMERICAN AIR|SKY AIRLINE|COPA AIR|TICKET', 'Pasajes aéreos'),
                 (r'TAXI|UBER|CABIFY|MOVILIDAD|TRASLADO|ESTACIONAMIENTO|PEAJE|COMBUSTIBLE', 'Movilidad y traslados'),
                 (r'RESTAURANT|ALMUERZO|CENA|DESAYUNO|COMIDA|CONSUMO|CAFETERIA|CATERING|BAR\b|COFFEE|STARBUCKS', 'Comidas y atenciones'),
                 (r'MULTA|SANCION|INTERES(ES)? MORATORIO|MORA\b|RECARGO', 'Multas e intereses'),
                 (r'SUSCRIPCION|SUBSCRIPTION|MEMBRESIA|MEMBERSHIP', 'Suscripciones'),
                 (r'LICENCIA|LICENSE|SOFTWARE', 'Licencias'),
                 (r'REGALO|OBSEQUIO|GIFT|ARREGLO FLORAL|FLORES|CANASTA', 'Obsequios y presentes'),
                 (r'EVENTO|CELEBRACION|ANIVERSARIO|FIESTA', 'Eventos')]
CONCEPTOS_TXT = [(re.compile(r), g) for r, g in CONCEPTOS_TXT]
GLOSAS_GENERICAS = ('Gastos no deducibles', 'Ajustes de ejercicios anteriores')
def glosa_genericas_por_texto(X):
    """UdN / Staff: si la glosa sólo repite la cuenta ('Gastos no deducibles', 'Ajustes de ejercicios anteriores'), se toma el
    concepto del texto de la TD (tarjeta corporativa, reembolso, viáticos, alojamiento, comidas...) o, si no calza ninguno y el
    texto describe un servicio, ese texto limpio."""
    from homologacion import sin_acentos
    m = X.Glosa.astype(str).isin(GLOSAS_GENERICAS)
    if not m.any(): return X
    X = X.copy()
    def nueva(t, g):
        u = sin_acentos(str(t or '')).upper()
        for rx, c in CONCEPTOS_TXT:
            if rx.search(u): return c if g == 'Gastos no deducibles' else f'{c} (ejercicios anteriores)'
        if texto_con_detalle(t): return texto_limpio(t)
        return g
    X.loc[m, 'Glosa'] = [nueva(t, g) for t, g in zip(X.loc[m, 'Texto'], X.loc[m, 'Glosa'])]
    return X

def glosa_detalle_grupo(X):
    """UdN / Staff (usuario, 2026-10-02): si la glosa sólo repite la cuenta contable, se da más detalle al usuario sin crear filas:
    por grupo compañía + CeCo + proveedor + cuenta + Nivel 2, la glosa pasa a ser el concepto (o el servicio descrito) del texto
    original de la TD del movimiento de mayor monto del grupo. Si ningún texto del grupo describe algo, queda la de la cuenta."""
    from homologacion import sin_acentos
    tok = lambda v: set(re.findall(r'[A-Z]{3,}', sin_acentos(str(v)).upper())) - {'DEL', 'LAS', 'LOS', 'POR', 'PARA'}
    rep = [len(tok(g)) > 0 and tok(g) <= tok(c) for g, c in zip(X.Glosa, X.Nom_Cta_Contable)]
    rep = pd.Series(rep, index=X.index)
    if not rep.any(): return X
    X = X.copy()
    def cand(t):
        u = sin_acentos(str(t or '')).upper()
        for rx, c in CONCEPTOS_TXT:
            if rx.search(u): return c
        return texto_limpio(t) if texto_con_detalle(t) else None
    k = ['Compañía', 'Ceco - Nombre', 'Proveedor_H', 'Nom_Cta_Contable', 'Nivel_2']
    llave = X[k].astype(object).fillna('').astype(str).agg('|'.join, axis=1)
    Y = X[rep].assign(_c=[cand(t) for t in X.loc[rep, 'Texto']], _a=X.loc[rep, 'Monto'].abs(), _k=llave[rep])
    Y = Y[Y._c.notna()]
    if not len(Y): return X
    mejor = Y.sort_values('_a', ascending=False).drop_duplicates('_k').set_index('_k')._c
    nuevo = [mejor.get(v) for v in llave[rep]]
    X.loc[rep, 'Glosa'] = [n if n else g for n, g in zip(nuevo, X.loc[rep, 'Glosa'])]
    return X

def glosa_ajustes_por_texto(X, n2col='Nivel_2'):
    """Proveedor con nombre cuyo único concepto en el grupo (compañía, CeCo, proveedor, Nivel 2) son ajustes de ejercicios
    anteriores: la glosa sale del texto original de la TD (el servicio real), no de la cuenta de ajuste."""
    from homologacion import es_sin_proveedor
    named = ~X.Proveedor_H.map(lambda p: es_sin_proveedor(p) or str(p) == '(sin proveedor)')
    aj = X.Glosa.astype(str).str.contains('ejercicios anteriores', case=False) | X.Nom_Cta_Contable.astype(str).str.upper().str.contains('EJERCICIOS ANTERIORES|EXTORNO|PROVISIONES DE GASTOS')
    k = ['Compañía', 'Ceco - Nombre', 'Proveedor_H', n2col]
    solo_aj = X.assign(_aj=aj).groupby(k, dropna=False)._aj.transform('all')
    m = named & aj & solo_aj
    if m.any():
        X = X.copy()
        X['_abs'] = X.Monto.abs(); X['_tl'] = X.Texto.map(texto_limpio)
        con_det = X.Texto.map(texto_con_detalle)
        mejor = X[m & X._tl.ne('') & con_det].sort_values('_abs', ascending=False).drop_duplicates(k).set_index(k)._tl
        idx = pd.MultiIndex.from_frame(X.loc[m, k])
        nuevo = [mejor.get(tuple(r)) for r in idx]
        X.loc[m, 'Glosa'] = [n if n else g for n, g in zip(nuevo, X.loc[m, 'Glosa'])]
        X = X.drop(columns=['_abs', '_tl'])
    return X

def _objetos(X):
    X = X.copy()
    for c in X.columns:
        if isinstance(X[c].dtype, pd.CategoricalDtype): X[c] = X[c].astype(object)
    return X

def _ceco(X, ctx, pais):
    X['CeCo_txt'] = X.CeCo.map(ceco_norm)
    falt = X.CeCo_txt.isin(['nan', 'None', '', '0'])
    nc = {str(n).strip().upper(): c for n, c in ctx.nombre_ceco.get(pais, {}).items()}
    X.loc[falt, 'CeCo_txt'] = [nc.get(str(n).strip().upper(), '') for n in X.loc[falt, 'Nom_CeCo']]
    X['Ceco - Nombre'] = [ctx.tablas_ceco.get(c) or (f'{c} - {n}' if c else str(n)) for c, n in zip(X.CeCo_txt, X.Nom_CeCo)]
    X['Nivel 1'] = X.Nivel_1.astype(str).str.replace(r'^\d+ - ', '', regex=True)
    return X

def _agrupar(X, k, pais, extra):
    for c in k:
        if X[c].isna().any(): X[c] = X[c].fillna('(sin dato)')
    if 'SRC' in X:      # sustento: movimientos de origen de cada línea
        L = X.groupby(k + ['Mes'], dropna=False, observed=True).agg(Monto=('Monto', 'sum'), SRC=('SRC', list)).reset_index()
    else:
        L = X.groupby(k + ['Mes'], dropna=False, observed=True).Monto.sum().reset_index()
    L = L.rename(columns={'Compañía': 'Vehículo', 'Nom_Cta_Contable': 'Nom Cta Contable', 'Nivel_2': 'Nivel 2', 'Proveedor_H': 'Proveedor', 'Glosa': 'Glosa / Texto', 'Nivel_3_final': 'Nivel 3'})
    if 'Sede' in L: L['Sede'] = L.Sede.replace({'': None, '(sin dato)': None})
    L['País'] = PAIS_TXT[pais]
    for c, v in extra.items(): L[c] = v
    for c in KEY:
        if c not in L: L[c] = None
    return L[KEY + ['Mes', 'Monto'] + (['SRC'] if 'SRC' in L else [])]

def filtrar(rubro, sub, pais, A, sin_ajustes_oys=True):
    """Filas (de la TD o del cierre, esquema cache) que caen en la plantilla, con los filtros de ene–jul."""
    A = A[A.Pais.astype(str) == pais]
    if rubro in ('STAFF', 'UDN'): return td(A, sub, 'Real 2026', pais)
    n1, n2 = A.Nivel_1.astype(str), A.Nivel_2.astype(str)
    if rubro == 'OGP': return A[(n1 == '2 - Gastos del Personal') & (n2.str.startswith('OGP') | (n2 == 'Capacitaciones'))]   # Capacitaciones va dentro de OGP
    if rubro == 'REM': return A[(n1 == '2 - Gastos del Personal') & n2.isin(REM)]
    if rubro == 'OGA': return A[(n1 == '3 - Gastos Administrativos') & n2.isin(OTROS_GA)]
    if rubro in N1: return A[n1 == N1[rubro]]
    if rubro == 'MKT': return A[(n1 == '3 - Gastos Administrativos') & (n2 == 'Marketing')]
    if rubro == 'CS':
        X = _objetos(A[n2 == 'CS Administrativo'])
        if not len(X): return X
        X['Cat'] = cs_source.asignar_categoria(X.assign(Nivel_3=X.Nivel_3.astype(str), Mes=X.Mes.astype(int)))
        return X[X.Cat == sub]
    if rubro == 'OYS':
        m = n2 == 'Oficinas y Suministros'
        if sin_ajustes_oys: m &= A.Ajuste.isna() | A.Ajuste.astype(str).isin(['(blank)', 'nan', 'None', ''])
        X = _objetos(A[m])
        if not len(X): return X
        cta = X.Nom_Cta_Contable.map(lambda v: fix(v) if isinstance(v, str) else v)
        X['Nivel_3_final'] = [oys_n3(a, b) for a, b in zip(cta, X.Nivel_3)]
        X['Cat'] = [oys_cat(a, b) for a, b in zip(cta, X.Nivel_3_final)]
        return X[X.Cat == sub]
    raise ValueError(rubro)

def lineas(rubro, sub, pais, R, ctx, compacto=False):
    """compacto=False: detalle fino (sin compactar), para que el encaje siga la granularidad propia de cada plantilla."""
    X = _objetos(R)
    if not len(X): return pd.DataFrame(columns=KEY + ['Mes', 'Monto'])
    for c in ['Nom_Cta_Contable', 'Texto', 'Proveedor', 'Nom_CeCo']:
        X[c] = X[c].map(lambda v: fix(v) if isinstance(v, str) else v)
    X['Mes'] = X.Mes.astype(int)
    if rubro in ('STAFF', 'UDN', 'OGA'):
        X = preparar(X, ctx.homol); X = _ceco(X, ctx, pais)
        X = glosa_comites(X)
        X = glosa_ajustes_por_texto(X)
        X = glosa_genericas_por_texto(X)
        X = glosa_detalle_grupo(X)
        k = ['Compañía', 'Ceco - Nombre', 'Nom_Cta_Contable', 'Nivel 1', 'Nivel_2', 'Proveedor_H', 'Glosa', 'Moneda']
        if compacto: X = agrupar_amplios(X, k, CUENTAS_CLIENTE)
        return _agrupar(X, k, pais, {})
    if rubro in FN:
        gf, pf = FN[rubro]
        if rubro == 'REM': X['Nom_Cta_Contable'] = X.Nom_Cta_Contable.fillna('(vacío)')
        homol = ctx.homol_vacio if rubro == 'REM' else ctx.homol
        X['Glosa'] = [gf(c, t) for c, t in zip(X.Nom_Cta_Contable, X.Texto)]
        X['Proveedor_H'] = [pf(homol, p, t, c, g) for p, t, c, g in zip(X.Proveedor, X.Texto, X.Nom_Cta_Contable, X.Glosa)]
        X = _ceco(X, ctx, pais)
        k = ['Compañía', 'Ceco - Nombre', 'Nom_Cta_Contable', 'Nivel 1', 'Nivel_2', 'Proveedor_H', 'Glosa', 'Moneda']
        if compacto: X = compactar(X, k)
        return _agrupar(X, k, pais, {})
    if rubro in ('OYS', 'CS'):
        if rubro == 'OYS':
            if 'Cat' not in X:
                X['Nivel_3_final'] = [oys_n3(a, b) for a, b in zip(X.Nom_Cta_Contable, X.Nivel_3)]
                X['Cat'] = [oys_cat(a, b) for a, b in zip(X.Nom_Cta_Contable, X.Nivel_3_final)]
                X = X[X.Cat == sub]
            X['Proveedor_H'] = [ctx.homol.nombre(p, t) for p, t in zip(X.Proveedor, X.Texto)]
            X['Glosa'] = [glosa_oys(sub, c, t) for c, t in zip(X.Nom_Cta_Contable, X.Texto)]
            X['Sede'] = [sede(t, c) for t, c in zip(X.Texto, X.Nom_Cta_Contable)]
        else:
            if 'Cat' not in X:
                X['Cat'] = cs_source.asignar_categoria(X.assign(Nivel_3=X.Nivel_3.astype(str)))
                X = X[X.Cat == sub]
            X['Nom_Cta_Contable'] = X.Nom_Cta_Contable.fillna('Contrato Soporte')
            X['Proveedor'] = [PROV_DEFECTO.get(c) if es_sin_proveedor(p) and c in PROV_DEFECTO else p for p, c in zip(X.Proveedor, X.Cat)]
            X['Nivel_3_final'] = X.Cat
            X['Proveedor_H'] = [ctx.homol.nombre(p, t) for p, t in zip(X.Proveedor, X.Texto)]
            X['Glosa'] = [glosa_cs(sub, c, t) for c, t in zip(X.Nom_Cta_Contable, X.Texto)]
            X['Sede'] = None
        if not len(X): return pd.DataFrame(columns=KEY + ['Mes', 'Monto'])
        X = _ceco(X, ctx, pais); X['Sede'] = X.Sede.fillna('')
        k = ['Pais', 'Compañía', 'Ceco - Nombre', 'Sede', 'Nom_Cta_Contable', 'Nivel 1', 'Nivel_2', 'Nivel_3_final', 'Proveedor_H', 'Glosa', 'Moneda']
        if compacto: X = compactar(X, k)
        return _agrupar(X, [c for c in k if c != 'Pais'], pais, {})
    raise ValueError(rubro)
