import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""Por rubro y país: total de la plantilla vs TD sin IPC; y cuánto IPC había en la TD (para ver qué se excluyó)."""
import pandas as pd, glob
from td_filter import VISTAS, NO_CONTABLES, sin_ipc, ajustes_ignorables
ROOT = RAIZ + 'salida/'
M = ['Ene-26', 'Feb-26', 'Mar-26', 'Abr-26', 'May-26', 'Jun-26', 'Jul-26']
PT = {'Chile': 'CHILE', 'Colombia': 'COLOMBIA', 'Perú': 'PERU', 'Panamá': 'PANAMA', 'USA': 'USA', 'México': 'MEXICO'}
df = pd.read_pickle('cache_full.pkl')
for c in ['Pais', 'Datos', 'Vista', 'Nivel_1', 'Nivel_2', 'Compañía', 'Ajuste']: df[c] = df[c].astype(str)
df = df[df.Datos == 'Real 2026'].assign(Mes=lambda x: x.Mes.astype(int))
df = df[df.Mes <= 7]
ign = ajustes_ignorables(df, 'AJUS?TE')
ok = df.Vista.isin(VISTAS) & ~df['Compañía'].isin(NO_CONTABLES)
noint = ~df['Compañía'].str.contains('INTERCOM')
ipc = ~sin_ipc(df)
N1 = {'Tecnología y Comunicaciones': ('4 - Tecnología y Comunicaciones', None, True),
      'Depreciación y Amortización': ('5 - Depreciación y Amortización', None, True),
      'Impuestos y Contribuciones': ('6 - Impuestos y Contribuciones', None, True),
      'Remuneración/Sin ajustes': ('2 - Gastos del Personal', ['Remuneración Fija', 'Incentivo Corto Plazo', 'Remuneración Variable'], True),
      'Remuneración/Con ajustes': ('2 - Gastos del Personal', ['Remuneración Fija', 'Incentivo Corto Plazo', 'Remuneración Variable'], False),
      'OGP': ('2 - Gastos del Personal', 'OGP', False)}
rows = []
for rubro, (n1, n2, sin_aj) in N1.items():
    c = ok & noint & (df.Nivel_1 == n1)
    if isinstance(n2, list): c &= df.Nivel_2.isin(n2)
    elif n2: c &= df.Nivel_2.str.startswith(n2)
    for f in glob.glob(ROOT + rubro + '/*.xlsx'):
        if '/~$' in f: continue
        t = pd.read_excel(f, sheet_name='Ppto27', header=8); t = t[t['País'].notna()]
        for pt, g in t.groupby('País'):
            p = PT[pt]; cp = c & (df.Pais == p)
            aj_all = df.Ajuste.str.upper().str.contains('AJUS?TE')
            viejo = df[cp & ~ipc & (~aj_all if sin_aj else True)].Monto.sum()   # criterio anterior (error)
            nuevo = df[cp & ~ipc & (~ign if sin_aj else True)].Monto.sum()
            rows.append(dict(rubro=rubro, pais=pt, plantilla=g[M].fillna(0).to_numpy().sum(), td_sin_ipc=nuevo,
                             ipc_en_td=df[cp & ipc].Monto.sum(), ipc_que_se_colaba=viejo - nuevo))
R = pd.DataFrame(rows); R['dif'] = R.plantilla - R.td_sin_ipc
pd.set_option('display.width', 250); pd.set_option('display.float_format', lambda v: f'{v:,.2f}')
print(R.to_string())
