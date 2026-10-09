const PALETTE = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948", "#b07aa1",
  "#ff9da7", "#9c755f", "#bab0ac", "#1f77b4", "#aec7e8", "#ffbb78", "#98df8a", "#c5b0d5",
  "#c49c94", "#f7b6d2", "#dbdb8d", "#9edae5", "#393b79"];
const NS = "http://www.w3.org/2000/svg";
const CSS = `
.pv { font-family: system-ui, sans-serif; user-select: none; font-size: 12px;
  --pv-unset: #ffffff; --pv-line: #9aa0a6; --pv-sel: #111; --pv-ring: #1a73e8; --pv-hover: rgba(127,127,127,.15); }
.pv.pv-dark { --pv-unset: #2a2a2a; --pv-line: #666; --pv-sel: #fff; --pv-ring: #8ab4f8; }
.pv-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
.pv-thumbs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.pv-thumb { font-size: 10px; text-align: center; cursor: pointer; }
.pv-thumb canvas { border: 2px solid transparent; border-radius: 3px; display: block; }
.pv-thumb.cur canvas { border-color: var(--pv-sel); }
.pv-main { display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; }
.pv-side { width: 260px; }
.pv-legend { max-height: 300px; overflow: auto; border: 1px solid var(--pv-line); border-radius: 6px; padding: 6px; }
.pv-li { display: flex; align-items: center; gap: 6px; padding: 2px 4px; border-radius: 4px; cursor: pointer; }
.pv-li:hover { background: var(--pv-hover); }
.pv-sw { width: 12px; height: 12px; border-radius: 6px; flex: none; }
.pv-cnt { margin-left: auto; opacity: .6; }
.pv-edit { margin-top: 12px; border: 1px solid var(--pv-line); border-radius: 6px; padding: 8px;
  display: flex; flex-direction: column; gap: 6px; }
.pv-label { font-size: 11px; text-transform: uppercase; opacity: .7; }
.pv-grad { height: 10px; border-radius: 3px; margin: 4px 0; }
.pv-hdr { cursor: pointer; font-size: 10px; fill: currentColor; }
.pv-hdr:hover { font-weight: bold; }
.pv-tip { position: fixed; pointer-events: none; background: #222; color: #fff; font-size: 11px;
  padding: 4px 6px; border-radius: 4px; display: none; white-space: pre; z-index: 1000; }
.pv-empty { opacity: .7; padding: 12px; }
.pv select, .pv input { font: inherit; color: inherit; background: transparent;
  border: 1px solid var(--pv-line); border-radius: 4px; padding: 3px 6px; }
.pv button { font: inherit; color: inherit; background: var(--pv-hover); cursor: pointer;
  border: 1px solid var(--pv-line); border-radius: 4px; padding: 4px 8px; }
.pv button:disabled { opacity: .5; cursor: default; }
`;

const wellName = (r, c) => String.fromCharCode(65 + r) + String(c + 1).padStart(2, "0");
const dims = (fmt) => (fmt === "384" ? [16, 24] : [8, 12]);
const isUnset = (v) => v === null || v === undefined || v === "";
const fmt = (n) => String(Number(n.toPrecision(3)));
const gradColor = (t) => `hsl(${220 - 200 * t} 70% ${85 - 45 * t}%)`;

function buildScale(model) {
  const all = [];
  for (const p of model.get("plates")) for (const v of model.get("values")[p] || []) if (!isUnset(v)) all.push(v);
  const nums = all.map(Number).filter((n) => !Number.isNaN(n));
  if (all.length && nums.length / all.length >= 0.9) {
    const pos = nums.filter((n) => n > 0);
    const logs = pos.map(Math.log10);
    const lo = logs.length ? Math.min(...logs) : 0;
    const hi = logs.length ? Math.max(...logs) : 0;
    return {
      numeric: true, lo: Math.pow(10, lo), hi: Math.pow(10, hi),
      color: (v) => {
        const n = Number(v);
        const t = n > 0 && hi > lo ? (Math.log10(n) - lo) / (hi - lo) : 0;
        return gradColor(Math.min(1, Math.max(0, t)));
      },
    };
  }
  const counts = new Map();
  for (const v of all) counts.set(v, (counts.get(v) || 0) + 1);
  const keys = [...counts.keys()];
  return { numeric: false, counts, color: (v) => PALETTE[keys.indexOf(v) % PALETTE.length] };
}

function render({ model, el }) {
  const controller = new AbortController();
  const { signal } = controller;
  const style = document.createElement("style");
  style.textContent = CSS;
  const root = document.createElement("div");
  root.className = "pv";
  const syncTheme = () => {
    const body = document.body;
    const dark = body.dataset.theme === "dark" || body.classList.contains("dark") || body.classList.contains("dark-theme");
    root.classList.toggle("pv-dark", dark);
  };
  syncTheme();
  const themeObserver = new MutationObserver(syncTheme);
  themeObserver.observe(document.body, { attributes: true, attributeFilter: ["class", "data-theme"] });
  root.innerHTML = `
    <div class="pv-bar">
      <label>Colour by <select data-ref="colorBy"></select></label>
      <span data-ref="selInfo"></span>
    </div>
    <div class="pv-thumbs" data-ref="thumbs"></div>
    <div class="pv-main">
      <div data-ref="plate"></div>
      <div class="pv-side">
        <div class="pv-label">Legend</div>
        <div class="pv-legend" data-ref="legend"></div>
        <div class="pv-edit">
          <div class="pv-label">Edit selected wells</div>
          <select data-ref="editField"></select>
          <input data-ref="editValue" placeholder="value (suggests existing)">
          <datalist data-ref="valList"></datalist>
          <button data-ref="apply">Apply</button>
          <button data-ref="undo">Undo last edit</button>
        </div>
      </div>
    </div>
    <div class="pv-tip" data-ref="tip"></div>`;
  el.append(style, root);
  const $ = (name) => root.querySelector(`[data-ref="${name}"]`);
  const listId = `pv-vals-${Math.random().toString(36).slice(2)}`;
  $("valList").id = listId;
  $("editValue").setAttribute("list", listId);

  let selected = new Set(model.get("selection"));
  let cells = [];
  let scale = buildScale(model);
  let drag = null;

  function commitSelection() {
    model.set("selection", [...selected]);
    model.save_changes();
  }

  function paintSelection() {
    for (const { ring, name } of cells) ring.style.display = selected.has(name) ? "" : "none";
    const n = selected.size;
    $("selInfo").textContent = `${n} well${n === 1 ? "" : "s"} selected on ${model.get("current_plate")}`;
    $("apply").textContent = `Apply to ${n} well${n === 1 ? "" : "s"}`;
    $("apply").disabled = n === 0;
  }

  function setSelection(next) {
    selected = next;
    paintSelection();
    commitSelection();
  }

  function fillSelect(select, options, value) {
    select.replaceChildren(...options.map((o) => new Option(o, o)));
    if (options.includes(value)) select.value = value;
  }

  function fillSuggestions() {
    const field = $("editField").value;
    const seen = new Set();
    for (const d of Object.values(model.get("detail"))) if (d[field]) seen.add(d[field]);
    if (field === model.get("color_field"))
      for (const p of model.get("plates")) for (const v of model.get("values")[p] || []) if (!isUnset(v)) seen.add(v);
    $("valList").replaceChildren(...[...seen].sort().map((v) => new Option(v)));
  }

  function drawPlate() {
    const plate = model.get("current_plate");
    if (!plate) {
      $("plate").innerHTML = `<div class="pv-empty">No wells to show. Load a template with assay conditions.</div>`;
      cells = [];
      return;
    }
    const [R, C] = dims(model.get("plate_format"));
    const vals = model.get("values")[plate] || [];
    const s = R === 16 ? 22 : 36;
    const pad = 24;
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("width", pad + C * s + 4);
    svg.setAttribute("height", pad + R * s + 4);
    const header = (x, y, text, wells) => {
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", x);
      t.setAttribute("y", y);
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("class", "pv-hdr");
      t.textContent = text;
      t.addEventListener("click", (e) => {
        const next = e.shiftKey ? new Set(selected) : new Set();
        wells.forEach((w) => next.add(w));
        setSelection(next);
      });
      svg.append(t);
    };
    const allWells = [];
    for (let r = 0; r < R; r++) for (let c = 0; c < C; c++) allWells.push(wellName(r, c));
    header(10, 14, "all", allWells);
    for (let c = 0; c < C; c++) header(pad + c * s + s / 2, 14, c + 1, [...Array(R).keys()].map((r) => wellName(r, c)));
    for (let r = 0; r < R; r++) header(10, pad + r * s + s / 2 + 3, String.fromCharCode(65 + r), [...Array(C).keys()].map((c) => wellName(r, c)));
    const detail = model.get("detail");
    const tip = $("tip");
    cells = [];
    for (let r = 0; r < R; r++) {
      for (let c = 0; c < C; c++) {
        const name = wellName(r, c);
        const v = vals[r * C + c];
        const empty = isUnset(v);
        const node = document.createElementNS(NS, "circle");
        node.setAttribute("cx", pad + c * s + s / 2);
        node.setAttribute("cy", pad + r * s + s / 2);
        node.setAttribute("r", s / 2 - 5);
        node.setAttribute("class", "pv-well");
        node.setAttribute("fill", empty ? "var(--pv-unset)" : scale.color(v));
        if (empty) {
          node.setAttribute("stroke", "var(--pv-line)");
          node.setAttribute("stroke-dasharray", "2 2");
        }
        const ring = document.createElementNS(NS, "circle");
        ring.setAttribute("cx", pad + c * s + s / 2);
        ring.setAttribute("cy", pad + r * s + s / 2);
        ring.setAttribute("r", s / 2 - 2);
        ring.setAttribute("fill", "none");
        ring.setAttribute("stroke", "var(--pv-ring)");
        ring.setAttribute("stroke-width", 3);
        ring.style.pointerEvents = "none";
        ring.style.display = "none";
        node.style.cursor = "pointer";
        node.addEventListener("mousedown", (e) => {
          drag = { r, c, base: e.shiftKey ? new Set(selected) : new Set() };
          selected = new Set([...drag.base, name]);
          paintSelection();
          e.preventDefault();
        });
        node.addEventListener("mouseenter", () => {
          const d = detail[name];
          const lines = d && Object.keys(d).length
            ? Object.entries(d).map(([k, x]) => `${k}: ${x}`).join("\n")
            : "(no metadata)";
          tip.textContent = `${plate} · ${name}\n${lines}`;
          tip.style.display = "block";
          if (drag) {
            const next = new Set(drag.base);
            for (let rr = Math.min(drag.r, r); rr <= Math.max(drag.r, r); rr++)
              for (let cc = Math.min(drag.c, c); cc <= Math.max(drag.c, c); cc++) next.add(wellName(rr, cc));
            selected = next;
            paintSelection();
          }
        });
        node.addEventListener("mousemove", (e) => {
          tip.style.left = `${e.clientX + 14}px`;
          tip.style.top = `${e.clientY + 14}px`;
        });
        node.addEventListener("mouseleave", () => { tip.style.display = "none"; });
        svg.append(node, ring);
        cells.push({ node, ring, name, value: v, empty });
      }
    }
    $("plate").replaceChildren(svg);
    paintSelection();
  }

  function drawLegend() {
    const legend = $("legend");
    const unsetRow = `<div class="pv-li" data-v=""><span class="pv-sw" style="background:var(--pv-unset);border:1px dashed var(--pv-line)"></span>unset</div>`;
    if (scale.numeric) {
      const stops = [0, 0.25, 0.5, 0.75, 1].map(gradColor).join(",");
      legend.innerHTML = `<div data-ref="gradTitle"></div>
        <div class="pv-grad" style="background:linear-gradient(90deg,${stops})"></div>
        <div style="display:flex;justify-content:space-between"><span>${fmt(scale.lo)}</span><span>${fmt(scale.hi)}</span></div>${unsetRow}`;
      legend.querySelector('[data-ref="gradTitle"]').textContent = `${model.get("color_field")} (log scale)`;
    } else {
      const rows = [...scale.counts].sort((a, b) => b[1] - a[1]);
      legend.innerHTML = "";
      for (const [v, n] of rows) {
        const li = document.createElement("div");
        li.className = "pv-li";
        li.dataset.v = v;
        const sw = document.createElement("span");
        sw.className = "pv-sw";
        sw.style.background = scale.color(v);
        const label = document.createElement("span");
        label.textContent = v;
        const cnt = document.createElement("span");
        cnt.className = "pv-cnt";
        cnt.textContent = n;
        li.append(sw, label, cnt);
        legend.append(li);
      }
      legend.insertAdjacentHTML("beforeend", unsetRow);
    }
    for (const li of legend.querySelectorAll(".pv-li")) {
      const v = li.dataset.v;
      const match = (cell) => (v === "" ? cell.empty : !cell.empty && String(cell.value) === v);
      li.addEventListener("mouseenter", () => cells.forEach((cell) => { cell.node.style.opacity = match(cell) ? 1 : 0.15; }));
      li.addEventListener("mouseleave", () => cells.forEach((cell) => { cell.node.style.opacity = 1; }));
      li.addEventListener("click", (e) => {
        const next = e.shiftKey ? new Set(selected) : new Set();
        cells.forEach((cell) => { if (match(cell)) next.add(cell.name); });
        setSelection(next);
      });
    }
  }

  function drawThumbs() {
    const [R, C] = dims(model.get("plate_format"));
    const current = model.get("current_plate");
    const values = model.get("values");
    $("thumbs").replaceChildren(...model.get("plates").map((p) => {
      const canvas = document.createElement("canvas");
      const k = R === 16 ? 3 : 5;
      canvas.width = C * k;
      canvas.height = R * k;
      const ctx = canvas.getContext("2d");
      const pv = values[p] || [];
      for (let i = 0; i < R * C; i++) {
        ctx.fillStyle = isUnset(pv[i]) ? "#e8e8e8" : scale.color(pv[i]);
        ctx.fillRect((i % C) * k, Math.floor(i / C) * k, k - 0.5, k - 0.5);
      }
      const wrap = document.createElement("div");
      wrap.className = `pv-thumb${p === current ? " cur" : ""}`;
      wrap.title = p;
      wrap.append(canvas, p);
      wrap.addEventListener("click", () => {
        model.set("current_plate", p);
        model.save_changes();
      });
      return wrap;
    }));
  }

  function redraw() {
    scale = buildScale(model);
    fillSelect($("colorBy"), model.get("fields"), model.get("color_field"));
    const editField = $("editField").value || model.get("color_field");
    fillSelect($("editField"), model.get("fields"), editField);
    $("undo").disabled = !model.get("can_undo");
    drawThumbs();
    drawPlate();
    drawLegend();
    fillSuggestions();
  }

  function apply() {
    if (!selected.size) return;
    model.set("edit_request", {
      id: Date.now(),
      action: "set",
      plate: model.get("current_plate"),
      wells: [...selected],
      field: $("editField").value,
      value: $("editValue").value,
    });
    model.save_changes();
  }

  $("colorBy").addEventListener("change", (e) => {
    model.set("color_field", e.target.value);
    model.save_changes();
    $("editField").value = e.target.value;
  }, { signal });
  $("editField").addEventListener("change", fillSuggestions, { signal });
  $("apply").addEventListener("click", apply, { signal });
  $("editValue").addEventListener("keydown", (e) => { if (e.key === "Enter") apply(); }, { signal });
  $("undo").addEventListener("click", () => {
    model.set("edit_request", { id: Date.now(), action: "undo" });
    model.save_changes();
  }, { signal });
  window.addEventListener("mouseup", () => {
    if (drag) {
      drag = null;
      commitSelection();
    }
  }, { signal });
  root.tabIndex = 0;
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape") setSelection(new Set());
  }, { signal });

  for (const trait of ["values", "plates", "fields", "plate_format", "color_field", "current_plate", "can_undo"])
    model.on(`change:${trait}`, redraw);
  model.on("change:detail", () => { drawPlate(); fillSuggestions(); });
  model.on("change:selection", () => {
    selected = new Set(model.get("selection"));
    paintSelection();
  });
  redraw();
  return () => {
    controller.abort();
    themeObserver.disconnect();
  };
}

export default { render };
