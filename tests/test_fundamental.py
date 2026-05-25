"""Testes da Fase 4 do rebuild - analise fundamentalista (`robusta.fundamental`).

Comando: pytest
"""

import pandas as pd

from robusta import data, fundamental


# --- F1: puxar_dados -------------------------------------------------------

def test_puxar_dados_parseia_tabela_minima(monkeypatch):
    """HTML com uma tabela minima -> lista nao vazia de DataFrames."""
    html = "<table><tr><td>Papel</td><td>PRIO3</td></tr></table>"
    monkeypatch.setattr(data, "baixa_html_fundamentus", lambda url: html)

    tabelas = fundamental.puxar_dados("http://exemplo/PRIO3")

    assert isinstance(tabelas, list)
    assert len(tabelas) >= 1
    assert isinstance(tabelas[0], pd.DataFrame)


def test_puxar_dados_usa_fixture_real_do_fundamentus(monkeypatch, fundamentus_html):
    """Com o HTML sintetico do Fundamentus, devolve varias tabelas e a
    primeira celula da primeira tabela e o rotulo 'Papel'."""
    monkeypatch.setattr(data, "baixa_html_fundamentus", lambda url: fundamentus_html)

    tabelas = fundamental.puxar_dados("http://exemplo/PRIO3")

    assert len(tabelas) >= 2
    assert tabelas[0].iloc[0, 0] == "Papel"


# --- F2: _converte_para_numero / formatar_tabela ---------------------------

def test_converte_para_numero_formatos_br():
    # '.' separador de milhar -> remove, anexa '00', /100.
    assert fundamental._converte_para_numero("1.234") == 1234.0
    assert fundamental._converte_para_numero("8.150.000.000") == 8150000000.0
    # ',' separador decimal -> '.'.
    assert fundamental._converte_para_numero("5,30") == 5.3
    # '%' descartado.
    assert fundamental._converte_para_numero("15,3%") == 15.3
    # Texto sem numero volta como esta.
    assert fundamental._converte_para_numero("Petróleo") == "Petróleo"


def test_formatar_tabela_limpa_transpoe_e_padroniza_ticker():
    """Uma tabela pequena com Papel/Setor/LPA/Nro. Ações + linhas a descartar."""
    tabela = pd.DataFrame([
        ["Papel", "PRIO3"],
        ["Setor", "Petróleo"],
        ["LPA", "5,30"],
        ["Nro. Ações", "8.150.000.000"],
        ["P/L", "10,5"],                          # descartada (recalculada)
        ["Indicadores fundamentalistas", ""],     # descartada (cabecalho)
    ])

    resultado = fundamental.formatar_tabela([tabela])

    # B2: a chave do papel vira 'Ticker' (maiusculo), nao 'ticker'.
    assert "Ticker" in resultado.columns
    assert "ticker" not in resultado.columns
    assert resultado["Ticker"].iloc[0] == "PRIO3"
    # Conversao numerica BR.
    assert resultado["LPA"].iloc[0] == 5.3
    assert resultado["Nro. Ações"].iloc[0] == 8150000000.0
    # Texto preservado.
    assert resultado["Setor"].iloc[0] == "Petróleo"
    # Linhas descartadas nao viram colunas.
    assert "P/L" not in resultado.columns
    assert "Indicadores fundamentalistas" not in resultado.columns


def test_formatar_tabela_consolida_multiplas_tabelas():
    """Tabelas seguintes sao empilhadas em pares de colunas (chave, valor)."""
    t0 = pd.DataFrame([["Papel", "ASAI3"], ["Setor", "Varejo"]])
    # Tabela com 4 colunas = dois pares chave/valor lado a lado.
    t1 = pd.DataFrame([["LPA", "2,50", "VPA", "10,00"]])

    resultado = fundamental.formatar_tabela([t0, t1])

    assert resultado["Ticker"].iloc[0] == "ASAI3"
    assert resultado["LPA"].iloc[0] == 2.5
    assert resultado["VPA"].iloc[0] == 10.0


def test_formatar_tabela_dedup_de_chave_repetida_na_pagina():
    """Se uma chave aparece duas vezes em tabelas diferentes da pagina, o
    transpose geraria colunas nao-unicas e quebraria o `pd.concat` em
    `varre_lista` (`InvalidIndexError`). A funcao mantem so a primeira
    ocorrencia e devolve um DataFrame com colunas unicas."""
    t0 = pd.DataFrame([["Papel", "PRIO3"], ["LPA", "5,30"]])
    # Segunda tabela repete a chave 'LPA' com valor diferente.
    t1 = pd.DataFrame([["LPA", "9,99"]])

    resultado = fundamental.formatar_tabela([t0, t1])

    assert resultado.columns.is_unique
    assert resultado["LPA"].iloc[0] == 5.3  # primeira ocorrencia preservada
    # Concat com outro ticker funciona, simulando o caminho do varre_lista.
    outro = fundamental.formatar_tabela(
        [pd.DataFrame([["Papel", "ASAI3"], ["LPA", "2,00"]])]
    )
    pd.concat([resultado, outro], ignore_index=True)  # nao levanta


# --- F3: gera_indicadores_extras -------------------------------------------

def _df_fundamental(ticker="PRIO3", lpa=5.0, vpa=10.0, nro_acoes=1000.0, div_liquida=2000.0):
    return pd.DataFrame([{
        "Ticker": ticker,
        "LPA": lpa,
        "VPA": vpa,
        "Nro. Ações": nro_acoes,
        "Dív. Líquida": div_liquida,
    }])


def test_gera_indicadores_extras_calcula_as_tres_contas():
    df = _df_fundamental(lpa=5.0, vpa=10.0, nro_acoes=1000.0, div_liquida=2000.0)
    precos = {"PRIO3": 50.0}

    resultado = fundamental.gera_indicadores_extras(df, precos)

    assert resultado["P/L"].iloc[0] == 10.0                       # 50 / 5
    assert resultado["P/VP"].iloc[0] == 5.0                       # 50 / 10
    # 2000 / (1000 * 50) = 0.04
    assert resultado["Dív. Líquida/Valor de mercado"].iloc[0] == 0.04


def test_gera_indicadores_extras_lpa_vpa_zero_marcam_menos_1e6():
    df = _df_fundamental(lpa=0.0, vpa=0.0)
    resultado = fundamental.gera_indicadores_extras(df, {"PRIO3": 50.0})
    assert resultado["P/L"].iloc[0] == -1e6
    assert resultado["P/VP"].iloc[0] == -1e6


def test_gera_indicadores_extras_nao_concatena_sa():
    """A funcao busca o ticker BASE no handoff. Se o dict so tiver a chave com
    '.SA', a busca falha -> sem valuation. Prova que nao concatena '.SA'."""
    df = _df_fundamental(ticker="PRIO3")
    precos_chave_errada = {"PRIO3.SA": 50.0}

    resultado = fundamental.gera_indicadores_extras(df, precos_chave_errada)

    assert "P/L" not in resultado.columns


def test_gera_indicadores_extras_ticker_ausente_nao_interrompe():
    """Ticker sem preco no handoff: fica sem valuation, sem levantar."""
    df = _df_fundamental(ticker="SEMPRECO3")
    resultado = fundamental.gera_indicadores_extras(df, {"PRIO3": 50.0})
    assert "P/L" not in resultado.columns
    assert len(resultado) == 1   # o loop terminou normalmente


# --- F4: rankeia_outros_indicadores_maior_melhor ---------------------------

def test_rankeia_maior_melhor_dez_valores_crescentes_dao_classes_1_a_10():
    df = pd.DataFrame({"ROIC": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
    resultado = fundamental.rankeia_outros_indicadores_maior_melhor(df, "ROIC")
    assert [int(x) for x in resultado["classe ROIC"]] == list(range(1, 11))


def test_rankeia_maior_melhor_muitos_empates_nao_levanta():
    """8 zeros e 2 positivos: bordas de decil colidem -> nao pode quebrar."""
    df = pd.DataFrame({"ROIC": [0, 0, 0, 0, 0, 0, 0, 0, 1, 2]})
    resultado = fundamental.rankeia_outros_indicadores_maior_melhor(df, "ROIC")
    assert "classe ROIC" in resultado.columns
    assert resultado["classe ROIC"].notna().all()


def test_rankeia_maior_melhor_atribui_fillna():
    """NaN no indicador vira 0 (fillna atribuido, ao contrario do legado)."""
    df = pd.DataFrame({"X": [1, 2, None, 4, 5, 6, 7, 8, 9, 10]})
    resultado = fundamental.rankeia_outros_indicadores_maior_melhor(df, "X")
    assert resultado["X"].isna().sum() == 0


def test_rankeia_maior_melhor_multiplos_indicadores():
    df = pd.DataFrame({
        "A": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "B": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    })
    resultado = fundamental.rankeia_outros_indicadores_maior_melhor(df, "A", "B")
    assert "classe A" in resultado.columns
    assert "classe B" in resultado.columns


# --- F5: rankeia_outros_indicadores_menor_melhor ---------------------------

def test_menor_melhor_permitido_menor_valor_pega_classe_10():
    """10 valores crescentes: o menor recebe classe 10, o maior classe 1."""
    df = pd.DataFrame({"DL": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})
    resultado = fundamental.rankeia_outros_indicadores_menor_melhor(df, "DL")
    assert [int(x) for x in resultado["classe DL"]] == list(range(10, 0, -1))


def test_menor_melhor_permitido_negativo_pode_pegar_melhor_classe():
    """Sem bloqueio, o menor valor (negativo) recebe a melhor classe."""
    df = pd.DataFrame({"PL": [-5.0, 1.0, 100.0]})
    resultado = fundamental.rankeia_outros_indicadores_menor_melhor(df, "PL")
    classes = [int(x) for x in resultado["classe PL"]]
    # row 0 = -5 (menor) deve ter classe maior que row 1 = 1.
    assert classes[0] > classes[1]
    assert classes[0] == max(classes)


def test_menor_melhor_bloqueado_negativo_nao_pega_melhor_classe():
    """Com bloqueio, o negativo e empurrado para a pior classe."""
    df = pd.DataFrame({"PL": [-5.0, 1.0, 100.0]})
    resultado = fundamental.rankeia_outros_indicadores_menor_melhor(
        df, "PL", bloquear_negativos=True
    )
    classes = [int(x) for x in resultado["classe PL"]]
    # row 0 = -5 (negativo) penalizado: classe pior que row 1 = 1 (baixo positivo).
    assert classes[0] < classes[1]
    assert classes[0] == min(classes)


def test_menor_melhor_atribui_fillna():
    df = pd.DataFrame({"X": [1, 2, None, 4, 5, 6, 7, 8, 9, 10]})
    resultado = fundamental.rankeia_outros_indicadores_menor_melhor(df, "X")
    assert resultado["X"].isna().sum() == 0


# --- F6: avaliacao_fundamentalista -----------------------------------------

def _linha_com_classes(setor, **classes):
    """Linha com Setor e as 6 colunas `classe ...` (decoys default = 100)."""
    base = {
        "Setor": setor,
        "classe P/L": 100, "classe Cres. Rec (5a)": 100,
        "classe ROIC": 100, "classe EV / EBIT": 100,
        "classe Dív. Líquida/Valor de mercado": 100, "classe P/VP": 100,
    }
    base.update({f"classe {k}": v for k, v in classes.items()})
    return base


def test_avaliacao_setor_geral_soma_colunas_gerais():
    """Setor geral soma P/L + Cres. Rec + ROIC + EV/EBIT (ignora Dív/P/VP)."""
    linha = _linha_com_classes(
        "Varejo",
        **{"P/L": 5, "Cres. Rec (5a)": 3, "ROIC": 8, "EV / EBIT": 2},
    )
    df = pd.DataFrame([linha])
    resultado = fundamental.avaliacao_fundamentalista(df)
    assert resultado["avaliacao_fundamentalista"].iloc[0] == 5 + 3 + 8 + 2


def test_avaliacao_setor_especial_soma_colunas_especiais():
    """Setor financeiro soma P/L + Cres. Rec + Dív/VM + P/VP (ignora ROIC/EVEBIT)."""
    linha = _linha_com_classes(
        "Previdência e Seguros",
        **{"P/L": 5, "Cres. Rec (5a)": 3,
           "Dív. Líquida/Valor de mercado": 7, "P/VP": 1},
    )
    df = pd.DataFrame([linha])
    resultado = fundamental.avaliacao_fundamentalista(df)
    assert resultado["avaliacao_fundamentalista"].iloc[0] == 5 + 3 + 7 + 1


def test_avaliacao_mistura_setores_usa_conjunto_correto_por_linha():
    geral = _linha_com_classes(
        "Varejo", **{"P/L": 1, "Cres. Rec (5a)": 1, "ROIC": 1, "EV / EBIT": 1}
    )
    especial = _linha_com_classes(
        "Intermediários Financeiros",
        **{"P/L": 2, "Cres. Rec (5a)": 2,
           "Dív. Líquida/Valor de mercado": 2, "P/VP": 2},
    )
    df = pd.DataFrame([geral, especial])
    resultado = fundamental.avaliacao_fundamentalista(df)
    assert resultado["avaliacao_fundamentalista"].iloc[0] == 4    # 1+1+1+1
    assert resultado["avaliacao_fundamentalista"].iloc[1] == 8    # 2+2+2+2


# --- F7: rankeando_empresas ------------------------------------------------

def test_rankeando_empresas_melhor_pior_e_meio_vazio():
    df = pd.DataFrame({
        "Ticker": ["A", "B", "C"],
        "Setor": ["X", "X", "X"],
        "avaliacao_fundamentalista": [10, 5, 1],
    })
    resultado = fundamental.rankeando_empresas(df).set_index("Ticker")
    assert resultado.loc["A", "Posicao setorial"] == "melhor"   # maior
    assert resultado.loc["C", "Posicao setorial"] == "pior"     # menor
    assert resultado.loc["B", "Posicao setorial"] == ""         # meio


def test_rankeando_empresas_por_setor_independente():
    df = pd.DataFrame({
        "Ticker": ["A", "B", "C", "D"],
        "Setor": ["X", "X", "Y", "Y"],
        "avaliacao_fundamentalista": [10, 1, 8, 2],
    })
    resultado = fundamental.rankeando_empresas(df).set_index("Ticker")
    assert resultado.loc["A", "Posicao setorial"] == "melhor"
    assert resultado.loc["B", "Posicao setorial"] == "pior"
    assert resultado.loc["C", "Posicao setorial"] == "melhor"
    assert resultado.loc["D", "Posicao setorial"] == "pior"


def test_rankeando_empresas_setor_de_uma_empresa_vira_pior():
    """max == min: 'melhor' e depois 'pior' (min roda por ultimo) -> 'pior'."""
    df = pd.DataFrame({
        "Ticker": ["A"],
        "Setor": ["X"],
        "avaliacao_fundamentalista": [42],
    })
    resultado = fundamental.rankeando_empresas(df).set_index("Ticker")
    assert resultado.loc["A", "Posicao setorial"] == "pior"


# --- F8: avaliacao_fundamentalista_analisys --------------------------------

def test_avaliacao_analisys_fronteiras():
    """Fronteiras: 14 -> -1, 15 -> 0, 31 -> 0, 32 -> 1."""
    df = pd.DataFrame({"avaliacao_fundamentalista": [14, 15, 31, 32]})
    resultado = fundamental.avaliacao_fundamentalista_analisys(df)
    assert list(resultado["Fundamental_?value"]) == [-1, 0, 0, 1]


def test_avaliacao_analisys_extremos():
    df = pd.DataFrame({"avaliacao_fundamentalista": [0, 50]})
    resultado = fundamental.avaliacao_fundamentalista_analisys(df)
    assert list(resultado["Fundamental_?value"]) == [-1, 1]


# --- F9: adicione_indicadores_e_ranking ------------------------------------

def test_adicione_indicadores_e_ranking_encadeia_F3_a_F8():
    """Fixture pequena passa por F3-F8 e sai com as colunas esperadas, sem
    'Unnamed' e sem NaN na avaliacao."""
    df = pd.DataFrame({
        "Ticker": ["PRIO3", "ASAI3", "LREN3"],
        "Setor": ["Petróleo", "Varejo", "Varejo"],
        "LPA": [5.0, 2.0, 3.0],
        "VPA": [10.0, 4.0, 6.0],
        "Nro. Ações": [1000.0, 2000.0, 1500.0],
        "Dív. Líquida": [2000.0, 1000.0, 3000.0],
        "Cres. Rec (5a)": [10.0, 5.0, 8.0],
        "ROIC": [15.0, 8.0, 12.0],
        "EV / EBIT": [6.0, 9.0, 7.0],
        "Unnamed: 0": [0, 1, 2],   # deve ser removida
    })
    precos = {"PRIO3": 50.0, "ASAI3": 30.0, "LREN3": 45.0}

    resultado = fundamental.adicione_indicadores_e_ranking(df, precos)

    # F3 criou os indicadores dependentes de preco.
    for col in ("P/L", "P/VP", "Dív. Líquida/Valor de mercado"):
        assert col in resultado.columns
    # F4/F5 criaram as classes.
    for col in ("classe Cres. Rec (5a)", "classe ROIC",
                "classe Dív. Líquida/Valor de mercado",
                "classe P/L", "classe P/VP", "classe EV / EBIT"):
        assert col in resultado.columns
    # F6/F7/F8.
    assert "avaliacao_fundamentalista" in resultado.columns
    assert "Posicao setorial" in resultado.columns
    assert "Fundamental_?value" in resultado.columns
    # Limpeza de 'Unnamed' e invariantes.
    assert not any("Unnamed" in c for c in resultado.columns)
    assert resultado["avaliacao_fundamentalista"].notna().all()
    assert set(resultado["Fundamental_?value"]).issubset({-1, 0, 1})


def test_adicione_indicadores_e_ranking_ranking_setorial():
    """No setor Varejo (2 empresas), uma vira 'melhor' e a outra 'pior'."""
    df = pd.DataFrame({
        "Ticker": ["ASAI3", "LREN3"],
        "Setor": ["Varejo", "Varejo"],
        "LPA": [2.0, 3.0],
        "VPA": [4.0, 6.0],
        "Nro. Ações": [2000.0, 1500.0],
        "Dív. Líquida": [1000.0, 3000.0],
        "Cres. Rec (5a)": [5.0, 8.0],
        "ROIC": [8.0, 12.0],
        "EV / EBIT": [9.0, 7.0],
    })
    precos = {"ASAI3": 30.0, "LREN3": 45.0}

    resultado = fundamental.adicione_indicadores_e_ranking(df, precos).set_index("Ticker")
    posicoes = set(resultado["Posicao setorial"])
    assert "melhor" in posicoes
    assert "pior" in posicoes


# --- F10: varre_lista ------------------------------------------------------

def _fake_puxar_por_url(url):
    """Mock de puxar_dados: o ticker e o sufixo da URL apos 'papel='."""
    ticker = url.split("=")[-1]
    return [pd.DataFrame([["Papel", ticker], ["Setor", "Varejo"], ["LPA", "5,0"]])]


def test_varre_lista_consolida_dois_tickers(monkeypatch):
    monkeypatch.setattr(fundamental, "puxar_dados", _fake_puxar_por_url)

    resultado = fundamental.varre_lista(["PRIO3", "ASAI3"])

    assert len(resultado) == 2
    assert set(resultado["Ticker"]) == {"PRIO3", "ASAI3"}


def test_varre_lista_pula_probleminhas(monkeypatch):
    monkeypatch.setattr(fundamental, "puxar_dados", _fake_puxar_por_url)

    resultado = fundamental.varre_lista(["PRIO3", "SKIP3"], probleminhas={"SKIP3"})

    assert len(resultado) == 1
    assert set(resultado["Ticker"]) == {"PRIO3"}


def test_varre_lista_falha_de_um_ticker_nao_interrompe(monkeypatch):
    def fake(url):
        ticker = url.split("=")[-1]
        if ticker == "BOOM3":
            raise ValueError("falha de rede")
        return _fake_puxar_por_url(url)

    monkeypatch.setattr(fundamental, "puxar_dados", fake)

    resultado = fundamental.varre_lista(["OK3", "BOOM3"])

    assert len(resultado) == 1
    assert set(resultado["Ticker"]) == {"OK3"}


def test_varre_lista_vazia_devolve_dataframe_vazio(monkeypatch):
    monkeypatch.setattr(fundamental, "puxar_dados", _fake_puxar_por_url)
    resultado = fundamental.varre_lista([])
    assert resultado.empty


def test_varre_lista_pula_ticker_sem_papel(monkeypatch, caplog):
    """Pagina do Fundamentus que nao tem a chave 'Papel' (ticker inexistente,
    redirect, layout quebrado) e pulada com warning, em vez de contaminar o
    concat e quebrar `gera_indicadores_extras` com `KeyError: 'Ticker'`."""
    def fake(url):
        ticker = url.split("=")[-1]
        if ticker == "FANTA3":
            # Pagina sem 'Papel': nada que sobreviva a `formatar_tabela`.
            return [pd.DataFrame([["Setor", "Varejo"], ["LPA", "5,0"]])]
        return _fake_puxar_por_url(url)

    monkeypatch.setattr(fundamental, "puxar_dados", fake)

    with caplog.at_level("WARNING"):
        resultado = fundamental.varre_lista(["OK3", "FANTA3"])

    assert set(resultado["Ticker"]) == {"OK3"}
    assert any("FANTA3" in r.message for r in caplog.records)
