"""BD de Oficinas y Suministros (Real y Ppto 2026), clasificada en BAU / NIIF / Seguros."""
import pandas as pd, re, unicodedata
from build_bd import fix
from td_filter import VISTAS, NO_CONTABLES, sin_ipc
acc_cat, acc_n3 = pd.read_pickle('oys_maps.pkl')          # criterio del compañero (por cuenta)
homo = pd.read_pickle('homo_oys.pkl'); homo_cat = dict(zip(homo.Cuenta, homo.Cat))
N3_NORM = {'alquiler oficina': 'Alquiler Oficina', 'gastos comunes': 'Gastos Comunes', 'útiles de oficina': 'Útiles de Oficina',
           'mantenimiento de oficina': 'Mantenimiento de Oficina', 'apertura y cierre de oficinas': 'Apertura y Cierre de Oficinas',
           'otros gastos de administración': 'Otros Gastos de Administración', 'seguros': 'Seguros', 'suministros': 'Útiles de Oficina'}

def n3(cta, n3td):
    if cta in acc_n3: return acc_n3[cta]
    k = str(n3td).strip().lower()
    return N3_NORM.get(k, 'Otros Gastos de Administración')

def categoria(cta, n3f):
    if n3f == 'Seguros': return 'Seguros'
    if cta in acc_cat: return acc_cat[cta]
    if homo_cat.get(cta) == 'NIIF': return 'NIIF'
    if homo_cat.get(cta) == 'Seguros': return 'Seguros'
    c = unicodedata.normalize('NFD', str(cta)).upper()
    if re.search(r'NIIF|DERECHO DE USO|GASTO FINANCIERO ARRENDAMIENTO|RIGHT OF USE|FINANCE LEASE', c): return 'NIIF'
    return 'BAU'

def main():
    df = pd.read_pickle('cache_full.pkl')
    for c in ['Pais', 'Datos', 'Vista', 'Nivel_1', 'Nivel_2', 'Compañía', 'Nivel_3']: df[c] = df[c].astype(str)
    m = ((df.Nivel_1 == '3 - Gastos Administrativos') & (df.Nivel_2 == 'Oficinas y Suministros') & df.Vista.isin(VISTAS)
         & ~df['Compañía'].str.contains('INTERCOM') & ~df['Compañía'].isin(NO_CONTABLES) & sin_ipc(df))
    X = df[m].copy()
    for c in ['Nom_Cta_Contable', 'Texto', 'Proveedor', 'Nom_CeCo', 'Nivel_3', 'Nivel_4']: X[c] = X[c].map(fix)
    X['Mes'] = pd.to_numeric(X['Mes'], errors='coerce').astype('Int64')
    X.loc[(X.Pais == 'PANAMA') & X['Compañía'].isin(['Commision Paid', 'TRASLADOS']), 'Compañía'] = 'BNK'
    X['Nivel_3_final'] = [n3(a, b) for a, b in zip(X.Nom_Cta_Contable, X.Nivel_3)]
    X['Cat'] = [categoria(a, b) for a, b in zip(X.Nom_Cta_Contable, X.Nivel_3_final)]
    R = X[X.Datos == 'Real 2026']; P = X[X.Datos == 'Ppto 2026']
    R.to_pickle('oys_real.pkl'); P.to_pickle('oys_ppto.pkl')
    print(R.groupby(['Cat', 'Pais']).Monto.agg(['sum', 'size']).round(0))
    print(P.groupby(['Cat', 'Pais']).Monto.agg(['sum', 'size']).round(0))
if __name__ == '__main__': main()
