"""Model lineage family queries for specific task visualization.

Schema notes for HFSEKG:
- Seeds attach to tasks via (seed:SEModel)-[:SUITABLE_FOR]->(t:SETask)
- Lineage uses :Model nodes (seeds are also :Model, plus :SEModel)
- Lineage convention: (child)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM]->(parent)
- Only :Model nodes whose `exist` property IS NULL are included.
"""

MODEL_LINEAGE_FAMILY_NODES_QUERY = """
// --- Models reachable from this task's seeds (only those with exist IS NULL) ---
MATCH (t:SETask)
WHERE coalesce(t.id, t.name, toString(id(t))) = $task_name

MATCH (seed:SEModel)-[:SUITABLE_FOR]->(t)
WHERE seed.exist IS NULL
WITH collect(DISTINCT seed) AS seeds
UNWIND seeds AS seed

// *0..20 lets the seed itself appear (path of length 0)
OPTIONAL MATCH (seed)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM*0..20]->(model:Model)
WHERE model.exist IS NULL
WITH seeds, model
WHERE model IS NOT NULL

// One row per distinct model
WITH seeds, collect(DISTINCT model) AS allModels
UNWIND allModels AS model

// Structural classification per model
WITH model,
     any(s IN seeds WHERE id(s) = id(model)) AS isSeed,
     NOT EXISTS {
       MATCH (model)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM]->(parent:Model)
       WHERE parent.exist IS NULL
     } AS isRoot

WITH coalesce(model.id, model.name, toString(id(model))) AS modelId,
     isSeed, isRoot,
     CASE
       WHEN isSeed AND isRoot THEN 'Seed + Root'
       WHEN isSeed            THEN 'Seed Model'
       WHEN isRoot            THEN 'Root Model'
       ELSE                        'Middle Model'
     END AS modelType,
     CASE
       WHEN isSeed AND isRoot THEN '#a855f7'   // purple
       WHEN isSeed            THEN '#ef4444'   // red
       WHEN isRoot            THEN '#22c55e'   // green
       ELSE                        '#3b82f6'   // blue
     END AS color

RETURN DISTINCT {
  id: modelId,
  label: 'Model',
  title: modelId,
  color: color,
  modelType: modelType,
  isSeed: isSeed
} AS node

UNION

// --- Task node ---
MATCH (t:SETask)
WHERE coalesce(t.id, t.name, toString(id(t))) = $task_name
RETURN {
  id: coalesce(t.id, t.name, toString(id(t))),
  label: 'SETask',
  title: coalesce(t.id, t.name, toString(id(t))),
  color: '#f97316',
  modelType: 'Task',
  isSeed: false
} AS node
"""

MODEL_LINEAGE_FAMILY_EDGES_QUERY = """
// --- Lineage edges among models with exist IS NULL ---
MATCH (t:SETask)
WHERE coalesce(t.id, t.name, toString(id(t))) = $task_name

MATCH (seed:SEModel)-[:SUITABLE_FOR]->(t)
WHERE seed.exist IS NULL

MATCH p = (seed)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM*1..20]->(target:Model)
WHERE target.exist IS NULL
  AND ALL(n IN nodes(p) WHERE n.exist IS NULL)
UNWIND relationships(p) AS rel

// Stored: (child)-[r]->(parent). For top-down tree draw parent -> child:
WITH DISTINCT
  coalesce(endNode(rel).id,   endNode(rel).name,   toString(id(endNode(rel))))   AS sourceId,
  coalesce(startNode(rel).id, startNode(rel).name, toString(id(startNode(rel)))) AS targetId,
  type(rel) AS relType

RETURN {
  source: sourceId,
  target: targetId,
  type: relType
} AS edge

UNION

// --- Task -> Seed edges (only seeds with exist IS NULL) ---
MATCH (t:SETask)
WHERE coalesce(t.id, t.name, toString(id(t))) = $task_name
MATCH (seed:SEModel)-[:SUITABLE_FOR]->(t)
WHERE seed.exist IS NULL
RETURN {
  source: coalesce(t.id, t.name, toString(id(t))),
  target: coalesce(seed.id, seed.name, toString(id(seed))),
  type: 'SUITABLE_FOR'
} AS edge
"""


MODEL_LINEAGE_BASE_FAMILY_TAG_CLOUD_QUERY = """
// Count most-used root/base model families for one task.
MATCH (t:SETask)
WHERE coalesce(t.id, t.name, toString(id(t))) = $task_name

MATCH (seed:SEModel)-[:SUITABLE_FOR]->(t)
WHERE seed.exist IS NULL

// Longest path endpoint(s) from each seed are treated as root/base for that seed.
OPTIONAL MATCH p = (seed)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM*0..20]->(root:Model)
WHERE root.exist IS NULL
WITH seed, root, length(p) AS depth
WHERE root IS NOT NULL

WITH seed, collect({root: root, depth: depth}) AS candidates
WITH seed,
     candidates,
     reduce(mx = 0, c IN candidates | CASE WHEN c.depth > mx THEN c.depth ELSE mx END) AS maxDepth
UNWIND [c IN candidates WHERE c.depth = maxDepth] AS top

WITH coalesce(top.root.id, top.root.name, toString(id(top.root))) AS rootModelId,
     count(DISTINCT seed) AS usageBySeed

WITH rootModelId,
     usageBySeed,
     toLower(rootModelId) AS rid

WITH
  CASE
    WHEN rid CONTAINS 'qwen' THEN 'qwen'
    WHEN rid CONTAINS 'llama' THEN 'llama'
    WHEN rid CONTAINS 'mistral' THEN 'mistral'
    WHEN rid CONTAINS 'gemma' THEN 'gemma'
    WHEN rid CONTAINS 'phi' THEN 'phi'
    WHEN rid CONTAINS 'deepseek' THEN 'deepseek'
    WHEN rid CONTAINS 'falcon' THEN 'falcon'
    WHEN rid CONTAINS 'mixtral' THEN 'mixtral'
    WHEN rid CONTAINS 'yi' THEN 'yi'
    ELSE split(split(rid, '/')[size(split(rid, '/')) - 1], '-')[0]
  END AS family,
  usageBySeed

RETURN family, sum(usageBySeed) AS usage
ORDER BY usage DESC, family ASC
LIMIT 40
"""