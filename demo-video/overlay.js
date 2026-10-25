// Injected into every page: a visible cursor with click ripples, caption pills, full-screen title cards
// and a spotlight for the chat assistant.
(() => {
  if (window.__demo) return;
  const css = `
  #__cur{position:fixed;left:0;top:0;width:30px;height:30px;z-index:2147483639;pointer-events:none;
    transform:translate(-4px,-3px);transition:transform .08s;filter:drop-shadow(0 3px 6px rgba(0,0,0,.35))}
  #__cur.down{transform:translate(-4px,-3px) scale(.86)}
  .__ripple{position:fixed;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;z-index:2147483638;pointer-events:none;
    border:3px solid rgba(249,115,22,.95);animation:__rip .55s ease-out forwards}
  @keyframes __rip{to{transform:scale(4.2);opacity:0}}

  #__cap{position:fixed;left:50%;bottom:40px;transform:translate(-50%,24px);opacity:0;z-index:2147483637;pointer-events:none;
    font:700 30px/1.2 "Plus Jakarta Sans","Inter",system-ui,sans-serif;color:#0f172a;letter-spacing:-.01em;
    padding:18px 34px 18px 24px;border-radius:999px;display:flex;gap:16px;align-items:center;white-space:nowrap;
    background:#fff;border:1px solid #d5e6e3;
    box-shadow:0 2px 6px rgba(15,23,42,.06),0 22px 55px rgba(15,118,110,.22);
    transition:opacity .4s ease, transform .4s cubic-bezier(.2,.8,.2,1)}
  #__cap.on{opacity:1;transform:translate(-50%,0)}
  #__cap i{width:14px;height:14px;border-radius:50%;background:#14b8a6;box-shadow:0 0 0 6px rgba(20,184,166,.18);flex:none}

  #__card{position:fixed;inset:0;z-index:2147483640;display:flex;align-items:center;justify-content:center;flex-direction:column;
    background:radial-gradient(1100px 650px at 15% 10%,#ccfbf1 0%,transparent 60%),radial-gradient(1000px 650px at 90% 95%,#e0e7ff 0%,transparent 60%),#f7fbfa;
    color:#0f172a;font-family:"Plus Jakarta Sans","Inter",system-ui,sans-serif;opacity:0;pointer-events:none;transition:opacity .6s ease}
  #__card.on{opacity:1}
  #__card .k{font:700 22px/1 inherit;letter-spacing:.32em;text-transform:uppercase;color:#0d9488;margin-bottom:28px;
    opacity:0;transform:translateY(16px);transition:all .6s .1s cubic-bezier(.2,.8,.2,1)}
  #__card h1{font-size:96px;line-height:1.08;font-weight:800;letter-spacing:-.035em;margin:0;text-align:center;max-width:1500px}
  #__card h1 .w{display:inline-block;opacity:0;transform:translateY(46px) scale(.96);filter:blur(10px);
    transition:opacity .55s ease, transform .7s cubic-bezier(.2,.9,.25,1.15), filter .55s ease}
  #__card h1 .w.a{background:linear-gradient(90deg,#0d9488,#6366f1);-webkit-background-clip:text;color:transparent}
  #__card p{font-size:32px;color:#475569;margin:30px 0 0;text-align:center;max-width:1300px;
    opacity:0;transform:translateY(24px);transition:all .8s cubic-bezier(.2,.8,.2,1)}
  #__card .logo{display:flex;align-items:center;gap:26px;font-size:120px;font-weight:800;letter-spacing:-.035em;margin-bottom:30px}
  #__card .logo .m{width:140px;height:140px;border-radius:38px;background:linear-gradient(135deg,#14b8a6,#0f766e);display:grid;place-items:center;
    box-shadow:0 24px 60px rgba(20,184,166,.35);opacity:0;transform:scale(.3) rotate(-25deg);
    transition:opacity .4s ease, transform .8s cubic-bezier(.2,1.4,.3,1)}
  #__card .logo .l{display:inline-block;opacity:0;transform:translateY(-70px) rotate(-8deg);filter:blur(8px);
    transition:opacity .35s ease, transform .65s cubic-bezier(.2,1.5,.35,1), filter .4s ease}
  #__card .logo .l.b{color:#0d9488}
  #__card .chips{display:flex;gap:16px;margin-top:46px;flex-wrap:wrap;justify-content:center;max-width:1400px}
  #__card .chips span{font-size:24px;padding:12px 22px;border-radius:999px;background:#fff;border:1px solid #d5e6e3;color:#0f766e;font-weight:600;box-shadow:0 8px 24px rgba(15,118,110,.1);
    opacity:0;transform:translateY(20px);transition:all .5s cubic-bezier(.2,.8,.2,1)}
  #__card.go .k,#__card.go p,#__card.go .chips span,#__card.go h1 .w,#__card.go .logo .l,#__card.go .logo .m{opacity:1;transform:none;filter:none}
  #__card.instant,#__card.instant *{transition:none!important}

  #__dim{position:fixed;inset:0;z-index:2147483500;background:rgba(240,249,247,.6);backdrop-filter:blur(4px);opacity:0;
    pointer-events:none;transition:opacity .6s ease}
  html.__chatfocus #__dim{opacity:1}
  .chat-widget{transition:transform .7s cubic-bezier(.2,.8,.2,1);transform-origin:100% 100%}
  html.__chatfocus .chat-widget{z-index:2147483600!important;transform:scale(1.45)}

  /* Booking codes are private: keep the QR, check-in code and private code unreadable on video. */
  .checkin-qr-image{filter:blur(14px)}
  .checkin-qr figcaption strong,.token-box .token,input[aria-label="Check-in code"]{filter:blur(9px)}
  `;
  const ss = (k, v) => { try { if (v === undefined) return sessionStorage.getItem(k); if (v === null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, v); } catch {} };

  // Delays are set inline so each word or letter arrives one after another.
  function cardHtml({ kicker = "", title = [], sub = "", logo = false, chips = [] }) {
    let d = 0.15;
    let html = "";
    if (logo) {
      html += `<div class="logo"><span class="m" style="transition-delay:${d}s"><svg viewBox="0 0 64 64" width="86" height="86"><path d="M27 14h10v13h13v10H37v13H27V37H14V27h13z" fill="#fff"/></svg></span><span>`;
      d += 0.35;
      for (const [i, ch] of [..."CareFlow"].entries()) {
        html += `<span class="l${i >= 4 ? " b" : ""}" style="transition-delay:${d.toFixed(2)}s">${ch}</span>`;
        d += 0.09;
      }
      html += "</span></div>";
      d += 0.25;
    }
    if (kicker) { html += `<div class="k" style="transition-delay:${d.toFixed(2)}s">${kicker}</div>`; d += 0.15; }
    if (title.length) {
      html += "<h1>";
      title.forEach((part, pi) => {
        for (const word of part.split(" ")) {
          html += `<span class="w${pi % 2 ? " a" : ""}" style="transition-delay:${d.toFixed(2)}s">${word}</span> `;
          d += 0.11;
        }
      });
      html += "</h1>";
      d += 0.1;
    }
    if (sub) { html += `<p style="transition-delay:${d.toFixed(2)}s">${sub}</p>`; d += 0.3; }
    if (chips.length) {
      html += `<div class="chips">${chips.map((c, i) => `<span style="transition-delay:${(d + i * 0.12).toFixed(2)}s">${c}</span>`).join("")}</div>`;
    }
    return html;
  }

  function mount() {
    if (document.getElementById("__cur")) return;
    const st = document.createElement("style"); st.textContent = css; document.documentElement.appendChild(st);
    const cur = document.createElement("div"); cur.id = "__cur";
    cur.innerHTML = '<svg viewBox="0 0 24 24" width="30" height="30"><path d="M3 2l7.5 19 2.6-7.9L21 10.5z" fill="#0f172a" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(cur);
    const dim = document.createElement("div"); dim.id = "__dim"; document.documentElement.appendChild(dim);
    const cap = document.createElement("div"); cap.id = "__cap"; document.documentElement.appendChild(cap);
    const card = document.createElement("div"); card.id = "__card"; document.documentElement.appendChild(card);
    const pos = JSON.parse(ss("__pos") || "[960,540]");
    cur.style.left = pos[0] + "px"; cur.style.top = pos[1] + "px";
    const c = ss("__cap"); if (c) { cap.innerHTML = "<i></i>" + c; cap.classList.add("on"); }
    const k = ss("__card"); if (k !== null && k !== undefined) { card.className = "instant on go"; card.innerHTML = k; }
    addEventListener("mousemove", (e) => { cur.style.left = e.clientX + "px"; cur.style.top = e.clientY + "px"; ss("__pos", JSON.stringify([e.clientX, e.clientY])); }, true);
    addEventListener("mousedown", (e) => {
      cur.classList.add("down");
      const r = document.createElement("div"); r.className = "__ripple"; r.style.left = e.clientX + "px"; r.style.top = e.clientY + "px";
      document.documentElement.appendChild(r); setTimeout(() => r.remove(), 700);
    }, true);
    addEventListener("mouseup", () => cur.classList.remove("down"), true);
  }

  window.__demo = {
    caption(text) {
      const cap = document.getElementById("__cap");
      if (!text) { cap.classList.remove("on"); ss("__cap", null); return; }
      ss("__cap", text);
      if (cap.classList.contains("on")) {
        cap.classList.remove("on");
        setTimeout(() => { cap.innerHTML = "<i></i>" + text; cap.classList.add("on"); }, 380);
      } else { cap.innerHTML = "<i></i>" + text; requestAnimationFrame(() => cap.classList.add("on")); }
    },
    card(opts) {
      window.__demo.caption(null);
      const card = document.getElementById("__card");
      const html = cardHtml(opts);
      const wasOn = card.classList.contains("on");
      card.className = wasOn ? "on" : ""; card.innerHTML = html; ss("__card", html);
      card.offsetHeight;
      requestAnimationFrame(() => requestAnimationFrame(() => card.classList.add("on", "go")));
    },
    hideCard() {
      const card = document.getElementById("__card");
      card.className = "on go"; ss("__card", null);
      requestAnimationFrame(() => card.classList.remove("on"));
    },
    chatFocus(on) { document.documentElement.classList.toggle("__chatfocus", on); },
  };
  if (document.documentElement) mount(); else document.addEventListener("DOMContentLoaded", mount);
  document.addEventListener("DOMContentLoaded", mount);
})();
