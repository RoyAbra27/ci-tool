import argparse
import json

from ci_tool.analyze import analyze
from ci_tool.env import load_env
from ci_tool.run import run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ci_tool")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, help_text in (
        ("run", "ingest once; replay from cache by default, --live fetches"),
        ("analyze", "LLM extraction stage; replay from cached responses by default"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--live", action="store_true", help="use the network and update caches")
        p.add_argument("--summary", action="store_true", help="human-readable output instead of JSON")
        p.add_argument("--config", default="config.toml")
    args = parser.parse_args(argv)

    load_env()
    stage = run if args.cmd == "run" else analyze
    report = stage(live=args.live, config_path=args.config)
    if args.summary:
        print(f"run {report['run_id']} ({report['mode']})")
        for sid, status in report.get("sources", {}).items():
            print(f"  {sid:28s} {status}")
        for name, value in report["counters"].items():
            print(f"  {name:28s} {value}")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
