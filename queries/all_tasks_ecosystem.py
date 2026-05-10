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
