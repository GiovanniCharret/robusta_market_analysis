"""CLI do ROBUSTA. Uso:

    python -m robusta run                              # lista inteira do Excel
    python -m robusta run --emit-latest                # grava latest.json + latest.xlsx
    python -m robusta run --export-xlsx saida.xlsx     # export manual ad-hoc
    python -m robusta run --tickers PRIO3 ASAI3        # subconjunto so para dev/debug
    python -m robusta run --refresh-fundamentos        # forca raspagem do Fundamentus

Por padrao o universo e a lista completa de `lista_tickers_liquidos.xlsx`
(`data.ler_lista_tickers`). O `--tickers` e apenas um override de
desenvolvimento/debug — nao ha lista de tickers embutida no codigo (o legado
tinha esse override hardcoded como bug).

Por padrao os fundamentos sao raspados so no 1o dia util do mes (cache mensal
em `all_ticker_financial_indicators.xlsx`). `--refresh-fundamentos` ignora a
regra e raspa imediatamente — util para mudanca de ticker, divulgacao de
resultados ou conferencia manual de valores.

`--emit-latest CAMINHO` grava `latest.json` + `latest.xlsx` na pasta indicada
(default: `~/robusta/var/`), usando o modulo `persistence`. E o que o cron
chama em producao.

Roda chamadas de rede reais (Yahoo Finance + Fundamentus) e pode sofrer
rate-limit.
"""

import argparse
import logging
from pathlib import Path

from robusta import data, persistence, pipeline

logger = logging.getLogger(__name__)


def _comando_run(args):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Default: lista inteira de lista_tickers_liquidos.xlsx. --tickers e so
    # um subconjunto opcional para dev/debug.
    universo = args.tickers or data.ler_lista_tickers()
    resultado = pipeline.executa_pipeline(
        universo,
        forcar_raspagem_fundamentos=args.refresh_fundamentos,
        debug_fundamentos=args.debug_fundamentos,
    )

    print(
        f"run_id={resultado.run_id} "
        f"tickers_ok={resultado.summary['tickers_ok']} "
        f"tickers_failed={resultado.summary['tickers_failed']}"
    )
    if resultado.failed_tickers:
        print("falhas:", ", ".join(f["ticker"] for f in resultado.failed_tickers))

    if args.export_xlsx:
        resultado.merged_results.to_excel(args.export_xlsx, index=False)
        print(f"merged exportado para {args.export_xlsx}")

    if args.emit_latest is not None:
        # `--emit-latest` sem argumento usa o default; com argumento usa o caminho.
        pasta = Path(args.emit_latest) if args.emit_latest else Path.home() / "robusta" / "var"
        persistence.grava_latest(resultado, pasta)
        print(f"latest.json + latest.xlsx gravados em {pasta}")


def construir_parser():
    parser = argparse.ArgumentParser(
        prog="robusta", description="ROBUSTA - screener da B3 (rebuild)"
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_run = sub.add_parser("run", help="Roda o pipeline completo")
    p_run.add_argument(
        "--tickers", nargs="*",
        help="DEV/DEBUG: subconjunto de tickers base (ex: PRIO3 ASAI3). "
             "Sem a flag, roda a lista inteira de lista_tickers_liquidos.xlsx.",
    )
    p_run.add_argument(
        "--export-xlsx", metavar="CAMINHO",
        help="Exporta o DataFrame merged para um .xlsx ad-hoc (opt-in).",
    )
    p_run.add_argument(
        "--refresh-fundamentos", action="store_true",
        help="Forca raspagem do Fundamentus mesmo fora do 1o dia util do mes.",
    )
    p_run.add_argument(
        "--debug-fundamentos", action="store_true",
        help="DEBUG: imprime URL/tabelas/colunas por ticker e traceback completo "
             "em caso de falha do scrape. Implica --refresh-fundamentos.",
    )
    p_run.add_argument(
        "--emit-latest", nargs="?", const="", default=None, metavar="PASTA",
        help="Grava latest.json + latest.xlsx para o frontend consumir. "
             "Sem argumento: ~/robusta/var/. Com argumento: usa o caminho.",
    )
    p_run.set_defaults(func=_comando_run)
    return parser


def main(argv=None):
    parser = construir_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
