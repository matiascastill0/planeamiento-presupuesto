"""Verifica plantillas v2: cuadre vs fuente por país x vehículo x CeCo x Nivel 2 x mes (ene–ago), cuentas operativas presentes,
ceros vacíos, Tablas S = proveedores usados y oculta."""
import pandas as pd, numpy as np, re, zipfile, openpyxl, os, sys, glob
import ruta_v2 as V
from agosto_lineas import filtrar
from agosto_encaje import nk
M = ['Ene-26', 'Feb-26', 'Mar-26', 'Abr-26', 'May-26', 'Jun-26', 'Jul-26', 'Ago-26']
c3 = lambda v: (lambda s: s[-3:] if len(s) == 6 and s.startswith('211') else s)(re.sub(r'\.0$', '', str(v)))
def leer(f):
    wb = openpyxl.load_workbook(f); ws = wb['Ppto27']; t = list(ws.tables.values())[0]
    r0 = int(re.match(r'[A-Z]+(\d+)', t.ref).group(1)); r1 = int(re.search(r'(\d+)$', t.ref).group(1))
    hdr = [str(ws.cell(r0, c).value or '').replace('\n', ' ').strip() for c in range(1, 42)]
    T = pd.DataFrame([[ws.cell(r, c).value for c in range(1, 42)] for r in range(r0 + 1, r1 + 1)], columns=hdr)
    ceros = sum(1 for r in range(r0 + 1, r1 + 1) for c in range(14, 26) if ws.cell(r, c).value == 0)
    tabl = wb['Tablas'] if 'Tablas' in wb.sheetnames else None
    s = [tabl.cell(i, 19).value for i in range(1, tabl.max_row + 1) if tabl.cell(i, 19).value] if tabl else None
    dn = wb.defined_names.get('Proveedor').attr_text if tabl is not None and 'Proveedor' in wb.defined_names else None
    return T, ceros, (tabl.sheet_state if tabl else 'sin Tablas'), s, dn
def fuente(rubro, sub, pais, TD, O, S, H, ctx=None):
    if rubro == 'CS' and sub == 'Indirecto BCP':      # excepción INTERCOM_BCP: se compara directo contra la TD (ene–ago)
        X = V.TD_INDIRECTO_BCP[V.TD_INDIRECTO_BCP.Pais == pais]
        return X.assign(N2=X.Nivel_2)
    if rubro in ('OYS', 'CS', 'CH'):
        B = {'OYS': O, 'CS': S, 'CH': H}[rubro]
        X = B[(B.Pais == pais) & ((B.Plantilla == sub) if rubro == 'OYS' else (B.Cat == sub))]
        if rubro == 'OYS':
            X = X[X.Ajuste.astype(str).str.upper().str.strip().isin(['CENTRALIZADO', 'IMPUTADO'])] if pais == 'CHILE' else X[X.Sin_Ajuste.astype(str).str.upper().isin(['TRUE', '1'])]
        return X.assign(Monto=X['Monto ML'], N2=X.get('Nivel_2', ''), Compañía=X['Compañía'])
    if rubro == 'ILP': X = TD[(TD.Pais == pais) & (TD.Nivel_2 == 'Incentivo Largo Plazo')]
    else:
        X = filtrar(rubro, sub, pais, TD, sin_ajustes_oys=False)
        if rubro in ('UDN', 'STAFF'):
            X = X[~X.Nivel_2.isin(['Oficinas y Suministros', 'CS Administrativo', 'Consultorías y Honorarios'])]
            C = V.consultorias_udn(sub, pais, H, ctx)       # Consultorías de Negocio / Staff: base regional por Agrupación
            if len(C): X = pd.concat([V._objetos(X), C], ignore_index=True)
    return X.assign(N2=X.Nivel_2)
if __name__ == '__main__':
    TD = V.cargar_td(); O, S, H = V.cargar_bases(TD)
    from agosto_lineas import Ctx
    ctx = Ctx(extra_prov=TD.Proveedor)
    res = []
    for f in sorted(glob.glob(V.DEST + '**/*.xlsx', recursive=True)):
        rel = os.path.relpath(f, V.DEST)
        if ('Validación' in rel or 'Checklist' in rel) or '~$' in rel or 'versiones-previas' in rel or (len(sys.argv) > 1 and sys.argv[1] not in V.nfc(rel)): continue
        rubro, sub, pais = V.clasificar(rel)
        T, ceros, estado, s, dn = leer(f)
        T = T[T['País'].notna()]
        for m in M: T[m] = pd.to_numeric(T[m], errors='coerce').fillna(0)
        paises = [pais] if pais else V.ORDEN_PAIS
        X = pd.concat([fuente(rubro, sub, p, TD, O, S, H, ctx) for p in paises], ignore_index=True)
        # nivel de comparación: país x vehículo x (CeCo salvo OyS Chile centralizado) x mes
        a = T.assign(P=T['País'].map(V.TXT2P), c=T['Ceco - Nombre'].astype(str).str.extract(r'^(\d+)')[0].map(c3)).melt(id_vars=['P', 'Vehículo', 'c'], value_vars=M, var_name='m', value_name='v')
        a['Mes'] = a.m.map({x: i for i, x in enumerate(M, 1)})
        if rubro == 'OYS':                    # OyS Chile CENTRALIZADO va al 309: se compara por país x vehículo x mes
            A = a.groupby(['P', 'Vehículo', 'Mes']).v.sum(); B = X.groupby(['Pais', 'Compañía', 'Mes']).Monto.sum()
        else:
            A = a.groupby(['P', 'Vehículo', 'c', 'Mes']).v.sum()
            Xc = X.assign(c=X.CeCo.map(c3) if 'CeCo' in X and X.CeCo.notna().any() else None)
            if Xc['c'].isna().all():                 # bases sin código de CeCo: comparar sin CeCo
                A = a.groupby(['P', 'Vehículo', 'Mes']).v.sum(); B = X.groupby(['Pais', 'Compañía', 'Mes']).Monto.sum()
            else: B = Xc.groupby(['Pais', 'Compañía', 'c', 'Mes']).Monto.sum()
        B.index.names = A.index.names
        d = pd.concat([A, B], axis=1, keys=['pl', 'src']).fillna(0); d['dif'] = d.pl - d.src
        provs = sorted({str(p) for p in T.Proveedor.dropna()})
        res.append(dict(archivo=V.nfc(rel).split('/')[-1][:50], rubro=rubro, filas=len(T), combos=len(d), combos_dif=int((d.dif.abs() > 0.01).sum()), max_dif=float(d.dif.abs().max() if len(d) else 0),
                        total_pl=float(T[M].to_numpy().sum()), total_src=float(X.Monto.sum()), ceros=ceros, tablas=estado,
                        s_ok=(s is not None and sorted(map(str, s)) == provs), dn=dn, varios=int(T.Proveedor.astype(str).str.match(r'(?i)\s*vario').sum())))
    R = pd.DataFrame(res); R.to_pickle('v2_verif.pkl')
    pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300); pd.set_option('display.float_format', lambda v: f'{v:,.2f}')
    print(R.to_string())
