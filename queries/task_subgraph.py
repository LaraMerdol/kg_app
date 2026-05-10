TASK_SUBGRAPH_QUERY = """
MATCH (t:SETask {id: $task_name})
OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
WITH t, collect(DISTINCT m) AS models_raw
WITH t, models_raw[0..$subgraph_model_limit] AS models
OPTIONAL MATCH (m2:Model)-[:SUITABLE_FOR]->(t)
WHERE coalesce(m2.id, m2.name, toString(id(m2))) IN [x IN models WHERE x IS NOT NULL | coalesce(x.id, x.name, toString(id(x)))]
OPTIONAL MATCH (m2)-[:TRAINED_ON]->(d:Dataset)
OPTIONAL MATCH (m2)-[:CITES]->(p:Paper)
OPTIONAL MATCH (m2)-[:EVALUATED_ON]->(b:Benchmark)
OPTIONAL MATCH (c:Collection)-[:CONTAINS]->(m2)
OPTIONAL MATCH (s:Space)-[:USES_MODEL]->(m2)
OPTIONAL MATCH (s2:Space)-[:USES_DATASET]->(d)

WITH
    t,
    collect(DISTINCT m2) AS models_nodes,
    collect(DISTINCT d) AS dataset_nodes,
    collect(DISTINCT p) AS paper_nodes,
    collect(DISTINCT b) AS benchmark_nodes,
    collect(DISTINCT c) AS collection_nodes,
    collect(DISTINCT s) AS space_model_nodes,
    collect(DISTINCT s2) AS space_dataset_nodes,
    collect(DISTINCT {
        source: coalesce(m2.id, m2.name, toString(id(m2))),
        target: coalesce(t.id, t.name, toString(id(t))),
        type: 'SUITABLE_FOR'
    }) +
    collect(DISTINCT {
        source: coalesce(m2.id, m2.name, toString(id(m2))),
        target: coalesce(d.id, d.name, toString(id(d))),
        type: 'TRAINED_ON'
    }) +
    collect(DISTINCT {
        source: coalesce(m2.id, m2.name, toString(id(m2))),
        target: coalesce(p.id, p.name, toString(id(p))),
        type: 'CITES'
    }) +
    collect(DISTINCT {
        source: coalesce(m2.id, m2.name, toString(id(m2))),
        target: coalesce(b.id, b.name, toString(id(b))),
        type: 'EVALUATED_ON'
    }) +
    collect(DISTINCT {
        source: coalesce(c.id, c.name, toString(id(c))),
        target: coalesce(m2.id, m2.name, toString(id(m2))),
        type: 'CONTAINS'
    }) +
    collect(DISTINCT {
        source: coalesce(s.id, s.name, toString(id(s))),
        target: coalesce(m2.id, m2.name, toString(id(m2))),
        type: 'USES_MODEL'
    }) +
    collect(DISTINCT {
        source: coalesce(s2.id, s2.name, toString(id(s2))),
        target: coalesce(d.id, d.name, toString(id(d))),
        type: 'USES_DATASET'
    }) AS raw_relationships

WITH
    [t] + models_nodes + dataset_nodes + paper_nodes + benchmark_nodes + collection_nodes + space_model_nodes + space_dataset_nodes AS raw_nodes,
    raw_relationships

RETURN
    [n IN raw_nodes
     WHERE n IS NOT NULL
     | {
         id: coalesce(n.id, n.name, toString(id(n))),
         label: head(labels(n)),
         title: coalesce(n.id, n.name, toString(id(n)))
     }] AS nodes,
    [r IN raw_relationships
     WHERE r.source IS NOT NULL AND r.target IS NOT NULL
     | r] AS relationships
"""


TASK_PAIR_SUBGRAPH_QUERY = """
MATCH (t:SETask)
WHERE t.id IN [$task1, $task2]
WITH collect(DISTINCT t) AS tasks
UNWIND tasks AS t
OPTIONAL MATCH (m:Model)-[:SUITABLE_FOR]->(t)
WITH tasks, collect(DISTINCT m) AS models_raw
WITH tasks, models_raw[0..$subgraph_model_limit] AS models
UNWIND tasks AS t2
OPTIONAL MATCH (m2:Model)-[:SUITABLE_FOR]->(t2)
WHERE coalesce(m2.id, m2.name, toString(id(m2))) IN [x IN models WHERE x IS NOT NULL | coalesce(x.id, x.name, toString(id(x)))]
OPTIONAL MATCH (m2)-[:TRAINED_ON]->(d:Dataset)
OPTIONAL MATCH (m2)-[:CITES]->(p:Paper)
OPTIONAL MATCH (m2)-[:EVALUATED_ON]->(b:Benchmark)
OPTIONAL MATCH (c:Collection)-[:CONTAINS]->(m2)
OPTIONAL MATCH (s:Space)-[:USES_MODEL]->(m2)
OPTIONAL MATCH (s2:Space)-[:USES_DATASET]->(d)

WITH
    tasks,
    collect(DISTINCT m2) AS models_nodes,
    collect(DISTINCT d) AS dataset_nodes,
    collect(DISTINCT p) AS paper_nodes,
    collect(DISTINCT b) AS benchmark_nodes,
    collect(DISTINCT c) AS collection_nodes,
    collect(DISTINCT s) AS space_model_nodes,
    collect(DISTINCT s2) AS space_dataset_nodes,
    collect(DISTINCT {
        source: coalesce(m2.id, m2.name, toString(id(m2))),
        target: coalesce(t2.id, t2.name, toString(id(t2))),
        type: 'SUITABLE_FOR'
    }) +
    collect(DISTINCT {
        source: coalesce(m2.id, m2.name, toString(id(m2))),
        target: coalesce(d.id, d.name, toString(id(d))),
        type: 'TRAINED_ON'
    }) +
    collect(DISTINCT {
        source: coalesce(m2.id, m2.name, toString(id(m2))),
        target: coalesce(p.id, p.name, toString(id(p))),
        type: 'CITES'
    }) +
    collect(DISTINCT {
        source: coalesce(m2.id, m2.name, toString(id(m2))),
        target: coalesce(b.id, b.name, toString(id(b))),
        type: 'EVALUATED_ON'
    }) +
    collect(DISTINCT {
        source: coalesce(c.id, c.name, toString(id(c))),
        target: coalesce(m2.id, m2.name, toString(id(m2))),
        type: 'CONTAINS'
    }) +
    collect(DISTINCT {
        source: coalesce(s.id, s.name, toString(id(s))),
        target: coalesce(m2.id, m2.name, toString(id(m2))),
        type: 'USES_MODEL'
    }) +
    collect(DISTINCT {
        source: coalesce(s2.id, s2.name, toString(id(s2))),
        target: coalesce(d.id, d.name, toString(id(d))),
        type: 'USES_DATASET'
    }) AS raw_relationships

WITH
    tasks + models_nodes + dataset_nodes + paper_nodes + benchmark_nodes + collection_nodes + space_model_nodes + space_dataset_nodes AS raw_nodes,
    raw_relationships

RETURN
    [n IN raw_nodes
     WHERE n IS NOT NULL
     | {
         id: coalesce(n.id, n.name, toString(id(n))),
         label: head(labels(n)),
         title: coalesce(n.id, n.name, toString(id(n)))
     }] AS nodes,
    [r IN raw_relationships
     WHERE r.source IS NOT NULL AND r.target IS NOT NULL
     | r] AS relationships
LIMIT 1
"""
