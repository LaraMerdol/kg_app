SOCIAL_COMMUNITY_COUNTS_QUERY = """
MATCH (t:SETask)
WITH t
ORDER BY toLower(coalesce(t.id, t.name, toString(id(t))))
LIMIT toInteger(coalesce($task_limit, 25))

OPTIONAL MATCH (m_root:Model)-[:SUITABLE_FOR]->(t)
WITH t,
     count(DISTINCT m_root) AS numModels,
     collect(DISTINCT m_root) AS task_models

CALL {
    WITH t
    OPTIONAL MATCH (t)-[:USED_FOR]-(a:SEActivity)
    WITH collect(DISTINCT coalesce(a.id, a.name, toString(id(a)))) AS activities
    RETURN CASE WHEN size(activities) = 0 THEN ['Unmapped'] ELSE activities END AS seActivities
}
CALL {
    WITH task_models
    UNWIND CASE WHEN size(task_models) = 0 THEN [NULL] ELSE task_models END AS m
    OPTIONAL MATCH (m)-[:TRAINED_ON]->(d:Dataset)
    RETURN count(DISTINCT d) AS numDatasets
}
CALL {
    WITH task_models
    UNWIND CASE WHEN size(task_models) = 0 THEN [NULL] ELSE task_models END AS m
    OPTIONAL MATCH (m)-[:CITES]->(p:Paper)
    RETURN count(DISTINCT p) AS numPapers
}
CALL {
    WITH task_models
    UNWIND CASE WHEN size(task_models) = 0 THEN [NULL] ELSE task_models END AS m
    OPTIONAL MATCH (m)-[:EVALUATED_ON]->(b:Benchmark)
    RETURN count(DISTINCT b) AS numBenchmarks
}
CALL {
    WITH task_models
    UNWIND CASE WHEN size(task_models) = 0 THEN [NULL] ELSE task_models END AS m
    WITH m WHERE m IS NOT NULL
    OPTIONAL MATCH (m)<-[:PUBLISHED]-(owner)
    WITH m,
         CASE WHEN owner:User THEN true ELSE false END AS isUser,
         CASE WHEN owner:Organization THEN true ELSE false END AS isOrg
    RETURN
        count(DISTINCT CASE WHEN isUser THEN m END) AS numModelsOwnedByUsers,
        count(DISTINCT CASE WHEN isOrg THEN m END) AS numModelsOwnedByOrganizations
}
CALL {
    WITH task_models, numModels
    WITH task_models AS models, numModels AS taskModelCount
    CALL {
        WITH models
        UNWIND CASE WHEN size(models) = 0 THEN [NULL] ELSE models END AS m
        OPTIONAL MATCH (u:User)-[:PUBLISHED]->(m)
        WITH u, count(DISTINCT m) AS modelCount
        WHERE u IS NOT NULL
        RETURN collect({
            contributor: coalesce(u.username, u.fullname, u.id, toString(id(u))),
            contributorType: 'User',
            modelCount: modelCount
        }) AS userContributors
    }
    CALL {
        WITH models
        UNWIND CASE WHEN size(models) = 0 THEN [NULL] ELSE models END AS m
        OPTIONAL MATCH (org:Organization)-[:PUBLISHED]->(m)
        WITH org, count(DISTINCT m) AS modelCount
        WHERE org IS NOT NULL
        RETURN collect({
            contributor: coalesce(org.id, org.name, toString(id(org))),
            contributorType: 'Organization',
            modelCount: modelCount
        }) AS orgContributors
    }
    WITH taskModelCount, (userContributors + orgContributors) AS contributors
    UNWIND contributors AS contributor_row
    WITH taskModelCount, contributor_row
    ORDER BY contributor_row.modelCount DESC,
             toLower(contributor_row.contributor),
             contributor_row.contributorType
    WITH taskModelCount, collect(contributor_row) AS rankedContributors
    RETURN
        CASE WHEN size(rankedContributors) = 0 THEN '' ELSE rankedContributors[0].contributor END AS topModelContributor,
        CASE WHEN size(rankedContributors) = 0 THEN '' ELSE rankedContributors[0].contributorType END AS topModelContributorType,
        CASE WHEN size(rankedContributors) = 0 THEN 0 ELSE toInteger(rankedContributors[0].modelCount) END AS topModelContributorModelCount,
        CASE
            WHEN taskModelCount = 0 OR size(rankedContributors) = 0 THEN 0.0
            ELSE round(10000.0 * toFloat(rankedContributors[0].modelCount) / toFloat(taskModelCount)) / 10000.0
        END AS modelContributorBusFactorRatio
}
CALL {
    WITH task_models
    UNWIND CASE WHEN size(task_models) = 0 THEN [NULL] ELSE task_models END AS m
    WITH m WHERE m IS NOT NULL
    WITH coalesce(m.id, m.name, toString(id(m))) AS model_id,
         toInteger(coalesce(m.downloads, 0)) AS downloads
    ORDER BY downloads DESC, toLower(model_id)
    RETURN
        coalesce(head(collect(model_id)), '') AS mostDownloadedModel,
        toInteger(coalesce(head(collect(downloads)), 0)) AS mostDownloadedModelDownloads
}
CALL {
    WITH task_models
    UNWIND CASE WHEN size(task_models) = 0 THEN [NULL] ELSE task_models END AS m
    WITH m WHERE m IS NOT NULL
    WITH coalesce(m.id, m.name, toString(id(m))) AS model_id,
         toInteger(coalesce(m.likes, 0)) AS likes
    ORDER BY likes DESC, toLower(model_id)
    RETURN
        coalesce(head(collect(model_id)), '') AS mostLikedModel,
        toInteger(coalesce(head(collect(likes)), 0)) AS mostLikedModelLikes
}
RETURN coalesce(t.id, t.name, toString(id(t))) AS seTask,
       seActivities,
       numModels,
       numDatasets,
       numPapers,
       numBenchmarks,
       numModelsOwnedByUsers,
       numModelsOwnedByOrganizations,
       topModelContributor,
       topModelContributorType,
       topModelContributorModelCount,
       modelContributorBusFactorRatio,
       mostDownloadedModel,
       mostDownloadedModelDownloads,
       mostLikedModel,
       mostLikedModelLikes
ORDER BY toLower(coalesce(t.id, t.name, toString(id(t))))
"""

SOCIAL_COMMUNITY_MODEL_LIKES_BY_OWNER_QUERY = """
MATCH (m:SEModel)
WHERE m.likes IS NOT NULL
MATCH (m)<-[:PUBLISHED]-(owner)
WHERE owner:User OR owner:Organization
RETURN
    coalesce(m.id, m.name, toString(id(m))) AS model_id,
    CASE
        WHEN owner:User THEN 'User'
        WHEN owner:Organization THEN 'Organization'
        ELSE 'Unknown'
    END AS owner_type,
    toFloat(coalesce(m.likes, 0)) AS likes
ORDER BY likes DESC, owner_type, model_id
"""

SOCIAL_COMMUNITY_MODEL_LIKES_BY_ORG_TYPE_QUERY = """
MATCH (m:SEModel)
WHERE m.likes IS NOT NULL
MATCH (m)<-[:PUBLISHED]-(org:Organization)
WITH
    coalesce(m.id, m.name, toString(id(m))) AS model_id,
    toLower(trim(coalesce(org.organization_type, org.org_type, org.organizationType, org.type, ''))) AS org_type,
    toFloat(coalesce(m.likes, 0)) AS likes
RETURN
    model_id,
    CASE
        WHEN org_type = 'company' THEN 'Industry'
        WHEN org_type IN ['university', 'classroom'] THEN 'Academic'
        WHEN org_type IN ['community', 'organization', '', 'non-profit', 'government'] THEN 'Non-Profit'
        ELSE 'Other'
    END AS organization_type,
    likes
"""

SOCIAL_COMMUNITY_NETWORK_QUERY = """
MATCH (t:SETask)
WITH t
ORDER BY toLower(coalesce(t.id, t.name, toString(id(t))))
LIMIT toInteger(coalesce($task_limit, 25))

OPTIONAL MATCH (m_root:SEModel)-[:SUITABLE_FOR]->(t)
WITH t, collect(DISTINCT m_root) AS task_models

CALL {
    WITH task_models
    UNWIND CASE WHEN size(task_models) = 0 THEN [NULL] ELSE task_models END AS m
    WITH m WHERE m IS NOT NULL
    OPTIONAL MATCH (m)<-[:PUBLISHED]-(u:User)
    OPTIONAL MATCH (m)<-[:PUBLISHED]-(org:Organization)
    RETURN
        count(DISTINCT u) AS numUsers,
        count(DISTINCT org) AS numOrganizations,
        (count(DISTINCT u) + count(DISTINCT org)) AS numHubContributors,
        count(DISTINCT CASE WHEN coalesce(u.isPro, false) = true THEN u END) AS numProHubContributors
}

RETURN
    coalesce(t.id, t.name, toString(id(t))) AS seTask,
    [] AS seActivities,
    numUsers,
    numOrganizations,
    numHubContributors,
    numProHubContributors,
    CASE WHEN numHubContributors = 0 THEN 0.0 ELSE toFloat(numProHubContributors) / toFloat(numHubContributors) END AS proHubContributorRatio
ORDER BY toLower(coalesce(t.id, t.name, toString(id(t))))
"""

SOCIAL_COMMUNITY_SUBGRAPH_QUERY = """
// Returns a simple list of model-publisher pairs for a task (by seTask string)
MATCH (t:SETask)
WHERE coalesce(t.id, t.name, toString(id(t))) = $seTask
OPTIONAL MATCH (m:SEModel)-[:SUITABLE_FOR]->(t)
OPTIONAL MATCH (m)<-[:PUBLISHED]-(pub)
RETURN coalesce(m.id, m.name, toString(id(m))) AS model_id,
       CASE WHEN pub:User THEN coalesce(pub.username, pub.fullname, toString(id(pub)))
            WHEN pub:Organization THEN coalesce(pub.name, toString(id(pub)))
            ELSE '' END AS publisher
"""