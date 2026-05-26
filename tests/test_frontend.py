"""Testes automatizados do frontend (Fase 7).

Não rodam um browser — só validam:
- sintaxe JS é válida (via `node --check`)
- HTMLs principais existem e têm as tags esperadas
- JSON da fixture e da carteira parseiam

Testes visuais são responsabilidade do usuário (abrir no navegador local).

Comando: pytest
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SITE = RAIZ / "site"


def test_app_js_existe():
    assert (SITE / "assets" / "app.js").exists()


def test_app_css_existe():
    assert (SITE / "assets" / "app.css").exists()


def test_index_html_existe():
    assert (SITE / "index.html").exists()


def test_index_html_carrega_app_js_e_css():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert 'src="assets/app.js"' in html
    assert 'href="assets/app.css"' in html


def test_index_html_tem_listas_long_e_short():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    # Containers que o JS preenche.
    assert 'id="long-list"' in html
    assert 'id="short-list"' in html
    # Subtitulo da coluna numerica indica o que ela mostra (%_to_MMA50).
    # Duas vezes (uma em cada coluna long/short).
    assert html.count('class="col-sub">%_to_MMA50</div>') == 2


def test_app_js_sintaxe_valida():
    """`node --check` valida sintaxe sem executar o script."""
    if shutil.which("node") is None:
        pytest.skip("node não está no PATH; sintaxe JS não validada")

    result = subprocess.run(
        ["node", "--check", str(SITE / "assets" / "app.js")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"node --check falhou:\n{result.stderr}"


def test_carteira_json_dev_parseia():
    """Template de carteira no diretório dev (site/data/) é JSON válido."""
    carteira = json.loads((SITE / "data" / "carteira.json").read_text(encoding="utf-8"))
    assert "tickers" in carteira
    assert isinstance(carteira["tickers"], list)
    assert all(isinstance(t, str) for t in carteira["tickers"])


def test_latest_mock_dev_parseia_e_tem_shape_minimo():
    """O latest.json local de dev (cópia do mock) bate com o JSON Contract."""
    payload = json.loads((SITE / "data" / "latest.json").read_text(encoding="utf-8"))

    chaves_obrigatorias = {
        "schema_version", "run_id", "generated_at", "robusta_version",
        "input_universe", "summary", "portfolio_signals", "tickers",
        "warnings", "failed_tickers",
    }
    assert chaves_obrigatorias.issubset(payload.keys())

    # portfolio_signals quebrado em longs/shorts (não array unificado).
    assert "longs" in payload["portfolio_signals"]
    assert "shorts" in payload["portfolio_signals"]

    # tickers é dict (não array).
    assert isinstance(payload["tickers"], dict)
    assert len(payload["tickers"]) >= 3


def test_latest_mock_inclui_tickers_da_carteira():
    """Carteira referencia tickers — todos devem estar no latest.json mock."""
    carteira = json.loads((SITE / "data" / "carteira.json").read_text(encoding="utf-8"))
    payload = json.loads((SITE / "data" / "latest.json").read_text(encoding="utf-8"))

    for ticker in carteira["tickers"]:
        assert ticker in payload["tickers"], f"{ticker} da carteira não está no mock"


def test_ticker_html_existe():
    assert (SITE / "ticker.html").exists()


def test_ticker_html_tem_placeholders_dos_blocos():
    """ticker.html precisa ter os IDs que o JS popula."""
    html = (SITE / "ticker.html").read_text(encoding="utf-8")
    for placeholder in [
        'id="tk-name"', 'id="tk-price"', 'id="tk-subsetor"',
        'id="fund-score"', 'id="fund-sinal"', 'id="fund-pos"',
        'id="fund-pct-mma50"',
        'id="ruler"', 'id="meta-std"', 'id="meta-momentum"',
    ]:
        assert placeholder in html, f"falta {placeholder} em ticker.html"


def test_latest_mock_inclui_sentinelas():
    """Mock deve exercitar Abismo e Foguete pra validar tratamento visual."""
    payload = json.loads((SITE / "data" / "latest.json").read_text(encoding="utf-8"))
    valores = []
    for ticker, dado in payload["tickers"].items():
        for campo in ["sup_min_by_mslf", "sup_med_by_mslf", "sup_max_by_mslf",
                      "res_min_by_mslf", "res_med_by_mslf", "res_max_by_mslf"]:
            valores.append(dado.get(campo))
    assert "Abismo" in valores, "mock deve ter pelo menos 1 'Abismo' pra teste visual"
    assert "Foguete" in valores, "mock deve ter pelo menos 1 'Foguete' pra teste visual"


def test_ticker_html_tem_bloco_carteira():
    """7d: bloco 'Carteira' presente em ticker.html com tabela compacta (3 colunas)."""
    html = (SITE / "ticker.html").read_text(encoding="utf-8")
    assert 'class="block carteira"' in html
    assert 'id="carteira-table"' in html
    assert ">Carteira<" in html
    for header in ["ticker", "preço"]:
        assert header in html, f"falta header '{header}' na tabela da carteira"


def test_app_js_exporta_monta_mini_regua_sr():
    """7d: helper de mini-régua existe e está exportado em window.ROBUSTA."""
    js = (SITE / "assets" / "app.js").read_text(encoding="utf-8")
    assert "function montaMiniReguaSR" in js
    # Aparece também no objeto window.ROBUSTA (export)
    assert js.count("montaMiniReguaSR") >= 2
