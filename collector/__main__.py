"""Uso: python -m collector 2026-08-04 [2026-08-05 ...]

Também aceita um intervalo: python -m collector 2026-08-01..2026-08-07
Lê apenas o que já está em cache/; não acessa a rede.
"""

import sys
from datetime import date, timedelta

from .dou import collect_day, save_day


def _days(args: list[str]):
    for arg in args:
        if ".." in arg:
            start, end = (date.fromisoformat(x) for x in arg.split(".."))
            while start <= end:
                yield start
                start += timedelta(days=1)
        else:
            yield date.fromisoformat(arg)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    for day in _days(argv):
        result = collect_day(day)
        if not result.total:
            print(f"{day}: nada em cache")
            continue
        path = save_day(result)
        print(result.funnel())
        for act in result.normative:
            print(f"    {act.identifica} | {act.ementa[:110]}")
        print(f"    -> {path.relative_to(path.parents[2])}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
