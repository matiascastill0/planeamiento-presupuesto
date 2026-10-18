"""Fuente de CS Administrativo: la TD con los filtros oficiales (sin IPC) + INTERCOM_BCP (Indirecto BCP), CeCo real de la TD."""
import pandas as pd, numpy as np, re
from build_bd import fix
from homologacion import es_sin_proveedor
from cs_homolog import PROV_DEFECTO
MAPA_N3 = {'BCP': 'BCP', 'CCS': 'CCS', 'CCSF': 'CCSF', 'GRUPO CREDITO': 'GC', 'GC': 'GC', 'RESEARCH': 'Research', 'Research': 'Research', 'INDIRECTO BCP': 'Indirecto BCP'}
def _k(d, cols):
    return pd.Series(list(zip(*[d[c].astype(str).str.strip().str.upper() for c in cols])), index=d.index)

def asignar_categoria(b):
    """Categoría (BCP/CCS/CCSF/GC/Research/Indirecto BCP) de cada movimiento de la TD, tomada de la clasificación del
    TD (Nivel 3); si viene en blanco u 'Otros', la del compañero para ese mismo movimiento (misma compañía, cuenta, mes, texto y monto); si no se encuentra, por
    compañía+cuenta+texto, luego país+cuenta."""
    o = pd.read_pickle('cs_base.pkl'); o = o[o.Mes <= 7].copy()
    o['Cat'] = o.Plantilla.str.extract(r'CS (?:Administrativo )?(.*)\.xlsx')[0].fillna('CCS')
    o['Monto'] = o['Monto ML'].round(2).astype(str); o['Mes'] = o.Mes.astype(int).astype(str)
    b = b.copy(); b['Monto_r'] = b.Monto.round(2).astype(str); b['Mes_s'] = b.Mes.astype(str)
    o['Monto_r'] = o.Monto; o['Mes_s'] = o.Mes
    cat = b.Nivel_3.astype(str).str.strip().map(MAPA_N3).astype(object)   # manda la TD; el compañero sólo donde la TD viene en blanco/Otros
    for cols in (['Pais', 'Compañía', 'Cta_Contable', 'Mes_s', 'Texto', 'Monto_r'], ['Pais', 'Compañía', 'Cta_Contable', 'Texto'],
                 ['Pais', 'Compañía', 'Cta_Contable'], ['Pais', 'Cta_Contable']):
        ref = o.groupby(_k(o, cols)).Cat.agg(lambda s: s.value_counts().index[0])
        falta = cat.isna()
        cat[falta] = _k(b[falta], cols).map(ref)
    return cat.fillna('CCS')

def main():
    # Real 2026 desde la TD (mismos filtros que la plantilla y la validación): cuadre CeCo por CeCo
    df = pd.read_pickle('cache_full.pkl')
    from td_filter import VISTAS, NO_CONTABLES, sin_ipc
    for c in ['Pais', 'Datos', 'Vista', 'Nivel_1', 'Nivel_2', 'Compañía', 'Nivel_3']: df[c] = df[c].astype(str)
    m = (df.Datos == 'Real 2026') & (df.Nivel_2 == 'CS Administrativo') & df.Vista.isin(VISTAS) & ~df['Compañía'].isin(NO_CONTABLES) & sin_ipc(df)
    m &= ~df['Compañía'].str.contains('INTERCOM') | (df['Compañía'] == 'INTERCOM_BCP')
    b = df[m].copy()
    for c in b.columns:
        if isinstance(b[c].dtype, pd.CategoricalDtype): b[c] = b[c].astype(object)
    b['Mes'] = pd.to_numeric(b.Mes).astype(int); b = b[b.Mes <= 7].copy()
    b['Cat'] = asignar_categoria(b)
    for c in ['Nom_Cta_Contable', 'Texto', 'Nom_CeCo', 'Proveedor']: b[c] = b[c].map(fix)
    b['Nom_Cta_Contable'] = b.Nom_Cta_Contable.fillna('Contrato Soporte')
    b['Proveedor'] = [PROV_DEFECTO.get(c) if es_sin_proveedor(p) and c in PROV_DEFECTO else p for p, c in zip(b.Proveedor, b.Cat)]
    b['Nivel_3_final'] = b.Cat
    b.loc[(b.Pais == 'PANAMA') & b['Compañía'].isin(['Commision Paid', 'TRASLADOS']), 'Compañía'] = 'BNK'
    b.to_pickle('cs_fuente.pkl')
    # Ppto 2026 desde la TD
    m = (df.Datos == 'Ppto 2026') & sin_ipc(df) & (df.Nivel_2 == 'CS Administrativo') & df.Vista.isin(VISTAS) & ~df['Compañía'].isin(NO_CONTABLES)
    m &= ~df['Compañía'].str.contains('INTERCOM') | (df['Compañía'] == 'INTERCOM_BCP')
    P = df[m].copy()
    for c in P.columns:
        if isinstance(P[c].dtype, pd.CategoricalDtype): P[c] = P[c].astype(object)
    P['Cat'] = P.Nivel_3.map(MAPA_N3).fillna('CCS'); P['Nivel_3_final'] = P.Cat
    P.to_pickle('cs_ppto.pkl')
    print(b.groupby(['Cat', 'Pais']).Monto.agg(['sum', 'size']).round(0)); print(P.groupby(['Cat', 'Pais']).Monto.sum().round(0))
if __name__ == '__main__': main()
