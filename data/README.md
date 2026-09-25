# City–cohort imagery sources and Wayback releases

This CSV accompanies Supplementary Table S11. One row represents one city–cohort,
in the native observation order. It includes all 82 city–cohorts;
37 use Esri World Imagery Wayback and the remainder use the named
official or government-hosted providers.

| Field | Meaning |
|---|---|
| city_id, city_name | City identifier and display name. |
| cohort_order, cohort_id | Original ordered observation label; neither is an exact observation date. |
| provider, source_type | Imagery provider and delivery type. |
| source_year | Provider/source year label, retained as a JSON value; not an inferred capture date. |
| capture_period_description | Recorded source period or cohort capture-selection window; not a summary of all image capture dates. An open end such as `now` is a source label, not a dynamically updated date. |
| source_endpoint | Provider service or catalogue endpoint. |
| wayback_applicable | Whether the row uses Wayback. |
| wayback_publication_date | ISO date of publication of the selected composite map. |
| wayback_layer_id | Numeric Wayback map-layer identifier. |
| wayback_version | Named Wayback release; retain literally, including when its year differs from publication year. |
| arcgis_item_id, arcgis_item_url | ArcGIS imagery item and its catalogue page. |
| wayback_tile_url | Exact selected release's WMTS tile template. Placeholders are intentionally retained. |
| metadata_item_id, metadata_service_url | Matching image metadata item and service. |
| identification_scope, capture_date_scope | Limits of source identification and date interpretation. |

Empty Wayback fields in non-Wayback rows mean **not applicable**, not a missing
Wayback version. No Wayback row has a missing release identifier. Official
source years and endpoints are provided as recorded; the table does not assert
that live provider services are immutable archival releases.

The table identifies selected map releases, not an exhaustive per-tile source
or capture-date validation. A publication date can be later than the cohort
period because a newly published mosaic can retain older imagery. Neither a
release date nor a cohort label is a building construction or PV installation
date. Provider/version effects on temporal-state errors require a separate
analysis; they cannot be established from this source list.

Esri explains the distinction between map publication and image capture dates
in [Wayback with World Imagery Metadata](https://www.esri.com/arcgis-blog/products/arcgis-living-atlas/imagery/wayback-with-world-imagery-metadata)
(Robert Waterman, 20 December 2018).
