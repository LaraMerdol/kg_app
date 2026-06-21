# KG App

A Streamlit app for exploring a Neo4j-backed knowledge graph of SE tasks, models, datasets, papers, benchmarks, collections, and spaces.

## What this project does

The app provides multiple analysis views for the graph data:

- Artifact Ecosystem
- Social Community
- Model Lineage
- Query Explorer
- Cache viewer

It also includes a separate script for computing the Ecosystem Maturity Index (EMI) across SE activities.

## Requirements

You need:

- Python 3.10+ recommended
- A running Neo4j instance
- The Python packages used by the app:
  - `streamlit`
  - `neo4j`
  - `pandas`
  - `numpy`
  - `plotly`

The easiest way to install them is with the included [requirements.txt](requirements.txt).

If you are using the bundled virtual environment, activate it before running anything.

## Setup

From PowerShell in the project root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

If the dependencies are not installed yet, install them into your environment with pip:

```powershell
pip install -r requirements.txt
```

## Run the Streamlit app

Start the main app from the project root:

```powershell
streamlit run main.py
```

You can also run the small wrapper script if you prefer:

```powershell
streamlit run neo4j_app.py
```

Streamlit usually opens at:

```text
http://localhost:8501
```

## Run the EMI script

The file [emi_se_activity_maturity.py](emi_se_activity_maturity.py) is a separate command-line script for computing EMI results directly against Neo4j.

Example:

```powershell
python emi_se_activity_maturity.py --help
```

Use `--help` first to see the supported arguments for your local version.

## Neo4j connection settings

The app uses these defaults from [config.py](config.py):

- URI: `bolt://localhost:7687`
- Username: `neo4j`
- Database: `neo4j`

The password is entered in the Streamlit sidebar at runtime.

If your Neo4j server uses different connection details, change them in the app sidebar before loading data.

## Cache behavior

The app uses a local cache file named [streamlit_query_cache.json](streamlit_query_cache.json).

Behavior:

- Cached query results are reused when you click the cache-first load actions.
- If Neo4j is offline and cached data exists, the app falls back to the cache.
- The Cache page in the UI shows stored query snapshots.

## Project structure

- [main.py](main.py) - Streamlit entrypoint for the app
- [neo4j_app.py](neo4j_app.py) - Thin wrapper that forwards to `main()`
- [config.py](config.py) - Default Neo4j and cache settings
- [data.py](data.py) - Query execution, caching, and fallback logic
- [pages_modules/](pages_modules) - Streamlit page renderers
- [queries/](queries) - Cypher query definitions
- [visualization.py](visualization.py) - Graph visualization helpers
- [emi_se_activity_maturity.py](emi_se_activity_maturity.py) - EMI computation script

## Common issues

If the app opens but no data loads:

- Make sure Neo4j is running.
- Verify the URI, username, password, and database values in the sidebar.
- Check that the graph contains the labels and relationships expected by the queries.

If Streamlit does not start:

- Confirm your virtual environment is activated.
- Confirm the required packages are installed in that environment.
- Run `python --version` to verify you are using the expected interpreter.

## Notes

The app is designed to work both with live Neo4j connectivity and with cached query results where available.
