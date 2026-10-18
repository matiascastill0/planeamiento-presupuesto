import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""Arma las líneas de la plantilla (Tabla1) a partir de la BD Real homologada."""
from prov_norm import reparar, sin_varios
import pandas as pd, numpy as np, glob
from homologacion import Homologador, glosa
ROOT=RAIZ
# Cuentas cuya contraparte es el cliente / fondo (no un proveedor): se agrupan en una sola línea
CUENTAS_CLIENTE={'AJUSTE AL MIL','OTRAS CARGAS DE GESTIÓN - AJUSTE POR REDONDEO','OTROS INGRESOS - AJUSTE POR REDONDEO',
    'OTRAS COMISIONES','OTROS INGRESOS','DEPÓSITOS DE AHORRO ORDINARIO','LIQUIDACION DE OTROS PASIVOS',
    'ABONO POR RECONOCIMIENTO OP COMISIONES','ABONOS MANEJO COMERCIAL','RECUPERACIONES CARTERA','PROVISION DEUDORES'}
PAIS_TXT={'CHILE':'Chile','COLOMBIA':'Colombia','PERU':'Perú','PANAMA':'Panamá','USA':'USA','MEXICO':'México'}

def mapa_proveedores_archivos():
    m={}
    for f in glob.glob(ROOT+'02. Insumos/05. Bases por área/Gastos Administrativos/*/*/*.xlsx'):
        try: d=pd.read_excel(f,sheet_name='Sheet1',usecols=['Proveedor','Proveedor_Homologado'])
        except Exception: continue
        d=d.dropna().drop_duplicates()
        for a,b in zip(d.Proveedor,d.Proveedor_Homologado):
            a=str(a).replace('\t',' ').strip().strip('"').strip()
            if b and b!='(sin proveedor)': m[a]=b
    return m

def preparar(R, homol):
    R=R.copy()
    R['Proveedor_H']=[homol.nombre(p,t) for p,t in zip(R.Proveedor,R.Texto)]
    R['Proveedor_H']=R.Proveedor_H.map(reparar)   # letras dañadas de origen (VIÃ?A -> VIÑA)
    R['Proveedor_H']=[sin_varios(p,t) for p,t in zip(R.Proveedor_H,R.Texto)]
    # REGLA: nunca 'Varios ...' como proveedor; cada línea con su proveedor/cliente real
    R['Glosa']=[glosa(n2,c,t) for n2,c,t in zip(R.Nivel_2,R.Nom_Cta_Contable,R.Texto)]
    return R

def lineas(R, ceco_nombre):
    """Agrupa por vehículo/ceco/cuenta/nivel 2/proveedor/glosa; columnas Ene..Jul."""
    R=R.copy()
    R['CeCo_txt']=R.CeCo.astype(str).str.replace(r'\.0$','',regex=True)
    R['Ceco - Nombre']=R.CeCo_txt.map(ceco_nombre).fillna(R.CeCo_txt+' - '+R.Nom_CeCo.fillna(''))
    R['Nivel 1']=R.Nivel_1.str.replace(r'^\d+ - ','',regex=True)
    R['Nom Cta Contable']=R.Nom_Cta_Contable
    k=['Pais','Compañía','Ceco - Nombre','Nom Cta Contable','Nivel 1','Nivel_2','Proveedor_H','Glosa','Moneda']
    p=R.pivot_table(index=k,columns='Mes',values='Monto',aggfunc='sum',fill_value=0).reset_index()
    meses=[c for c in p.columns if isinstance(c,(int,np.integer))]
    p=p[p[meses].abs().sum(axis=1)>0.5]
    return p,meses
