"""Generate documented PBIP/PBIR metadata; Power BI Desktop loads the data."""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "powerbi"
BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


TABLES = {
    "Eventos": (
        "FactEvent",
        [
            ("event_id", "string"),
            ("time_utc", "dateTime"),
            ("date_key", "int64"),
            ("latitude", "double"),
            ("longitude", "double"),
            ("depth_km", "double"),
            ("magnitude", "double"),
            ("magnitude_type", "string"),
            ("zone_key", "int64"),
            ("magnitude_key", "int64"),
            ("depth_band", "string"),
            ("place", "string"),
            ("status", "string"),
            ("updated_utc", "dateTime"),
            ("source_url", "string"),
        ],
    ),
    "Calendario": (
        "DimDate",
        [
            ("date_key", "int64"),
            ("date", "dateTime"),
            ("year", "int64"),
            ("month", "int64"),
            ("year_month", "string"),
            ("month_start", "dateTime"),
        ],
    ),
    "Zona": (
        "DimZone",
        [
            ("zone_key", "int64"),
            ("zone", "string"),
            ("latitude_min", "double"),
            ("latitude_max", "double"),
        ],
    ),
    "Magnitud": (
        "DimMagnitude",
        [
            ("magnitude_key", "int64"),
            ("magnitude_band", "string"),
            ("magnitude_min", "double"),
            ("magnitude_max", "double"),
        ],
    ),
    "Ejecuciones": (
        "ETLRun",
        [
            ("run_id", "string"),
            ("completed_utc", "dateTime"),
            ("start_date", "dateTime"),
            ("end_date", "dateTime"),
            ("min_magnitude", "double"),
            ("received", "int64"),
            ("loaded", "int64"),
            ("rejected", "int64"),
            ("duplicates_removed", "int64"),
        ],
    ),
}
MEASURES = [
    ("Eventos registrados", "COALESCE(COUNTROWS(Eventos),0)", "#,0"),
    ("Magnitud máxima", "MAX(Eventos[magnitude])", "0.0"),
    ("Magnitud media", "AVERAGE(Eventos[magnitude])", "0.00"),
    ("Profundidad media (km)", "AVERAGE(Eventos[depth_km])", "0.0"),
    (
        "Eventos M5+",
        "COALESCE(CALCULATE(COUNTROWS(Eventos),KEEPFILTERS(Eventos[magnitude]>=5)),0)",
        "#,0",
    ),
    (
        "Porcentaje superficiales",
        "DIVIDE(CALCULATE(COUNTROWS(Eventos),KEEPFILTERS(Eventos[depth_km]<70)),COUNTROWS(Eventos))",
        "0.0%",
    ),
    (
        "Eventos mes anterior",
        "CALCULATE([Eventos registrados],DATEADD(Calendario[date],-1,MONTH))",
        "#,0",
    ),
    (
        "Variación mensual",
        "DIVIDE([Eventos registrados]-[Eventos mes anterior],[Eventos mes anterior])",
        "0.0%",
    ),
    (
        "Eventos año anterior",
        "CALCULATE([Eventos registrados],DATEADD(Calendario[date],-1,YEAR))",
        "#,0",
    ),
    ("Fecha último evento", "MAX(Eventos[time_utc])", "dd/MM/yyyy HH:mm"),
    ("Título panorama", '"PERÚ Y ENTORNO | Sismicidad"', None),
    ("Título distribución", '"DISTRIBUCIÓN | Magnitud y profundidad"', None),
    ("Título calidad", '"DATOS | Trazabilidad y calidad"', None),
    (
        "Alcance",
        'VAR Ultima = TOPN(1,ALL(Ejecuciones),Ejecuciones[completed_utc],DESC) RETURN "USGS · M ≥" & FORMAT(MAXX(Ultima,Ejecuciones[min_magnitude]),"0.0") & " · " & FORMAT(MAXX(Ultima,Ejecuciones[start_date]),"yyyy-MM-dd") & " a " & FORMAT(MAXX(Ultima,Ejecuciones[end_date])-1,"yyyy-MM-dd") & " · UTC"',
        None,
    ),
    (
        "Nota de alcance",
        '[Alcance] & " | Lat. -20 a 0 / lon. -84 a -68 (mar y países vecinos)."',
        None,
    ),
    (
        "Nota científica",
        '"Análisis descriptivo del catálogo; no predicción ni evaluación de riesgo."',
        None,
    ),
    (
        "Nota zonas",
        '"Norte/Centro/Sur son bandas latitudinales, no regiones administrativas."',
        None,
    ),
    ("Última extracción", "MAX(Ejecuciones[completed_utc])", "dd/MM/yyyy HH:mm"),
    (
        "Filas recibidas",
        "VAR Ultima = TOPN(1,ALL(Ejecuciones),Ejecuciones[completed_utc],DESC) RETURN MAXX(Ultima,Ejecuciones[received])",
        "#,0",
    ),
    (
        "Filas rechazadas",
        "VAR Ultima = TOPN(1,ALL(Ejecuciones),Ejecuciones[completed_utc],DESC) RETURN MAXX(Ultima,Ejecuciones[rejected])",
        "#,0",
    ),
    (
        "Duplicados eliminados",
        "VAR Ultima = TOPN(1,ALL(Ejecuciones),Ejecuciones[completed_utc],DESC) RETURN MAXX(Ultima,Ejecuciones[duplicates_removed])",
        "#,0",
    ),
]


def model(mode):
    load_dotenv(ROOT / ".env")
    server = os.getenv("SQL_SERVER", "localhost").replace('"', '""')
    tables = []
    types = {
        "string": "type text",
        "int64": "Int64.Type",
        "double": "type number",
        "dateTime": "type datetime",
    }
    for name, (sql_table, columns) in TABLES.items():
        if mode == "sql":
            expr = [
                "let",
                f'    Source = Sql.Database("{server}", "SeismicAnalytics", [CreateNavigationProperties=false]),',
                f'    Data = Source{{[Schema="dbo",Item="{sql_table}"]}}[Data]',
                "in",
                "    Data",
            ]
        else:
            files = {
                "Eventos": "fact_event.csv",
                "Calendario": "dim_date.csv",
                "Zona": "dim_zone.csv",
                "Magnitud": "dim_magnitude.csv",
                "Ejecuciones": "etl_runs.csv",
            }
            path = (ROOT / "data" / "processed" / files[name]).as_posix()
            typed = ", ".join('{"' + c + '", ' + types[t] + "}" for c, t in columns)
            expr = [
                "let",
                f'    Source = Csv.Document(File.Contents("{path}"),[Delimiter=",",Encoding=65001,QuoteStyle=QuoteStyle.Csv]),',
                "    Headers = Table.PromoteHeaders(Source,[PromoteAllScalars=true]),",
                f'    Data = Table.TransformColumnTypes(Headers,{{{typed}}},"en-US")',
                "in",
                "    Data",
            ]
        cols = []
        for c, t in columns:
            col = {"name": c, "dataType": t, "sourceColumn": c, "summarizeBy": "none"}
            if c.endswith("_key") or c == "run_id":
                col["isHidden"] = True
            if t == "dateTime":
                col["formatString"] = "yyyy-MM-dd HH:mm:ss" if c.endswith("_utc") else "yyyy-MM-dd"
            if c == "latitude":
                col["dataCategory"] = "Latitude"
            if c == "longitude":
                col["dataCategory"] = "Longitude"
            if c == "source_url":
                col["dataCategory"] = "WebUrl"
            if c == "magnitude":
                col["formatString"] = "0.0"
            if c == "depth_km":
                col["formatString"] = "0.0"
            cols.append(col)
        table = {
            "name": name,
            "columns": cols,
            "partitions": [
                {"name": name, "mode": "import", "source": {"type": "m", "expression": expr}}
            ],
        }
        if name == "Eventos":
            table["measures"] = [
                {
                    "name": n,
                    "expression": e,
                    **({"formatString": f} if f else {}),
                    "displayFolder": "Indicadores"
                    if not n.startswith(("Título", "Nota", "Alcance"))
                    else "Contexto",
                }
                for n, e, f in MEASURES
            ]
        if name == "Calendario":
            table["dataCategory"] = "Time"
            for col in cols:
                if col["name"] == "date":
                    col["isKey"] = True
                if col["name"] == "year_month":
                    col["sortByColumn"] = "month_start"
        if name == "Magnitud":
            for col in cols:
                if col["name"] == "magnitude_band":
                    col["sortByColumn"] = "magnitude_key"
        tables.append(table)
    relationships = [
        {
            "name": "Eventos_" + table,
            "fromTable": "Eventos",
            "fromColumn": key,
            "toTable": table,
            "toColumn": key,
            "fromCardinality": "many",
            "toCardinality": "one",
            "crossFilteringBehavior": "oneDirection",
        }
        for table, key in [
            ("Calendario", "date_key"),
            ("Zona", "zone_key"),
            ("Magnitud", "magnitude_key"),
        ]
    ]
    return {
        "name": "PeruSeismicAnalytics",
        "compatibilityLevel": 1601,
        "model": {
            "culture": "es-PE",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": tables,
            "relationships": relationships,
            "annotations": [{"name": "PBI_TimeIntelligenceEnabled", "value": "0"}],
        },
    }


def literal(v):
    text = (
        "true"
        if v is True
        else "false"
        if v is False
        else str(v) + "D"
        if isinstance(v, (int, float))
        else "'" + v.replace("'", "''") + "'"
    )
    return {"expr": {"Literal": {"Value": text}}}


def color(v):
    return {"solid": {"color": literal(v)}}


def field(table, column, measure=False):
    return {
        "Measure" if measure else "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": column,
        }
    }


def proj(table, column, measure=False, label=None):
    return {
        "field": field(table, column, measure),
        "queryRef": table + "." + column,
        "nativeQueryRef": column,
        **({"displayName": label} if label else {}),
    }


def average(table, column):
    return {
        "field": {"Aggregation": {"Expression": field(table, column), "Function": 1}},
        "queryRef": f"Avg({table}.{column})",
        "nativeQueryRef": column,
    }


def visual(page, name, kind, x, y, w, h, roles, title=None, subtitle=None, sort=None, objects=None):
    vc = {
        "background": [
            {
                "properties": {
                    "show": literal(True),
                    "color": color("#FFFFFF"),
                    "transparency": literal(0),
                }
            }
        ],
        "border": [
            {
                "properties": {
                    "show": literal(True),
                    "color": color("#E1E8EF"),
                    "radius": literal(10),
                }
            }
        ],
    }
    if title:
        vc["title"] = [
            {
                "properties": {
                    "show": literal(True),
                    "text": literal(title),
                    "fontSize": literal(12),
                    "fontColor": color("#16334D"),
                    "bold": literal(True),
                }
            }
        ]
    if subtitle:
        vc["subTitle"] = [
            {
                "properties": {
                    "show": literal(True),
                    "text": literal(subtitle),
                    "fontSize": literal(9),
                    "fontColor": color("#64748B"),
                }
            }
        ]
    q = {"queryState": {role: {"projections": values} for role, values in roles.items()}}
    if sort:
        q["sortDefinition"] = {
            "sort": [{"field": sort[0], "direction": sort[1]}],
            "isDefaultSort": False,
        }
    value = {
        "$schema": BASE + "visualContainer/2.4.0/schema.json",
        "name": name,
        "position": {
            "x": x,
            "y": y,
            "z": len(
                list((OUT / "Seismic.Report" / "definition" / "pages" / page / "visuals").glob("*"))
            )
            if (OUT / "Seismic.Report" / "definition" / "pages" / page / "visuals").exists()
            else 0,
            "width": w,
            "height": h,
            "tabOrder": 0,
        },
        "visual": {
            "visualType": kind,
            "query": q,
            "visualContainerObjects": vc,
            "drillFilterOtherVisuals": True,
        },
    }
    if objects:
        value["visual"]["objects"] = objects
    save(
        OUT / "Seismic.Report" / "definition" / "pages" / page / "visuals" / name / "visual.json",
        value,
    )


def card(page, name, measure, x, y, w=280, h=100, font=32, header=False):
    obj = {
        "labels": [{"properties": {"fontSize": literal(font), "color": color("#0E7490")}}],
        "categoryLabels": [
            {
                "properties": {
                    "show": literal(not header),
                    "color": color("#475569"),
                    "fontSize": literal(11),
                }
            }
        ],
    }
    visual(
        page, name, "card", x, y, w, h, {"Values": [proj("Eventos", measure, True)]}, objects=obj
    )


def chart(page, name, kind, table, col, title, x, y, w, h, subtitle=None):
    visual(
        page,
        name,
        kind,
        x,
        y,
        w,
        h,
        {"Category": [proj(table, col)], "Y": [proj("Eventos", "Eventos registrados", True)]},
        title,
        subtitle,
        sort=(field(table, col), "Ascending"),
    )


def slicer(page, name, table, col, x, w, title):
    visual(
        page,
        name,
        "slicer",
        x,
        100,
        w,
        72,
        {"Values": [proj(table, col, label=title)]},
        title,
        objects={
            "data": [{"properties": {"mode": literal("Dropdown")}}],
            "header": [{"properties": {"show": literal(False)}}],
        },
    )


def build(mode):
    save(
        OUT / "Seismic.pbip",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": "Seismic.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    save(
        OUT / "Seismic.SemanticModel" / "definition.pbism",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "1.0",
            "settings": {},
        },
    )
    save(OUT / "Seismic.SemanticModel" / "model.bim", model(mode))
    save(
        OUT / "Seismic.Report" / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../Seismic.SemanticModel"}},
        },
    )
    definition = OUT / "Seismic.Report" / "definition"
    save(
        definition / "version.json",
        {"$schema": BASE + "versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
    )
    save(
        definition / "report.json",
        {
            "$schema": BASE + "report/3.1.0/schema.json",
            "themeCollection": {},
            "settings": {
                "useStylableVisualContainerHeader": True,
                "exportDataMode": "AllowSummarized",
                "defaultDrillFilterOtherVisuals": True,
            },
        },
    )
    pages = [
        ("panorama", "01 · Panorama", "Título panorama"),
        ("distribucion", "02 · Distribución", "Título distribución"),
        ("calidad", "03 · Datos y calidad", "Título calidad"),
    ]
    save(
        definition / "pages" / "pages.json",
        {
            "$schema": BASE + "pagesMetadata/1.0.0/schema.json",
            "pageOrder": [p[0] for p in pages],
            "activePageName": "panorama",
        },
    )
    for page, label, title in pages:
        save(
            definition / "pages" / page / "page.json",
            {
                "$schema": BASE + "page/2.0.0/schema.json",
                "name": page,
                "displayName": label,
                "displayOption": "FitToPage",
                "width": 1280,
                "height": 820,
                "objects": {
                    "background": [
                        {"properties": {"color": color("#F3F6FA"), "transparency": literal(0)}}
                    ]
                },
            },
        )
        card(page, "encabezado", title, 24, 18, 1232, 68, 26, True)
    page = "panorama"
    slicer(page, "filtro_anio", "Calendario", "year", 24, 280, "Año")
    slicer(page, "filtro_zona", "Zona", "zone", 320, 430, "Banda latitudinal")
    slicer(page, "filtro_magnitud", "Magnitud", "magnitude_band", 766, 490, "Rango de magnitud")
    for i, m in enumerate(
        ["Eventos registrados", "Magnitud máxima", "Eventos M5+", "Porcentaje superficiales"]
    ):
        card(page, "kpi_" + str(i), m, 24 + i * 312, 188, 296, 104)
    visual(
        page,
        "evolucion",
        "lineChart",
        24,
        308,
        800,
        350,
        {
            "Category": [proj("Calendario", "month_start", label="Mes")],
            "Y": [proj("Eventos", "Eventos registrados", True)],
        },
        "Evolución mensual de eventos",
        "El último mes puede estar incompleto; los ceros describen el catálogo consultado.",
        sort=(field("Calendario", "month_start"), "Ascending"),
        objects={
            "categoryAxis": [
                {"properties": {"axisType": literal("Scalar"), "fontSize": literal(10)}}
            ]
        },
    )
    chart(
        page,
        "zonas",
        "barChart",
        "Zona",
        "zone",
        "Eventos por banda latitudinal",
        840,
        308,
        416,
        350,
    )
    card(page, "nota_alcance", "Nota de alcance", 24, 675, 1232, 55, 13, True)
    card(page, "nota_cientifica", "Nota científica", 24, 744, 1232, 52, 13, True)
    page = "distribucion"
    slicer(page, "filtro_anio", "Calendario", "year", 24, 280, "Año")
    slicer(page, "filtro_zona", "Zona", "zone", 320, 430, "Banda latitudinal")
    slicer(page, "filtro_magnitud", "Magnitud", "magnitude_band", 766, 490, "Rango de magnitud")
    chart(
        page,
        "rangos",
        "columnChart",
        "Magnitud",
        "magnitude_band",
        "Distribución por magnitud",
        24,
        188,
        608,
        250,
    )
    chart(
        page,
        "profundidad",
        "barChart",
        "Eventos",
        "depth_band",
        "Distribución por profundidad",
        648,
        188,
        608,
        250,
    )
    visual(
        page,
        "coordenadas",
        "scatterChart",
        24,
        454,
        800,
        276,
        {
            "Category": [proj("Eventos", "event_id")],
            "X": [average("Eventos", "longitude")],
            "Y": [average("Eventos", "latitude")],
        },
        "Ubicación de los eventos",
        "Coordenadas del epicentro; sin clasificación por departamento.",
    )
    card(page, "profundidad_media", "Profundidad media (km)", 840, 454, 416, 128)
    card(page, "magnitud_media", "Magnitud media", 840, 598, 416, 132)
    card(page, "nota_zonas", "Nota zonas", 24, 745, 1232, 51, 13, True)
    page = "calidad"
    for i, m in enumerate(
        ["Filas recibidas", "Filas rechazadas", "Duplicados eliminados", "Última extracción"]
    ):
        card(page, "calidad_" + str(i), m, 24 + i * 312, 108, 296, 108, 24)
    visual(
        page,
        "detalle",
        "tableEx",
        24,
        232,
        1232,
        458,
        {
            "Values": [
                proj("Eventos", c, label=l)
                for c, l in [
                    ("time_utc", "Fecha UTC"),
                    ("place", "Ubicación informada"),
                    ("magnitude", "Magnitud"),
                    ("depth_km", "Profundidad (km)"),
                    ("magnitude_type", "Tipo"),
                    ("status", "Revisión"),
                    ("event_id", "ID USGS"),
                ]
            ]
        },
        "Eventos del catálogo",
        sort=(field("Eventos", "time_utc"), "Descending"),
    )
    card(page, "ultimo_evento", "Fecha último evento", 24, 706, 440, 90, 22)
    card(page, "nota_cientifica", "Nota científica", 480, 706, 776, 90, 13, True)
    dax = "\n\n".join(f"{n} =\n{e}" for n, e, f in MEASURES)
    (OUT / "Medidas.dax").write_text(dax, encoding="utf-8")
    print("Power BI project generated:", OUT / "Seismic.pbip", "source:", mode)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["sql", "csv"], default="sql")
    args = p.parse_args()
    build(args.source)
