"""Glosas y proveedores para Impuestos y Contribuciones."""
import re
from homologacion import sin_acentos, glosa_cuenta, es_sin_proveedor

GLOSA_IYC = {
    'AJUSTE AL MIL': 'Ajuste al mil', 'Bank Charges - Bank License': 'Licencia bancaria', 'COMISION AGENCIA DE ADUANAS': 'Agencia de aduanas',
    'CONTRIBUCION AMV': 'Contribución AMV (autorregulador)', 'CONTRIBUCION ASOBOLSA': 'Contribución Asobolsa', 'CONTRIBUCION FIDUCOL': 'Contribución Fiducol (fondo de garantías)',
    'CONTRIBUCION SUPERINTENDENCIA': 'Contribución Superintendencia Financiera', 'CUOTA DE SOSTENIMIENTO OTRAS ENTIDADES': 'Cuotas de sostenimiento gremios',
    'DONACIONES': 'Donaciones', 'GASTO POR IMPUESTO AL PATRIMONIO': 'Impuesto al patrimonio', 'IMPUESTO AL PATRIMONIO': 'Impuesto al patrimonio',
    'GASTOS NO DEDUCIBLES': 'Impuesto a no domiciliados y no deducibles', 'GMF GASTOS BANCARIOS': 'GMF (4x1000) en operaciones', 'GMF IMPUESTOS': 'GMF (4x1000)',
    'IMPUESTO 35% GTOS. RECHAZADOS': 'Impuesto 35% gastos rechazados', 'IMPUESTO A LAS TRANSACCIONES FINANCIERAS': 'ITF (impuesto a las transacciones financieras)',
    'IMPUESTO A LAS TRANSACCIONES FINANCIERAS - DIVIDENDOS': 'ITF dividendos', 'IMPUESTO A LOS PRODUCTOS COMENSTIBLES ULTRAPROCESADOS ICUI': 'Impuestos al consumo',
    'IMPUESTO AD VALOREM (IMPUESTO DEPARTAMENTAL AL CONSUMO DE LICORES ADV)': 'Impuestos al consumo', 'IMPUESTO AL CONSUMO DE LICORES (ICL)': 'Impuestos al consumo',
    'IMPUESTO CONSUMO': 'Impuestos al consumo', 'IMPUESTO IBUA': 'Impuestos al consumo', 'IMPUESTO DE ICA SERVICIOS BARRANQUILLA': 'ICA Barranquilla',
    'IMPUESTO DE ICA SERVICIOS BOGOTA': 'ICA Bogotá', 'IMPUESTO DE ICA SERVICIOS CALI': 'ICA Cali', 'IMPUESTO DE ICA SERVICIOS MEDELLIN': 'ICA Medellín',
    'IMPUESTO DIFERIDO': 'Impuesto diferido', 'IMPUESTO PREDIAL': 'Impuesto predial', 'IMPUESTO REGISTRO CAMARA': 'Impuesto de registro Cámara de Comercio',
    'IMPUESTOS ASUMIDOS': 'Impuestos asumidos (retenciones)', 'INTERESES BANCOS DEL EXTERIOR': 'Intereses bancos del exterior', 'INTERESES DE MORA': 'Intereses de mora',
    'INTERESES DE MORA R.O': 'Intereses de mora', 'IVA MAYOR VALOR DEL GASTO': 'IVA mayor valor del gasto', 'IVA NO RECUPERABLE': 'IVA no recuperable',
    'IVA PROPORCIONAL': 'IVA proporcional', 'LIQUIDACION DE OTROS PASIVOS': 'Liquidación de otros pasivos', 'OTROS IMPUESTOS PAGADOS': 'Otros impuestos (ITE, impuesto adicional)',
    'OTROS INGRESOS': 'Intereses SUNAT a favor', 'OTROS SERVICIOS': 'IGV no deducible', 'Other Taxes': 'Otros impuestos', 'SERVICIO DE SOPORTE RELACIONADAS': 'Impuesto a no domiciliados',
    'TASA ESPECIAL SEGURIDAD Y CONVIVENCIA CIUDADANA': 'Tasa de seguridad ciudadana', 'Taxes - Foreign Tax Paid': 'Impuestos pagados en el exterior', 'Taxes - Miscellaneous': 'Otros impuestos',
}
def glosa_iyc(cuenta, texto):
    base = GLOSA_IYC.get(cuenta) or glosa_cuenta(cuenta)
    t = sin_acentos(str(texto or '')).upper()
    if base in ('Impuesto al patrimonio',) and re.search(r'REVERSI', t):
        return 'Impuesto al patrimonio (reversión)'
    if base == 'GMF (4x1000)' and re.search(r'DIVISAS', t):
        return 'GMF (4x1000) venta de divisas'
    if base == 'Impuestos asumidos (retenciones)' and re.search(r'RETENCION', t):
        return 'Impuestos asumidos (retenciones Chile y Perú)'
    return base

CUENTAS_VARIOS = {'IVA MAYOR VALOR DEL GASTO', 'GMF GASTOS BANCARIOS', 'IMPUESTO CONSUMO', 'IMPUESTO A LOS PRODUCTOS COMENSTIBLES ULTRAPROCESADOS ICUI',
                  'IMPUESTO AD VALOREM (IMPUESTO DEPARTAMENTAL AL CONSUMO DE LICORES ADV)', 'IMPUESTO AL CONSUMO DE LICORES (ICL)', 'IMPUESTO IBUA',
                  'IMPUESTO 35% GTOS. RECHAZADOS', 'AJUSTE AL MIL', 'LIQUIDACION DE OTROS PASIVOS', 'IMPUESTOS ASUMIDOS'}
AUTORIDAD = {'IMPUESTO DE ICA SERVICIOS BOGOTA': 'SECRETARIA DISTRITAL DE HACIENDA DE BOGOTA D.C.', 'IMPUESTO DE ICA SERVICIOS MEDELLIN': 'SECRETARIA DE HACIENDA DEL MUNICIPIO DE MEDELLIN',
             'IMPUESTO DE ICA SERVICIOS CALI': 'ALCALDIA DE SANTIAGO DE CALI', 'IMPUESTO DE ICA SERVICIOS BARRANQUILLA': 'ALCALDIA DISTRITAL DE BARRANQUILLA',
             'IVA PROPORCIONAL': 'DIAN', 'GASTO POR IMPUESTO AL PATRIMONIO': 'DIAN', 'IMPUESTO AL PATRIMONIO': 'DIAN', 'IMPUESTO DIFERIDO': 'DIAN',
             'CONTRIBUCION SUPERINTENDENCIA': 'SUPERINTENDENCIA FINANCIERA DE COLOMBIA', 'CONTRIBUCION AMV': 'AMV (AUTORREGULADOR DEL MERCADO DE VALORES)',
             'IMPUESTO A LAS TRANSACCIONES FINANCIERAS': 'SUNAT', 'IMPUESTO A LAS TRANSACCIONES FINANCIERAS - DIVIDENDOS': 'SUNAT', 'GASTOS NO DEDUCIBLES': 'SUNAT',
             'SERVICIO DE SOPORTE RELACIONADAS': 'SUNAT', 'OTROS INGRESOS': 'SUNAT', 'IVA NO RECUPERABLE': 'SII', 'OTROS IMPUESTOS PAGADOS': 'SII'}
NORMA = [(r'DIRECCION DE IMPUESTOS Y AD', 'DIAN'), (r'SUPERINTENDENCIA NACIONAL DE ADUANAS', 'SUNAT'), (r'AUTORREGULADOR', 'AMV (AUTORREGULADOR DEL MERCADO DE VALORES)'),
         (r'SECRETARIA DISTRITAL DE HACIENDA DE BOGOTA', 'SECRETARIA DISTRITAL DE HACIENDA DE BOGOTA D.C.'), (r'^IMPUESTOS$', 'SII')]
NORMA = [(re.compile(r), p) for r, p in NORMA]

def proveedor_iyc(homol, prov, texto, cuenta, glosa):
    if es_sin_proveedor(prov) or str(prov).strip().upper() in ('OTROS', 'PTY', 'NA', 'TERCERO GENERICO', 'TERCERO GENÉRICO') or re.fullmatch(r'[\d\s\-/\.]+', str(prov).strip()):
        return AUTORIDAD.get(cuenta, '(sin proveedor)')
    n = homol.nombre(prov, texto); u = sin_acentos(n).upper()
    for rx, p in NORMA:
        if rx.search(u): return p
    return n
