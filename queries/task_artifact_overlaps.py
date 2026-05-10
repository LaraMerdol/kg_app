_ARTIFACT_FILTER = "any(lbl IN labels(n) WHERE lbl IN ['Model','Dataset','Paper','Benchmark','Collection','Space'])"

_TASK_ARTIFACT_BASE = f"""
MATCH (n)
WHERE {_ARTIFACT_FILTER}
  AND n.seTaskGroups IS NOT NULL
WITH
  CASE head(labels(n))
    WHEN 'Collection' THEN 'Collection:' + coalesce(n.slug, toString(n.id), n.name, toString(id(n)))
    ELSE head(labels(n)) + ':' + coalesce(toString(n.id), n.name, toString(id(n)))
  END AS artifactKey,
  head(labels(n)) AS artifactType,
  [g IN n.seTaskGroups WHERE g IS NOT NULL AND g <> ''] AS groups
WHERE size(groups) > 0
"""

TASK_ARTIFACT_COUNTS_QUERY = _TASK_ARTIFACT_BASE + """
UNWIND groups AS task
RETURN task, count(DISTINCT artifactKey) AS artifactCount
ORDER BY task
"""

TASK_ARTIFACT_TYPE_COUNTS_QUERY = _TASK_ARTIFACT_BASE + """
UNWIND groups AS task
RETURN
  task,
  count(DISTINCT CASE WHEN artifactType = 'Dataset' THEN artifactKey END) AS datasetCount,
  count(DISTINCT CASE WHEN artifactType = 'Model' THEN artifactKey END) AS modelCount,
  count(DISTINCT CASE WHEN artifactType = 'Space' THEN artifactKey END) AS spaceCount,
  count(DISTINCT CASE WHEN artifactType = 'Benchmark' THEN artifactKey END) AS benchmarkCount,
  count(DISTINCT CASE WHEN artifactType = 'Collection' THEN artifactKey END) AS collectionCount
ORDER BY task
"""

TASK_ARTIFACT_TOP_OVERLAPS_QUERY = _TASK_ARTIFACT_BASE + """
UNWIND groups AS task1
UNWIND groups AS task2
WITH artifactKey, artifactType, task1, task2
WHERE task1 < task2
WITH
  task1,
  task2,
  collect(DISTINCT artifactKey) AS sharedAll,
  collect(DISTINCT CASE WHEN artifactType = 'Dataset' THEN artifactKey END) AS sharedDatasetRaw,
  collect(DISTINCT CASE WHEN artifactType = 'Model' THEN artifactKey END) AS sharedModelRaw,
  collect(DISTINCT CASE WHEN artifactType = 'Space' THEN artifactKey END) AS sharedSpaceRaw,
  collect(DISTINCT CASE WHEN artifactType = 'Benchmark' THEN artifactKey END) AS sharedBenchmarkRaw,
  collect(DISTINCT CASE WHEN artifactType = 'Collection' THEN artifactKey END) AS sharedCollectionRaw
WITH
  task1,
  task2,
  sharedAll,
  [x IN sharedDatasetRaw WHERE x IS NOT NULL] AS sharedDataset,
  [x IN sharedModelRaw WHERE x IS NOT NULL] AS sharedModel,
  [x IN sharedSpaceRaw WHERE x IS NOT NULL] AS sharedSpace,
  [x IN sharedBenchmarkRaw WHERE x IS NOT NULL] AS sharedBenchmark,
  [x IN sharedCollectionRaw WHERE x IS NOT NULL] AS sharedCollection
RETURN
  task1,
  task2,
  size(sharedAll) AS sharedArtifactCount,
  size(sharedDataset) AS overlapDatasetCount,
  size(sharedModel) AS overlapModelCount,
  size(sharedSpace) AS overlapSpaceCount,
  size(sharedBenchmark) AS overlapBenchmarkCount,
  size(sharedCollection) AS overlapCollectionCount
ORDER BY sharedArtifactCount DESC, task1, task2
LIMIT $top_n
"""

TASK_ARTIFACT_PAIR_OVERLAP_QUERY = _TASK_ARTIFACT_BASE + """
WITH artifactKey, groups,
     CASE WHEN $task1 IN groups THEN 1 ELSE 0 END AS inTask1,
     CASE WHEN $task2 IN groups THEN 1 ELSE 0 END AS inTask2
WITH
  collect(DISTINCT CASE WHEN inTask1 = 1 THEN artifactKey END) AS task1Raw,
  collect(DISTINCT CASE WHEN inTask2 = 1 THEN artifactKey END) AS task2Raw,
  collect(DISTINCT CASE WHEN inTask1 = 1 AND inTask2 = 1 THEN artifactKey END) AS sharedRaw
WITH
  [x IN task1Raw WHERE x IS NOT NULL] AS task1Artifacts,
  [x IN task2Raw WHERE x IS NOT NULL] AS task2Artifacts,
  [x IN sharedRaw WHERE x IS NOT NULL] AS sharedArtifacts
RETURN
  task1Artifacts,
  task2Artifacts,
  sharedArtifacts,
  size(task1Artifacts) AS task1ArtifactCount,
  size(task2Artifacts) AS task2ArtifactCount,
  size(sharedArtifacts) AS sharedArtifactCount,
  CASE
    WHEN (size(task1Artifacts) + size(task2Artifacts) - size(sharedArtifacts)) = 0
    THEN 0.0
    ELSE toFloat(size(sharedArtifacts)) / toFloat(size(task1Artifacts) + size(task2Artifacts) - size(sharedArtifacts))
  END AS jaccardArtifacts,
  CASE
    WHEN size(task1Artifacts) = 0 OR size(task2Artifacts) = 0
    THEN 0.0
    ELSE toFloat(size(sharedArtifacts)) /
         toFloat(CASE WHEN size(task1Artifacts) < size(task2Artifacts) THEN size(task1Artifacts) ELSE size(task2Artifacts) END)
  END AS overlapCoeffArtifacts
LIMIT 1
"""

TASK_ARTIFACT_PAIR_DETAILS_QUERY = """
MATCH (n)
WHERE any(lbl IN labels(n) WHERE lbl IN ['Model','Dataset','Paper','Benchmark','Collection','Space'])
  AND n.seTaskGroups IS NOT NULL
  AND ($task1 IN n.seTaskGroups OR $task2 IN n.seTaskGroups)
WITH
  CASE head(labels(n))
    WHEN 'Collection' THEN 'Collection:' + coalesce(n.slug, n.id, n.name, toString(id(n)))
    ELSE head(labels(n)) + ':' + coalesce(n.id, n.name, toString(id(n)))
  END AS artifactKey,
  head(labels(n)) AS artifactType,
  [g IN n.seTaskGroups WHERE g IS NOT NULL AND g <> ''] AS groups,
  CASE WHEN $task1 IN n.seTaskGroups THEN true ELSE false END AS inTask1,
  CASE WHEN $task2 IN n.seTaskGroups THEN true ELSE false END AS inTask2
RETURN
  artifactKey,
  artifactType,
  groups,
  inTask1,
  inTask2
ORDER BY inTask1 DESC, inTask2 DESC, artifactType, artifactKey
LIMIT $pair_detail_limit
"""


TASK_ACTIVITY_BY_TASK_QUERY = """
MATCH (t:SETask)-[:USED_FOR]-(a:SEActivity)
WITH
  coalesce(t.id, t.name, toString(id(t))) AS task,
  coalesce(a.id, a.name, toString(id(a))) AS activity
RETURN
  task,
  collect(DISTINCT activity) AS activities
ORDER BY task
"""


TASK_ACTIVITY_TOP_OVERLAPS_QUERY = """
MATCH (n)
WHERE any(lbl IN labels(n) WHERE lbl IN ['Model','Dataset','Space'])
  AND n.seTaskGroups IS NOT NULL
WITH
  CASE head(labels(n))
    WHEN 'Collection' THEN 'Collection:' + coalesce(toString(n.slug), toString(n.id), n.name, toString(id(n)))
    ELSE head(labels(n)) + ':' + coalesce(toString(n.id), n.name, toString(id(n)))
  END AS artifactKey,
  head(labels(n)) AS artifactType,
  [g IN n.seTaskGroups WHERE g IS NOT NULL AND g <> ''] AS groups
WHERE size(groups) > 0
UNWIND groups AS taskId
MATCH (t:SETask)-[:USED_FOR]-(a:SEActivity)
WHERE toLower(trim(coalesce(t.id, ''))) = toLower(trim(taskId))
   OR toLower(trim(coalesce(t.name, ''))) = toLower(trim(taskId))
WITH DISTINCT artifactKey, artifactType, coalesce(a.id, a.name, toString(id(a))) AS activity
WITH
  activity,
  collect(DISTINCT artifactKey) AS allArtifactsRaw,
  collect(DISTINCT CASE WHEN artifactType = 'Model' THEN artifactKey END) AS modelArtifactsRaw,
  collect(DISTINCT CASE WHEN artifactType = 'Dataset' THEN artifactKey END) AS datasetArtifactsRaw,
  collect(DISTINCT CASE WHEN artifactType = 'Space' THEN artifactKey END) AS spaceArtifactsRaw
WITH
  activity,
  [x IN allArtifactsRaw WHERE x IS NOT NULL] AS allArtifacts,
  [x IN modelArtifactsRaw WHERE x IS NOT NULL] AS modelArtifacts,
  [x IN datasetArtifactsRaw WHERE x IS NOT NULL] AS datasetArtifacts,
  [x IN spaceArtifactsRaw WHERE x IS NOT NULL] AS spaceArtifacts
WITH collect({
  activity: activity,
  allArtifacts: allArtifacts,
  modelArtifacts: modelArtifacts,
  datasetArtifacts: datasetArtifacts,
  spaceArtifacts: spaceArtifacts
}) AS activityRows
UNWIND range(0, size(activityRows) - 1) AS i
UNWIND range(i + 1, size(activityRows) - 1) AS j
WITH activityRows[i] AS a1, activityRows[j] AS a2
WITH
  a1,
  a2,
  [x IN a1.allArtifacts WHERE x IN a2.allArtifacts] AS overlapTotal,
  [x IN a1.modelArtifacts WHERE x IN a2.modelArtifacts] AS overlapModel,
  [x IN a1.datasetArtifacts WHERE x IN a2.datasetArtifacts] AS overlapDataset,
  [x IN a1.spaceArtifacts WHERE x IN a2.spaceArtifacts] AS overlapSpace
RETURN
  a1.activity AS activity1,
  a2.activity AS activity2,
  size(overlapDataset) AS overlapDatasetCount,
  size(overlapSpace) AS overlapSpaceCount,
  size(overlapModel) AS overlapModelCount,
  size(overlapTotal) AS overlapTotalCount,
  CASE
    WHEN (size(a1.allArtifacts) + size(a2.allArtifacts) - size(overlapTotal)) = 0
    THEN 0.0
    ELSE toFloat(size(overlapTotal)) /
         toFloat(size(a1.allArtifacts) + size(a2.allArtifacts) - size(overlapTotal))
  END AS jaccardTotal,
  CASE
    WHEN (size(a1.modelArtifacts) + size(a2.modelArtifacts) - size(overlapModel)) = 0
    THEN 0.0
    ELSE toFloat(size(overlapModel)) /
         toFloat(size(a1.modelArtifacts) + size(a2.modelArtifacts) - size(overlapModel))
  END AS jaccardModel,
  CASE
    WHEN (size(a1.datasetArtifacts) + size(a2.datasetArtifacts) - size(overlapDataset)) = 0
    THEN 0.0
    ELSE toFloat(size(overlapDataset)) /
         toFloat(size(a1.datasetArtifacts) + size(a2.datasetArtifacts) - size(overlapDataset))
  END AS jaccardDataset,
  CASE
    WHEN (size(a1.spaceArtifacts) + size(a2.spaceArtifacts) - size(overlapSpace)) = 0
    THEN 0.0
    ELSE toFloat(size(overlapSpace)) /
         toFloat(size(a1.spaceArtifacts) + size(a2.spaceArtifacts) - size(overlapSpace))
  END AS jaccardSpace
ORDER BY overlapTotalCount DESC, jaccardTotal DESC, overlapModelCount DESC, overlapDatasetCount DESC, overlapSpaceCount DESC, activity1, activity2
LIMIT $top_n
"""


TASK_ARTIFACT_SPECIFICITY_QUERY = _TASK_ARTIFACT_BASE + """
UNWIND groups AS task
WITH artifactKey, artifactType, groups, task
WHERE task = $task_name
RETURN
  artifactKey,
  artifactType,
  size(groups) AS taskShareCount,
  groups AS taskGroups
ORDER BY taskShareCount ASC, artifactType, artifactKey
LIMIT $top_n
"""


TASK_ARTIFACT_TASK_SHARE_QUERY = _TASK_ARTIFACT_BASE + """
UNWIND groups AS task
RETURN
  task,
  artifactKey,
  artifactType,
  size(groups) AS taskShareCount
ORDER BY task, taskShareCount, artifactType, artifactKey
LIMIT $top_n
"""


