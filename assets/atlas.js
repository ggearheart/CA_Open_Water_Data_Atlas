// Shared chrome + helpers for every plate.
const PLATES = [
  ["index.html", "Atlas"],
  ["plates/statute.html", "I · The Law"],
  ["plates/plan.html", "II · The Plan"],
];

const ROOT = document.documentElement.dataset.root || "";

function chrome() {
  const here = location.pathname.split("/").slice(-2).join("/");
  const nav = PLATES.slice(1).map(([href, label]) => {
    const cur = here.endsWith(href.split("/").pop()) ? ' aria-current="page"' : "";
    return `<a href="${ROOT}${href}"${cur}>${label}</a>`;
  }).join("");
  document.body.insertAdjacentHTML("afterbegin",
    `<header class="site"><div class="wrap"><a class="brand" href="${ROOT}index.html">CA Open Water Data Atlas</a><nav>${nav}</nav></div></header>`);
  document.body.insertAdjacentHTML("beforeend",
    `<footer class="site"><div class="wrap">An independent atlas of California's Open and Transparent Water Data Act (AB 1755, 2016). Not an official State publication. Data files live in <code>/data</code>; status judgments are drafts open to correction.</div></footer>`);
}

// Minimal RFC-4180 CSV parser -> array of objects.
function parseCSV(text) {
  const rows = []; let row = [], f = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { f += '"'; i++; }
      else if (c === '"') q = false;
      else f += c;
    } else if (c === '"') q = true;
    else if (c === ",") { row.push(f); f = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(f); f = ""; if (row.some(v => v !== "")) rows.push(row); row = [];
    } else f += c;
  }
  if (f !== "" || row.length) { row.push(f); rows.push(row); }
  const [head, ...body] = rows;
  return body.map(r => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ""])));
}

async function loadCSV(path) {
  const r = await fetch(ROOT + path);
  return parseCSV(await r.text());
}

// One floating tooltip shared by every chart on the page.
const tip = (() => {
  let el;
  return {
    show(html, ev) {
      if (!el) { el = document.createElement("div"); el.className = "tip"; document.body.append(el); }
      el.innerHTML = html; el.classList.add("on");
      const x = Math.min(ev.clientX + 14, innerWidth - el.offsetWidth - 8);
      const y = ev.clientY + 14 + el.offsetHeight > innerHeight ? ev.clientY - el.offsetHeight - 10 : ev.clientY + 14;
      el.style.left = x + "px"; el.style.top = y + "px";
    },
    hide() { el && el.classList.remove("on"); },
  };
})();

const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const STATUS = {
  done:       { label: "Done",        color: "var(--good)",     icon: "●" },
  partial:    { label: "Partial",     color: "var(--warning)",  icon: "◐" },
  not_done:   { label: "Not done",    color: "var(--critical)", icon: "○" },
  superseded: { label: "Superseded",  color: "var(--s1)",       icon: "↷" },
  unverified: { label: "Unverified",  color: "var(--neutral)",  icon: "?" },
};

chrome();
