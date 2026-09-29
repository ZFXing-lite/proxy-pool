"""
CLI 命令行工具
"""
import argparse
import sys
import json


def main():
    parser = argparse.ArgumentParser(
        prog="proxy-pool",
        description="多源公开代理 IP 池工具",
    )
    sub = parser.add_subparsers(dest="command")

    # fetch
    p_fetch = sub.add_parser("fetch", help="抓取并验证代理")
    p_fetch.add_argument("--validate", action="store_true", help="验证代理可用性")
    p_fetch.add_argument("--timeout", type=int, default=5, help="验证超时(秒)")

    # serve
    p_serve = sub.add_parser("serve", help="启动 API 服务")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)

    # export
    p_export = sub.add_parser("export", help="导出代理列表")
    p_export.add_argument("--format", choices=["txt", "json", "csv"], default="txt")
    p_export.add_argument("-o", "--output", default=None, help="输出文件")
    p_export.add_argument("--protocol", default=None)

    # stats
    sub.add_parser("stats", help="查看代理池统计")

    # get
    p_get = sub.add_parser("get", help="获取代理")
    p_get.add_argument("--count", type=int, default=1)
    p_get.add_argument("--protocol", default=None)
    p_get.add_argument("--strategy", choices=["random", "round_robin", "fastest"], default="random")

    args = parser.parse_args()

    if args.command == "fetch":
        from .core import ProxyPool
        print("正在抓取代理...")
        pool = ProxyPool(auto_fetch=False)
        result = pool.refresh(validate=args.validate)
        print(f"抓取: {result['fetched']} 个代理")
        if args.validate:
            print(f"可用: {result['alive']} 个")
        print(f"耗时: {result['elapsed_seconds']}s")

    elif args.command == "serve":
        import uvicorn
        print(f"启动 API 服务: http://{args.host}:{args.port}")
        uvicorn.run("proxy_pool.api:app", host=args.host, port=args.port, reload=False)

    elif args.command == "export":
        from .core import ProxyPool
        pool = ProxyPool(auto_fetch=False)
        data = pool.export(protocol=args.protocol, fmt=args.format)
        if args.output:
            with open(args.output, "w") as f:
                f.write(data)
            print(f"已导出到 {args.output}")
        else:
            print(data)

    elif args.command == "stats":
        from .core import ProxyPool
        pool = ProxyPool(auto_fetch=False)
        s = pool.stats()
        print(json.dumps(s, indent=2, ensure_ascii=False))

    elif args.command == "get":
        from .core import ProxyPool
        pool = ProxyPool(auto_fetch=False)
        proxies = pool.get_proxies(count=args.count, protocol=args.protocol, strategy=args.strategy)
        for p in proxies:
            print(f"{p.protocol}://{p.address}  latency={p.latency}s  source={p.source}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
