const state = {
  data: null,
  kind: "all",
  sort: "weight",
  query: "",
  active: null,
};

const $ = (id) => document.getElementById(id);

function directionClass(direction) {
  if (direction === "RISING" || direction === "UPPER_LIMIT") return "up";
  if (direction === "FALLING" || direction === "LOWER_LIMIT") return "down";
  return "flat";
}

function formatWon(value) {
  return `${Math.round(value).toLocaleString("ko-KR")}원`;
}

function formatCap(value) {
  const jo = value / 1e12;
  if (Math.abs(jo) >= 1) {
    return `${jo.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}조`;
  }
  const eok = value / 1e8;
  return `${eok.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}억`;
}

function formatWeight(value) {
  if (value >= 1) return `${value.toFixed(2)}%`;
  if (value >= 0.01) return `${value.toFixed(3)}%`;
  return `${value.toFixed(4)}%`;
}

function formatSigned(value, digits = 2) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toLocaleString("ko-KR", { maximumFractionDigits: digits })}`;
}

function topicParticle(name) {
  const last = name.charCodeAt(name.length - 1);
  if (Number.isNaN(last) || last < 0xac00 || last > 0xd7a3) return "는";
  return (last - 0xac00) % 28 === 0 ? "는" : "은";
}

function formatWhen(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function marketLabel(status) {
  if (status === "OPEN") return "장중";
  if (status === "CLOSE") return "장마감";
  if (status === "PREOPEN") return "개장 전";
  return status || "시세";
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function visibleStocks() {
  const query = state.query.trim().toLowerCase();
  let rows = state.data.stocks.filter((stock) => {
    if (state.kind === "common" && stock.preferred) return false;
    if (state.kind === "preferred" && !stock.preferred) return false;
    if (!query) return true;
    return stock.name.toLowerCase().includes(query) || stock.code.includes(query);
  });
  const sorters = {
    weight: (a, b) => b.weight - a.weight,
    marketCap: (a, b) => b.marketCap - a.marketCap,
    changeRate: (a, b) => b.changeRate - a.changeRate,
    price: (a, b) => b.price - a.price,
    name: (a, b) => a.name.localeCompare(b.name, "ko"),
  };
  rows.sort(sorters[state.sort]);
  return rows;
}

function render() {
  const data = state.data;
  const leader = data.stocks[0];
  $("hero-line").innerHTML = leader
    ? `${escapeHtml(leader.name)}${topicParticle(leader.name)} 코스피 시가총액의 <em>${formatWeight(leader.weight)}</em>입니다.`
    : "표시할 종목이 없습니다.";

  const indexClass = directionClass(data.index.direction);
  const indexSign = data.index.change > 0 ? "+" : "";
  $("stats").innerHTML = [
    ["코스피", data.index.close.toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }), `<span class="${indexClass}">${indexSign}${data.index.change.toLocaleString("ko-KR")} (${formatSigned(data.index.changeRate)}%)</span>`],
    ["코스피 시가총액", formatCap(data.totalMarketCap), "상장 주식 합계"],
    ["종목 수", data.stockCount.toLocaleString("ko-KR"), `보통주 ${data.commonCount.toLocaleString("ko-KR")} · 우선주 ${data.preferredCount.toLocaleString("ko-KR")}`],
    ["상위 10종목", formatWeight(data.concentration.top10), "시가총액 합계 대비"],
  ].map(([label, value, sub]) => `
    <article class="stat">
      <span>${label}</span>
      <strong>${value}</strong>
      <small>${sub}</small>
    </article>
  `).join("");

  const top = data.stocks.slice(0, 12);
  const maxWeight = top[0]?.weight || 1;
  $("chart").innerHTML = top.map((stock) => `
    <div class="bar-row">
      <div class="bar-name" title="${escapeHtml(stock.name)}">${escapeHtml(stock.name)}</div>
      <div class="bar-track"><i class="bar-fill" style="width:${(stock.weight / maxWeight) * 100}%"></i></div>
      <div class="bar-weight">${formatWeight(stock.weight)}</div>
    </div>
  `).join("");

  const bands = [
    ["1위", data.concentration.top1],
    ["5위까지", data.concentration.top5],
    ["10위까지", data.concentration.top10],
    ["30위까지", data.concentration.top30],
  ];
  $("concentration").innerHTML = bands.map(([label, value]) => `
    <div class="conc-row">
      <span>${label}</span>
      <div class="meter"><i style="width:${Math.min(value, 100)}%"></i></div>
      <strong>${formatWeight(value)}</strong>
    </div>
  `).join("");
  $("note").textContent = data.note;

  const rows = visibleStocks();
  $("result-count").textContent = `${rows.length.toLocaleString("ko-KR")}개 종목`;
  $("rows").innerHTML = rows.length
    ? rows.map((stock) => {
        const cls = directionClass(stock.direction);
        const rate = `${formatSigned(stock.changeRate)}%`;
        return `
          <tr data-code="${stock.code}" class="${state.active === stock.code ? "is-active" : ""}">
            <td>${stock.rank}</td>
            <td>
              <div class="name-cell">
                <img alt="" src="${escapeHtml(stock.logo)}" />
                <div>
                  <strong>${escapeHtml(stock.name)}${stock.preferred ? '<span class="tag">우선주</span>' : ""}</strong>
                  <span class="code">${stock.code}</span>
                </div>
              </div>
            </td>
            <td class="num">${formatWon(stock.price)}</td>
            <td class="num ${cls}">${rate}</td>
            <td class="num">${formatCap(stock.marketCap)}</td>
            <td class="num weight-cell">
              <div class="weight-line">
                <div class="mini-track"><i style="width:${Math.min(stock.weight / maxWeight * 100, 100)}%"></i></div>
                <strong>${formatWeight(stock.weight)}</strong>
              </div>
            </td>
            <td class="num">${formatWeight(stock.cumulative)}</td>
          </tr>
        `;
      }).join("")
    : `<tr><td class="empty" colspan="7">조건에 맞는 종목이 없습니다.</td></tr>`;

  $("status-line").textContent = `${marketLabel(data.marketStatus)} · ${formatWhen(data.asOf)} 기준${data.cached ? " · 잠시 저장된 시세" : ""}`;
}

async function load(refresh) {
  $("status-line").textContent = "시세를 불러오는 중";
  $("refresh").disabled = true;
  try {
    let response;
    try {
      response = await fetch(refresh ? "/api/market/refresh" : "/api/market");
      if (!response.ok && response.status === 404) {
        // 정적 호스팅(GitHub Pages 등) 환경 fallback
        response = await fetch("./data/market.json");
      }
    } catch {
      response = await fetch("./data/market.json");
    }
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.error || "요청 실패");
    state.data = payload;
    render();
  } catch (error) {
    $("hero-line").textContent = "시세를 가져오지 못했습니다.";
    $("status-line").textContent = error.message;
  } finally {
    $("refresh").disabled = false;
  }
}

$("refresh").addEventListener("click", () => load(true));
$("query").addEventListener("input", (event) => {
  state.query = event.target.value;
  render();
});
$("sort").addEventListener("change", (event) => {
  state.sort = event.target.value;
  render();
});
document.querySelector(".filters").addEventListener("click", (event) => {
  const button = event.target.closest("[data-kind]");
  if (!button) return;
  state.kind = button.dataset.kind;
  document.querySelectorAll(".chip").forEach((chip) => chip.classList.toggle("is-on", chip === button));
  render();
});
$("rows").addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-code]");
  if (!row) return;
  state.active = row.dataset.code;
  render();
});

load(false);
