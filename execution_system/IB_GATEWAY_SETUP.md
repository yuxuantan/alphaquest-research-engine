# IB Gateway Setup For `ibkr_es_l2_ohlcv_poc.py`

This guide sets up IB Gateway so the Python script can connect to it, subscribe to ES market depth, and print 1-minute OHLCV.

## 1. Install And Log In

1. Install IB Gateway from Interactive Brokers.
2. Start IB Gateway.
3. Log in to either paper or live.
4. Keep the Gateway window/session running while the Python script is running.

IBKR's API connects to a running TWS or IB Gateway session over a local socket. IBKR notes that TWS and IB Gateway both require GUI authentication; fully headless login is not supported.

## 2. Enable API Socket Access

In IB Gateway, open the settings/configuration screen and go to:

```text
API -> Settings
```

Check these settings:

- Enable socket clients/API socket access.
- Confirm the socket port.
- Leave `Read Only API` enabled for this POC if you only want market data and no order placement.
- If there is a trusted IPs list, allow `127.0.0.1` for local scripts.

The script connects to `127.0.0.1`, so Gateway must be listening on the same machine and port unless you explicitly run it over your network.

## 3. Pick The Correct Port

Common IBKR defaults:

| Session | Typical Port |
| --- | ---: |
| TWS live | `7496` |
| TWS paper | `7497` |
| IB Gateway live | `4001` |
| IB Gateway paper | `4002` |

For IB Gateway paper, run:

```bash
python3 ibkr_es_l2_ohlcv_poc.py --port 4002 --client-id 72
```

For IB Gateway live, run:

```bash
python3 ibkr_es_l2_ohlcv_poc.py --port 4001 --client-id 72
```

You can also set environment variables:

```bash
export IB_HOST=127.0.0.1
export IB_PORT=4002
export IB_CLIENT_ID=72
python3 ibkr_es_l2_ohlcv_poc.py
```

Use a different `--client-id` for each separate API program connected to the same Gateway session.

## 4. Install Python Dependency

```bash
python3 -m pip install ibapi
```

Then verify the script starts:

```bash
python3 ibkr_es_l2_ohlcv_poc.py --help
```

## 5. Run The ES POC

Paper Gateway example:

```bash
python3 ibkr_es_l2_ohlcv_poc.py \
  --port 4002 \
  --client-id 72 \
  --expiry 202606 \
  --once
```

Live Gateway example:

```bash
python3 ibkr_es_l2_ohlcv_poc.py \
  --port 4001 \
  --client-id 72 \
  --expiry 202606
```

Add depth printing:

```bash
python3 ibkr_es_l2_ohlcv_poc.py --port 4002 --print-depth
```

Use IBKR's 1-minute historical live-updating bars instead of local aggregation:

```bash
python3 ibkr_es_l2_ohlcv_poc.py --port 4002 --bar-mode historical-1m
```

## 6. Seed Historical Data For Signals

Before relying on live bars for an entry signal, seed your signal engine with recent 1-minute history:

```bash
python3 ibkr_es_historical_1m_fetch.py \
  --port 4001 \
  --client-id 73 \
  --expiry 202606
```

By default this requests:

```text
duration: 1 D
bar size: 1 min
whatToShow: TRADES
useRTH: 0
```

The default output path is:

```text
data/ibkr/historical/ES_202606_CME_1min_latest.csv
```

Use a different `--client-id` than the live streaming script if both are connected at the same time. To write somewhere else:

```bash
python3 ibkr_es_historical_1m_fetch.py \
  --port 4001 \
  --client-id 73 \
  --expiry 202606 \
  --output data/ibkr/historical/es_seed.csv
```

The CSV columns are:

```text
timestamp_utc,timestamp_epoch,ib_timestamp,symbol,expiry,exchange,open,high,low,close,volume,wap,bar_count
```

## 7. Market Data Requirements

For real ES depth and trade bars, your IBKR username/session needs the relevant CME futures market data permissions. If you do not have live permissions, IBKR may return delayed data, no depth, or an API error.

The script defaults to:

```text
--market-data-type 1
```

That requests live data. For delayed data testing, try:

```bash
python3 ibkr_es_l2_ohlcv_poc.py --port 4002 --market-data-type 3
```

## 8. Troubleshooting

`Timed out waiting for IBKR nextValidId`

- Gateway is not running, not logged in, or API access is not enabled.
- The script is using the wrong port.
- A firewall is blocking the local socket connection.

`IBKR error 502`

- Usually means the socket cannot be opened. Check that Gateway is listening on the same port the script uses.

`No security definition has been found`

- Check `--expiry`, `--exchange`, and `--multiplier`.
- For ES, defaults are `--symbol ES --exchange CME --multiplier 50`.

`No market data / delayed data only`

- Check CME market data subscriptions for the exact username logged into Gateway.
- Paper trading sessions may depend on live account market data sharing.

`Already connected / duplicate client id`

- Use a different `--client-id`.

## 9. Operational Notes

IBKR states that TWS and IB Gateway are designed to be restarted daily. Gateway can auto-restart, but you should still expect periodic re-authentication, especially after weekend maintenance.

For this POC, keep it simple:

1. Start IB Gateway.
2. Log in.
3. Confirm API socket port.
4. Run the script using that port.

## Sources

- IBKR TWS API Initial Setup: https://interactivebrokers.github.io/tws-api/initial_setup.html
- IBKR TWS API Connectivity: https://interactivebrokers.github.io/tws-api/connection.html
- IBKR API connection parameters and Gateway ports: https://interactivebrokers.github.io/tws-api/rtd_simple_syntax.html
- IBKR API software/download page: https://interactivebrokers.github.io/
