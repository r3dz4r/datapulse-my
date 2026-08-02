# DataPulse MY

DataPulse MY is an open-source trust layer for Malaysian public data. It makes
official datasets easier to assess and reuse by publishing a small manifest,
human-readable health reports, and machine-readable health envelopes.

It does not replace the official source. It documents what is available,
whether it is fresh, how its schema behaves, and which collection quirks users
need to handle.

## Who it is for

- Journalists and researchers checking whether a public dataset is usable.
- Civic technologists building reproducible data pipelines.
- Public servants improving the discoverability and reliability of open data.
- Developers who need stable, machine-readable dataset health metadata.

## Use this for

- **Journalist fact-check:** before citing a fuel price figure, check fuelprice
  freshness to make sure it's current.
- **Pipeline health gate:** fail the build if data.gov.my has been down for
  more than 24 hours.
- **RAG knowledge base:** consume the JSON envelopes as structured context for
  a chatbot answering "what's the latest BNM rate?"

## Included datasets

- [Malaysian Fuel Prices](data/fuelprice.md) — Samples:
  [CSV](samples/fuelprice.csv), [JSON](samples/fuelprice.json)
- [ePerolehan Tender Notices (DIIKLANKAN)](data/eperolehan-diklankan.md) —
  [Sample JSON](samples/eperolehan-diklankan.json)
- [PriceCatcher (Daily Grocery Prices)](data/pricecatcher.md) — Samples:
  [main CSV](samples/pricecatcher.csv),
  [item lookup](samples/pricecatcher_lookup_item.csv),
  [premise lookup](samples/pricecatcher_lookup_premise.csv)

### Daily Reference Data (Bank Negara Malaysia)

These four BNM reference-rate datasets are updated on weekdays at fixed MYT
publication times:

- [BNM Daily Exchange Rates (0900)](data/exchangerates_daily_0900.md) —
  [Sample JSON](samples/exchangerates_daily_0900.json)
- [BNM Daily Exchange Rates (1130)](data/exchangerates_daily_1130.md) —
  [Sample JSON](samples/exchangerates_daily_1130.json)
- [BNM Daily Exchange Rates (1200)](data/exchangerates_daily_1200.md) —
  [Sample JSON](samples/exchangerates_daily_1200.json)
- [BNM Daily Exchange Rates (1700)](data/exchangerates_daily_1700.md) —
  [Sample JSON](samples/exchangerates_daily_1700.json)

DataPulse MY currently tracks seven datasets in total.

## Current coverage

### Refresh cadence

| Dataset | Refresh cadence |
| --- | --- |
| Malaysian Fuel Prices (`fuelprice`) | Weekly |
| ePerolehan Tender Notices (`eperolehan-diklankan`) | Daily |
| PriceCatcher (`pricecatcher`) | Monthly |
| BNM Daily Exchange Rates (`exchangerates_daily_0900`) | Daily on weekdays at 0900 MYT |
| BNM Daily Exchange Rates (`exchangerates_daily_1130`) | Daily on weekdays at 1130 MYT |
| BNM Daily Exchange Rates (`exchangerates_daily_1200`) | Daily on weekdays at 1200 MYT |
| BNM Daily Exchange Rates (`exchangerates_daily_1700`) | Daily on weekdays at 1700 MYT |

## How to use it

Start with [`datapulse.json`](datapulse.json) to discover datasets and their
official sources. Follow each `health_report` link for a plain-language
assessment, or consume the matching file under `data/json/` in an automated
workflow.

For example, a data pipeline can inspect `status` and `freshness_days` before
processing a source, while a researcher can review the known quirks before
designing a collection method.

## Roadmap

- Scheduled health checks — in progress.
- RSS feed — planned.
- Status badges — planned.
- More datasets — planned.

## Adopt a dataset

Know a Malaysian public dataset that deserves dependable health metadata?
Adopt it: verify its source and licence, document its schema and quirks, and
submit a health report. See [CONTRIBUTING.md](CONTRIBUTING.md) for the expected
three-file contribution model.

## Licence

DataPulse MY is released under the [MIT License](LICENSE). Source datasets
remain subject to the licences and attribution requirements stated in their
individual health reports.
