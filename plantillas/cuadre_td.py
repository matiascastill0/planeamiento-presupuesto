"""Bases de OyS, CS Administrativo y Consultorías y Honorarios con MONTOS DE LA TD (usuario, 2026-10-02: todo debe cuadrar con
la TD a la perfección). Cada movimiento de la TD (filtros oficiales) busca su par en la base consolidada del usuario (país,
compañía, mes, cuenta, CeCo, texto y monto redondeado) y hereda su clasificación (plantilla, Nivel 3, proveedor homologado,
servicio, ajuste CENTRALIZADO/IMPUTADO en Chile). Lo que la base no trae se clasifica por reglas; lo que la base trae y la TD
no, queda fuera. Resultado: las plantillas suman exactamente la TD por país, compañía, CeCo y mes.
OyS: Chile = todas las filas OyS de la TD (el centralizado se comprime en el CeCo 309); resto de países = sin ajustes (sin DIST)."""
import re
import pandas as pd
from build_bd import fix

def _norm(s):
    return re.sub(r'\s+', ' ', fix(s) if isinstance(s, str) else '').strip().upper()

def _llave(df, monto):
    return pd.DataFrame({'Pais': df.Pais.astype(str).values, 'Comp': df['Compañía'].astype(str).values, 'Mes': df.Mes.astype(int).values,
                         'Cta': df.Nom_Cta_Contable.map(_norm).values, 'CeCo': df[('Nom_CeCo' if 'Nom_CeCo' in df else 'Nom - CeCo')].map(_norm).values,
                         'Txt': df.Texto.map(_norm).str[:150].values, 'M': df[monto].astype(float).round(0).values}, index=df.index)

def emparejar(T, B):
    """Índice de la fila de la base que corresponde a cada fila de la TD (o NaN). Emparejamiento uno a uno."""
    kt, kb = _llave(T, 'Monto'), _llave(B, 'Monto ML')
    cols = list(kt.columns)
    kt['n'] = kt.groupby(cols).cumcount(); kb['n'] = kb.groupby(cols).cumcount()
    m = kt.reset_index(names='it').merge(kb.reset_index(names='ib'), on=cols + ['n'], how='left')
    return pd.Series(m.ib.values, index=m.it.values)

def _base_desde_td(T, B, par, cols_base):
    """Filas de la TD con las columnas de la base: clasificación de la base donde hay par, montos y datos de la TD siempre."""
    X = pd.DataFrame(index=T.index)
    for c in cols_base:
        X[c] = B[c].reindex(par.values).values if c in B else None
    for c in ['Pais', 'Compañía', 'Agrupación_CeCo', 'Nom_Cta_Contable', 'Cta_Contable', 'Texto', 'Factura', 'Fecha', 'Vista', 'Moneda', 'Nivel_1', 'Nivel_2']:
        if c in T: X[c] = T[c].values
    X['Nom_CeCo'] = T.Nom_CeCo.values; X['CeCo'] = T.CeCo.astype(str).values
    X['Mes'] = T.Mes.astype(int).values; X['Monto ML'] = T.Monto.astype(float).values
    X['Monto PEN'] = pd.to_numeric(T.get('Monto_PEN_Oficial'), errors='coerce').values if 'Monto_PEN_Oficial' in T else None
    X['TD_idx'] = T.index.values
    X['Con_par_base'] = par.notna().values
    X['Nivel_3_TD'] = T.Nivel_3.astype(str).values; X['Proveedor_TD'] = T.Proveedor.values
    return X

def oys(TD, O):
    from oys_bd import n3 as oys_n3, categoria as oys_cat
    t = TD[TD.Nivel_2.astype(str) == 'Oficinas y Suministros']
    aj = t.Ajuste.astype(str).str.upper()
    T = t[(t.Pais == 'CHILE') | ~aj.str.contains('DIST')]
    par = emparejar(T, O)
    X = _base_desde_td(T, O, par, list(O.columns))
    sin = ~X.Con_par_base
    cta = T.Nom_Cta_Contable.map(lambda v: fix(v) if isinstance(v, str) else v)
    n3 = [oys_n3(a, b) for a, b in zip(cta, T.Nivel_3)]
    X.loc[sin, 'Nivel_3'] = [n for n, s in zip(n3, sin) if s]
    X.loc[sin, 'Plantilla'] = [oys_cat(a, n) for a, n, s in zip(cta, n3, sin) if s]
    X.loc[sin, 'Proveedor_Homologado'] = X.loc[sin, 'Proveedor_TD']; X.loc[sin, 'Proveedor'] = X.loc[sin, 'Proveedor_TD']
    taj = T.Ajuste.astype(str).str.upper().str.strip().values
    X.loc[sin & (X.Pais == 'CHILE'), 'Ajuste'] = ['IMPUTADO' if a == 'IMPUTADO' else 'CENTRALIZADO' for a, s, p in zip(taj, sin, X.Pais) if s and p == 'CHILE']
    X.loc[X.Pais != 'CHILE', 'Sin_Ajuste'] = True
    return X

def cs(TD, S):
    from cs_source import MAPA_N3
    t = TD[TD.Nivel_2.astype(str) == 'CS Administrativo']
    comp = t['Compañía'].astype(str)
    T = t[~comp.str.contains('INTERCOM') | (comp.eq('INTERCOM_BCP') & t.Nivel_3.astype(str).str.upper().eq('INDIRECTO BCP'))]
    par = emparejar(T, S)
    X = _base_desde_td(T, S, par, list(S.columns))
    sin = ~X.Con_par_base | X.Plantilla.astype(str).str.contains('sin clasificar', case=False)   # sin par o sin categoría en la base
    if sin.any():
        cat = T.loc[sin, 'Nivel_3'].astype(str).str.strip().map(MAPA_N3).astype(object)
        S2 = S.assign(_cat=S.Plantilla.astype(str).str.extract(r' - CS (?:Administrativo )?(.*?)\.xlsx')[0])
        for cols in (['Pais', 'Compañía', 'Nom_Cta_Contable'], ['Pais', 'Compañía'], ['Pais']):
            ref = S2.dropna(subset=['_cat']).groupby(cols)._cat.agg(lambda s: s.value_counts().index[0])
            falta = cat.isna()
            if falta.any():
                cat[falta] = [ref.get(tuple(r) if len(cols) > 1 else r[0]) for r in T.loc[sin].loc[falta, cols].astype(str).values]
        cat = cat.fillna('CCS')
        cat[T.loc[sin, 'Compañía'].astype(str).eq('INTERCOM_BCP')] = 'Indirecto BCP'
        X.loc[sin, 'Plantilla'] = ['Plantilla Ppto 2027 - CS ' + ('Indirecto BCP' if c == 'Indirecto BCP' else f'Administrativo {c}') + '.xlsx' for c in cat]
        X.loc[sin, 'Proveedor_Homologado'] = X.loc[sin, 'Proveedor_TD']; X.loc[sin, 'Proveedor'] = X.loc[sin, 'Proveedor_TD']
        X.loc[sin, 'Nivel_3'] = X.loc[sin, 'Nivel_3_TD']
    return X

def ch(TD, H):
    t = TD[TD.Nivel_2.astype(str) == 'Consultorías y Honorarios']
    par = emparejar(t, H)
    X = _base_desde_td(t, H, par, list(H.columns))
    X['Nom - CeCo'] = X.Nom_CeCo; X = X.drop(columns=['Nom_CeCo'])          # cargar_bases renombra 'Nom - CeCo' -> 'Nom_CeCo'
    sin = ~X.Con_par_base
    n3 = X.loc[sin, 'Nivel_3_TD']
    X.loc[sin, 'Nivel_3'] = n3
    X.loc[sin, 'Plantilla'] = ['AsesoriasLegales_V1y3' if str(v).startswith('Asesorías Legales') else ('Dietas_V1y3' if v == 'Dietas' else 'Auditorias_V1y3') for v in n3]
    X.loc[sin, 'Proveedor'] = X.loc[sin, 'Proveedor_TD']
    return X

def clasificar_cs_pendientes(S):
    """CS Administrativo (usuario, 2026-10-02): la base queda TAL CUAL; sólo las filas marcadas 'sin clasificar' reciben su
    categoría: Nivel 3 de la fila si es una categoría conocida; si no, la categoría más frecuente de la base para la misma
    compañía + cuenta, luego compañía, luego país."""
    from cs_source import MAPA_N3
    S = S.copy()
    pend = S.Plantilla.astype(str).str.contains('sin clasificar', case=False)
    if not pend.any(): return S, pend
    cat = S.loc[pend, 'Nivel_3'].astype(str).str.strip().map(MAPA_N3).astype(object)
    ok = S[~pend].assign(_cat=S.loc[~pend, 'Plantilla'].astype(str).str.extract(r' - CS (?:Administrativo )?(.*?)\.xlsx')[0]).dropna(subset=['_cat'])
    for cols in (['Pais', 'Compañía', 'Nom_CeCo', 'Nom_Cta_Contable'], ['Pais', 'Compañía', 'Nom_CeCo'], ['Pais', 'Compañía', 'Nom_Cta_Contable'], ['Pais', 'Compañía'], ['Pais']):
        ref = ok.astype({c: str for c in cols}).groupby(cols)._cat.agg(lambda s: s.value_counts().index[0])
        falta = cat.isna()
        if falta.any():
            cat[falta] = [ref.get(tuple(r) if len(cols) > 1 else r[0]) for r in S.loc[pend].loc[falta, cols].astype(str).values]
    cat = cat.fillna('CCS')
    # movimiento y su reverso (mismo país, compañía, CeCo y mes) van a la misma plantilla: la de la fila de mayor monto
    P_ = S.loc[pend].assign(_cat=cat.values, _a=S.loc[pend, 'Monto ML'].abs())
    g = ['Pais', 'Compañía', 'Nom_CeCo', 'Mes']
    mayor = P_.sort_values('_a', ascending=False).drop_duplicates(g).set_index(g)._cat
    cat = pd.Series([mayor.get(tuple(r)) for r in P_[g].values], index=P_.index)
    S.loc[pend, 'Plantilla'] = ['Plantilla Ppto 2027 - CS ' + ('Indirecto BCP' if c == 'Indirecto BCP' else f'Administrativo {c}') + '.xlsx' for c in cat]
    S['Clasificado_por_regla'] = pend
    return S, pend
