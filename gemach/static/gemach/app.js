/* גמ"ח חליפות לשמחות — חיפוש לקוח, חלונות צפים, והזמנה חדשה בשלבים */
(function () {
  const G = window.GEMACH;
  const $ = (id) => document.getElementById(id);
  const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmtP = (p) => String(p).replace(/^(\d{3})(\d{3})(\d{4})$/, "$1-$2-$3");
  const DAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
  const pd = (s) => new Date(s + "T12:00");
  const HD = window.HebDate;
  const dm = (s) => (HD ? HD.short(s) : s);
  const dn = (s) => "יום " + DAYS[pd(s).getDay()] + ",";
  const swatch = (n) => (n.includes("שחור") ? "#1b1b1b" : n.includes("שמנת") ? "#EFE6D2" : "#c9c4b8");

  // ---------- dialogs ----------
  document.addEventListener("click", (e) => {
    const o = e.target.closest("[data-open]");
    if (o) { const d = $(o.dataset.open); if (d) { d.showModal(); d.querySelector("select,input")?.focus(); } }
    const c = e.target.closest("[data-close]");
    if (c) c.closest("dialog").close();
  });
  document.querySelectorAll("dialog").forEach((d) => d.addEventListener("click", (e) => { if (e.target === d) d.close(); }));

  // ---------- tabs (dashboard) ----------
  document.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => {
    document.querySelectorAll("[data-tab]").forEach((x) => x.setAttribute("aria-selected", x === b));
    document.querySelectorAll("[data-pane]").forEach((p) => (p.hidden = p.dataset.pane !== b.dataset.tab));
  }));

  // ---------- global search ----------
  const gq = $("gq"), gres = $("gres");
  let seq = 0;
  async function search() {
    const q = gq.value.trim();
    if (!q) { gres.hidden = true; return; }
    const my = ++seq;
    let data;
    try { data = await (await fetch(G.search + "?q=" + encodeURIComponent(q))).json(); } catch (e) { return; }
    if (my !== seq) return;
    const digits = q.replace(/\D/g, "");
    gres.innerHTML = data.customers.map((c) => `<div class="gr"><div><div class="n">${esc(c.name)}${c.late ? ' <span class="chip bad">באיחור</span>' : ""}</div>
      <div class="s"><bdi dir="ltr">${fmtP(c.phone)}</bdi> · ${c.orders} הזמנות${c.next ? " · הבאה " + c.next : ""}</div></div>
      <div class="acts"><a class="mini" href="${G.customer}${c.id}/">פתיחה</a><button type="button" class="mini solid" data-new='${JSON.stringify({ id: c.id, name: c.name, phone: c.phone }).replace(/'/g, "&#39;")}'>הזמנה</button></div></div>`).join("")
      + (data.customers.length ? "" : `<div class="gempty">לא נמצא לקוח<button type="button" class="mini solid" data-newq="1">הזמנה ללקוח חדש</button></div>`);
    gres.hidden = false;
    gres.querySelectorAll("[data-new]").forEach((b) => (b.onclick = () => { gres.hidden = true; const c = JSON.parse(b.dataset.new); wizard({ cust: c, phone: c.phone }); }));
    gres.querySelectorAll("[data-newq]").forEach((b) => (b.onclick = () => { gres.hidden = true; wizard(digits.length >= 9 ? { phone: digits } : { name: q }); }));
  }
  if (gq) {
    gq.addEventListener("input", () => { clearTimeout(gq._t); gq._t = setTimeout(search, 200); });
    gq.addEventListener("focus", search);
    document.addEventListener("click", (e) => { if (!e.target.closest("#gs")) gres.hidden = true; });
    document.addEventListener("keydown", (e) => {
      if (e.key === "/" && !e.target.matches("input,select,textarea")) { e.preventDefault(); gq.focus(); }
      if (e.key === "Escape") gres.hidden = true;
    });
  }

  // ---------- new order wizard ----------
  const wz = $("wz"), wb = $("wb"), werr = $("werr");
  if (!wz) return;
  const STEPS = ["לקוח", "תאריך", "ז׳קטים", "סיכום"];
  const W = {};
  window.wizard = wizard;
  async function wizard(init = {}) {
    Object.assign(W, { step: init.cust ? 1 : 0, cust: init.cust || null, matches: [], phone: init.phone || "", name: init.name || "",
      email: "", date: init.date || "", avail: null, lines: [], fitting: "", note: "" });
    if (W.step === 1 && W.date) W.step = 2;
    wz.showModal();
    if (W.date) await loadAvail();
    draw();
  }
  $("newo").onclick = () => wizard();
  document.querySelectorAll("[data-wizard-date]").forEach((b) => (b.onclick = () => wizard({ date: b.dataset.wizardDate })));

  async function loadAvail() {
    W.avail = null;
    try { W.avail = await (await fetch(G.avail + "?date=" + W.date)).json(); } catch (e) { W.avail = { models: [] }; }
  }
  async function lookup() {
    const d = W.phone.replace(/\D/g, "");
    if (d.length < 9) { W.matches = []; return; }
    try { W.matches = (await (await fetch(G.lookup + "?phone=" + d)).json()).customers; } catch (e) { W.matches = []; }
  }
  function free(mid, size) {
    const m = W.avail?.models.find((x) => x.id === mid); const s = m?.sizes.find((x) => x.size === size);
    return (s ? s.free : 0) - W.lines.filter((l) => l.m === mid && l.s === size).length;
  }
  async function draw() {
    werr.textContent = "";
    $("wsteps").innerHTML = STEPS.map((t, i) => `<span class="step ${i < W.step ? "ok" : i === W.step ? "on" : ""}"><i>${i < W.step ? "✓" : i + 1}</i>${t}</span>`).join("");
    $("wback").hidden = W.step === 0;
    $("wnext").textContent = W.step === 3 ? "שמירת ההזמנה" : "המשך";
    if (W.step === 0) {
      wb.innerHTML = `<label>טלפון<input id="wp" inputmode="tel" value="${esc(W.phone)}" autocomplete="off"></label><div id="wsug"></div>
        <div id="wnew" class="grid" style="gap:12px"><label>שם<input id="wn" value="${esc(W.name)}" autocomplete="off"></label>
        <label>מייל (לא חובה)<input id="we" type="email" value="${esc(W.email)}" autocomplete="off"></label></div>`;
      const wp = $("wp"), sug = $("wsug");
      const paint = () => {
        sug.innerHTML = W.matches.length ? `<div class="pick">${W.matches.map((c) => `<button type="button" data-c="${c.id}" aria-pressed="${W.cust && W.cust.id === c.id}"><span>${esc(c.name)}${c.notes ? ' <small>· ' + esc(c.notes) + "</small>" : ""}</span><small>${c.orders} הזמנות</small></button>`).join("")}
          <button type="button" data-c="0" aria-pressed="${!W.cust}"><span>לקוח אחר עם אותו טלפון</span><small>חדש</small></button></div>` : "";
        sug.querySelectorAll("[data-c]").forEach((b) => (b.onclick = () => { const c = W.matches.find((x) => x.id === +b.dataset.c); W.cust = c || null; if (!c) W.name = ""; paint(); }));
        $("wnew").hidden = !!W.cust;
      };
      wp.oninput = async () => { W.phone = wp.value; W.cust = null; await lookup(); paint(); };
      $("wn").oninput = (e) => (W.name = e.target.value);
      $("we").oninput = (e) => (W.email = e.target.value);
      await lookup(); paint(); wp.focus();
    }
    if (W.step === 1) {
      wb.innerHTML = `<div class="sumbox"><div class="r"><span>לקוח</span><b>${esc(W.cust ? W.cust.name : W.name)}</b></div></div>
        <label>תאריך השמחה<input type="date" id="wd" value="${W.date}"></label>
        <div class="dates">${W.date ? `<span>איסוף: ${dn(W.avail.pickup)} ${dm(W.avail.pickup)}</span><span>החזרה: ${dn(W.avail.return)} ${dm(W.avail.return)}</span>` : ""}</div>`;
      const wd = $("wd"); wd.focus();
      wd.onchange = async () => { W.date = wd.value; W.lines = []; if (W.date) await loadAvail(); draw(); };
    }
    if (W.step === 2) {
      const ms = W.avail?.models || [];
      wb.innerHTML = (ms.length ? `<div class="hint">לחיצה על מידה מוסיפה ילד · המספר = כמה פנויים לשמחה ב־${HD ? HD.short(W.date) : W.date}</div>
        <div class="sizes">${ms.map((m) => `<div class="srow"><span class="m"><i class="sw" style="background:${swatch(m.name)}"></i>${esc(m.name)}</span><div class="tiles">${m.sizes.map((s) => {
          const left = free(m.id, s.size);
          return `<button type="button" class="tile" ${left <= 0 ? "disabled" : ""} data-m="${m.id}" data-s="${esc(s.size)}"><b>${esc(s.size)}</b><small>${left > 0 ? left + " פנויים" : "אין"}</small></button>`;
        }).join("")}</div></div>`).join("")}</div>` : `<p class="empty">אין ז׳קטים במלאי. קודם מוסיפים ז׳קטים במסך ״ז׳קטים״.</p>`)
        + `<div class="chosen">${W.lines.map((l, i) => { const m = ms.find((x) => x.id === l.m);
          return `<div class="crow"><span><i class="sw" style="background:${swatch(m.name)}"></i>${esc(m.name)} · מידה ${esc(l.s)}</span><input placeholder="שם הילד (לא חובה)" data-k="${i}" value="${esc(l.k)}"><button type="button" class="rm" data-rm="${i}" aria-label="הסרה">×</button></div>`; }).join("")}</div>`;
      wb.querySelectorAll(".tile:not(:disabled)").forEach((b) => (b.onclick = () => { W.lines.push({ m: +b.dataset.m, s: b.dataset.s, k: "" }); draw(); }));
      wb.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = () => { W.lines.splice(+b.dataset.rm, 1); draw(); }));
      wb.querySelectorAll("[data-k]").forEach((i) => (i.oninput = () => (W.lines[+i.dataset.k].k = i.value)));
    }
    if (W.step === 3) {
      const ms = W.avail.models;
      wb.innerHTML = `<div class="sumbox">
        <div class="r"><span>לקוח</span><b>${esc(W.cust ? W.cust.name : W.name)} · <bdi dir="ltr">${fmtP(W.phone.replace(/\D/g, ""))}</bdi></b></div>
        <div class="r"><span>שמחה</span><b>${dn(W.date)} ${dm(W.date)}</b></div>
        <div class="r"><span>איסוף</span><span>${dn(W.avail.pickup)} ${dm(W.avail.pickup)}</span></div>
        <div class="r"><span>החזרה</span><span>${dn(W.avail.return)} ${dm(W.avail.return)}</span></div>
        ${W.lines.map((l) => `<div class="r"><span>${esc(ms.find((x) => x.id === l.m).name)} ${esc(l.s)}</span><span>${esc(l.k) || "—"}</span></div>`).join("")}
        <div class="r" style="border-top:1px solid var(--line);padding-top:6px"><span>לתשלום באיסוף</span><span class="tot">${30 * W.lines.length} ₪</span></div></div>
        <label>מדידה (מה סוכם)<input id="wf" value="${esc(W.fitting)}" placeholder="למשל: יום ב׳ בערב"></label>
        <label>הערה<input id="wo" value="${esc(W.note)}"></label>
        <label class="check"><input type="checkbox" id="wnm"> לא לשלוח מייל ללקוח</label>`;
      $("wf").oninput = (e) => (W.fitting = e.target.value);
      $("wo").oninput = (e) => (W.note = e.target.value);
    }
  }
  function submit() {
    const f = $("wform");
    f.querySelectorAll("input:not([name=csrfmiddlewaretoken])").forEach((i) => i.remove());
    const add = (n, v) => { const i = document.createElement("input"); i.type = "hidden"; i.name = n; i.value = v; f.appendChild(i); };
    add("phone", W.phone); add("name", W.cust ? W.cust.name : W.name); add("email", W.email);
    add("customer_id", W.cust ? W.cust.id : ""); add("event_date", W.date);
    add("fitting_note", W.fitting); add("note", W.note);
    if ($("wnm")?.checked) add("no_email", "1");
    W.lines.forEach((l) => { add("line_id", ""); add("line_model", l.m); add("line_size", l.s); add("line_child", l.k); });
    f.submit();
  }
  async function next() {
    if (W.step === 0) {
      if (W.phone.replace(/\D/g, "").length < 9) { werr.textContent = "מספר טלפון לא תקין"; return; }
      if (!W.cust && !W.name.trim()) { werr.textContent = "חסר שם"; return; }
    }
    if (W.step === 1 && !W.date) { werr.textContent = "בחרי תאריך"; return; }
    if (W.step === 1 && !W.avail) await loadAvail();
    if (W.step === 2 && !W.lines.length) { werr.textContent = "בחרי לפחות מידה אחת"; return; }
    if (W.step === 3) { submit(); return; }
    W.step++; draw();
  }
  $("wnext").onclick = next;
  $("wback").onclick = () => { W.step--; draw(); };
  wz.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.tagName === "INPUT" && !e.target.dataset.k && e.target.type !== "checkbox") { e.preventDefault(); next(); } });
})();
