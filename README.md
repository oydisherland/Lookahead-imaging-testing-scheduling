# Lookahead Imaging Testing Scheduling

Tools to find candidate lookahead captures and optionally insert them into an existing schedule for HYPSO satellites.

Quick start

- Run the main script from this folder:

```bash
python3 main.py -s now -e +48 -h 2 -targets lookahead_targets.json -schedule campaign_scripts_h2_2026-05-28.txt
```

Entrypoint is [main.py](main.py). It calls `getLookaheadCaptureCandidates` (see [get_lookahead_captures.py](get_lookahead_captures.py)).

### Command-line flags

- `-s`: start time.
  - Use an ISO timestamp such as `2026-06-01T13:00:00Z`.
  - You can also use `now` to start from the current UTC time.
- `-e`: end time.
  - Use an ISO timestamp such as `2026-06-03T13:00:00Z`.
  - You can also use `+X` to mean X hours after the start time, for example `+24` or `+48`.
- `-h`: HYPSO satellite number.
  - Example values: `1` or `2`.
- `-targets`: path to the target file.
  - Example: `lookahead_targets.json`.
- `-schedule`: path to the schedule.txt file that you want to insert lookahead captures into
  - Example : `campaign_scripts_h2_2026-05-28.txt``

## Using `getLookaheadCaptureCandidates(...)` directly

The function is defined in [`get_lookahead_captures.py`](get_lookahead_captures.py):

```python
getLookaheadCaptureCandidates(planningStartTime, planningEndTime, hypsoNr, lookaheadTargets_jsonfilepath, inputSchedule_filePath)
```

### Parameters

- `planningStartTime`: `datetime.datetime` marking the beginning of the planning horizon.
- `planningEndTime`: `datetime.datetime` marking the end of the planning horizon.
- `hypsoNr`: integer HYPSO satellite number (typically `1` or `2`).
- `lookaheadTargets_jsonfilepath`: path to the target JSON file (e.g. `lookahead_targets.json`).
- `inputSchedule_filePath`: path to the existing schedule file that the function will try to insert lookahead captures into (e.g. `campaign_scripts_h2_2026-05-28.txt`).

### Behavior and outputs

- The function searches for candidate consecutive-orbit capture pairs, ranks them by cloud-level difference, and generates `lookahead_candidates.txt` in the same folder as the script.
- It will attempt to insert up to a small number (currently 5) of selected capture command lines into the provided schedule file. The insertion is performed via a temporary updated file (named like `*_updated.txt`), which is copied back to `inputSchedule_filePath` and then removed.
- The function performs its work as a side effect (writing files and updating the schedule); you generally do not need to capture a return value.

### Example (calling directly)

```python
import datetime, os
from get_lookahead_captures import getLookaheadCaptureCandidates

start = datetime.datetime.now(datetime.timezone.utc)
end = start + datetime.timedelta(hours=48)
targets = os.path.join(os.path.dirname(__file__), "lookahead_targets.json")
schedule = os.path.join(os.path.dirname(__file__), "campaign_scripts_h2_2026-05-28.txt")

getLookaheadCaptureCandidates(start, end, 2, targets, schedule)
```

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

## Important targets

The file `important_targets.json` contains a list of targets that come from the original schedule and must be treated as non-removable. These targets are used by the insertion logic to avoid inserting lookahead capture command lines that would overlap or conflict with high-priority entries from the original schedule.

