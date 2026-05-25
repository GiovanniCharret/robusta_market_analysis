"""CLI minimo do ROBUSTA (fatia antecipada da Fase 8).

Permite rodar o pipeline de ponta a ponta e, opcionalmente, exportar o
DataFrame merged para xlsx (opt-in via flag, conforme o PLAN: export Excel so
atras de flag explicita). Uso:

    python -m robusta run                          # roda a lista INTEIRA do Excel
    python -m robusta run --export-xlsx saida.xlsx
    python -m robusta run --tickers PRIO3 ASAI3    # subconjunto so para dev/debug
    python -m robusta run --refresh-fundamentos    # forca raspagem do Fundamentus

Por padrao o universo e a lista completa de `lista_tickers_liquidos.xlsx`
(`data.ler_lista_tickers`). O `--tickers` e apenas um override de
desenvolvimento/debug — nao ha lista de tickers embutida no codigo (o legado
tinha esse override hardcoded como bug).

Por padrao os fundamentos sao raspados so no 1o dia util do mes (cache mensal
em `all_ticker_financial_indicators.xlsx`). `--refresh-fundamentos` ignora a
regra e raspa imediatamente — util para mudanca de ticker, divulgacao de
resultados ou conferencia manual de valores.

Roda chamadas de rede reais (Yahoo Finance + Fundamentus) e pode sofrer
rate-limit. A CLI completa (`run`/`api`/`schedule`) e os logs definitivos sao
da Fase 8.
"""

import argparse
import logging

from robusta import data, pipeline

logger = logging.getLogger(__name__)


def _comando_run(args):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Default: lista inteira de lista_tickers_liquidos.xlsx. --tickers e so
    # um subconjunto opcional para dev/debug.
    universo = args.tickers or data.ler_lista_tickers()
    resultado = pipeline.executa_pipeline(
        universo, forcar_raspagem_fundamentos=args.refresh_fundamentos
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
        help="Exporta o DataFrame merged para um .xlsx (opt-in).",
    )
    p_run.add_argument(
        "--refresh-fundamentos", action="store_true",
        help="Forca raspagem do Fundamentus mesmo fora do 1o dia util do mes "
             "(ex: mudanca de ticker, divulgacao de resultados, conferencia).",
    )
    p_run.set_defaults(func=_comando_run)
    return parser


def main(argv=None):
    parser = construir_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
