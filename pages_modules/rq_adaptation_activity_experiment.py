"""
RQ: Model Adaptation Strategy Distribution (Activity Level)
=============================================================
How do different model adaptation strategies (fine-tuning, quantization,
adapters, merges) vary across SE activities?

Aggregated to the 5 SEActivity categories.

Experiment pipeline:
  1. Extract adaptation strategy per SEModel, mapped to SEActivity
  2. Descriptive statistics & proportions per activity
  3. Chi-square test of independence (strategy × activity)
  4. Cramér's V effect size
  5. Standardized residuals
  6. Post-hoc pairwise chi-square (all 10 pairs, Bonferroni)
  7. Correspondence analysis (biplot)
  8. Visualizations

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
MIN_MODELS_PER_ACTIVITY = 20
DEFAULT_MAX_LINEAGE_DEPTH = 20
DEFAULT_TOP_GROUPS = 10
ALPHA = 0.05
OUTPUT_DIR = "rq_adaptation_activity_results"

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

def get_adaptation_data_by_activity(driver, max_lineage_depth):
    """
    For each SEModel, determine adaptation strategy and map to SEActivity
    via SEModel -> SUITABLE_FOR -> SETask -> USED_FOR -> SEActivity.
    """
    query = f"""
    MATCH (m:SEModel)-[:SUITABLE_FOR]->(t:SETask)-[:USED_FOR]->(a:SEActivity)

    CALL {{
        WITH m
        OPTIONAL MATCH p = (m)-[:IS_FINETUNED_FROM|IS_QUANTIZED_FROM|IS_ADAPTER_OF|IS_MERGE_OF*0..{int(max_lineage_depth)}]->(root:SEModel)
        WHERE NOT (root)-[:IS_FINETUNED_FROM|IS_QUANTIZED_FROM|IS_ADAPTER_OF|IS_MERGE_OF]->()
        RETURN coalesce(max(length(p)), 0) AS lineage_length
    }}

    OPTIONAL MATCH (m)-[ft:IS_FINETUNED_FROM]->()
    OPTIONAL MATCH (m)-[qt:IS_QUANTIZED_FROM]->()
    OPTIONAL MATCH (m)-[ad:IS_ADAPTER_OF]->()
    OPTIONAL MATCH (m)-[mg:IS_MERGE_OF]->()

    WITH m, t, a, lineage_length,
         count(DISTINCT ft) > 0 AS is_finetuned,
         count(DISTINCT qt) > 0 AS is_quantized,
         count(DISTINCT ad) > 0 AS is_adapter,
         count(DISTINCT mg) > 0 AS is_merge

    RETURN
        m.id            AS model_id,
        t.id            AS task_id,
        t.id          AS task_name,
        a.id            AS activity_id,
        a.id          AS activity_name,
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
                "activity_id": record["activity_id"],
                "activity_name": record["activity_name"],
                "lineage_length": record["lineage_length"],
                "is_finetuned": record["is_finetuned"],
                "is_quantized": record["is_quantized"],
                "is_adapter": record["is_adapter"],
                "is_merge": record["is_merge"],
            })
    return pd.DataFrame(records)


def build_lineage_length_stats(df, group_col, group_name_col, min_models):
    """Aggregate lineage-length counts and summary statistics per group."""
    if df.empty:
        return pd.DataFrame()

    rows = []
    grouped = df.groupby(group_col)
    for group_value, group_df in grouped:
        lengths = pd.to_numeric(group_df["lineage_length"], errors="coerce").fillna(0).astype(int)
        group_name = str(group_df[group_name_col].dropna().astype(str).iloc[0]) if group_name_col in group_df.columns and not group_df[group_name_col].dropna().empty else str(group_value)
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

    fig, ax = plt.subplots(figsize=(12, max(5, len(plot_data) * 0.45)))
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
    fig, ax = plt.subplots(figsize=(12, max(5, len(plot_data) * 0.45)))
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


# ═════════════════════════════════════════════
# STEP 1: Statistical helpers
# ═════════════════════════════════════════════

def cramers_v(contingency_table):
    """Compute Cramér's V effect size."""
    chi2, _, _, _ = chi2_contingency(contingency_table)
    n = contingency_table.values.sum()
    k = min(contingency_table.shape) - 1
    if k == 0 or n == 0:
        return 0.0, "negligible"
    v = np.sqrt(chi2 / (n * k))
    if v < 0.1:
        mag = "negligible"
    elif v < 0.3:
        mag = "small"
    elif v < 0.5:
        mag = "medium"
    else:
        mag = "large"
    return v, mag


def standardized_residuals(contingency_table):
    """Adjusted standardized residuals. |value| > 2 = significant."""
    _, _, _, expected = chi2_contingency(contingency_table)
    observed = contingency_table.values
    row_totals = observed.sum(axis=1, keepdims=True)
    col_totals = observed.sum(axis=0, keepdims=True)
    n = observed.sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        residuals = (observed - expected) / np.sqrt(
            expected * (1 - row_totals / n) * (1 - col_totals / n)
        )
    residuals = np.nan_to_num(residuals, nan=0.0, posinf=0.0, neginf=0.0)
    return pd.DataFrame(residuals, index=contingency_table.index,
                        columns=contingency_table.columns)


# ═════════════════════════════════════════════
# STEP 2: Descriptive statistics
# ═════════════════════════════════════════════

def compute_descriptive_stats(df):
    """Strategy counts and proportions per activity."""
    counts = df.groupby(["activity_name", "strategy"]).size().unstack(fill_value=0)
    for s in STRATEGY_ORDER:
        if s not in counts.columns:
            counts[s] = 0
    counts = counts[STRATEGY_ORDER]
    counts["total"] = counts.sum(axis=1)
    proportions = counts[STRATEGY_ORDER].div(counts["total"], axis=0)
    return counts, proportions


def compute_task_breakdown(df):
    """Which tasks contribute to each activity, and their strategy mix."""
    breakdown = (
        df.groupby(["activity_name", "task_name", "strategy"])
        .size()
        .reset_index(name="count")
    )
    return breakdown


# ═════════════════════════════════════════════
# STEP 3: Chi-square test
# ═════════════════════════════════════════════

def run_chi_square(df):
    """Chi-square test of independence: strategy × activity."""
    contingency = pd.crosstab(df["activity_name"], df["strategy"])
    contingency = contingency.loc[:, contingency.sum() > 0]

    chi2, p_value, dof, expected = chi2_contingency(contingency)
    v, v_mag = cramers_v(contingency)
    resid = standardized_residuals(contingency)

    return {
        "chi2": chi2,
        "p_value": p_value,
        "dof": dof,
        "cramers_v": v,
        "v_magnitude": v_mag,
        "significant": p_value < ALPHA,
        "contingency": contingency,
        "expected": pd.DataFrame(expected, index=contingency.index,
                                 columns=contingency.columns),
        "residuals": resid,
    }


# ═════════════════════════════════════════════
# STEP 4: Post-hoc pairwise chi-square
# ═════════════════════════════════════════════

def run_all_pairwise_chi_square(df):
    """All pairwise chi-square between activities (only 10 pairs)."""
    activities = sorted(df["activity_name"].unique())
    all_pairs = list(itertools.combinations(activities, 2))
    n_comparisons = len(all_pairs)

    rows = []
    for a1, a2 in all_pairs:
        subset = df[df["activity_name"].isin([a1, a2])]
        contingency = pd.crosstab(subset["activity_name"], subset["strategy"])
        contingency = contingency.loc[:, contingency.sum() > 0]

        if contingency.shape[0] < 2 or contingency.shape[1] < 2:
            continue

        chi2, p_value, dof, _ = chi2_contingency(contingency)
        v, v_mag = cramers_v(contingency)
        p_corrected = min(p_value * n_comparisons, 1.0)

        rows.append({
            "activity_1": a1,
            "activity_2": a2,
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
    """Correspondence analysis for activity × strategy."""
    try:
        import prince
        ca = prince.CA(n_components=2, random_state=42)
        ca = ca.fit(contingency)
        row_coords = ca.row_coordinates(contingency)
        col_coords = ca.column_coordinates(contingency)
        inertia = ca.percentage_of_variance_
        return row_coords, col_coords, inertia
    except ImportError:
        print("  ⚠ 'prince' not installed — skipping CA")
        return None, None, None
    except Exception as e:
        print(f"  ⚠ CA failed: {e}")
        return None, None, None


# ═════════════════════════════════════════════
# STEP 6: Visualizations
# ═════════════════════════════════════════════

def plot_stacked_bar(proportions, output_path):
    """Stacked bar chart of strategy proportions per activity."""
    plot_data = proportions.sort_values("Original", ascending=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    plot_data.plot(
        kind="barh",
        stacked=True,
        color=[STRATEGY_COLORS.get(s, "#999") for s in plot_data.columns],
        ax=ax,
        edgecolor="white",
        linewidth=0.5,
    )
    ax.set_xlabel("Proportion", fontsize=12)
    ax.set_ylabel("SE Activity", fontsize=12)
    ax.set_title("Adaptation Strategy Distribution by SE Activity", fontsize=14)
    ax.legend(title="Strategy", bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_xlim(0, 1)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


def plot_grouped_bar(counts, output_path):
    """Grouped bar chart for absolute counts."""
    plot_cols = [s for s in STRATEGY_ORDER if s in counts.columns and s != "total"]
    plot_data = counts[plot_cols]

    fig, ax = plt.subplots(figsize=(14, 7))
    plot_data.plot(
        kind="bar",
        color=[STRATEGY_COLORS.get(s, "#999") for s in plot_cols],
        ax=ax,
        edgecolor="white",
        width=0.8,
    )
    ax.set_xlabel("SE Activity", fontsize=12)
    ax.set_ylabel("Number of Models", fontsize=12)
    ax.set_title("Adaptation Strategy Counts by SE Activity", fontsize=14)
    ax.legend(title="Strategy", fontsize=9)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


def plot_residuals_heatmap(residuals, output_path):
    """Heatmap of adjusted standardized residuals."""
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.heatmap(
        residuals,
        cmap="RdBu_r",
        center=0,
        annot=True,
        fmt=".2f",
        linewidths=1,
        cbar_kws={"label": "Adjusted Std. Residual"},
        square=True,
        ax=ax,
    )
    ax.set_title(
        "Standardized Residuals: Activity × Strategy\n(|value| > 2 = significant over/under-representation)",
        fontsize=13,
    )
    ax.set_ylabel("SE Activity", fontsize=11)
    ax.set_xlabel("Adaptation Strategy", fontsize=11)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


def plot_pairwise_heatmap(pairwise_df, output_path):
    """Heatmap of Cramér's V with significance for all activity pairs."""
    activities = sorted(set(pairwise_df["activity_1"]) | set(pairwise_df["activity_2"]))
    v_matrix = pd.DataFrame(0.0, index=activities, columns=activities)
    sig_matrix = pd.DataFrame("", index=activities, columns=activities)

    for _, row in pairwise_df.iterrows():
        a1, a2 = row["activity_1"], row["activity_2"]
        v_matrix.loc[a1, a2] = row["cramers_v"]
        v_matrix.loc[a2, a1] = row["cramers_v"]
        marker = "***" if row["p_bonferroni"] < 0.001 else \
                 "**" if row["p_bonferroni"] < 0.01 else \
                 "*" if row["p_bonferroni"] < 0.05 else "ns"
        sig_matrix.loc[a1, a2] = marker
        sig_matrix.loc[a2, a1] = marker

    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(
        v_matrix,
        annot=sig_matrix,
        fmt="s",
        cmap="YlOrRd",
        vmin=0, vmax=0.5,
        square=True,
        linewidths=1,
        cbar_kws={"label": "Cramér's V", "shrink": 0.8},
        ax=ax,
    )
    ax.set_title(
        "Pairwise Cramér's V with Significance\n(* p<.05, ** p<.01, *** p<.001)",
        fontsize=13,
    )
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


def plot_correspondence_biplot(row_coords, col_coords, inertia, output_path):
    """Biplot from correspondence analysis."""
    fig, ax = plt.subplots(figsize=(10, 8))

    for idx in row_coords.index:
        ax.scatter(row_coords.loc[idx, 0], row_coords.loc[idx, 1],
                   c="#4C72B0", s=80, zorder=3)
        ax.annotate(idx, (row_coords.loc[idx, 0], row_coords.loc[idx, 1]),
                    fontsize=10, fontweight="bold", ha="left", va="bottom",
                    color="#4C72B0")

    for idx in col_coords.index:
        ax.scatter(col_coords.loc[idx, 0], col_coords.loc[idx, 1],
                   c=STRATEGY_COLORS.get(idx, "#C44E52"), s=150,
                   marker="D", zorder=4, edgecolors="black", linewidth=0.8)
        ax.annotate(idx, (col_coords.loc[idx, 0], col_coords.loc[idx, 1]),
                    fontsize=11, fontweight="bold", ha="center", va="bottom",
                    color=STRATEGY_COLORS.get(idx, "#C44E52"))

    ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax.axvline(0, color="gray", linewidth=0.5, linestyle="--")
    ax.set_xlabel(f"Dimension 1 ({inertia[0]:.1f}% inertia)", fontsize=12)
    ax.set_ylabel(f"Dimension 2 ({inertia[1]:.1f}% inertia)", fontsize=12)
    ax.set_title("Correspondence Analysis: SE Activities × Adaptation Strategies",
                 fontsize=14)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  → Saved: {output_path}")


# ═════════════════════════════════════════════
# STEP 7: LaTeX tables
# ═════════════════════════════════════════════

def generate_latex_table(counts, proportions, chi_result):
    """LaTeX table: counts with proportions in parentheses."""
    strategies = [s for s in STRATEGY_ORDER if s in counts.columns and s != "total"]
    short = {"Original": "Orig", "Fine-tuned": "FT", "Quantized": "Quant",
             "Adapter": "Adpt", "Merge": "Mrg", "Mixed": "Mix"}

    header = " & ".join([short.get(s, s) for s in strategies])
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Adaptation strategy distribution by SE activity. "
        r"Cell values show count (\%).}",
        r"\label{tab:adaptation_activity}",
        r"\begin{tabular}{l" + "r" * (len(strategies) + 1) + "}",
        r"\toprule",
        f"Activity & {header} & Total \\\\",
        r"\midrule",
    ]

    for activity in counts.index:
        vals = []
        for s in strategies:
            c = int(counts.loc[activity, s])
            p = proportions.loc[activity, s] * 100
            vals.append(f"{c} ({p:.0f}\\%)")
        total = int(counts.loc[activity, "total"])
        lines.append(f"  {activity} & {' & '.join(vals)} & {total} \\\\")

    lines.append(r"\midrule")
    lines.append(
        f"  \\multicolumn{{{len(strategies) + 2}}}{{l}}"
        f"{{$\\chi^2={chi_result['chi2']:.2f}$, "
        f"$p={chi_result['p_value']:.2e}$, "
        f"Cram\\'er's $V={chi_result['cramers_v']:.3f}$ "
        f"({chi_result['v_magnitude']})}} \\\\"
    )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


def build_arg_parser():
    parser = argparse.ArgumentParser(description="RQ adaptation strategy analysis by activity")
    parser.add_argument("--min-models-per-activity", type=int, default=MIN_MODELS_PER_ACTIVITY)
    parser.add_argument("--max-lineage-depth", type=int, default=DEFAULT_MAX_LINEAGE_DEPTH)
    parser.add_argument("--top-groups", type=int, default=DEFAULT_TOP_GROUPS)
    return parser


def generate_pairwise_latex(pairwise_df):
    """LaTeX table for pairwise results."""
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Pairwise chi-square tests between SE activities (Bonferroni corrected).}",
        r"\label{tab:adaptation_pairwise}",
        r"\begin{tabular}{llrrrrl}",
        r"\toprule",
        r"Activity 1 & Activity 2 & $\chi^2$ & $p$ (corr.) & Cram\'er's $V$ & Effect \\",
        r"\midrule",
    ]
    for _, row in pairwise_df.iterrows():
        sig_mark = "$^{*}$" if row["significant"] else ""
        lines.append(
            f"  {row['activity_1']} & {row['activity_2']} & "
            f"{row['chi2']:.2f} & {row['p_bonferroni']:.3e}{sig_mark} & "
            f"{row['cramers_v']:.3f} & {row['effect_magnitude']} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines)


# ═════════════════════════════════════════════
# MAIN PIPELINE
# ═════════════════════════════════════════════

def main():
    args = build_arg_parser().parse_args()

    print("=" * 60)
    print("RQ: Adaptation Strategy Distribution (Activity Level)")
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

    df = get_adaptation_data_by_activity(driver, args.max_lineage_depth)
    driver.close()

    df["strategy"] = df.apply(classify_strategy, axis=1)

    # Deduplicate: model × activity (a model in multiple tasks of same activity counts once)
    df_dedup = df.drop_duplicates(subset=["model_id", "activity_name"])

    print(f"  ✓ {len(df)} raw records → {len(df_dedup)} after dedup (model × activity)")
    print(f"  ✓ {df_dedup['model_id'].nunique()} unique models")
    print(f"  ✓ {df_dedup['activity_name'].nunique()} SE activities")
    print(f"\n  Global strategy distribution:")
    print(f"  {df_dedup['strategy'].value_counts().to_dict()}")

    print("\n[2b/8] Lineage length statistics by SE activity...")
    lineage_stats = build_lineage_length_stats(df_dedup, "activity_name", "activity_name", args.min_models_per_activity)
    lineage_stats.to_csv(os.path.join(OUTPUT_DIR, "lineage_length_stats_activity.csv"), index=False)
    if lineage_stats.empty:
        print("  No activities met the lineage-length minimum model threshold.")
    else:
        print(f"  ✓ {len(lineage_stats)} activities with >= {args.min_models_per_activity} models")
        print(
            lineage_stats[["activity_name", "totalModels", "avgLineageLength", "medianLineageLength", "maxLineageLength"]]
            .head(min(args.top_groups, len(lineage_stats)))
            .to_string(index=False)
        )

    # ── Descriptive stats ──
    print("\n[2/8] Descriptive statistics per activity...")
    counts, proportions = compute_descriptive_stats(df_dedup)
    counts.to_csv(os.path.join(OUTPUT_DIR, "strategy_counts_activity.csv"))
    proportions.to_csv(os.path.join(OUTPUT_DIR, "strategy_proportions_activity.csv"),
                       float_format="%.4f")
    print(f"\n  Counts:")
    print(counts.to_string())
    print(f"\n  Proportions:")
    print(proportions.round(3).to_string())

    # Task breakdown within activities
    breakdown = compute_task_breakdown(df)
    breakdown.to_csv(os.path.join(OUTPUT_DIR, "task_strategy_breakdown.csv"), index=False)

    # ── Chi-square test ──
    print("\n[3/8] Chi-square test of independence (strategy × activity)...")
    chi_result = run_chi_square(df_dedup)
    print(f"  χ²          : {chi_result['chi2']:.4f}")
    print(f"  p-value     : {chi_result['p_value']:.2e}")
    print(f"  dof         : {chi_result['dof']}")
    print(f"  Cramér's V  : {chi_result['cramers_v']:.4f} ({chi_result['v_magnitude']})")
    print(f"  Significant : {'YES' if chi_result['significant'] else 'NO'} (α={ALPHA})")

    chi_summary = {k: v for k, v in chi_result.items()
                   if k not in ("contingency", "expected", "residuals")}
    pd.DataFrame([chi_summary]).to_csv(
        os.path.join(OUTPUT_DIR, "chi_square_activity.csv"), index=False
    )

    # ── Standardized residuals ──
    print("\n[4/8] Standardized residuals...")
    resid = chi_result["residuals"]
    resid.to_csv(os.path.join(OUTPUT_DIR, "residuals_activity.csv"), float_format="%.3f")
    print(f"\n{resid.round(2).to_string()}")

    noteworthy = []
    for act in resid.index:
        for strat in resid.columns:
            val = resid.loc[act, strat]
            if abs(val) > 2:
                noteworthy.append({
                    "activity": act,
                    "strategy": strat,
                    "residual": round(val, 3),
                    "direction": "over" if val > 0 else "under",
                })
    if noteworthy:
        nw_df = pd.DataFrame(noteworthy).sort_values("residual", key=abs, ascending=False)
        print(f"\n  Noteworthy cells (|r| > 2):")
        print(f"  {nw_df.to_string(index=False)}")

    # ── Post-hoc pairwise ──
    if chi_result["significant"]:
        print("\n[5/8] Pairwise chi-square (all activity pairs, Bonferroni)...")
        pairwise_df = run_all_pairwise_chi_square(df_dedup)
        pairwise_path = os.path.join(OUTPUT_DIR, "pairwise_chi_square_activity.csv")
        pairwise_df.to_csv(pairwise_path, index=False, float_format="%.4f")
        sig_count = pairwise_df["significant"].sum()
        print(f"  ✓ {sig_count}/{len(pairwise_df)} pairs significant")
        print(f"\n{pairwise_df[['activity_1', 'activity_2', 'chi2', 'p_bonferroni', 'cramers_v', 'effect_magnitude']].to_string(index=False)}")
    else:
        print("\n[5/8] Skipping post-hoc (omnibus not significant)")
        pairwise_df = None

    # ── Correspondence analysis ──
    print("\n[6/8] Correspondence analysis...")
    row_coords, col_coords, inertia = run_correspondence_analysis(chi_result["contingency"])
    if row_coords is not None:
        row_coords.to_csv(os.path.join(OUTPUT_DIR, "ca_activity_coords.csv"), float_format="%.4f")
        col_coords.to_csv(os.path.join(OUTPUT_DIR, "ca_strategy_coords.csv"), float_format="%.4f")
        print(f"  Inertia: Dim1={inertia[0]:.1f}%, Dim2={inertia[1]:.1f}%")

    # ── Visualizations ──
    print("\n[7/8] Generating visualizations...")
    plot_stacked_bar(proportions, os.path.join(OUTPUT_DIR, "stacked_bar_activity.png"))
    plot_grouped_bar(counts, os.path.join(OUTPUT_DIR, "grouped_bar_activity.png"))
    plot_residuals_heatmap(resid, os.path.join(OUTPUT_DIR, "residuals_heatmap_activity.png"))

    if not lineage_stats.empty:
        plot_lineage_length_distribution(
            lineage_stats.head(args.top_groups),
            "activity_name",
            os.path.join(OUTPUT_DIR, "lineage_length_distribution_activity.png"),
            "Lineage Length Distribution by SE Activity",
            "SE Activity",
        )
        plot_average_lineage_length(
            lineage_stats.head(args.top_groups),
            "activity_name",
            os.path.join(OUTPUT_DIR, "average_lineage_length_activity.png"),
            "Average Lineage Length by SE Activity",
            "SE Activity",
        )

    if pairwise_df is not None:
        plot_pairwise_heatmap(pairwise_df, os.path.join(OUTPUT_DIR, "pairwise_cramers_v_heatmap.png"))

    if row_coords is not None:
        plot_correspondence_biplot(row_coords, col_coords, inertia,
                                   os.path.join(OUTPUT_DIR, "correspondence_biplot_activity.png"))

    # ── LaTeX tables ──
    print("\n[8/8] Generating LaTeX tables...")
    latex_main = generate_latex_table(counts, proportions, chi_result)
    with open(os.path.join(OUTPUT_DIR, "table_adaptation_activity.tex"), "w") as f:
        f.write(latex_main)

    if pairwise_df is not None:
        latex_pair = generate_pairwise_latex(pairwise_df)
        with open(os.path.join(OUTPUT_DIR, "table_pairwise_activity.tex"), "w") as f:
            f.write(latex_pair)

    print(f"  → Saved LaTeX tables")

    # ── Done ──
    print("\n" + "=" * 60)
    print("EXPERIMENT COMPLETE")
    print("=" * 60)
    print(f"All outputs in: {OUTPUT_DIR}/")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        print(f"  - {f}")


if __name__ == "__main__":
    main()
