# Building the dataset

The project starts from one table, `data/idealista18_listings.parquet`: every 2018 sale listing of Madrid, Barcelona and Valencia in idealista18, one per row. [`build_dataset.py`](../../build_dataset.py) builds it from its public source with one command, as an **ETL** (extract, transform, load) pipeline: a data-engineering task rather than a machine-learning one, and the step every machine-learning project depends on. These two notebooks run the same pipeline one step at a time, and explain and check each step; using the table doesn't require them. The table is not stored in the repository: running the script, or the notebooks, rebuilds it.

| Notebook | What it covers |
| --- | --- |
| [idealista18 and the .rda format](source_and_rda_format.ipynb) | Where the data comes from, its licence and its anonymisation; what an `.rda` file is, byte by byte; reading R objects from Python, including spatial (`sf`) objects and text encodings |
| [An ETL pipeline for idealista18](etl_pipeline.ipynb) | Extract the three cities; check the source against its documentation; descriptive names and explicit types; decoding coded columns; enrichment with each listing's neighbourhood (a point-in-polygon join); recomputing the source's own distances; a data-quality report; load to Parquet |

## Where ETL ends and modelling begins

The ETL stops at one line: a step belongs to it only if it learns nothing from the data and doesn't depend on how the data will be split for a model. Whatever is fitted to the data (a median, a list of categories, a cluster) is fitted later, on the training data only, inside the model's pipeline; the table is the same for every user, and each model builds what it needs from it. The same criterion, applied to every common preparation step: [Where data preparation ends and modelling begins](https://github.com/avidaldo/ai/blob/main/saa/data-preparation/where_preparation_ends.ipynb).

Here is where the steps of this project fall:

| Step | Where it belongs | In this project |
| --- | --- | --- |
| Extraction, descriptive names, types, decoded columns, one table for three cities | ETL: the pipeline | `.rda` → DataFrame; the redundant `geometry` column dropped; nullable integers |
| Data-quality rules | ETL *reports* them and keeps every row; modelling decides what to do | prices rounded to €1,000; construction years after 2018. The report travels with the table; whether a construction year of 2291 becomes a missing value is a modelling decision |
| Enrichment from fixed reference data | ETL: the pipeline | the neighbourhood of each listing; the distances to the centre and the metro, recomputed and checked against the source's |
| Imputation, scaling, encoding | modelling, fitted on the training data | filling a missing construction year; one-hot encoding the neighbourhood |
| Features fitted to the data | modelling, fitted on the training data | clusters of coordinates; a neighbourhood's average price |
| Features built from *other listings' prices* | modelling, with the most care: the highest risk of leakage, and the time order matters too | the average price per m² of nearby listings |
| Transforming the target | modelling | the logarithm of the price |

**The landmark distances show where harmonising stops.** Computing the distance from a listing to its city's main street is enrichment, so it is ETL. The three cities measure it to three different streets, so the table keeps three columns, `dist_castellana_km`, `dist_diagonal_km` and `dist_blasco_km`, each empty outside its city. Merging them into one "distance to the landmark" column would look like harmonising, but it would hide a difference of meaning. Whether a model trained in one city can use another city's landmark is a modelling question, not the ETL's.

## Building the table

With the dependencies of [`requirements.txt`](../../requirements.txt) installed, from the root of the repository:

```bash
python build_dataset.py
```

The first run downloads the source files, about 14 MB, which can take a few minutes; later runs reuse them and take less than a minute. The script prints what each step of the pipeline does as it goes. With [uv](https://docs.astral.sh/uv/), `uv run --with-requirements requirements.txt python build_dataset.py` runs it without installing anything first, in a temporary environment with those packages.

Everything is written under `data/`, which is not versioned: datasets are rebuilt, never committed.

| File | What it holds |
| --- | --- |
| `data/raw_rda/*.rda` | the source files, downloaded once and kept for the next run |
| `data/idealista18_listings.parquet` | the table: every listing of the three cities |
| `data/idealista18_quality_report.csv` | how many rows break each quality rule |

The notebooks run the same pipeline and write the same files, with the same table. To follow it step by step, open them in order and run all their cells: the second one uses what the first one downloaded.

## Licence

idealista18 is published under the [Open Database License (ODbL) v1.0](https://opendatacommons.org/licenses/odbl/1-0/). Any table derived from it and used in public must be offered under the same licence, with this citation: Rey-Blanco, D., Arbués, P., López, F. & Páez, A. (2024). A geo-referenced micro-data set of real estate listings for Spain's three largest cities. *Environment and Planning B: Urban Analytics and City Science*. https://doi.org/10.1177/23998083241242844.
