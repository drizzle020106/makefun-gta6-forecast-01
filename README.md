# makefun-gta6-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/drizzle020106/makefun-gta6-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/drizzle020106/makefun-gta6-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts GTA VI's launch-day Twitch viewers hour by hour. `main.py` (Python 3.13, standard library only, no network) reads one case file from `/input`, fits the shape of a big launch day from the case's own comparables, and writes five quantiles per hour (5%, 25%, 50%, 75%, 95%) for hours 2–24 to `/output`.

How it works: for each forecast hour, it takes the median log-ratio of that hour's viewers to the same launch's hour-1 viewers across all usable past launches (tier "comparable", full 24-hour release day, hour-1 viewers ≥ 5000), with the spread from the interquartile range of those log-ratios. The fitted shape dips to about 0.73× hour 1 in the deep night (hour 4) and peaks near 2.4× in the US evening (hours 19–20), matching the rolling midnight-unlock wave. If the comparable pool is too thin for an hour, that hour falls back to staying at hour 1 with a widening random-walk spread. The output is fully deterministic: same case, same bytes.

Local leave-one-out validation on 12 past launches (each held out in turn, forecast from its hour 1 alone): mean pinball loss 0.359 vs 0.477 for the house baseline starter on the same launches. On the six held-out launches closest to GTA VI (console-only, rolling midnight unlock, hour-1 viewers ≥ 10,000): 0.233 vs 0.363 for the baseline.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

Entered on [make.fun](https://make.fun/?ref=jrdmgfv5&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards
