# Atlantic vagrancy ship-assistance feasibility audit

## Scope

The audit contains **3,198 unique events** from **11,582 GBIF observations** for 30 species in the project's Atlantic Vagrancy Index. Event dates span 1955-01-16 to 2026-10-01. Each event is one species, date, and location rounded to two decimal degrees. Multiple GBIF observations of the same event are merged and counted in `observation_count`.
Records before 1940 are omitted because the configured ERA5 archive begins in 1940.

**Weather unavailable:** 12 events (17 GBIF observations) are retained with null weather fields and classified as `weather unavailable`.

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
| Rose-breasted Grosbeak | 2016-05-12 | 52.03000, 4.77000 | Netherlands | 0.01 | 0.83 | Rotterdam (24 km) | 31.9 | 1 |
| Baltimore Oriole | 2010-04-14 | 52.60000, 4.75000 | Netherlands | 0.15 | 0.83 | IJmuiden (19 km) | 8.9 | 1 |
| Baltimore Oriole | 2010-04-13 | 52.60000, 4.75000 | Netherlands | 0.19 | 0.82 | IJmuiden (19 km) | 8.9 | 1 |
| Baltimore Oriole | 2010-04-11 | 52.60000, 4.75000 | Netherlands | 0.23 | 0.81 | IJmuiden (19 km) | 8.9 | 3 |
| Baltimore Oriole | 2010-04-12 | 52.60000, 4.75000 | Netherlands | 0.24 | 0.80 | IJmuiden (19 km) | 8.9 | 2 |
| Dark-eyed Junco | 2015-09-02 | 53.25000, 6.59000 | Netherlands | 0.12 | 0.80 | Eemshaven (28 km) | 21.0 | 1 |
| Indigo Bunting | 1983-06-08 | 52.90000, 5.00000 | Netherlands | 0.05 | 0.80 | IJmuiden (56 km) | 5.0 | 1 |
| Indigo Bunting | 1983-06-25 | 52.90000, 5.00000 | Netherlands | 0.05 | 0.80 | IJmuiden (56 km) | 5.0 | 3 |
| Dark-eyed Junco | 2021-05-01 | 51.98000, 4.07000 | Netherlands | 0.26 | 0.80 | Rotterdam (30 km) | 1.0 | 1 |
| Baltimore Oriole | 2010-04-10 | 52.60000, 4.75000 | Netherlands | 0.26 | 0.80 | IJmuiden (19 km) | 8.9 | 4 |
| Indigo Bunting | 1983-06-19 | 52.90000, 5.00000 | Netherlands | 0.07 | 0.80 | IJmuiden (56 km) | 5.0 | 1 |
| Indigo Bunting | 1983-06-10 | 52.90000, 5.00000 | Netherlands | 0.08 | 0.79 | IJmuiden (56 km) | 5.0 | 1 |
| Grey-cheeked Thrush | 2018-11-20 | 52.05000, 4.20000 | Netherlands | 0.31 | 0.79 | Rotterdam (25 km) | 1.0 | 7 |
| Baltimore Oriole | 2010-04-05 | 52.60000, 4.75000 | Netherlands | 0.29 | 0.79 | IJmuiden (19 km) | 8.9 | 6 |

## Species coverage

Registry species processed: **30**; with events: **30**; without events: **0**; skipped: **0** (included among species without events).

| Species | Events | Weather-unavailable events | Excluded observations | Status | Reason |
|---|---:|---:|---:|---|---|
| Red-eyed Vireo | 468 | 1 | 0 | partially processed | 1 events retained with null ERA5 route-weather data and classified as weather unavailable. |
| Yellow-throated Vireo | 17 | 0 | 0 | processed | — |
| American Robin | 199 | 1 | 0 | partially processed | 1 events retained with null ERA5 route-weather data and classified as weather unavailable. |
| Veery | 30 | 0 | 0 | processed | — |
| Grey-cheeked Thrush | 169 | 0 | 0 | processed | — |
| Swainson's Thrush | 153 | 0 | 0 | processed | — |
| Hermit Thrush | 40 | 0 | 0 | processed | — |
| White-throated Sparrow | 277 | 4 | 0 | partially processed | 4 events retained with null ERA5 route-weather data and classified as weather unavailable. |
| Dark-eyed Junco | 298 | 3 | 0 | partially processed | 3 events retained with null ERA5 route-weather data and classified as weather unavailable. |
| Indigo Bunting | 80 | 0 | 0 | processed | — |
| Bobolink | 145 | 0 | 0 | processed | — |
| Scarlet Tanager | 37 | 0 | 0 | processed | — |
| Rose-breasted Grosbeak | 113 | 0 | 0 | processed | — |
| Baltimore Oriole | 185 | 0 | 0 | processed | — |
| Cedar Waxwing | 73 | 0 | 0 | processed | — |
| Northern Waterthrush | 97 | 0 | 0 | processed | — |
| Blackpoll Warbler | 196 | 1 | 0 | partially processed | 1 events retained with null ERA5 route-weather data and classified as weather unavailable. |
| Ovenbird | 13 | 0 | 0 | processed | — |
| Common Yellowthroat | 96 | 0 | 0 | processed | — |
| Black-and-white Warbler | 83 | 1 | 0 | partially processed | 1 events retained with null ERA5 route-weather data and classified as weather unavailable. |
| Canada Warbler | 9 | 0 | 0 | processed | — |
| American Redstart | 34 | 0 | 0 | processed | — |
| Yellow-rumped Warbler | 181 | 1 | 0 | partially processed | 1 events retained with null ERA5 route-weather data and classified as weather unavailable. |
| Blue-winged Warbler | 5 | 0 | 0 | processed | — |
| Tennessee Warbler | 25 | 0 | 0 | processed | — |
| Cape May Warbler | 32 | 0 | 0 | processed | — |
| Magnolia Warbler | 35 | 0 | 0 | processed | — |
| Blackburnian Warbler | 22 | 0 | 0 | processed | — |
| Wilson's Warbler | 8 | 0 | 0 | processed | — |
| Northern Parula | 78 | 0 | 0 | processed | — |

## Rarity events

The audit contains **3,198 events**, where one event is a unique species, date, and location rounded to two decimal degrees.

### Top 10 species by event count

| Species | Events |
|---|---:|
| Red-eyed Vireo | 468 |
| Dark-eyed Junco | 298 |
| White-throated Sparrow | 277 |
| American Robin | 199 |
| Blackpoll Warbler | 196 |
| Baltimore Oriole | 185 |
| Yellow-rumped Warbler | 181 |
| Grey-cheeked Thrush | 169 |
| Swainson's Thrush | 153 |
| Bobolink | 145 |

## Country breakdown

| Country | Events |
|---|---:|
| United Kingdom (GB) | 2528 |
| Ireland (IE) | 200 |
| Netherlands (NL) | 289 |
| Belgium (BE) | 32 |
| Denmark (DK) | 149 |

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
