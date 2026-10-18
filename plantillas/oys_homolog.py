"""Glosas y sede para Oficinas y Suministros (BAU / NIIF / Seguros)."""
import re
from homologacion import sin_acentos, glosa_cuenta

GLOSA_OYS = {
    # Alquiler de oficinas
    'ALQUILER DE OFICINAS - RELACIONADAS': 'Arriendo de oficinas (relacionadas)', 'ALQUILERES EDIFICACIONES TERCEROS': 'Arriendo de oficinas',
    'ARRENDAMIENTOS RELACIONADAS': 'Arriendo de oficinas (relacionadas)', 'ARRIENDOS DE ESTACIONAMIENTOS': 'Arriendo de estacionamientos',
    'ARRIENDOS DE OFICINAS': 'Arriendo de oficinas', 'ARRIENDOS RECIBIDOS': 'Subarriendo recibido', 'ASESORIA TECNICA': 'Asesoría técnica de arquitectura',
    'INTERESES SUBARRENDAMIENTO AFILIADA': 'Intereses de subarriendo', 'OTROS ALQUILERES - RELACIONADA': 'Otros arriendos (relacionadas)',
    'Rent': 'Arriendo de oficinas', 'Rent - Miami': 'Arriendo oficina Miami', 'Rent - Miami Interest': 'Intereses arriendo Miami',
    'Rent - Miscellaneous': 'Otros gastos de arriendo', 'Rent - Premises': 'Arriendo de oficinas', 'Rent Expense': 'Arriendo de oficinas',
    'Rent Expense - Colombia': 'Arriendo oficina Colombia', 'Rent Expense - Miami': 'Arriendo oficina Miami',
    'Rent Expense - Miami Interest': 'Intereses arriendo Miami', 'Rent Expense - Other': 'Otros arriendos',
    # Apertura y cierre
    'ARBITRIOS MUNICIPALES Y SEGURIDAD CIUDADANA': 'Arbitrios municipales', 'PATENTES COMERCIALES': 'Patentes municipales',
    # Gastos comunes
    'ASEOS DE OFICINAS': 'Aseo de oficinas', 'Advertising': 'Publicidad', 'CANALES WAN': 'Canales WAN', 'CONSUMO GAS NATURAL': 'Gas natural',
    'CUOTA DE ADMINISTRACION': 'Cuota de administración del edificio', 'Cable': 'Televisión por cable', 'ELECTRICIDAD': 'Energía eléctrica',
    'ELEMENTOS DE ASEO Y CAFETERIA': 'Elementos de aseo y cafetería', 'GASTOS COMUNES': 'Gastos comunes del edificio',
    'Maintenance - Light': 'Energía eléctrica', 'Maintenance - Office Cleaning': 'Aseo de oficinas',
    'OTROS SERVICIOS - ESTACIONAMIENTO': 'Estacionamientos', 'OTROS SERVICIOS- VIGILANCIA Y PROTECCIÓN PRIVADA': 'Vigilancia y seguridad',
    'Office Expense': 'Gastos de oficina', 'Office Expenses': 'Gastos de oficina', 'PARQUEADEROS': 'Estacionamientos', 'Parking': 'Estacionamientos',
    'Personnel - Staff Parking': 'Estacionamientos del personal', 'SERVICIO DE ACUEDUCTO': 'Agua (acueducto)', 'SERVICIO DE ASEO': 'Aseo de oficinas',
    'SERVICIO DE ASISTENCIA TECNICA DOCUMENTOS': 'Administración de centro documental', 'SERVICIO DE ENERGIA': 'Energía eléctrica',
    'SERVICIO DE FUMIGACION': 'Fumigación', 'SERVICIO DE LAVANDERIA': 'Lavandería', 'SERVICIO DE SUSCRIPCION POR CABLE': 'Televisión por cable',
    'SERVICIO DE VIDEOLINEAS': 'Servicio de videolíneas', 'SERVICIO MONITOREO Y ALARMA': 'Monitoreo y alarmas', 'SERVICIO VIGILANCIA': 'Vigilancia y seguridad',
    'SERVICIOS BÁSICOS - ENERGIA ELÉCTRICA': 'Energía eléctrica', 'SERVICIOS DE INFORMACIÓN': 'Servicios de información', 'SISTEMAS DE ALARMAS': 'Monitoreo y alarmas',
    # Mantenimiento
    'ACCESORIOS ADECUACIONES INSTALACIONES ELECTRICAS': 'Adecuaciones eléctricas', 'ACCESORIOS MATENIMIENTO EQUIPO DE OFICINA': 'Mantenimiento de equipos de oficina',
    'ADECUACION DE OFICINAS': 'Adecuación de oficinas', 'ADECUACIONES INSTALACIONES ELECTRICAS': 'Adecuaciones eléctricas',
    'ASESORIA Y CONSULTORIA - ADMINISTRATIVA': 'Asesoría de mantenimiento', 'Computer Repairs': 'Reparación de equipos',
    'MANTENIMIENTO AIRE ACONDICIONADO': 'Mantenimiento de aire acondicionado', 'MANTENIMIENTO EQUIPO DE OFICINA': 'Mantenimiento de equipos de oficina',
    'MANTENIMIENTO FACILITIES': 'Mantenimiento de instalaciones', 'MANTENIMIENTO INFRAESTRUCTURA (DIRECTO)': 'Mantenimiento de infraestructura',
    'MANTENIMIENTO Y REPARACIONES INMOBILIARIA': 'Mantenimiento del inmueble', 'MANTENIMIENTO Y REPARACIONES INMOBILIARIAS-AFILIADAS': 'Mantenimiento del inmueble (relacionadas)',
    'MATERIAL DE MANTENIMIENTO': 'Materiales de mantenimiento', 'Maintenance - Furniture and Equipment': 'Mantenimiento de muebles y equipos',
    'Maintenance - Miscellaneous': 'Mantenimiento varios', 'Maintenance - Premises': 'Mantenimiento del inmueble',
    'OTROS INGRESOS POR SERVICIOS RELACIONADA': 'Recupero de mantenimiento (relacionadas)', 'REPARACIONES OFICINAS Y/O LOCATIVAS': 'Reparaciones locativas',
    'REPARACIÓN MUEBLES': 'Reparación de muebles', 'REPARACIÓN Y MANTENCIÓN DE OFICINAS': 'Mantenimiento de oficinas', 'SUSCRIPCIONES': 'Soporte y mantenimiento anual',
    # Otros gastos de administración
    'ARREGLOS FLORALES': 'Arreglos florales', 'AVALUO COMERCIAL': 'Avalúo comercial', 'CHEQUERAS Y OTROS': 'Chequeras', 'CONSTRUCCIONES Y EDIFICACIONES': 'Baja de activos (construcciones)',
    'CORREO, PORTES Y TELEGRAMAS': 'Correo', 'GASTOS DE REPRESENTACION': 'Gastos de representación', 'GESTIÓN - GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'Miscellaneous': 'Gastos varios', 'OTRAS': 'Gastos varios', 'OTRAS RECUPERACIONES': 'Recuperación de provisiones', 'OTROS EQUIPOS MENORES': 'Equipos menores',
    'OTROS GASTOS': 'Gastos varios', 'OTROS GASTOS DE ADMINISTRACIÓN': 'Otros gastos de administración', 'OTROS GASTOS FINANCIEROS': 'Otros gastos financieros',
    'OTROS GASTOS POR SERVICIOS RELACIONADAS': 'Servicios con relacionadas', 'OTROS INGRESOS': 'Otros ingresos',
    'OTROS INGRESOS - EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores', 'OTROS INGRESOS - EJERCICIOS ANTERIORES PROVISIONES': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS - EXTORNO DE PROV EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores', 'PROVISIONES DE GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS DIVERSOS': 'Otros ingresos', 'OTROS SERVICIOS': 'Otros servicios', 'Other Expenses - Previous Years': 'Ajustes de ejercicios anteriores',
    'Other Expenses - Small Items Assets & Books': 'Activos menores y libros', 'POR REEXPRESION DE PASIVOS ADMINISTRATIVOS': 'Diferencia de cambio (reexpresión)',
    'REEXPRESION DE PASIVOS ADMINISTRATIVOS': 'Diferencia de cambio (reexpresión)', 'POR VENTA DE EQUIPO DE COMPUTACION': 'Venta de equipos',
    'POR VENTA DE EQUIPO ELECTRONICO': 'Venta de equipos', 'Postage and Delivery': 'Correo y envíos', 'RELACIONES PÚBLICAS - EVENTOS': 'Eventos',
    # Útiles
    '(blank)': 'Útiles de oficina', 'ARTÍCULOS DE OFICINAS': 'Útiles de oficina', 'CONSUMO DE COCINA': 'Cafetería y cocina', 'Equipment': 'Equipos menores',
    'OTROS GASTOS CULTURA Y COMUNICACIONES': 'Material de comunicaciones', 'OTROS PRODUCTOS': 'Otros productos', 'OTROS SERVICIOS - GDH': 'Útiles de gestión humana',
    'OTROS SERVICIOS IMPRESIÓN Y EMPASTE': 'Impresión y empaste', 'Office Supplies': 'Útiles de oficina', 'SERVICIO DE IMPRESION Y FOTOCOPIADO': 'Impresión y fotocopiado',
    'SUMINISTROS': 'Útiles de oficina', 'Stationery - Office Supplies': 'Útiles de oficina', 'TELEFONOS': 'Teléfonos', 'UTILES Y PAPELERIA': 'Útiles y papelería',
    # NIIF 16
    'ARRENDAMIENTO OFICINAS': 'Canon de arrendamiento', 'Cost of Finance Lease Asset': 'Costo arrendamiento financiero',
    'DEPRECIACION PPE DERECHO DE USO OFICINA': 'Depreciación derecho de uso', 'DEPRECIACION PPE DERECHO DE USO OFICINA - RELACIONADAS': 'Depreciación derecho de uso (relacionadas)',
    'DEPRECIACIÓN ACTIVO POR DERECHO DE USO': 'Depreciación derecho de uso', 'Depreciation - Right of Use Assets': 'Depreciación derecho de uso',
    'DIFERENCIA EN CAMBIO NIIF 16 - RELACIONADAS': 'Diferencia de cambio NIIF 16', 'DIFERENCIA EN CAMBIO NIIF 16': 'Diferencia de cambio NIIF 16',
    'GASTO FINANCIERO ARRENDAMIENTO': 'Intereses pasivo por arrendamiento', 'GASTO INTERESES SOBRE LOS PASIVOS ARRENDAMIENTOS OFICINA': 'Intereses pasivo por arrendamiento',
    'GASTO INTERESES SOBRE LOS PASIVOS ARRENDAMIENTOS OFICINA- RELACIONADA': 'Intereses pasivo por arrendamiento (relacionadas)',
    'GASTO POR INTERÉS ARRENDAMIENTO FINANCIERO': 'Intereses pasivo por arrendamiento', 'MANTENIMIENTO INFRAESTRUCTURA': 'Cuota de mantenimiento y aseo del edificio',
    'OTRAS RECUPERACIONES NIIF 16': 'Recuperación NIIF 16', 'OTRAS RECUPERACIONES NIIF 16 - BAJA DE ARRENDAMIENTO': 'Baja de arrendamiento NIIF 16',
    'REVERSION GASTO ARRENDAMIENTO NIIF 16 - RELACIONADAS': 'Reversión de arriendo por NIIF 16', 'REVERSIÓN GASTO POR ALQUILER APLIACIÓN NIIF 16': 'Reversión de arriendo por NIIF 16',
    # Seguros (glosa base; el texto precisa el tipo de póliza)
    'BENEFICIO SEGURO ONCOLOGICO': 'Seguro oncológico', 'Disability Insurance': 'Seguro de invalidez', 'Insurance - Blanket Bonds': 'Póliza 3B (Bankers Blanket Bond)',
    'Insurance - General Bank Policy': 'Póliza bancaria general', 'Insurance - Miscellaneous': 'Seguros corporativos', 'Insurance - Other': 'Seguros corporativos',
    'Insurance Expense': 'Seguros corporativos', 'Insurance Expense - Other': 'Seguros corporativos', 'Insurance': 'Seguros corporativos',
    'Liability Insurance': 'Responsabilidad civil', 'OTROS SEGUROS': 'Seguros corporativos', 'POLIZA DE SEGURO RELACIONADAS': 'Seguros corporativos',
    'POLIZA DE SEGURO TODO RIESGO': 'Póliza todo riesgo', 'POLIZA MANEJO GLOBAL BANCARIO': 'Póliza de manejo global bancario (3B)',
    'POLIZA RESPONSABILIDAD CIVIL Y DAÑOS': 'Responsabilidad civil', 'SEGUROS - EMPRESA AFILIADA': 'Seguros corporativos', 'SEGUROS - EMPRESA TERCEROS': 'Seguros corporativos',
    'SEGUROS DE INFRAESTRUCTURAS': 'Seguro de infraestructura', 'Work Comp': 'Seguro de accidentes laborales',
}

GENERICAS = {'Seguros corporativos', 'Gastos de oficina', 'Otros servicios', 'Gastos varios', 'Ajustes de ejercicios anteriores', 'Otros gastos de arriendo',
             'Gastos comunes del edificio', 'Mantenimiento del inmueble', 'Otros gastos de administración', 'Recuperación de provisiones', 'Otros arriendos'}

REGLAS = [  # (categoría o None, regex, glosa) — sólo para cuentas genéricas
    ('Seguros', r'\b3B\b|BANCOS ?3B|BLANKET|INFIDELIDAD|FIDELIDAD|MANEJO GLOBAL', 'Póliza 3B / infidelidad'),
    ('Seguros', r'CYBER|CIBER', 'Ciberseguro'),
    ('Seguros', r'KYR|K&R|SECUESTRO', 'Póliza K&R'),
    ('Seguros', r'RESPONSABILIDAD CIVIL|LIABILITY|D&O|DIRECTORES', 'Responsabilidad civil'),
    ('Seguros', r'MULTIRRIESGO|TODO RIESGO|PATRIMONIAL|INCENDIO', 'Multirriesgo / patrimonial'),
    ('Seguros', r'ONCOLOG', 'Seguro oncológico'),
    ('Seguros', r'VIAJE|TRAVEL', 'Seguro de viaje'),
    ('Seguros', r'RENOVACI[OÓ]N DE SEGUROS CORPORATIVOS', 'Renovación seguros corporativos'),
    (None, r'KITCHEN|COCINA|CAFETERIA|\bCAFE\b|COFFEE', 'Cafetería y cocina'),
    (None, r'PARTY|FIESTA|BBQ|HOLIDAY|CORP RUN|CELEBRA', 'Actividades de oficina'),
    (None, r'CONDOMINIO|GASTOS COMUNES|CUOTA DE ADMINISTRACI', 'Gastos comunes del edificio'),
    (None, r'ESTACIONAMIENTO|PARQUEADERO|PARKING|COCHERA|ESTAC\.', 'Estacionamientos'),
    (None, r'VIGILANCIA|SEGURIDAD', 'Vigilancia y seguridad'),
    (None, r'REMODELACI|OBRA|BALDOSA|ADECUACI', 'Remodelación y adecuación de oficinas'),
    (None, r'RENTA FIJA|ARRENDAMIENTO|ALQUILER|ARRIENDO|\bRENT\b|CANON', 'Arriendo de oficinas'),
    (None, r'HVAC|AIRE ACONDICIONADO', 'Aire acondicionado'),
    (None, r'DATASAFE|RASTREO', 'Custodia y rastreo de documentos'),
    (None, r'MANTENIMIENTO|MAINTENANCE|REPARACI', 'Mantenimiento del inmueble'),
    (None, r'RECUPERACI[OÓ]N DE PROVISIONES', 'Recuperación de provisiones'),
    (None, r'ENERGIA|ELECTRICIDAD|\bLUZ\b', 'Energía eléctrica'),
    (None, r'AGUA|ACUEDUCTO', 'Agua (acueducto)'),
    (None, r'ASEO|LIMPIEZA|CLEANING', 'Aseo de oficinas'),
    (None, r'PAPELER|UTILES|SUPPLIES|STATIONERY', 'Útiles de oficina'),
]
REGLAS = [(c, re.compile(r), g) for c, r, g in REGLAS]

def glosa_oys(cat, cuenta, texto):
    base = GLOSA_OYS.get(cuenta) or glosa_cuenta(cuenta)
    if base not in GENERICAS:
        return base
    t = sin_acentos(str(texto or '')).upper()
    for c, rx, g in REGLAS:
        if c and c != cat:
            continue
        if rx.search(t):
            return g
    return base

SEDES = [(r'BOGOT', 'Bogotá'), (r'\bCALI\b', 'Cali'), (r'MEDELL', 'Medellín'), (r'BARRANQUILLA', 'Barranquilla'), (r'CARTAGENA', 'Cartagena'),
         (r'BUCARAMANGA', 'Bucaramanga'), (r'PEREIRA', 'Pereira'), (r'MIAMI', 'Miami'), (r'NEW YORK|NUEVA YORK', 'Nueva York'),
         (r'PARDO Y ALIAGA|SAN ISIDRO|MIRAFLORES|\bLIMA\b', 'Lima'), (r'SANTIAGO|LAS CONDES|APOQUINDO', 'Santiago')]
SEDES = [(re.compile(r), s) for r, s in SEDES]

def sede(texto, cuenta):
    t = sin_acentos(f'{texto or ""} {cuenta or ""}').upper()
    for rx, s in SEDES:
        if rx.search(t):
            return s
    return None
