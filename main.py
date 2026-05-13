
"""
### ROBUSTA - 13 - Reborn Stronger
"""

import yfinance
import requests
from bs4 import BeautifulSoup
import re
from numpy import percentile, sign, amax, amin, arange, where, random, log, exp, inf, where, select, sqrt, ceil, linspace, digitize, bincount, argsort, nan, nansum, maximum
import pandas
# Setup
#pandas.set_option('future.no_silent_downcasting', True)
from pandas.tseries.offsets import BDay, MonthBegin
from pandas.tseries.holiday import AbstractHolidayCalendar, Holiday, USFederalHolidayCalendar
#from datetime import datetime
from datetime import datetime, timedelta
#from sklearn.linear_model import LinearRegression
#import itertools
from tqdm import tqdm  # Biblioteca para mostrar uma barra de progresso
#from icecream import ic
#import ast # converter str para dict
from io import StringIO
#import schedule
import time


# Whatsapp
#from twilio.rest import Client

"""## História"""

# Após usar o stock concentration da IA, criei mnhha própria lógica que tem muita aderência com minha intuição de valor.
# veremos se ela é util mesmo.
# Melhorei a lógica da Robusta 12.2 utilizando uma coluna de valoração das edges (se estão 0, 1, 2 ou dois desvios)
# e criei os limites automaticos para colocar no screeening

"""### Versão"""

# O que essas versão faz?

# Ainda nada novo. Se a minha lógica bater a da IA, eu substituo o algoritmo central

versao = "13"

"""### Funções Gerais e Administrativas"""

def configurar_data(data_ajuste, ano=0, mes=0, dia=1):

    adjusted_date = data_ajuste - pandas.DateOffset(years=ano, months=mes, days=dia)

    return adjusted_date

def ler_todos_tickers():
    #return pandas.read_excel('lista_tickers_corrigido.xlsx') # Quando quiser rodar todos
    return pandas.read_excel('lista_tickers_liquidos.xlsx') # Rodar só os mais líquidos


def first_day_alert(date):
    """
    Função retorna true se hoje for o primeiro bussiness day
    """

    # Encontre o primeiro dia do mês atual
    primeiro_dia_do_mes = pandas.offsets.MonthBegin().rollback(hoje)

    # Vá para o próximo dia útil
    primeiro_dia_util = primeiro_dia_do_mes + BDay(0)

    # Verifique se a data atual é igual ao primeiro dia útil do mês
    if hoje == primeiro_dia_util:
        return True

    return False

def find_latest_market_days(total_days):
    """
    Lista as datas de operação do mercado.
    Importante para o backtest conseguir calcular corretamente 5, 10, 15 e 20 dias pois as datas de negociação não seguirem um padrão perfeitamente regular.
    """
    # Baixando os dados do BOVA11
    ticker = yfinance.download('BOVA11.SA', progress=False, period='1y', auto_adjust=False,)

    # Obtendo as últimas 60 datas e convertendo para string
    latest_market_days = ticker.tail(total_days).index.strftime('%Y-%m-%d').tolist()

    return latest_market_days

def alerta_final_do_mes():
    '''
    Final de mês tem oscilações técnicas de fluxo
    '''

    ultimo_dia_do_mes = hoje + pandas.tseries.offsets.MonthEnd(0)
    dois_dias_uteis_antes = ultimo_dia_do_mes - BDay(2)

    if hoje >= dois_dias_uteis_antes:

        return f'Final de Mês. Estresse na Posição'

    return False

def release_date_alert(df):


    df['Alerta'] = df['Data de Divulgação de resultados'].apply(lambda x: 'Inverter posição. Publicação de Resultado'
                                                if 0 < (x - hoje).days < 2 else f'Robust_{versao}')

    return df

"""### Todos os parâmetros"""

# Datas
hoje = pandas.Timestamp.now()
data_formatada = hoje.date()
# Obtém a data e hora atuais
now = datetime.now()


# Calendário 2025
class CustomHolidayCalendar(AbstractHolidayCalendar):
    rules = [
        Holiday("Ano Novo", month=1, day=1),
        Holiday("Carnaval", month=3, day=3),
        Holiday("Carnaval", month=3, day=4),
        Holiday("Paixão de Cristo", month=4, day=18),
        Holiday("Tiradentes", month=4, day=21),
        Holiday("Dia do Trabalho", month=5, day=1),
        Holiday("Corpus Christi", month=6, day=19),
        Holiday("Independência do Brasil", month=9, day=7),
        Holiday("Nossa Sra. Aparecida", month=10, day=12),
        Holiday("Finados", month=11, day=2),
        Holiday("Proclamação da República", month=11, day=15),
        Holiday("Consciência Negra", month=11, day=20),
        Holiday("Natal", month=12, day=25),
    ]

# Criar um índice de feriados
feriados = CustomHolidayCalendar().holidays(start='2024-01-01', end='2030-12-31')

# Formata a hora no formato "hh:mm"
hora_formatada = now.strftime("%H:%M")

# A data de início do download do dataframe
data_inicio = configurar_data(hoje, 5, 0, 0)

# Funções de backtest --------------------
# Dias de retrocesso
# 15 dias por causa do modelo que analisa últimas 5 variações dos últimos 10 dias. Total 15. +1 dia porque a função mme trabalha com iloc[-2]. Então o laço precisa de 2 linhas para não quebrar
total_days_backtest = 16

# Encontrar a data de inicio
backtest_inicial = hoje - BDay(total_days_backtest + 1)

# Últimas 60 datas de negociação do mercado
latest_market_days = find_latest_market_days(60)

# Ações
# Lista de tickers que darão problemas
probleminhas = ['MBLY3.SA','CCRO3','ATMP3','ALPA3.SA',
               ]

probleminhas = set(probleminhas)

probleminhas_temp = [] # Antes de mandar para o registro definitivo, cai aqui


# Setup técnico
# Listas de MMA (Médias móveis Aritméticas)
mma_list = 9, 10, 26, 50, 150, 200

# Volatilidade Anualizada
mes_anualized_vol = ['30']

# Lista de ATRs
atr_windows = [5 , 14]

# Tolerâncias
# de perda
tolerancia_perda = 0.05
# Introduzir um fator de desvio para determinar sinais significativos
tolerancia_erro = 0.005

# Window de atr_stops e RSI (14 dias porque é o padrão de mercado)
stop_atr = 14
rsi_window = stop_atr

# Macro
# Lista
macro = ['^TNX']

# Setup
"""
Por que não usa só uma variável em macro e técnico? Porque o backtest fica muito grande e
perde a função primordial, além de ficar muito pesado
"""
macro_mma_list = [200] # Listas de MMA
macro_momentum_list = [10, 20] # Lista de Momentum


# Strings de nomes e endereços
# NomeS que completarão o arquivo
nome_versao = f'Robust {versao}'
nome_arquivo = f'all_ticker_total_analisys_{data_formatada}'
# URLs para informações fundamentalistas
url_release_dates = "https://www.empiricus.com.br/artigos/investimentos/agenda-de-resultados-4t23-divulgacao-calendario-temporada-balancos-4t2023-quarto-trimestre-2023/"
# https://www.moneytimes.com.br/agenda-de-resultados-do-4t23-veja-datas-e-o-que-esperar-dos-balancos-das-empresas-da-b3/

# Indicadores Financeiros
url_financials = f'https://www.fundamentus.com.br/detalhes.php?papel='

# DFs, Listas e Dicionários
carteira_automatica = pandas.DataFrame()

# Cria um dicionário para armazenar os dados já buscados
data_cache_backtest = {}
# Datas de publicações de resultados
all_ticker_release_dates = None
# Lista para armazenar os resultados temporários
resultados_temp_backtest = []

# Auths Twilio
#account_sid = 'AC21eeeaea36979f94ef43da089a11001f'
#auth_token = 'aed7022684336fa1045a4a330217a5e1'

TWILIO_ACCOUNT_SID='AC21eeeaea36979f94ef43da089a11001f'
TWILIO_AUTH_TOKEN='aed7022684336fa1045a4a330217a5e1'
#TWILIO_WHATSAPP_FROM=whatsapp:+5521995159373
#TWILIO_WHATSAPP_TO=whatsapp:+5521995159373  # valor padrão se não houver coluna 'contato'
#client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Evitando Unboundlocarlerror quando a consulta ao primeiro ticker volta falso
dados_para_analise = None

"""### Bloco Técnico

#### extrai_cotacoes, crie_variacao, crie_medias_moveis, calculate_obv,calcule_exaustao_atr
"""

# Bloco Dataset fonte
def extrai_cotacoes(ticker):
    """


    """
    stock_data = yfinance.download('GOAU3')

    print(stock_data)
    for attempt in range(5): # Multiplas tentativas de download

        try:
            stock_data = yfinance.download(ticker)
            print(stock_data)
            stock_data = yfinance.download(
                ticker,
                progress=False,
                start=data_inicio,
                auto_adjust=False,
                multi_level_index=False)

        except YFRateLimitError:

            wait = 2 ** attempt
            print(f"Rate limit atingido, aguardando {wait}s antes da próxima tentativa")
            time.sleep(wait)


    # se o método download retornar vazio, encerrar a função
    if stock_data.empty:
        print(f'{ticker} Excluído - Não retornou dados')
        probleminhas_temp.append(ticker)
        return False

    # Verificar se o volume médio dos últimos 30 dias é menor que 10.000
    if stock_data['Volume'].tail(30).mean().item() < 10000:
        print(f'{ticker} Excluído - Volume financeiro')
        probleminhas_temp.append(ticker)
        return False

    else:

        # Isso resolve o problema de MultiIndex ao remover o primeiro nível do índice de colunas,
        #garantindo que stock_data['Close'] seja uma Series e não um DataFrame.
        stock_data = stock_data.droplevel(0) if isinstance(stock_data.columns, pandas.MultiIndex) else stock_data

        # Biblioteca que será utilizada pela análise fundamentalista
        data_cache_backtest[ticker] = stock_data.loc[backtest_inicial:]

        # 1) transforma o índice datetime em coluna 'Date'
        stock_data = stock_data.reset_index()

        # 2) insere a coluna 'Ticker' como segunda coluna (posição 1)
        stock_data.insert(1, 'Ticker', f'{ticker[:-3]}')

        # adicionar coluna de variação do ticker
        stock_data = crie_variacao(stock_data, 1)
        # adicionar colunas de médias móveis
        stock_data = crie_medias_moveis(stock_data, mma_list)

        # adicionar volatilidade anualizada
        stock_data = calcule_volatilidade_anualizada(stock_data, 30) # 30 porque são os dias que mais se assemelham  ao utilizado pelo mercado de derivativos
        stock_data = alto_volume_persistente(stock_data)

        # Calculando o OBV
        #stock_data = calculate_obv(stock_data)
        #stock_data = calcule_exaustao_atr(stock_data)

        # Calcula suportes e resistências últimos 180 dias
        #stock_data = add_price_concentration_levels(stock_data)

        stock_data = add_price_concentration_levels_by_me(stock_data)

        return [ticker, stock_data]


# Cálculos
def crie_variacao(stock_data, info): #recebe o dataframe
    '''
    Utilizo a função para processar mais de uma coluna

    info - Qual coluna o código deve processar?

    1 - Variação da coluna Close
    2 - Variação da coluna Momentum
    '''

    if info == 1:

        info_out = 'Return'
        info_in = 'Close'

    elif info == 2:

        info_out = 'Oscillation'
        info_in = 'Momentum'



    # adiciona coluna de variação
    stock_data[info_out] = stock_data[info_in].pct_change()

    # retorna o dataframe
    return stock_data

def crie_medias_moveis(stock_data, lista_args): #recebe o dataframe e as médias para cálculo

    for i in lista_args:

        # 1 - adiciona uma coluna extra no dataset com os dados da mma
        stock_data[f'MMA{i}'] = stock_data['Close'].rolling(window=i).mean()

        # 2 - Identificando fechamentos acima ou abaixo em relação
        stock_data[f'Position_MMA{i}'] = where(
            pandas.notnull(stock_data[f'MMA{i}']),  # Verifica se a MMA{i} não é nula
            where(stock_data['Close'] > stock_data[f'MMA{i}'], 1, -1),  # Condição original
            0  # Valor para quando MMA{i} é nula
        )

        # 3 - Calculando distância para MMA. Quanto maior, melhor
        stock_data[f'%_to_MMA{i}'] = ((stock_data['Close'] - stock_data[f'MMA{i}']) / stock_data[f'MMA{i}']) * 100

    return stock_data

def calculate_obv(stock_data):
    """
    """

    # Inicializando a lista OBV com o primeiro valor como 0
    obv = [0]

    # Iterando sobre os preços de fechamento e volumes
    for i in range(1, len(stock_data['Adj Close'])):
        if stock_data['Adj Close'].iloc[i] > stock_data['Adj Close'].iloc[i-1]:
            # Se o preço de fechamento atual é maior que o anterior, adicionar o volume
            obv.append(obv[-1] + stock_data['Volume'].iloc[i])
        elif stock_data['Adj Close'].iloc[i] < stock_data['Adj Close'].iloc[i-1]:
            # Se o preço de fechamento atual é menor que o anterior, subtrair o volume
            obv.append(obv[-1] - stock_data['Volume'].iloc[i])
        else:
            # Se o preço de fechamento é igual ao anterior, OBV não muda
            obv.append(obv[-1])

    # Adicionar a coluna OBV ao DataFrame
    stock_data['OBV'] = obv

    # Calcular o OBV para todas as mma_list
    # Usando a média móvel dos últimos 20 dias.
    window = 20

    stock_data[f'OBV_MA_{window}days'] = stock_data['OBV'].rolling(window=window).mean()

    # Atribuindo value
    stock_data[f'OBV_{window}d_?value'] = [1 if stock_data['OBV'].iloc[i] > stock_data[f'OBV_MA_{window}days'].iloc[i] else -1 for i in range(len(stock_data))]

    # Apagando colunas desnecessárias
    stock_data.drop(columns=[f'OBV_MA_{window}days'], inplace=True)

    return stock_data


def calcule_exaustao_atr(df, atr_period=14, multiplier=1.5):
    """
    Calcula o ATR (Average True Range) e verifica se o movimento (True Range) do candle atual
    é, pelo menos, 'multiplier' vezes maior que o ATR do dia anterior.

    Se sim, adiciona "1" na coluna "Exaustao ATR", caso contrário, NaN.

    Parâmetros:
      - atr_period: período em dias para cálculo da média (padrão 14).
      - multiplier: fator multiplicador para definir “movimento forçado” (padrão 1.5).
    """
    df = df.copy()

    # True Range (TR): a maior entre (High - Low), |High - prev_Close| e |Low - prev_Close|
    # Fechamento do dia anterior - df['Adj Close'].shift(1)
    df['TR'] = maximum(df['High'] - df['Low'],
               maximum(abs(df['High'] - df['Adj Close'].shift(1)), abs(df['Low'] - df['Adj Close'].shift(1))))

    # Cálculo do ATR: média móvel simples do TR, com janela definida por atr_period
    df['ATR'] = df['TR'].rolling(window=atr_period).mean()

    # Se o TR do candle atual for pelo menos "multiplier" vezes maior que o ATR do dia anterior,
    # então:
    # - Se df['Return'] for negativo, atribui -1 (movimento forçado de baixa).
    # - Se df['Return'] for positivo, atribui 1 (movimento forçado de alta).
    # Caso contrário, atribui 0.

    df['Exaustao ATR_?value'] = where(
        df['TR'] >= multiplier * df['ATR'].shift(1) * (1 - tolerancia_erro),
        where(df['Return'] < 0, -1, where(df['Return'] > 0, 1, 0)),
        0
    )

    return df

"""#### alto_volume_persistente, calcule_volatilidade_anualizada, add_price_concentration_levels, add_price_concentration_levels_by_me, crie_min_e_max"""

def alto_volume_persistente(df):
    """
    Marca ±1 quando:
      • volume alto por k dias consecutivos
      • preço sobe (ou cai) em 'return_window' dias
        - se return_window=None, usa candle do dia (shift 1)
        - se return_window=k, compara close_t vs close_{t-k}
    Cria coluna: 'Alto_volume_{multiplier}_p{k}d_?value'
    """
    # Parâmetros internos
    volume_window = 20
    volume_multiplier = 2
    k = 2

    vol_ma = df["Volume"].rolling(volume_window, min_periods=volume_window).mean()

    hv_flag = (df["Volume"] >= vol_ma * volume_multiplier).astype(int)
    hv_streak = hv_flag.rolling(k).sum() == k

    # Calculando a diferença
    ret = df['Close'].pct_change(k)
    price_up   = ret > 0
    price_down = ret < 0

    # Varrendo o df
    df['Alto_volume_persistente'] = select(
        [hv_streak & price_down, hv_streak & price_up],
        [-1, 1],
        default=0
    )

    return df

def calcule_volatilidade_anualizada(dados, vol_window):
    """
    Calcula a volatilidade anualizada com uma janela móvel para os retornos logarítmicos.

    Args:
    dados (DataFrame): DataFrame contendo os preços com uma coluna 'Return' para os retornos diários logarítmicos.
    vol_window (int): Janela de tempo em dias para o cálculo da volatilidade móvel.

    Returns:
    DataFrame: O mesmo DataFrame de entrada com uma nova coluna adicionada para a volatilidade anualizada.
    """

    # Calculando a volatilidade anualizada com uma janela móvel
    dados[f'vol_anualized_{vol_window}days'] = dados['Return'].rolling(window=vol_window).std() * sqrt(252)

    return dados


def add_price_concentration_levels(
    df,
    window: int = 180,
    bins: int = 50,
    top_n: int = 9
):
    # ---------- colunas de saída ----------
    for c in ["sup_min", "sup_med", "sup_max",
              "res_min", "res_med", "res_max"]:
        df[c] = nan

    # ---------- função interna ----------
    def _levels(win):
        pmin, pmax = win["Low"].min(), win["High"].max()
        edges   = linspace(pmin, pmax, bins + 1)
        centers = (edges[:-1] + edges[1:]) / 2

        idx = digitize(win["Close"].to_numpy(), edges) - 1
        idx[idx == bins] = bins - 1        # <<<<< CLAMP

        counts  = bincount(idx, minlength=bins)
        ordered = argsort(counts)[::-1]
        cur     = win["Close"].iloc[-1]

        sup, res = [], []
        for j in ordered:
            lvl = float(centers[j])
            if lvl < cur and len(sup) < top_n:
                sup.append(lvl)
            elif lvl > cur and len(res) < top_n:
                res.append(lvl)
            if len(sup) >= top_n and len(res) >= top_n:
                break

        sup.sort(); res.sort()
        return sup, res

    # ---------- loop pelas janelas ----------
    for i in range(window - 1, len(df)):
        win = df.iloc[i - window + 1 : i + 1]
        sup, res = _levels(win)
        idx = df.index[i]

        # ---------- SUPORTE ----------
        if len(sup) == top_n:     # cálculo OK
            df.loc[idx, ["sup_min","sup_med","sup_max"]] = [
                sup[0], sup[len(sup)//2], sup[-1]
            ]
        elif i > 0:       # cálculo vazio → repete linha anterior
            df.loc[idx, ["sup_min","sup_med","sup_max"]] = \
                df.iloc[i-1][["sup_min","sup_med","sup_max"]].values

        # ---------- RESISTÊNCIA ----------
        if len(res) == top_n:
            df.loc[idx, ["res_min","res_med","res_max"]] = [
                res[0], res[len(res)//2], res[-1]
            ]
        elif i > 0:
            df.loc[idx, ["res_min","res_med","res_max"]] = \
                df.iloc[i-1][["res_min","res_med","res_max"]].values

    # Adicionando as fórmulas consolidadoras
    pts_cols = ["sup_min", "sup_med", "sup_max",
                "res_min", "res_med", "res_max"]

    # 1) edges_concentratio ----------------------------------------------
    # Quando mais alto o valor, mais comprado o mercado

    close_array  = df["Close"].to_numpy(dtype="float64").reshape(-1, 1)
    points_array = df[pts_cols].to_numpy(dtype="float64")
    rel_dist     = close_array / points_array - 1          # matriz Nx6
    df["edge_levels"] = nansum(rel_dist, axis=1)      # soma linha a linha

    mean_edges = df["edge_levels"].mean(skipna=True)
    std_edges  = df["edge_levels"].std(skipna=True)

    # z-score de cada linha
    z = (df["edge_levels"] - mean_edges) / std_edges

    # categoriza em degraus de desvio-padrão
    df["edges_concentration_std"] = select(
        [
            z <= -2,
            (z > -2) & (z <= -1),
            (z > -1) & (z < 1),
            (z >= 1) & (z < 2),
            z >= 2,
        ],
        [-2, -1, 0, 1, 2],
        default=nan,
    )

    # 3) momentum_break  ---------------------------------------------
    df["momentum_break"] = select(
        [
            df["Close"] < df["sup_min"],                                                 # abaixo de todo suporte
            (df["Close"] >= df["sup_min"]) & (df["Close"] < df["sup_med"]),              # entre sup_min e sup_med
            (df["Close"] >= df["sup_med"]) & (df["Close"] < df["sup_max"]),              # entre sup_med e sup_max
            (df["Close"] >= df["sup_max"]) & (df["Close"] < df["res_min"]),              # entre sup_max e res_min
            (df["Close"] >= df["res_min"]) & (df["Close"] < df["res_med"]),              # entre res_min e res_med
            (df["Close"] >= df["res_med"]) & (df["Close"] < df["res_max"]),              # entre res_med e res_max
            df["Close"] >= df["res_max"],                                                # acima de toda resistência
        ],
        [-3, -2, -1, 0, 1, 2, 3],                                                       # valores atribuídos
        default=nan,                                                                 # mantém NaN se faltarem níveis
    )

    return df


def add_price_concentration_levels_by_me(df) -> dict:
    """

    """

    df_copy = df.copy() #copiando o df para não ter que deletar várias colunas ao final

    # Essa informação será usada na linha que compara os três valores acima e abaixo do "Adj Close"
    price_today = df['Adj Close'].iloc[-1]

    #1 - Arredondamento naturalmente diminui a quantidade de edges. Senão, seria centenas
    #2 - Os edges que disputam a zona de concentração
    df_copy = df_copy.round(1)
    #3 - Contando edges repetidos
    q_high = df_copy['High'].value_counts(dropna=False)
    q_low = df_copy['Low'].value_counts(dropna=False)
    #4 - Cria o map do edges high porque é necessário ver se na ponta oposta do candle haverá acumulação
    df_copy['quant_high'] = df_copy['High'].map(q_high).astype(float)
    df_copy['quant_low_apply_map_high'] = df_copy['Low'].map(q_high).fillna(0).astype('int64') #fillna obriga a célula a ficar zerada, permitindo ser somada. Senão quebra a soma abaixo
    df_copy['quant_close_apply_map_high'] = df_copy['Adj Close'].map(q_high).fillna(0)
    #5 - Soma high, low e Close, com base no map
    df_copy['sum_edges_by_map_high'] = df_copy['quant_high'] +  df_copy['quant_low_apply_map_high'] + df_copy['quant_close_apply_map_high']
    #6 - Repete tudo para a ponta low para comparar se resistências foram criadas com base em volume de suportes
    df_copy['quant_low'] = df_copy['Low'].map(q_low).astype('int64')
    df_copy['quant_high_apply_map_low'] = df_copy['High'].map(q_low).fillna(0) #fillna obriga a célula a ficar zerada, permitindo ser somada. Senão quebra a soma abaixo
    df_copy['quant_close_apply_map_low'] = df_copy['Adj Close'].map(q_low).fillna(0)
    #7 - Soma high, low e Close, com base no map
    df_copy['sum_edges_by_map_low'] = df_copy['quant_low'] +  df_copy['quant_high_apply_map_low']  + df_copy['quant_close_apply_map_low']

    #8 - Jornada de organizar os dados
    #8.1 - Cria a coluna central para encontrar o edge que mais se repetiu
    df_copy['ranking_edges'] = where(
            df_copy['sum_edges_by_map_high'] >= df_copy['sum_edges_by_map_low'], df_copy['sum_edges_by_map_high'], df_copy['sum_edges_by_map_low'])
    #8.2 - Para não confundir se a coluna foi a low, ou high, escreve o nome da coluna vencedora
    #CHECK - NÃO USO -----------
    #df['winner_col'] = where(
    #       df['sum_edges_by_map_high'] >= df['sum_edges_by_map_low'], "High","Low")
    #8.3 - Procura o valor do close se a coluna referente ao nome da vencedora.
    df_copy['winner_value_edge'] = where(
            df_copy['sum_edges_by_map_high'] >= df_copy['sum_edges_by_map_low'], df_copy['High'], df_copy['Low'])

    #9 Calculando percentis
    #9.1 Calcula os percentis
    p68, p95, p99 = df_copy["ranking_edges"].quantile(0.68), df_copy["ranking_edges"].quantile(0.95), df_copy["ranking_edges"].quantile(0.99)

    # 9.2 Aplicando classificação de desvio apropriados da tabela normal
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


    #8 Filtro e análise

    #8.1- OPCIONAL - ver os valores únicos de winner_value_edge
    #unique_winners = df_sorted["winner_value_edge"].unique()
    #n_unique = len(unique_winners)

    #8.2 Se não aplicar drop_dupiicates, vão aparecer 5 linhas com 23.7, 9 com 20.2. Ou seja, value_edges repetidos
    top_rows = df_copy.drop_duplicates(subset="winner_value_edge", keep="first")

    #8.3 CADUDO - Retorna só uma linha por winner_value_edge
    #out = top_rows.reset_index(drop=True).copy()

    # 9 - Eliminar os "std_ranking_edges" 0 e criar uma df com os maiores desvios e os limites
    # 9.1 - Filtra o dataframe para manter apenas as linhas com o menor valor
    df_winner_ranking_level = top_rows[top_rows['std_ranking_edges'] > 0]
    # 9.2 - Seleciona as linhas correspondentes ao menor e ao maior winner_value_edge
    df_sorted = top_rows.loc[[top_rows["winner_value_edge"].idxmin(), top_rows["winner_value_edge"].idxmax()]]

    # 9.3 - Concatena max value, min value  winner_value_edge com df_winner_ranking_level
    df_winner_ranking_level = pandas.concat([df_sorted, df_winner_ranking_level])
    # 9.4 - Ordena o top_rows para para a próxma linha de pegar o primeiro e último "winner_value_edge"
    df_sorted = df_winner_ranking_level.sort_values("winner_value_edge", ascending=False, na_position="last")

    # Check---------------------
    #df_sorted.to_excel(f'df_{ticker}_trade_concentration_new_version.xlsx')
    #print(f'{ticker} df_trade_concentration_new_version')

    # 10 Criando a tabela de inteiração com o DF principal

    # 10.1 cria dfs 3 abaixo e 3 acima do Adj Close
    below = df_winner_ranking_level[df_winner_ranking_level["winner_value_edge"] < price_today].sort_values("winner_value_edge", ascending=False).head(3)
    above = df_winner_ranking_level[df_winner_ranking_level["winner_value_edge"] > price_today].sort_values("winner_value_edge", ascending=True).head(3)

    # 10.1.1 - Pega o maior valor de ranking edge entre as tê
    max_std_ranking_edges = max(
        pandas.to_numeric(below['std_ranking_edges'], errors='coerce').max(),
        pandas.to_numeric(above['std_ranking_edges'], errors='coerce').max())

    # 10.2 transforma em uma lista
    below_vals = below["winner_value_edge"].tolist()
    above_vals = above["winner_value_edge"].tolist()

    # 10.3 Há casos em que não há 3 pontos de concentração abaixo do Adj Close. Ele está na cara do abismo. Nesse caso, escreve abismo
    while len(below_vals) < 3:
        below_vals.append("Abismo")
    while len(above_vals) < 3:
        above_vals.append("Foguete")

    # 10.3.1 Lembra que está crescente? Aqui precisa inverter
    below_vals = list(reversed(below_vals))

    # 10.4 Cáclulo do momentum break. Que é quanto o ticker está para romper o limite dos últimos 12 meses
    if above_vals.count("Foguete") >= 2:
        momentum_break = 1
    elif below_vals.count("Abismo") >= 2:
        momentum_break = -1
    else:
        momentum_break = 0

    # 10.5 Monta o DF para concatenar com o df principal
    df["sup_min_by_mslf"]: below_vals[0]
    df["sup_med_by_mslf"]: below_vals[1]
    df["sup_max_by_mslf"]: below_vals[2]
    df["res_min_by_mslf"]: above_vals[0]
    df["res_med_by_mslf"]: above_vals[1]
    df["res_max_by_mslf"]: above_vals[2]
    df["std_raking_value_by_mslf"]: max_std_ranking_edges
    df["momentum_break_by_mslf"]: momentum_break


    return df


def crie_min_e_max(stock_data):
    """
    Na verdade criarei o min. O Max é aquele que está a 100% do min.
    """

    # Encontrar os valores mínimos e máximos da coluna 'Close'
    min_close = stock_data['Close'].min()
    max_close = stock_data['Close'].max()

    # Adicionar coluna com percentual de distância do mínimo e máximo
    stock_data['Close_%_to_Min'] = ((stock_data['Close'] - min_close) / (max_close - min_close)) * 100

    return stock_data

## Análises long ou short
def distorions_analysys(todas_montagens):
    """
    A função NÃO RECEBE um df de ticker. Recebe o df com todas as montagens técnicas.
    A função categoriza a coluna de acima de um desvio com -1 e abaixo de 1 desvio com 1
    Também categoriza colunas com 1 a 10 de acordo com os percentis
    """

    # Vol Mês^Anual
    media = todas_montagens['vol_anualized_30days'].mean()
    std_vol = todas_montagens['vol_anualized_30days'].std()

    # Função para categorizar em 10 grupos usando percentis
    def categorizar_percentil(coluna):
        return (
            coluna.rank(pct=True)  # Calcula percentis
            .mul(10)               # Multiplica para escala de 1 a 10
            .apply(ceil)        # Arredonda para cima
            .fillna(0)             # Substitui NaN por 0
            .clip(upper=10)        # Limita o valor máximo a 10
            .astype(int)           # Converte para inteiro
        )

    # Adicionando colunas categorizadas de 50 e 10 dias
    todas_montagens['%_to_MMA50_Categoria'] = categorizar_percentil(todas_montagens['%_to_MMA50'])
    todas_montagens['%_to_MMA10_Categoria'] = categorizar_percentil(todas_montagens['%_to_MMA10'])

    # Aplicando _?value para vol
    todas_montagens['Vol Mês^Anual_?value'] = todas_montagens['vol_anualized_30days'].apply(lambda x: 1 if x < media - std_vol else (-1 if x > media + std_vol else 0))

    return [todas_montagens, {'média':media, 'std_vol':std_vol}]


def distorted_price_analysis(todas_montagens, mma50_wgh, mma10_wgh):
    """
    Gera um novo df super filtrado só com as maiores oportunidades de short e long considerando
    movimentos rápidos em relação à mma50
    """

    # Fórmula do ranking de preços distorcidos
    todas_montagens['distortion_ranking'] = ((todas_montagens['avaliacao_fundamentalista'] - 40) * -1)
    + todas_montagens['%_to_MMA50_Categoria']  * mma50_wgh
    + todas_montagens['%_to_MMA50_Categoria']  * mma10_wgh

    todas_montagens.to_excel(f'carteira_automatica.xlsx')

    # Selecionar os cinco maiores e cinco menores valores de 'distortion_ranking'
    top_5 = todas_montagens.nlargest(5, 'distortion_ranking')
    bottom_5 = todas_montagens.nsmallest(5, 'distortion_ranking')

    # Combinar os dois DataFrames para criar o resultado
    filtered_montagens = pandas.concat([top_5, bottom_5])

    # Filtrar as colunas desejadas
    filtered_montagens = filtered_montagens[['Ticker', 'Subsetor', 'distortion_ranking', '%_to_MMA10']]

    # Mudando os nomes para melhorar a interpretação
    filtered_montagens.rename(columns={'distortion_ranking': 'Major->Long'}, inplace=True)

    return filtered_montagens


def all_time_low_and_high_analysis(todas_montagens):
    """
    """

    # 1 - Remove os tickers com volatilidade muito alta
    todas_montagens = todas_montagens[todas_montagens['Vol Mês^Anual_?value'].isin([0,1])].copy()

    # 2 - Filtra os dfs pelos tickers na mínima e máxima
    tickers_minima = todas_montagens[todas_montagens['Close_%_to_Min'].isin([0])].copy()
    tickers_maxima = todas_montagens[todas_montagens['Close_%_to_Min'].isin([100])].copy()

    # Selecionar os três maiores e três menores valores de 'distortion_ranking'
    bottom_3 = tickers_minima.nlargest(3, '%_to_MMA50')
    top_3 = tickers_maxima.nsmallest(3, '%_to_MMA50')

    # Combinar os dois DataFrames para criar o resultado
    filtered_montagens = pandas.concat([top_3, bottom_3])

    # Filtrar as colunas desejadas
    filtered_montagens = filtered_montagens[['Ticker', 'Setor', 'Subsetor', 'Close_%_to_Min', 'MMA50']]

    # Mudando os nomes para melhorar a interpretação
    filtered_montagens.rename(columns={'MMA50': 'Stop'}, inplace=True)
    filtered_montagens.rename(columns={'Close_%_to_Min': 'long->100'}, inplace=True)


    return filtered_montagens


# Administrativo
def concatene_analises_tecnicas(dados, carteira_automatica):
    '''
    Cria a lista de dicionários que reúne as informações sobre cada ticker
    '''


    # Criar uma Series para o ticker e concatenar na posição correta
    ticker_series = pandas.Series({'Ticker': dados[0][:-3]})
    last_line = pandas.concat([ticker_series, last_line])  # Concatena o ticker no início

    # --- concatena verticalmente e zera o índice ---
    carteira_automatica = pandas.concat(
        [carteira_automatica, last_line],
        ignore_index=True
    )

    return carteira_automatica

"""#### Screener"""

def screener(lista, carteira_automatica):
    '''
    Parametros: Lista de tickers
                Informação se o dataframe será do dia atual ou para backtest

    '''
    # Variáveis locais
    probleminhas_temp = []
    frames_para_concat = []          # evita concatenações repetidas

    # Evitando Unboundlocarlerror quando a consulta ao primeiro ticker volta falso
    dados_para_analise = None



    for ticker in tqdm(lista, desc="Processando Tickers"):

        # filtro para quando o papel está com algum erro de dados na Yahoo Finance
        if ticker not in probleminhas:

            yf_ticker = f'{ticker}.SA' # Para atender ao código do ticker no Yfinance

            try:

                dados_para_analise = extrai_cotacoes(yf_ticker)

                # Exportações de df de análise técnica
                if len(lista) <=2: # Aciona a exportação só se a lista de tickers é pequena
                    autoriza_exportar = input(f'Exportar arquivo?')
                    dados_para_analise[1].to_excel(f'{yf_ticker}.xlsx')

            except:

                print(f'Erro ao calcular {yf_ticker}.')
                dados_para_analise = None
                continue


            if  dados_para_analise:

                # ---------- monta a linha ----------
                last_row  = dados_para_analise[1].tail(1)

                # Empilha verticalmente
                carteira_automatica = pandas.concat(
                                                [carteira_automatica, last_row],
                                                axis=0,
                                                ignore_index=True
                                                )
        else:

            print(f'{ticker} em probleminhas')

    return carteira_automatica

"""## Bloco Fundamentalista"""

# Web Scraping

def puxar_dados(url):
    """

    """
    # Modificando os headers da requisição
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
    response = requests.get(url, headers=headers)

    # Usando o pandas para extrair as tabelas da página web
    tables = pandas.read_html(StringIO(response.text))

    return tables


def formatar_tabela(tables):
    """
    Os dados puxados estão muito desformatados para trabalhar com numpy ou pandas
    O objetivo é deixar o df perfeito
    """

    # 1 - Apagando tickers que são FIIs
    if tables[0].iloc[0,0] =="?FII":
        tables = tables.drop(tables.index)

    # 2 - Os dados vem organizados verticalmente e desalinhados em várias colunas. Precisa arranjar tudo em duas colunas de keys e values
    # Primeiro cria duas colunas
    formated_table = tables[0].iloc[:, :2].copy()

    # check ----------------------------------
    # print(formated_table)

    # Depois adiciona as demais tabelas ao DataFrame consolidado, fazendo o alinhamento
    for table in tables[1:]:
        # Iterando sobre as colunas da tabela atual de duas em duas
        for i in range(0, table.shape[1], 2):
            # Concatenando as colunas atual e seguinte ao DataFrame consolidado
            formated_table = pandas.concat([formated_table, table.iloc[:, i:i+2].rename(columns={i: 0, i+1: 1})], ignore_index=True)

    # 3 Removendo as linhas que contêm células vazias
    formated_table = formated_table.drop(formated_table[formated_table.iloc[:, 0].str.contains(r'Indicadores fundamentalistas|Dados Balanço Patrimonial|Dados demonstrativos de resultados|Empresa|Últimos 12 meses|Últimos 3 meses|^\s*$', na=False)].index)
    # 4 Removendo as linhas que o a própria robusta calcula na análise técnia
    formated_table = formated_table.drop(formated_table[formated_table.iloc[:, 0].str.contains(r'Oscilações|Dia|Mês|Empresa|30 dias|12 meses|2024|2023|2022|2021|2020|2019|^\s*$', na=False)].index)
    # 5 Removendo as linhas que o a própria robusta calcula na análise fundamentalista
    formated_table = formated_table.drop(formated_table[formated_table.iloc[:, 0].str.contains(r'P/L|P/VP|Valor de mercado|^\s*$', na=False)].index)


    def remova_caracteres_converta_numeros(df):
        """
        df vem com vários caraceres especiais e todos os números estão em strngs impossibilitando contas
        Essa função remove todos e muda todos os objetos para deixar o df pronto para fazer contas
        """
        # Removendo caracteres especiais da primeira coluna
        #print(repr(row) for row in df['0'])
        #df = df.rename(columns=lambda x: x.replace('? ', '') if isinstance(x, str) else x, index=lambda x: x.replace('?', '') if isinstance(x, str) else x).replace('?', '', regex=False)

        # Remover linhas vazias, se houver
        df.dropna(how='all', inplace=True)

        # Transformar a coluna "0" em índice
        df.set_index(0, inplace=True)

        def convert_to_number(value):

            try:
                # Remover pontos e adicionar "00"
                if '.' in value:
                    value = value.replace('.', '') + '00'
                # Tentar converter para float ou integer e dividir por 100
                num = float(value) / 100
                return num

            except ValueError:

                # Tratar valores com "," e "%"
                if ',' in value:
                    value = value.replace(',', '.')
                if '%' in value:
                    value = value.replace('%', '')
                # Tentar converter novamente para float
                try:
                    return float(value)
                except ValueError:
                    # Se ainda for um erro, retornar o valor original

                    return value

        # Convertendo toda a coluna em números
        df[1] = df[1].apply(lambda x: convert_to_number(str(x)))

        return df

    formated_table = remova_caracteres_converta_numeros(formated_table)

    # 4 - Transpondo o DataFrame
    formated_table = formated_table.transpose()

    # 5 - Deixando o nome da coluna dos códigos dos papeis no padrão dos demais df
    # formated_table = formated_table.replace('?', '', regex=False)
    formated_table.rename(columns={'Papel': 'ticker'}, inplace=True)

    return formated_table


def gera_indicadores_extras(dados_financeiro_all_tickers):
    """
    Indicadores que precisam ser atualizados com o preço do papel via YFINANCE
    As colunas abaixo foram deletadas na função formatar_tabela, que recebeu os dados do web-scrapping porque eles não são atualizados
    'P/L','Dív. Líquida/Valor de mercado', 'P/VP'

    """
    for index, row in dados_financeiro_all_tickers.iterrows():

        ticker = row['ticker']
        ticker_yf = f'{ticker}.SA'  # Ticker seguindo o código do Yfinance


        # Quando um ticker é bloqueado por problemas. Por causa que a análise técnica roda diariamente
        # e a fundamentalista mensalmente, pode dar keyerror. O try impede isso.
        try:
            # 1 - Puxo o preço de fechamento do ativo
            last_close_price = data_cache_backtest[ticker_yf].iloc[-1]['Close']

            # 2 - Faço as contas e alimento as novas células
            # Verificar se LPA e VPA não são zero para evitar divisão por zero
            lpa = row['LPA']
            if lpa != 0:
                dados_financeiro_all_tickers.loc[index, 'P/L'] = round(last_close_price / lpa,2)
            else:
                dados_financeiro_all_tickers.loc[index, 'P/L'] = -1e6

            nro_acoes = row['Nro. Ações']
            div_liquida = row['Dív. Líquida']
            valor_de_mercado = nro_acoes * last_close_price
            dados_financeiro_all_tickers.loc[index, 'Dív. Líquida/Valor de mercado'] = round(div_liquida / valor_de_mercado,2)

            vpa = row['VPA']
            if vpa != 0:
                dados_financeiro_all_tickers.loc[index, 'P/VP'] = round(last_close_price / vpa,2)
            else:
                dados_financeiro_all_tickers.loc[index, 'P/VP'] = -1e6

        except:

            print(f'Sem análise técnica de {ticker}. Sem dados de valuation')

    return dados_financeiro_all_tickers


# Análises
def rankeia_outros_indicadores_maior_melhor(dados_financeiro_all_tickers, *kwargs):
    """
    Indicadores quanto maior, melhor.

    Laço que ordena indicadores por classe de qualidade.
    Os indicadores são argumentos da função
    Tem que ter o str da col do dataframe dados_financeiro_all_tickers

    Uso esses, por enquanto:
    "Cres. Rec (5a) 	ROIC	"

    """
    print(dados_financeiro_all_tickers)
    for indicador in kwargs:

        print(f'Avaliando {indicador} separando por Classe')

        # Certificar-se de que a coluna é numérica e lidar com NaNs
        dados_financeiro_all_tickers[indicador] = pandas.to_numeric(dados_financeiro_all_tickers[indicador], errors='coerce')
        dados_financeiro_all_tickers[indicador].fillna(0)

        # Atribuir notas com base em percentis.
        dados_financeiro_all_tickers[f'classe {indicador}'] = pandas.qcut(dados_financeiro_all_tickers[indicador], 10, labels=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10])


    return dados_financeiro_all_tickers


def rankeia_outros_indicadores_menor_melhor_neg_permitido(dados_financeiro_all_tickers, *kwargs):
    """
    Indicadores quando menor melhor, sem restrição para negativo.

    Ordena indicadores por classe de qualidade.
    Tem que ter o str da col do dataframe dados_financeiro_all_tickers

    Uso esses, por enquanto
    "Dív. Líquida/Valor de mercado"

    """

    for indicador in kwargs:

        print(f'Avaliando {indicador} menor_melhor separando por Classe')

        # Certificar-se de que a coluna é numérica e lidar com NaNs
        dados_financeiro_all_tickers[indicador] = pandas.to_numeric(dados_financeiro_all_tickers[indicador], errors='coerce')
        dados_financeiro_all_tickers[indicador].fillna(0)

        # Atribuir notas com base em percentis.
        dados_financeiro_all_tickers[f'classe {indicador}'] = pandas.qcut(dados_financeiro_all_tickers[indicador], 10, labels=[10, 9, 8, 7,6,5,4,3,2,1])


    return dados_financeiro_all_tickers


def rankeia_outros_indicadores_menor_melhor_neg_bloqueado(dados_financeiro_all_tickers, *kwargs):
    """
    Indicadores quando menor melhor, mas até o limite de > 0.
    Exemplo. P/L de -15 não é melhor que P/L de 1

    Laço que ordena indicadores por classe de qualidade.
    Os indicadores são argumentos da função
    Tem que ter o str da col do dataframe dados_financeiro_all_tickers

    Uso esses, por enquanto
    "P/L P/VP 'EV / EBIT'"
    """

    for indicador in kwargs:

        print(f'Avaliando {indicador} menor_melhor e separando por Classe')

        # Criando um novo indicador temporário para classificação
        indicador_temp = f'{indicador} descarte'
        dados_financeiro_all_tickers[indicador_temp] = dados_financeiro_all_tickers[indicador]

        # Certificar-se de que a coluna é numérica. Ainda tem valores que vieram da função formatar_tabela como str
        dados_financeiro_all_tickers[indicador_temp] = pandas.to_numeric(dados_financeiro_all_tickers[indicador_temp], errors='coerce')

        # Ajustando valores negativos e zero
        dados_financeiro_all_tickers.loc[dados_financeiro_all_tickers[indicador_temp] <= 0, indicador_temp] += 1e9
        #dados_financeiro_all_tickers.loc[dados_financeiro_all_tickers[indicador_temp] == 0, indicador_temp] += 1e9

        # Atribuindo notas com base em percentis
        dados_financeiro_all_tickers[f'classe {indicador}'] = pandas.qcut(dados_financeiro_all_tickers[indicador_temp], 10, labels=[10,9,8,7,6,5,4,3,2,1])

        # Apagando coluna desnecessária
        dados_financeiro_all_tickers.drop(columns=[indicador_temp], inplace=True)

    return dados_financeiro_all_tickers



def avaliacao_fundamentalista(dados_financeiro_all_tickers):

    def soma_colunas(row):

        # Definindo os setores e colunas para somar
        setores_especiais = ['Previdência e Seguros', 'Intermediários Financeiros']
        colunas_especiais = ['classe P/L', 'classe Cres. Rec (5a)', 'classe Dív. Líquida/Valor de mercado', 'classe P/VP']
        colunas_gerais = ['classe P/L', 'classe Cres. Rec (5a)', 'classe ROIC', 'classe EV / EBIT']

        # Condicional para decidir quais colunas somar
        if row['Setor'] in setores_especiais:
            return row[colunas_especiais].sum()
        else:
            return row[colunas_gerais].sum()

    print(f'Aplicando Análise fundamentalista')

    # Aplicando a função para cada linha do dataframe e criando uma nova coluna com os resultados
    dados_financeiro_all_tickers['avaliacao_fundamentalista'] = dados_financeiro_all_tickers.apply(soma_colunas, axis=1)

    return dados_financeiro_all_tickers


def rankeando_empresas(dados_financeiro_all_tickers):

    def rotula_melhor_pior(grupo):

        # Encontre os valores máximos e mínimos do grupo
        max_valor = grupo['avaliacao_fundamentalista'].max()
        min_valor = grupo['avaliacao_fundamentalista'].min()

        # Atribua "melhor" ou "pior" com base nos valores
        grupo.loc[grupo['avaliacao_fundamentalista'] == max_valor, 'Posicao setorial'] = 'melhor'
        grupo.loc[grupo['avaliacao_fundamentalista'] == min_valor, 'Posicao setorial'] = 'pior'

        return grupo

    print(f'Aplicando rótulos por setor')

    # Inicialize a coluna "Posicao setorial" com valores vazios
    dados_financeiro_all_tickers['Posicao setorial'] = ''

    # Aplicar o groupby sem incluir a coluna de agrupamento
    dados_financeiro_all_tickers = (
        dados_financeiro_all_tickers
        .groupby(dados_financeiro_all_tickers['Setor'])
        .apply(rotula_melhor_pior)
        .reset_index(drop=True)
    )

    return dados_financeiro_all_tickers

def avaliacao_fundamentalista_analisys(dados_financeiro_all_tickers):
    """
    Gera a col necessária para o backtest e atribui valores para ele combinar e simular

    Value 1 para empresas que não tenham nenhuma nota 1 no somatório.
    Value -1 para empresas que não tenham três notas 1
    Value 0 os demais

    """

    dados_financeiro_all_tickers['Fundamental_?value'] = dados_financeiro_all_tickers['avaliacao_fundamentalista'].apply(
    lambda x: 1 if x >= 32 else (-1 if x <= 14 else 0))

    return dados_financeiro_all_tickers


def adicione_indicadores_e_ranking(all_ticker_financial_indicators):

    """
    Despoluir o principal da Robusta
    Além disso, a função apaga colunas "Unnamed", indesejadas, que foram geradas por um bug desconnhecido durante a criação das colunas anteriores

    """

    #Atualizando o df com informações que dependem do valor do papel no dia
    all_ticker_financial_indicators = gera_indicadores_extras(all_ticker_financial_indicators)

    #Gerando indicadores e classe de empresas por indicadores
    # Funções diferentes porque os indicadores não são iguais. Alguns, como PL, quanto menor, melhor. Senqo que negativo é ruim.
    # Outruos como Dív. Líquida/Valor de mercado, negativo é bom.
    #all_ticker_financial_indicators = rankeia_PL(all_ticker_financial_indicators)
    all_ticker_financial_indicators = rankeia_outros_indicadores_maior_melhor(all_ticker_financial_indicators, 'Cres. Rec (5a)','ROIC')
    all_ticker_financial_indicators = rankeia_outros_indicadores_menor_melhor_neg_permitido(all_ticker_financial_indicators, 'Dív. Líquida/Valor de mercado')
    all_ticker_financial_indicators = rankeia_outros_indicadores_menor_melhor_neg_bloqueado(all_ticker_financial_indicators,'P/L', 'P/VP','EV / EBIT')

    #Somando as classes
    all_ticker_financial_indicators = avaliacao_fundamentalista(all_ticker_financial_indicators)

    #Rankear empresas por setor
    all_ticker_financial_indicators = rankeando_empresas(all_ticker_financial_indicators)

    #Atribuindo valores para o backtest
    all_ticker_financial_indicators = avaliacao_fundamentalista_analisys(all_ticker_financial_indicators)


    #3.8 Apagando colunas que contêm 'Unnamed' no nome
    cols_to_drop = all_ticker_financial_indicators.filter(like='Unnamed').columns
    all_ticker_financial_indicators = all_ticker_financial_indicators.drop(columns=cols_to_drop)


    return all_ticker_financial_indicators


def varre_lista(lista):

    # Instancia variável
    all_ticker_financial_indicators = pandas.DataFrame()

    # Contador do dataframe_all_ticker_financial_indicators
    ticker_contador = 2 # dois porque vai começar na terceira linha

    for values in lista:

        if values not in probleminhas:

            print(f'Analisando {values}')

            try:

                tables = puxar_dados(url_financials+values)

            except:

                tables = [tables]
                print(f'Erro no dowload de {values}')

                if values not in probleminhas:
                    probleminhas_temp.append(values)

            # Adicionando dados ao all_ticker_financial_indicators

            try:

                if len(tables) != 0:

                    # Deixando os dados no formato de um df
                    indicadores = formatar_tabela(tables)

                    # Adicionando indicadores ao all_ticker_financial_indicators
                    # Mas se all_ticker_financial_indicators estiver vazio tem que copiar o primeiro df
                    if len(all_ticker_financial_indicators) == 0:
                        all_ticker_financial_indicators = indicadores


                    # No restante basta concatenar os demais df
                    else:

                        for column in indicadores.columns:

                            # Adicionando o valor de new_data_df à próxima linha vazia de consolidated_table_transposed
                            if column in all_ticker_financial_indicators.columns:

                                all_ticker_financial_indicators.loc[ticker_contador, column] = indicadores.loc[1, column]

                        ticker_contador += 1

            except:

                    print(f'Checar {values}. Problemas com os dados')
                    if values not in probleminhas:
                        probleminhas_temp.append(values)


    return all_ticker_financial_indicators

"""### Consolidadoras de funções Principais"""

def gere_df_principal(carteira_automatica):

    #1. ANÁLISE TÉCNICA

    #1.1 - Escaneando ticker e atribuindo leitura técnica
    ticker_list = ler_todos_tickers()

    # Exportações de df técnico------------------------------------------
    ticker_list = {'ticker':['PRIO3','ASAI3','LREN3']}
    # ---------------------------------------------------------------------

    carteira_automatica = screener(ticker_list['ticker'], carteira_automatica) # colocando df no parâmetro para evitar do código não localizar a variável

    # 2. ANÁLISE FUNDAMENTALISTA

    # 2.1 Se não dia é dia de atualizar a planilha, basta carregar a já atualizada do arquivo

    if first_day_alert(hoje):

        # Puxa informação de datas e fundamentos uma vez por mês, sempre no início.
        try:
            all_ticker_financial_indicators = pandas.read_excel('all_ticker_financial_indicators.xlsx')

        except:
            print('Erro ao carregar arquivo')

    else:

        # Puxando dados das empresas
        all_ticker_financial_indicators = varre_lista(ticker_list['ticker'])

    #2.1 Atualizado Preço do papel com YFINANCE
    all_ticker_financial_indicators = adicione_indicadores_e_ranking(all_ticker_financial_indicators)

    #2.2 Export necessário para atualizar indicadores. Não é ÓPCIONAL
    all_ticker_financial_indicators.to_excel('all_ticker_financial_indicators.xlsx')

    # 3 - MERGES
    print(carteira_automatica,'\n',all_ticker_financial_indicators)

    carteira_automatica_com_todos_fechamentos = carteira_automatica.merge(
            all_ticker_financial_indicators,
            on='Ticker',
            how='left',
            )

    #Check----------------------------------
    carteira_automatica_com_todos_fechamentos.to_excel(' carteira_automatica.xlsx')

    # Análise de grandes distorçoes
    carteira_automatica_com_todos_fechamentos_plus_ranking, volatidade_hoje = distorions_analysys(carteira_automatica_com_todos_fechamentos)

    return carteira_automatica_com_todos_fechamentos_plus_ranking

def send_whatsapp_messages(df):

    '''
    '''

    distorted_price_report = distorted_price_analysis(df, 4, 1)

    texto = str(distorted_price_report)
    print("Mergulhador - Achador de fundo - ", texto)

    numero_destino = "whatsapp:+5521995159373"

    msg = client.messages.create(
        body=texto,
        from_="whatsapp:+14155238886", # Sandbox
        to=numero_destino
    )

    # Log rápido para debug
    print("SID:", msg.sid, "Status:", msg.status)

"""## Principal - Roda o código"""

'''
Analise os fundamentos de matd3, ServMédHospit Análises e Diagnósticos, incluindo geração de caixa
'''

while True:

    print('.',end='')

    # Hora ajustada para o fuso de Brasília (GMT-3)
    agora = datetime.utcnow() - timedelta(hours=3)

    hora_atual = agora.strftime("%H:%M")

    # Check------------------------------------------------
    hora_atual = "19:00"

    data_atual = agora.date()

    # Verifica se é dia útil (semana e não feriado)
    eh_dia_util = agora.weekday() < 5 and pandas.Timestamp(data_atual) not in feriados
    eh_dia_util = True

    if eh_dia_util:

        if hora_atual in ["14:56", "19:00"]:
            print(f"Executando tarefas às {hora_atual} em {data_atual}")
            carteira_automatica = gere_df_principal(carteira_automatica)
            send_whatsapp_messages(carteira_automatica)
            break

    time.sleep(30)  # Verifica a cada 30 segundos
