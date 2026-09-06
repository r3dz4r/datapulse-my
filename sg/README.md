# Singapore data.gov.sg probe adapters

This isolated package observes five public, read-only Singapore data.gov.sg source families. It does not alter the DataPulse manifest or health pipeline.

| Family | Bounded endpoint | Observation |
|---|---|---|
| COE bidding | CKAN datastore search, `limit=3` | total, columns, up to three records |
| HDB resale prices | Dataset list-rows, `limit=3` | total when supplied, columns, up to three rows |
| HDB metadata | Dataset metadata | `lastUpdated` where supplied |
| Taxi availability | Taxi realtime endpoint | source timestamp where supplied |
| Weather readings | Air-temperature realtime endpoint | source timestamp; the adapter also supports rainfall and relative-humidity |

Run the bounded probe with:

```bash
python3 -m sg.probe_sg_datagov --out sg_probe_results.json
```

Each request is a GET with a 20-second timeout. Reads are capped at three rows and the runner waits two seconds between its five family probes. If `SG_DATAGOV_API_KEY` is set, it is sent only as the `x-api-key` request header; it is neither written to output nor included in error text. The public endpoints work without it (the key raises the documented rate allowance from four to eight requests per ten seconds).
