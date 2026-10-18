"""Glosas y proveedores para CS Administrativo (servicios entre empresas del grupo)."""
import re
from homologacion import sin_acentos, glosa_cuenta

GLOSA_CS = {
    '0': 'Servicio de soporte', '(sin dato)': 'Servicio de soporte', 'OTROS INGRESOS POR SERVICIOS RELACIONADOS': 'Ingreso por research a relacionadas',
    'SERVICIO DE SOPORTE RELACIONADAS': 'Servicio de soporte', 'COSTO SOPORTE RELACIONADAS': 'Servicio de soporte', 'CONTRATO SOPORTE RELACIONADAS': 'Soporte administrativo',
    'CONTRATO SOPORTE SERV. ADM': 'Servicios a demanda (riesgos, auditoría, legal, data)', 'Contrato Soporte': 'Soporte BCP (indirecto)',
    'Consultants - Related parties': 'Servicio de soporte', 'Consultants-Soporte CC Col-Ofic Rep': 'Gastos oficina de representación Colombia (ASB)',
    'Other Pro Fees - Affiliates': 'Servicio de soporte', 'Expense Sharing - Affiliate': 'Expense sharing con afiliadas', 'ASESORIAS HONORARIOS RELACIONADAS': 'Asesorías con relacionadas',
    'ASESORIA TECNICA RELACIONADA': 'Servicios profesionales especializados', 'ASESORIA TECNICA RELACIONADAS': 'Servicios profesionales especializados',
    'ASESORIAS HONORARIOS': 'Asesorías', 'CHAPERONING': 'Chaperoning', 'COMISION OTROS RELACIONADAS -EXTERIOR': 'Servicios a relacionadas del exterior',
    'COMISION RESEARCH - RELACIONADAS': 'Ingreso por research a relacionadas', 'COMISION RESEARCH RFPNG - RELACIONADAS': 'Ingreso por research a relacionadas',
    'CONSULTA INFORMACION APLICACIONES RELACIONADAS': 'Servicios aplicación Tyba', 'CUOTA DE ADMINISTRACION': 'Reembolso cuota de administración',
    'GASTOS NO DEDUCIBLES': 'Cobranza entre relacionadas', 'SUSCRIPCIONES RELACIONADAS': 'Soporte de software (Negocios Digitales)',
    'REEXPRESION DE ACTIVOS ADMINISTRATIVOS': 'Diferencia de cambio (reexpresión)', 'REEXPRESION DE RELACIONADAS': 'Diferencia de cambio (reexpresión)',
    'SERVICIO DE MERCADO DE CAPITALES RELACIONADAS': 'Servicio de mercado de capitales a relacionadas', 'SERVICIO DE SOPORTE CON NO VINCULADOS': 'Servicio de soporte a no vinculados',
    'SERVICIO DE SOPORTE RELACIONADAS - EXPORTACIÓN': 'Ingreso por soporte a relacionadas (exportación)', 'OTROS INGRESOS POR SERVICIOS RELACIONADAS - EXPORTACIÓN': 'Ingreso por servicios a relacionadas (exportación)',
    'OTROS INGRESOS POR SERVICIOS RELACIONADAS': 'Ingreso por servicios a relacionadas', 'OTROS INGRESOS POR SERVICIOS RELACIONADA': 'Ingreso por servicios a relacionadas',
    'OTROS INGRESOS POR SERVICIOS RELACIONADOS ': 'Ingreso por research a relacionadas', 'OTROS INGRESOS - SERVICIOS ADICIONALES (AFILIADA)': 'Ingreso por servicios adicionales a afiliadas',
    'OTROS INGRESOS': 'Provisión de proyectos', 'REALIZACION DE OTROS ACTIVOS': 'Realización de otros activos',
    'GESTIÓN - GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores', 'PROVISIONES DE GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'PROVISIONES DE GASTOS DE EJERCICIOS ANTERIORES ': 'Ajustes de ejercicios anteriores', 'OTROS INGRESOS - EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS - EJERCICIOS ANTERIORES PROVISIONES': 'Ajustes de ejercicios anteriores', 'OTROS INGRESOS - EXTORNO DE PROV EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS - EJERCICIOS ANTERIORES INGRESOS DIVERSOS': 'Ajuste servicio de soporte regional', 'Other Expenses - Previous Years': 'Ajustes de ejercicios anteriores',
}
GENERICAS = {'Servicio de soporte', 'Servicios profesionales especializados', 'Ajustes de ejercicios anteriores', 'Asesorías con relacionadas', 'Provisión de proyectos',
             'Soporte administrativo', 'Ingreso por servicios a relacionadas', 'Expense sharing con afiliadas'}
REGLAS = [
    (r'SERVICIOS? ADICIONALES|ADICIONALES', 'Servicios adicionales'),
    (r'SOPORTE REGIONAL|ASESOR[IÍ]A REGIONAL', 'Soporte regional'),
    (r'OPERATIVO VARIABLE|\+ ?VARIABLE|SOPORTE VARIABLE', 'Servicio de soporte + variable'),
    (r'PROFESIONALES ESPECIALIZADOS', 'Servicios profesionales especializados'),
    (r'RESEARCH|ESTUDIOS DE MERCADO', 'Servicio de research'),
    (r'NUAM|REDWOOD', 'Proyecto NUAM / Redwood'),
    (r'RYDOO|WORKVIVO|CUENTAS INT', 'Proyectos Rydoo / Workvivo / Cuentas internas'),
    (r'MDK', 'Proyecto MDK'),
    (r'CAPITAL LAB|CANAL DIGITAL', 'Proyecto Capital Lab / Canal Digital'),
    (r'VIAJE', 'Reembolso de viajes asesoría regional'),
    (r'COMMUNICATION', 'Comunicaciones compartidas'),
    (r'SOPORTE ADMINISTRATIVO|SOPORTE ADMON|SERVICIOS ADMINISTRATIVOS', 'Soporte administrativo'),
    (r'SERVICIOS? INFORM[AÁ]TICOS', 'Servicios informáticos'),
    (r'SERVICIO DE SOPORTE|SOPORTE', 'Servicio de soporte'),
    (r'IMPORTACI[OÓ]N DE ASIENTOS', 'Asientos de distribución entre relacionadas'),
    (r'RECLASIFICACI', 'Reclasificación contable'),
]
REGLAS = [(re.compile(r), g) for r, g in REGLAS]

def glosa_cs(cat, cuenta, texto):
    base = GLOSA_CS.get(cuenta) or glosa_cuenta(cuenta)
    if base not in GENERICAS:
        return base
    t = re.sub(r'\{.*?\}', ' ', sin_acentos(str(texto or '')).upper())
    for rx, g in REGLAS:
        if rx.search(t):
            return g
    return base

PROV_DEFECTO = {'BCP': 'BANCO DE CREDITO DEL PERU', 'Indirecto BCP': 'BANCO DE CREDITO DEL PERU', 'CCS': 'CREDICORP CAPITAL SERVICIOS SAS',
                'CCSF': 'CREDICORP CAPITAL SERVICIOS FINANCIEROS S.A.', 'GC': 'GRUPO CREDITO S.A.'}
