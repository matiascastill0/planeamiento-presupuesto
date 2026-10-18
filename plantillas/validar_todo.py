import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""Control global: CeCo numerado en todas las líneas + cuadre por país y mes contra la TD (con regla sin IPC)."""
import pandas as pd, glob, openpyxl, os
from td_filter import VISTAS, NO_CONTABLES, sin_ipc, ajustes_ignorables
ROOT = RAIZ + 'salida/'
M = ['Ene-26', 'Feb-26', 'Mar-26', 'Abr-26', 'May-26', 'Jun-26', 'Jul-26']
PT = {'Chile': 'CHILE', 'Colombia': 'COLOMBIA', 'Perú': 'PERU', 'Panamá': 'PANAMA', 'USA': 'USA', 'México': 'MEXICO'}
df = pd.read_pickle('cache_full.pkl')
for c in ['Pais', 'Datos', 'Vista', 'Nivel_1', 'Nivel_2', 'Compañía', 'Ajuste']: df[c] = df[c].astype(str)
df = df[df.Datos == 'Real 2026'].assign(Mes=lambda x: x.Mes.astype(int))
base = df.Vista.isin(VISTAS) & ~df['Compañía'].isin(NO_CONTABLES) & sin_ipc(df)
noint = ~df['Compañía'].str.contains('INTERCOM')
aj = ajustes_ignorables(df, 'AJUS?TE')   # los traslados hacia/desde IPC no se ignoran
REF = {
    'Oficinas y Suministros': base & noint & (df.Nivel_1 == '3 - Gastos Administrativos') & (df.Nivel_2 == 'Oficinas y Suministros'),
    'CS Administrativo': base & (noint | (df['Compañía'] == 'INTERCOM_BCP')) & (df.Nivel_2 == 'CS Administrativo'),
    'Consultorías y Honorarios': base & noint & (df.Nivel_1 == '3 - Gastos Administrativos') & (df.Nivel_2 == 'Consultorías y Honorarios'),
    'OGP': base & noint & (df.Nivel_1 == '2 - Gastos del Personal') & df.Nivel_2.str.startswith('OGP'),
    'Marketing': base & noint & (df.Nivel_1 == '3 - Gastos Administrativos') & (df.Nivel_2 == 'Marketing'),
    'Tecnología y Comunicaciones': base & noint & (df.Nivel_1 == '4 - Tecnología y Comunicaciones') & ~aj,
    'Depreciación y Amortización': base & noint & (df.Nivel_1 == '5 - Depreciación y Amortización') & ~aj,
    'Impuestos y Contribuciones': base & noint & (df.Nivel_1 == '6 - Impuestos y Contribuciones') & ~aj,
    'Remuneración/Con ajustes': base & noint & (df.Nivel_1 == '2 - Gastos del Personal') & df.Nivel_2.isin(['Remuneración Fija', 'Incentivo Corto Plazo', 'Remuneración Variable']),
    'Remuneración/Sin ajustes': base & noint & (df.Nivel_1 == '2 - Gastos del Personal') & df.Nivel_2.isin(['Remuneración Fija', 'Incentivo Corto Plazo', 'Remuneración Variable']) & ~aj,
}
malas = 0; tot_lineas = 0
for rubro, cond in REF.items():
    fs = glob.glob(ROOT + rubro + '/*.xlsx')
    T = []
    for f in fs:
        t = pd.read_excel(f, sheet_name='Ppto27', header=8); t = t[t['País'].notna()]; T.append(t)
    T = pd.concat(T); tot_lineas += len(T)
    bad = T[~T['Ceco - Nombre'].astype(str).str.match(r'^\d+ - ')]; malas += len(bad)
    R = df[cond]
    mx = max(abs(T[T['País'] == pt][mc].sum() - R[(R.Pais == p) & (R.Mes == i)].Monto.sum()) for pt, p in PT.items() for i, mc in enumerate(M, 1))
    print(f'{rubro:30s} {len(fs):2d} archivos | {len(T):6d} líneas | sin CeCo numerado: {len(bad)} | máx dif país x mes vs TD: {mx:.6f}')
ud = [f for f in glob.glob(ROOT + '99. Archivo/Versiones anteriores (salida)/UdN/*/*.xlsx') + glob.glob(ROOT + '99. Archivo/Versiones anteriores (salida)/Staff/*/*.xlsx') if '/~$' not in f]; b2 = 0
for f in ud:
    t = pd.read_excel(f, sheet_name='Ppto27', header=8, usecols='A:C'); t = t[t['País'].notna()]
    b2 += (~t['Ceco - Nombre'].astype(str).str.match(r'^\d+ - ')).sum()
print(f'UdN / Staff: {len(ud)} archivos | sin CeCo numerado: {b2}')
print('TOTAL líneas sin CeCo numerado:', malas + b2)
