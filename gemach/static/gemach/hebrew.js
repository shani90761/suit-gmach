/* תאריך עברי: עיצוב, בוחר תאריכים עברי, ותגיות data-hd. משתמש ב-Intl של הדפדפן (לוח עברי). */
(function () {
  const ONES = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"];
  const TENS = ["", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ"];
  const HUND = ["", "ק", "ר", "ש", "ת", "תק", "תר", "תש", "תת", "תתק"];
  function gematria(n) {
    n = n % 1000;
    let s = HUND[Math.floor(n / 100)];
    let r = n % 100;
    if (r === 15) s += "טו"; else if (r === 16) s += "טז"; else s += TENS[Math.floor(r / 10)] + ONES[r % 10];
    return s.length > 1 ? s.slice(0, -1) + "״" + s.slice(-1) : s + "׳";
  }
  const fmt = new Intl.DateTimeFormat("he-u-ca-hebrew-nu-latn", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  const DAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
  const toDate = (iso) => new Date(iso + "T00:00:00Z");
  const iso = (d) => d.toISOString().slice(0, 10);
  const addDays = (d, n) => new Date(d.getTime() + n * 864e5);
  function parts(d) {
    const p = {}; fmt.formatToParts(d).forEach((x) => (p[x.type] = x.value));
    return { day: +p.day, month: p.month, year: +p.year };
  }
  const H = {
    gematria, parts, iso, toDate, addDays, DAYS,
    day: (s) => gematria(parts(toDate(s)).day),
    short: (s) => { const p = parts(toDate(s)); return `${gematria(p.day)} ${p.month}`; },
    long: (s) => { const p = parts(toDate(s)); return `${gematria(p.day)} ${p.month} ${gematria(p.year)}`; },
    greg: (s) => { const d = toDate(s); return `${d.getUTCDate()}.${d.getUTCMonth() + 1}`; },
    weekday: (s) => "יום " + DAYS[toDate(s).getUTCDay()],
    monthTitle: (d) => { const p = parts(d); return `${p.month} ${gematria(p.year)}`; },
    /** כל ימי החודש העברי שבו נמצא התאריך */
    monthDays(d) {
      let s = d; while (parts(s).day !== 1) s = addDays(s, -1);
      const m = parts(s).month, out = [];
      for (let x = s; parts(x).month === m; x = addDays(x, 1)) out.push(x);
      return out;
    },
  };
  window.HebDate = H;

  // ---------- <span data-hd="YYYY-MM-DD" data-hd-fmt="short|long|day"> ----------
  function paint(root) {
    root.querySelectorAll("[data-hd]:not([data-hd-done])").forEach((el) => {
      const s = el.dataset.hd; if (!s) return;
      const f = el.dataset.hdFmt || "short";
      el.textContent = (f === "weekday" ? H.weekday(s) + ", " + H.short(s) : H[f](s));
      el.title = H.weekday(s) + ", " + H.long(s);
      el.dataset.hdDone = "1";
    });
  }

  // ---------- Hebrew date picker: replaces every <input type="date"> ----------
  function enhance(input) {
    if (input.dataset.hp) return; input.dataset.hp = "1";
    input.type = "hidden";
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "hp-btn";
    const label = () => { btn.innerHTML = input.value ? `<b>${H.weekday(input.value)}, ${H.long(input.value)}</b>` : '<span class="hp-ph">בחירת תאריך</span>'; };
    label();
    input.after(btn);
    let pop = null, cur = null;
    const close = () => { pop?.remove(); pop = null; document.removeEventListener("mousedown", outside); };
    const outside = (e) => { if (pop && !pop.contains(e.target) && e.target !== btn && !btn.contains(e.target)) close(); };
    function draw() {
      const days = H.monthDays(cur), today = iso(new Date(Date.now() - new Date().getTimezoneOffset() * 6e4));
      const lead = days[0].getUTCDay();
      pop.innerHTML = `<div class="hp-h"><button type="button" class="hp-nav" data-m="-1" aria-label="חודש קודם">›</button><b>${H.monthTitle(days[0])}</b><button type="button" class="hp-nav" data-m="1" aria-label="חודש הבא">‹</button></div>
        <div class="hp-g">${["א", "ב", "ג", "ד", "ה", "ו", "ש"].map((x) => `<span class="hp-w">${x}</span>`).join("")}${"<span></span>".repeat(lead)}${days.map((d) => {
          const s = iso(d);
          return `<button type="button" class="hp-d${s === input.value ? " on" : ""}${s === today ? " today" : ""}${d.getUTCDay() === 6 ? " sh" : ""}" data-v="${s}"><b>${H.gematria(H.parts(d).day)}</b></button>`;
        }).join("")}</div>
        <div class="hp-f"><button type="button" class="mini" data-today>היום</button></div>`;
      pop.querySelectorAll("[data-m]").forEach((b) => (b.onclick = () => { const ds = H.monthDays(cur); cur = +b.dataset.m > 0 ? addDays(ds[ds.length - 1], 1) : addDays(ds[0], -1); draw(); }));
      pop.querySelectorAll("[data-v]").forEach((b) => (b.onclick = () => pick(b.dataset.v)));
      pop.querySelector("[data-today]").onclick = () => pick(today);
    }
    function pick(v) {
      input.value = v; label(); close();
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      if (input.form && input.dataset.autosubmit !== undefined) input.form.requestSubmit();
    }
    btn.onclick = () => {
      if (pop) { close(); return; }
      cur = input.value ? toDate(input.value) : toDate(iso(new Date()));
      pop = document.createElement("div"); pop.className = "hp-pop";
      btn.parentElement.style.position ||= "relative";
      btn.after(pop); draw();
      setTimeout(() => document.addEventListener("mousedown", outside), 0);
    };
  }
  const scan = (root) => { root.querySelectorAll?.('input[type="date"]').forEach(enhance); paint(root); };
  document.addEventListener("DOMContentLoaded", () => scan(document));
  new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => n.nodeType === 1 && scan(n.parentElement || n))))
    .observe(document.documentElement, { childList: true, subtree: true });
})();
