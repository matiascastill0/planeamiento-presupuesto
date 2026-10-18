"""Homologación de glosas y proveedores para OGP (Otros Gastos de Personal)."""
import re
from homologacion import sin_acentos, glosa_cuenta, es_sin_proveedor

GLOSA_OGP = {
    # Seguros y Salud
    'BENEFICIO EPS HIJOS MAYORES 18 AÑOS RELACIONADAS': 'Aporte EPS hijos mayores de 18', 'BENEFICIO SEGURO ONCOLOGICO': 'Seguro oncológico',
    'BENEFICIO SEGURO PADRE RELACIONADAS': 'Seguro de salud padres', 'BENEFICIO SEGURO SUEGROS RELACIONADAS': 'Seguro de salud suegros',
    'DESCUENTO BENEFICIO PLAN SALUD COMPENSAR': 'Plan complementario de salud', 'DESCUENTO BENEFICIO PLAN SALUD SURA': 'Plan complementario de salud',
    'Disability Insurance': 'Seguro de invalidez', 'Employee Benefits': 'Beneficios de salud y 401K', 'Insurance - Other': 'Seguro de invalidez',
    'OTROS BENEFICIOS - EXAMENES MÉDICOS': 'Exámenes médicos y salud ocupacional', 'POLIZA DE DIRECTORES Y ADMINISTRADORES': 'Seguro de salud colectivo',
    'Personnel - Medical and Life Insurance': 'Seguro médico y de vida', 'SALUD OCUPACIONAL': 'Exámenes médicos y salud ocupacional',
    'SAR': 'Aporte SAR (retiro)', 'SEGURO COMPLEMENTARIO DE TRABAJO RIESGO': 'SCTR (seguro complementario de trabajo de riesgo)',
    'SEGURO DE VIDA': 'Seguro de vida', 'SEGURO DE VIDA COLECTIVA': 'Seguro de vida colectivo', 'SEGUROS - EMPRESA AFILIADA': 'Seguro médico internacional gerentes',
    'SEGUROS PARTICULARES DE PRESTACIÓN DE SALUD - EPS EMPLEADOS RELACIONADAS': 'Aporte EPS colaboradores',
    'SEGUROS PARTICULARES DE PRESTACIÓN DE SALUD - PRACTICANTES': 'Seguro de salud practicantes', 'Seguros de Vida': 'Seguro de vida y médico colectivo',
    # Otros gastos de personal
    'AUXILIO VIVIENDA GARANTIZADO': 'Auxilio de vivienda (nómina)', 'Bonuses - Other': 'Bonos (relocalización y otros)', 'Bonuses - discretionary': 'Bonos discrecionales',
    'CONDICION DE TRABAJO ESPECIAL': 'Subvención condición de trabajo especial', 'CUOTA SOSTENIMIENTO': 'Cuota de sostenimiento aprendices',
    'DOTACION Y SUMINISTRO A TRABAJADORES': 'Dotación a colaboradores', 'EXPEDICION DE VISA': 'Trámite de visas', 'GRATIFICACIONES - EXTRAORDINARIA': 'Bono de retención',
    'IMSS CUOTA PATRONAL': 'Cuota patronal IMSS', 'INFONAVIT': 'Aporte INFONAVIT', 'OTRAS MODALIDADES DE CONTRATACIÓN': 'Practicantes y otras modalidades de contratación',
    'Otras modalidades de Contratación': 'Practicantes y otras modalidades de contratación', 'OTRAS REMUNERACIONES - SUBVENCIÓN': 'Subvención practicantes',
    'Personnel - Expatriate Others': 'Beneficios expatriados', 'Personnel - Miscellaneous': 'Otros gastos de personal', 'Personnel - Moving Expenses': 'Gastos de traslado y nómina',
    'OTROS GASTOS AL PERSONAL': 'Bono de retención',
    # Bienestar / eventos
    'CELEBRACION FIN DE MES BENEFICIOS A EMPLEADOS': 'Celebraciones de fin de mes', 'Celebraciones y Regalos Corporativos': 'Celebraciones y regalos',
    'Colaciones': 'Colaciones (alimentación)', 'EVENTOS': 'Eventos para colaboradores', 'EVENTOS CORPORATIVOS': 'Eventos para colaboradores',
    'MATERIAL CORPORATIVO': 'Material corporativo y kits', 'OBSEQUIO COLABORADORES': 'Obsequios y kits de bienvenida', 'OTROS BENEFICIOS': 'Otros beneficios',
    'OTROS BENEFICIOS A EMPLEADOS': 'Otros beneficios', 'Personnel - Benefits and Events': 'Beneficios y eventos', 'ATENCIÓN AL PERSONAL - RECREATIVOS': 'Actividades recreativas',
    'ATENCIÓN AL PERSONAL - OTROS': 'Atenciones al personal', 'OTROS SERVICIOS - GDH': 'Programa de asistencia al empleado',
    'SERVICIO DE DISEÑO GRAFICO': 'Diseño gráfico', 'OTROS GASTOS CULTURA Y COMUNICACIONES': 'Cultura y comunicación interna',
    'RELACIONES PÚBLICAS - EVENTOS': 'Eventos', 'SERVICIOS DE INFORMACIÓN': 'Campañas y servicios de información', 'SUSCRIPCIONES': 'Suscripciones y aportes',
    # Cultura
    'CAMPAÑAS DE COMUNICACIÓN': 'Campañas de comunicación interna', 'UTILES Y PAPELERIA': 'Material para colaboradores',
    # Consultoría / compensaciones / selección
    'ASESORÍAS RRRH': 'Plataforma de RR.HH. (Buk)', 'CONSULTORIAS GDH': 'Consultorías de gestión humana', 'ASESORIA Y CONSULTORIA - GDH': 'Consultoría de gestión humana',
    'ASESORIA Y CONSULTORIA - ADMINISTRATIVA': 'Consultoría de gestión humana', 'GESTION Y ADMINISTRACION DE NOMINA': 'Administración de nómina (outsourcing)',
    'Payroll': 'Administración de nómina (outsourcing)', 'Personnel - Compensation services': 'Servicios de compensación', 'Personnel - Other Fees': 'Administración de nómina (outsourcing)',
    'Personnel - Selection/Onboarding': 'Plataformas de selección', 'Recruiting': 'Reclutamiento', 'SELECCION DE PERSONAL': 'Selección de personal',
    'SELECCION DE PERSONAL (DIFERIDO)': 'LinkedIn Recruiter', 'SELECCIÓN': 'Selección de personal', 'Selección': 'Selección de personal',
    'CAPACITACIÓN TALENTO': 'Programas de talento y liderazgo', 'Capacitación Talento': 'Programas de talento y liderazgo',
    'GASTOS NO DEDUCIBLES': 'Extornos EPS', 'Other Expenses - Previous Years': 'Ajustes de ejercicios anteriores',
    'GESTIÓN - GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores', 'PROVISIONES DE GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS - EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores', 'OTROS INGRESOS - EJERCICIOS ANTERIORES PROVISIONES': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS - EXTORNO DE PROV EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores', 'OTROS SERVICIOS': 'Plataformas de selección',
}
GENERICAS = {'Otros beneficios', 'Atenciones al personal', 'Otros gastos de personal', 'Ajustes de ejercicios anteriores', 'Beneficios y eventos',
             'Consultoría de gestión humana', 'Campañas y servicios de información', 'Suscripciones y aportes', 'Cultura y comunicación interna',
             'Actividades recreativas', 'Eventos para colaboradores', 'Seguro de vida y médico colectivo', 'Seguro médico y de vida',
             'Beneficios de salud y 401K', 'Material corporativo y kits', 'Servicios de compensación', 'Gastos de traslado y nómina', 'Bonos (relocalización y otros)'}
REGLAS = [
    (r'OFFICE EXPENSES ?- ?PAYROLL', 'Nómina oficina Colombia (pagada desde USA)'),
    (r'MEDICO INTERNACIONAL', 'Seguro médico internacional ejecutivos'),
    (r'INTERNET BONUS', 'Bono de internet (trabajo remoto)'),
    (r'^\d\d/\d\d PAYROLL', 'Bonos pagados en nómina'),
    (r'RELOCATION', 'Bono de relocalización'),
    (r'^BONUS$', 'Bonos pagados en nómina'),
    (r'MOVING EXPENSES|MUDANZA', 'Gastos de mudanza'),
    (r'401K|MATCH', 'Aporte 401K'),
    (r'REEMBOLSO|REEM\b', 'Reembolsos a colaboradores'),
    (r'TCCORPORATIVA|TC CORPO|TARJETA CORPORATIVA|PAGO TC|GASTOS TC|LEG TC', 'Tarjeta corporativa'),
    (r'FIESTA|FIN DE A[NÑ]O|NAVIDAD|NAVIDE', 'Fiesta de fin de año y Navidad'),
    (r'DIA DE LA MADRE|DIA DEL PADRE|MADRES|PADRE', 'Día de la madre / del padre'),
    (r'ANIVERSARIO', 'Aniversarios laborales'),
    (r'KIT (DE )?BIENVENIDA|LANYARD|ONBOARDING', 'Kit de bienvenida'),
    (r'ASISTENCIA AL EMPLEADO|EAP', 'Programa de asistencia al empleado'),
    (r'NUTRICION|BIENESTAR|POSTRES SALUDABLES', 'Programa de bienestar'),
    (r'SEGURIDAD EN EL TRABAJO|SALUD OCUPACIONAL|EXAMEN|CHEQUEO', 'Exámenes médicos y salud ocupacional'),
    (r'ENCUESTA|MERCER|LEAD\b|LIDERAZGO', 'Encuestas y evaluación de liderazgo'),
    (r'MARCA EMPLEADORA|EMPLOYER', 'Marca empleadora'),
    (r'CATERING|REFRIGERIO|DESAYUNO|ALMUERZO|KICK OFF|DESPLIEGUE', 'Catering y eventos internos'),
    (r'PRACTICANTE|PRACTICA\b', 'Practicantes'),
    (r'PAN AMERICAN LIFE|POLIZA|SEGURO', 'Seguro médico y de vida'),
    (r'UNITED HEALTH|HEALTH', 'Seguro de salud'),
    (r'401K|MATCH', 'Aporte 401K'),
    (r'RELOCATION', 'Bono de relocalización'),
    (r'PLANILLA|PAYROLL|NOMINA', 'Administración de nómina (outsourcing)'),
    (r'CLUB DE GOLF', 'Membresía club (expatriados)'),
    (r'PRESTAMO', 'Préstamo a colaborador'),
    (r'CIBERSEGURIDAD', 'Campaña de ciberseguridad'),
    (r'REGALO|OBSEQUIO|GIFT', 'Regalos a colaboradores'),
    (r'TALLER|CAPACITACI|CURSO', 'Talleres para colaboradores'),
]
REGLAS = [(re.compile(r), g) for r, g in REGLAS]

def glosa_ogp(cuenta, texto):
    base = GLOSA_OGP.get(cuenta) or glosa_cuenta(cuenta)
    t = re.sub(r'\{.*?\}', ' ', sin_acentos(str(texto or '')).upper()).strip()
    if base in GENERICAS or re.search(r'REEMBOLSO|TCCORPORATIVA|TC CORPO|OFFICE EXPENSES ?- ?PAYROLL|MEDICO INTERNACIONAL|INTERNET BONUS', t):
        for rx, g in REGLAS:
            if rx.search(t):
                return g
    return base

# proveedor implícito en la cuenta cuando viene vacío
PROV_CUENTA = {'DESCUENTO BENEFICIO PLAN SALUD SURA': 'SURA (plan complementario)', 'DESCUENTO BENEFICIO PLAN SALUD COMPENSAR': 'COMPENSAR (plan complementario)'}
MARCAS_OGP = [(r'PAN AMERICAN LIFE', 'PAN AMERICAN LIFE INSURANCE'), (r'METLIFE', 'METLIFE CHILE SEGUROS DE VIDA S.A.'), (r'SODEXO', 'SODEXO'),
              (r'EDENRED|BIG PASS', 'BIG PASS EDENRED S.A.S.'), (r'HEINSOHN', 'HEINSOHN HUMAN GLOBAL SOLUCTIONS SAS'), (r'TAWA', 'TAWA CONSULTING S.A.C.'),
              (r'\bBUK\b', 'BUK SPA'), (r'PAYCHEX', 'Paychex'), (r'HIRINT', 'HIRINT GLOBAL, S.L'), (r'HIREIN', 'HIREIN CLOUD LLC'), (r'LINKEDIN|RECRUITER|JOB SLOTS', 'LINKEDIN IRELAND UNLIMITED COMPANY'),
              (r'MERCER', 'MERCER (COLOMBIA) LTDA SUCURSAL PERU'), (r'UNITED HEALTH', 'United Healthcare'), (r'ALLIANZ', 'ALLIANZ SEGUROS DE VIDA S.A'),
              (r'GALINDO', 'GALINDO, ARIAS Y LOPEZ'), (r'CLUB DE GOLF', 'CLUB DE GOLF'), (r'TECNOLOGIA APLICADA', 'TECNOLOGIA APLICADA')]
MARCAS_OGP = [(re.compile(r), p) for r, p in MARCAS_OGP]

def proveedor_ogp(homol, prov, texto, cuenta, glosa):
    if es_sin_proveedor(prov) or str(prov).strip().upper() in ('OTROS', 'PTY') or re.fullmatch(r'[\d\s\-/\.]+|ESA-[\d\s]+', str(prov).strip()):
        if cuenta in PROV_CUENTA:
            return PROV_CUENTA[cuenta]
        t = sin_acentos(str(texto or '')).upper()
        for rx, p in MARCAS_OGP:
            if rx.search(t):
                return homol.nombre(p)
        return homol.nombre(None, texto)
    n = homol.nombre(prov, texto)
    u = sin_acentos(n).upper()
    for rx, p in MARCAS_OGP:                 # misma marca escrita distinto -> un solo nombre
        if rx.search(u):
            return p
    return n
