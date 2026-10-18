import pandas as pd, unicodedata
sa=lambda x: ''.join(ch for ch in unicodedata.normalize('NFD',str(x)) if unicodedata.category(ch)!='Mn').upper()
N2=['Gastos de Representación','Misiones','Pagos Transaccionales, Bolsas y Otros','Suscripciones y Servicios de Información','Transporte y Mensajería','Provisión de Incobrables']
# Compañías que no son de la contabilidad (se tratan igual que INTERCOM)
NO_CONTABLES=['ELIM_SC','ELIM_CCSPP']
# Regla fija: Invertir para Crecer (IPC) queda fuera de todas las plantillas
def sin_ipc(df):
    return ~(df['Agrupación_CeCo'].astype(str).eq('Invertir para Crecer') | df['UdN'].astype(str).str.upper().eq('IPC'))
VISTAS=['1 Vista directa C.Benef','3 Vista directa C.costo']
def td(df,unidad,datos='Real 2026',pais=None):
    """Replica los filtros de la TD Regional (hoja Plantilla) para una UdN o Staff."""
    staff=unidad.startswith('Staff')
    m=(df.Datos==datos)&df.Vista.isin(VISTAS)&~df['Compañía'].astype(str).str.contains('INTERCOM')&~df['Compañía'].astype(str).isin(NO_CONTABLES)&(df.Nivel_1=='3 - Gastos Administrativos')&sin_ipc(df)
    if pais: m&=(df.Pais==pais)
    ag=df['Agrupación_CeCo']==unidad
    main=m&ag&df.Nivel_2.isin(N2)
    cons=m&ag&(df.Nivel_2=='Consultorías y Honorarios')&(df.Nivel_3==('Consultorías de Staff' if staff else 'Consultorías de Negocio'))
    if not staff: cons&=df.UdN.astype(str).map(sa)==sa(unidad)
    return df[main|cons]

# Ajustes: en los rubros "sin ajustes" se ignoran, SALVO los traslados hacia/desde Invertir para Crecer.
# Si se ignoraran, el gasto reclasificado a IPC quedaría en los CeCos normales (p.ej. licencias GenAI -> CeCo 367).
def ajustes_ignorables(df, patron='AJUSTE'):
    """True en las filas de ajuste que se pueden ignorar (no trasladan monto hacia/desde IPC)."""
    import pandas as pd
    aj = df['Ajuste'].astype(str).str.upper().str.contains(patron, regex=True)
    base = df['Ajuste'].astype(str).str.replace(r'\s*-\s*1\s*$', '', regex=True).str.strip().str.upper()
    ipc = ~sin_ipc(df)
    llave = [df['Datos'].astype(str), df['Pais'].astype(str), df['Nivel_1'].astype(str), base]
    neto_ipc = df['Monto'].where(ipc & aj, 0.0).groupby(llave).transform('sum')
    traslado_ipc = aj & (neto_ipc.abs() > 0.5)
    return aj & ~traslado_ipc
