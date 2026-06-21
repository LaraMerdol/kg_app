MODEL_LINEAGE_ALL_TASKS_QUERY = """
MATCH (t:SETask)
WITH coalesce(t.id, t.name, toString(id(t))) AS taskKey
MATCH (seed:Model)
WHERE taskKey IN coalesce(seed.seTaskGroups, [])
OPTIONAL MATCH (seed)-[r:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM]->(:Model)
WHERE ($confidence_is_null AND r.confidence IS NULL)
    OR ((NOT $confidence_is_null) AND r.confidence IS NOT NULL)

WITH taskKey, type(r) AS relType
WITH taskKey,
     sum(CASE WHEN relType = 'IS_FINETUNED_FROM' THEN 1 ELSE 0 END) AS finetunes,
     sum(CASE WHEN relType = 'IS_ADAPTER_OF' THEN 1 ELSE 0 END) AS adapters,
     sum(CASE WHEN relType = 'IS_MERGE_OF' THEN 1 ELSE 0 END) AS merges,
     sum(CASE WHEN relType = 'IS_QUANTIZED_FROM' THEN 1 ELSE 0 END) AS quantizations

WITH taskKey, finetunes, adapters, merges, quantizations,
     (finetunes + adapters + merges + quantizations) AS total

RETURN taskKey AS seTask,
       total,
       finetunes,
       adapters,
       merges,
       quantizations,
       CASE WHEN total = 0 THEN 0.0 ELSE toFloat(finetunes) / total END AS finetuneShare,
       CASE WHEN total = 0 THEN 0.0 ELSE toFloat(adapters) / total END AS adapterShare,
       CASE WHEN total = 0 THEN 0.0 ELSE toFloat(merges) / total END AS mergeShare,
       CASE WHEN total = 0 THEN 0.0 ELSE toFloat(quantizations) / total END AS quantShare
ORDER BY adapterShare DESC
"""


MODEL_LINEAGE_LENGTH_DISTRIBUTION_BY_TASK_QUERY = """
MATCH (t:SETask)
WITH coalesce(t.id, t.name, toString(id(t))) AS taskKey
MATCH (seed:Model)
WHERE taskKey IN coalesce(seed.seTaskGroups, [])

// Compute max lineage length for each seed (0 if no ancestry)
CALL {
    WITH seed
    OPTIONAL MATCH p = (seed)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM*1..20]->(lm:Model)
    WHERE NOT (lm)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM]->()
    RETURN coalesce(max(length(p)), 0) AS lineageLen
}

WITH taskKey, seed, lineageLen
WITH taskKey,
         count(DISTINCT seed) AS numSeeds,
         sum(CASE WHEN lineageLen = 0 THEN 1 ELSE 0 END) AS len0,
         sum(CASE WHEN lineageLen = 1 THEN 1 ELSE 0 END) AS len1,
         sum(CASE WHEN lineageLen = 2 THEN 1 ELSE 0 END) AS len2,
         sum(CASE WHEN lineageLen = 3 THEN 1 ELSE 0 END) AS len3,
         sum(CASE WHEN lineageLen = 4 THEN 1 ELSE 0 END) AS len4,
         sum(CASE WHEN lineageLen >= 5 THEN 1 ELSE 0 END) AS len5plus

RETURN taskKey AS seTask, numSeeds,
             len0, len1, len2, len3, len4, len5plus,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len0)/numSeeds END AS share0,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len1)/numSeeds END AS share1,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len2)/numSeeds END AS share2,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len3)/numSeeds END AS share3,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len4)/numSeeds END AS share4,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len5plus)/numSeeds END AS share5plus
ORDER BY numSeeds DESC
"""


MODEL_LINEAGE_BY_ACTIVITY_QUERY = """
MATCH (t:SETask)-[:USED_FOR]->(a:SEActivity)
WITH coalesce(t.id, t.name, toString(id(t))) AS taskKey,
     coalesce(a.id, a.label, toString(id(a))) AS activityKey
MATCH (seed:Model)
WHERE taskKey IN coalesce(seed.seTaskGroups, [])
WITH DISTINCT activityKey, seed
OPTIONAL MATCH (seed)-[r:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM]->(:Model)
WHERE ($confidence_is_null AND r.confidence IS NULL)
    OR ((NOT $confidence_is_null) AND r.confidence IS NOT NULL)

WITH activityKey, type(r) AS relType
WITH activityKey,
     sum(CASE WHEN relType = 'IS_FINETUNED_FROM' THEN 1 ELSE 0 END) AS finetunes,
     sum(CASE WHEN relType = 'IS_ADAPTER_OF' THEN 1 ELSE 0 END) AS adapters,
     sum(CASE WHEN relType = 'IS_MERGE_OF' THEN 1 ELSE 0 END) AS merges,
     sum(CASE WHEN relType = 'IS_QUANTIZED_FROM' THEN 1 ELSE 0 END) AS quantizations

WITH activityKey, finetunes, adapters, merges, quantizations,
     (finetunes + adapters + merges + quantizations) AS total

RETURN activityKey AS seActivity,
       total,
       finetunes,
       adapters,
       merges,
       quantizations,
       CASE WHEN total = 0 THEN 0.0 ELSE toFloat(finetunes) / total END AS finetuneShare,
       CASE WHEN total = 0 THEN 0.0 ELSE toFloat(adapters) / total END AS adapterShare,
       CASE WHEN total = 0 THEN 0.0 ELSE toFloat(merges) / total END AS mergeShare,
       CASE WHEN total = 0 THEN 0.0 ELSE toFloat(quantizations) / total END AS quantShare
ORDER BY adapterShare DESC
"""


MODEL_LINEAGE_LENGTH_DISTRIBUTION_BY_ACTIVITY_QUERY = """
MATCH (t:SETask)-[:USED_FOR]->(a:SEActivity)
WITH coalesce(t.id, t.name, toString(id(t))) AS taskKey,
     coalesce(a.id, a.label, toString(id(a))) AS activityKey
MATCH (seed:Model)
WHERE taskKey IN coalesce(seed.seTaskGroups, [])
WITH DISTINCT activityKey, seed
CALL {
    WITH seed
    OPTIONAL MATCH p = (seed)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM*1..20]->(lm:Model)
    WHERE NOT (lm)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM]->()
        AND (
            relationships(p) IS NULL
            OR all(
                rel IN relationships(p)
                WHERE ($confidence_is_null AND rel.confidence IS NULL)
                     OR ((NOT $confidence_is_null) AND rel.confidence IS NOT NULL)
            )
        )
    RETURN coalesce(max(length(p)), 0) AS lineageLen
}

WITH activityKey, seed, lineageLen
WITH activityKey,
         count(DISTINCT seed) AS numSeeds,
         sum(CASE WHEN lineageLen = 0 THEN 1 ELSE 0 END) AS len0,
         sum(CASE WHEN lineageLen = 1 THEN 1 ELSE 0 END) AS len1,
         sum(CASE WHEN lineageLen = 2 THEN 1 ELSE 0 END) AS len2,
         sum(CASE WHEN lineageLen = 3 THEN 1 ELSE 0 END) AS len3,
         sum(CASE WHEN lineageLen = 4 THEN 1 ELSE 0 END) AS len4,
         sum(CASE WHEN lineageLen >= 5 THEN 1 ELSE 0 END) AS len5plus

RETURN activityKey AS seActivity,
             numSeeds AS totalModels,
             len0 AS len0Models,
             len1 AS len1Models,
             len2 AS len2Models,
             len3 AS len3Models,
             len4 AS len4Models,
             len5plus AS len5PlusModels,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len0) / numSeeds END AS share0,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len1) / numSeeds END AS share1,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len2) / numSeeds END AS share2,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len3) / numSeeds END AS share3,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len4) / numSeeds END AS share4,
             CASE WHEN numSeeds = 0 THEN 0.0 ELSE toFloat(len5plus) / numSeeds END AS share5plus
ORDER BY totalModels DESC
"""


MODEL_LINEAGE_BASE_MODELS_BY_TASK_QUERY = """
MATCH (t:SETask)
WITH coalesce(t.id, t.name, toString(id(t))) AS taskKey
MATCH (seed:Model)
WHERE taskKey IN coalesce(seed.seTaskGroups, [])

CALL {
    WITH seed
    MATCH p = (seed)-[r:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM*1..10]->(lm:Model)
    WHERE length(p) <= $max_lineage_depth
        AND NOT (lm)-[:IS_FINETUNED_FROM|IS_ADAPTER_OF|IS_MERGE_OF|IS_QUANTIZED_FROM]->()
        AND ALL(rel IN r WHERE rel.confidence IS NULL)
    RETURN max(length(p)) AS maxLen,
                 collect(DISTINCT coalesce(lm.id, lm.name, toString(id(lm)))) AS baseModelIds
}
WITH taskKey, seed,
         CASE WHEN maxLen IS NULL THEN 0 ELSE maxLen END AS lineageLen,
         baseModelIds

WITH taskKey,
         count(DISTINCT seed) AS numSeeds,
         avg(toFloat(lineageLen)) AS avgLineageLength,
         collect({seedId: id(seed), bases: baseModelIds}) AS perSeedLite

UNWIND perSeedLite AS ps
UNWIND ps.bases AS bm
WITH taskKey, numSeeds, avgLineageLength, bm,
         count(DISTINCT ps.seedId) AS seedsForBase

WITH taskKey, numSeeds, avgLineageLength,
         collect({baseModel: bm, seeds: seedsForBase}) AS rankedBases
WITH taskKey, numSeeds, avgLineageLength, rankedBases,
         [x IN rankedBases WHERE x.seeds > $popularity_threshold] AS popularBases,
         [x IN rankedBases WHERE x.seeds <= $popularity_threshold] AS notPopularBases

RETURN
    taskKey AS seTask,
    numSeeds,
    avgLineageLength,
    size(rankedBases) AS numBaseModels,
    size(popularBases) AS numPopularBases,
    size(notPopularBases) AS numNotPopularBases,
    popularBases AS popularBaseModels,
    notPopularBases[0..5] AS topNotPopularBaseModels,
    [x IN rankedBases | x.baseModel] AS allBaseModels
ORDER BY avgLineageLength DESC
"""