# IBKR ES Data POC Commands

This workspace contains small Python POCs for Interactive Brokers ES futures data:

- `ibkr_es_historical_1m_fetch.py`: fetches historical 1-minute OHLCV bars and saves CSV.
- `ibkr_es_l2_ohlcv_poc.py`: streams ES level II depth and live 1-minute OHLCV.
- `IB_GATEWAY_SETUP.md`: setup notes for IB Gateway.

## 1. Prerequisites

Start IB Gateway first, then log in.

Common ports:

| Gateway Session | Port |
| --- | ---: |
| Live IB Gateway | `4001` |
| Paper IB Gateway | `4002` |

Install the Python API dependency:

```bash
python3 -m pip install ibapi
```

Check script help:

```bash
python3 ibkr_es_historical_1m_fetch.py --help
python3 ibkr_es_l2_ohlcv_poc.py --help
```

## 2. Recommended Startup Flow

For a signal engine, seed the last day of 1-minute bars first, then start the live stream.

```bash
python3 ibkr_es_historical_1m_fetch.py \
  --port 4001 \
  --client-id 73 \
  --expiry 202606
```

Then start live L2 plus live OHLCV:

```bash
python3 ibkr_es_l2_ohlcv_poc.py \
  --port 4001 \
  --client-id 72 \
  --expiry 202606
```

Use different `--client-id` values when both scripts are connected at the same time.

## 3. Fetch Historical 1-Minute Bars

Default live Gateway command:

```bash
python3 ibkr_es_historical_1m_fetch.py \
  --port 4001 \
  --client-id 73 \
  --expiry 202606
```

Default paper Gateway command:

```bash
python3 ibkr_es_historical_1m_fetch.py \
  --port 4002 \
  --client-id 73 \
  --expiry 202606
```

By default, this requests:

```text
duration: 1 D
bar size: 1 min
whatToShow: TRADES
useRTH: 0
```

Default output:

```text
data/ibkr/historical/ES_202606_CME_1min_latest.csv
```

Write to a custom CSV:

```bash
python3 ibkr_es_historical_1m_fetch.py \
  --port 4001 \
  --client-id 73 \
  --expiry 202606 \
  --output data/ibkr/historical/es_seed.csv
```

Fetch more history:

```bash
python3 ibkr_es_historical_1m_fetch.py \
  --port 4001 \
  --client-id 73 \
  --expiry 202606 \
  --duration "2 D"
```

Fetch a specific Singapore-date range:

```bash
python3 ibkr_es_historical_1m_fetch.py \
  --port 4001 \
  --client-id 73 \
  --expiry 202606 \
  --start 2026-06-01 \
  --end 2026-06-05 \
  --timezone Asia/Singapore
```

Date-only range values are interpreted in `--timezone`. The start date uses `00:00:00`; the end date uses `23:59:59`. With the default `Asia/Singapore` timezone, `--start 2026-06-05` means `2026-06-05 00:00:00+08`.

Fetch an exact timestamp range:

```bash
python3 ibkr_es_historical_1m_fetch.py \
  --port 4001 \
  --client-id 73 \
  --expiry 202606 \
  --start "2026-06-05T06:00:00+08:00" \
  --end "2026-06-06T05:00:00+08:00"
```

For range downloads, the script requests daily chunks from IBKR, filters bars to the requested start/end, de-duplicates overlap, and writes one combined CSV. This is necessary because IBKR historical requests use `endDateTime + durationString`, not direct start/end parameters.

Regular trading hours only:

```bash
python3 ibkr_es_historical_1m_fetch.py \
  --port 4001 \
  --client-id 73 \
  --expiry 202606 \
  --use-rth 1
```

## 4. Inspect The Historical CSV

Show row count:

```bash
wc -l data/ibkr/historical/ES_202606_CME_1min_latest.csv
```

Show first rows:

```bash
head -n 5 data/ibkr/historical/ES_202606_CME_1min_latest.csv
```

Show latest rows:

```bash
tail -n 5 data/ibkr/historical/ES_202606_CME_1min_latest.csv
```

CSV columns:

```text
timestamp_utc,timestamp_epoch,ib_timestamp,symbol,expiry,exchange,open,high,low,close,volume,wap,bar_count
```

## 5. Stream Live L2 And OHLCV

Live Gateway:

```bash
python3 ibkr_es_l2_ohlcv_poc.py \
  --port 4001 \
  --client-id 72 \
  --expiry 202606
```

Paper Gateway:

```bash
python3 ibkr_es_l2_ohlcv_poc.py \
  --port 4002 \
  --client-id 72 \
  --expiry 202606
```

Print top-of-book L2 updates to stderr:

```bash
python3 ibkr_es_l2_ohlcv_poc.py \
  --port 4001 \
  --client-id 72 \
  --expiry 202606 \
  --print-depth
```

Print only completed 1-minute bars:

```bash
python3 ibkr_es_l2_ohlcv_poc.py \
  --port 4001 \
  --client-id 72 \
  --expiry 202606 \
  --completed-only
```

Exit after the first OHLCV line:

```bash
python3 ibkr_es_l2_ohlcv_poc.py \
  --port 4001 \
  --client-id 72 \
  --expiry 202606 \
  --once
```

## 6. Trigger ES Orders Through Proteryx

`proteryx_es_market_bracket.py` posts a Proteryx Auto Trader webhook payload for
an ES market order with attached take-profit and stop-loss distances.

The script is dry-run by default. It prints the exact JSON payload and only sends
the order when `--execute` is provided.

Set your Auto Trader UUID:

```bash
export PROTERYX_STRATEGY_UUID="your-proteryx-auto-trader-uuid"
```

Dry-run a 1-contract ES buy with a 10-point TP and 5-point SL:

```bash
python3 proteryx_es_market_bracket.py \
  --side buy \
  --quantity 1 \
  --symbol ES \
  --tp-points 10 \
  --sl-points 5
```

Send it to Proteryx:

```bash
python3 proteryx_es_market_bracket.py \
  --side buy \
  --quantity 1 \
  --symbol ES \
  --tp-points 10 \
  --sl-points 5 \
  --execute
```

If your Proteryx/broker route expects a specific contract month, pass it
explicitly, for example `--symbol ESM6`. If your Auto Trader needs portfolio or
route fields:

```bash
python3 proteryx_es_market_bracket.py \
  --side sell \
  --quantity 1 \
  --symbol ESM6 \
  --tp-ticks 40 \
  --sl-ticks 20 \
  --portfolio Terminal \
  --route selected_accounts
```

## 7. Apex 50K EOD Guardrails

`apex_eod_guardrails.py` is a manual pre-trade compliance gate for five Apex
50K EOD accounts. It blocks orders before they hit Apex's 50K EOD evaluation
limits:

- $3,000 evaluation profit target
- $2,000 EOD drawdown
- $1,000 daily loss limit
- 6 max standard contracts, with 10 micros equal to 1 standard contract
- required stop/risk controls, no hedging/reversal through the guard, and no
  new opening trades after the configured ET flat cutoff

Important: Apex currently publishes a prohibited-activities rule that says no
automation or algorithm usage is allowed. Use this only as a manually invoked
risk/compliance gate unless Apex explicitly confirms your workflow is permitted.
It cannot guarantee payouts.

Copy the example config and update each account snapshot from your Apex/broker
dashboard before trading:

```bash
cp apex_50k_eod_guardrails.example.json apex_50k_eod_guardrails.json
```

Check account status:

```bash
python3 apex_eod_guardrails.py \
  --config apex_50k_eod_guardrails.json \
  status
```

Dry-run a guarded ES order across all enabled accounts:

```bash
python3 apex_eod_guardrails.py \
  --config apex_50k_eod_guardrails.json \
  check-order \
  --side buy \
  --quantity 1 \
  --symbol ES \
  --tp-points 10 \
  --sl-points 4
```

Guard the order, then dry-run the Proteryx payload:

```bash
export PROTERYX_STRATEGY_UUID="your-proteryx-auto-trader-uuid"

python3 apex_eod_guardrails.py \
  --config apex_50k_eod_guardrails.json \
  send-order \
  --side buy \
  --quantity 1 \
  --symbol ES \
  --tp-points 10 \
  --sl-points 4
```

Actually post to Proteryx only after the guardrail report is clean:

```bash
python3 apex_eod_guardrails.py \
  --config apex_50k_eod_guardrails.json \
  send-order \
  --side buy \
  --quantity 1 \
  --symbol ES \
  --tp-points 10 \
  --sl-points 4 \
  --execute
```

If you are trading a PA instead of an evaluation, set an account's
`account_type` to `pa`. The status report will add the 50K EOD PA payout
checks for 5 qualifying days, $52,100 safety net, $52,600 minimum request
balance, 50% consistency, and the six-payout cap.

## 8. Live Strategy Execution Bridge

`strategy_execution_bridge.py` connects the research strategy configs to the
execution system without modifying the research code:

1. Loads the configured campaign variant YAML read-only.
2. Pulls recent 1-minute ES historical bars from IBKR.
3. Subscribes to IBKR 5-second live bars and aggregates completed 1-minute bars.
4. Builds the same session, timeframe, and feature columns used by backtests.
5. Runs the modular strategy on newly completed strategy bars.
6. Computes entry estimate, stop, target, and strategy-suggested size.
7. Walks size down until the Apex guardrails approve the order.
8. Dry-runs or sends the guarded market/TP/SL payload to Proteryx.

The example bridge config points at:

```text
configs/campaigns/pdh_pdl_breakout_continuation/variants/ES/2m/gap_hold_fast_confirmation_wfa_probe.yaml
```

The bridge needs the same Python environment as the research stack plus IBKR:

```bash
python3 -m pip install pandas pyyaml ibapi
```

Check the bridge help:

```bash
python3 strategy_execution_bridge.py --help
```

Run one live completed-minute evaluation in dry-run mode:

```bash
python3 strategy_execution_bridge.py \
  --config strategy_execution_bridge.example.json \
  --once
```

Run continuously in dry-run mode:

```bash
python3 strategy_execution_bridge.py \
  --config strategy_execution_bridge.example.json
```

Allow Proteryx POSTs only after the strategy signal, sizing, and guardrails all
pass:

```bash
export PROTERYX_STRATEGY_UUID="your-proteryx-auto-trader-uuid"

python3 strategy_execution_bridge.py \
  --config strategy_execution_bridge.example.json \
  --execute
```

Keep `apex_50k_eod_guardrails.example.json` current with live Apex account
balances, start-of-day balances, EOD thresholds, and open exposure. The bridge
uses the lowest selected account equity as the live sizing base, then clamps the
result to the largest quantity that passes every selected Apex account.

## 9. Delayed Data Testing

If your account does not have live CME data permissions, try delayed data:

```bash
python3 ibkr_es_l2_ohlcv_poc.py \
  --port 4001 \
  --client-id 72 \
  --expiry 202606 \
  --market-data-type 3
```

Market data type values:

| Value | Meaning |
| ---: | --- |
| `1` | Live |
| `2` | Frozen |
| `3` | Delayed |
| `4` | Delayed frozen |

## 10. Use Environment Variables

Instead of repeating flags:

```bash
export IB_HOST=127.0.0.1
export IB_PORT=4001
export IB_ES_EXPIRY=202606
export IB_EXCHANGE=CME
export IB_MULTIPLIER=50
```

Then run:

```bash
python3 ibkr_es_historical_1m_fetch.py --client-id 73
python3 ibkr_es_l2_ohlcv_poc.py --client-id 72
```

## 11. Practical Signal Engine Flow

1. Run `ibkr_es_historical_1m_fetch.py` at startup.
2. Load `data/ibkr/historical/ES_202606_CME_1min_latest.csv`.
3. Compute indicators and initial signal state from the historical bars.
4. Start `ibkr_es_l2_ohlcv_poc.py`.
5. Append each completed live 1-minute bar to your in-memory bar series.
6. Recompute entry signals only after a completed bar, unless your strategy explicitly uses partial bars.

## 12. Common Problems

`Couldn't connect to TWS`

- Confirm IB Gateway is running and logged in.
- Confirm the script port matches Gateway's socket port.
- Use `4001` for live Gateway and `4002` for paper Gateway.

`duplicate client id`

- Use different `--client-id` values for each running script.

No OHLCV lines print

- ES may be outside trading hours.
- Your account may not have the needed CME market data subscription.
- Try `--market-data-type 3` for delayed data testing.

No depth lines print

- Add `--print-depth`.
- Confirm level II market data permissions for CME futures.

`No security definition has been found`

- Check `--expiry`.
- For ES, keep `--symbol ES --exchange CME --multiplier 50`.
