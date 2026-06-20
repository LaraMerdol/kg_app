"""
RQ: Model Adaptation Strategy Distribution (Task Level)
========================================================
How do different model adaptation strategies (fine-tuning, quantization,
adapters, merges) vary across SE tasks?

Experiment pipeline:
  1. Extract adaptation strategy per SEModel from Neo4j
  2. Filter to tasks with > 20 models
  3. Descriptive statistics & proportions per task
  4. Chi-square test of independence (strategy × task)
  5. Cramér's V effect size
  6. Standardized residuals (which cells drive significance)
  7. Post-hoc pairwise chi-square (Bonferroni corrected)
  8. Correspondence analysis (2D biplot)
  9. Visualizations (stacked bars, heatmaps, mosaic)

Requirements:
  pip install neo4j pandas scipy matplotlib seaborn prince
"""

import argparse
import os
import warnings
import itertools
import numpy as np
import pandas as pd
from neo4j import GraphDatabase
from scipy import stats
from scipy.stats import chi2_contingency
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "01234567")
MIN_MODELS_PER_TASK = 20
DEFAULT_MAX_LINEAGE_DEPTH = 20
DEFAULT_TOP_GROUPS = 25
ALPHA = 0.05
OUTPUT_DIR = "rq_adaptation_task_results"

os.makedirs(OUTPUT_DIR, exist_ok=True)

STRATEGY_ORDER = ["Original", "Fine-tuned", "Quantized", "Adapter", "Merge", "Mixed"]
STRATEGY_COLORS = {
    "Original": "#4C72B0",
    "Fine-tuned": "#55A868",
    "Quantized": "#C44E52",
    "Adapter": "#8172B3",
    "Merge": "#CCB974",
    "Mixed": "#64B5CD",
}


# ═════════════════════════════════════════════
# STEP 0: Neo4j data extraction
# ═════════════════════════════════════════════

def get_adaptation_data(driver, min_models_per_task, max_lineage_depth):
    """
    For each SEModel, determine its adaptation strategy based on
    incoming lineage edges, filtered to tasks with a minimum model count.
    """
    query = f"""
    // Get tasks with enough models
    MATCH (m:SEModel)-[:SUITABLE_FOR]->(t:SETask)
    WITH t, count(m) AS model_count
    WHERE model_count > {int(min_models_per_task)}
    WITH collect(t) AS qualifying_tasks

    // For each qualifying task, get models and their lineage types
    UNWIND qualifying_tasks AS t
    MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)

    CALL {{
        WITH m
        OPTIONAL MATCH p = (m)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM*0..{int(max_lineage_depth)}]->(root:SEModel)
        WHERE NOT (root)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM]->()
        RETURN coalesce(max(length(p)), 0) AS lineage_length
    }}

    // Check each lineage type
    OPTIONAL MATCH (m)-[ft:IS_FINETUNED_FROM]->()
    OPTIONAL MATCH (m)-[qt:IS_QUANTIZED_FROM]->()
    OPTIONAL MATCH (m)-[ad:IS_ADAPTER_OF]->()
    OPTIONAL MATCH (m)-[mg:IS_MERGE_OF]->()

    WITH m, t, lineage_length,
         count(DISTINCT ft) > 0 AS is_finetuned,
         count(DISTINCT qt) > 0 AS is_quantized,
         count(DISTINCT ad) > 0 AS is_adapter,
         count(DISTINCT mg) > 0 AS is_merge

    RETURN
        m.id            AS model_id,
        t.id            AS task_id,
        t.id          AS task_name,
        lineage_length,
        is_finetuned,
        is_quantized,
        is_adapter,
        is_merge
    """
    records = []
    with driver.session() as session:
        result = session.run(query)
        for record in result:
            records.append({
                "model_id": record["model_id"],
                "task_id": record["task_id"],
                "task_name": record["task_name"],
                "lineage_length": record["lineage_length"],
                "is_finetuned": record["is_finetuned"],
                "is_quantized": record["is_quantized"],
                "is_adapter": record["is_adapter"],
                "is_merge": record["is_merge"],
            })
    return pd.DataFrame(records)


def classify_strategy(row):
    """Classify a model's adaptation strategy from boolean flags."""
    flags = []
    if row["is_finetuned"]:
        flags.append("Fine-tuned")
    if row["is_quantized"]:
        flags.append("Quantized")
    if row["is_adapter"]:
        flags.append("Adapter")
    if row["is_merge"]:
        flags.append("Merge")

    if len(flags) == 0:
        return "Original"
    elif len(flags) == 1:
        return flags[0]
    else:
        return "Mixed"


def build_lineage_length_stats(df, group_col, group_name_col, min_models):
    """Aggregate lineage-length counts and summary statistics per group."""
    if df.empty:
        return pd.DataFrame()

    rows = []
    for group_value, group_df in df.groupby(group_col):
        lengths = pd.to_numeric(group_df["lineage_length"], errors="coerce").fillna(0).astype(int)
        group_name = (
            str(group_df[group_name_col].dropna().astype(str).iloc[0])
            if group_name_col in group_df.columns and not group_df[group_name_col].dropna().empty
            else str(group_value)
        )
        rows.append({
            group_col: group_value,
            group_name_col: group_name,
            "totalModels": int(len(group_df)),
            "avgLineageLength": float(lengths.mean()) if len(lengths) else 0.0,
            "medianLineageLength": float(lengths.median()) if len(lengths) else 0.0,
            "maxLineageLength": int(lengths.max()) if len(lengths) else 0,
            "len0": int((lengths == 0).sum()),
            "len1": int((lengths == 1).sum()),
            "len2": int((lengths == 2).sum()),
            "len3": int((lengths == 3).sum()),
            "len4": int((lengths == 4).sum()),
            "len5plus": int((lengths >= 5).sum()),
        })

    stats_df = pd.DataFrame(rows)
    stats_df = stats_df[stats_df["totalModels"] >= int(min_models)].sort_values(
        ["totalModels", "avgLineageLength", group_name_col],
        ascending=[False, False, True],
    )
    return stats_df


def plot_lineage_length_distribution(stats_df, group_name_col, output_path, title, y_label):
    """Stacked distribution plot for lineage-length bins."""
    if stats_df.empty:
        return

    plot_cols = ["len0", "len1", "len2", "len3", "len4", "len5plus"]
    plot_data = stats_df.set_index(group_name_col)[plot_cols]
    plot_data = plot_data.sort_values("len0", ascending=True)

    fig, ax = plt.subplots(figsize=(14, max(6, len(plot_data) * 0.45)))
    plot_data.plot(
        kind="barh",
        stacked=True,
        color=["#4C72B0", "#55A868", "#C44E52", "#8172B3", "#CCB974", "#64B5CD"],
        ax=ax,
        edgecolor="white",
        linewidth=0.5,
    )
    ax.set_xlabel("Number of Models", fontsize=12)
    ax.set_ylabel(y_label, fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend(title="Lineage length", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


def plot_average_lineage_length(stats_df, group_name_col, output_path, title, y_label):
    """Bar chart for average lineage length per group."""
    if stats_df.empty:
        return

    plot_data = stats_df.sort_values("avgLineageLength", ascending=True)
    fig, ax = plt.subplots(figsize=(14, max(6, len(plot_data) * 0.45)))
    bars = ax.barh(plot_data[group_name_col], plot_data["avgLineageLength"], color="#4C72B0", edgecolor="white")
    for bar, total in zip(bars, plot_data["totalModels"]):
        ax.text(bar.get_width() + 0.03, bar.get_y() + bar.get_height() / 2, f"n={int(total)}", va="center", fontsize=8)
    ax.set_xlabel("Average lineage length", fontsize=12)
    ax.set_ylabel(y_label, fontsize=12)
    ax.set_title(title, fontsize=14)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


# ═════════════════════════════════════════════
# STEP 1: Statistical helpers
# ═════════════════════════════════════════════

def cramers_v(contingency_table):
    """Compute Cramér's V effect size for a contingency table."""
    chi2, _, _, _ = chi2_contingency(contingency_table)
    n = contingency_table.values.sum()
    k = min(contingency_table.shape) - 1
    if k == 0 or n == 0:
        return 0.0, "negligible"
    v = np.sqrt(chi2 / (n * k))
    # Interpret (Cohen's benchmarks for df*)
    # df* = min(rows-1, cols-1)
    if v < 0.1:
        magnitude = "negligible"
    elif v < 0.3:
        magnitude = "small"
    elif v < 0.5:
        magnitude = "medium"
    else:
        magnitude = "large"
    return v, magnitude


def standardized_residuals(contingency_table):
    """
    Compute adjusted standardized residuals for each cell.
    Values > |2| indicate significant over/under-representation.
    """
    chi2, _, _, expected = chi2_contingency(contingency_table)
    observed = contingency_table.values
    row_totals = observed.sum(axis=1, keepdims=True)
    col_totals = observed.sum(axis=0, keepdims=True)
    n = observed.sum()

    # Adjusted standardized residuals
    with np.errstate(divide="ignore", invalid="ignore"):
        residuals = (observed - expected) / np.sqrt(
            expected * (1 - row_totals / n) * (1 - col_totals / n)
        )
    residuals = np.nan_to_num(residuals, nan=0.0, posinf=0.0, neginf=0.0)

    return pd.DataFrame(
        residuals,
        index=contingency_table.index,
        columns=contingency_table.columns,
    )


# ═════════════════════════════════════════════
# STEP 2: Descriptive statistics
# ═════════════════════════════════════════════

def compute_descriptive_stats(df):
    """Compute strategy proportions per task."""
    # Counts
    counts = df.groupby(["task_id", "strategy"]).size().unstack(fill_value=0)
    # Ensure all strategies present
    for s in STRATEGY_ORDER:
        if s not in counts.columns:
            counts[s] = 0
    counts = counts[STRATEGY_ORDER]

    # Proportions
    proportions = counts.div(counts.sum(axis=1), axis=0)

    # Add task names and totals
    task_names = df[["task_id", "task_name"]].drop_duplicates().set_index("task_id")
    counts["total"] = counts.sum(axis=1)
    counts = counts.join(task_names)

    return counts, proportions


# ═════════════════════════════════════════════
# STEP 3: Chi-square test of independence
# ═════════════════════════════════════════════

def run_chi_square(df):
    """Run chi-square test: is strategy distribution independent of task?"""
    contingency = pd.crosstab(df["task_id"], df["strategy"])

    # Remove columns with all zeros
    contingency = contingency.loc[:, contingency.sum() > 0]

    chi2, p_value, dof, expected = chi2_contingency(contingency)
    v, v_magnitude = cramers_v(contingency)
    resid = standardized_residuals(contingency)

    return {
        "chi2": chi2,
        "p_value": p_value,
        "dof": dof,
        "cramers_v": v,
        "v_magnitude": v_magnitude,
        "significant": p_value < ALPHA,
        "contingency": contingency,
        "expected": pd.DataFrame(expected, index=contingency.index, columns=contingency.columns),
        "residuals": resid,
    }


# ═════════════════════════════════════════════
# STEP 4: Post-hoc pairwise chi-square
# ═════════════════════════════════════════════

def run_pairwise_chi_square(df, max_pairs=None):
    """Pairwise chi-square tests between tasks with Bonferroni correction."""
    tasks = sorted(df["task_id"].unique())
    all_pairs = list(itertools.combinations(tasks, 2))
    n_comparisons = len(all_pairs)

    if max_pairs and n_comparisons > max_pairs:
        # If too many pairs, only compare tasks with most distinct profiles
        all_pairs = all_pairs[:max_pairs]
        n_comparisons = max_pairs

    rows = []
    for t1, t2 in all_pairs:
        subset = df[df["task_id"].isin([t1, t2])]
        contingency = pd.crosstab(subset["task_id"], subset["strategy"])
        contingency = contingency.loc[:, contingency.sum() > 0]

        # Skip if contingency table is degenerate
        if contingency.shape[0] < 2 or contingency.shape[1] < 2:
            continue

        chi2, p_value, dof, _ = chi2_contingency(contingency)
        v, v_mag = cramers_v(contingency)

        # Bonferroni correction
        p_corrected = min(p_value * n_comparisons, 1.0)

        rows.append({
            "task_1": t1,
            "task_2": t2,
            "chi2": chi2,
            "dof": dof,
            "p_value": p_value,
            "p_bonferroni": p_corrected,
            "significant": p_corrected < ALPHA,
            "cramers_v": v,
            "effect_magnitude": v_mag,
        })

    return pd.DataFrame(rows).sort_values("p_bonferroni")


# ═════════════════════════════════════════════
# STEP 5: Correspondence analysis
# ═════════════════════════════════════════════

def run_correspondence_analysis(contingency):
    """Run correspondence analysis and return coordinates for biplot."""
    try:
        import prince
        ca = prince.CA(n_components=2, random_state=42)
        ca = ca.fit(contingency)
        row_coords = ca.row_coordinates(contingency)
        col_coords = ca.column_coordinates(contingency)
        # Explained inertia
        inertia = ca.percentage_of_variance_
        return row_coords, col_coords, inertia
    except ImportError:
        print("  ⚠ 'prince' not installed — skipping correspondence analysis")
        print("    Install with: pip install prince")
        return None, None, None
    except Exception as e:
        print(f"  ⚠ Correspondence analysis failed: {e}")
        return None, None, None


# ═════════════════════════════════════════════
# STEP 6: Visualizations
# ═════════════════════════════════════════════

def plot_stacked_bar(proportions, task_names_map, output_path):
    """Stacked bar chart of strategy proportions per task."""
    # Sort by proportion of Original (or Fine-tuned) for visual clarity
    sort_col = "Original" if "Original" in proportions.columns else proportions.columns[0]
    plot_data = proportions.sort_values(sort_col, ascending=True)

    # Map task IDs to names
    plot_data.index = [task_names_map.get(t, t) for t in plot_data.index]

    fig, ax = plt.subplots(figsize=(14, max(6, len(plot_data) * 0.4)))
    plot_data.plot(
        kind="barh",
        stacked=True,
        color=[STRATEGY_COLORS.get(s, "#999999") for s in plot_data.columns],
        ax=ax,
        edgecolor="white",
        linewidth=0.5,
    )
    ax.set_xlabel("Proportion", fontsize=12)
    ax.set_ylabel("SE Task", fontsize=12)
    ax.set_title("Adaptation Strategy Distribution by SE Task", fontsize=14)
    ax.legend(title="Strategy", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
    ax.set_xlim(0, 1)
    ax.tick_params(axis="y", labelsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


def plot_residuals_heatmap(residuals, task_names_map, output_path):
    """Heatmap of adjusted standardized residuals."""
    plot_data = residuals.copy()
    plot_data.index = [task_names_map.get(t, t) for t in plot_data.index]

    fig, ax = plt.subplots(figsize=(10, max(6, len(plot_data) * 0.4)))
    sns.heatmap(
        plot_data,
        cmap="RdBu_r",
        center=0,
        annot=True,
        fmt=".1f",
        linewidths=0.5,
        cbar_kws={"label": "Adjusted Std. Residual"},
        ax=ax,
    )
    ax.set_title(
        "Adjusted Standardized Residuals (|value| > 2 = significant)",
        fontsize=13,
    )
    ax.set_ylabel("SE Task", fontsize=11)
    ax.set_xlabel("Adaptation Strategy", fontsize=11)
    ax.tick_params(axis="y", labelsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


def plot_correspondence_biplot(row_coords, col_coords, inertia,
                                task_names_map, output_path):
    """2D biplot from correspondence analysis."""
    fig, ax = plt.subplots(figsize=(12, 9))

    # Plot tasks (row points)
    for idx in row_coords.index:
        label = task_names_map.get(idx, idx)
        ax.scatter(row_coords.loc[idx, 0], row_coords.loc[idx, 1],
                   c="#4C72B0", s=40, zorder=3)
        ax.annotate(label, (row_coords.loc[idx, 0], row_coords.loc[idx, 1]),
                    fontsize=7, ha="left", va="bottom", color="#4C72B0")

    # Plot strategies (column points)
    for idx in col_coords.index:
        ax.scatter(col_coords.loc[idx, 0], col_coords.loc[idx, 1],
                   c=STRATEGY_COLORS.get(idx, "#C44E52"), s=120,
                   marker="D", zorder=4, edgecolors="black", linewidth=0.8)
        ax.annotate(idx, (col_coords.loc[idx, 0], col_coords.loc[idx, 1]),
                    fontsize=10, fontweight="bold", ha="center", va="bottom",
                    color=STRATEGY_COLORS.get(idx, "#C44E52"))

    ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax.axvline(0, color="gray", linewidth=0.5, linestyle="--")
    ax.set_xlabel(f"Dimension 1 ({inertia[0]:.1f}% inertia)", fontsize=12)
    ax.set_ylabel(f"Dimension 2 ({inertia[1]:.1f}% inertia)", fontsize=12)
    ax.set_title("Correspondence Analysis: SE Tasks × Adaptation Strategies", fontsize=14)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


def plot_strategy_counts(df, output_path):
    """Overall strategy counts (global distribution)."""
    counts = df["strategy"].value_counts().reindex(STRATEGY_ORDER).dropna()

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        counts.index, counts.values,
        color=[STRATEGY_COLORS.get(s, "#999") for s in counts.index],
        edgecolor="white",
    )
    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                f"{int(val)}", ha="center", va="bottom", fontsize=10)
    ax.set_xlabel("Adaptation Strategy", fontsize=12)
    ax.set_ylabel("Number of Models", fontsize=12)
    ax.set_title("Overall Distribution of Adaptation Strategies", fontsize=14)
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


def plot_dominant_strategy_per_task(proportions, task_names_map, output_path):
    """Bar chart showing the dominant strategy per task."""
    dominant = proportions.idxmax(axis=1).to_frame("dominant_strategy")
    dominant["proportion"] = proportions.max(axis=1)
    dominant["task_name"] = [task_names_map.get(t, t) for t in dominant.index]
    dominant = dominant.sort_values("proportion", ascending=True)

    fig, ax = plt.subplots(figsize=(12, max(6, len(dominant) * 0.4)))
    colors = [STRATEGY_COLORS.get(s, "#999") for s in dominant["dominant_strategy"]]
    ax.barh(dominant["task_name"], dominant["proportion"], color=colors, edgecolor="white")
    ax.set_xlabel("Proportion of Dominant Strategy", fontsize=12)
    ax.set_ylabel("SE Task", fontsize=12)
    ax.set_title("Dominant Adaptation Strategy per SE Task", fontsize=14)
    ax.set_xlim(0, 1)
    ax.tick_params(axis="y", labelsize=8)

    # Legend
    handles = [plt.Rectangle((0, 0), 1, 1, color=STRATEGY_COLORS[s])
               for s in STRATEGY_ORDER if s in dominant["dominant_strategy"].values]
    labels = [s for s in STRATEGY_ORDER if s in dominant["dominant_strategy"].values]
    ax.legend(handles, labels, title="Strategy", loc="lower right", fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


# ═════════════════════════════════════════════
# STEP 7: LaTeX table
# ═════════════════════════════════════════════

def generate_latex_table(counts, chi_result):
    """LaTeX table of strategy counts per task."""
    strategies = [s for s in STRATEGY_ORDER if s in counts.columns and s != "total"]
    short = {"Original": "Orig", "Fine-tuned": "FT", "Quantized": "Quant",
             "Adapter": "Adpt", "Merge": "Mrg", "Mixed": "Mix"}

    header_cols = " & ".join([short.get(s, s) for s in strategies])
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Adaptation strategy distribution by SE task.}",
        r"\label{tab:adaptation_task}",
        r"\footnotesize",
        r"\begin{tabular}{l" + "r" * (len(strategies) + 1) + "}",
        r"\toprule",
        f"Task & {header_cols} & Total \\\\",
        r"\midrule",
    ]
    for task_id, row in counts.iterrows():
        name = row.get("task_name", task_id)
        if isinstance(name, str) and len(name) > 25:
            name = name[:22] + "..."
        vals = " & ".join([str(int(row.get(s, 0))) for s in strategies])
        total = int(row.get("total", sum(row.get(s, 0) for s in strategies)))
        lines.append(f"  {name} & {vals} & {total} \\\\")

    lines.append(r"\midrule")
    lines.append(
        f"  \\multicolumn{{{len(strategies) + 2}}}{{l}}"
        f"{{$\\chi^2={chi_result['chi2']:.2f}$, $p={chi_result['p_value']:.2e}$, "
        f"Cram\\'er's $V={chi_result['cramers_v']:.3f}$ ({chi_result['v_magnitude']})}} \\\\"
    )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def build_arg_parser():
    parser = argparse.ArgumentParser(description="RQ adaptation strategy analysis by task")
    parser.add_argument("--min-models-per-task", type=int, default=MIN_MODELS_PER_TASK)
    parser.add_argument("--max-lineage-depth", type=int, default=DEFAULT_MAX_LINEAGE_DEPTH)
    parser.add_argument("--top-groups", type=int, default=DEFAULT_TOP_GROUPS)
    return parser


# ═════════════════════════════════════════════
# MAIN PIPELINE
# ═════════════════════════════════════════════

def main():
    args = build_arg_parser().parse_args()

    print("=" * 60)
    print("RQ: Adaptation Strategy Distribution (Task Level)")
    print("=" * 60)

    # ── Connect & extract ──
    print("\n[1/8] Connecting to Neo4j and extracting data...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        print("  ✓ Connected")
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        return

    df = get_adaptation_data(driver, args.min_models_per_task, args.max_lineage_depth)
    driver.close()

    # Classify strategies
    df["strategy"] = df.apply(classify_strategy, axis=1)
    print(f"  ✓ {len(df)} model-task records")
    print(f"  ✓ {df['model_id'].nunique()} unique models")
    print(f"  ✓ {df['task_id'].nunique()} tasks (with > {args.min_models_per_task} models)")
    print(f"\n  Global strategy distribution:")
    print(f"  {df['strategy'].value_counts().to_dict()}")

    # Build name map
    task_names_map = df.set_index("task_id")["task_name"].to_dict()

    print("\n[2b/8] Lineage length statistics by SE task...")
    lineage_stats = build_lineage_length_stats(df, "task_id", "task_name", args.min_models_per_task)
    lineage_stats.to_csv(os.path.join(OUTPUT_DIR, "lineage_length_stats_task.csv"), index=False)
    if lineage_stats.empty:
        print("  No tasks met the lineage-length minimum model threshold.")
    else:
        print(f"  ✓ {len(lineage_stats)} tasks with >= {args.min_models_per_task} models")
        print(
            lineage_stats[["task_name", "totalModels", "avgLineageLength", "medianLineageLength", "maxLineageLength"]]
            .head(min(args.top_groups, len(lineage_stats)))
            .to_string(index=False)
        )

    # ── Descriptive stats ──
    print("\n[2/8] Computing descriptive statistics...")
    counts, proportions = compute_descriptive_stats(df)
    counts.to_csv(os.path.join(OUTPUT_DIR, "strategy_counts_per_task.csv"), float_format="%.0f")
    proportions.to_csv(os.path.join(OUTPUT_DIR, "strategy_proportions_per_task.csv"), float_format="%.4f")
    print(f"  → Saved counts and proportions CSVs")
    print(f"\n  Proportions (top 5 tasks by model count):")
    print(proportions.head().to_string())

    # ── Chi-square test ──
    print("\n[3/8] Running chi-square test of independence...")
    chi_result = run_chi_square(df)
    print(f"  χ²          : {chi_result['chi2']:.4f}")
    print(f"  p-value     : {chi_result['p_value']:.2e}")
    print(f"  dof         : {chi_result['dof']}")
    print(f"  Cramér's V  : {chi_result['cramers_v']:.4f} ({chi_result['v_magnitude']})")
    print(f"  Significant : {'YES' if chi_result['significant'] else 'NO'} (α={ALPHA})")

    chi_summary = {k: v for k, v in chi_result.items()
                   if k not in ("contingency", "expected", "residuals")}
    pd.DataFrame([chi_summary]).to_csv(
        os.path.join(OUTPUT_DIR, "chi_square_result.csv"), index=False
    )

    # ── Standardized residuals ──
    print("\n[4/8] Computing standardized residuals...")
    resid = chi_result["residuals"]
    resid.to_csv(os.path.join(OUTPUT_DIR, "standardized_residuals.csv"), float_format="%.3f")

    # Find noteworthy cells (|residual| > 2)
    noteworthy = []
    for task in resid.index:
        for strategy in resid.columns:
            val = resid.loc[task, strategy]
            if abs(val) > 2:
                direction = "over-represented" if val > 0 else "under-represented"
                noteworthy.append({
                    "task": task,
                    "task_name": task_names_map.get(task, task),
                    "strategy": strategy,
                    "residual": val,
                    "direction": direction,
                })
    noteworthy_df = pd.DataFrame(noteworthy).sort_values("residual", key=abs, ascending=False)
    noteworthy_df.to_csv(os.path.join(OUTPUT_DIR, "noteworthy_residuals.csv"), index=False)
    print(f"  ✓ {len(noteworthy_df)} noteworthy cells (|residual| > 2)")
    if len(noteworthy_df) > 0:
        print(f"\n{noteworthy_df.head(15).to_string(index=False)}")

    # ── Post-hoc pairwise chi-square ──
    if chi_result["significant"]:
        print("\n[5/8] Running post-hoc pairwise chi-square (Bonferroni)...")
        pairwise_df = run_pairwise_chi_square(df)
        pairwise_path = os.path.join(OUTPUT_DIR, "pairwise_chi_square.csv")
        pairwise_df.to_csv(pairwise_path, index=False, float_format="%.4f")
        sig_pairs = pairwise_df["significant"].sum()
        total_pairs = len(pairwise_df)
        print(f"  ✓ {sig_pairs}/{total_pairs} pairs significant after Bonferroni")
        print(f"  → Saved: {pairwise_path}")

        if sig_pairs > 0:
            print(f"\n  Top significant pairs:")
            print(pairwise_df[pairwise_df["significant"]]
                  [["task_1", "task_2", "chi2", "p_bonferroni", "cramers_v", "effect_magnitude"]]
                  .head(10).to_string(index=False))
    else:
        print("\n[5/8] Skipping post-hoc (omnibus not significant)")

    # ── Correspondence analysis ──
    print("\n[6/8] Running correspondence analysis...")
    row_coords, col_coords, inertia = run_correspondence_analysis(chi_result["contingency"])

    if row_coords is not None:
        row_coords.to_csv(os.path.join(OUTPUT_DIR, "ca_task_coordinates.csv"), float_format="%.4f")
        col_coords.to_csv(os.path.join(OUTPUT_DIR, "ca_strategy_coordinates.csv"), float_format="%.4f")

    # ── Visualizations ──
    print("\n[7/8] Generating visualizations...")
    plot_strategy_counts(df, os.path.join(OUTPUT_DIR, "global_strategy_counts.png"))
    plot_stacked_bar(proportions, task_names_map, os.path.join(OUTPUT_DIR, "stacked_bar_task.png"))
    plot_residuals_heatmap(resid, task_names_map, os.path.join(OUTPUT_DIR, "residuals_heatmap.png"))
    plot_dominant_strategy_per_task(proportions, task_names_map,
                                    os.path.join(OUTPUT_DIR, "dominant_strategy_task.png"))

    if not lineage_stats.empty:
        plot_lineage_length_distribution(
            lineage_stats.head(args.top_groups),
            "task_name",
            os.path.join(OUTPUT_DIR, "lineage_length_distribution_task.png"),
            "Lineage Length Distribution by SE Task",
            "SE Task",
        )
        plot_average_lineage_length(
            lineage_stats.head(args.top_groups),
            "task_name",
            os.path.join(OUTPUT_DIR, "average_lineage_length_task.png"),
            "Average Lineage Length by SE Task",
            "SE Task",
        )

    if row_coords is not None:
        plot_correspondence_biplot(row_coords, col_coords, inertia,
                                   task_names_map,
                                   os.path.join(OUTPUT_DIR, "correspondence_biplot.png"))

    # ── LaTeX table ──
    print("\n[8/8] Generating LaTeX table...")
    latex = generate_latex_table(counts, chi_result)
    latex_path = os.path.join(OUTPUT_DIR, "table_adaptation_task.tex")
    with open(latex_path, "w") as f:
        f.write(latex)
    print(f"  → Saved: {latex_path}")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("EXPERIMENT COMPLETE")
    print("=" * 60)
    print(f"All outputs in: {OUTPUT_DIR}/")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        print(f"  - {f}")


if __name__ == "__main__":
    main()
