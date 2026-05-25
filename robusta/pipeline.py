"""Pipeline consolidado do ROBUSTA (Fase 5 do PLAN).

Orquestra a analise tecnica (`robusta.technical`) e fundamentalista
(`robusta.fundamental`), faz o merge, o ranking cross-sectional e empacota o
resultado num `RunResult` pronto para a persistencia JSON (Fase 6).
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from robusta import config, data, fundamental, technical

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def distorions_analysys(todas_montagens):
    """Ranking cross-sectional sobre o DataFrame de todas as montagens tecnicas.

    Acrescenta tres colunas e devolve, alem do DataFrame, a media e o desvio
    padrao da volatilidade anualizada (que o legado descartava e a Fase 5
    preserva para o `summary` do JSON):
      - `%_to_MMA50_Categoria`, `%_to_MMA10_Categoria` — percentil (1..10) da
        distancia para a MMA, via `rank(pct=True)`.
      - `Vol Mês^Anual_?value` — `1` se a vol esta abaixo de (media - desvio),
        `-1` se acima de (media + desvio), `0` caso contrario.

    Porte fiel de `main.py:745-775`: o nome (com o typo "distorions") e os
    nomes das colunas sao preservados porque estao no baseline
    (`tests/baseline/COLUMN_SCHEMA.md`). Devolve `(df, {'média', 'std_vol'})`.
    """
    media = todas_montagens["vol_anualized_30days"].mean()
    std_vol = todas_montagens["vol_anualized_30days"].std()

    def categorizar_percentil(coluna):
        return (
            coluna.rank(pct=True)
            .mul(10)
            .apply(np.ceil)
            .fillna(0)
            .clip(upper=10)
            .astype(int)
        )

    todas_montagens["%_to_MMA50_Categoria"] = categorizar_percentil(
        todas_montagens["%_to_MMA50"]
    )
    todas_montagens["%_to_MMA10_Categoria"] = categorizar_percentil(
        todas_montagens["%_to_MMA10"]
    )

    todas_montagens["Vol Mês^Anual_?value"] = todas_montagens[
        "vol_anualized_30days"
    ].apply(lambda x: 1 if x < media - std_vol else (-1 if x > media + std_vol else 0))

    return todas_montagens, {"média": media, "std_vol": std_vol}


def distorted_price_analysis(todas_montagens, mma50_wgh, mma10_wgh):
    """Seleciona as maiores oportunidades de long/short por preco distorcido.

    Calcula `distortion_ranking` combinando o score fundamentalista (invertido
    em torno de 40) com a distancia categorizada as medias de 50 e 10 dias, e
    devolve os 5 maiores (long) e 5 menores (short), com as colunas
    `['Ticker', 'Subsetor', 'Major->Long', '%_to_MMA10']`.

    **Bugs corrigidos a pedido do usuario** (`main.py:778-804`):
      - Continuacao de linha: no legado as parcelas de MMA eram statements
        soltos (descartados), entao `distortion_ranking` usava so
        `(avaliacao - 40) * -1`. Agora as tres parcelas somam de fato.
      - Copy-paste: a 3a parcela usava `%_to_MMA50_Categoria` (em vez de
        `%_to_MMA10_Categoria`). Corrigido para a formula pretendida
        (MMA50 * mma50_wgh + MMA10 * mma10_wgh).
      - Removido o `to_excel` (side effect proibido no fluxo normal).

    Requer as colunas de `distorions_analysys` (`%_to_MMA50_Categoria`,
    `%_to_MMA10_Categoria`); o orquestrador garante a ordem.
    """
    todas_montagens["distortion_ranking"] = (
        (todas_montagens["avaliacao_fundamentalista"] - 40) * -1
        + todas_montagens["%_to_MMA50_Categoria"] * mma50_wgh
        + todas_montagens["%_to_MMA10_Categoria"] * mma10_wgh
    )

    top_5 = todas_montagens.nlargest(5, "distortion_ranking")
    bottom_5 = todas_montagens.nsmallest(5, "distortion_ranking")

    filtered_montagens = pd.concat([top_5, bottom_5])
    filtered_montagens = filtered_montagens[
        ["Ticker", "Subsetor", "distortion_ranking", "%_to_MMA10"]
    ]
    filtered_montagens = filtered_montagens.rename(
        columns={"distortion_ranking": "Major->Long"}
    )

    return filtered_montagens


@dataclass
class RunResult:
    """Resultado de uma execucao do pipeline, pronto para persistencia (Fase 6).

    Segura os DataFrames de cada etapa + os metadados. A conversao para
    registros JSON (NaN -> null, tipos numpy, Timestamp -> ISO) e a gravacao
    sao responsabilidade da Fase 6; aqui a Fase 5 so calcula.
    """
    schema_version: int
    run_id: str
    generated_at: str
    robusta_version: str
    input_universe: list
    summary: dict
    technical_results: pd.DataFrame
    fundamental_results: pd.DataFrame
    merged_results: pd.DataFrame
    portfolio_signals: pd.DataFrame
    warnings: list = field(default_factory=list)
    failed_tickers: list = field(default_factory=list)


def executa_pipeline(universo, momento=None, mma50_wgh=4, mma10_wgh=1):
    """Roda a analise completa para `universo` e devolve um `RunResult`.

    Etapas: tecnica (`screener`) -> fundamentos (regra mensal de cache) ->
    ranking fundamentalista -> merge -> ranking cross-sectional -> sinais de
    portfolio. Os pesos `4`/`1` reproduzem a chamada legada de
    `distorted_price_analysis`.

    `momento` (default: agora em UTC) define `run_id`/`generated_at` e a data
    usada na regra do cache de fundamentos (raspar so no 1o dia util do mes).
    """
    if momento is None:
        momento = pd.Timestamp.now(tz="UTC")
    momento = pd.Timestamp(momento)

    universo = list(universo)
    warnings = []
    failed_tickers = []

    # 1. Analise tecnica + handoff de precos.
    carteira, precos_por_ticker = technical.screener(universo, pd.DataFrame())
    for ticker in universo:
        if ticker not in precos_por_ticker:
            failed_tickers.append(
                {"ticker": ticker, "reason": "sem dados tecnicos ou baixa liquidez"}
            )

    # 2. Fundamentos: raspa so no 1o dia util do mes, senao le o cache.
    fundamentos = data.carrega_fundamentos(
        momento, raspar_fn=lambda: fundamental.varre_lista(universo)
    )

    # 3. Indicadores dependentes de preco + rankings + score + sinal.
    fundamentos = fundamental.adicione_indicadores_e_ranking(
        fundamentos, precos_por_ticker
    )

    # 4. Merge tecnica + fundamental.
    merged = carteira.merge(fundamentos, on="Ticker", how="left")

    # 5. Ranking cross-sectional (preserva media/std da volatilidade).
    merged, vol_stats = distorions_analysys(merged)

    # 6. Sinais de portfolio (top 5 long / bottom 5 short).
    portfolio_signals = distorted_price_analysis(merged, mma50_wgh, mma10_wgh)

    # Aviso para tickers analisados tecnicamente mas sem fundamentos no merge.
    sem_fundamentos = merged.loc[
        merged["avaliacao_fundamentalista"].isna(), "Ticker"
    ].tolist()
    for ticker in sem_fundamentos:
        warnings.append(f"{ticker}: sem dados fundamentalistas no merge")

    summary = {
        "tickers_ok": len(precos_por_ticker),
        "tickers_failed": len(failed_tickers),
        "vol_media": vol_stats["média"],
        "vol_std": vol_stats["std_vol"],
    }

    return RunResult(
        schema_version=SCHEMA_VERSION,
        run_id=momento.strftime("%Y-%m-%dT%H-%M-%SZ"),
        generated_at=momento.isoformat(),
        robusta_version=config.VERSION,
        input_universe=universo,
        summary=summary,
        technical_results=carteira,
        fundamental_results=fundamentos,
        merged_results=merged,
        portfolio_signals=portfolio_signals,
        warnings=warnings,
        failed_tickers=failed_tickers,
    )
