TASK_ECOSYSTEM_QUERY = """
MATCH (t:SETask {id: $task_name})
MATCH (m:Model)-[:SUITABLE_FOR]->(t)

OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
OPTIONAL MATCH (m)-[:CITES]->(p:Paper)
OPTIONAL MATCH (m)-[:EVALUATED_ON]->(b:Benchmark)
OPTIONAL MATCH (c:Collection)-[:CONTAINS]->(m)
OPTIONAL MATCH (s:Space)-[:USES_MODEL]->(m)
OPTIONAL MATCH (s2:Space)-[:USES_DATASET]->(d)

CALL {
    WITH t
    MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    WITH d, count(DISTINCT m) AS score
    WHERE d IS NOT NULL
    WITH coalesce(d.id, d.name, toString(id(d))) AS dataset_id, score
    ORDER BY score DESC, dataset_id ASC
    RETURN
        head(collect(dataset_id)) AS mostUsedDataset,
        coalesce(head(collect(score)), 0) AS mostUsedDatasetCount
}
CALL {
    WITH t
    MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (m)-[:EVALUATED_ON]->(b:Benchmark)
    WITH b, count(DISTINCT m) AS score
    WHERE b IS NOT NULL
    WITH coalesce(b.id, b.name, toString(id(b))) AS benchmark_id, score
    ORDER BY score DESC, benchmark_id ASC
    RETURN
        head(collect(benchmark_id)) AS mostUsedBenchmark,
        coalesce(head(collect(score)), 0) AS mostUsedBenchmarkCount
}
CALL {
    WITH t
    MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (c_model:Collection)-[:CONTAINS]->(m)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d2:Dataset)
    OPTIONAL MATCH (c_data:Collection)-[:CONTAINS]->(d2)
    WITH m, (collect(DISTINCT c_model) + collect(DISTINCT c_data)) AS collections
    UNWIND collections AS c
    WITH c, count(DISTINCT m) AS score
    WHERE c IS NOT NULL
    WITH coalesce(c.id, c.name, toString(id(c))) AS collection_id, score
    ORDER BY score DESC, collection_id ASC
    RETURN
        head(collect(collection_id)) AS mostUsedCollection,
        coalesce(head(collect(score)), 0) AS mostUsedCollectionCount
}
CALL {
    WITH t
    MATCH (m:Model)-[:SUITABLE_FOR]->(t)
    OPTIONAL MATCH (s_model:Space)-[:USES_MODEL]->(m)
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d2:Dataset)
    OPTIONAL MATCH (s_data:Space)-[:USES_DATASET]->(d2)
    WITH m, (collect(DISTINCT s_model) + collect(DISTINCT s_data)) AS spaces
    UNWIND spaces AS s
    WITH s, count(DISTINCT m) AS score
    WHERE s IS NOT NULL
    WITH coalesce(s.id, s.name, toString(id(s))) AS space_id, score
    ORDER BY score DESC, space_id ASC
    RETURN
        head(collect(space_id)) AS mostUsedSpace,
        coalesce(head(collect(score)), 0) AS mostUsedSpaceCount
}

RETURN t.id AS seTask,
       count(DISTINCT m) AS numModels,
       count(DISTINCT d) AS numDatasets,
       count(DISTINCT p) AS numPapers,
       count(DISTINCT b) AS numBenchmarks,
       count(DISTINCT c) AS numCollections,
       count(DISTINCT s) AS numSpaces,
       count(DISTINCT s2) AS numSpacesUsingDatasets,
       coalesce(mostUsedDataset, "") AS mostUsedDataset,
       toInteger(coalesce(mostUsedDatasetCount, 0)) AS mostUsedDatasetCount,
       coalesce(mostUsedBenchmark, "") AS mostUsedBenchmark,
       toInteger(coalesce(mostUsedBenchmarkCount, 0)) AS mostUsedBenchmarkCount,
       coalesce(mostUsedCollection, "") AS mostUsedCollection,
       toInteger(coalesce(mostUsedCollectionCount, 0)) AS mostUsedCollectionCount,
       coalesce(mostUsedSpace, "") AS mostUsedSpace,
       toInteger(coalesce(mostUsedSpaceCount, 0)) AS mostUsedSpaceCount
"""
