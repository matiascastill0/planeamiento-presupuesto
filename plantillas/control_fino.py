import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""1) Rubros 'sin ajustes': plantilla vs TD sin IPC con/sin filtro de ajustes (lo que verá el usuario en su TD).
2) Cuadre fino por País x Vehículo x CeCo x Mes contra la TD (rubros que salen de la TD)."""
import pandas as pd, glob
from td_filter import VISTAS, NO_CONTABLES, sin_ipc, ajustes_ignorables
from build_plantillas import ceco_norm
ROOT = RAIZ + 'salida/'
M = ['Ene-26', 'Feb-26', 'Mar-26', 'Abr-26', 'May-26', 'Jun-26', 'Jul-26']
PT = {'Chile': 'CHILE', 'Colombia': 'COLOMBIA', 'Perú': 'PERU', 'Panamá': 'PANAMA', 'USA': 'USA', 'México': 'MEXICO'}
df = pd.read_pickle('cache_full.pkl')
for c in ['Pais', 'Datos', 'Vista', 'Nivel_1', 'Nivel_2', 'Compañía', 'Ajuste']: df[c] = df[c].astype(str)
df = df[df.Datos == 'Real 2026'].assign(Mes=lambda x: x.Mes.astype(int)); df = df[df.Mes <= 7]
ign = ajustes_ignorables(df, 'AJUS?TE'); aj = df.Ajuste.str.upper().str.contains('AJUS?TE')
base = df.Vista.isin(VISTAS) & ~df['Compañía'].isin(NO_CONTABLES) & ~df['Compañía'].str.contains('INTERCOM') & sin_ipc(df)
df.loc[(df.Pais == 'PANAMA') & df['Compañía'].isin(['Commision Paid', 'TRASLADOS']), 'Compañía'] = 'BNK'
df['c3'] = df.CeCo.map(ceco_norm)
REM = ['Remuneración Fija', 'Incentivo Corto Plazo', 'Remuneración Variable']
R = {'Tecnología y Comunicaciones': (base & (df.Nivel_1 == '4 - Tecnología y Comunicaciones'), True),
     'Depreciación y Amortización': (base & (df.Nivel_1 == '5 - Depreciación y Amortización'), True),
     'Impuestos y Contribuciones': (base & (df.Nivel_1 == '6 - Impuestos y Contribuciones'), True),
     'Remuneración/Sin ajustes': (base & (df.Nivel_1 == '2 - Gastos del Personal') & df.Nivel_2.isin(REM), True),
     'Remuneración/Con ajustes': (base & (df.Nivel_1 == '2 - Gastos del Personal') & df.Nivel_2.isin(REM), False),
     'OGP': (base & (df.Nivel_1 == '2 - Gastos del Personal') & df.Nivel_2.str.startswith('OGP'), False),
     'Marketing': (base & (df.Nivel_1 == '3 - Gastos Administrativos') & (df.Nivel_2 == 'Marketing'), False)}
print('1) Rubros sin ajustes: plantilla vs TD sin IPC según filtro de ajustes')
fino = []
for rubro, (cond, sin_aj) in R.items():
    T = []
    for f in glob.glob(ROOT + rubro + '/*.xlsx'):
        if '/~$' in f: continue
        t = pd.read_excel(f, sheet_name='Ppto27', header=8); T.append(t[t['País'].notna()])
    T = pd.concat(T)
    T['c3'] = T['Ceco - Nombre'].astype(str).str.extract(r'^(\d+) - ')[0]
    X = df[cond & (~ign if sin_aj else True)]
    if sin_aj:
        for pt, g in T.groupby('País'):
            p = PT[pt]; tot = g[M].fillna(0).to_numpy().sum()
            s_todo = df[cond & (df.Pais == p)].Monto.sum(); s_sinaj = df[cond & ~aj & (df.Pais == p)].Monto.sum()
            if abs(tot - s_todo) > 1 or abs(tot - s_sinaj) > 1:
                print(f'   {rubro:28s} {pt:9s} plantilla {tot:,.0f} | TD sin IPC (todos los ajustes) {s_todo:,.0f} | TD sin IPC filtrando "ajuste" {s_sinaj:,.0f}')
    # fino
    a = T.melt(id_vars=['País', 'Vehículo', 'c3'], value_vars=M, var_name='m', value_name='v')
    a['Mes'] = a.m.map({m: i for i, m in enumerate(M, 1)}); a['Pais'] = a['País'].map(PT)
    a = a.groupby(['Pais', 'Vehículo', 'c3', 'Mes']).v.sum()
    b = X.groupby(['Pais', 'Compañía', 'c3', 'Mes']).Monto.sum(); b.index.names = a.index.names
    d = pd.concat([a, b], axis=1, keys=['pl', 'td']).fillna(0); d['dif'] = d.pl - d.td
    malas = d[d.dif.abs() > 0.01]
    fino.append((rubro, len(d), len(malas), d.dif.abs().max()))
print('\n2) Cuadre fino País x Vehículo x CeCo x Mes')
for r, n, m, mx in fino: print(f'   {r:30s} combinaciones {n:6d} | con diferencia: {m} | máx dif {mx:.6f}')
