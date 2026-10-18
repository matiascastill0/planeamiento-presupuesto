"""Glosas para Remuneración Fija, Incentivo Corto Plazo y Remuneración Variable (nómina: sin proveedor)."""
import re
from homologacion import sin_acentos, glosa_cuenta

GLOSA_REM = {
    '(vacío)': 'Reclasificación de cargas laborales', 'BONIFICACION POR MERA LIBERALIDAD': 'Bonificación por mera liberalidad', 'BONO': 'Bono anual',
    'BONOS AL PERSONAL': 'Bono anual', 'BONOS MULTIPLO SALARIO-INCENTIVO CORTO PLAZO': 'Bono múltiplo salario (ICP)', 'BONOS MULTIPLO SALARIO-REMUNERACIONES': 'Bono de cumplimiento (provisión)',
    'Bonuses - Other': 'Bonos', 'Bonuses - discret': 'Bonos discrecionales', 'Bonuses - discretionary': 'Bonos discrecionales', 'CARGAS LABORALES': 'Cargas laborales',
    'GESTIÓN - GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores', 'OTRAS REMUNERACIONES - BONO ANUAL': 'Bono anual (provisión ICP)',
    'OTROS INGRESOS - EJERCICIOS ANTERIORES': 'Extorno provisión año anterior', 'PROVISION BONOS': 'Provisión de bonos', 'PROVISION DE BONO': 'Provisión de bonos',
    'Payroll Expenses': 'Nómina', 'Personnel - Other Fees': 'Provisión ICP y RV', 'RECUPERACIÓN BONO DE CUMPLIMIENTO': 'Recuperación bono de cumplimiento',
    '2.5% SOBRE NOMINAS': 'Impuesto 2,5% sobre nómina', 'APORTE PENSIONES': 'Aporte a pensiones', 'APORTES CAJA DE COMPENSACION': 'Aporte caja de compensación',
    'APORTES ICBF': 'Aporte ICBF', 'APORTES SALUD': 'Aporte a salud', 'APORTES SERVICIO NACIONAL DE APRENDIZAJE': 'Aporte SENA', 'ATENCIÓN AL PERSONAL - RECREATIVOS': 'Aguinaldo y canastas',
    'AUXILIO DE CONECTIVIDAD': 'Auxilio de conectividad', 'BONIFICACION DE RETIRO NO SALARIAL': 'Bonificación de retiro', 'BONOS GARANTIZADOS-REMUNERACIONES': 'Bono garantizado',
    'CESANTIA Y VEJEZ PATRONAL': 'Cesantía y vejez patronal (IMSS)', 'CESANTIAS': 'Cesantías', 'COMISION OTROS RELACIONADAS -EXTERIOR': 'Recupero de remuneraciones (relacionadas)',
    'COMPENSACIÓN POR TIEMPO DE SERVICIOS CTS': 'CTS (compensación por tiempo de servicios)', 'CONDICION DE TRABAJO ESPECIAL': 'Condición de trabajo especial', 'Employee Benefits': 'Beneficios al personal',
    'GASTOS NO DEDUCIBLES': 'Gastos no deducibles', 'GRATIFICACIONES': 'Gratificaciones', 'HORAS EXTRA': 'Horas extra', 'INCAPACIDADES': 'Incapacidades',
    'INDEMNIZACION EMPLEADOS': 'Indemnizaciones', 'INDEMNIZACIONES': 'Indemnizaciones y finiquitos', 'INDEMNIZACIONES AL PERSONAL': 'Indemnizaciones',
    'INTERESES CESANTIAS': 'Intereses sobre cesantías', 'OTRAS BONIFICACIONES': 'Otras bonificaciones', 'OTRAS REMUNERACIONES': 'Otras remuneraciones',
    'OTRAS REMUNERACIONES - BONIFICACIONES': 'Bonificaciones', 'OTRAS REMUNERACIONES - BONO CAMBIO DE TARGET': 'Bono cambio de target', 'OTRAS REMUNERACIONES - ESCOLARIDAD': 'Asignación por escolaridad',
    'OTRAS REMUNERACIONES - MOVILIDAD': 'Movilidad', 'OTRAS REMUNERACONES - BONO GARANTIZADO': 'Bono garantizado', 'OTROS INGRESOS - EXTORNO DE PROV EJERCICIOS ANTERIORES': 'Extorno provisión año anterior',
    'PRIMA DE SERVICIOS': 'Prima de servicios', 'PROVISION AGUINALDO': 'Provisión aguinaldo', 'PROVISION PRIMA VACACIONAL': 'Provisión prima vacacional',
    'PROVISIONES DE GASTOS DE EJERCICIOS ANTERIORES': 'Ajustes de ejercicios anteriores', 'PROVISIÓN VACACIONES': 'Provisión de vacaciones', 'Payroll Taxes': 'Impuestos sobre nómina',
    'Personnel - Consultants': 'Vales de alimentación', 'Personnel - Indemnities & Seniority Premium': 'Indemnizaciones y prima de antigüedad', 'Personnel - Salaries and Wages': 'Sueldos y salarios',
    'Personnel - Social Security Tax': 'Seguro social', 'Personnel - Tax - Education Insurance': 'Seguro educativo', 'Personnel - Tax - Professional Risk': 'Riesgos profesionales',
    'Personnel - Vacations': 'Vacaciones', 'Personnel - XIII Month': 'Décimo tercer mes', 'REMUNERACIONES': 'Remuneraciones', 'RIESGOS LABORALES': 'Riesgos laborales (ARL)',
    'SALARIO BASICO': 'Salario básico', 'SALARIO INTEGRAL': 'Salario integral', 'SEGURO DE VIDA - ESSALUD': 'EsSalud', 'SEGURO DE VIDA COLECTIVA - AFILIADA': 'Seguro vida ley',
    'SIGNINGS': 'Signing bonus', 'SUBSIDIO DE TRANSPORTE': 'Subsidio de transporte', 'SUELDO Y SALARIOS - BÁSICA': 'Sueldo básico', 'SUELDOS': 'Sueldos', 'VACACIONES': 'Vacaciones',
    'VACACIONES - PROVISIÓN': 'Provisión de vacaciones', 'BONOS MULTIPLO SALARIO-REMUNERACION VARIABLE': 'Remuneración variable (provisión)', "Brokers' Commissions": 'Comisiones de brokers',
    'COMISIONES EMPLEADO': 'Comisiones', 'OTRAS REMUNERACIONES - INCENTIVO POR PRODUCTIVIDAD': 'Incentivo por productividad', 'Personal - Variable Compensation': 'Remuneración variable',
    'REMUNERACION VARIABLE': 'Remuneración variable', 'SUELDO Y SALARIOS - VARIABLE': 'Sueldo variable (comisiones)',
}
def glosa_rem(cuenta, texto):
    base = GLOSA_REM.get(cuenta) or glosa_cuenta(cuenta)
    t = sin_acentos(str(texto or '')).upper()
    if base == 'Remuneraciones' and re.search(r'PROVISI', t): return 'Remuneraciones (provisión)'
    if base == 'Nómina' and re.search(r'401K|MATCH', t): return 'Aporte 401K'
    if base == 'Beneficios al personal' and re.search(r'INTERNET BONUS', t): return 'Bono de internet'
    return base

def proveedor_rem(homol, prov, texto, cuenta, glosa):
    return '(sin proveedor)'       # nómina: no hay proveedor
