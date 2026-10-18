"""Glosas para Depreciación y Amortización (por clase de activo y tipo de movimiento)."""
import re
from homologacion import sin_acentos, glosa_cuenta, es_sin_proveedor

GLOSA_DYA = {
    'AMORTIZACION ADECUACIONES ELECTRICAS': 'Amortización adecuaciones eléctricas', 'AMORTIZACION COSTOS DE IMPLEMENTACIÓN': 'Amortización costos de implementación',
    'AMORTIZACION LICENCIAS DE SOFTWARE': 'Amortización licencias de software', 'AMORTIZACION MEJORAS A PROPIEDADES AJENAS': 'Amortización mejoras en oficinas arrendadas',
    'AMORTIZACION SOFTWARE': 'Amortización de software', 'AMORTIZACIÓN SOFTWARE': 'Amortización de software',
    'AMORTIZACION SOFTWARE DESARROLLO INTERNO': 'Amortización software de desarrollo interno', 'Amortization - Leasehold Improv': 'Amortización mejoras en oficinas arrendadas',
    'Amortization - Web Development': 'Amortización desarrollo web', 'DEPRECIACION EDIFICACIONES': 'Depreciación de edificaciones',
    'DEPRECIACION EQ.DE TELECOMUNICACIONES': 'Depreciación equipos de telecomunicaciones', 'DEPRECIACION EQUIPO DE COMPUTACION': 'Depreciación equipos de cómputo',
    'DEPRECIACIÓN COMPUTADORES': 'Depreciación equipos de cómputo', 'DEPRECIACION EQUIPO DE OFICINA': 'Depreciación muebles y equipos de oficina',
    'DEPRECIACIÓN MAQUINAS Y EQUIPOS DE OF.': 'Depreciación muebles y equipos de oficina', 'DEPRECIACION EQUIPO ELECTRONICO': 'Depreciación equipos electrónicos',
    'DEPRECIACIÓN EQUIPOS DIVERSOS': 'Depreciación equipos diversos', 'Depreciation - Equipment': 'Depreciación de equipos', 'Depreciation - Furn & Equip': 'Depreciación muebles y equipos de oficina',
    'Depreciation - Furniture': 'Depreciación de mobiliario', 'Depreciation - Leasehold Improvements': 'Amortización mejoras en oficinas arrendadas',
    'Depreciation - Software': 'Amortización de software', 'Depreciation - Software Core': 'Amortización software core bancario', 'Depreciation Expense': 'Depreciación de activos',
    'GASTOS NO DEDUCIBLES': 'Gastos no deducibles', 'SERVICIO DE SOPORTE RELACIONADAS': 'Depreciación cobrada por relacionadas', 'SUSCRIPCIONES': 'Suscripciones',
}
def glosa_dya(cuenta, texto):
    base = GLOSA_DYA.get(cuenta) or glosa_cuenta(cuenta)
    t = sin_acentos(str(texto or '')).upper()
    if re.search(r'\bBAJA\b.*VALOR NETO|DADO DE BAJA', t):
        return f'Baja de activos - {base.lower()}'
    if re.search(r'DEPRECIACION ACELERADA', t):
        return f'{base} (depreciación acelerada)'
    return base

def proveedor_dya(homol, prov, texto, cuenta, glosa):
    if es_sin_proveedor(prov) or str(prov).strip().upper() in ('OTROS', 'PTY', 'NA') or re.fullmatch(r'[\d\s\-/\.]+', str(prov).strip()):
        return '(sin proveedor)'
    return homol.nombre(prov, texto)
