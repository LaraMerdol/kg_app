SUCCESSFUL_MODELS_TASK_BENCHMARK_COMPARISON_QUERY = """
MATCH (task:SETask)
WITH task
ORDER BY toLower(coalesce(task.label, task.name, task.id, toString(id(task))))
LIMIT toInteger(coalesce($task_limit, 10000))
CALL {
    WITH task
    MATCH (task)<-[:SUITABLE_FOR]-(model:Model)
    MATCH (model)-[evaluated:EVALUATED_ON]->(benchmark:Benchmark)
    WITH
        coalesce(task.label, task.name, task.id, toString(id(task))) AS task_name,
        coalesce(benchmark.name, benchmark.id, toString(id(benchmark))) AS benchmark_name,
        evaluated.metric AS metric,
        model,
        toFloat(coalesce(evaluated.score, 0)) AS score,
        toInteger(coalesce(model.likes, 0)) AS popularity
    WHERE metric IS NOT NULL
    WITH task_name, benchmark_name, metric, model, score, popularity
    ORDER BY popularity DESC,
             score DESC,
             toLower(coalesce(model.name, model.id, toString(id(model))))
    WITH
        task_name,
        benchmark_name,
        metric,
        collect({
            modelName: coalesce(model.name, model.id, toString(id(model))),
            modelId: coalesce(model.id, model.name, toString(id(model))),
            score: score,
            popularity: popularity
        }) AS models
    WHERE size(models) > 1
    RETURN
        task_name AS TaskName,
        benchmark_name AS BenchmarkName,
        metric AS Metric,
        size(models) AS ModelCount,
        models AS Models
}
RETURN TaskName,
       BenchmarkName,
       Metric,
       ModelCount,
       Models
ORDER BY toLower(TaskName), toLower(BenchmarkName), toLower(Metric)
"""