import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""Control de duplicados en TODAS las plantillas de salida/:
A) texto dañado (Ã) en proveedor / glosa
B) mismo proveedor escrito distinto en la misma llave (clave fuerte igual, nombre distinto)
C) línea '(sin proveedor)' con misma llave donde existe UN solo proveedor con nombre
D) filas exactamente repetidas en la llave (no debería existir tras el pivot)"""
import pandas as pd, glob, sys
from prov_norm import clave
ROOT = RAIZ + 'salida/'
res = []
for f in sorted(glob.glob(ROOT + '**/Ppto27*.xlsx', recursive=True)):
    try:
        d = pd.read_excel(f, sheet_name='Ppto27', header=8, usecols='A:M')
    except Exception as e:
        print('ERROR', f, e); continue
    c = list(d.columns)
    d = d[d[c[0]].notna()]
    prov, glosa = c[9], c[10]
    llave = [c[i] for i in (0, 1, 2, 3, 4, 6, 7, 10, 12)]
    X = d.copy()
    for k in llave + [prov]: X[k] = X[k].astype(str)
    a = int(X[prov].str.contains('Ã|�').sum() + X[glosa].str.contains('Ã|�').sum())
    X['_k'] = X[prov].map(lambda p: p if p.startswith('(') or p.upper().startswith('VARIOS') else clave(p))
    g = X.groupby(llave + ['_k'])[prov].nunique()
    b = int((g > 1).sum())
    ej_b = g[g > 1].index[:2].tolist()
    con = X[X[prov] != '(sin proveedor)'].groupby(llave)[prov].nunique()
    uno = set(con[con == 1].index)
    sin = X[X[prov] == '(sin proveedor)']
    cc = int(sum(tuple(r) in uno for r in sin[llave].itertuples(index=False)))
    dd = int(X.duplicated(llave + [prov]).sum())
    res.append(dict(archivo=f.replace(ROOT, ''), filas=len(d), danado=a, prov_variantes=b, sin_prov_pegable=cc, repetidas=dd))
    if b: print('  ej. variantes', f.replace(ROOT, ''), ej_b)
R = pd.DataFrame(res)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500); pd.set_option('display.max_colwidth', 90)
print(R.to_string())
print('\nTOTAL con algún problema:', int(((R.danado + R.prov_variantes + R.sin_prov_pegable + R.repetidas) > 0).sum()), 'de', len(R))
R.to_pickle('control_duplicados.pkl')
