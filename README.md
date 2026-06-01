# Lookahead Imaging Testing Scheduling

This folder contains the scripts used to generate lookahead capture candidates for HYPSO missions.

## What the main script does

The entrypoint is [`main.py`](main.py). It calls `getLookaheadCaptureCandidates(...)` from [`get_lookahead_captures.py`](get_lookahead_captures.py) and writes the resulting candidate capture commands to `lookahead_candidates.txt`.

## How to run the main code

Run the script from inside this folder:

```bash
python3 main.py -s now -e +48 -h 2 -input lookahead_targets.json
```

### Command-line flags

- `-s`: start time.
  - Use an ISO timestamp such as `2026-06-01T13:00:00Z`.
  - You can also use `now` to start from the current UTC time.
- `-e`: end time.
  - Use an ISO timestamp such as `2026-06-03T13:00:00Z`.
  - You can also use `+X` to mean X hours after the start time, for example `+24` or `+48`.
- `-h`: HYPSO satellite number.
  - Example values: `1` or `2`.
- `-input`: path to the target file.
  - Example: `lookahead_targets.json`.

Example with explicit timestamps:

```bash
python3 main.py \
  -s 2026-06-01T13:00:00Z \
  -e 2026-06-03T13:00:00Z \
  -h 2 \
  -input lookahead_targets.json
```

## Using `getLookaheadCaptureCandidates(...)` directly

The function is defined in [`get_lookahead_captures.py`](get_lookahead_captures.py):

```python
getLookaheadCaptureCandidates(planningStartTime, planningEndTime, hypsoNr, lookaheadTargets_jsonfilepath)
```

### Parameters

- `planningStartTime`: `datetime.datetime` object marking the beginning of the planning horizon.
- `planningEndTime`: `datetime.datetime` object marking the end of the planning horizon.
- `hypsoNr`: integer HYPSO number, usually `1` or `2`.
- `lookaheadTargets_jsonfilepath`: path to the target JSON file.

### What it returns

The function creates `lookahead_candidates.txt`, which contains candidate command lines for lookahead captures sorted by cloud-level difference and annotated with extra scheduling information.

## About `targets.json`

The file [`targets.json`](targets.json) contains the targets used to generate lookahead captures.

Each object describes one target and includes fields such as:

- `name`: target name
- `lat`: latitude
- `lon`: longitude
- `elev`: elevation
- `cc`: cloud cover value used by the scheduling logic
- `exp`: exposure value
- `mode`: capture mode
- `night`: whether the target is intended for night use
- `t0` and `t1`: optional time bounds for the target
- `comment`: optional notes about the target

These are the target definitions the scheduling code uses when searching for valid lookahead capture opportunities.

## Output files

- `lookahead_candidates.txt`: generated command lines for candidate lookahead captures.

