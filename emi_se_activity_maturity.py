from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import plotly.express as px
from neo4j import GraphDatabase

from config import DEFAULT_DATABASE, DEFAULT_URI, DEFAULT_USER




# ============================================================
# Step 1: Run this ONCE to get global log min/max across all years
# Then pass as fixed parameters to the main EMI query
# ============================================================

EMI_GLOBAL_MINMAX_QUERY = """
MATCH (a:SEActivity)<-[:USED_FOR]-(t:SETask)
OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
WHERE m IS NOT NULL AND m.createdAt IS NOT NULL

WITH a,
     count(DISTINCT t)                          AS taskCount,
     count(DISTINCT m)                          AS totalModels,
     count(DISTINCT CASE WHEN m IS NULL THEN t END) AS tasksWithoutModels

WITH a, taskCount, totalModels, tasksWithoutModels,
     CASE WHEN tasksWithoutModels < taskCount
          THEN toFloat(totalModels) / (taskCount - tasksWithoutModels)
          ELSE 1.0 END AS avgModelsPerTask

RETURN
    min(CASE WHEN avgModelsPerTask > 0 THEN log(avgModelsPerTask) ELSE log(1.0) END) AS globalLogMin,
    max(CASE WHEN avgModelsPerTask > 0 THEN log(avgModelsPerTask) ELSE log(1.0) END) AS globalLogMax
"""

# ============================================================
# Step 2: Main EMI query — pass $year, $logMin, $logMax
# ============================================================

EMI_QUERY = """
// ============================================================
// Ecosystem Maturity Index (EMI) — Per SEActivity with Year Filter
// Weights:
//   avgModelsPerTask (log-norm, FIXED global scale) : 0.20
//   benchmarkCompletenessRatio                      : 0.30
//   coverage (1 - tasksWithoutRatio)                : 0.20
//   datasetCompletenessRatio                        : 0.10
//   paperCompletenessRatio                          : 0.10
//   spaceCompletenessRatio                          : 0.05
//   collectionCompletenessRatio                     : 0.05
//
// IMPORTANT: $logMin and $logMax are fixed global anchors
//            computed once across ALL years so that EMI scores
//            are comparable across time (no normalization artifact).
// ============================================================

MATCH (a:SEActivity)<-[:USED_FOR]-(t:SETask)

OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
WHERE m IS NULL
   OR (m.createdAt IS NOT NULL AND toInteger(substring(toString(m.createdAt), 0, 4)) <= toInteger($year))

WITH a,
     count(DISTINCT t)                                               AS taskCount,
     count(DISTINCT m)                                               AS totalModels,
     count(DISTINCT CASE WHEN m IS NULL THEN t END)                  AS tasksWithoutModels

WITH a,
     taskCount,
     totalModels,
     tasksWithoutModels,
     toFloat(tasksWithoutModels) / taskCount                         AS tasksWithoutModelsRatio,
     CASE WHEN tasksWithoutModels < taskCount
          THEN toFloat(totalModels) / (taskCount - tasksWithoutModels)
          ELSE 0.0 END                                               AS avgModelsPerTask

MATCH (a)<-[:USED_FOR]-(t2:SETask)
MATCH (m2:Model)-[:SUITABLE_FOR]->(t2)
WHERE m2.createdAt IS NOT NULL
  AND toInteger(substring(toString(m2.createdAt), 0, 4)) <= toInteger($year)

OPTIONAL MATCH (m2)-[:TRAINED_ON]->(d:Dataset)
WHERE d IS NULL
   OR (d.createdAt IS NOT NULL AND toInteger(substring(toString(d.createdAt), 0, 4)) <= toInteger($year))

OPTIONAL MATCH (m2)-[:CITES]->(p:Paper)
WHERE p IS NULL
   OR (p.publishedAt IS NOT NULL AND toInteger(substring(toString(p.publishedAt), 0, 4)) <= toInteger($year))

OPTIONAL MATCH (m2)-[:EVALUATED_ON]->(b:Benchmark)
WHERE b IS NULL
   OR (b.createdAt IS NOT NULL AND toInteger(substring(toString(b.createdAt), 0, 4)) <= toInteger($year))

OPTIONAL MATCH (c:Collection)-[:CONTAINS]->(m2)
OPTIONAL MATCH (s:Space)-[:USES_MODEL]->(m2)
OPTIONAL MATCH (s2:Space)-[:USES_DATASET]->(d)

WITH a,
     taskCount, totalModels, tasksWithoutModels,
     tasksWithoutModelsRatio, avgModelsPerTask,
     count(DISTINCT m2)                                                          AS modelsInScope,
     count(DISTINCT CASE WHEN d  IS NOT NULL THEN m2 END)                        AS withDataset,
     count(DISTINCT CASE WHEN p  IS NOT NULL THEN m2 END)                        AS withPaper,
     count(DISTINCT CASE WHEN b  IS NOT NULL THEN m2 END)                        AS withBenchmark,
     count(DISTINCT CASE WHEN c  IS NOT NULL THEN m2 END)                        AS withCollection,
     count(DISTINCT CASE WHEN (s IS NOT NULL OR s2 IS NOT NULL) THEN m2 END)     AS withSpace

WITH a,
     taskCount, totalModels, tasksWithoutModels,
     tasksWithoutModelsRatio, avgModelsPerTask, modelsInScope,
     CASE WHEN modelsInScope > 0 THEN toFloat(withDataset)    / modelsInScope ELSE 0.0 END AS datasetRatio,
     CASE WHEN modelsInScope > 0 THEN toFloat(withPaper)      / modelsInScope ELSE 0.0 END AS paperRatio,
     CASE WHEN modelsInScope > 0 THEN toFloat(withBenchmark)  / modelsInScope ELSE 0.0 END AS benchmarkRatio,
     CASE WHEN modelsInScope > 0 THEN toFloat(withCollection) / modelsInScope ELSE 0.0 END AS collectionRatio,
     CASE WHEN modelsInScope > 0 THEN toFloat(withSpace)      / modelsInScope ELSE 0.0 END AS spaceRatio,
     // Normalize avgModelsPerTask using FIXED global log min/max (passed as params)
     CASE WHEN $logMax > $logMin
          THEN (log(CASE WHEN avgModelsPerTask > 0 THEN avgModelsPerTask ELSE 1.0 END) - $logMin)
               / ($logMax - $logMin)
          ELSE 0.0 END                                                           AS avgModels_lognorm

WITH a,
     taskCount, totalModels, tasksWithoutModels,
     tasksWithoutModelsRatio, avgModelsPerTask, avgModels_lognorm, modelsInScope,
     datasetRatio, paperRatio, benchmarkRatio, collectionRatio, spaceRatio,
     round(1000 * (
         avgModels_lognorm                    * 0.30 +
         benchmarkRatio                       * 0.30 +
         (1.0 - tasksWithoutModelsRatio)      * 0.20 +
         datasetRatio                         * 0.10 +
         paperRatio                           * 0.10 +
         spaceRatio                           * 0.00 +
         collectionRatio                      * 0.00
     )) / 1000.0 AS EMI

RETURN
    toInteger($year)                                                    AS year,
    a.id                                                                AS seActivity,
    taskCount,
    totalModels,
    tasksWithoutModels,
    round(1000 * tasksWithoutModelsRatio)    / 1000.0                  AS tasksWithoutModelsRatio,
    round(1000 * avgModelsPerTask)           / 1000.0                  AS avgModelsPerTask,
    round(1000 * avgModels_lognorm)          / 1000.0                  AS avgModels_lognorm,
    round(1000 * (1.0 - tasksWithoutModelsRatio)) / 1000.0             AS coverage,
    round(1000 * datasetRatio)               / 1000.0                  AS datasetCompletenessRatio,
    round(1000 * collectionRatio)            / 1000.0                  AS collectionCompletenessRatio,
    round(1000 * spaceRatio)                 / 1000.0                  AS spaceCompletenessRatio,
    round(1000 * benchmarkRatio)             / 1000.0                  AS benchmarkCompletenessRatio,
    round(1000 * paperRatio)                 / 1000.0                  AS paperCompletenessRatio,
    EMI
ORDER BY EMI DESC
"""

# ============================================================
# Step 3: Python usage — run global anchors once, then loop years
# ============================================================

# import math
# from neo4j import GraphDatabase
#
# driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
#
# with driver.session() as session:
#     # Get fixed global anchors ONCE
#     anchors = session.run(EMI_GLOBAL_MINMAX_QUERY).single()
#     log_min = anchors["globalLogMin"]
#     log_max = anchors["globalLogMax"]
#
#     # Loop over years using the same fixed anchors
#     all_results = []
#     for year in range(2019, 2026):
#         results = session.run(EMI_QUERY, year=year, logMin=log_min, logMax=log_max)
#         for r in results:
#             all_results.append(dict(r))



def run_query_for_years(
    uri: str,
    username: str,
    password: str,
    database: str,
    years: Iterable[int],
) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    driver = GraphDatabase.driver(uri, auth=(username, password))

    try:
        with driver.session(database=database) as session:
            anchor_row = session.run(EMI_GLOBAL_MINMAX_QUERY).single()
            if anchor_row is None:
                return pd.DataFrame()

            log_min = float(anchor_row.get("globalLogMin", 0.0) or 0.0)
            log_max = float(anchor_row.get("globalLogMax", 0.0) or 0.0)

            for year in years:
                records = session.run(
                    EMI_QUERY,
                    year=int(year),
                    logMin=log_min,
                    logMax=log_max,
                ).data()
                frame = pd.DataFrame(records)
                if frame.empty:
                    continue
                frames.append(frame)
    finally:
        driver.close()

    if not frames:
        return pd.DataFrame()

    out_df = pd.concat(frames, ignore_index=True)
    out_df["seActivity"] = out_df["seActivity"].fillna("UnknownActivity").astype(str)
    return out_df


def save_outputs(df: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "emi_seactivity_raw.csv"
    df.to_csv(csv_path, index=False)

    trend_fig = px.line(
        df.sort_values(["year", "seActivity"]),
        x="year",
        y="EMI",
        color="seActivity",
        markers=True,
        title="SEActivity Ecosystem Maturity (EMI) Over Time",
    )
    trend_fig.update_layout(legend_title_text="SEActivity")
    trend_fig.write_html(str(output_dir / "emi_trend_by_activity.html"), include_plotlyjs="cdn")

    heat_df = (
        df.pivot_table(index="seActivity", columns="year", values="EMI", aggfunc="mean")
        .sort_index()
        .reset_index()
    )
    heat_melt = heat_df.melt(id_vars=["seActivity"], var_name="year", value_name="EMI")
    heat_fig = px.density_heatmap(
        heat_melt,
        x="year",
        y="seActivity",
        z="EMI",
        color_continuous_scale="Viridis",
        title="SEActivity EMI Heatmap",
    )
    heat_fig.write_html(str(output_dir / "emi_heatmap.html"), include_plotlyjs="cdn")

    metric_fig = px.line(
        df.sort_values(["year", "seActivity"]),
        x="year",
        y="tasksWithoutModelsRatio",
        color="seActivity",
        markers=True,
        title="Tasks Without Models Ratio Over Time",
    )
    metric_fig.update_yaxes(range=[0, 1])
    metric_fig.write_html(str(output_dir / "tasks_without_models_ratio_trend.html"), include_plotlyjs="cdn")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EMI query across years and export charts.")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j URI (default from config.py)")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j username")
    parser.add_argument("--password", required=True, help="Neo4j password")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Neo4j database name")
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2020, 2021, 2022, 2023, 2024, 2025, 2026],
        help="Years to run, e.g. --years 2020 2021 2022 2023 2024",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/emi",
        help="Folder for CSV and HTML chart outputs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = run_query_for_years(
        uri=args.uri,
        username=args.user,
        password=args.password,
        database=args.database,
        years=args.years,
    )

    if df.empty:
        print("No rows returned for the selected years.")
        return

    save_outputs(df, Path(args.output_dir))

    summary_cols = [
        "year",
        "seActivity",
        "EMI",
        "taskCount",
        "totalModels",
        "tasksWithoutModels",
        "tasksWithoutModelsRatio",
    ]
    summary_cols = [c for c in summary_cols if c in df.columns]

    print("Saved outputs to:", Path(args.output_dir).resolve())
    print(df.sort_values(["year", "EMI"], ascending=[True, False])[summary_cols].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
