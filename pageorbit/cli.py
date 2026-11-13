import argparse

def main(argv=None):
    parser = argparse.ArgumentParser(prog="pageorbit")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("site")
    p.add_argument("--port", type=int, default=8763)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--wave", type=int, default=1)
    s = sub.add_parser("sync")
    s.add_argument("--base", required=True)
    s.add_argument("--source", required=True)
    s.add_argument("--sink", required=True)
    s.add_argument("--checkpoint", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--sink", required=True)
    v.add_argument("--expect", required=True)
    v.add_argument("--wave", type=int, default=2)
    args = parser.parse_args(argv)
    if args.cmd == "site":
        from pageorbit.site import serve
        serve(host=args.host, port=args.port, wave=args.wave)
        return 0
    if args.cmd == "sync":
        from pageorbit.sync import run_sync
        return run_sync(args)
    if args.cmd == "verify":
        from pageorbit.verify import run_verify
        return run_verify(args)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
