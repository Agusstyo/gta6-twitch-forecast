# gta6-twitch-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Agusstyo/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Agusstyo/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts the Twitch concurrent viewers of the Grand Theft Auto VI category for every hour of launch day, as five quantiles per hour: past launches pooled in log space, weighted by pre-release similarity, anchored on the observed first hour.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## Method

A launch day's viewer curve has a fairly stable shape once its scale is divided out, so the forecaster works with shapes, not levels. Every past launch bundled in a case contributes its release day as log-ratios to its own first hour; those ratios, pooled hour by hour, are the raw material. Two refinements make the pool honest. First, each comparable is weighted by how closely its pre-release trajectory — the twelve hours before its day began — matches the target's: launches that gathered viewers in the same pattern before daybreak tend to unfold alike after it. Second, the mid-day hours, where trajectories diverge most because unlock timing differs, are hedged halfway toward a flat persistence forecast, while the opening dip and the evening climb are trusted to the shape. The five numbers per hour are weighted quantiles of the pooled ratios, scaled by the one fact known for certain — the target's observed first-hour print — so the interval widths come from how much similar launches actually deviated, not from a fixed padding. On the kit's four practice launches this scores a pinball loss of 0.272 against the house baseline's 0.387.

---

<sub>Entered on [make.fun](https://make.fun/?ref=hh8nsv3m&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
