# idealista18-avm

An automated valuation model (AVM) estimates the market value of a property. Banks, property portals and appraisers use them every day, and an estimate is only useful if it is clear how far it can be trusted. This project builds an AVM for homes for sale on real 2018 listings from Madrid, Barcelona and Valencia.

## Getting started

1. Fork this repository and clone your fork.
2. Install the dependencies in `requirements.txt` (`pip install -r requirements.txt`, or uv or conda), and add the ones your own code uses.
3. Build the table the project starts from, `data/idealista18_listings.parquet`, from the root of the repository:

   ```bash
   python build_dataset.py
   ```

   The first run downloads the source data, about 14 MB, which can take a few minutes; later runs take less than a minute. The script says what it is doing at each step. `data/` is not versioned: each clone builds its own.
4. Read [`00a_exploring_the_listings.ipynb`](00a_exploring_the_listings.ipynb): the exploration of the table behind the first model's decisions (which listings, which columns, and why).
5. Open [`00b_a_first_model.ipynb`](00b_a_first_model.ipynb): it applies those decisions and prepares the columns of a first model. Continue working on it to create your first model.

> [!NOTE]
> **Optional reading: how the table is built.** [Building the dataset](docs/building-the-dataset/README.md) explains, in two notebooks, what `build_dataset.py` does and why: reading R data files, decoding columns, adding each listing's neighbourhood, checking the data's quality. It is data engineering rather than machine learning: the project starts from the table the script builds, and working on it doesn't require reading this.

The project's documentation is in [`docs/`](docs/README.md).

## Data and licence

The source is [idealista18](https://github.com/paezha/idealista18) (Rey-Blanco, Arbués, López & Páez, 2024, *Environment and Planning B*, [doi:10.1177/23998083241242844](https://doi.org/10.1177/23998083241242844)): the sale listings of the idealista portal in Madrid, Barcelona and Valencia during 2018, extracted once per quarter. It holds 189,923 listings: 94,815 in Madrid, 61,486 in Barcelona and 33,622 in Valencia. Each has its asking price, floor area, rooms and bathrooms, amenities, construction year, data from the Spanish cadastre, coordinates, the distances to the city centre, the nearest metro station and a main street, its neighbourhood, and its quarter.

The working table, `data/idealista18_listings.parquet`, is built from the source by `build_dataset.py`, which also writes a report of what the data-quality checks found ([Building the dataset](docs/building-the-dataset/README.md) explains each step). The table is not cleaned for modelling: which columns and rows a model may use is a decision of the project, to justify.

What the data is and isn't:

- **Asking prices, not sale prices.** A model trained on them estimates what a seller asks.
- **Anonymised on purpose.** Before publishing, the source's authors multiplied every price by a random factor between 0.975 and 1.025 and rounded it to €1,000, and moved every location 30 to 60 m in a random direction. No model can recover that noise, so it sets a floor under the error any estimate can reach.
- **Licensed [ODbL v1.0](https://opendatacommons.org/licenses/odbl/1-0/).** It may be used, shared and adapted, citing the source above; a database derived from it and published must stay under the same licence.

This repository stores no data: `build_dataset.py` downloads the source and builds the table on your machine. It is not affiliated with or endorsed by idealista.
