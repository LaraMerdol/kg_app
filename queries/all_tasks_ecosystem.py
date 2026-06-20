ALL_TASKS_ECOSYSTEM_QUERY = """
MATCH (t:SETask)
CALL {
    WITH t
    OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    RETURN count(DISTINCT m) AS numModels
}
CALL {
    WITH t
    OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    RETURN count(DISTINCT d) AS numDatasets
}
CALL {
    WITH t
    OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    WITH m
    WHERE m IS NOT NULL AND EXISTS { (m)-[:TRAINED_ON]->(:Dataset) }
    RETURN count(DISTINCT m) AS numModelsWithDataset
}
CALL {
    WITH t
    OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (m)-[:CITES]->(p_model:Paper)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    OPTIONAL MATCH (p_data:Paper)-[:CITES]->(d)
    WITH collect(DISTINCT p_model) + collect(DISTINCT p_data) AS paper_nodes
    UNWIND paper_nodes AS p
    WITH p
    WHERE p IS NOT NULL
    RETURN count(DISTINCT p) AS numPapers
}
CALL {
    WITH t
    OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (m)-[:EVALUATED_ON]->(b:Benchmark)
    RETURN count(DISTINCT b) AS numBenchmarks
}
CALL {
    WITH t
    OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    WITH m
    WHERE m IS NOT NULL AND EXISTS { (m)-[:EVALUATED_ON]->(:Benchmark) }
    RETURN count(DISTINCT m) AS numModelsWithBenchmark
}
CALL {
    WITH t
    OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (c_model:Collection)-[:CONTAINS]->(m)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    OPTIONAL MATCH (c_data:Collection)-[:CONTAINS]->(d)
    WITH collect(DISTINCT c_model) + collect(DISTINCT c_data) AS collection_nodes
    UNWIND collection_nodes AS c
    WITH c
    WHERE c IS NOT NULL
    RETURN count(DISTINCT c) AS numCollections
}
CALL {
    WITH t
    OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    WITH m
    WHERE m IS NOT NULL AND (
        EXISTS { (:Collection)-[:CONTAINS]->(m) }
        OR EXISTS {
            (m)-[:TRAINED_ON]->(:Dataset)<-[:CONTAINS]-(:Collection)
        }
    )
    RETURN count(DISTINCT m) AS numModelsWithCollection
}
CALL {
    WITH t
    OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (s_model:Space)-[:USES_MODEL]->(m)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    OPTIONAL MATCH (s_data:Space)-[:USES_DATASET]->(d)
    WITH collect(DISTINCT s_model) + collect(DISTINCT s_data) AS space_nodes
    UNWIND space_nodes AS s
    WITH s
    WHERE s IS NOT NULL
    RETURN count(DISTINCT s) AS numSpaces
}
CALL {
    WITH t
    OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    WITH m
    WHERE m IS NOT NULL AND (
        EXISTS { (:Space)-[:USES_MODEL]->(m) }
        OR EXISTS {
            (m)-[:TRAINED_ON]->(:Dataset)<-[:USES_DATASET]-(:Space)
        }
    )
    RETURN count(DISTINCT m) AS numModelsWithSpace
}

RETURN coalesce(t.id, t.name, toString(id(t))) AS seTask,
             numModels,
             numModelsWithDataset,
             numModelsWithCollection,
             numModelsWithSpace,
             numModelsWithBenchmark,
             numDatasets,
             numPapers,
             numBenchmarks,
             numCollections,
             numSpaces
ORDER BY toLower(coalesce(t.id, t.name, toString(id(t))))
"""


ALL_TASKS_ECOSYSTEM_RATIO_QUERY = """
CALL {
    MATCH (m:SEModel)
    RETURN count(DISTINCT m) AS totalModels
}
CALL {
    MATCH (m:SEModel)-[:TRAINED_ON]->(d:Dataset)
    RETURN count(DISTINCT d) AS totalDatasets
}
CALL {
    OPTIONAL MATCH (m:SEModel)-[:CITES]->(p_model:Paper)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    OPTIONAL MATCH (p_data:Paper)-[:CITES]->(d)
    WITH collect(DISTINCT p_model) + collect(DISTINCT p_data) AS paper_nodes
    UNWIND paper_nodes AS p
    WITH p
    WHERE p IS NOT NULL
    RETURN count(DISTINCT p) AS totalPapers
}
CALL {
    MATCH (m:SEModel)-[:EVALUATED_ON]->(b:Benchmark)
    RETURN count(DISTINCT b) AS totalBenchmarks
}
CALL {
    MATCH (m:SEModel)
    OPTIONAL MATCH (c_model:Collection)-[:CONTAINS]->(m)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    OPTIONAL MATCH (c_data:Collection)-[:CONTAINS]->(d)
    WITH collect(DISTINCT c_model) + collect(DISTINCT c_data) AS collection_nodes
    UNWIND collection_nodes AS c
    WITH c
    WHERE c IS NOT NULL
    RETURN count(DISTINCT c) AS totalCollections
}
CALL {
    MATCH (m:SEModel)
    OPTIONAL MATCH (s_model:Space)-[:USES_MODEL]->(m)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    OPTIONAL MATCH (s_data:Space)-[:USES_DATASET]->(d)
    WITH collect(DISTINCT s_model) + collect(DISTINCT s_data) AS space_nodes
    UNWIND space_nodes AS s
    WITH s
    WHERE s IS NOT NULL
    RETURN count(DISTINCT s) AS totalSpaces
}
MATCH (t:SETask)
WITH t, coalesce(t.id, t.name, toString(id(t))) AS taskId,
     totalModels, totalDatasets, totalPapers, totalBenchmarks, totalCollections, totalSpaces
CALL {
    WITH t, taskId
    OPTIONAL MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)
    RETURN count(DISTINCT m) AS numModels
}
CALL {
    WITH t, taskId
    OPTIONAL MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    RETURN count(DISTINCT d) AS numDatasets
}
CALL {
    WITH t, taskId
    OPTIONAL MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (m)-[:CITES]->(p_model:Paper)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    OPTIONAL MATCH (p_data:Paper)-[:CITES]->(d)
    WITH collect(DISTINCT p_model) + collect(DISTINCT p_data) AS paper_nodes
    UNWIND paper_nodes AS p
    WITH p
    WHERE p IS NOT NULL
    RETURN count(DISTINCT p) AS numPapers
}
CALL {
    WITH t, taskId
    OPTIONAL MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (m)-[:EVALUATED_ON]->(b:Benchmark)
    RETURN count(DISTINCT b) AS numBenchmarks
}
CALL {
    WITH t, taskId
    OPTIONAL MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (c_model:Collection)-[:CONTAINS]->(m)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    OPTIONAL MATCH (c_data:Collection)-[:CONTAINS]->(d)
    WITH collect(DISTINCT c_model) + collect(DISTINCT c_data) AS collection_nodes
    UNWIND collection_nodes AS c
    WITH c
    WHERE c IS NOT NULL
    RETURN count(DISTINCT c) AS numCollections
}
CALL {
    WITH t, taskId
    OPTIONAL MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (s_model:Space)-[:USES_MODEL]->(m)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    OPTIONAL MATCH (s_data:Space)-[:USES_DATASET]->(d)
    WITH collect(DISTINCT s_model) + collect(DISTINCT s_data) AS space_nodes
    UNWIND space_nodes AS s
    WITH s
    WHERE s IS NOT NULL
    RETURN count(DISTINCT s) AS numSpaces
}
RETURN
    taskId AS seTask,
    numModels,
    totalModels,
    CASE WHEN totalModels = 0 THEN 0.0 ELSE toFloat(numModels) / toFloat(totalModels) END AS modelSharePct,
    numDatasets,
    totalDatasets,
    CASE WHEN totalDatasets = 0 THEN 0.0 ELSE toFloat(numDatasets) / toFloat(totalDatasets) END AS datasetSharePct,
    numPapers,
    totalPapers,
    CASE WHEN totalPapers = 0 THEN 0.0 ELSE toFloat(numPapers) / toFloat(totalPapers) END AS paperSharePct,
    numBenchmarks,
    totalBenchmarks,
    CASE WHEN totalBenchmarks = 0 THEN 0.0 ELSE toFloat(numBenchmarks) / toFloat(totalBenchmarks) END AS benchmarkSharePct,
    numCollections,
    totalCollections,
    CASE WHEN totalCollections = 0 THEN 0.0 ELSE toFloat(numCollections) / toFloat(totalCollections) END AS collectionSharePct,
    numSpaces,
    totalSpaces,
    CASE WHEN totalSpaces = 0 THEN 0.0 ELSE toFloat(numSpaces) / toFloat(totalSpaces) END AS spaceSharePct
ORDER BY toLower(taskId)
"""


ALL_TASKS_MOST_USED_AND_LIKED_DATASETS_QUERY = """
MATCH (t:SETask)
WITH t, coalesce(t.id, t.name, toString(id(t))) AS taskId
CALL {
    WITH t
    MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)-[:USED_FOR]-(a:SEActivity)
    MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    WHERE d.likes IS NOT NULL
    WITH coalesce(d.id, d.name, toString(id(d))) AS datasetId, count(DISTINCT m) AS linkedModelCount
    ORDER BY linkedModelCount DESC, toLower(datasetId)
    RETURN collect(datasetId)[0..3] AS top3MostUsedDatasets, collect(linkedModelCount)[0..3] AS top3MostUsedCounts
}
CALL {
    WITH t
    MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)-[:USED_FOR]-(a:SEActivity)
    MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    WHERE d.likes IS NOT NULL
    WITH coalesce(d.id, d.name, toString(id(d))) AS datasetId, toInteger(coalesce(d.likes, 0)) AS datasetLikes
    ORDER BY datasetLikes DESC, toLower(datasetId)
    RETURN collect( distinct datasetId)[0..3] AS top3MostLikedDatasets, collect(datasetLikes)[0..3] AS top3MostLikedLikes
}

WITH t, taskId,
     top3MostUsedDatasets, top3MostUsedCounts,
     top3MostLikedDatasets, top3MostLikedLikes
WITH t, taskId,
     top3MostUsedDatasets, top3MostUsedCounts,
     top3MostLikedDatasets, top3MostLikedLikes,
     coalesce(head(top3MostUsedDatasets), "") AS mostUsedDataset,
     toInteger(coalesce(head(top3MostUsedCounts), 0)) AS mostUsedDatasetCount,
     coalesce(head(top3MostLikedDatasets), "") AS mostLikedDataset,
     toInteger(coalesce(head(top3MostLikedLikes), 0)) AS mostLikedDatasetLikes
CALL {
    WITH t, mostUsedDataset
    MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)-[:USED_FOR]-(a:SEActivity)
    MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    WHERE d.likes IS NOT NULL
    WITH mostUsedDataset, coalesce(d.id, d.name, toString(id(d))) AS datasetId, toInteger(coalesce(d.likes, 0)) AS datasetLikes
    WHERE datasetId = mostUsedDataset
    RETURN toInteger(coalesce(max(datasetLikes), 0)) AS mostUsedDatasetLikes
}
CALL {
    WITH t, mostLikedDataset
    MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)-[:USED_FOR]-(a:SEActivity)
    MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    WHERE d.likes IS NOT NULL
    WITH mostLikedDataset, coalesce(d.id, d.name, toString(id(d))) AS datasetId, count(DISTINCT m) AS linkedModelCount
    WHERE datasetId = mostLikedDataset
    RETURN toInteger(coalesce(max(linkedModelCount), 0)) AS mostLikedDatasetUsedCount
}
RETURN
    taskId AS seTask,
    mostUsedDataset,
    mostUsedDatasetCount,
    top3MostUsedDatasets,
    top3MostUsedCounts,
    mostUsedDatasetLikes,
    mostLikedDataset,
    mostLikedDatasetLikes,
    top3MostLikedDatasets,
    top3MostLikedLikes,
    mostLikedDatasetUsedCount
ORDER BY toLower(taskId)
"""


ALL_TASKS_SEMODEL_DATASET_PROPERTIES_QUERY = """
MATCH (m:SEModel)-[:SUITABLE_FOR]->(t:SETask)
OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
WITH
    coalesce(d.id, d.name, toString(id(d))) AS datasetId,
    coalesce(d.name, d.id, toString(id(d))) AS datasetName,
    coalesce(d.`n.modalities`, d.modalities, d.modality, d.n_modalities, []) AS modalities,
    coalesce(d.`n.formats`, d.formats, d.format, d.n_formats, []) AS formats,
    count(DISTINCT m) AS linkedModels,
    collect(DISTINCT coalesce(t.id, t.name, toString(id(t)))) AS tasks
WHERE datasetId IS NOT NULL AND datasetId <> ''
RETURN
    datasetId,
    datasetName,
    modalities,
    formats,
    linkedModels,
    size([task IN tasks WHERE task IS NOT NULL AND task <> '']) AS taskCount,
    [task IN tasks WHERE task IS NOT NULL AND task <> ''] AS tasks
ORDER BY linkedModels DESC, taskCount DESC, toLower(datasetId)
LIMIT toInteger(coalesce($dataset_limit, 200))
"""


ALL_TASKS_DATASET_MODULE_DISTRIBUTION_QUERY = """
MATCH (t:SETask)
WITH coalesce(t.id, t.name, toString(id(t))) AS seTask, t
CALL {
    WITH t
    OPTIONAL MATCH (t)-[:USED_FOR]-(a:SEActivity)
    WITH collect(DISTINCT coalesce(a.id, a.name, toString(id(a)))) AS activities
    RETURN CASE WHEN size(activities) = 0 THEN ['Unmapped'] ELSE activities END AS seActivities
}
CALL {
    WITH t
    OPTIONAL MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    WITH coalesce(d.`n.formats`, d.formats, d.format, d.n_formats, []) AS formatValues
    UNWIND CASE WHEN size(formatValues) = 0 THEN [NULL] ELSE formatValues END AS formatValue
    WITH toString(formatValue) AS formatValue
    WHERE formatValue IS NOT NULL AND trim(formatValue) <> ''
    WITH formatValue, count(*) AS frequency
    ORDER BY frequency DESC, toLower(formatValue)
    RETURN
        coalesce(head(collect(formatValue)), '') AS mostUsedFormat,
        coalesce(head(collect(frequency)), 0) AS mostUsedFormatCount
}
CALL {
    WITH t
    OPTIONAL MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    WITH coalesce(d.`n.modalities`, d.modalities, d.modality, d.n_modalities, []) AS modalityValues
    UNWIND CASE WHEN size(modalityValues) = 0 THEN [NULL] ELSE modalityValues END AS modalityValue
    WITH toString(modalityValue) AS modalityValue
    WHERE modalityValue IS NOT NULL AND trim(modalityValue) <> ''
    WITH modalityValue, count(*) AS frequency
    ORDER BY frequency DESC, toLower(modalityValue)
    RETURN
        coalesce(head(collect(modalityValue)), '') AS mostUsedModality,
        coalesce(head(collect(frequency)), 0) AS mostUsedModalityCount
}
CALL {
    WITH t
    OPTIONAL MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    RETURN count(DISTINCT d) AS numDatasets
}
RETURN
    seTask,
    seActivities,
    numDatasets,
    mostUsedFormat,
    mostUsedFormatCount,
    mostUsedModality,
    mostUsedModalityCount
ORDER BY toLower(seTask)
"""
