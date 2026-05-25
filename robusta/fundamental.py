"""Analise fundamentalista do ROBUSTA (Fase 4 do PLAN, F1-F10).

As funcoes deste modulo limpam os dados crus do Fundamentus, recalculam
indicadores dependentes de preco, ranqueiam em decis e produzem a
`avaliacao_fundamentalista`. Preservam assinatura e retorno do legado em
`main.py` para comparacao contra o baseline em `tests/baseline/COLUMN_SCHEMA.md`.
"""

import logging
from io import StringIO

import pandas as pd
from tqdm import tqdm

from robusta import config, data

logger = logging.getLogger(__name__)


def puxar_dados(url):
    """Baixa a pagina do Fundamentus e devolve a lista de tabelas (read_html).

    Delega o GET HTTP (com User-Agent) a `data.baixa_html_fundamentus`
    (Fase 2) e parseia o HTML com `pandas.read_html`, devolvendo a lista de
    DataFrames como o legado (`main.py:916-928`).
    """
    html = data.baixa_html_fundamentus(url)
    return pd.read_html(StringIO(html))


def _converte_para_numero(value):
    """Converte um valor textual do Fundamentus (formato BR) em numero.

    Regras preservadas do legado (`main.py:978-1001`):
      - `.` e separador de milhar: remove o `.`, anexa `'00'` e divide por
        100 (ex: `"1.234"` -> `1234.0`).
      - **Atencao:** a divisao por 100 ocorre mesmo sem `.` no valor; e
        comportamento do legado (metodologia), nao se altera no porte.
      - `,` e separador decimal: vira `.`.
      - `%` e descartado.
      - Se nada converter, devolve o valor original (string) — caso de
        textos como nome de setor.
    """
    try:
        if "." in value:
            value = value.replace(".", "") + "00"
        return float(value) / 100
    except ValueError:
        if "," in value:
            value = value.replace(",", ".")
        if "%" in value:
            value = value.replace("%", "")
        try:
            return float(value)
        except ValueError:
            return value


# Linhas cujo rotulo (coluna 0) e descartado: cabecalhos de secao, colunas de
# data e indicadores que a propria ROBUSTA recalcula. Regex preservadas do
# legado (`main.py:956-960`).
_PADROES_LINHAS_DESCARTADAS = (
    r"Indicadores fundamentalistas|Dados Balanço Patrimonial|"
    r"Dados demonstrativos de resultados|Empresa|Últimos 12 meses|"
    r"Últimos 3 meses|^\s*$",
    r"Oscilações|Dia|Mês|Empresa|30 dias|12 meses|"
    r"2024|2023|2022|2021|2020|2019|^\s*$",
    r"P/L|P/VP|Valor de mercado|^\s*$",
)


def formatar_tabela(tables):
    """Transforma as tabelas cruas do Fundamentus num DataFrame de uma linha.

    Consolida todos os pares chave/valor das tabelas em duas colunas (0=chave,
    1=valor), descarta cabecalhos/datas/indicadores recalculados, converte os
    valores BR em numero, transpoe (chaves viram colunas) e padroniza a chave
    do papel como `Ticker`.

    Mudancas de porte vs legado (`main.py:931-1017`):
      - **Bug B2 resolvido**: o legado renomeava `Papel` -> `ticker`
        (minusculo), divergindo do merge (`on='Ticker'`), do Excel cacheado
        e do lado tecnico. Aqui renomeamos `Papel` -> `Ticker` (maiusculo),
        unificando a chave em todo o pipeline.
      - Omitido o ramo de FII (`tables[0].iloc[0,0] == "?FII"`): era codigo
        morto e quebrado (`tables` e uma lista, sem `.drop`) e nunca rodava no
        caminho de acoes. Filtro de FII, se necessario, e decisao separada.
      - `concat` em loop trocado por acumulacao em lista + um unico `concat`.
    """
    # Consolida os pares chave/valor de todas as tabelas em colunas 0 e 1.
    pedacos = [tables[0].iloc[:, :2].copy()]
    for table in tables[1:]:
        for i in range(0, table.shape[1], 2):
            pedacos.append(
                table.iloc[:, i:i + 2].rename(columns={i: 0, i + 1: 1})
            )
    formated_table = pd.concat(pedacos, ignore_index=True)

    # O Fundamentus prefixa cada rotulo com um icone de tooltip ("?" literal)
    # vindo de `<span class="help tips">?</span>` no HTML. read_html concatena
    # esse `?` ao texto do rotulo, virando "?Papel", "?Cotacao" etc. — o que
    # quebra o rename `Papel -> Ticker` la embaixo. Removemos o `?` na fonte.
    formated_table[0] = formated_table[0].astype(str).str.lstrip("?").str.strip()

    # Descarta as linhas cujos rotulos batem com os padroes a remover.
    for padrao in _PADROES_LINHAS_DESCARTADAS:
        formated_table = formated_table.drop(
            formated_table[
                formated_table.iloc[:, 0].str.contains(padrao, na=False)
            ].index
        )

    # Limpa, indexa pela chave e converte os valores.
    formated_table.dropna(how="all", inplace=True)
    formated_table.set_index(0, inplace=True)
    formated_table[1] = formated_table[1].apply(lambda x: _converte_para_numero(str(x)))

    # Algumas paginas do Fundamentus repetem a mesma chave em secoes diferentes;
    # sem dedup, o transpose gera colunas nao-unicas e o pd.concat de varre_lista
    # quebra com InvalidIndexError. Mantemos a primeira ocorrencia (canonica).
    formated_table = formated_table[~formated_table.index.duplicated(keep="first")]

    # Transpoe (chaves viram colunas) e padroniza a chave do papel.
    formated_table = formated_table.transpose()
    formated_table.rename(columns={"Papel": "Ticker"}, inplace=True)

    return formated_table


def gera_indicadores_extras(dados_financeiro_all_tickers, precos_por_ticker):
    """Recalcula `P/L`, `P/VP` e `Dív. Líquida/Valor de mercado` com o ultimo preco.

    Esses tres indicadores dependem do preco do papel e foram descartados por
    `formatar_tabela` (o Fundamentus nao os atualiza em tempo real). Aqui sao
    refeitos a partir de `precos_por_ticker` — o handoff `Dict[str, float]`
    (ticker base -> ultimo `Close`) produzido pelo `screener` (T7).

    Mudancas de porte vs legado (`main.py:1020-1062`):
      - Recebe `precos_por_ticker` como argumento explicito, no lugar do
        global `data_cache_backtest`.
      - Le `row['Ticker']` (maiusculo, padronizado em F2) e **nao** concatena
        `.SA`: a chave do handoff ja e o ticker base.
      - `except:` nu vira `except Exception`; logging no lugar de print.

    Politica numerica preservada: `LPA`/`VPA` == 0 -> indicador = `-1e6`;
    valores arredondados a 2 casas. Um ticker sem preco (ausente do handoff)
    fica sem valuation, sem interromper o loop.
    """
    for index, row in dados_financeiro_all_tickers.iterrows():
        ticker = row["Ticker"]
        try:
            last_close_price = precos_por_ticker[ticker]

            lpa = row["LPA"]
            if lpa != 0:
                dados_financeiro_all_tickers.loc[index, "P/L"] = round(last_close_price / lpa, 2)
            else:
                dados_financeiro_all_tickers.loc[index, "P/L"] = -1e6 #Esse número paraPod o cálculo quebra porque divide por 0 o LPA

            nro_acoes = row["Nro. Ações"]
            div_liquida = row["Dív. Líquida"]
            valor_de_mercado = nro_acoes * last_close_price
            dados_financeiro_all_tickers.loc[index, "Dív. Líquida/Valor de mercado"] = round(
                div_liquida / valor_de_mercado, 2
            )

            vpa = row["VPA"]
            if vpa != 0:
                dados_financeiro_all_tickers.loc[index, "P/VP"] = round(last_close_price / vpa, 2)
            else:
                dados_financeiro_all_tickers.loc[index, "P/VP"] = -1e6

        except Exception:
            logger.info("Sem analise tecnica de %s. Sem dados de valuation", ticker)

    return dados_financeiro_all_tickers


def _classe_decil(serie, crescente=True):
    """Classifica uma serie numerica em decis 1..10.

    - `crescente=True` (maior melhor): maior valor -> maior classe (labels 1..10).
    - `crescente=False` (menor melhor): menor valor -> maior classe (labels 10..1).

    Protege contra universos pequenos / muitos empates: se as bordas dos
    decis colidirem (o que faria `qcut` levantar `ValueError`), cai para
    `duplicates='drop'` com rotulagem inteira, devolvendo menos de 10 classes
    em vez de quebrar. O legado (`main.py:1088,1115,1150`) usava `qcut(..., 10)`
    sem protecao e quebrava nesses casos.
    """
    labels = list(range(1, 11)) if crescente else list(range(10, 0, -1))
    try:
        return pd.qcut(serie, 10, labels=labels)
    except ValueError:
        codigos = pd.qcut(serie, 10, labels=False, duplicates="drop")
        if crescente:
            return codigos + 1
        return codigos.max() - codigos + 1


def rankeia_outros_indicadores_maior_melhor(dados_financeiro_all_tickers, *indicadores):
    """Para cada indicador "quanto maior, melhor", cria `classe {indicador}` (1..10).

    Ex: `Cres. Rec (5a)`, `ROIC`. O maior valor recebe a maior classe.

    Mudancas de porte vs legado (`main.py:1066-1091`):
      - Bug do `.fillna(0)` corrigido: o legado descartava o resultado
        (`dados[col].fillna(0)` sem atribuir); aqui ele e atribuido de volta.
      - `qcut` protegido contra empates via `_classe_decil`.
      - Prints removidos.
    """
    for indicador in indicadores:
        dados_financeiro_all_tickers[indicador] = pd.to_numeric(
            dados_financeiro_all_tickers[indicador], errors="coerce"
        )
        dados_financeiro_all_tickers[indicador] = dados_financeiro_all_tickers[indicador].fillna(0)

        dados_financeiro_all_tickers[f"classe {indicador}"] = _classe_decil(
            dados_financeiro_all_tickers[indicador]
        )

    return dados_financeiro_all_tickers


def rankeia_outros_indicadores_menor_melhor(
    dados_financeiro_all_tickers, *indicadores, bloquear_negativos=False
):
    """Para cada indicador "quanto menor, melhor", cria `classe {indicador}` (10..1).

    Unifica as duas funcoes do legado (`main.py:1094-1155`) via o parametro
    `bloquear_negativos`:
      - `False` (neg_permitido): menor valor -> maior classe, sem restricao
        de sinal. Ex: `Dív. Líquida/Valor de mercado`.
      - `True` (neg_bloqueado): valores `<= 0` sao empurrados para o fim (pior
        classe), pois um `P/L` de -15 nao pode ser melhor que um `P/L` positivo
        pequeno. Ex: `P/L`, `P/VP`, `EV / EBIT`.

    Correcoes vs legado: `.fillna(0)` agora e atribuido (era descartado em
    neg_permitido) e o `qcut` e protegido contra empates via `_classe_decil`.
    A penalizacao de negativos roda numa serie de trabalho (espelha o
    `{indicador} descarte` temporario do legado), preservando o valor real do
    indicador na coluna original.
    """
    for indicador in indicadores:
        dados_financeiro_all_tickers[indicador] = pd.to_numeric(
            dados_financeiro_all_tickers[indicador], errors="coerce"
        ).fillna(0)

        base = dados_financeiro_all_tickers[indicador]
        if bloquear_negativos:
            # valores <= 0 ganham +1e9, indo para a pior classe na inversao.
            base = base.where(base > 0, base + 1e9)

        dados_financeiro_all_tickers[f"classe {indicador}"] = _classe_decil(
            base, crescente=False
        )

    return dados_financeiro_all_tickers


# Setores que usam um conjunto de colunas distinto na avaliacao, e os dois
# conjuntos de colunas `classe ...` somadas. Preservado verbatim do legado
# (`main.py:1164-1166`) — listas, nomes e composicao sao metodologia.
_SETORES_ESPECIAIS = ["Previdência e Seguros", "Intermediários Financeiros"]
_COLUNAS_ESPECIAIS = [
    "classe P/L", "classe Cres. Rec (5a)",
    "classe Dív. Líquida/Valor de mercado", "classe P/VP",
]
_COLUNAS_GERAIS = [
    "classe P/L", "classe Cres. Rec (5a)", "classe ROIC", "classe EV / EBIT",
]


def avaliacao_fundamentalista(dados_financeiro_all_tickers):
    """Soma as colunas `classe ...` em `avaliacao_fundamentalista` (score por papel).

    Setores em `_SETORES_ESPECIAIS` (financeiros) somam `_COLUNAS_ESPECIAIS`;
    os demais somam `_COLUNAS_GERAIS`. As colunas `classe ...` devem ter sido
    criadas antes por F4/F5.

    Porte fiel do legado (`main.py:1159-1179`); apenas o print foi removido.
    """
    def soma_colunas(row):
        if row["Setor"] in _SETORES_ESPECIAIS:
            return row[_COLUNAS_ESPECIAIS].sum()
        return row[_COLUNAS_GERAIS].sum()

    dados_financeiro_all_tickers["avaliacao_fundamentalista"] = (
        dados_financeiro_all_tickers.apply(soma_colunas, axis=1)
    )
    return dados_financeiro_all_tickers


def rankeando_empresas(dados_financeiro_all_tickers):
    """Rotula, dentro de cada `Setor`, a melhor e a pior empresa por
    `avaliacao_fundamentalista`, na coluna `Posicao setorial`.

    A(s) empresa(s) com a maior avaliacao do setor recebem `'melhor'`, a(s) de
    menor recebem `'pior'`, as demais ficam `''`. Num setor de uma so empresa,
    `max == min`: ela recebe `'melhor'` e em seguida `'pior'` (a atribuicao de
    min roda por ultimo), terminando como `'pior'` — quirk preservado.

    Porte fiel de `main.py:1182-1209` (apenas print removido).
    """
    def rotula_melhor_pior(grupo):
        max_valor = grupo["avaliacao_fundamentalista"].max()
        min_valor = grupo["avaliacao_fundamentalista"].min()
        grupo.loc[grupo["avaliacao_fundamentalista"] == max_valor, "Posicao setorial"] = "melhor"
        grupo.loc[grupo["avaliacao_fundamentalista"] == min_valor, "Posicao setorial"] = "pior"
        return grupo

    dados_financeiro_all_tickers["Posicao setorial"] = ""
    dados_financeiro_all_tickers = (
        dados_financeiro_all_tickers
        .groupby("Setor", group_keys=False)
        .apply(rotula_melhor_pior)
        .reset_index(drop=True)
    )
    return dados_financeiro_all_tickers


def avaliacao_fundamentalista_analisys(dados_financeiro_all_tickers):
    """Cria o sinal de backtest `Fundamental_?value` a partir do score.

    Faixas preservadas do legado (`main.py:1211-1224`):
      - `avaliacao_fundamentalista >= 32` -> `1`
      - `avaliacao_fundamentalista <= 14` -> `-1`
      - caso contrario (15..31) -> `0`

    O nome `Fundamental_?value` (com o `?` herdado de mojibake) e mantido
    porque esta no baseline (`tests/baseline/COLUMN_SCHEMA.md`).
    """
    dados_financeiro_all_tickers["Fundamental_?value"] = (
        dados_financeiro_all_tickers["avaliacao_fundamentalista"].apply(
            lambda x: 1 if x >= 32 else (-1 if x <= 14 else 0)
        )
    )
    return dados_financeiro_all_tickers


def adicione_indicadores_e_ranking(all_ticker_financial_indicators, precos_por_ticker):
    """Orquestra a fundamentalista: F3 -> F4 -> F5 -> F6 -> F7 -> F8 e limpa `Unnamed`.

    Encadeia as fases sobre o DataFrame de fundamentos (bruto do scraper ou
    cacheado), usando `precos_por_ticker` (handoff do `screener`) para os
    indicadores dependentes de preco.

    Mudancas de porte vs legado (`main.py:1227-1261`):
      - Recebe e repassa `precos_por_ticker` a `gera_indicadores_extras` (F3),
        no lugar do global `data_cache_backtest`.
      - As duas funcoes `menor_melhor` do legado viram chamadas da unificada:
        `Dív. Líquida/Valor de mercado` com `bloquear_negativos=False`;
        `P/L`, `P/VP`, `EV / EBIT` com `bloquear_negativos=True`.
      - Conjuntos de indicadores e a remocao de colunas `Unnamed` preservados.
    """
    df = gera_indicadores_extras(all_ticker_financial_indicators, precos_por_ticker)

    df = rankeia_outros_indicadores_maior_melhor(df, "Cres. Rec (5a)", "ROIC")
    df = rankeia_outros_indicadores_menor_melhor(df, "Dív. Líquida/Valor de mercado")
    df = rankeia_outros_indicadores_menor_melhor(
        df, "P/L", "P/VP", "EV / EBIT", bloquear_negativos=True
    )

    df = avaliacao_fundamentalista(df)
    df = rankeando_empresas(df)
    df = avaliacao_fundamentalista_analisys(df)

    # Remove colunas 'Unnamed' geradas no IO do Excel.
    cols_to_drop = df.filter(like="Unnamed").columns
    df = df.drop(columns=cols_to_drop)

    return df


def varre_lista(lista, probleminhas=None):
    """Raspa o Fundamentus para cada ticker da lista e consolida num DataFrame.

    Para cada ticker base: monta a URL (`config.FUNDAMENTUS_URL_BASE + ticker`),
    baixa via `puxar_dados` (F1) e limpa via `formatar_tabela` (F2), acumulando
    a linha resultante. Tickers em `probleminhas` sao pulados; falhas de
    download/parse sao logadas e ignoradas sem interromper a varredura.

    Mudancas de porte vs legado (`main.py:1264-1324`):
      - `probleminhas` vira parametro (era global); `probleminhas_temp` removido.
      - `url_financials` global -> `config.FUNDAMENTUS_URL_BASE`.
      - Acumulacao em lista + um unico `pd.concat` no final, no lugar do
        preenchimento manual via `.loc[ticker_contador, ...]` (que descartava
        colunas ausentes no primeiro ticker e tinha um `except` quebrado
        referenciando `tables` indefinido). O `concat` unifica as colunas.
      - `except:` nus viram `except Exception` com logging.
      - `tqdm` mantido (reintroduzido a pedido do usuario) para feedback
        visual no laco mais lento (HTTP por ticker no Fundamentus).
    """
    if probleminhas is None:
        probleminhas = set()

    linhas = []
    for ticker in tqdm(lista, desc="Fundamentus", unit="ticker"):
        if ticker in probleminhas:
            logger.info("%s em probleminhas - pulado", ticker)
            continue

        try:
            tables = puxar_dados(config.FUNDAMENTUS_URL_BASE + ticker)
            indicadores = formatar_tabela(tables)
        except Exception:
            logger.warning("Erro ao raspar/parsear %s", ticker, exc_info=True)
            continue

        # Pagina do Fundamentus sem 'Papel' (ticker inexistente, redirect ou
        # layout quebrado): sem a chave do papel, a linha contamina o
        # concat e quebra `gera_indicadores_extras` (KeyError: 'Ticker').
        if "Ticker" not in indicadores.columns:
            logger.warning(
                "%s: pagina do Fundamentus sem 'Papel' - ticker pulado", ticker
            )
            continue

        linhas.append(indicadores)

    if not linhas:
        return pd.DataFrame()

    return pd.concat(linhas, ignore_index=True)

