import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""Construye la BD Real 2026 y Ppto 2026 por unidad/país replicando los filtros de la TD Regional."""
import pandas as pd, numpy as np, glob, os, re, unicodedata
from td_filter import td
ROOT=RAIZ
nfc=lambda s: unicodedata.normalize('NFC',s)
def fix(s):
    if not isinstance(s,str): return s
    s=s.replace('\t',' ').strip().strip('"').strip()
    if 'Ã' in s or 'Â' in s:
        try: s=s.encode('latin1').decode('utf8')
        except Exception: pass
    return re.sub(r'\s+',' ',s)
UNIDADES=[('udn',nfc(u)) for u in sorted(os.listdir(ROOT+'02. Insumos/05. Bases por área/Gastos Administrativos/udn')) if not u.startswith('.')]+[('staff',nfc(u)) for u in sorted(os.listdir(ROOT+'02. Insumos/05. Bases por área/Gastos Administrativos/staff')) if not u.startswith('.')]
def agrup(u): return u.replace('COE DE_CX','COE DE/CX')
def main():
    df=pd.read_pickle('cache_full.pkl')
    for c in ['Pais','Datos','Vista','Nivel_1','Nivel_2','Nivel_3','Agrupación_CeCo','UdN','Compañía']: df[c]=df[c].astype(str)
    # quitar acentos para comparar UdN (Tesorería vs TESORERIA)
    real=[];ppto=[]
    for tipo,u in UNIDADES:
        ag=agrup(u)
        r=td(df,ag,'Real 2026'); p=td(df,ag,'Ppto 2026')
        r=r.assign(Unidad=u,Tipo=tipo,origen='TD'); p=p.assign(Unidad=u,Tipo=tipo,origen='TD')
        # Colombia: Nivel_3 viene vacío en la TD para consultorías -> usar filas clasificadas del archivo regional de consultorías
        f=glob.glob(ROOT+f'02. Insumos/05. Bases por área/Gastos Administrativos/{tipo}/*/*_COLOMBIA_V1y3.xlsx')
        f=[x for x in f if nfc(os.path.basename(x)).startswith(u+'_')]
        if f:
            d=pd.read_excel(f[0],sheet_name='Sheet1'); c=d[d.origen=='Consultorias_Regional'].copy()
            if len(c):
                c=c.rename(columns={'Compania':'Compañía','Agrupacion_CeCo':'Agrupación_CeCo'})
                c['Unidad']=u;c['Tipo']=tipo;c['origen']='Consultorias_Regional';c['Pais']='COLOMBIA'
                real.append(c[[x for x in c.columns if x in r.columns or x in('Proveedor_Homologado',)]])
        real.append(r); ppto.append(p)
    R=pd.concat(real,ignore_index=True); P=pd.concat(ppto,ignore_index=True)
    for X in (R,P):
        for c in ['Nom_Cta_Contable','Texto','Proveedor','Nom_CeCo','Nivel_3','Nivel_4']: X[c]=X[c].map(fix)
        X['Mes']=pd.to_numeric(X['Mes'],errors='coerce').astype('Int64')
        # Panamá: Commision Paid y TRASLADOS se registran como vehículo BNK
        X['Compañía']=X['Compañía'].astype(str)
        X.loc[(X.Pais=='PANAMA')&X['Compañía'].isin(['Commision Paid','TRASLADOS']),'Compañía']='BNK'
    R.to_pickle('bd_real.pkl'); P.to_pickle('bd_ppto.pkl')
    print(R.groupby(['Unidad','Pais']).size().to_string())
    print('real',len(R),'ppto',len(P))
    print('ppto units/countries without real:', sorted(set(P.groupby(['Unidad','Pais']).groups)-set(R.groupby(['Unidad','Pais']).groups)))
if __name__=='__main__': main()
