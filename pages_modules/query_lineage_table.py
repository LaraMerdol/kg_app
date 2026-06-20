"""
SEModel Lineage Overview Table
===============================
Queries Neo4j to produce a flat table with:
  - SEModel ID
  - Immediate ancestor model(s) + relationship type(s)
  - Max lineage length (longest chain to root)
  - Base model(s) (root ancestor at the end of the chain)
  - SE Task(s)
  - SE Activity(ies)

Saves as CSV and optionally as Excel.

Requirements:
  pip install neo4j pandas openpyxl
"""

import os
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "01234567")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
OUTPUT_DIR = Path("lineage_table_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = OUTPUT_DIR / "se_model_lineage_table.csv"
XLSX_PATH = OUTPUT_DIR / "se_model_lineage_table.xlsx"


def query_lineage_table(driver, database=None):
    """
    Build the full lineage overview table.
    
    Strategy: run multiple focused queries and merge in Python,
    which is more robust than one massive Cypher query.
    """

    # ─── Query 1: Immediate ancestors + relationship types ───
    q_immediate = """
    MATCH (m:SEModel)
    OPTIONAL MATCH (m)-[r:IS_FINETUNED_FROM|IS_QUANTIZED_FROM|IS_ADAPTER_OF|IS_MERGE_OF]->(parent)
    WITH m,
         collect(DISTINCT parent.id) AS parent_ids,
         collect(DISTINCT type(r))   AS rel_types
    RETURN
        m.id AS model_id,
        m.name AS model_name,
        parent_ids,
        rel_types
    """

    # ─── Query 2: Max lineage length + base model(s) ───
    q_lineage = """
    MATCH (m:SEModel)
    OPTIONAL MATCH path = (m)-[:IS_FINETUNED_FROM|IS_QUANTIZED_FROM|IS_ADAPTER_OF|IS_MERGE_OF*]->(root)
    WHERE NOT (root)-[:IS_FINETUNED_FROM|IS_QUANTIZED_FROM|IS_ADAPTER_OF|IS_MERGE_OF]->()
    WITH m,
         COALESCE(MAX(length(path)), 0) AS max_lineage_length,
         collect(DISTINCT root.id)       AS base_model_ids
    RETURN
        m.id AS model_id,
        max_lineage_length,
        base_model_ids
    """

    # ─── Query 3: SE Tasks ───
    q_tasks = """
    MATCH (m:SEModel)-[:SUITABLE_FOR]->(t:SETask)
    RETURN
        m.id AS model_id,
        collect(DISTINCT t.id)   AS task_ids,
        collect(DISTINCT t.id) AS task_names
    """

    # ─── Query 4: SE Activities (via task) ───
    q_activities = """
    MATCH (m:SEModel)-[:SUITABLE_FOR]->(t:SETask)-[:USED_FOR]->(a:SEActivity)
    RETURN
        m.id AS model_id,
        collect(DISTINCT a.id)   AS activity_ids,
        collect(DISTINCT a.id) AS activity_names
    """

    session_kwargs = {"database": database} if database else {}
    with driver.session(**session_kwargs) as session:
        # Run all queries
        print("  Running query 1/4: immediate ancestors...")
        immediate_records = []
        for r in session.run(q_immediate):
            immediate_records.append({
                "model_id": r["model_id"],
                "model_name": r["model_name"],
                "immediate_ancestor_ids": r["parent_ids"],
                "ancestor_rel_types": r["rel_types"],
            })
        df_immediate = pd.DataFrame(immediate_records)
        print(f"    ✓ {len(df_immediate)} models")

        print("  Running query 2/4: lineage length + base models...")
        lineage_records = []
        for r in session.run(q_lineage):
            lineage_records.append({
                "model_id": r["model_id"],
                "max_lineage_length": r["max_lineage_length"],
                "base_model_ids": r["base_model_ids"],
            })
        df_lineage = pd.DataFrame(lineage_records)
        print(f"    ✓ {len(df_lineage)} models")

        print("  Running query 3/4: SE tasks...")
        task_records = []
        for r in session.run(q_tasks):
            task_records.append({
                "model_id": r["model_id"],
                "task_ids": r["task_ids"],
                "task_names": r["task_names"],
            })
        df_tasks = pd.DataFrame(task_records)
        print(f"    ✓ {len(df_tasks)} model-task mappings")

        print("  Running query 4/4: SE activities...")
        activity_records = []
        for r in session.run(q_activities):
            activity_records.append({
                "model_id": r["model_id"],
                "activity_ids": r["activity_ids"],
                "activity_names": r["activity_names"],
            })
        df_activities = pd.DataFrame(activity_records)
        print(f"    ✓ {len(df_activities)} model-activity mappings")

    return df_immediate, df_lineage, df_tasks, df_activities


def build_table(df_immediate, df_lineage, df_tasks, df_activities):
    """Merge all dataframes into a single flat table."""

    # Start with immediate ancestors
    df = df_immediate.copy()

    # Merge lineage info
    df = df.merge(df_lineage, on="model_id", how="left")

    # Merge tasks
    df = df.merge(df_tasks, on="model_id", how="left")

    # Merge activities
    df = df.merge(df_activities, on="model_id", how="left")

    # ── Flatten list columns to semicolon-separated strings ──
    def flatten(val):
        if isinstance(val, list):
            # Filter out None values
            cleaned = [str(v) for v in val if v is not None]
            return "; ".join(cleaned) if cleaned else None
        return val

    list_cols = [
        "immediate_ancestor_ids", "ancestor_rel_types",
        "base_model_ids", "task_ids", "task_names",
        "activity_ids", "activity_names",
    ]
    for col in list_cols:
        if col in df.columns:
            df[col] = df[col].apply(flatten)

    # ── Clean up relationship type names ──
    rel_map = {
        "IS_FINETUNED_FROM": "Fine-tuned",
        "IS_QUANTIZED_FROM": "Quantized",
        "IS_ADAPTER_OF": "Adapter",
        "IS_MERGE_OF": "Merge",
    }

    def clean_rel_types(val):
        if not val or pd.isna(val):
            return None
        parts = [v.strip() for v in str(val).split(";")]
        return "; ".join([rel_map.get(p, p) for p in parts])

    df["adaptation_type"] = df["ancestor_rel_types"].apply(clean_rel_types)

    # ── Fill NAs for models with no lineage ──
    df["max_lineage_length"] = df["max_lineage_length"].fillna(0).astype(int)
    df.loc[df["immediate_ancestor_ids"].isna(), "adaptation_type"] = "Original"

    # ── Reorder and rename columns ──
    df = df[[
        "model_id",
        "model_name",
        "adaptation_type",
        "immediate_ancestor_ids",
        "ancestor_rel_types",
        "max_lineage_length",
        "base_model_ids",
        "task_ids",
        "task_names",
        "activity_ids",
        "activity_names",
    ]]

    df = df.rename(columns={
        "model_id": "se_model_id",
        "model_name": "se_model_name",
        "immediate_ancestor_ids": "immediate_ancestor",
        "ancestor_rel_types": "ancestor_rel_type_raw",
        "base_model_ids": "base_model",
        "task_ids": "se_task_id",
        "task_names": "se_task",
        "activity_ids": "se_activity_id",
        "activity_names": "se_activity",
    })

    df = df.sort_values(["max_lineage_length", "se_model_id"], ascending=[False, True])

    return df


def generate_lineage_table(uri, username, password, database):
    """Build the lineage table, save it to disk, and return the dataframe."""
    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()
        df_immediate, df_lineage, df_tasks, df_activities = query_lineage_table(driver, database=database)
    finally:
        driver.close()

    df = build_table(df_immediate, df_lineage, df_tasks, df_activities)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False)

    try:
        df.to_excel(XLSX_PATH, index=False, sheet_name="Lineage")
        xlsx_path = XLSX_PATH
    except ImportError:
        xlsx_path = None

    return df, CSV_PATH, xlsx_path


def load_saved_lineage_table(csv_path=CSV_PATH):
    """Load a previously saved lineage table CSV."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Saved lineage table CSV not found: {csv_path}")
    return pd.read_csv(csv_path)


def print_summary(df):
    """Print summary statistics of the table."""
    print(f"\n  Total rows           : {len(df)}")
    print(f"  Unique SE models     : {df['se_model_id'].nunique()}")
    print(f"  With lineage (>0)    : {(df['max_lineage_length'] > 0).sum()}")
    print(f"  Original (length=0)  : {(df['max_lineage_length'] == 0).sum()}")
    print(f"  Max lineage length   : {df['max_lineage_length'].max()}")
    print(f"  Mean lineage length  : {df['max_lineage_length'].mean():.2f}")
    print(f"  Median lineage length: {df['max_lineage_length'].median():.0f}")

    print(f"\n  Adaptation type distribution:")
    for t, c in df["adaptation_type"].value_counts().items():
        print(f"    {t:20s} : {c}")

    if "se_activity" in df.columns:
        print(f"\n  SE Activity coverage:")
        activity_counts = df["se_activity"].dropna().str.split("; ").explode().value_counts()
        for a, c in activity_counts.items():
            print(f"    {a:30s} : {c}")


def main():
    print("=" * 60)
    print("SEModel Lineage Overview Table Builder")
    print("=" * 60)

    print("\n[1/4] Connecting to Neo4j and building table...")
    try:
        df, csv_path, xlsx_path = generate_lineage_table(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return

    print("  ✓ Connected")
    print_summary(df)

    print("\n[2/4] Saving outputs...")
    print(f"  → CSV : {csv_path}")
    if xlsx_path is not None:
        print(f"  → XLSX: {xlsx_path}")
    else:
        print("  ⚠ openpyxl not installed — skipping Excel export")

    # ── Preview ──
    print(f"\n  Preview (first 10 rows):")
    preview_cols = [
        "se_model_id", "adaptation_type", "immediate_ancestor",
        "max_lineage_length", "base_model", "se_task", "se_activity",
    ]
    print(df[preview_cols].head(10).to_string(index=False))

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
