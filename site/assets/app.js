/*
 * ROBUSTA frontend — vanilla JS, sem framework, sem build.
 *
 * Responsabilidades:
 *   - busca `/data/latest.json` (gerado pelo pipeline Python via persistence.py)
 *   - busca `/data/carteira.json` (lista de tickers da carteira pessoal)
 *   - parseia `?ticker=XXXX` da URL para a página de drill-down
 *   - renderiza o dashboard (index.html) e a página do ticker (ticker.html)
 *
 * Sem dependências. Carregado direto via <script> tag nos dois HTML.
 */

"use strict";

const DATA_URL = "/data/latest.json";
const CARTEIRA_URL = "/data/carteira.json";

/* ------------------------------------------------------------------ */
/*  fetch + parse                                                     */
/* ------------------------------------------------------------------ */

async function carregaDados() {
  const [latestRes, carteiraRes] = await Promise.all([
    fetch(DATA_URL, { cache: "no-cache" }),
    fetch(CARTEIRA_URL, { cache: "no-cache" }).catch(() => null),
  ]);

  if (!latestRes.ok) {
    throw new Error(`falha ao carregar ${DATA_URL}: HTTP ${latestRes.status}`);
  }
  const latest = await latestRes.json();

  let carteira = { tickers: [] };
  if (carteiraRes && carteiraRes.ok) {
    try {
      carteira = await carteiraRes.json();
    } catch (e) {
      console.warn("carteira.json existe mas não parseou", e);
    }
  }

  return {
    runId: latest.run_id,
    generatedAt: latest.generated_at,
    summary: latest.summary || {},
    signals: latest.portfolio_signals || { longs: [], shorts: [] },
    tickers: latest.tickers || {},
    warnings: latest.warnings || [],
    failedTickers: latest.failed_tickers || [],
    carteira: carteira.tickers || [],
  };
}

/* ------------------------------------------------------------------ */
/*  helpers de URL e formato                                          */
/* ------------------------------------------------------------------ */

function getTickerParam() {
  const params = new URLSearchParams(window.location.search);
  const t = params.get("ticker");
  return t ? t.toUpperCase().trim() : null;
}

function urlDoTicker(ticker) {
  return `ticker.html?ticker=${encodeURIComponent(ticker)}`;
}

function formataData(iso) {
  // "2026-05-26T16:00:00+00:00" -> "26 mai 2026 · 13:00 BRT"
  // (assume UTC e converte mentalmente -3h pra BRT na exibição)
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;

  const meses = ["jan", "fev", "mar", "abr", "mai", "jun",
                 "jul", "ago", "set", "out", "nov", "dez"];
  const dia = String(d.getUTCDate()).padStart(2, "0");
  const mes = meses[d.getUTCMonth()];
  const ano = d.getUTCFullYear();
  // BRT = UTC-3
  const horaBRT = (d.getUTCHours() - 3 + 24) % 24;
  const min = String(d.getUTCMinutes()).padStart(2, "0");
  return `${dia} ${mes} ${ano} · ${String(horaBRT).padStart(2, "0")}:${min} BRT`;
}

function formataPreco(valor) {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
  return "R$ " + valor.toFixed(2).replace(".", ",");
}

function formataPercentual(valor) {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
  const abs = Math.abs(valor).toFixed(2).replace(".", ",");
  return valor >= 0 ? `+${abs}%` : `−${abs}%`;
}

function formataSinal(valor) {
  if (valor === null || valor === undefined) return "0";
  if (valor > 0) return "+1";
  if (valor < 0) return "−1";
  return "0";
}

function ehSentinela(valor) {
  return valor === "Abismo" || valor === "Foguete";
}

function formataNivel(valor) {
  if (ehSentinela(valor)) return valor;
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
  return formataPreco(valor);
}

/* ------------------------------------------------------------------ */
/*  régua SVG suporte/resistência                                     */
/* ------------------------------------------------------------------ */

/*
 * Layout ordinal (posições fixas, independente dos valores reais):
 *   sup_min: x=40    sup_med: x=155   sup_max: x=345
 *   PREÇO:   x=475 (círculo clay)
 *   res_min: x=585   res_med: x=700   res_max: x=840
 *
 * Sentinelas "Abismo" / "Foguete" mostram o label em vez de número, e omitem
 * a linha vertical do nível (não há preço pra marcar).
 */

const NIVEL_LAYOUT = [
  { campo: "sup_min_by_mslf", x:  40, label: "sup_min", cor: "#788C5D" },
  { campo: "sup_med_by_mslf", x: 155, label: "sup_med", cor: "#788C5D" },
  { campo: "sup_max_by_mslf", x: 345, label: "sup_max", cor: "#788C5D" },
  { campo: "res_min_by_mslf", x: 585, label: "res_min", cor: "#8A3B1E" },
  { campo: "res_med_by_mslf", x: 700, label: "res_med", cor: "#8A3B1E" },
  { campo: "res_max_by_mslf", x: 840, label: "res_max", cor: "#8A3B1E" },
];

function svgEl(name, attrs, texto) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  if (texto !== undefined) el.textContent = texto;
  return el;
}

function montaReguaSR(ticker) {
  const svg = svgEl("svg", {
    viewBox: "0 0 880 110",
    role: "img",
    "aria-label": "Régua de suporte e resistência",
  });

  // linha base
  svg.appendChild(svgEl("line", {
    x1: 40, y1: 55, x2: 840, y2: 55,
    stroke: "#D1CFC5", "stroke-width": 1.5,
  }));

  // níveis sup/res
  for (const n of NIVEL_LAYOUT) {
    const valor = ticker[n.campo];

    if (!ehSentinela(valor)) {
      // linha vertical do nível
      svg.appendChild(svgEl("line", {
        x1: n.x, y1: 40, x2: n.x, y2: 70,
        stroke: n.cor, "stroke-width": 2,
      }));
    }
    // valor (ou rótulo sentinela "Abismo"/"Foguete")
    svg.appendChild(svgEl("text", {
      x: n.x, y: 92, "text-anchor": "middle",
      "font-size": 12, fill: "#3D3D3A",
      "font-family": "ui-monospace, monospace",
      "font-style": ehSentinela(valor) ? "italic" : "normal",
    }, formataNivel(valor)));
    // label do campo
    svg.appendChild(svgEl("text", {
      x: n.x, y: 106, "text-anchor": "middle",
      "font-size": 10, fill: "#87867F",
      "font-family": "ui-monospace, monospace",
    }, n.label));
  }

  // preço (círculo clay no centro)
  svg.appendChild(svgEl("circle", {
    cx: 475, cy: 55, r: 9,
    fill: "#D97757", stroke: "#FFFFFF", "stroke-width": 3,
  }));
  svg.appendChild(svgEl("text", {
    x: 475, y: 32, "text-anchor": "middle",
    "font-size": 14, fill: "#141413",
    "font-family": "ui-monospace, monospace", "font-weight": 700,
  }, formataPreco(ticker.preco)));
  svg.appendChild(svgEl("text", {
    x: 475, y: 18, "text-anchor": "middle",
    "font-size": 10, fill: "#D97757",
    "font-family": "ui-monospace, monospace",
    "letter-spacing": 1,
  }, "PREÇO"));

  return svg;
}

/* ------------------------------------------------------------------ */
/*  mini-régua S/R (versão compacta para a tabela da carteira)        */
/* ------------------------------------------------------------------ */

/*
 * Layout ordinal fixo, espelhando o da régua grande mas em viewBox 320×26.
 * Sem labels numéricos, sem texto — só a linha base, 6 marcações e o círculo
 * de preço. Sentinelas "Abismo"/"Foguete" omitem a linha vertical do nível.
 */

const MINI_NIVEL_LAYOUT = [
  { campo: "sup_min_by_mslf", x:  15, cor: "#788C5D" },
  { campo: "sup_med_by_mslf", x:  58, cor: "#788C5D" },
  { campo: "sup_max_by_mslf", x: 125, cor: "#788C5D" },
  { campo: "res_min_by_mslf", x: 215, cor: "#8A3B1E" },
  { campo: "res_med_by_mslf", x: 262, cor: "#8A3B1E" },
  { campo: "res_max_by_mslf", x: 305, cor: "#8A3B1E" },
];

function montaMiniReguaSR(ticker) {
  const svg = svgEl("svg", {
    viewBox: "0 0 320 26",
    role: "img",
    "aria-label": "Mini-régua S/R",
  });

  svg.appendChild(svgEl("line", {
    x1: 6, y1: 13, x2: 314, y2: 13,
    stroke: "#D1CFC5", "stroke-width": 1,
  }));

  for (const n of MINI_NIVEL_LAYOUT) {
    const valor = ticker[n.campo];
    if (ehSentinela(valor)) continue;
    svg.appendChild(svgEl("line", {
      x1: n.x, y1: 6, x2: n.x, y2: 20,
      stroke: n.cor, "stroke-width": 1.5,
    }));
  }

  svg.appendChild(svgEl("circle", {
    cx: 170, cy: 13, r: 5,
    fill: "#D97757", stroke: "#FFFFFF", "stroke-width": 2,
  }));

  return svg;
}

/* ------------------------------------------------------------------ */
/*  shape público — pra testes manuais via console e pros HTMLs       */
/* ------------------------------------------------------------------ */

window.ROBUSTA = {
  carregaDados,
  getTickerParam,
  urlDoTicker,
  formataData,
  formataPreco,
  formataPercentual,
  formataSinal,
  formataNivel,
  ehSentinela,
  montaReguaSR,
  montaMiniReguaSR,
};
