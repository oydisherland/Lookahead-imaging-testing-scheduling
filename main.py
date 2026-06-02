import argparse
import datetime
import os
import sys

from get_lookahead_captures import getLookaheadCaptureCandidates


def parse_datetime(value: str) -> datetime.datetime:
    normalized_value = value.strip().replace("Z", "+00:00")
    parsed_value = datetime.datetime.fromisoformat(normalized_value)

    if parsed_value.tzinfo is None:
        parsed_value = parsed_value.replace(tzinfo=datetime.timezone.utc)

    return parsed_value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run getLookaheadCaptureCandidates from the terminal.",
        add_help=False,
    )
    parser.add_argument("-s", dest="start_time", required=True, help="Start time in ISO format, e.g. 2026-06-01T00:00:00Z, or write now for current time")
    parser.add_argument("-e", dest="end_time", required=True, help="End time in ISO format, e.g. 2026-06-02T00:00:00Z, or write +X for X hours from start time, e.g. +24 for 24 hours from start time")
    parser.add_argument("-h", dest="hypso_number", required=True, type=int, help="HYPSO satellite number, e.g. 1 or 2")
    parser.add_argument("-targets", dest="target_file_path", required=True, help="Path to the target JSON file")
    parser.add_argument("-schedule", dest="input_schedule_file_path", required=True, help="Path to the input schedule file to insert lookahead capture cmdLines into, if not provided cmdLines will not be inserted into schedule file")
    parser.add_argument("--help", action="help", help="Show this help message and exit")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.start_time.lower() == "now":
        start_time = datetime.datetime.now(datetime.timezone.utc)
    else:
        start_time = parse_datetime(args.start_time)
    if args.end_time.startswith("+"):
        end_time = start_time + datetime.timedelta(hours=int(args.end_time[1:]))
    else:
        end_time = parse_datetime(args.end_time)
    target_file_path = os.path.abspath(args.target_file_path)
    input_schedule_file_path = os.path.abspath(args.input_schedule_file_path)

    getLookaheadCaptureCandidates(start_time, end_time, args.hypso_number, target_file_path, input_schedule_file_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
