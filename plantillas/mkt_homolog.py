"""Glosas y proveedores para Marketing."""
import re
from homologacion import sin_acentos, glosa_cuenta, es_sin_proveedor

GLOSA_MKT = {
    'AGENCIA CREATIVA': 'Agencia creativa y comunicación estratégica', 'AJUSTE AL MIL': 'Ajuste al mil', 'ASESORIA TECNICA': 'Consultoría de comunicaciones',
    'ASESORIA Y CONSULTORIA - ADMINISTRATIVA': 'Agencia de marketing', 'ATENCIÓN AL PERSONAL - OTROS': 'Premios y atenciones campañas comerciales',
    'ATENCIÓN AL PERSONAL - RECREATIVOS': 'Eventos y talleres de marca', 'AUSPICIOS': 'Auspicios y patrocinios', 'AUSPICIOS/PATROCINIOS': 'Auspicios y patrocinios',
    'AVISOS Y PUBLICACIONES': 'Avisos y contenido audiovisual', 'CAMPAÑAS PUBLICITARIAS': 'Campañas publicitarias', 'CONGRESOS': 'Patrocinio de congresos',
    'ESTUDIOS DE IMAGEN': 'Estudios de imagen y medición de marca', 'EVENTOS': 'Eventos con clientes', 'EVENTOS CORPORATIVOS': 'Eventos corporativos',
    'FIDELIZACIÓN Y CAPTACIÓN DE CLIENTES': 'Fidelización y eventos con clientes', 'GASTOS DE REPRESENTACION': 'Regalos a clientes',
    'GASTOS NO DEDUCIBLES': 'Reclasificación de reembolsos', 'GESTIÓN - GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'INTERESES DE MORA': 'Intereses de mora', 'LIQUIDACION DE OTROS PASIVOS': 'Diferencia en cambio facturas', 'MATERIAL CORPORATIVO': 'Merchandising',
    'Marketing': 'Marketing', 'OTRAS RECUPERACIONES': 'Recuperación de provisiones', 'OTROS BENEFICIOS A EMPLEADOS': 'Reclasificación de provisiones',
    'OTROS GASTOS CULTURA Y COMUNICACIONES': 'Redes sociales y consumo de medios', 'OTROS INGRESOS': 'Reversa de provisiones',
    'OTROS INGRESOS - EJERCICIOS ANTERIORES PROVISIONES': 'Ajustes de ejercicios anteriores', 'OTROS INGRESOS - EXTORNO DE PROV EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'OTROS SERVICIOS': 'Talleres y servicios de marca', 'PARQUEADEROS': 'Estacionamientos', 'POSICIONAMIENTO DE MARCA': 'Posicionamiento de marca',
    'PRENSA': 'Prensa y relacionamiento con medios', 'PROVISIONES DE GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores', 'PUBLICIDAD': 'Publicidad',
    'REGALOS': 'Regalos a clientes', 'REGALOS A CLIENTES': 'Regalos a clientes', 'RELACIONES PÚBLICAS - EVENTOS': 'Eventos y relaciones públicas',
    'SERVICIOS DE INFORMACIÓN': 'Soporte digital y licencias', 'SUSCRIPCIONES': 'Suscripciones y fee de agencia',
}
# Reglas por texto: eventos y campañas emblemáticas (aplican siempre, tienen prioridad)
FUERTES = [
    (r'INVESTOR CONFERENCE|INVERSOR CONFERENS|CONFERENCISTA|KN SPEAKER|SPEAKER', 'Investor Conference'),
    (r'EUROMONEY', 'Premios Euromoney'),
    (r'AM DAY|ASSET MANAGEMENT CONFERENCE', 'AM Day / Asset Management Conference'),
    (r'CHILE DAY', 'Chile Day'),
    (r'FORMULA|MOTORSPORT|\bF1\b', 'Fórmula 1 (evento clientes)'),
    (r'CUMPLEA', 'Campaña cumpleaños clientes'),
    (r'NAVIDAD|FIN DE A[NÑ]O', 'Regalos y eventos de fin de año'),
    (r'DIA DEL PADRE|DIA DE LA MADRE', 'Día de la madre / del padre'),
    (r'RESEARCH', 'Conferencias de Research'),
]
DEBILES = [  # sólo cuentas genéricas
    (r'REDES SOCIALES|SOCIAL MEDIA|COMMUNITY', 'Gestión de redes sociales'),
    (r'CONSUMO DE MEDIOS|OSUMO DE MEDIOS|PAUTA|CAMPA[NÑ]A DIGITAL', 'Pauta y consumo de medios'),
    (r'FEE DE AGENCIA|LINKEDIN', 'Fee de agencia (LinkedIn)'),
    (r'STAND|CONGRESO', 'Stand en congresos'),
    (r'AUSPICIO|PATROCINI|SPONSOR', 'Auspicios y patrocinios'),
    (r'AUDIOVISUAL|VIDEOCAST|VODCAST', 'Contenido audiovisual'),
    (r'MERCHANDISING|INVENTARIO', 'Merchandising'),
    (r'GIFT CARD|TARJETAS REGALO|PREMIO', 'Premios y gift cards'),
    (r'TALLER DE MARCA|MARCA', 'Talleres de marca'),
    (r'CATERING|CENA|ALMUERZO', 'Catering eventos'),
    (r'AMORTIZ|PPD', 'Amortización gastos prepagados'),
    (r'REEMBOLSO', 'Reembolsos de gastos de marketing'),
    (r'LICENCIA|SSL|BITLY|APPLE', 'Licencias digitales'),
    (r'EVENTO', 'Eventos con clientes'),
]
FUERTES = [(re.compile(r), g) for r, g in FUERTES]; DEBILES = [(re.compile(r), g) for r, g in DEBILES]
GENERICAS = {'Marketing', 'Publicidad', 'Eventos y relaciones públicas', 'Suscripciones y fee de agencia', 'Agencia de marketing',
             'Redes sociales y consumo de medios', 'Talleres y servicios de marca', 'Fidelización y eventos con clientes', 'Posicionamiento de marca',
             'Campañas publicitarias', 'Eventos con clientes', 'Avisos y contenido audiovisual', 'Auspicios y patrocinios', 'Premios y atenciones campañas comerciales',
             'Ajustes de ejercicios anteriores', 'Prensa y relacionamiento con medios'}

def glosa_mkt(cuenta, texto):
    base = GLOSA_MKT.get(cuenta) or glosa_cuenta(cuenta)
    t = re.sub(r'\{.*?\}', ' ', sin_acentos(str(texto or '')).upper())
    for rx, g in FUERTES:
        if rx.search(t): return g
    if base in GENERICAS:
        for rx, g in DEBILES:
            if rx.search(t): return g
    return base

def proveedor_mkt(homol, prov, texto, cuenta, glosa):
    if glosa in ('Reclasificación de reembolsos',):
        return '(sin proveedor)'
    if es_sin_proveedor(prov) or re.fullmatch(r'[\d\s\-/\.]+', str(prov).strip()):
        return homol.nombre(None, texto)
    return homol.nombre(prov, texto)
