"""
Gerador deterministico de fixtures OHLCV para os testes do rebuild ROBUSTA.

Por que este arquivo existe:
- O `main.py` legado so produz dados rodando contra a Yahoo Finance, cujos
  valores mudam todo dia. Isso nao serve como baseline reproduzivel.
- Aqui geramos um "snapshot" sintetico e deterministico (mesma seed -> mesmos
  numeros), salvo como CSV versionado em `tests/fixtures/`. As fases seguintes
  do rebuild comparam suas saidas contra esses CSVs.

So usa biblioteca padrao, entao roda sem o ambiente virtual instalado.
Rode com:  python tests/fixtures/_generate_ohlcv.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

# Cada ticker tem uma seed e um preco inicial proprios, para gerar series
# diferentes mas estaveis entre execucoes.
TICKERS = {
    "PRIO3": {"seed": 1, "preco_inicial": 40.0, "volume_base": 8_000_000},
    "ASAI3": {"seed": 2, "preco_inicial": 12.0, "volume_base": 15_000_000},
    "LREN3": {"seed": 3, "preco_inicial": 18.0, "volume_base": 10_000_000},
}

# Quantidade de pregoes. 260 ~= um ano de bolsa, suficiente para a MMA200
# ter valores nao-nulos no fim da serie.
N_PREGOES = 260
DATA_INICIAL = date(2025, 5, 12)  # uma segunda-feira

# Colunas na mesma ordem que `yfinance.download(..., auto_adjust=False)` devolve.
COLUNAS = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]


def dias_uteis(inicio, quantidade):
    """Devolve `quantidade` datas, pulando sabados e domingos (sem feriados)."""
    datas = []
    dia = inicio
    while len(datas) < quantidade:
        if dia.weekday() < 5:  # 0=segunda ... 4=sexta
            datas.append(dia)
        dia += timedelta(days=1)
    return datas


def gera_serie(seed, preco_inicial, volume_base):
    """Gera uma lista de linhas OHLCV via passeio aleatorio com seed fixa."""
    rng = random.Random(seed)
    datas = dias_uteis(DATA_INICIAL, N_PREGOES)
    linhas = []
    preco = preco_inicial

    for i, dia in enumerate(datas):
        # Retorno diario: pequena tendencia de alta + ruido.
        retorno = rng.gauss(0.0005, 0.018)
        abertura = preco
        fechamento = round(abertura * (1 + retorno), 2)
        # High/Low respeitam a relacao OHLC (High >= max(O,C), Low <= min(O,C)).
        maxima = round(max(abertura, fechamento) * (1 + abs(rng.gauss(0, 0.006))), 2)
        minima = round(min(abertura, fechamento) * (1 - abs(rng.gauss(0, 0.006))), 2)

        # Volume com ruido. Nos dois ultimos pregoes injetamos um pico de
        # volume para que `alto_volume_persistente` tenha sinal nao-nulo.
        volume = int(volume_base * (1 + rng.gauss(0, 0.3)))
        if i >= N_PREGOES - 2:
            volume = int(volume_base * 3)

        linhas.append([
            dia.isoformat(),
            abertura,
            maxima,
            minima,
            fechamento,
            fechamento,  # Adj Close = Close (fixture sem proventos)
            max(volume, 0),
        ])
        preco = fechamento

    return linhas


def main():
    destino = Path(__file__).parent
    for ticker, cfg in TICKERS.items():
        linhas = gera_serie(cfg["seed"], cfg["preco_inicial"], cfg["volume_base"])
        caminho = destino / f"ohlcv_{ticker}.csv"
        with caminho.open("w", newline="", encoding="utf-8") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(COLUNAS)
            escritor.writerows(linhas)
        print(f"Gerado {caminho.name} ({len(linhas)} pregoes)")


if __name__ == "__main__":
    main()
