# TTools Package

---

## Introduction

The `ttools` package is a minimal event-driven backtesting framework designed for simulating single-symbol, single-strategy trading using one-second OHLCV bar data sourced from a DataBento-formatted CSV file. The framework has three components: `datafeed`, `strategy`, and `ttanalytics`. 

The `datafeed` component simulates a connection to a live feed by reading a CSV file row by row, converting each row into an `IncomingBarEventMessage`, and placing these messages into the `incoming_bar_event_message_queue`.

The `strategy` component concurrently consumes messages from the `incoming_bar_event_message_queue` and simulates signal generation as well as order execution. Since strategy logic is evaluated on completed bars, orders can be submitted—and filled, in the case of market orders—no earlier than at the open of the following bar. Thus:
* When a new bar arrives, the `strategy` component first fills all "pending" market orders at the bar's opening price. It then evaluates pending limit and stop orders to determine if their fill conditions are met and, if so, fills them as well. All executed trades will be enqueued as a `TradeEventMessage` into the `trade_event_message_queue`. Performance metrics (position size, average entry price, maximum drawdown, etc.) will be tracked as indicators.
* Only then will the strategy logic be updated with the data from the incoming bar, and new orders will be generated (to be executed at the earliest when the next bar arrives). The data contained in the `IncomingBarEventMessage` will be enriched with all calculated indicators and enqueued as a `ProcessedBarEventMessage` into the `processed_bar_event_message_queue`.

The `ttanalytica` (short for technical trade analytics) component will periodically consume `ProcessedBarEventMessage`s and `TradeEventMessage`s from their respective queues and write the data to corresponding CSV files. To facilitate trade review, charts displaying each trade in context will be saved to disk for all trades that occurred.


---
## Components

### Datafeeds

### Strategies

### TTAnalytica