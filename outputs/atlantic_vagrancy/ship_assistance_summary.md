# Atlantic vagrancy ship-assistance feasibility audit

## Scope

The audit contains **2,830 unique events** from **9,927 GBIF observations** for 30 species in the project's Atlantic Vagrancy Index. Event dates span 1955-01-16 to 2022-12-02. Each event is one species, date, and location rounded to two decimal degrees. Multiple GBIF observations of the same event are merged and counted in `observation_count`.
Records before 1940 are omitted because the configured ERA5 archive begins in 1940.

**Partial cache-only rebuild:** 1,655 occurrence records across 24 species were omitted because their complete ERA5 route-weather data were not present in the local cache. No weather requests were made during this rebuild. The species and counts are listed in the coverage table below.

These are **screening indicators, not causal classifications or probabilities**. The audit does not build or apply a predictive model, does not identify ships, and cannot prove that any individual bird was carried by a vessel.

## Weather Support Score

For each dated location, ERA5 hourly 10 m wind and mean sea-level pressure are sampled at seven points on a generic great-circle route from 45°N, 55°W (eastern North America) to the occurrence coordinate, during the seven calendar days ending on the record date. Tailwind uses wind projected onto the local route bearing; the corridor score combines mean positive along-route wind and the share of samples with tailwind ≥2 m/s. Headwind intensity is the mean opposing wind component. A major low is screened at ≤1000 hPa; its strength and proximity to the arrival date contribute to the composite. The final 0–1 score is `0.60 × tailwind corridor + 0.25 × storm support + 0.15 × low timing`, reduced by the opposing-wind penalty. A score of 0 means no support in these proxies; 1 is the maximum heuristic support.

This is a coarse surface-weather corridor, **not an air-mass trajectory or bird-flight wind**: ERA5 surface winds are used because the public API does not provide the required multi-decadal route-level upper-air trajectory in this audit. Species may travel by different routes or arrive days after a weather event.

## Harbour and shipping exposure

Harbour distances are geodesic distances from each occurrence coordinate to the six requested port coordinates. Nearest major commercial port is selected from the current EMODnet main-port locations layer. Container ports are ports classified as `Container ship` in the EMODnet 2025 main-port vessel-traffic layer. Shipping-route distance is the distance to the nearest mapped cell in EMODnet/EMSA's all-vessel average route-density WMS layer. The map is a recent aggregate route network, not event-date AIS. Therefore shipping exposure is a present-day geographic proxy for records from every year; the audit does not infer a contemporaneous ship position.

`distance_to_offshore_transfer_area_km` is blank for every row: no consistent public offshore ship-to-ship transfer-area layer was verified for this audit. Offshore oil/gas installations are not treated as transfer areas.

The shipping exposure score combines exponential proximity to the mapped route-density network (25 km scale) and to a container port (100 km scale). It is not a measure of actual vessel exposure.

## Preliminary Ship Assistance Indicator

The 0–1 indicator is a transparent weighted checklist, not a probability: 25% low weather support, 20% proximity to one of the six requested harbours (100 km decay), 15% species capability input, 15% isolated same-day arrival (distinct species within 100 km), 15% outside the species' 80%-coverage months in this project record set, and 10% shipping exposure. Blackpoll Warbler receives a low ship-assistance input because non-stop transoceanic migration has been documented; other species receive neutral inputs because their trans-Atlantic capability was not quantified here. The project record months are an effort-biased seasonal proxy, not an independent migration calendar.

`weather_supported` means Weather Support Score ≥0.60. `possible_ship_assisted` requires Weather Support Score <0.35 and Ship Assistance Indicator ≥0.60. Other rows are `ambiguous`. These cutoffs are descriptive triage thresholds only.

## Events most difficult to explain by weather alone

The following are the highest Ship Assistance Indicator events among those with Weather Support Score <0.35. They are candidates for manual review, not ship-assistance findings.

| Species | Date | Location (lat, lon) | Country | Weather support | Ship indicator | Nearest requested harbour | Route-cell distance (km) | GBIF observations |
|---|---|---|---|---:|---:|---|---:|---:|
| American Robin | 2014-04-27 | 52.50000, 4.60000 | Netherlands | 0.23 | 0.85 | IJmuiden (4 km) | 1.0 | 283 |
| American Robin | 2014-04-27 | 52.53000, 4.61000 | Netherlands | 0.23 | 0.84 | IJmuiden (8 km) | 1.0 | 2 |
| American Robin | 2014-04-27 | 52.53000, 4.62000 | Netherlands | 0.23 | 0.84 | IJmuiden (8 km) | 2.0 | 3 |
| American Robin | 2014-04-27 | 52.53000, 4.63000 | Netherlands | 0.23 | 0.84 | IJmuiden (8 km) | 2.0 | 1 |
| American Robin | 2014-04-27 | 52.54000, 4.63000 | Netherlands | 0.23 | 0.84 | IJmuiden (9 km) | 2.2 | 1 |
| White-throated Sparrow | 1967-09-28 | 51.90000, 4.40000 | Netherlands | 0.17 | 0.83 | Rotterdam (6 km) | 21.2 | 1 |
| Indigo Bunting | 2019-04-01 | 52.50000, 4.90000 | Netherlands | 0.06 | 0.83 | IJmuiden (22 km) | 20.2 | 1 |
| Rose-breasted Grosbeak | 2016-05-12 | 52.03000, 4.77000 | Netherlands | 0.01 | 0.83 | Rotterdam (24 km) | 31.9 | 1 |
| Baltimore Oriole | 2010-04-14 | 52.60000, 4.75000 | Netherlands | 0.15 | 0.83 | IJmuiden (19 km) | 8.9 | 1 |
| White-throated Sparrow | 2021-01-06 | 51.65000, 4.30000 | Netherlands | 0.01 | 0.82 | Rotterdam (31 km) | 26.4 | 1 |
| Baltimore Oriole | 2010-04-13 | 52.60000, 4.75000 | Netherlands | 0.19 | 0.82 | IJmuiden (19 km) | 8.9 | 1 |
| Baltimore Oriole | 2010-04-11 | 52.60000, 4.75000 | Netherlands | 0.23 | 0.81 | IJmuiden (19 km) | 8.9 | 3 |
| Dark-eyed Junco | 2015-04-09 | 53.25000, 6.55000 | Netherlands | 0.09 | 0.81 | Eemshaven (30 km) | 21.0 | 1 |
| Baltimore Oriole | 2010-04-12 | 52.60000, 4.75000 | Netherlands | 0.24 | 0.80 | IJmuiden (19 km) | 8.9 | 2 |
| Dark-eyed Junco | 2015-09-02 | 53.25000, 6.59000 | Netherlands | 0.12 | 0.80 | Eemshaven (28 km) | 21.0 | 1 |
| Dark-eyed Junco | 2021-05-01 | 51.98000, 4.07000 | Netherlands | 0.26 | 0.80 | Rotterdam (30 km) | 1.0 | 1 |
| Baltimore Oriole | 2010-04-10 | 52.60000, 4.75000 | Netherlands | 0.26 | 0.80 | IJmuiden (19 km) | 8.9 | 4 |
| Dark-eyed Junco | 2015-04-10 | 53.20000, 6.55000 | Netherlands | 0.09 | 0.80 | Eemshaven (34 km) | 26.0 | 2 |
| Dark-eyed Junco | 2015-04-09 | 53.20000, 6.55000 | Netherlands | 0.09 | 0.79 | Eemshaven (34 km) | 26.0 | 1 |
| Grey-cheeked Thrush | 2018-11-20 | 52.05000, 4.20000 | Netherlands | 0.31 | 0.79 | Rotterdam (25 km) | 1.0 | 7 |

## Species coverage

Registry species processed: **30**; with events: **30**; without events: **0**; skipped: **0** (included among species without events).

| Species | Events | Excluded observations | Status | Reason |
|---|---:|---:|---|---|
| Red-eyed Vireo | 431 | 101 | partially processed | 101 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Yellow-throated Vireo | 17 | 0 | processed | — |
| American Robin | 196 | 3 | partially processed | 3 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Veery | 24 | 34 | partially processed | 34 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Grey-cheeked Thrush | 159 | 16 | partially processed | 16 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Swainson's Thrush | 141 | 21 | partially processed | 21 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Hermit Thrush | 40 | 0 | processed | — |
| White-throated Sparrow | 208 | 284 | partially processed | 284 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Dark-eyed Junco | 289 | 30 | partially processed | 30 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Indigo Bunting | 46 | 358 | partially processed | 358 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Bobolink | 134 | 20 | partially processed | 20 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Scarlet Tanager | 32 | 37 | partially processed | 37 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Rose-breasted Grosbeak | 112 | 1 | partially processed | 1 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Baltimore Oriole | 179 | 8 | partially processed | 8 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Cedar Waxwing | 72 | 1 | partially processed | 1 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Northern Waterthrush | 66 | 258 | partially processed | 258 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Blackpoll Warbler | 195 | 1 | partially processed | 1 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Ovenbird | 12 | 1 | partially processed | 1 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Common Yellowthroat | 96 | 0 | processed | — |
| Black-and-white Warbler | 72 | 36 | partially processed | 36 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Canada Warbler | 5 | 61 | partially processed | 61 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| American Redstart | 34 | 0 | processed | — |
| Yellow-rumped Warbler | 127 | 153 | partially processed | 153 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Blue-winged Warbler | 5 | 0 | processed | — |
| Tennessee Warbler | 20 | 8 | partially processed | 8 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Cape May Warbler | 14 | 33 | partially processed | 33 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Magnolia Warbler | 2 | 169 | partially processed | 169 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Blackburnian Warbler | 20 | 16 | partially processed | 16 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |
| Wilson's Warbler | 8 | 0 | processed | — |
| Northern Parula | 74 | 5 | partially processed | 5 occurrence records excluded because their ERA5 route-weather data are missing from the local cache. |

## Rarity events

The audit contains **2,830 events**, where one event is a unique species, date, and location rounded to two decimal degrees.

### Top 10 species by event count

| Species | Events |
|---|---:|
| Red-eyed Vireo | 431 |
| Dark-eyed Junco | 289 |
| White-throated Sparrow | 208 |
| American Robin | 196 |
| Blackpoll Warbler | 195 |
| Baltimore Oriole | 179 |
| Grey-cheeked Thrush | 159 |
| Swainson's Thrush | 141 |
| Bobolink | 134 |
| Yellow-rumped Warbler | 127 |

## Country breakdown

| Country | Events |
|---|---:|
| United Kingdom (GB) | 2290 |
| Ireland (IE) | 169 |
| Netherlands (NL) | 284 |
| Belgium (BE) | 29 |
| Denmark (DK) | 58 |

## Data and method sources

- [Project Atlantic Vagrancy Index occurrence builder](../../src/build_atlantic_vagrancy_dataset.py): species registry, countries and GBIF filters.
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api): ERA5 hourly historical weather; global reanalysis availability from 1940 at 0.25° and API usage terms.
- [EMODnet/EMSA Route Density Map metadata](https://ows.emodnet-humanactivities.eu/geonetwork/srv/api/records/74eef9c6-13fe-4630-b935-f26871c8b661): 1 km AIS-derived route-density cells, CC BY 4.0; aggregate route restoration, not live ship tracks.
- [EMODnet Human Activities WFS](https://ows.emodnet-humanactivities.eu/wfs): main-port locations and vessel traffic by vessel type; the latter includes data through 2025.
- [DeLuca et al. (2015), Transoceanic migration by a 12 g songbird](https://repository.si.edu/items/0f7b5206-191b-446c-a6fd-9dbd38647f90): geolocator evidence for non-stop oceanic migration by Blackpoll Warblers.

## Limitations

- Record locations are GBIF occurrence coordinates; they do not establish where or when a bird arrived.
- GBIF observation coverage and reporting effort vary by country, year, site, species and observer.
- The generic North Atlantic route and ERA5 10 m winds simplify the species-specific flight path, flight altitude, wind selection, and storm-track timing.
- Port and route proximity indicate geographic opportunity only. A landfall near a port does not show the bird was aboard a vessel.
- EMODnet route density is spatially aggregated and recent; its route proximity is not historically matched to an occurrence date.
- The season and same-day-arrival indicators are computed from this same record set and inherit its reporting biases.
