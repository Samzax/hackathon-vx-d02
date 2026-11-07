"""uv run python -m agente [--http [--porta 8100]]"""

import argparse
import logging

from .cliente import Torre
from .servidor import criar_servidor


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m agente", description="Servidor MCP da RegulaIA")
    p.add_argument("--http", action="store_true", help="streamable HTTP em vez de stdio")
    p.add_argument("--porta", type=int, default=8100)
    args = p.parse_args()
    logging.getLogger("httpx").setLevel(logging.WARNING)      # cada requisição à API não é notícia
    servidor = criar_servidor(Torre.do_ambiente())
    if args.http:
        servidor.run("streamable-http", host="127.0.0.1", port=args.porta)
    else:
        servidor.run("stdio")


if __name__ == "__main__":
    main()
