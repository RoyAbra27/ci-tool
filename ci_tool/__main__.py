import argparse
import json

from ci_tool.run import run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ci_tool")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="ingest once; replay from cache by default, --live fetches")
    run_p.add_argument("--live", action="store_true", help="fetch from the network and update the raw cache")
    run_p.add_argument("--summary", action="store_true", help="human-readable output instead of JSON")
    run_p.add_argument("--config", default="config.toml")
    args = parser.parse_args(argv)

    report = run(live=args.live, config_path=args.config)
    if args.summary:
        print(f"run {report['run_id']} ({report['mode']})")
        for sid, status in report["sources"].items():
            print(f"  {sid:28s} {status}")
        for name, value in report["counters"].items():
            print(f"  {name:28s} {value}")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
