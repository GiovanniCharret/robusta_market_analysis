"""Analise tecnica do ROBUSTA.

As funcoes deste modulo recebem um DataFrame OHLCV (ja baixado por
`robusta.data`) e devolvem o mesmo DataFrame acrescido das colunas que cada
fase do `planning/PLAN.md` (T1 a T7) prescreve. Cada funcao preserva a
assinatura e o tipo de retorno do legado em `main.py`, para que a comparacao
contra o baseline em `tests/baseline/COLUMN_SCHEMA.md` seja coluna a coluna.
"""

import logging

import numpy as np
import pandas as pd
from tqdm import tqdm

from robusta import config, data

logger = logging.getLogger(__name__)


def crie_variacao(stock_data, info):
    """Acrescenta ao DataFrame uma coluna de variacao percentual (pct_change).

    - `info == 1`: variacao da coluna `Close`, gravada em `Return`.
    - `info == 2`: variacao da coluna `Momentum`, gravada em `Oscillation`.

    O fluxo principal do screener usa apenas `info == 1` (ver
    `extrai_cotacoes` no legado). O caminho `info == 2` e preservado para
    manter o contrato da assinatura original.
    """
    if info == 1:
        coluna_destino = "Return"
        coluna_fonte = "Close"
    elif info == 2:
        coluna_destino = "Oscillation"
        coluna_fonte = "Momentum"
    else:
        raise ValueError(f"info deve ser 1 ou 2; recebido: {info!r}")

    stock_data[coluna_destino] = stock_data[coluna_fonte].pct_change()
    return stock_data


def crie_medias_moveis(stock_data, lista_args):
    """Acrescenta tres colunas por janela de media movel em `lista_args`.

    Para cada `n` em `lista_args` (normalmente `config.MMA_WINDOWS`):
      - `MMA{n}` — media movel aritmetica de `Close` na janela `n`.
      - `Position_MMA{n}` — `1` se `Close > MMA{n}`, `-1` caso contrario, e
        `0` enquanto a janela nao tem dados suficientes (`MMA{n}` e NaN).
      - `%_to_MMA{n}` — distancia percentual de `Close` ate a MMA, em %.

    Contrato preservado do legado (`main.py:345-362`): `Close == MMA` cai no
    ramo `-1` (o legado usa `>` estrito), e a coluna `%_to_MMA{n}` permanece
    NaN onde `MMA{n}` e NaN.
    """
    for n in lista_args:
        coluna_mma = f"MMA{n}"
        stock_data[coluna_mma] = stock_data["Close"].rolling(window=n).mean()

        stock_data[f"Position_MMA{n}"] = np.where(
            pd.notnull(stock_data[coluna_mma]),
            np.where(stock_data["Close"] > stock_data[coluna_mma], 1, -1),
            0,
        )

        stock_data[f"%_to_MMA{n}"] = (
            (stock_data["Close"] - stock_data[coluna_mma]) / stock_data[coluna_mma]
        ) * 100

    return stock_data


def calcule_volatilidade_anualizada_std(dados, vol_window):
    """Acrescenta `vol_anualized_{vol_window}days` ao DataFrame.

    Volatilidade anualizada por **desvio-padrao simples** dos retornos
    diarios numa janela movel de `vol_window` dias, anualizada por
    `sqrt(252)` (numero de pregoes em um ano). Daqui o sufixo `_std` no
    nome: distingue de outras estimativas de volatilidade (GARCH, EWMA,
    Parkinson, ...) que podem entrar em fases futuras.

    Espera a coluna `Return` ja criada por `crie_variacao(..., info=1)`.

    Contrato preservado do legado (`main.py:471-486`): a docstring legada
    chamava `Return` de "retorno logaritmico", mas o pipeline gera `Return`
    via `pct_change` (retorno simples). Mantemos o calculo como esta — a
    troca para log-return e mudanca de metodologia, nao de porte.
    """
    coluna_destino = f"vol_anualized_{vol_window}days"
    dados[coluna_destino] = dados["Return"].rolling(window=vol_window).std() * np.sqrt(252)
    return dados


def alto_volume_persistente(df):
    """Acrescenta a coluna `Alto_volume_persistente` com sinais -1, 0 ou 1.

    Marca como volume alto persistente:
      - **1** quando, por `k` dias consecutivos, o volume diario fica acima
        de `volume_multiplier x` a media movel de volume **e** o `Close`
        subiu nos ultimos `k` dias (`Close.pct_change(k) > 0`);
      - **-1** mesma condicao mas com `Close` caindo (`pct_change(k) < 0`);
      - **0** nos demais casos (sem streak, ou pct_change zero/NaN).

    Parametros internos preservados do legado (`main.py:438-469`):
      - `volume_window = 20` — janela da media movel de volume.
      - `volume_multiplier = 2` — quantas vezes a media e considerada "alto".
      - `k = 2` — dias consecutivos exigidos.

    O nome da coluna final e `Alto_volume_persistente` (esta no baseline).
    A docstring legada mencionava um nome parametrizado
    `Alto_volume_{multiplier}_p{k}d_?value` que nunca foi de fato gerado.
    """
    volume_window = 20
    volume_multiplier = 2
    k = 2

    vol_ma = df["Volume"].rolling(volume_window, min_periods=volume_window).mean()

    hv_flag = (df["Volume"] >= vol_ma * volume_multiplier).astype(int)
    hv_streak = hv_flag.rolling(k).sum() == k

    ret = df["Close"].pct_change(k)
    price_up = ret > 0
    price_down = ret < 0

    df["Alto_volume_persistente"] = np.select(
        [hv_streak & price_down, hv_streak & price_up],
        [-1, 1],
        default=0,
    )

    return df


def add_price_concentration_levels_by_me(df):
    """Acrescenta 8 colunas de suporte/resistencia (`*_by_mslf`) ao DataFrame.

    Mede concentracao de precos ("most significant levels found"): arredonda
    os edges de candle a 1 casa, conta repeticoes de High/Low/Adj Close e
    cria ate 3 suportes abaixo e 3 resistencias acima do ultimo Adj Close,
    mais um score de desvio (`std_raking_value_by_mslf`) e um sinal de
    rompimento (`momentum_break_by_mslf`).

    Corrige o bug B1 do legado (`main.py:718-725`, ver
    `tests/baseline/COLUMN_SCHEMA.md`): as 8 atribuicoes finais usavam `:` no
    lugar de `=`, virando anotacoes no-op (PEP 526) — as colunas nunca eram
    criadas, embora a funcao ja retornasse `df`. Os nomes (incluindo o typo
    `raking` em `std_raking_value_by_mslf`) sao preservados porque estao no
    baseline. Niveis inexistentes viram os sentinelas "Abismo"/"Foguete".
    """
    df_copy = df.copy()
    # price_today usa o df original (nao arredondado).
    price_today = df["Adj Close"].iloc[-1]

    # Arredonda os edges para reduzir a quantidade de niveis candidatos.
    # Arredondamos coluna a coluna para nao pegar a coluna Date (datetime) que
    # vem do reset_index em extrai_cotacoes — round(1) no DataFrame inteiro
    # dispara UserWarning benigno do pandas.
    for col in ("High", "Low", "Adj Close"):
        df_copy[col] = df_copy[col].round(1)
    q_high = df_copy["High"].value_counts(dropna=False)
    q_low = df_copy["Low"].value_counts(dropna=False)

    # Para cada edge, quantas vezes ele aparece como High/Low/Close (lado high).
    df_copy["quant_high"] = df_copy["High"].map(q_high).astype(float)
    df_copy["quant_low_apply_map_high"] = df_copy["Low"].map(q_high).fillna(0).astype("int64")
    df_copy["quant_close_apply_map_high"] = df_copy["Adj Close"].map(q_high).fillna(0)
    df_copy["sum_edges_by_map_high"] = (
        df_copy["quant_high"]
        + df_copy["quant_low_apply_map_high"]
        + df_copy["quant_close_apply_map_high"]
    )

    # Repete pelo lado low.
    df_copy["quant_low"] = df_copy["Low"].map(q_low).astype("int64")
    df_copy["quant_high_apply_map_low"] = df_copy["High"].map(q_low).fillna(0)
    df_copy["quant_close_apply_map_low"] = df_copy["Adj Close"].map(q_low).fillna(0)
    df_copy["sum_edges_by_map_low"] = (
        df_copy["quant_low"]
        + df_copy["quant_high_apply_map_low"]
        + df_copy["quant_close_apply_map_low"]
    )

    # Edge vencedor: o lado (high ou low) com maior concentracao.
    df_copy["ranking_edges"] = np.where(
        df_copy["sum_edges_by_map_high"] >= df_copy["sum_edges_by_map_low"],
        df_copy["sum_edges_by_map_high"],
        df_copy["sum_edges_by_map_low"],
    )
    df_copy["winner_value_edge"] = np.where(
        df_copy["sum_edges_by_map_high"] >= df_copy["sum_edges_by_map_low"],
        df_copy["High"],
        df_copy["Low"],
    )

    # Classifica cada nivel por faixa de desvio (tabela normal: 68/95/99).
    p68 = df_copy["ranking_edges"].quantile(0.68)
    p95 = df_copy["ranking_edges"].quantile(0.95)
    p99 = df_copy["ranking_edges"].quantile(0.99)

    def classificar(valor):
        if valor < p68:
            return 0
        elif valor < p95:
            return 1
        elif valor < p99:
            return 2
        else:
            return 3

    df_copy["std_ranking_edges"] = df_copy["ranking_edges"].apply(classificar)

    # Uma linha por nivel de preco; remove repeticoes de winner_value_edge.
    top_rows = df_copy.drop_duplicates(subset="winner_value_edge", keep="first")

    # Mantem niveis com desvio > 0, garantindo o menor e o maior nivel.
    df_winner_ranking_level = top_rows[top_rows["std_ranking_edges"] > 0]
    df_sorted = top_rows.loc[
        [top_rows["winner_value_edge"].idxmin(), top_rows["winner_value_edge"].idxmax()]
    ]
    df_winner_ranking_level = pd.concat([df_sorted, df_winner_ranking_level])

    # Tres suportes abaixo e tres resistencias acima do ultimo Adj Close.
    below = (
        df_winner_ranking_level[df_winner_ranking_level["winner_value_edge"] < price_today]
        .sort_values("winner_value_edge", ascending=False)
        .head(3)
    )
    above = (
        df_winner_ranking_level[df_winner_ranking_level["winner_value_edge"] > price_today]
        .sort_values("winner_value_edge", ascending=True)
        .head(3)
    )

    max_std_ranking_edges = max(
        pd.to_numeric(below["std_ranking_edges"], errors="coerce").max(),
        pd.to_numeric(above["std_ranking_edges"], errors="coerce").max(),
    )

    below_vals = below["winner_value_edge"].tolist()
    above_vals = above["winner_value_edge"].tolist()

    # Sem nivel suficiente vira sentinela: "Abismo" abaixo, "Foguete" acima.
    while len(below_vals) < 3:
        below_vals.append("Abismo")
    while len(above_vals) < 3:
        above_vals.append("Foguete")

    # below estava decrescente; inverte para ir do mais distante ao mais proximo.
    below_vals = list(reversed(below_vals))

    # Momentum break: quao perto o ticker esta de romper o limite dos 12 meses.
    if above_vals.count("Foguete") >= 2:
        momentum_break = 1
    elif below_vals.count("Abismo") >= 2:
        momentum_break = -1
    else:
        momentum_break = 0

    # B1 corrigido: `=` no lugar de `:`. Escalares sao broadcast a todas as linhas.
    df["sup_min_by_mslf"] = below_vals[0]
    df["sup_med_by_mslf"] = below_vals[1]
    df["sup_max_by_mslf"] = below_vals[2]
    df["res_min_by_mslf"] = above_vals[0]
    df["res_med_by_mslf"] = above_vals[1]
    df["res_max_by_mslf"] = above_vals[2]
    df["std_raking_value_by_mslf"] = max_std_ranking_edges
    df["momentum_break_by_mslf"] = momentum_break

    return df


def extrai_cotacoes(ticker):
    """Baixa e enriquece o OHLCV de um ticker Yahoo (ex: `"PRIO3.SA"`).

    Devolve `False` se o download vier vazio ou se a liquidez for baixa
    (volume medio dos ultimos 30 pregoes < 10.000); caso contrario devolve
    `[ticker, stock_data]` com o DataFrame ja enriquecido por T1-T5.

    Mudancas de porte vs legado (`main.py:241-313`):
      - Removido o download incondicional de `'GOAU3'` e o segundo download
        redundante de `ticker` — eram artefatos de debug, junto com os prints.
      - O retry e o tratamento de `YFRateLimitError` agora vivem em
        `data.baixa_cotacoes_yahoo` (Fase 2); aqui um download esgotado chega
        como DataFrame vazio e cai no mesmo caminho de falha.
      - Sem efeitos colaterais em globais: nao popula `data_cache_backtest`
        nem `probleminhas_temp`. O caller (screener, T7) monta o handoff de
        precos e a lista de falhas a partir do retorno.
      - O guard `droplevel(0) if MultiIndex` do legado foi omitido porque
        `baixa_cotacoes_yahoo` usa `multi_level_index=False` (colunas sempre
        planas) — alem de o legado dropar do indice de linhas, nao de colunas.
    """
    stock_data = data.baixa_cotacoes_yahoo(ticker)

    if stock_data.empty:
        logger.info("%s excluido - download nao retornou dados", ticker)
        return False

    if stock_data["Volume"].tail(30).mean().item() < 10000:
        logger.info("%s excluido - volume financeiro baixo", ticker)
        return False

    # datetime index -> coluna 'Date'
    stock_data = stock_data.reset_index()
    # 'Ticker' base (sem o sufixo '.SA') na posicao 1
    stock_data.insert(1, "Ticker", ticker[:-3])

    stock_data = crie_variacao(stock_data, 1)
    stock_data = crie_medias_moveis(stock_data, config.MMA_WINDOWS)
    stock_data = calcule_volatilidade_anualizada_std(stock_data, config.VOL_WINDOW)
    stock_data = alto_volume_persistente(stock_data)
    stock_data = add_price_concentration_levels_by_me(stock_data)

    return [ticker, stock_data]


def screener(lista, carteira_automatica, probleminhas=None):
    """Roda a analise tecnica sobre `lista` (tickers base, ex: `"PRIO3"`).

    Para cada ticker: anexa o sufixo `.SA`, baixa+enriquece via
    `extrai_cotacoes`, e empilha a ultima linha (o "estado de hoje") em
    `carteira_automatica`. Tickers em `probleminhas` sao pulados; tickers
    cujo download falha (`extrai_cotacoes` -> `False`) ou que levantam erro
    sao ignorados sem interromper a varredura.

    Devolve a tupla `(carteira_automatica, precos_por_ticker)`:
      - `carteira_automatica` — DataFrame com uma linha por ticker analisado.
      - `precos_por_ticker` — `Dict[str, float]` ticker base -> ultimo `Close`.
        E o handoff explicito para a fase fundamentalista (F3), no lugar do
        global `data_cache_backtest` do legado.

    Mudancas de porte vs legado (`main.py:857-910`):
      - `probleminhas` vira parametro explicito (era global).
      - Removido o export Excel interativo (`input()` + `to_excel` para listas
        <= 2) — responsabilidade do CLI (Fase 8).
      - `tqdm` mantido (reintroduzido a pedido do usuario) para feedback
        visual no laco mais lento (download Yahoo por ticker).
      - Acumula as linhas numa lista e faz um unico `concat` no final (o legado
        declarava `frames_para_concat` mas concatenava em loop a cada ticker).
      - `except:` nu vira `except Exception` (nao engole KeyboardInterrupt).
    """
    if probleminhas is None:
        probleminhas = set()

    frames_para_concat = []
    precos_por_ticker = {}

    for ticker in tqdm(lista, desc="Yahoo Finance", unit="ticker"):
        if ticker in probleminhas:
            logger.info("%s em probleminhas - pulado", ticker)
            continue

        yf_ticker = f"{ticker}.SA"
        try:
            dados_para_analise = extrai_cotacoes(yf_ticker)
        except Exception:
            logger.warning("Erro ao calcular %s", yf_ticker, exc_info=True)
            continue

        if not dados_para_analise:
            continue

        stock_data = dados_para_analise[1]
        frames_para_concat.append(stock_data.tail(1))
        precos_por_ticker[ticker] = float(stock_data["Close"].iloc[-1])

    if frames_para_concat:
        carteira_automatica = pd.concat(
            [carteira_automatica, *frames_para_concat],
            axis=0,
            ignore_index=True,
        )

    return carteira_automatica, precos_por_ticker
