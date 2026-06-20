"""
Queries for activity-level metrics over time.
Fixed to match actual graph schema:
  - SEActivity: properties id (unique), label
  - SEModel: properties createdAt (STRING, e.g. "2023-05-14T..."), id (unique)
  - SEModelAncestor (also :Model): same properties + SUITABLE_FOR -> SETask
  - SEModelDescendant (also :Model): same properties + SUITABLE_FOR -> SETask
  - SETask: properties id (unique), label, description
  - Dataset: properties createdAt (STRING), id (unique)
  - Relationships:
      (SEModel|SEModelAncestor|SEModelDescendant)-[:SUITABLE_FOR]->(SETask)
      (SETask)-[:USED_FOR]->(SEActivity)
      (SEModel|SEModelAncestor|SEModelDescendant)-[:TRAINED_ON]->(Dataset)

NOTE: SUITABLE_FOR connects SETask from multiple model labels
      (SEModel, SEModelAncestor, SEModelDescendant, Model).
      We use a generic (m)-[:SUITABLE_FOR]->(t:SETask) pattern
      to capture all model types that are mapped to SE tasks.
      If you only want core SEModel nodes, replace (m) with (m:SEModel).
"""

# ─────────────────────────────────────────────────────────────────────
# (1) MODEL COUNT BY ACTIVITY AND YEAR
# ─────────────────────────────────────────────────────────────────────
MODELS_BY_ACTIVITY_YEAR_QUERY = """
MATCH (m)-[:SUITABLE_FOR]->(t:SETask)-[:USED_FOR]->(a:SEActivity)
WHERE m.createdAt IS NOT NULL
WITH
    a.label AS activity_name,
    toInteger(substring(toString(m.createdAt), 0, 4)) AS year,
    toInteger(substring(toString(m.createdAt), 5, 2)) AS month,
    m
WHERE year >= 2020
WITH
    activity_name,
    toString(year) + '-Q' + toString(toInteger((month - 1) / 3) + 1) AS time_bucket,
    count(DISTINCT m) AS quarterly_model_count
RETURN
    activity_name,
    time_bucket,
    quarterly_model_count AS model_count
ORDER BY activity_name, time_bucket
"""

# ─────────────────────────────────────────────────────────────────────
# (2) DATASET COUNT BY ACTIVITY AND YEAR
#     Counts distinct datasets linked (via TRAINED_ON) to models
#     in each activity. Year is based on the model's createdAt,
#     i.e. "when did this model-dataset pair enter the ecosystem?"
# ─────────────────────────────────────────────────────────────────────
DATASETS_BY_ACTIVITY_YEAR_QUERY = """
MATCH (m)-[:SUITABLE_FOR]->(t:SETask)-[:USED_FOR]->(a:SEActivity)
WHERE m.createdAt IS NOT NULL
MATCH (m)-[:TRAINED_ON]->(d:Dataset)
WITH
    a.label AS activity_name,
    toInteger(substring(toString(m.createdAt), 0, 4)) AS year,
    toInteger(substring(toString(m.createdAt), 5, 2)) AS month,
    d
WHERE year >= 2020
WITH
    activity_name,
    toString(year) + '-Q' + toString(toInteger((month - 1) / 3) + 1) AS time_bucket,
    count(DISTINCT d) AS quarterly_dataset_count
RETURN
    activity_name,
    time_bucket,
    quarterly_dataset_count AS dataset_count
ORDER BY activity_name, time_bucket
"""

# ─────────────────────────────────────────────────────────────────────
# (3) TASK COVERAGE BY ACTIVITY AND YEAR
#     For each activity and year, what proportion of its SE tasks
#     have at least one model created by that year (cumulative)?
# ─────────────────────────────────────────────────────────────────────
TASK_COVERAGE_BY_ACTIVITY_YEAR_QUERY = """
// Step 1: Get total task count per activity
MATCH (t:SETask)-[:USED_FOR]->(a:SEActivity)
WITH a.label AS activity_name, count(DISTINCT t) AS total_tasks

// Step 2: For each activity+quarter, count tasks whose first model appears in that quarter
MATCH (m)-[:SUITABLE_FOR]->(t:SETask)-[:USED_FOR]->(a:SEActivity)
WHERE m.createdAt IS NOT NULL
  AND a.label = activity_name
  AND toInteger(substring(toString(m.createdAt), 0, 4)) >= 2020
WITH
    activity_name,
    total_tasks,
    t,
    toInteger(substring(toString(m.createdAt), 0, 4)) AS year,
    toInteger(substring(toString(m.createdAt), 5, 2)) AS month
WITH
    activity_name,
    total_tasks,
    t,
    min(toString(year) + '-Q' + toString(toInteger((month - 1) / 3) + 1)) AS time_bucket
WITH
    activity_name,
    total_tasks,
    time_bucket,
    count(*) AS quarterly_tasks_with_models
RETURN
    activity_name,
    time_bucket,
    total_tasks,
    quarterly_tasks_with_models AS monthly_tasks_with_models,
    round(toFloat(quarterly_tasks_with_models) / toFloat(total_tasks), 4) AS task_coverage_ratio
ORDER BY activity_name, time_bucket
"""

# ─────────────────────────────────────────────────────────────────────
# (3b) TASK COVERAGE - ALTERNATIVE (simpler, no correlated subquery)
#      If the above has scoping issues in your Neo4j version,
#      use this two-step approach in Python instead.
# ─────────────────────────────────────────────────────────────────────
TOTAL_TASKS_PER_ACTIVITY_QUERY = """
MATCH (t:SETask)-[:USED_FOR]->(a:SEActivity)
RETURN a.label AS activity_name, count(DISTINCT t) AS total_tasks
ORDER BY activity_name
"""

TASKS_WITH_MODELS_PER_ACTIVITY_YEAR_QUERY = """
MATCH (m)-[:SUITABLE_FOR]->(t:SETask)-[:USED_FOR]->(a:SEActivity)
WHERE m.createdAt IS NOT NULL
WITH
    a.label AS activity_name,
    toInteger(substring(toString(m.createdAt), 0, 4)) AS year,
    t
WITH
    activity_name,
    year,
    count(DISTINCT t) AS tasks_with_models
RETURN
    activity_name,
    year,
    tasks_with_models
ORDER BY activity_name, year
"""

# Then in Python: task_coverage = tasks_with_models / total_tasks

# ─────────────────────────────────────────────────────────────────────
# (4) CUMULATIVE VERSIONS
#     The queries above give per-year counts. If you need cumulative
#     (all models created up to and including year Y), use these:
# ─────────────────────────────────────────────────────────────────────

CUMULATIVE_MODELS_BY_ACTIVITY_YEAR_QUERY = """
MATCH (m)-[:SUITABLE_FOR]->(t:SETask)-[:USED_FOR]->(a:SEActivity)
WHERE m.createdAt IS NOT NULL
WITH
    a.label AS activity_name,
    toInteger(substring(toString(m.createdAt), 0, 4)) AS model_year,
    m
WITH
    activity_name,
    model_year,
    count(DISTINCT m) AS yearly_count
ORDER BY activity_name, model_year
WITH
    activity_name,
    collect({year: model_year, count: yearly_count}) AS yearly_data
UNWIND range(0, size(yearly_data) - 1) AS idx
WITH
    activity_name,
    yearly_data[idx].year AS year,
    reduce(s = 0, i IN range(0, idx) | s + yearly_data[i].count) AS cumulative_model_count
RETURN activity_name, year, cumulative_model_count
ORDER BY activity_name, year
"""

CUMULATIVE_DATASETS_BY_ACTIVITY_YEAR_QUERY = """
MATCH (m)-[:SUITABLE_FOR]->(t:SETask)-[:USED_FOR]->(a:SEActivity)
WHERE m.createdAt IS NOT NULL
MATCH (m)-[:TRAINED_ON]->(d:Dataset)
WITH
    a.label AS activity_name,
    toInteger(substring(toString(m.createdAt), 0, 4)) AS model_year,
    d
WITH
    activity_name,
    model_year,
    count(DISTINCT d) AS yearly_count
ORDER BY activity_name, model_year
WITH
    activity_name,
    collect({year: model_year, count: yearly_count}) AS yearly_data
UNWIND range(0, size(yearly_data) - 1) AS idx
WITH
    activity_name,
    yearly_data[idx].year AS year,
    reduce(s = 0, i IN range(0, idx) | s + yearly_data[i].count) AS cumulative_dataset_count
RETURN activity_name, year, cumulative_dataset_count
ORDER BY activity_name, year
"""

CUMULATIVE_TASK_COVERAGE_BY_ACTIVITY_YEAR_QUERY = """
// For cumulative task coverage, count distinct tasks with
// at least one model created <= that year
MATCH (m)-[:SUITABLE_FOR]->(t:SETask)-[:USED_FOR]->(a:SEActivity)
WHERE m.createdAt IS NOT NULL
WITH
    a.label AS activity_name,
    t,
    min(toInteger(substring(toString(m.createdAt), 0, 4))) AS first_model_year

// Get total tasks per activity for the denominator
MATCH (t2:SETask)-[:USED_FOR]->(a2:SEActivity)
WHERE a2.label = activity_name
WITH activity_name, first_model_year, t,
     count(DISTINCT t2) AS total_tasks

// For each year, count how many tasks had their first model by that year
UNWIND range(2018, 2026) AS year
WITH activity_name, year, total_tasks,
     sum(CASE WHEN first_model_year <= year THEN 1 ELSE 0 END) AS tasks_with_models
WHERE tasks_with_models > 0
RETURN
    activity_name,
    year,
    total_tasks,
    tasks_with_models,
    round(toFloat(tasks_with_models) / toFloat(total_tasks), 4) AS task_coverage_ratio
ORDER BY activity_name, year
"""

# ─────────────────────────────────────────────────────────────────────
# (5) COMBINED TIMESERIES QUERY
#     Used by the package import path and any dashboard code that wants
#     all three metrics in one result set.
# ─────────────────────────────────────────────────────────────────────
ACTIVITY_METRICS_ALL_TIMESERIES_QUERY = """
CALL {
    MATCH (m)-[:SUITABLE_FOR]->(t:SETask)-[:USED_FOR]->(a:SEActivity)
    WHERE m.createdAt IS NOT NULL
      AND toInteger(substring(toString(m.createdAt), 0, 4)) >= 2020
    WITH
        a.label AS activity_name,
        substring(toString(m.createdAt), 0, 7) AS time_bucket,
        count(DISTINCT m) AS metric_value
    RETURN activity_name, time_bucket, metric_value, 'model_count' AS metric_type
}
UNION ALL
CALL {
    MATCH (m)-[:SUITABLE_FOR]->(t:SETask)-[:USED_FOR]->(a:SEActivity)
    WHERE m.createdAt IS NOT NULL
      AND toInteger(substring(toString(m.createdAt), 0, 4)) >= 2020
    MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    WITH
        a.label AS activity_name,
        substring(toString(m.createdAt), 0, 7) AS time_bucket,
        count(DISTINCT d) AS metric_value
    RETURN activity_name, time_bucket, metric_value, 'dataset_count' AS metric_type
}
UNION ALL
CALL {
    MATCH (t:SETask)-[:USED_FOR]->(a:SEActivity)
    WITH a.label AS activity_name, count(DISTINCT t) AS total_tasks
    MATCH (m)-[:SUITABLE_FOR]->(t2:SETask)-[:USED_FOR]->(a2:SEActivity)
    WHERE m.createdAt IS NOT NULL
      AND a2.label = activity_name
      AND toInteger(substring(toString(m.createdAt), 0, 4)) >= 2020
    WITH
        activity_name,
        total_tasks,
        t2,
        substring(toString(m.createdAt), 0, 7) AS time_bucket
    WITH
        activity_name,
        total_tasks,
        t2,
        min(time_bucket) AS time_bucket
    WITH
        activity_name,
        total_tasks,
        time_bucket,
        count(*) AS metric_value
    RETURN activity_name, time_bucket, metric_value, 'task_coverage' AS metric_type
}
RETURN activity_name, time_bucket, metric_value, metric_type
ORDER BY activity_name, metric_type, time_bucket
"""