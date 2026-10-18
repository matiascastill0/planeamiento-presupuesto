"""Glosas y proveedores para Tecnología y Comunicaciones."""
import re
from homologacion import sin_acentos, glosa_cuenta, es_sin_proveedor

GLOSA_TYC = {
    'Communication - Equipment and Others': 'Equipos de comunicaciones', 'Communication - Internet': 'Internet', 'Communication - Telephone': 'Telefonía',
    'Computer - IT Expenses': 'Gastos de TI', 'Computer - Maintenance': 'Mantención de equipos', 'Equipment Rental': 'Arriendo de equipos',
    'GASTOS DE IMPRESIÓN': 'Impresión y fotocopiado', 'MANTENIMIENTO DE FACILIDADES': 'Mantención de instalaciones TI', 'OTROS EQUIPOS MENORES': 'Equipos menores',
    'OTROS GASTOS CULTURA Y COMUNICACIONES': 'Comunicaciones internas', 'OTROS SERVICIOS - GDH': 'Plataformas de gestión humana', 'Personnel - Salaries and Wages': 'Personal TI (sueldos)',
    'RENTING DE EQUIPOS': 'Arriendo y leasing de equipos', 'Rent - Photocopier': 'Arriendo de fotocopiadoras', 'SERVICIO DE SUSCRIPCION POR CABLE': 'Televisión por cable',
    'SERVICIO DE TELEFONIA FIJA LD': 'Telefonía fija larga distancia', 'SERVICIOS BÁSICOS- CABLE': 'Televisión por cable', 'SERVICIOS DATACENTER': 'Servicios de datacenter',
    'SISTEMA SIGA ADMINISTRACIÓN ACTIVOS': 'Sistema SIGA (administración de activos)', 'SUELDO Y SALARIOS - BÁSICA': 'Personal TI (sueldos)',
    'SUMINISTROS INFORMÁTICOS': 'Suministros informáticos', 'TELÉFONOS': 'Telefonía',
    'Computer - Software': 'Software y aplicaciones', 'MANTENCIÓN DE SOFTWARE': 'Mantención de software', 'DESARROLLO DE SISTEMAS': 'Desarrollo de sistemas',
    'MANTENIMIENTO Y REPARACIÓN INTANGIBLES RELACIONADA': 'Mantención de software (relacionadas)', 'MANTENIMIENTO Y REPARACIÓN INTANGIBLES': 'Mantención de software',
    'CONSULTA INFORMACION APLICACIONES RELACIONADAS': 'Servicios aplicación Tyba', 'SERVICIOS DE INFORMACIÓN': 'Servicios de TI', 'MANTENIMIENTO EN APLICACIONES': 'Soporte y mantenimiento de aplicaciones',
    'MANTENIMIENTO EN APLICACIONES (DIRECTO)': 'Soporte y mantenimiento de aplicaciones', 'SUSCRIPCIONES': 'Suscripciones de software', 'ARRENDAMIENTO DE APLICATIVOS': 'Arriendo de aplicativos',
    'MANTENIMIENTO Y DESARROLLO TI': 'Desarrollo y mantenimiento TI', 'MANTENIMIENTO INFRAESTRUCTURA': 'Soporte de infraestructura', 'MANTENIMIENTO INFRAESTRUCTURA (DIRECTO)': 'Soporte de infraestructura',
    'CANALES WAN': 'Enlaces de datos (WAN)', 'SERVICIO DE TELEFONIA CELULAR': 'Telefonía celular', 'LÍNEAS DE ENLACES': 'Enlaces e internet', 'SERVICIO DE TELEFONIA LOCAL': 'Telefonía local e internet',
    'Communication - Swift': 'SWIFT', 'Telephone': 'Telefonía', 'INTERNET': 'Internet', 'LÍNEAS CAPÍTULOS': 'Telefonía local',
    'ASESORÍAS OTROS': 'Asesorías y proyectos TI', 'CONTRATO SOPORTE SERV. TI': 'Soporte TI (relacionadas)', 'SERVICIOS DE MONITOREO': 'Monitoreo de seguridad',
    'SERVICIO OUTSOURCING IT': 'Outsourcing TI', 'ARRENDAMIENTO EQUIPO DE COMPUTACION': 'Arriendo y leasing de equipos', 'ARRIENDO Y MANTENCIÓN DE HARDWARE': 'Arriendo y mantención de hardware',
    'ALQUILERES EQUIPOS COMPUTO': 'Arriendo de equipos de cómputo', 'SERVICIO DE IMPRESION Y FOTOCOPIADO': 'Impresión y fotocopiado',
    'SERVICIO DE SOPORTE RELACIONADAS': 'Servicios informáticos (relacionadas)', 'Dues and Subscriptions': 'Suscripciones de software', 'ARRIENDO Y MANTENCIÓN OTROS HARDWARES': 'Arriendo y mantención de hardware',
    'Data & Computer Services': 'Servicios de datos y cómputo', 'CARGO SERVICIO REUTERS': 'Refinitiv / Reuters', 'ASESORIA TECNICA': 'Asesoría técnica y proyectos',
    'MANTENIMIENTO Y REPARACIÓN DE EQUIPO - TECNOLOGIA': 'Equipos y mantención', 'OTROS SERVICIOS RELACIONADOS': 'Servicios informáticos (relacionadas)',
    'MANTENIMIENTO Y REPARACIÓN TI': 'Mantención TI', 'GASTOS NO DEDUCIBLES': 'Gastos no deducibles', 'SERVICIO DE INFORMACION BURSATIL': 'Información bursátil',
    'OTROS GASTOS BOLSA DE COMERCIO': 'Pantallas y terminales de bolsa', 'CARGO ARRENDAMIENTO BLOOMBERG': 'Terminales Bloomberg', 'GASTOS BLOOMBERG': 'Terminales Bloomberg',
    'OTRAS LICENCIAS TI': 'Licencias de software', 'CARGO SERVICIO BLOOMBERG': 'Servicios Bloomberg (datos)', 'DERECHOS COBRADOS BOLSA DE COMERCIO': 'Derechos de bolsa',
    'GASTOS BOLSA ELECTRONICA': 'Derechos Bolsa Electrónica', 'CERTIFICADO DIGITAL': 'Certificados digitales', 'OTRAS RECUPERACIONES': 'Recuperación de provisiones',
    'LIQUIDACION DE OTROS PASIVOS': 'Liquidación de otros pasivos',
    'GESTIÓN - GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores', 'PROVISIONES DE GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS - EJERCICIOS ANTERIORES PROVISIONES': 'Ajustes de ejercicios anteriores', 'OTROS INGRESOS - EXTORNO DE PROV EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'Other Expenses - Previous Years': 'Ajustes de ejercicios anteriores', 'OTROS INGRESOS': 'Otros ingresos',
}
# Reglas por texto (servicio concreto). Se aplican a todas las cuentas salvo ajustes contables específicos.
REGLAS = [
    (r'AZURE', 'Consumo Azure'),
    (r'COPILOT', 'Licencias Microsoft Copilot'),
    (r'M365|M3 ?65|O365|OFFICE ?365|UNIFIED FSA|MICROSOFT|TEAMS ROOM|DEFENDER', 'Licencias Microsoft 365'),
    (r'BLOOMBERG ANYWHERE|BLOOMBERG TERMINAL|LICENCIAS BLOOMBERG|\bTOMS\b', 'Terminales Bloomberg'),
    (r'REFINITIV|REUTERS|WORKSPACE BILLING', 'Refinitiv / Reuters'),
    (r'TEMENOS|\bT24\b', 'Temenos (core bancario)'),
    (r'INTELLECT', 'Intellect (mantención y soporte)'),
    (r'CALYPSO', 'Calypso (upgrade y soporte)'),
    (r'MULTIFONDS', 'Multifonds (soporte)'),
    (r'ADDEPAR', 'Addepar'),
    (r'ADENZA|ANNUAL FEE INCLUDES', 'Adenza (licencia anual)'),
    (r'SALESFORCE', 'Salesforce'),
    (r'ORACLE', 'Oracle (licencias y soporte)'),
    (r'ARRIENDO PANTALLA|TERMINAL NEGOCIACION|NUAM', 'Pantallas y terminales de bolsa'),
    (r'DERECHOS DE BOLSA|REMATE ELECTRONICO', 'Derechos de bolsa'),
    (r'LEASING|DAAS|RENTING|ARRENDAMIENTO DE EQUIPOS|ALQUILER DE (PCS|EQUIPOS)|ARRIENDO DESKTOPS', 'Arriendo y leasing de equipos'),
    (r'IAAS|DRAAS|BACKUP', 'Infraestructura en la nube y backup'),
    (r'ETHICAL|PENTEST|CIBERSEG|CYBERSOC|SEGURIDAD DE LA INFORMACI|CSIRT|ANALISTA DE SEGURIDAD|SOPHOS|VULNERABILIDAD', 'Ciberseguridad'),
    (r'MESA DE SERVICIOS|MESA DE AYUDA|HELP ?DESK|SOPORTE NIVEL', 'Mesa de servicios y soporte'),
    (r'DEVOPS|STAFFING', 'DevOps y staffing TI'),
    (r'DESARROLLO|\bRFC\b|\bODS\b', 'Desarrollo de software'),
    (r'MPLS|IPVPN|ENLACE|CIRCUITO|DATACENTER', 'Enlaces de datos (WAN)'),
    (r'CELULAR', 'Telefonía celular'),
    (r'INTERNET', 'Internet'),
    (r'SWIFT', 'SWIFT'),
    (r'SERVICIOS INFORM[AÁ]TICOS|PRIMERA L[IÍ]NEA DE DEFENSA|FLUJO DE INTERCAMB', 'Servicios informáticos (relacionadas)'),
    (r'TYBA', 'Servicios aplicación Tyba'),
    (r'SOPORTE D&A|DATA GOVERNANCE|GOBIERNO DE DATOS|FINOPS', 'Datos y analítica'),
    (r'IMPRESI|PRINTING|FOTOCOPI', 'Impresión y fotocopiado'),
    (r'CERTIFICADO', 'Certificados digitales'),
]
REGLAS = [(re.compile(r), g) for r, g in REGLAS]
SIN_REGLA = {'Recuperación de provisiones', 'Liquidación de otros pasivos', 'Gastos no deducibles', 'Otros ingresos'}

def glosa_tyc(cuenta, texto):
    base = GLOSA_TYC.get(cuenta) or glosa_cuenta(cuenta)
    if base in SIN_REGLA:
        return base
    t = re.sub(r'\{.*?\}', ' ', sin_acentos(str(texto or '')).upper())
    for rx, g in REGLAS:
        if rx.search(t):
            return g
    return base

MARCAS = [(r'MICROSOFT', 'MICROSOFT'), (r'BLOOMBERG', 'BLOOMBERG'), (r'REFINITIV|REUTERS', 'REFINITIV'), (r'ORACLE', 'ORACLE'), (r'TEMENOS', 'TEMENOS'),
          (r'HEWLETT|^HP INC|HP INC ', 'HP'), (r'NTT DATA', 'NTT DATA'), (r'TATA CONSULTANCY|^TCS ', 'TATA CONSULTANCY SERVICES (TCS)'), (r'GFT TECHNOLOGIES', 'GFT TECHNOLOGIES'),
          (r'KYNDRYL', 'KYNDRYL'), (r'SOLUCIONES EN BASES? DE DATOS', 'SOLUCIONES EN BASES DE DATOS SBD'), (r'DIGISOC', 'DIGISOC'), (r'BELLTECH|BELL TECHNOLOGIES', 'BELLTECH'),
          (r'COMCEL|COMUNICACION CELULAR', 'CLARO (COMCEL)'), (r'NUAM|HOLDING BURSATIL', 'NUAM (Holding Bursátil Regional)'), (r'ZYTRUST', 'ZYTRUST'),
          (r'DELCOP', 'DELCOP COLOMBIA'), (r'MILENIO PC', 'MILENIO PC'), (r'TSOFT', 'TSOFT PERU'), (r'INTELLECT', 'INTELLECT DESIGN ARENA'), (r'I T C SOLUCIONES', 'ITC SOLUCIONES TECNOLOGICAS'),
          (r'CLEVER IT', 'CLEVER IT'), (r'ADENZA', 'ADENZA'), (r'ADDEPAR', 'ADDEPAR'), (r'SALESFORCE', 'SALESFORCE'), (r'DAVINCI', 'DAVINCI TECHNOLOGIES'),
          (r'CAPITALTEC', 'CAPITALTEC'), (r'GTD', 'GTD'), (r'TELEFONICA', 'TELEFONICA'), (r'INTEGRATEL', 'INTEGRATEL PERU'), (r'ENTEL', 'ENTEL'),
          (r'BANCO DE CR[EÉ]DITO DEL PER[UÚ]', 'BANCO DE CREDITO DEL PERU'), (r'CREDICORP NEGOCIOS DIGITALES', 'CREDICORP NEGOCIOS DIGITALES'),
          (r'EMPRESA DE TELECOMUNICACIONES', 'ETB (EMPRESA DE TELECOMUNICACIONES DE BOGOTA)'), (r'SONDA', 'SONDA'), (r'RICOH', 'RICOH')]
MARCAS = [(re.compile(r), p) for r, p in MARCAS]

CUENTAS_VARIOS = {'AJUSTE AL MIL', 'LIQUIDACION DE OTROS PASIVOS', 'OTRAS RECUPERACIONES'}

def proveedor_tyc(homol, prov, texto, cuenta, glosa):
    if es_sin_proveedor(prov) or str(prov).strip().upper() in ('OTROS', 'PTY', 'NA') or re.fullmatch(r'[\d\s\-/\.]+', str(prov).strip()):
        n = homol.nombre(None, texto)
        if n == '(sin proveedor)':
            t = sin_acentos(str(texto or '')).upper()
            for rx, p in MARCAS:
                if rx.search(t): return p
        return n
    n = homol.nombre(prov, texto)
    u = sin_acentos(n).upper()
    for rx, p in MARCAS:
        if rx.search(u): return p
    return n
