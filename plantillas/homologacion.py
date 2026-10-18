"""Homologación de proveedores y glosas para las plantillas Ppto27.

Criterio: glosa genérica y distintiva (que la unidad entienda en qué se gasta),
el menor número de líneas posible, y separar sólo cuando el texto aclara un gasto distinto.
"""
import re, unicodedata
from collections import Counter, defaultdict

def sin_acentos(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

# ---------------------------------------------------------------- glosa por cuenta contable
CUENTA_GLOSA = {
    # Consultorías y Honorarios
    'CONTRATO COLOCACIÓN DE CUOTAS RELACIONADOS': 'Colocación de cuotas',
    'Other Professional Fees': 'Honorarios profesionales',
    'Professional - Consultants': 'Consultorías',
    'Professional Fees - Other': 'Honorarios profesionales',
    'Other Pro Fees - Affiliates': 'Honorarios con relacionadas',
    'ASESORIA TECNICA RELACIONADA': 'Asesoría técnica con relacionadas',
    'OTROS INGRESOS POR SERVICIOS RELACIONADAS': 'Servicios con relacionadas',
    'ASESORÍAS FINANCIERAS': 'Asesorías financieras',
    'HONORARIOS': 'Honorarios',
    'ASESORIA Y CONSULTORIA - ADMINISTRATIVA': 'Asesoría administrativa',
    'ASESORIA Y CONSULTORIA - LEGAL': 'Asesoría legal',
    'ASESORÍAS RRRH': 'Asesorías de RR.HH.',
    'ASESORÍAS EMPRESAS RELACIONADAS': 'Asesorías con relacionadas',
    'ASESORÍAS ADMINISTRADORA DE INVERSIONES': 'Asesorías de inversión',
    'ASESOR COMITE INVERSIONES': 'Asesor del comité de inversiones',
    'ASESORIA TECNICA': 'Asesoría técnica',
    'ASESORIA TRIBUTARIA': 'Asesoría tributaria',
    'ASESORIAS HONORARIOS': 'Honorarios de asesoría',
    'ASESORIAS HONORARIOS TERCEROS - EXPORTACIÓN': 'Honorarios de asesoría',
    'CONSULTA CENTRALES DE RIESGO': 'Consulta a centrales de riesgo',
    'CONSULTORIAS GDH': 'Consultorías de gestión humana',
    'CONTRALOR NORMATIVO': 'Contralor normativo',
    'DEFENSOR DEL CONSUMIDOR': 'Defensor del consumidor financiero',
    'Otros Honorarios': 'Honorarios',
    'OTROS HONORARIOS': 'Honorarios',
    'REALIZACION DE OTROS ACTIVOS': 'Realización de otros activos',
    'SUSCRIPCIONES RELACIONADAS': 'Suscripciones con relacionadas',
    'OTROS SERVICIOS PRESTADOS TERCEROS LEGALIZACION Y DERECHOS NOTARIALES': 'Gastos notariales',
    # Representación
    'GASTOS DE REPRESENTACION': 'Gastos de representación',
    'GASTOS DE REPRESENTACIÓN': 'Gastos de representación',
    'RELACIONES PUBLICAS': 'Relaciones públicas',
    'RELACIONES PÚBLICAS - EVENTOS': 'Eventos',
    'REUNIONES Y COMIDAS': 'Reuniones y comidas',
    'CONSUMOS': 'Consumos',
    'CONGRESOS': 'Congresos',
    'AUSPICIOS': 'Auspicios',
    'ATENCIÓN AL PERSONAL - OTROS': 'Atenciones al personal',
    'ATENCIÓN AL PERSONAL - RECREATIVOS': 'Actividades recreativas',
    'CELEBRACIONES COLABORADORES': 'Celebraciones colaboradores',
    'ESTUDIOS DE IMAGEN': 'Estudios de imagen',
    'EXPEDICION DE VISA': 'Trámite de visas',
    'MISCELANEOS': 'Gastos varios',
    'Personnel - Dinner Money/Late Work': 'Alimentación por trabajo extendido',
    'Entertainment': 'Gastos de representación',
    'Advertising': 'Publicidad',
    'Public Relation': 'Relaciones públicas',
    'PARQUEADEROS': 'Estacionamientos',
    'CAPACITACION PERSONAL': 'Capacitación',
    # Misiones
    'OTRAS PROVISIONES - TARJETA DE CREDITO': 'Tarjeta corporativa',
    'ALOJAMIENTO INTERNACIONAL': 'Alojamiento internacional',
    'ALOJAMIENTO NACIONAL': 'Alojamiento nacional',
    'GASTOS DE VIAJE INTERNACIONAL': 'Gastos de viaje internacional',
    'PASAJES AEREOS INTERNACIONAL VIAJES': 'Pasajes aéreos internacionales',
    'PASAJES AEREOS NACIONALES VIAJES': 'Pasajes aéreos nacionales',
    'Travel - Hotel & Others': 'Alojamiento y gastos de viaje',
    'TRAVEL - HOTEL': 'Alojamiento',
    'TRAVEL - MEALS': 'Alimentación en viajes',
    'Airfare': 'Pasajes aéreos',
    'T&E - Airfare': 'Pasajes aéreos',
    'Travel & Ent': 'Gastos de viaje',
    'Travel': 'Gastos de viaje',
    'T&E - Travel': 'Gastos de viaje',
    'Lodging': 'Alojamiento',
    'T&E - Lodging': 'Alojamiento',
    'Meals': 'Alimentación en viajes',
    'T&E - Meals': 'Alimentación en viajes',
    'Transportation': 'Transporte en viajes',
    'T&E - Transportation': 'Transporte en viajes',
    'POLIZA MANEJO GLOBAL BANCARIO': 'Póliza de manejo global bancario',
    'MANUTENCION INTERNACIONAL': 'Manutención internacional',
    'MANUTENCION NACIONAL': 'Manutención nacional',
    'GASTOS VIATICOS': 'Viáticos',
    'VIATICOS': 'Viáticos',
    'OTROS GASTOS DE VIAJE': 'Otros gastos de viaje',
    'GASTOS DE VIAJE': 'Gastos de viaje',
    'GASTOS DE VIAJES': 'Gastos de viaje',
    'OTROS SEGUROS': 'Seguros de viaje',
    'TRANSPORTE TERRESTRE VIAJES': 'Transporte terrestre en viajes',
    'SEGURO CUMPLIMIENTO': 'Seguro de cumplimiento',
    # Pagos transaccionales
    'AJUSTE AL MIL': 'Ajuste al mil',
    'GASTOS FONDOS DE INVERSIÓN': 'Gastos de fondos de inversión',
    'GASTOS ASOC.FONDOS DE INVERSIÓN': 'Gastos asociados a fondos de inversión',
    'COMISIONES - RELACIONADAS': 'Comisiones con relacionadas',
    'COMISIONES RELACIONADAS': 'Comisiones con relacionadas',
    'COMISIÓN USO DE RED RELACIONADA': 'Comisión uso de red',
    'ASESORIA DE INVERSION - EXPORTACION RELACIONADA': 'Asesoría de inversión con relacionadas',
    'ASESORIA DE INVERSION - EXPORTACION TERCEROS': 'Asesoría de inversión con terceros',
    'COSTO DE SERVICIOS TERCEROS': 'Servicios de terceros',
    'COMM PAID - CRED CAP SF (Victtus)': 'Comisión pagada - Credicorp Capital SF (Vicctus)',
    'COMISIÓN AGENTE COLOCADOR': 'Comisión de agente colocador',
    'OTROS SERVICIOS- REEMBOLSOS CAVALI': 'Reembolsos Cavali',
    'METODO PARTICIPACION CCC': 'Método de participación',
    'METODO PARTICIPACION CCF': 'Método de participación',
    'METODO PARTICIPACION CORPORACION': 'Método de participación',
    'PERDIDAS METODO DE PARTICIPACION CCC': 'Método de participación',
    'PERDIDAS METODO DE PARTICIPACION CORPORACION': 'Método de participación',
    'Ingresos Prod. Estruct. y Fond. Terceros 10': 'Productos estructurados y fondos de terceros',
    'Comisión pagada por CC - GDP': 'Comisión pagada - GDP',
    'Clearing Charges - Other': 'Costos de clearing',
    'Foreign Securities Clg': 'Clearing de valores extranjeros',
    'CARGO VARIABLE RENTA VARIABLE': 'Cargo variable renta variable',
    'CARGO VARIABLE RENTA FIJA': 'Cargo variable renta fija',
    'CARGO VARIABLE RENTA FIJA - FI': 'Cargo variable renta fija',
    'CARGO VARIABLE VALORES RENTA FIJA - FI': 'Cargo variable renta fija',
    'CARGO VARIABLE VALORES RF': 'Cargo variable renta fija',
    'CARGO VARIABLE VALORES RV': 'Cargo variable renta variable',
    'CARGO VARIABLE DERIVADOS': 'Cargo variable derivados',
    'CARGO VARIABLE DERIVADOS CRCC': 'Cargo variable derivados CRCC',
    'CARGO VARIABLE DIVISAS SISTEMAS DE NEGOCIACION': 'Cargo variable divisas',
    'CARGO CRCC RENTA FIJA': 'Cargo CRCC renta fija',
    'CARGO FIJO CUSTODIA VALORES RF': 'Custodia de valores renta fija',
    'CARGO FIJO CUSTODIA VALORES RENTA FIJA - FI': 'Custodia de valores renta fija',
    'CARGO FIJO CUSTODIA VALORES RV': 'Custodia de valores renta variable',
    'CARGO FIJO CUSTODIA VALORES RENTA VARIABLE - FI': 'Custodia de valores renta variable',
    'CARGO FIJO ADMON Y CUSTODIA VALORES RV': 'Custodia de valores renta variable',
    'CUSTODIA DE TITULOS - FI': 'Custodia de títulos',
    'CARGO FIJO DERIVADOS': 'Cargo fijo derivados',
    'CARGO FIJO DERIVADOS CRCC': 'Cargo fijo derivados CRCC',
    'CARGO FIJO RENTA FIJA': 'Cargo fijo renta fija',
    'CARGO FIJO SERVICIO DE INFORMACION RF': 'Servicio de información renta fija',
    'CARGO FIJO SERVICIO DE INFORMACION RF - FI': 'Servicio de información renta fija',
    'CARGO CONEXION FINANCIERA': 'Cargo conexión financiera',
    'CARGO PLATAFORMA ACCIONES': 'Plataforma de acciones',
    'CARGO PLATAFORMA DIVISAS': 'Plataforma de divisas',
    'PLATAFORMA NEGOCIACION ACCIONES': 'Plataforma de negociación de acciones',
    'PLATAFORMA OPERATIVA INTERNACIONAL': 'Plataforma operativa internacional',
    'SERVICIO DE SOPORTE RELACIONADAS': 'Servicio de soporte entre relacionadas',
    'OTROS LITIGIOS EN PROCESO ADMINISTRATIVO JUDICIAL O ARBITRAL': 'Litigios y procesos judiciales',
    'OTRAS CARGAS DE GESTIÓN - AJUSTE POR REDONDEO': 'Ajuste por redondeo',
    'OTROS INGRESOS - AJUSTE POR REDONDEO': 'Ajuste por redondeo',
    'COMM PAID-TRADE GDPP': 'Comisión pagada - trading GDP',
    'OTROS SERVICIOS': 'Otros servicios',
    'ADMINISTRACION DE CARTERA RELACIONADAS': 'Administración de cartera',
    'INGRESOS POR ADMINISTRACIÓN DE CARTERA RELACIONADA': 'Administración de cartera',
    'COMISIONES TRANSFERENCIAS CAC': 'Comisiones por transferencias CAC',
    'Comm Rebate - Equity & MF\'s': 'Rebate de comisiones renta variable y fondos',
    'Commission Rebate - Bonds': 'Rebate de comisiones bonos',
    'COMM PAID-REF-CCSF (CV)': 'Comisión pagada - referenciamiento CCSF',
    'Pago a US por Trading Equity (45%) 9': 'Pago a USA por trading de acciones',
    'Pago a US por Trading Equity (55%) 11': 'Pago a USA por trading de acciones',
    'COMM PAID-INV ADVISORY-CC SF': 'Comisión pagada - asesoría de inversión',
    'COMM PAID - INV ADV-CC SAB': 'Comisión pagada - asesoría de inversión',
    'COSTO VARIABLE CCLV MRV': 'Costo variable CCLV',
    'COSTO VARIABLE DCV': 'Costo variable DCV',
    'COMISIONES OPERACIONES RELACIONADAS': 'Comisiones por operaciones con relacionadas',
    'COMISIONES OPERACIONES RELACIONADAS - RF EXTRANJERA EXONERADA': 'Comisiones por operaciones con relacionadas',
    'COMISIONES OPERACIONES RELACIONADAS - RF EXTRANJERA GRAVADA': 'Comisiones por operaciones con relacionadas',
    'COMISIONES OPERACIONES RELACIONADAS - RF PERUANA GRAVADA': 'Comisiones por operaciones con relacionadas',
    'COMISIONES OPERACIONES RELACIONADAS - RF PERUANA INAFECTA': 'Comisiones por operaciones con relacionadas',
    'COMISIONES OPERACIONES - REC.CUST.': 'Comisiones de custodia',
    'COMISIONES RECAUDOS': 'Comisiones por recaudos',
    'GASTOS BANCARIOS': 'Gastos bancarios',
    'GASTOS BANCARIOS BANREP': 'Gastos bancarios Banco de la República',
    'GASTOS BANCARIOS MONEDA EXTRANJERA TRANSACCIONAL': 'Gastos bancarios moneda extranjera',
    'GASTOS BANCARIOS RELACIONADA': 'Gastos bancarios',
    'GASTOS BANCARIOS TERCEROS': 'Gastos bancarios',
    'GASTOS BANCARIOS EXTERIOR RELACIONADA': 'Gastos bancarios del exterior',
    'GASTOS BANCARIOS EXTERIOR RELACIONADA RENTA FTE PERUANA EXONERADA': 'Gastos bancarios del exterior',
    'COMISION DE BANCOS DEL EXTERIOR': 'Comisiones de bancos del exterior',
    'COMISION DEL EXTERIOR - RENTA EXTRANJERA GRAVADA': 'Comisiones de bancos del exterior',
    'COMISION DEL EXTERIOR - RENTA PERUANA GRAVADA': 'Comisiones de bancos del exterior',
    'Bank Charges - Bank': 'Gastos bancarios',
    'Bank Charges - Miscellaneous': 'Gastos bancarios',
    'Bank Service Charges': 'Gastos bancarios',
    'BANK CHARGE COMM SERV RFL PEN': 'Gastos bancarios',
    'BANK CHARGES-CCRFL': 'Gastos bancarios',
    'BANK CHARGES-COMM SERV RFL': 'Gastos bancarios',
    'BANK CHARGES-RV BTG': 'Gastos bancarios',
    'BANK CHARGES-RV VELOCITY': 'Gastos bancarios',
    'COMISIONES BANCARIAS': 'Gastos bancarios',
    'COMISIÓN BANCARIA RF ME': 'Gastos bancarios',
    'COMISIÓN BANCARIA RF MN': 'Gastos bancarios',
    'GASTOS POR COMISIONES TRADINGS': 'Comisiones de trading',
    'CHAPERONING': 'Chaperoning',
    'COMISION CHAPERONING': 'Chaperoning',
    'BROKER TRANSACCIONAL': 'Comisiones de broker',
    'COMISIONES BROKER': 'Comisiones de broker',
    'Fees Paid to Affililates': 'Comisiones a relacionadas',
    'SUSCRIPCIONES': 'Suscripciones',
    'INTERESES BANCARIOS RELACIONADAS': 'Intereses bancarios',
    'INTERESES CREDITOS BANCOS CON RELACIONADAS': 'Intereses bancarios',
    'INTERESES LINEAS DE CREDITO': 'Intereses de líneas de crédito',
    'INTERESES SOBREGIROS BANCARIOS': 'Intereses de sobregiro',
    'REALIZACION ACTIVOS POSICION PROPIA': 'Realización de activos posición propia',
    'CONTRIBUCION SMV': 'Contribución SMV',
    'CONTRIBUCIONES - RENTA EXTRANJERA GRAVADA': 'Contribuciones',
    'CONTRIBUCIONES - RENTA PERUANA GRAVADA': 'Contribuciones',
    'COMM PAID - BROKERS FEE- GSC': 'Comisión pagada - brokers',
    'COMM PAID - BROKERS FEE-WELL': 'Comisión pagada - brokers',
    'COMM PAID - BROKERS FEE-PIM': 'Comisión pagada - brokers',
    'COMM PAID-CCSF-AHF': 'Comisión pagada - CCSF',
    'SERVICIO DE INFORMACION BURSATIL': 'Servicio de información bursátil',
    'COMISION ADQUIRENCIA': 'Comisión de adquirencia',
    'CONTRATOS DE COLABORACIÓN IFP\'S': 'Contratos de colaboración IFP',
    'Interest Expense': 'Intereses',
    'Comision por Admin PE': 'Comisión por administración',
    'Asesoría Renta Fija Latam GDA': 'Asesoría renta fija Latam',
    'MANTENIMIENTO Y REPARACIÓN INTANGIBLES': 'Mantenimiento de intangibles',
    'MANTENIMIENTO Y REPARACIÓN TI': 'Mantenimiento TI',
    'COMISIONES SEBRA': 'Comisiones SEBRA',
    'TERMINALES Y PANTALLAS SEBRA': 'Terminales y pantallas SEBRA',
    'Pago comisión GDA - Servicios Financieros / ASB Mandatos': 'Comisión GDA - servicios financieros',
    'Pago comisión GDA - Servicios Financieros / FFTT': 'Comisión GDA - servicios financieros',
    'POLIZA DE SEGURO RELACIONADAS - RESARCIMIENTOS': 'Resarcimientos',
    'GASTOS POR RESARCIMIENTO': 'Resarcimientos',
    'COMISIONES CENIT TRANSACCIONAL': 'Comisiones CENIT',
    'OTRAS RECUPERACIONES': 'Recuperaciones',
    'RECUPERACIONES RIESGO OPERATIVO': 'Recuperaciones de riesgo operativo',
    'MULTAS Y SANCIONES': 'Multas y sanciones',
    'MULTAS': 'Multas y sanciones',
    'COMM PAID - CC VARIABLE INC': 'Comisión pagada - ingreso variable',
    'ABONOS MANEJO COMERCIAL': 'Abonos de manejo comercial',
    'ABONO POR RECONOCIMIENTO OP COMISIONES': 'Abono por reconocimiento de comisiones',
    'COMISIÓN POR TRASPASOS LBTR': 'Comisión por traspasos LBTR',
    'SERVICIO DE INFORMACION PANTALLAS OTROS': 'Servicio de información - pantallas',
    'SERVICIO DE INFORMACION PANTALLAS OTROS - FI': 'Servicio de información - pantallas',
    'SERVICIO DE INFORMACION DE PRECIOS': 'Servicio de información de precios',
    'SERVICIO DE INFORMACION DE PRECIOS INFORMACION - FI': 'Servicio de información de precios',
    'COMM PAID - INT DATA-PRICING': 'Comisión pagada - información de precios',
    'COMM PAID-PIP PERU-PRICING': 'Comisión pagada - información de precios',
    'COMM PAID -MARKET INFO SERV': 'Comisión pagada - información de mercado',
    'DATATEC': 'Servicio Datatec',
    'COMM PAID - CC FI LOCAL PORT': 'Comisión pagada - portafolio local',
    'COMM PAID-SMV REGUL. SERV': 'Comisión pagada - servicios regulatorios',
    'COMISIONES CARTAS FIANZAS': 'Comisiones por cartas fianza',
    'COMISIONES CARTAS FIANZAS RELACIONADA': 'Comisiones por cartas fianza',
    'SUNDRY ACCOUNT-PERSHING': 'Cargos varios Pershing',
    'DIGITALIZACIÓN': 'Digitalización de documentos',
    'RIESGO OPERATIVO - OTROS GASTOS': 'Riesgo operativo',
    'RIESGO OPERATIVO ANULACION DE OPERACIONES': 'Riesgo operativo',
    'RIESGO OPERATIVO CORRECCION DE OPERACIONES': 'Riesgo operativo',
    'GESTION FALLAS EN LA EJECUCION Y ADM DE PROCESOS': 'Fallas operativas',
    'Error losses & Write-offs': 'Pérdidas por errores operativos',
    'Error a/c losses': 'Pérdidas por errores operativos',
    'REGULARIZACIONES OPERACIONALES': 'Regularizaciones operacionales',
    'MISC INC - PREVIOUS YEAR': 'Ajustes de ejercicios anteriores',
    'Other Expenses - Previous Years': 'Ajustes de ejercicios anteriores',
    'GESTIÓN - GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'PROVISIONES DE GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'PROVISIONES DE GASTOS DE EJERCICIOS ANTERIORES - TARJETAS CORPORATIVAS': 'Tarjeta corporativa',
    'OTROS INGRESOS - EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS - EJERCICIOS ANTERIORES PROVISIONES': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS - EJERCICIOS ANTERIORES INGRESOS DIVERSOS': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS - EJERCICIOS ANTERIORES PCD': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS - EXTORNO DE PROV EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores',
    'OTROS INGRESOS - EXTORNO DE PROV EJERCICIOS ANTERIORES TARJETAS CORPORATIVAS': 'Tarjeta corporativa',
    'OTROS SERVICIOS IMPRESIÓN Y EMPASTE': 'Impresión y empaste',
    'COMISION DE VENTA': 'Comisión de venta',
    'COMISION QUINTO CICLO TRANSACCIONAL': 'Comisión quinto ciclo',
    'COMISIONES PAGOS ACH': 'Comisiones pagos ACH',
    'SERVICIO DE RECAUDO PSE': 'Servicio de recaudo PSE',
    'RENOVACION REGISTRO MERCANTIL': 'Renovación registro mercantil',
    'OTROS INGRESOS': 'Otros ingresos',
    'OTRAS COMISIONES': 'Otras comisiones',
    'COMISION CHEQUES DE GERENCIA TRANSACCIONAL': 'Comisión cheques de gerencia',
    'COMISION EFECTIVO TRANSACCIONAL': 'Comisión manejo de efectivo',
    'COMISION MANEJO CUENTA': 'Comisión manejo de cuenta',
    'COMISION CUSTODIA ESTADO DE CUENTA': 'Comisión custodia estado de cuenta',
    'COMISION ADR': 'Comisión ADR',
    'COMISIONES CREDICARGO RELACIONADAS': 'Comisiones Credicargo',
    'COMISIÓN VENTA ACCIONES AFILIADA': 'Comisión venta de acciones',
    'COMISIÓN VENTA ACCIONES TERCEROS': 'Comisión venta de acciones',
    'CARGO VARIABLE': 'Cargo variable',
    'NO DEDUCIBLES': 'Gastos no deducibles',
    'GASTOS NO DEDUCIBLES': 'Gastos no deducibles',
    'GASTOS NO DEDUCIBLES OTROS': 'Gastos no deducibles',
    'GASTOS RECHAZADOS': 'Gastos rechazados',
    'REFERENCIAMIENTO TERCEROS': 'Referenciamiento de terceros',
    'DEPÓSITOS DE AHORRO ORDINARIO': 'Depósitos de ahorro',
    'LIQUIDACION DE OTROS PASIVOS': 'Liquidación de otros pasivos',
    'Accounting': 'Servicios contables',
    'AHS SPC - AUDIT': 'Auditoría',
    'CALIFICADORA DE RIESGO DE CONTRAPARTE': 'Calificadora de riesgo',
    'CLASIFICADORA DE RIESGO': 'Clasificadora de riesgo',
    'CLASIFICADORA DE RIESGOS': 'Clasificadora de riesgo',
    'PERDIDA CAMBIARIA NO REALIZADA': 'Diferencia de cambio',
    'PERDIDA CAMBIARIA NO REALIZADA EXT PR': 'Diferencia de cambio',
    'PERDIDA CAMBIARIA REALIZADA': 'Diferencia de cambio',
    'GANANCIA CAMBIARIA DEVENGADA': 'Diferencia de cambio',
    'GANANCIA CAMBIARIA DEVENGADA NAC PNR': 'Diferencia de cambio',
    'GANANCIA CAMBIARIA REALIZADA': 'Diferencia de cambio',
    'GANANCIA CAMBIARIA REALIZADA NAC PNR': 'Diferencia de cambio',
    'INTERESES A FAVOR SUNAT': 'Intereses SUNAT',
    'INTERESES DE MORA': 'Intereses de mora',
    'INTERESES DE MORA R.O': 'Intereses de mora',
    'INTERES MORA TC': 'Intereses de mora tarjeta de crédito',
    'CUOTA MANEJO TARJETAS DE CREDITO': 'Cuota de manejo tarjetas de crédito',
    'SERVICIO DE MONITORES COMUNICACION': 'Servicio de monitores',
    'Bad Debt Expense': 'Deudas incobrables',
    'CONTABLE': 'Ajuste contable',
    'MDK CHARGE': 'Cargo MDK',
    'REGUL. CONTR. AND FEES': 'Contribuciones regulatorias',
    'COMM PAID - HELD FOR TRADING': 'Comisión pagada - trading',
    'COMM PAID - EQUITY 890312': 'Comisión pagada - renta variable',
    'COMM PAID - EQUITY': 'Comisión pagada - renta variable',
    'COMM PAID-CORPORATE BOND': 'Comisión pagada - bonos corporativos',
    'COMM PAID - VISA DEBIT-INS': 'Comisión pagada - tarjeta Visa débito',
    'COMM PAID - VISA DEBIT-OTHER': 'Comisión pagada - tarjeta Visa débito',
    'COMM PAID - VISA DEBIT-PROC': 'Comisión pagada - tarjeta Visa débito',
    'COMM PAID - JP MORGAN': 'Comisión pagada - JP Morgan',
    'COMM PAID - CUSTODY - BCPL': 'Comisión pagada - custodia',
    'COMM PAID - BB&H - CUSTODY': 'Comisión pagada - custodia',
    'COMM PAID - BoNY - PROP.': 'Comisión pagada - custodia',
    'COMM PAID - S&P GLOBAL MI': 'Comisión pagada - S&P Global',
    'COMM PAID - OTHER SERVICES': 'Comisión pagada - otros servicios',
    'COMM PAID-SUB-ADV FEE CCUS': 'Comisión pagada - subasesoría',
    'COMM PAID-M FUNDS ENALTA': 'Comisión pagada - fondos mutuos',
    'COMM PAID-PORTF TESCC': 'Comisión pagada - portafolio',
    'COMM PAID-SEC PMA': 'Comisión pagada - SEC',
    'COMM - FEE CHECK': 'Comisión por cheques',
    'Bony': 'Custodia BNY',
    'Gastos asesoría Rafael Castellanos': 'Asesoría',
    'SERVICIOS DE INFORMACIÓN': 'Servicios de información',
    'SERVICIOS PRESTADOS A EMP.RELACIONADAS': 'Servicios con relacionadas',
    'CORREO, PORTES Y TELEGRAMAS': 'Servicio de correos',
    'INGRESOS NO ACUMULABLES': 'Ingresos no acumulables',
    'Sell/Buy Investment Cost': 'Costo de compra/venta de inversiones',
    'Sell/Buy Inves Comm afilia': 'Comisiones compra/venta con relacionadas',
    'Sell/Buy Invest Comm affiliate': 'Comisiones compra/venta con relacionadas',
    'PRIMA DE SEGURO': 'Primas de seguro',
    'SEGUROS - EMPRESA AFILIADA': 'Seguros',
    'SEGURO DE DEPÓSITOS-FOGAFIN': 'Seguro de depósitos Fogafin',
    'OTRAS': 'Otros gastos',
    'AJUSTE': 'Ajuste contable',
    '(blank)': 'Otros gastos',
    'AMPLIACION DE HORARIO': 'Ampliación de horario',
    'OTROS GASTOS FINANCIEROS': 'Otros gastos financieros',
    'OTROS GASTOS POR SERVICIOS RELACIONADAS': 'Servicios con relacionadas',
    'UTILES Y PAPELERIA': 'Útiles y papelería',
    'RENDIMIENTOS RESCATE': 'Rendimientos por rescate',
    'OTROS INGRESOS FINANCIEROS': 'Otros ingresos financieros',
    'PERDIDA EN PARTICIPACION FONDO MUTUO': 'Pérdida en fondo mutuo',
    'CERTIFICACION DOCUMENTOS': 'Certificación de documentos',
    'CERTIFICADO DE REPRESENTACION Y EXISTENCIA': 'Certificados de existencia y representación',
    'PROVEEDOR DE INFORMACION DE MERCADO': 'Proveedor de información de mercado',
    'SUSCRIPCION EMERGING MARKETS': 'Suscripción Emerging Markets',
    # Provisión de incobrables
    'DEUDAS INCOBRABLES': 'Deudas incobrables',
    'PROVISION DEUDORES': 'Provisión de deudores',
    'PROVISION DEUDORES RELACIONADAS': 'Provisión de deudores',
    'RECUPERACIONES CARTERA': 'Recuperación de cartera',
    'PROVISIÓN - PÉRDIDA ESPERADA': 'Provisión de pérdida esperada',
    # Suscripciones y servicios de información
    'Subscriptions - Partnership': 'Suscripciones y membresías',
    'Subscriptions - Miscellaneous': 'Suscripciones',
    'MANTENIMIENTO EN APLICACIONES': 'Mantenimiento de aplicaciones',
    'SUSCRIPCIONES PUBLICACIONES JURIDICAS': 'Suscripciones jurídicas',
    'Registration Fees': 'Registros regulatorios',
    'Registration & Regulatory fees': 'Registros regulatorios',
    'Servicios Morningstar y Data Licence': 'Servicios Morningstar',
    'SUSCRIPCION INFORMACION MERCADO': 'Suscripción de información de mercado',
    'SERVICIO DE VIDEOLINEAS': 'Servicio de videolíneas',
    'IMPUESTOS ASUMIDOS': 'Impuestos asumidos',
    'PUBLICIDAD': 'Publicidad',
    'PUBLICACIONES': 'Publicaciones',
    # Transporte y mensajería
    'OTROS SERVICIOS - MOVILIDAD': 'Movilidad',
    'SERVICIO DE MENSAJERIA EXPRESA': 'Servicio de mensajería',
    'SERVICIO DE IMPRESION EXTRACTOS MOVILIDAD': 'Impresión y envío de extractos',
    'MOVILIZACIÓN Y TRASLADOS': 'Movilización y traslados',
    'MOVILIZACIÓN Y ATENCIÓN A CLIENTES': 'Movilización y traslados',
    'SERVICIO DE TRANSPORTE ESPECIAL': 'Servicio de transporte especial',
    'TAXIS Y BUSES': 'Taxis y buses',
    'SERVICIO DE MENSAJERIA INTERNACIONAL MOVILIDAD': 'Servicio de mensajería internacional',
    'TRANSPORTE. FLETES Y ACARREOS': 'Fletes y acarreos',
    'Communication - Courier Lima': 'Servicio de courier',
    'Communication - Courier Others': 'Servicio de courier',
    'Communication - Postal': 'Servicio de correos',
    'Correos': 'Servicio de correos',
    'CORREOS': 'Servicio de correos',
    'Maintenance - Car Expenses': 'Mantenimiento de vehículos',
    'RESPONSABILIDAD SOCIAL EMPRESARIAL': 'Responsabilidad social empresarial',
    'EVENTOS': 'Eventos',
}

SIGLAS = {'RF','RV','FI','SMV','SUNAT','CRCC','DCV','CCLV','LBTR','ACH','PSE','SEBRA','CAC','ADR','TC','GDA','CENIT','MDK','IFP','ERP','USA','US','USD','TI','GDP','CCSF','SAB','SF','PCD'}

def glosa_cuenta(cta):
    if not isinstance(cta, str) or not cta.strip():
        return 'Otros gastos'
    if cta in CUENTA_GLOSA:
        return CUENTA_GLOSA[cta]
    palabras = cta.strip().split()
    out = []
    for i, w in enumerate(palabras):
        out.append(w if w.upper() in SIGLAS else (w.capitalize() if i == 0 else w.lower()))
    return ' '.join(out)

# ---------------------------------------------------------------- reglas por texto
# Sólo separan cuando el texto aclara un gasto distinto. Se aplican sobre el texto sin acentos en mayúsculas.
REGLAS_TEXTO = [
    # (Nivel 2 donde aplica o None, regex, glosa)
    (None, r'RENDICI[OÓ]N PENDIENTE|RENDICION PENDIENTE', 'Rendición pendiente'),
    (None, r'MOV(IMIENTOS)? NO FACTURADOS|TARJETA CORPORATIVA|TARJ\.? ?CREDITO|TARJETA BCP|PROV(ISION)? (DE )?TARJETA|REVERSION DE TARJETA|TC CORPO', 'Tarjeta corporativa'),
    (None, r'LEGALIZACI', 'Legalización de gastos'),
    ('Gastos de Representación', r'\bREGALO|GIFT|ATENCION(ES)? (A )?CLIENTE|OBSEQUIO|ANCHETA|FLORES|FLORERIA', 'Regalos y atenciones a clientes'),
    ('Gastos de Representación', r'\bEVENTO|CONGRESO|SEMINARIO|CONFERENCIA|FORO\b|AUSPICIO|PATROCINIO', 'Eventos'),
    ('Gastos de Representación', r'ALMUERZO|CENA|DESAYUNO|RESTAURANT|COMIDA|CAFE|LUNCH|DINNER', 'Reuniones y comidas'),
    ('Misiones', r'PASAJE|TIQUETE|BOLETO|AEREO|VUELO|AIRFARE|FLIGHT|LATAM|AVIANCA|\bCOPA\b|\bSKY\b|JETSMART|AMERICAN AIRLINES|UNITED AIRLINES|IBERIA', 'Pasajes aéreos'),
    ('Misiones', r'HOTEL|ALOJAMIENTO|HOSPEDAJE|LODGING|AIRBNB|MARRIOTT|HILTON|HYATT|SHERATON', 'Alojamiento'),
    ('Misiones', r'VIATICO|MANUTENCI|ALIMENTACI|PER DIEM|MEALS', 'Viáticos y manutención'),
    ('Misiones', r'SEGURO (DE )?VIAJE|ASISTENCIA (AL )?VIAJERO|ASSIST CARD|TRAVEL ACE|UNIVERSAL ASSISTANCE', 'Seguro de viaje'),
    ('Transporte y Mensajería', r'CABIFY|UBER|DIDI|\bTAXI|EASY TAXI|\bBEAT\b|INDRIVER|MAXI MOBILITY', 'Taxis y movilidad'),
    ('Transporte y Mensajería', r'COURIER|\bDHL\b|FEDEX|\bUPS\b|MENSAJER|ENCOMIENDA|CORREOS? DE CHILE|SERPOST|OLVA|CHILEXPRESS|SERVIENTREGA|INTERRAPIDISIMO|4-72', 'Servicio de mensajería'),
    ('Transporte y Mensajería', r'ESTACIONAMIENTO|PARQUEADERO|PARKING|PEAJE|TAG\b|AUTOPISTA|COMBUSTIBLE|GASOLINA', 'Estacionamientos, peajes y combustible'),
    ('Provisión de Incobrables', r'\b(REV|REVERSA|REVERSO|EXTORNO|RECUPERO)\b.*(PROV|INCOBRABLE|PCD)|RECUPERO PDC', 'Provisión de incobrables'),
    ('Provisión de Incobrables', r'PROV.*INCOBRABLE|\bPCD\b|INCOBRABLE|PERDIDA ESPERADA|DETERIORO', 'Provisión de incobrables'),
    ('Pagos Transaccionales, Bolsas y Otros', r'BALANCE DE MONEDA', 'Ajuste por diferencia de cambio'),
    ('Pagos Transaccionales, Bolsas y Otros', r'RECONOCIMIENTO (MENOR|MAYOR) VALOR COMISION', 'Reconocimiento de comisiones a clientes'),
    ('Pagos Transaccionales, Bolsas y Otros', r'CONCILIACION SALDOS MENORES', 'Conciliación de saldos menores'),
    ('Pagos Transaccionales, Bolsas y Otros', r'INTEREST|INTERES', 'Intereses a clientes'),
    ('Pagos Transaccionales, Bolsas y Otros', r'\bSWIFT\b', 'Servicio SWIFT'),
    ('Pagos Transaccionales, Bolsas y Otros', r'CLEARING|EXECUTION FEES|EXECUTION CHGS', 'Costos de clearing y ejecución'),
    ('Pagos Transaccionales, Bolsas y Otros', r'CUSTODIA|CUSTODY', 'Custodia de valores'),
    ('Suscripciones y Servicios de Información', r'MEMBRES|MEMBERSHIP|ASOCIACI[OÓ]N|GREMIO|CAMARA DE COMERCIO|CUOTA SOCIAL', 'Membresías y asociaciones'),
    ('Suscripciones y Servicios de Información', r'DIARIO|PERIODICO|REVISTA|EL MERCURIO|LA TERCERA|EL COMERCIO|GESTION|FINANCIAL TIMES|WALL STREET|ECONOMIST|PORTAFOLIO|LA REPUBLICA|DF\b', 'Suscripciones a diarios y revistas'),
]
REGLAS_TEXTO = [(n2, re.compile(rx), g) for n2, rx, g in REGLAS_TEXTO]

# Cuentas genéricas donde el texto decide la glosa (en el resto manda la cuenta)
CUENTAS_GENERICAS = {'Otros gastos', 'Otros servicios', 'Gastos de viaje', 'Gastos de representación', 'Ajustes de ejercicios anteriores',
                     'Tarjeta corporativa', 'Suscripciones', 'Movilidad', 'Movilización y traslados', 'Gastos no deducibles',
                     'Alojamiento y gastos de viaje', 'Consumos', 'Relaciones públicas', 'Honorarios', 'Otros ingresos', 'Viáticos',
                     'Otros gastos de viaje', 'Servicios de información', 'Gastos varios', 'Ajuste contable', 'Gastos rechazados',
                     'Servicio de correos', 'Deudas incobrables', 'Provisión de deudores',
                     'Otras comisiones', 'Depósitos de ahorro', 'Ajuste al mil', 'Recuperación de cartera'}
# reglas que siempre aplican, aunque la cuenta sea específica
REGLAS_SIEMPRE = {'Rendición pendiente', 'Legalización de gastos'}

def glosa(nivel2, cuenta, texto):
    base = glosa_cuenta(cuenta)
    t = sin_acentos(str(texto or '')).upper()
    for n2, rx, g in REGLAS_TEXTO:
        if n2 and n2 != nivel2:
            continue
        if g in REGLAS_SIEMPRE or base in CUENTAS_GENERICAS:
            if rx.search(t):
                return g
    return base

# ---------------------------------------------------------------- proveedores
SIN_PROV = {'', '0', 'N/E', 'NE', '(BLANK)', 'NA', 'N/A', 'NAN', 'NONE', '-', '(SIN PROVEEDOR)', 'SIN PROVEEDOR', 'NO APLICA', '#N/A'}
SUFIJOS = r'\b(S\.?A\.?S?|S\.?A\.?C|S\.?P\.?A|SPA|LTDA|LIMITADA|L\.?L\.?C|INC|CORP|CORPORATION|LTD|LIMITED|E\.?I\.?R\.?L|S\.?R\.?L|S\.? DE R\.?L\.?( DE C\.?V\.?)?|DE C\.?V|SAC|SAA|S\.?A\.?A|CIA|Y CIA|PLC|GMBH|B\.?V|N\.?V|AG|LP|L\.?P)\b\.?'

def clave_proveedor(p):
    s = sin_acentos(p).upper()
    s = re.sub(r'[\"\'`´]', '', s)
    s = s.replace('&', ' ')
    s = re.sub(r'[,\.]', ' ', s)
    s = re.sub(SUFIJOS.replace(r'\.', ' ?'), ' ', s)
    s = re.sub(r'[^A-Z0-9&]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

# marcas que se reconocen en el texto cuando no hay proveedor
MARCAS = [
    (r'CABIFY', 'CABIFY'), (r'\bUBER\b', 'UBER'), (r'\bDIDI\b', 'DIDI'),
    (r'BLOOMBERG', 'BLOOMBERG'), (r'REFINITIV|REUTERS', 'REFINITIV'),
    (r'S&P GLOBAL|STANDARD & POOR', 'S&P GLOBAL'), (r'FITCH', 'FITCH RATINGS'), (r'MOODY', "MOODY'S"),
    (r'\bKPMG\b', 'KPMG'), (r'DELOITTE', 'DELOITTE'), (r'\bPWC\b|PRICEWATERHOUSE', 'PWC'), (r'\bEY\b|ERNST & YOUNG', 'EY'),
    (r'JP ?MORGAN|\bJPM\b|JP CORRES', 'JP MORGAN'), (r'\bCITI(BANK)?\b', 'CITIBANK'), (r'WELLS F', 'WELLS FARGO'),
    (r'INVERSIS', 'BANCO INVERSIS'), (r'FIDESSA', 'FIDESSA'), (r'IRON MOUNTAIN', 'IRON MOUNTAIN'), (r'RISKAMERICA', 'RISKAMERICA'),
    (r'AVIATUR', 'AGENCIA DE VIAJES Y TURISMO AVIATUR SAS'), (r'TRAVEL SECURITY', 'TRAVEL SECURITY SA'), (r'\bSWIFT\b', 'SWIFT'),
    (r'PERSHING', 'PERSHING LLC'), (r'ALLFUNDS', 'ALLFUNDS BANK SA'), (r'MORNINGSTAR', 'MORNINGSTAR'), (r'\bBBH\b|BROWN BROTHERS', 'BROWN BROTHERS HARRIMAN'),
    (r'SCOTIA', 'SCOTIABANK'), (r'\bBBVA\b', 'BBVA'), (r'CAVALI', 'CAVALI'), (r'LATAM', 'LATAM AIRLINES'), (r'AVIANCA', 'AVIANCA'),
    (r'\bDHL\b', 'DHL'), (r'FEDEX', 'FEDEX'), (r'ICAP', 'ICAP'), (r'DATATEC', 'DATATEC'), (r'\bDCV\b', 'DEPOSITO CENTRAL DE VALORES'),
    (r'BOLSA ELECTRONICA', 'BOLSA ELECTRONICA DE CHILE'), (r'BOLSA DE COMERCIO', 'BOLSA DE COMERCIO DE SANTIAGO'),
    (r'EXPERIAN', 'EXPERIAN'), (r'EQUIFAX', 'EQUIFAX'), (r'MICROSOFT', 'MICROSOFT'), (r'GOOGLE', 'GOOGLE'), (r'AMAZON|\bAWS\b', 'AMAZON'),
    (r'LINKEDIN', 'LINKEDIN'), (r'\bZOOM\b', 'ZOOM'), (r'ORACLE', 'ORACLE'), (r'ALPACA', 'ALPACA'), (r'VICCTUS|VICTTUS', 'VICCTUS'),
    (r'CORREOS DE CHILE', 'CORREOS DE CHILE'), (r'CHILEXPRESS', 'CHILEXPRESS'),
]
MARCAS = [(re.compile(rx), p) for rx, p in MARCAS]
PREFIJOS_PROV = [
    re.compile(r'PENDIENTE (?:SII|BITACORA|BITARCORA)\s+(.+)'),
    re.compile(r'MOV(?:IMIENTOS)? NO FACTURADOS\s+(.+)'),
    re.compile(r'RENDICI[OÓ]N PENDIENTE\s+(.+)'),
    re.compile(r'^FACTURA (?:INV )?([A-Z][A-Z&\.\' ]{3,}?)(?:\s*/|\s+\d|$)'),
    re.compile(r'^FRA (?:F )?([A-Z][A-Z&\.\' ]{3,}?)\s*/'),
]

MESES = r'\b(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|SETIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)\b'

def proveedor_desde_texto(texto):
    t = sin_acentos(str(texto or '')).upper().strip()
    t = re.sub(MESES, ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if not t or t in SIN_PROV:
        return None
    for rx in PREFIJOS_PROV:
        m = rx.search(t)
        if m:
            p = re.sub(r'[\d\-/\(\)\{\}#]+.*$', '', m.group(1)).strip(' .-')
            if len(p) >= 4:
                return p
    for rx, p in MARCAS:
        if rx.search(t):
            return p
    return None

def es_sin_proveedor(p):
    return not isinstance(p, str) or sin_acentos(p).upper().strip() in SIN_PROV

class Homologador:
    """Agrupa variantes de un mismo proveedor bajo un único nombre visible.
    La clave del nombre original y la del nombre homologado de los archivos se unen (union-find)."""
    def __init__(self, proveedores, mapa_archivos=None):
        self.mapa = mapa_archivos or {}
        self.padre = {}
        cnt = defaultdict(Counter)
        for p, n in proveedores.items():
            if es_sin_proveedor(p):
                continue
            raw = re.sub(r'\s+', ' ', str(p)).strip(' .,"')
            k1 = clave_proveedor(raw)
            k2 = clave_proveedor(str(self.mapa.get(p, raw)))
            if not k1:
                continue
            self._union(k1, k2 or k1)
            cnt[k1][raw] += n
        # claves que sólo difieren por un token final basura (p.ej. "...SERVICES LLCC")
        for k in list(cnt):
            toks = k.split()
            if len(toks) >= 3 and (len(toks[-1]) <= 2 or toks[-1].isdigit() or toks[-1] in ('LLCC', 'LLCCIN', 'CIN', 'INCCI', 'CDT')):
                base = ' '.join(toks[:-1])
                if base in cnt and len(base.split()) >= 2:
                    self._union(k, base)
        grupos = defaultdict(Counter)
        for k, c in cnt.items():
            grupos[self._find(k)].update(c)
        nombre = {g: sorted(c.items(), key=lambda kv: (-kv[1], not kv[0].isupper()))[0][0] for g, c in grupos.items()}
        self.canon = {k: nombre[self._find(k)] for k in list(self.padre)}
        self.alias = {}

    def _find(self, k):
        self.padre.setdefault(k, k)
        while self.padre[k] != k:
            self.padre[k] = self.padre[self.padre[k]]; k = self.padre[k]
        return k

    def _union(self, a, b):
        ra, rb = self._find(a), self._find(b)
        if ra != rb: self.padre[rb] = ra

    def nombre(self, p, texto=None):
        if es_sin_proveedor(p):
            q = proveedor_desde_texto(texto)
            if not q:
                return '(sin proveedor)'
            p = q
        raw = re.sub(r'\s+', ' ', str(p)).strip(' .,"')
        for k in (clave_proveedor(raw), clave_proveedor(str(self.mapa.get(p, raw)))):
            if k and k in self.canon:
                return self.canon[k]
        k = clave_proveedor(raw)
        if not k:
            return '(sin proveedor)'
        toks = k.split()                      # p.ej. nombre sacado del texto con basura al final
        for n in range(len(toks) - 1, 1, -1):
            c = ' '.join(toks[:n])
            if c in self.canon:
                return self.canon[c]
        return raw
