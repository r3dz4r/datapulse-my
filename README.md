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

## Included datasets

- [Malaysian Fuel Prices](data/fuelprice.md)
- [ePerolehan Tender Notices (DIIKLANKAN)](data/eperolehan-diklankan.md)
- [PriceCatcher (Daily Grocery Prices)](data/pricecatcher.md)

### Daily Reference Data (Bank Negara Malaysia)

These four BNM reference-rate datasets are updated on weekdays at fixed MYT
publication times:

- [BNM Daily Exchange Rates (0900)](data/exchangerates_daily_0900.md)
- [BNM Daily Exchange Rates (1130)](data/exchangerates_daily_1130.md)
- [BNM Daily Exchange Rates (1200)](data/exchangerates_daily_1200.md)
- [BNM Daily Exchange Rates (1700)](data/exchangerates_daily_1700.md)

DataPulse MY currently tracks seven datasets in total.

## How to use it

Start with [`datapulse.json`](datapulse.json) to discover datasets and their
official sources. Follow each `health_report` link for a plain-language
assessment, or consume the matching file under `data/json/` in an automated
workflow.

For example, a data pipeline can inspect `status` and `freshness_days` before
processing a source, while a researcher can review the known quirks before
designing a collection method.

## Adopt a dataset

Know a Malaysian public dataset that deserves dependable health metadata?
Adopt it: verify its source and licence, document its schema and quirks, and
submit a health report. See [CONTRIBUTING.md](CONTRIBUTING.md) for the expected
three-file contribution model.

## Licence

DataPulse MY is released under the [MIT License](LICENSE). Source datasets
remain subject to the licences and attribution requirements stated in their
individual health reports.
