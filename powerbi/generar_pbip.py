"""Genera el proyecto Power BI (.pbip) del Entregable 1 - Contable con el tema Credicorp Capital.

Estructura que crea en "01. Power BI/":
  Ppto27 Contable.pbip
  Ppto27 Contable.SemanticModel/   model.bim (tablas, tipos, relaciones, medidas, parámetro RutaDatos) + definition.pbism
  Ppto27 Contable.Report/          report.json (3 páginas) + definition.pbir + tema
  Tema Credicorp Capital.json      el mismo tema, para importarlo en cualquier otro reporte

Dos orígenes de datos (mismo reporte, mismas medidas y relaciones):
  python3 generar_pbip.py              → "01. Power BI/"              CSV (parámetro RutaDatos)
  python3 generar_pbip.py databricks   → "01. Power BI (Databricks)/" conector Azure Databricks (guía corporativa):
        Databricks.Catalogs(Hostname, HttpPath) → Catalogo → Esquema → ppto27_gld_<tabla>, modo Import, autenticación
        Azure Active Directory (cuenta Credicorp Capital). Parámetros: Hostname, HttpPath, Catalogo, Esquema.
"""
import json, os, sys, uuid
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
ENT = os.path.dirname(AQUI)                                       # 02. Entregable 1 - Contable
TOP = os.path.dirname(ENT)                                        # 05. Databricks
CSV = os.path.join(TOP, '01. Datos ejemplo (CSV)')
ORIGEN = 'databricks' if 'databricks' in sys.argv[1:] else 'csv'
OUT = os.path.join(ENT, '01. Power BI (Databricks)' if ORIGEN == 'databricks' else '01. Power BI')
NOMBRE = 'Ppto27 Contable'
RUTA_DEFECTO = 'C:\\Ppto27\\01. Datos ejemplo (CSV)\\'
# conexión Databricks (se cambian en Power BI: Transformar datos > Editar parámetros)
DBX_HOSTNAME = os.environ.get('DBX_HOSTNAME', 'adb-XXXXXXXXXXXX.X.azuredatabricks.net')   # SQL Warehouse > Connection details
DBX_HTTPPATH = '/sql/1.0/warehouses/COMPLETAR'                        # SQL Warehouses > (warehouse) > Connection details > HTTP path
DBX_CATALOGO, DBX_ESQUEMA = 'catalogo_ppto', 'esquema_ppto'

# ───────────────────────── tema Credicorp Capital ─────────────────────────
CORAL, OSCURO, GRIS, GRIS_CL, FONDO, CREMA = '#E86953', '#2F3437', '#8C9D9D', '#E3E7E7', '#F6F7F7', '#FFF4D6'
F_REG = 'Inter, Segoe UI, wf_segoe-ui_normal, helvetica, arial, sans-serif'
F_SEMI = 'Inter SemiBold, Segoe UI Semibold, wf_segoe-ui_semibold, helvetica, arial, sans-serif'
TEMA = {
    'name': 'Credicorp Capital',
    'dataColors': [CORAL, OSCURO, GRIS, '#F2B84B', '#5B9A68', '#B5523B', '#C9D1D1', '#6E7B7B', '#F4A78F', '#4A5458'],
    'background': '#FFFFFF', 'foreground': OSCURO, 'tableAccent': CORAL,
    'good': '#5B9A68', 'neutral': '#F2B84B', 'bad': '#C0392B',
    'maximum': CORAL, 'center': '#F2B84B', 'minimum': '#FBE3DF', 'null': GRIS_CL,
    'textClasses': {
        'callout': {'fontSize': 26, 'fontFace': F_SEMI, 'color': OSCURO},
        'title': {'fontSize': 11, 'fontFace': F_SEMI, 'color': OSCURO},
        'header': {'fontSize': 11, 'fontFace': F_SEMI, 'color': OSCURO},
        'label': {'fontSize': 9, 'fontFace': F_REG, 'color': OSCURO},
    },
    'visualStyles': {
        '*': {'*': {
            'background': [{'show': True, 'color': {'solid': {'color': '#FFFFFF'}}, 'transparency': 0}],
            'border': [{'show': True, 'color': {'solid': {'color': GRIS_CL}}, 'radius': 6}],
            'dropShadow': [{'show': False}],
            'title': [{'show': True, 'fontColor': {'solid': {'color': OSCURO}}, 'fontSize': 11, 'fontFamily': F_SEMI}],
            'visualHeader': [{'foreground': {'solid': {'color': GRIS}}, 'border': {'solid': {'color': GRIS_CL}}}],
            'padding': [{'top': 8, 'bottom': 8, 'left': 10, 'right': 10}],
        }},
        'page': {'*': {'background': [{'color': {'solid': {'color': FONDO}}, 'transparency': 0}],
                       'outspace': [{'color': {'solid': {'color': FONDO}}, 'transparency': 0}]}},
        'card': {'*': {'labels': [{'color': {'solid': {'color': OSCURO}}, 'fontSize': 22, 'fontFamily': F_SEMI}],
                       'categoryLabels': [{'color': {'solid': {'color': GRIS}}, 'fontSize': 9}],
                       'border': [{'show': True, 'color': {'solid': {'color': GRIS_CL}}, 'radius': 6}]}},
        'slicer': {'*': {'items': [{'fontColor': {'solid': {'color': OSCURO}}, 'textSize': 9}],
                         'header': [{'fontColor': {'solid': {'color': CORAL}}, 'textSize': 9}]}},
        'tableEx': {'*': {'columnHeaders': [{'backColor': {'solid': {'color': OSCURO}}, 'fontColor': {'solid': {'color': '#FFFFFF'}}}],
                          'values': [{'backColorSecondary': {'solid': {'color': FONDO}}}],
                          'grid': [{'gridHorizontalColor': {'solid': {'color': GRIS_CL}}}]}},
        'pivotTable': {'*': {'columnHeaders': [{'backColor': {'solid': {'color': OSCURO}}, 'fontColor': {'solid': {'color': '#FFFFFF'}}}],
                             'rowHeaders': [{'fontColor': {'solid': {'color': OSCURO}}}],
                             'subTotals': [{'backColor': {'solid': {'color': CREMA}}}],
                             'grandTotal': [{'backColor': {'solid': {'color': '#FBE3DF'}}}]}},
        'clusteredColumnChart': {'*': {'dataPoint': [{'defaultColor': {'solid': {'color': CORAL}}}]}},
        'clusteredBarChart': {'*': {'dataPoint': [{'defaultColor': {'solid': {'color': CORAL}}}]}},
    },
}

# ───────────────────────── modelo semántico ─────────────────────────
TABLAS = ['fact_ppto', 'fact_flags', 'dim_linea_pyg', 'dim_fecha', 'dim_pais', 'dim_ceco', 'dim_vehiculo', 'dim_cuenta', 'dim_proveedor',
          'dim_plantilla', 'dim_flag']
ENTEROS = {'id_fecha', 'id_cuenta', 'id_proveedor', 'anio', 'mes_num', 'ceco', 'id_linea_pyg', 'orden_n1', 'orden_n2'}
DECIMALES = {'monto_origen', 'monto_local', 'monto_pen'}
FECHAS = {'fecha'}
OCULTAS_PREFIJO = ('id_',)
SORT_BY = {('dim_fecha', 'periodo'): 'mes_num', ('dim_fecha', 'mes'): 'mes_num',
           ('dim_linea_pyg', 'n1_formato'): 'orden_n1', ('dim_linea_pyg', 'n2_formato'): 'orden_n2'}
RELACIONES = [('fact_ppto', 'id_linea_pyg', 'dim_linea_pyg', 'id_linea_pyg'), ('fact_ppto', 'id_fecha', 'dim_fecha', 'id_fecha'), ('fact_ppto', 'id_pais', 'dim_pais', 'id_pais'),
              ('fact_ppto', 'id_ceco', 'dim_ceco', 'id_ceco'), ('fact_ppto', 'id_vehiculo', 'dim_vehiculo', 'id_vehiculo'),
              ('fact_ppto', 'id_cuenta', 'dim_cuenta', 'id_cuenta'), ('fact_ppto', 'id_proveedor', 'dim_proveedor', 'id_proveedor'),
              ('fact_ppto', 'id_plantilla', 'dim_plantilla', 'id_plantilla'),
              ('fact_flags', 'id_plantilla', 'dim_plantilla', 'id_plantilla'), ('fact_flags', 'codigo_flag', 'dim_flag', 'codigo_flag')]
VALIDAS = '{ "OK", "OK con alerta" }'
MEDIDAS = {
    'fact_ppto': [
        ('Ppto PEN', f'CALCULATE ( SUM ( fact_ppto[monto_pen] ), fact_ppto[estado_linea] IN {VALIDAS} )', '#,0;(#,0)', 'Ppto 2027 contable en PEN (líneas válidas). Gasto en negativo.'),
        ('Gasto PEN', '- [Ppto PEN]', '#,0', 'Mismo Ppto en positivo, para gráficos.'),
        ('Ppto Moneda Local', f'IF ( HASONEVALUE ( dim_pais[id_pais] ), CALCULATE ( SUM ( fact_ppto[monto_local] ), fact_ppto[estado_linea] IN {VALIDAS} ) )', '#,0;(#,0)', 'Sólo con un país seleccionado (no se suman monedas distintas).'),
        ('Gasto Moneda Local', '- [Ppto Moneda Local]', '#,0', 'Moneda local en positivo.'),
        ('Ppto Cuarentena PEN', 'CALCULATE ( SUM ( fact_ppto[monto_pen] ), fact_ppto[estado_linea] = "Cuarentena" )', '#,0;(#,0)', 'Ppto de líneas con ERROR: no entra al contable.'),
        ('Ppto Total Cargado PEN', 'SUM ( fact_ppto[monto_pen] )', '#,0;(#,0)', 'Todo lo que trajeron las plantillas (válido + cuarentena): control 100 = 100.'),
        ('% Cuarentena', 'DIVIDE ( [Ppto Cuarentena PEN], [Ppto Total Cargado PEN] )', '0.0%', ''),
        ('Líneas', 'DISTINCTCOUNT ( fact_ppto[id_linea] )', '#,0', 'Líneas de plantilla con Ppto 2027.'),
        ('Plantillas', 'DISTINCTCOUNT ( fact_ppto[id_plantilla] )', '#,0', ''),
        ('Gasto PEN Mes Anterior', 'CALCULATE ( [Gasto PEN], DATEADD ( dim_fecha[fecha], -1, MONTH ) )', '#,0', ''),
        ('Var % vs Mes Anterior', 'DIVIDE ( [Gasto PEN] - [Gasto PEN Mes Anterior], [Gasto PEN Mes Anterior] )', '0.0%', ''),
    ],
    'fact_flags': [
        ('Flags', 'COUNTROWS ( fact_flags )', '#,0', ''),
        ('Flags Error', 'CALCULATE ( [Flags], dim_flag[severidad] IN { "BLOQUEANTE", "ERROR" } )', '#,0', ''),
        ('Flags Alerta', 'CALCULATE ( [Flags], dim_flag[severidad] = "ALERTA" )', '#,0', ''),
        ('Plantillas con Error', 'CALCULATE ( DISTINCTCOUNT ( fact_flags[id_plantilla] ), dim_flag[severidad] IN { "BLOQUEANTE", "ERROR" } )', '#,0', ''),
    ],
}


def tipo(tabla, col):
    if col in ENTEROS:
        return 'int64'
    if col in DECIMALES:
        return 'double'
    if col in FECHAS:
        return 'dateTime'
    return 'string'


def m_tabla(tabla, cols):
    pq = {'int64': 'Int64.Type', 'double': 'type number', 'dateTime': 'type date', 'string': 'type text'}
    tipos = ', '.join(f'{{"{c}", {pq[tipo(tabla, c)]}}}' for c in cols)
    if ORIGEN == 'databricks':
        lista = ', '.join(f'"{c}"' for c in cols)
        return [
            'let',
            '    // Conexión al SQL Warehouse de Databricks (parámetros Hostname y HttpPath)',
            '    Origen = Databricks.Catalogs(Hostname, HttpPath, [Catalog = null, Database = null, EnableAutomaticProxyDiscovery = null]),',
            '    CatalogoUC = Origen{[Name = Catalogo, Kind = "Database"]}[Data],',
            '    EsquemaUC = CatalogoUC{[Name = Esquema, Kind = "Schema"]}[Data],',
            f'    Tabla = EsquemaUC{{[Name = "ppto27_gld_{tabla}", Kind = "Table"]}}[Data],',
            '    // Sólo las columnas que usa el modelo (buena práctica: nada de select *)',
            f'    Columnas = Table.SelectColumns(Tabla, {{{lista}}}),',
            f'    Tipos = Table.TransformColumnTypes(Columnas, {{{tipos}}}, "en-US")',
            'in',
            '    Tipos',
        ]
    return [
        'let',
        '    Carpeta = if Text.EndsWith(Text.Trim(RutaDatos), "\\") then Text.Trim(RutaDatos) else Text.Trim(RutaDatos) & "\\",',
        f'    Origen = Csv.Document(File.Contents(Carpeta & "{tabla}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        '    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),',
        '    SinBOM = Table.TransformColumnNames(Encabezados, each Text.Replace(_, Character.FromNumber(65279), "")),',
        f'    Tipos = Table.TransformColumnTypes(SinBOM, {{{tipos}}}, "en-US")',
        'in',
        '    Tipos',
    ]


def _param(nombre, valor, desc):
    return {'name': nombre, 'kind': 'm', 'description': desc,
            'expression': f'"{valor}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]'}


def EXPRESIONES():
    if ORIGEN == 'databricks':
        return [_param('Hostname', DBX_HOSTNAME, 'Server hostname del SQL Warehouse (Databricks > SQL Warehouses > Connection details)'),
                _param('HttpPath', DBX_HTTPPATH, 'HTTP path del SQL Warehouse (Databricks > SQL Warehouses > Connection details)'),
                _param('Catalogo', DBX_CATALOGO, 'Catálogo de Unity Catalog donde están las tablas ppto27_gld_*'),
                _param('Esquema', DBX_ESQUEMA, 'Esquema de Unity Catalog donde están las tablas ppto27_gld_*')]
    return [_param('RutaDatos', RUTA_DEFECTO, 'Carpeta con los CSV (terminar en \\).')]


def modelo():
    tablas = []
    columnas = {}
    for t in TABLAS:
        cols = list(pd.read_csv(os.path.join(CSV, f'{t}.csv'), nrows=1, encoding='utf-8-sig').columns)
        columnas[t] = cols
        tc = []
        for c in cols:
            d = {'name': c, 'dataType': tipo(t, c), 'sourceColumn': c,
                 'summarizeBy': 'sum' if c in DECIMALES else 'none'}
            if c.startswith(OCULTAS_PREFIJO) or c in ('hash', 'orden_n1', 'orden_n2'):
                d['isHidden'] = True
            if c in DECIMALES:
                d['formatString'] = '#,0.00'
            if c in FECHAS:
                d['formatString'] = 'dd/mm/yyyy'
            if (t, c) in SORT_BY:
                d['sortByColumn'] = SORT_BY[(t, c)]
            if t == 'dim_fecha' and c == 'fecha':
                d['isKey'] = True
            tc.append(d)
        tab = {'name': t, 'columns': tc,
               'partitions': [{'name': t, 'mode': 'import', 'source': {'type': 'm', 'expression': m_tabla(t, cols)}}]}
        if t == 'dim_fecha':
            tab['dataCategory'] = 'Time'
        if t in MEDIDAS:
            tab['measures'] = [{'name': n, 'expression': e, 'formatString': f, **({'description': d} if d else {}),
                                'displayFolder': 'Calidad' if t == 'fact_flags' else 'Ppto'} for n, e, f, d in MEDIDAS[t]]
        tablas.append(tab)
    rel = [{'name': str(uuid.uuid5(uuid.NAMESPACE_DNS, f'{a}.{b}->{c}.{d}')), 'fromTable': a, 'fromColumn': b,
            'toTable': c, 'toColumn': d} for a, b, c, d in RELACIONES]
    bim = {
        'name': NOMBRE, 'compatibilityLevel': 1567,
        'model': {
            'culture': 'es-ES', 'sourceQueryCulture': 'es-ES',
            'dataAccessOptions': {'legacyRedirects': True, 'returnErrorValuesAsNull': True},
            'defaultPowerBIDataSourceVersion': 'powerBI_V3',
            'tables': tablas, 'relationships': rel,
            'expressions': EXPRESIONES(),
            'annotations': [{'name': 'PBI_QueryOrder', 'value': json.dumps([e['name'] for e in EXPRESIONES()] + TABLAS)},
                            {'name': '__PBI_TimeIntelligenceEnabled', 'value': '0'},
                            {'name': 'PBIDesktopVersion', 'value': '2.130.0'}],
        },
    }
    return bim, columnas


# ───────────────────────── reporte ─────────────────────────
ALIAS = {}


def ref(tabla, campo, medida=False):
    return {'tabla': tabla, 'campo': campo, 'medida': medida}


def proto(campos):
    """prototypeQuery a partir de una lista de campos {tabla, campo, medida}."""
    frm, sel = [], []
    for c in campos:
        t = c['tabla']
        if t not in [f['Entity'] for f in frm]:
            frm.append({'Name': f'a{len(frm)}', 'Entity': t, 'Type': 0})
        alias = next(f['Name'] for f in frm if f['Entity'] == t)
        k = 'Measure' if c['medida'] else 'Column'
        sel.append({k: {'Expression': {'SourceRef': {'Source': alias}}, 'Property': c['campo']}, 'Name': f"{t}.{c['campo']}"})
    return {'Version': 2, 'From': frm, 'Select': sel}


def titulo_obj(texto):
    return {'title': [{'properties': {'show': {'expr': {'Literal': {'Value': 'true'}}},
                                      'text': {'expr': {'Literal': {'Value': f"'{texto}'"}}}}}]}


def visual(nombre, tipo_v, x, y, w, h, roles, titulo=None, objetos=None, z=0):
    campos = [c for lista in roles.values() for c in lista]
    proj = {rol: [{'queryRef': f"{c['tabla']}.{c['campo']}", **({'active': True} if not c['medida'] and rol in ('Category', 'Rows') else {})}
                  for c in lista] for rol, lista in roles.items()}
    sv = {'visualType': tipo_v, 'projections': proj, 'prototypeQuery': proto(campos), 'drillFilterOtherVisuals': True}
    vco = {}
    if titulo:
        vco.update(titulo_obj(titulo))
    if vco:
        sv['vcObjects'] = vco
    if objetos:
        sv['objects'] = objetos
    cfg = {'name': nombre, 'layouts': [{'id': 0, 'position': {'x': x, 'y': y, 'z': z, 'width': w, 'height': h}}], 'singleVisual': sv}
    return {'x': x, 'y': y, 'z': z, 'width': w, 'height': h, 'config': json.dumps(cfg, ensure_ascii=False), 'filters': '[]'}


def texto(nombre, x, y, w, h, corridas, z=0):
    sv = {'visualType': 'textbox', 'drillFilterOtherVisuals': True,
          'objects': {'general': [{'properties': {'paragraphs': [{'textRuns': corridas}]}}]},
          'vcObjects': {'background': [{'properties': {'show': {'expr': {'Literal': {'Value': 'false'}}}}}],
                        'border': [{'properties': {'show': {'expr': {'Literal': {'Value': 'false'}}}}}]}}
    cfg = {'name': nombre, 'layouts': [{'id': 0, 'position': {'x': x, 'y': y, 'z': z, 'width': w, 'height': h}}], 'singleVisual': sv}
    return {'x': x, 'y': y, 'z': z, 'width': w, 'height': h, 'config': json.dumps(cfg, ensure_ascii=False), 'filters': '[]'}


def encabezado(pagina, titulo):
    return [texto(f'{pagina}_marca', 24, 12, 400, 24, [{'value': 'CREDICORP CAPITAL', 'textStyle': {'fontWeight': 'bold', 'fontSize': '9pt', 'color': CORAL}}]),
            texto(f'{pagina}_titulo', 24, 32, 820, 40, [{'value': titulo, 'textStyle': {'fontWeight': 'bold', 'fontSize': '18pt', 'color': OSCURO}}])]


def slicer(nombre, x, y, w, h, campo, titulo):
    return visual(nombre, 'slicer', x, y, w, h, {'Values': [campo]}, titulo,
                  objetos={'data': [{'properties': {'mode': {'expr': {'Literal': {'Value': "'Dropdown'"}}}}}]})


def seccion(nombre, display, contenedores, orden):
    return {'name': nombre, 'displayName': display, 'displayOption': 1, 'width': 1280, 'height': 720,
            'config': '{}', 'filters': '[]', 'ordinal': orden, 'visualContainers': contenedores}


def reporte(tema_archivo):
    pais = ref('dim_pais', 'pais_bi'); periodo = ref('dim_fecha', 'periodo'); tipo_pl = ref('dim_plantilla', 'tipo')
    area = ref('dim_plantilla', 'area'); n2 = ref('dim_linea_pyg', 'n2_formato'); agr = ref('dim_ceco', 'agrupacion')
    n1 = ref('dim_linea_pyg', 'n1_formato'); ppto = ref('fact_ppto', 'Ppto PEN', True)
    ceco = ref('dim_ceco', 'ceco_nombre'); gasto = ref('fact_ppto', 'Gasto PEN', True)
    filtros = lambda p: [slicer(f'{p}_s_pais', 880, 14, 125, 58, pais, 'País'), slicer(f'{p}_s_tipo', 1015, 14, 125, 58, tipo_pl, 'Tipo'),
                         slicer(f'{p}_s_mes', 1150, 14, 110, 58, periodo, 'Mes')]
    p0 = encabezado('p0', 'Ppto 2027 · Formato Perú (Nivel 1 y Nivel 2)') + filtros('p0') + [
        slicer('p0_s_area', 24, 84, 300, 58, area, 'Área / UdN'),
        slicer('p0_s_ceco', 334, 84, 300, 58, agr, 'Agrupación CeCo'),
        visual('p0_k1', 'card', 644, 84, 300, 58, {'Values': [ppto]}, 'Ppto 2027 (PEN)'),
        visual('p0_k2', 'card', 954, 84, 302, 58, {'Values': [ref('fact_ppto', 'Ppto Moneda Local', True)]}, 'Ppto moneda local (elige un país)'),
        visual('p0_m1', 'pivotTable', 24, 156, 1232, 546, {'Rows': [n1, n2], 'Columns': [periodo], 'Values': [ppto]},
               'Gastos por Nivel 1 y Nivel 2 · PEN (gasto en negativo)'),
    ]
    p1 = encabezado('p1', 'Ppto 2027 · Vista contable') + filtros('p1') + [
        visual('p1_k1', 'card', 24, 90, 295, 100, {'Values': [gasto]}, 'Gasto Ppto 2027 (PEN)'),
        visual('p1_k2', 'card', 334, 90, 295, 100, {'Values': [ref('fact_ppto', 'Gasto Moneda Local', True)]}, 'Gasto en moneda local (elige un país)'),
        visual('p1_k3', 'card', 644, 90, 295, 100, {'Values': [ref('fact_ppto', 'Plantillas', True)]}, 'Plantillas con Ppto'),
        visual('p1_k4', 'card', 954, 90, 302, 100, {'Values': [ref('fact_ppto', '% Cuarentena', True)]}, '% del Ppto en cuarentena'),
        visual('p1_c1', 'clusteredColumnChart', 24, 206, 615, 240, {'Category': [periodo], 'Y': [gasto]}, 'Gasto mensual (PEN)'),
        visual('p1_c2', 'clusteredBarChart', 654, 206, 602, 240, {'Category': [n2], 'Y': [gasto]}, 'Gasto por Nivel 2 (PEN)'),
        visual('p1_m1', 'pivotTable', 24, 462, 1232, 240, {'Rows': [pais, tipo_pl], 'Columns': [ref('dim_fecha', 'trimestre')], 'Values': [gasto]},
               'País y tipo de plantilla por trimestre (PEN)'),
    ]
    p2 = encabezado('p2', 'Detalle por CeCo y cuenta') + filtros('p2') + [
        slicer('p2_s_area', 24, 84, 300, 58, area, 'Área / UdN'),
        slicer('p2_s_n1', 334, 84, 300, 58, n1, 'Nivel 1'),
        visual('p2_m1', 'pivotTable', 24, 156, 1232, 300, {'Rows': [agr, ceco], 'Columns': [periodo], 'Values': [gasto]}, 'Gasto por agrupación y CeCo (PEN)'),
        visual('p2_t1', 'tableEx', 24, 470, 1232, 232,
               {'Values': [ref('dim_ceco', 'ceco_nombre'), ref('dim_vehiculo', 'vehiculo'), ref('dim_cuenta', 'nom_cta_contable'),
                           ref('dim_proveedor', 'proveedor'), gasto]}, 'Detalle por cuenta y proveedor'),
    ]
    sev = ref('dim_flag', 'severidad')
    p3 = encabezado('p3', 'Calidad de las plantillas (flags)') + [
        slicer('p3_s_sev', 880, 14, 185, 58, sev, 'Severidad'), slicer('p3_s_pais', 1075, 14, 185, 58, ref('dim_plantilla', 'pais'), 'País'),
        visual('p3_k1', 'card', 24, 90, 295, 100, {'Values': [ref('fact_flags', 'Flags', True)]}, 'Flags detectados'),
        visual('p3_k2', 'card', 334, 90, 295, 100, {'Values': [ref('fact_flags', 'Flags Error', True)]}, 'Flags de error'),
        visual('p3_k3', 'card', 644, 90, 295, 100, {'Values': [ref('fact_flags', 'Plantillas con Error', True)]}, 'Plantillas con error'),
        visual('p3_k4', 'card', 954, 90, 302, 100, {'Values': [ref('fact_ppto', 'Ppto Cuarentena PEN', True)]}, 'Ppto en cuarentena (PEN)'),
        visual('p3_c1', 'clusteredBarChart', 24, 206, 500, 496, {'Category': [ref('dim_flag', 'flag')], 'Y': [ref('fact_flags', 'Flags', True)]}, 'Flags por tipo'),
        visual('p3_t1', 'tableEx', 539, 206, 717, 496,
               {'Values': [ref('dim_plantilla', 'archivo'), ref('dim_flag', 'codigo_flag'), sev, ref('fact_flags', 'celdas'), ref('fact_flags', 'detalle')]},
               'Detalle de flags por plantilla'),
    ]
    cfg = {'version': '5.55',
           'themeCollection': {'baseTheme': {'name': 'CY24SU10', 'version': '5.55', 'type': 2},
                               'customTheme': {'name': tema_archivo, 'version': '5.55', 'type': 1}},
           'activeSectionIndex': 0, 'defaultDrillFilterOtherVisuals': True,
           'settings': {'useNewFilterPaneExperience': True, 'allowChangeFilterTypes': True, 'useStylableVisualContainerHeader': True,
                        'exportDataMode': 1}}
    return {
        'config': json.dumps(cfg),
        'layoutOptimization': 0,
        'resourcePackages': [
            {'resourcePackage': {'disabled': False, 'items': [{'name': 'CY24SU10', 'path': 'BaseThemes/CY24SU10.json', 'type': 202}],
                                 'name': 'SharedResources', 'type': 2}},
            {'resourcePackage': {'disabled': False, 'items': [{'name': tema_archivo, 'path': tema_archivo, 'type': 201}],
                                 'name': 'RegisteredResources', 'type': 1}}],
        'sections': [seccion('ReportSection0', 'Formato Perú', p0, 0), seccion('ReportSection1', 'Resumen', p1, 1),
                     seccion('ReportSection2', 'Detalle CeCo', p2, 2), seccion('ReportSection3', 'Calidad', p3, 3)],
    }, [p0, p1, p2, p3]


def escribir(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        if isinstance(obj, str):
            fh.write(obj)
        else:
            json.dump(obj, fh, ensure_ascii=False, indent=2)


def main():
    bim, columnas = modelo()
    tema_archivo = 'CredicorpCapital.json'
    rep, paginas = reporte(tema_archivo)

    # validar que todo campo usado en el reporte exista en el modelo
    medidas = {(t, m[0]) for t, ms in MEDIDAS.items() for m in ms}
    faltan = set()
    for pag in paginas:
        for vc in pag:
            sv = json.loads(vc['config'])['singleVisual']
            for s in sv.get('prototypeQuery', {}).get('Select', []):
                t, c = s['Name'].split('.', 1)
                if 'Measure' in s and (t, c) not in medidas or 'Column' in s and c not in columnas.get(t, []):
                    faltan.add(s['Name'])
    assert not faltan, f'Campos inexistentes en el modelo: {faltan}'

    SM, RP = f'{NOMBRE}.SemanticModel', f'{NOMBRE}.Report'
    escribir(os.path.join(OUT, f'{NOMBRE}.pbip'),
             {'version': '1.0', 'artifacts': [{'report': {'path': RP}}], 'settings': {'enableAutoRecovery': True}})
    escribir(os.path.join(OUT, SM, 'model.bim'), bim)
    escribir(os.path.join(OUT, SM, 'definition.pbism'), {'version': '1.0', 'settings': {}})
    escribir(os.path.join(OUT, SM, '.platform'), {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json',
                                                   'metadata': {'type': 'SemanticModel', 'displayName': NOMBRE},
                                                   'config': {'version': '2.0', 'logicalId': str(uuid.uuid5(uuid.NAMESPACE_DNS, SM))}})
    escribir(os.path.join(OUT, RP, 'report.json'), rep)
    escribir(os.path.join(OUT, RP, 'definition.pbir'), {'version': '1.0', 'datasetReference': {'byPath': {'path': f'../{SM}'}, 'byConnection': None}})
    escribir(os.path.join(OUT, RP, '.platform'), {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json',
                                                   'metadata': {'type': 'Report', 'displayName': NOMBRE},
                                                   'config': {'version': '2.0', 'logicalId': str(uuid.uuid5(uuid.NAMESPACE_DNS, RP))}})
    escribir(os.path.join(OUT, RP, 'StaticResources', 'RegisteredResources', tema_archivo), TEMA)
    escribir(os.path.join(OUT, RP, 'StaticResources', 'SharedResources', 'BaseThemes', 'CY24SU10.json'),
             {'name': 'CY24SU10', 'dataColors': TEMA['dataColors'], 'background': '#FFFFFF', 'foreground': OSCURO, 'tableAccent': CORAL})
    escribir(os.path.join(OUT, '.gitignore'), '**/.pbi/localSettings.json\n**/.pbi/cache.abf\n')
    escribir(os.path.join(ENT, 'Tema Credicorp Capital.json'), TEMA)
    n_vis = sum(len(p) for p in paginas)
    print(f'PBIP generado en {OUT}\n  {len(bim["model"]["tables"])} tablas · {len(bim["model"]["relationships"])} relaciones · '
          f'{sum(len(v) for v in MEDIDAS.values())} medidas · {len(paginas)} páginas · {n_vis} visuales')


if __name__ == '__main__':
    main()
