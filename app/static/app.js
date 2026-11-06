/* TagTrack front-end: scan-to-register, live tracking, steppers, on-screen keyboard. */
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const getJSON = (url) => fetch(url, { cache: "no-store" }).then((r) => r.json());

  // ---- kiosk flag: the Pi launches http://localhost:8080/?kiosk=1 -------------
  try {
    if (new URLSearchParams(location.search).get("kiosk") === "1") localStorage.setItem("kiosk", "1");
  } catch (e) {}
  const isKiosk = (() => { try { return localStorage.getItem("kiosk") === "1"; } catch (e) { return false; } })();

  // ---- reader status pill (refresh every 3 s) ----------------------------------
  const pill = $("#reader-status");
  if (pill) setInterval(() => getJSON("/api/status").then((s) => {
    pill.className = "status status-" + s.status;
    pill.textContent = pill.textContent.split(" · ")[0] + " · " + s.status;
    pill.title = s.error || s.info || "";
  }).catch(() => {}), 3000);

  // ---- +/- steppers on the settings screen -------------------------------------
  $$(".stepper").forEach((st) => {
    const inp = $("input", st), step = +st.dataset.step, min = +st.dataset.min, max = +st.dataset.max;
    const bump = (d) => { const v = Math.min(max, Math.max(min, (parseFloat(inp.value) || 0) + d)); inp.value = Math.round(v * 10) / 10; };
    $(".step-down", st).onclick = () => bump(-step);
    $(".step-up", st).onclick = () => bump(step);
  });

  // ---- on-screen keyboard (kiosk only; phones use their own keyboard) ---------
  const osk = $("#osk");
  let target = null, shift = true;
  const ROWS = [["1","2","3","4","5","6","7","8","9","0"], ["q","w","e","r","t","y","u","i","o","p"],
    ["a","s","d","f","g","h","j","k","l","-"], ["⇧","z","x","c","v","b","n","m","⌫"], ["#", "space", "'", "Done"]];
  function drawOsk() {
    osk.innerHTML = ROWS.map((row) => '<div class="osk-row">' + row.map((k) => {
      const cls = k === "space" ? "space" : k === "Done" ? "wide done" : (k === "⇧" || k === "⌫") ? "wide" : "";
      const label = k === "space" ? "" : (shift && k.length === 1 ? k.toUpperCase() : k);
      return `<button type="button" class="${cls}" data-k="${esc(k)}">${esc(label)}</button>`;
    }).join("") + "</div>").join("");
  }
  if (osk && isKiosk) {
    osk.addEventListener("pointerdown", (e) => e.preventDefault()); // keep focus in the input
    osk.addEventListener("click", (e) => {
      const k = e.target.dataset && e.target.dataset.k;
      if (!k || !target) return;
      if (k === "Done") { target.blur(); return hideOsk(); }
      if (k === "⇧") { shift = !shift; return drawOsk(); }
      if (k === "⌫") target.value = target.value.slice(0, -1);
      else { target.value += k === "space" ? " " : (shift ? k.toUpperCase() : k); if (shift) { shift = false; drawOsk(); } }
      target.dispatchEvent(new Event("input"));
    });
    $$(".osk-input").forEach((inp) => {
      inp.setAttribute("inputmode", "none"); // stop any system keyboard popping up too
      inp.addEventListener("focus", () => { target = inp; shift = inp.value === ""; drawOsk(); osk.hidden = false; document.body.classList.add("osk-open"); setTimeout(() => inp.scrollIntoView({ block: "center" }), 50); });
    });
    document.addEventListener("pointerdown", (e) => {
      if (!osk.hidden && !osk.contains(e.target) && !e.target.classList.contains("osk-input")) hideOsk();
    });
  }
  function hideOsk() { if (osk) { osk.hidden = true; document.body.classList.remove("osk-open"); } }

  // ---- quick-name chips ---------------------------------------------------------
  function initQuickNames() {
    $$(".quick .chip").forEach((b) => b.addEventListener("click", () => {
      const name = $("#name"); name.value = b.dataset.name;
      name.closest(".field").scrollIntoView({ block: "center" });
    }));
  }

  // ---- add-item: show strongest unregistered tag, lock it in -------------------
  function initScan() {
    const box = $("#scanbox"), msg = $("#scan-msg"), tagEl = $("#scan-tag"), meta = $("#scan-meta");
    const lockBtn = $("#scan-lock"), resetBtn = $("#scan-reset"), epcInput = $("#epc");
    let locked = false, candidate = null;

    function lock(epc) {
      locked = true; epcInput.value = epc;
      box.className = "scanbox locked";
      msg.innerHTML = "✓ Tag selected. Now name the item.";
      tagEl.textContent = epc; meta.textContent = "";
      lockBtn.hidden = true; resetBtn.hidden = false;
    }
    function unlock() {
      locked = false; epcInput.value = ""; candidate = null;
      box.className = "scanbox"; lockBtn.hidden = false; resetBtn.hidden = true; lockBtn.disabled = true;
      msg.innerHTML = "Hold <b>one</b> tag close to the reader antenna…"; tagEl.textContent = "";
    }
    lockBtn.onclick = () => candidate && lock(candidate);
    resetBtn.onclick = unlock;
    $("#item-form").addEventListener("submit", (e) => {
      if (!epcInput.value) { e.preventDefault(); msg.innerHTML = "<b>Select a tag first</b> (tap “Use this tag”)."; }
    });
    if (box.dataset.preset) lock(box.dataset.preset);

    (function poll() {
      if (!locked) getJSON("/api/nearest").then((d) => {
        if (locked) return;
        if (d.status !== "running") { msg.textContent = "Reader is " + d.status + "…"; return; }
        if (d.nearest) {
          candidate = d.nearest.epc;
          box.className = "scanbox found";
          msg.innerHTML = "Found a tag" + (d.others ? ` <small>(+${d.others} other unregistered tag${d.others > 1 ? "s" : ""} in range: move them away or pick the strongest)</small>` : "");
          tagEl.textContent = d.nearest.epc;
          meta.textContent = `Signal ${d.nearest.rssi} dBm`;
          lockBtn.disabled = false;
        } else {
          candidate = null; box.className = "scanbox"; lockBtn.disabled = true; tagEl.textContent = "";
          msg.innerHTML = "Hold <b>one</b> tag close to the reader antenna…";
          meta.textContent = d.registered_in_range.length ? "Already registered nearby: " + d.registered_in_range.map((t) => t.name).join(", ") : "";
        }
      }).catch(() => { msg.textContent = "Can't reach the app server."; });
      setTimeout(poll, 500);
    })();
  }

  // ---- tracking screen ------------------------------------------------------------
  function initTrack(kitId, addUrl) {
    let tab = "check";
    $$(".tab").forEach((b) => b.addEventListener("click", () => {
      tab = b.dataset.tab;
      $$(".tab").forEach((x) => x.classList.toggle("on", x === b));
      $("#tab-check").hidden = tab !== "check";
      $("#tab-signal").hidden = tab !== "signal";
    }));
    const pct = (rssi) => rssi == null ? 0 : Math.max(0, Math.min(100, (rssi + 90) / 60 * 100)); // -90..-30 dBm

    function draw(canvas, hist, thr) {
      const dpr = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      const c = canvas.getContext("2d"); c.scale(dpr, dpr); c.clearRect(0, 0, w, h);
      const span = 30, lo = -95, hi = -25; // last 30 s, dBm range
      const x = (t) => w + (t / span) * w, y = (r) => h - ((r - lo) / (hi - lo)) * h;
      c.strokeStyle = "#f5b041"; c.setLineDash([4, 4]); c.lineWidth = 1;
      c.beginPath(); c.moveTo(0, y(thr)); c.lineTo(w, y(thr)); c.stroke(); c.setLineDash([]);
      const pts = hist.filter((p) => p[0] >= -span);
      c.fillStyle = "#3d9cff";
      pts.forEach((p) => { c.fillRect(x(p[0]) - 1.5, y(p[1]) - 1.5, 3, 3); });
    }

    function render(d) {
      const items = d.items, sum = $("#summary");
      const missing = items.filter((i) => i.state === "missing"), weak = items.filter((i) => i.state === "weak");
      if (d.status !== "running") { sum.className = "summary has-missing"; sum.textContent = "Reader " + d.status + (d.error ? ": " + d.error : ""); }
      else if (!items.length) { sum.className = "summary"; sum.textContent = "This bag has no items yet."; }
      else if (missing.length) { sum.className = "summary has-missing"; sum.textContent = `${missing.length} missing: ` + missing.map((i) => i.name).join(", "); }
      else if (weak.length) { sum.className = "summary has-weak"; sum.textContent = `All detected, ${weak.length} weak: ` + weak.map((i) => i.name).join(", "); }
      else { sum.className = "summary all-ok"; sum.textContent = `✓ All ${items.length} items present`; }

      if (tab === "check") {
        $("#checklist").innerHTML = items.map((i) => `
          <div class="card ${i.state}">
            <div class="nm">${esc(i.name)}</div>
            <div class="bar"><i style="width:${pct(i.rssi)}%"></i></div>
            <div class="meta"><span class="badge ${i.state}">${i.state}</span>
              <span>${i.rssi != null ? i.rssi + " dBm" : "—"}${i.age != null && i.age > 1 ? " · " + Math.round(i.age) + "s ago" : ""}</span></div>
          </div>`).join("");
      } else {
        $("#thr").textContent = d.min_rssi;
        const box = $("#signal");
        if (box.dataset.keys !== items.map((i) => i.epc).join()) {
          box.dataset.keys = items.map((i) => i.epc).join();
          box.innerHTML = items.map((i) => `<div class="sig" data-epc="${esc(i.epc)}"><div class="nm">${esc(i.name)}</div><canvas></canvas><div class="num"></div></div>`).join("");
        }
        items.forEach((i) => {
          const row = $(`.sig[data-epc="${CSS.escape(i.epc)}"]`, box);
          draw($("canvas", row), i.history, d.min_rssi);
          $(".num", row).innerHTML = `<b>${i.rssi != null ? i.rssi + " dBm" : "—"}</b>${i.reads_per_s.toFixed(1)} reads/s`;
        });
        $("#others").innerHTML = d.other.length ? d.other.map((t) => `
          <div class="row-item"><span class="list-main mono">${t.name ? esc(t.name) + " <small>(other bag)</small>" : "…" + esc(t.epc.slice(-12))}</span>
            <span class="list-sub">${t.rssi ?? "—"} dBm</span>
            ${t.name ? "" : `<a class="btn btn-small" href="${addUrl}?epc=${encodeURIComponent(t.epc)}&kit=${kitId}">Register</a>`}</div>`).join("")
          : '<p class="hint">None.</p>';
      }
    }
    (function poll() {
      getJSON("/api/track?kit=" + kitId).then(render).catch(() => { $("#summary").textContent = "Can't reach the app server."; })
        .finally(() => setTimeout(poll, 500));
    })();
  }

  window.TagTrack = { initScan, initTrack, initQuickNames };
})();
