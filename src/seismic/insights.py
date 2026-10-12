import json
from pathlib import Path


def build_insights(frame, calendar, quality, document: Path, summary_path: Path):
    monthly = frame.groupby("year_month").size()
    zones = frame.groupby("zone").size().sort_values(ascending=False)
    largest = frame.sort_values("magnitude", ascending=False).iloc[0]
    metrics = {
        "events": len(frame),
        "max_magnitude": float(frame.magnitude.max()),
        "avg_magnitude": float(frame.magnitude.mean()),
        "avg_depth_km": float(frame.depth_km.mean()),
        "m5_plus": int((frame.magnitude >= 5).sum()),
        "shallow_percent": float((frame.depth_km < 70).mean() * 100),
        "busiest_month": str(monthly.idxmax()),
        "busiest_month_count": int(monthly.max()),
        "zones": {str(k): int(v) for k, v in zones.items()},
        "largest_event": {
            "id": largest.event_id,
            "magnitude": float(largest.magnitude),
            "place": largest.place,
            "date": str(largest.time_utc),
            "url": largest.source_url,
        },
        "scope": {
            "start": quality["start_inclusive"],
            "end_exclusive": quality["end_exclusive"],
            "minimum_magnitude": quality["min_magnitude"],
            "bounds": quality["bounds"],
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    document.parent.mkdir(parents=True, exist_ok=True)
    text = f"""# Resultados de la extracción

Datos reales consultados en USGS. Periodo UTC: {quality["start_inclusive"]} a {quality["end_exclusive"]} (fin excluido). Magnitud mínima: {quality["min_magnitude"]}.

- **{len(frame):,} eventos** únicos válidos dentro del área de estudio.
- **{metrics["m5_plus"]:,} eventos de magnitud ≥5**; magnitud máxima registrada: **{metrics["max_magnitude"]:.1f}**.
- El **{metrics["shallow_percent"]:.1f}%** de los eventos del catálogo tiene profundidad menor a 70 km.
- El mes con más registros en la extracción fue **{metrics["busiest_month"]}**, con **{metrics["busiest_month_count"]} eventos**.
- La banda latitudinal con más registros fue **{zones.index[0]}**, con **{int(zones.iloc[0])} eventos**.

El mayor evento consultado: [{largest.place}]({largest.source_url}), {largest.time_utc}, magnitud {largest.magnitude} ({largest.magnitude_type}).

## Interpretación y límites

Estas cifras describen el catálogo consultado, no la totalidad de sismos ocurridos. No demuestran tendencia causal, capacidad predictiva ni riesgo para una ciudad. El periodo final puede estar incompleto y el catálogo puede revisar registros. Las bandas Norte/Centro/Sur son agrupaciones analíticas de latitud, no departamentos del Perú. El rectángulo de estudio incluye mar y partes de países vecinos: por eso se denomina **Perú y entorno**. Los tipos de magnitud pueden variar; la media es solo un resumen descriptivo y la magnitud es logarítmica, no una suma de energía.

## Calidad

Recibidos: {quality["received"]:,}. Duplicados eliminados: {quality["duplicates_removed"]:,}. Excluidos por límites del estudio: {quality["excluded_by_scope"]:,}. Rechazados por datos inválidos: {quality["rejected_count"]:,}.
Los valores desconocidos de magnitud, coordenadas o tiempos no se inventan ni se rellenan con cero. Consulta `data/processed/quality.json` y los manifiestos de extracción para reproducir los resultados.
"""
    document.write_text(text, encoding="utf-8")
