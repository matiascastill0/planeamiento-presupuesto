"""Glosas para Consultorías y Honorarios (Auditorías / Asesorías Legales / Dietas)."""
import re
from homologacion import sin_acentos

BASE_N3 = {'Asesorías Legales': 'Asesoría legal', 'Asesorías Legales Sartor': 'Asesoría legal caso Sartor', 'Auditorías Tributarias y Financieras': 'Auditoría y asesoría tributaria',
           'Consultorías de Negocio': 'Consultoría de negocio', 'Consultorías de Staff': 'Consultoría de staff', 'Consultorías Bolsa CEO': 'Consultoría Bolsa CEO', 'Dietas': 'Dietas de directorio'}
REGLAS = [
    (r'NOTARI|ESCRITURA P[UÚ]BLICA|REGISTRAL|LEGALIZACI', 'Gastos notariales y registrales'),
    (r'REVISOR[IÍ]A FISCAL', 'Revisoría fiscal'),
    (r'AUDITOR[IÍ]A|AUDITORES|AUDIT\b|AUDIT OF|PROV AUD|TANAKA|KAUFMAN ROSSIN', 'Auditoría de estados financieros'),
    (r'FATCA|FACTCA|\bCRS\b|REPORTE FISCAL|INFORMACION FISCAL', 'Reportes fiscales FATCA/CRS'),
    (r'FISCALIZACI[OÓ]N (SUNAT|TRIBUTARIA)', 'Fiscalización tributaria'),
    (r'TRIBUTARI|DECLARACIONES JURADAS|PRECIOS DE TRANSFERENCIA|REPORTE LOCAL|TEST DE BENEFICIO|\bTAX\b', 'Asesoría tributaria'),
    (r'COMIT[EÉ] DE RIESGO', 'Dietas comité de riesgo'),
    (r'COMIT[EÉ] DE (INVERSI|CR[EÉ]DITO|DERECHOS)|MIEMBRO DEL COMIT|ASESOR COMITE', 'Comités de inversión y crédito'),
    (r'DIETA|DIRECTORIO|JUNTA DIRECTIVA|PAGO DIRECTORES', 'Dietas de directorio'),
    (r'TRADUCCI', 'Traducciones'),
    (r'DEFENSOR[IÍ]A DEL CONSUMIDOR|DEFENSOR DEL CONSUMIDOR', 'Defensor del consumidor financiero'),
    (r'CONSULAR|\bVISA\b', 'Trámites migratorios'),
    (r'SARTOR|LOVELLS', 'Asesoría legal caso Sartor'),
    (r'LEGAL|ABOGAD|JUR[IÍ]DIC|\bLAW\b|CUATRECASAS|ERRAZURIZ|CAREY Y|POSSE HERRERA|GODOY CORDOBA|REBAZA|OSTERLING|PAYET|CONYERS|ROSENOW|RIED FABRES|RECABARREN', 'Asesoría legal'),
    (r'CONTRALOR[IÍ]A NORMATIVA|CONTRALOR NORMATIVO', 'Contralor normativo'),
    (r'MESA DE PARTES', 'Mesa de partes'),
    (r'TRANSFORMACI', 'Proyecto de transformación'),
    (r'SOPORTE DE SOFTWARE|NEGOCIOS DIGITALES', 'Soporte de software (Negocios Digitales)'),
    (r'GESTI[OÓ]N POR PROCES', 'Diagnóstico de procesos'),
    (r'GRI MEMBERSHIP|GRI CLUB', 'Membresía GRI'),
    (r'COMUNICACIONES|COYUNTURA|SOCIOPOL', 'Asesoría en comunicaciones'),
    (r'IMPORTACI[OÓ]N DE ASIENTOS|REALIZACI', 'Asientos entre relacionadas'),
]
REGLAS = [(re.compile(r), g) for r, g in REGLAS]

def glosa_ch(cat, cuenta, texto, n3=None, proveedor=None):
    t = sin_acentos(f'{texto or ""} | {cuenta or ""} | {proveedor or ""}').upper()
    for rx, g in REGLAS:
        if rx.search(t):
            return g
    return BASE_N3.get(n3, 'Honorarios profesionales')

# ---------------------------------------------------------------- categoría por contenido (reclasificación)
R_DIETAS = re.compile(r'DIETA|DIRECTORIO|JUNTA DIRECTIVA|PAGO DIRECTORES|MIEMBRO DEL COMIT|COMIT[EÉ] DE (INVERSI|RIESGO|CR[EÉ]DITO|DERECHOS)|ASESOR COMITE')
R_NOTARIAL = re.compile(r'NOTARI|ESCRITURA P[UÚ]BLICA|REGISTRAL')
R_AUDIT = re.compile(r'FATCA|FACTCA|\bCRS\b|REPORTE FISCAL|INFORMACION FISCAL|AUDITOR[IÍ]A|AUDITORES|AUDIT\b|AUDIT OF|REVISOR[IÍ]A FISCAL|TRIBUTARI|FISCALIZACI[OÓ]N (SUNAT|TRIBUTARIA)|DECLARACIONES JURADAS|PRECIOS DE TRANSFERENCIA|\bTAX\b|TANAKA|KAUFMAN ROSSIN')
R_LEGAL = re.compile(r'LEGAL|ABOGAD|JUR[IÍ]DIC|\bLAW\b|NOTARI|ESCRITURA P[UÚ]BLICA|REGISTRAL|TRADUCCI|DEFENSOR|CONSULAR|\bVISA\b|LOVELLS|CUATRECASAS|ERRAZURIZ|CAREY Y|POSSE HERRERA|GODOY CORDOBA|REBAZA|OSTERLING|PAYET|CONYERS|ROSENOW|RIED FABRES|RECABARREN')
def categoria_ch(n3, cuenta, texto, proveedor):
    t = sin_acentos(f'{texto or ""} | {cuenta or ""} | {proveedor or ""}').upper()
    if R_NOTARIAL.search(t): return 'Asesorías Legales'
    if R_DIETAS.search(t): return 'Dietas'
    if R_AUDIT.search(t): return 'Auditorías'
    if R_LEGAL.search(t): return 'Asesorías Legales'
    n3 = str(n3 or '')
    if n3.startswith('Asesorías Legales'): return 'Asesorías Legales'
    if n3 == 'Dietas': return 'Dietas'
    if n3 == 'Auditorías Tributarias y Financieras': return 'Auditorías'
    return 'Consultorías'

CAT_DE_GLOSA = {
    'Gastos notariales y registrales': 'Asesorías Legales', 'Asesoría legal': 'Asesorías Legales', 'Asesoría legal caso Sartor': 'Asesorías Legales',
    'Traducciones': 'Asesorías Legales', 'Defensor del consumidor financiero': 'Asesorías Legales', 'Trámites migratorios': 'Asesorías Legales',
    'Revisoría fiscal': 'Auditorías', 'Auditoría de estados financieros': 'Auditorías', 'Fiscalización tributaria': 'Auditorías',
    'Asesoría tributaria': 'Auditorías', 'Auditoría y asesoría tributaria': 'Auditorías', 'Reportes fiscales FATCA/CRS': 'Auditorías',
    'Dietas de directorio': 'Dietas', 'Dietas comité de riesgo': 'Dietas', 'Comités de inversión y crédito': 'Dietas',
}
def categoria_por_glosa(glosa):
    return CAT_DE_GLOSA.get(glosa, 'Consultorías')

# ---------------------------------------------------------------- destino de cada fila de la base Regional C&H (ruta v2)
# No se decide sólo por la hoja / Nivel 3 de la base ni por la cuenta (en Perú "ASESORIA Y CONSULTORIA - ADMINISTRATIVA"
# se usa para legal, auditoría y servicios). Se mira primero el TEXTO, luego el PROVEEDOR y sólo al final la CUENTA;
# si nada calza, el Nivel 3 de la base. Mesa de partes nunca es asesoría legal: va a Consultorías (UdN / Staff).
R_CONSULT_ADM = re.compile(r'MESA DE PARTES')
DESTINOS = {'Auditorías': 'Auditorías Tributarias y Financieras', 'Asesorías Legales': 'Asesorías Legales', 'Dietas': 'Dietas', 'Consultorías': 'Consultorías'}
# Dietas = SÓLO directorio (usuario, 2026-10-01): comités de inversión / crédito / riesgo / derechos económicos no son dietas,
# van a Consultorías de la UdN / Staff de su Agrupación (servicio 'Comités de inversiones', etc.); auditoría antes que dietas.
R_COMITE = re.compile(r'COMIT[EÉ]')
R_DIRECTORIO = re.compile(r'DIRECTORIO|JUNTA DIRECTIVA|PAGO DIRECTORES|DIRECTOR(ES)? INDEPENDIENTE|\bDIETAS?\b|RETRIBUCION(ES)? AL DIRECTORIO')
REGLAS_CH = [(R_CONSULT_ADM, 'Consultorías', 'mesa de partes (servicio administrativo)'),
             (R_NOTARIAL, 'Asesorías Legales', 'notarial / registral'),
             (R_COMITE, 'Consultorías', 'comités (inversión / crédito / riesgo): no son dietas'),
             (R_AUDIT, 'Auditorías', 'auditoría / tributario'),
             (R_DIRECTORIO, 'Dietas', 'dietas de directorio'),
             (R_LEGAL, 'Asesorías Legales', 'legal / abogados')]
# Orden de búsqueda por país (reunión con Yaco, 2026-10-01): en Perú manda el proveedor; en Chile y Colombia la cuenta
# contable; luego el texto. Sin proveedor -> cuenta.
ORDEN_PAIS = {'PERU': ('proveedor', 'texto', 'cuenta'), 'CHILE': ('cuenta', 'texto', 'proveedor'), 'COLOMBIA': ('cuenta', 'texto', 'proveedor')}
def destino_ch(n3, cuenta, texto, proveedor, pais=None):
    """(plantilla destino, regla, campo que decidió) de una fila de la base Regional C&H."""
    val = {'texto': sin_acentos(str(texto or '')).upper(), 'proveedor': sin_acentos(str(proveedor or '')).upper(),
           'cuenta': sin_acentos(str(cuenta or '')).upper()}
    campos = [(c, val[c]) for c in ORDEN_PAIS.get(str(pais or '').upper(), ('texto', 'proveedor', 'cuenta'))]
    for campo, val in campos:
        for rx, cat, regla in REGLAS_CH:
            if campo == 'cuenta' and cat == 'Consultorías' and rx is R_CONSULT_ADM: continue
            if rx.search(val): return DESTINOS[cat], regla, campo
    n3 = str(n3 or '')
    if n3.startswith('Asesorías Legales'): return 'Asesorías Legales', 'Nivel 3 de la base', 'nivel 3'
    if n3 == 'Dietas': return 'Consultorías', 'base dice Dietas sin directorio en texto/cuenta: honorarios -> Consultorías', 'nivel 3'
    if n3 == 'Auditorías Tributarias y Financieras': return 'Auditorías Tributarias y Financieras', 'Nivel 3 de la base', 'nivel 3'
    return 'Consultorías', 'Nivel 3 de la base', 'nivel 3'
