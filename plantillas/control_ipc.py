import os as _os; RAIZ = _os.environ.get('PPTO27_RAIZ', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))) + '/'  # raíz del proyecto
"""Control IPC (regla sagrada) con la lista oficial de CeCos de 02. Insumos/06. Maestros/Homologación de CeCos 2026 2.xlsx:
1) En la TD, todo movimiento de un CeCo IPC debe estar marcado como IPC (si no, sin_ipc no lo excluiría).
2) Ninguna plantilla (Ppto27 ni BD - Ppto26) contiene CeCos IPC.
3) Traslados de ajuste hacia/desde IPC: la plantilla no debe quedarse con el gasto reclasificado a IPC."""
import pandas as pd, glob, openpyxl
from td_filter import sin_ipc
BASE = RAIZ
H = pd.read_excel(BASE + '02. Insumos/06. Maestros/Homologación de CeCos 2026 2.xlsx', sheet_name='Homologación')
IPC = {str(int(c)) for c in H.loc[H['Agrupación Ceco'].astype(str).eq('Invertir para Crecer'), 'Centro_Costos'].dropna()}
print('CeCos IPC oficiales:', sorted(IPC))

C = pd.read_pickle('cache_full.pkl')
ce = C.CeCo.astype(str).str.replace(r'\.0$', '', regex=True).str[-3:]
es_ipc_ceco = ce.isin(IPC)
mal = C[es_ipc_ceco & sin_ipc(C)]
print('1) Movimientos de CeCo IPC NO marcados como IPC en la TD:', len(mal), '| monto', round(mal.Monto.sum(), 2))
if len(mal):
    print(mal.groupby([mal.Pais.astype(str), mal.CeCo.astype(str), mal.Nom_CeCo.astype(str), mal['Agrupación_CeCo'].astype(str), mal.Datos.astype(str)]).Monto.sum())
otros = C[~es_ipc_ceco & ~sin_ipc(C)]
print('   Movimientos marcados IPC con CeCo fuera de la lista:', len(otros), otros.CeCo.astype(str).value_counts().head(5).to_dict())

n = 0; bd = 0
for f in glob.glob(BASE + '99. Archivo/Versiones anteriores (salida)/**/Ppto27*.xlsx', recursive=True):
    if '/~$' in f: continue
    d = pd.read_excel(f, sheet_name='Ppto27', header=8, usecols='C')
    n += int(d.iloc[:, 0].astype(str).str.extract(r'^(\d+) - ')[0].isin(IPC).sum())
    b = pd.read_excel(f, sheet_name='BD - Ppto26')
    if 'CeCo' in b:
        bd += int(b.CeCo.astype(str).str.replace(r'\.0$', '', regex=True).str[-3:].isin(IPC).sum())
    if 'Agrupación_CeCo' in b:
        bd += int(b['Agrupación_CeCo'].astype(str).eq('Invertir para Crecer').sum())
print('2) Líneas con CeCo IPC en hojas Ppto27:', n, '| filas IPC en hojas BD - Ppto26:', bd)
