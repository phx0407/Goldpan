/* Goldpan cookie consent - gates Google Analytics until the visitor accepts. */
(function () {
  var GA_ID = "G-NGENFQKBT1";
  var KEY = "goldpan_cookie_consent";
  function loadGA() {
    if (window.__gpGA) return;
    window.__gpGA = true;
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_ID;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { dataLayer.push(arguments); };
    gtag("js", new Date());
    gtag("config", GA_ID);
  }
  var choice = null;
  try { choice = localStorage.getItem(KEY); } catch (e) {}
  if (choice === "accepted") { loadGA(); return; }
  if (choice === "declined") { return; }
  function save(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  function build() {
    var bar = document.createElement("div");
    bar.setAttribute("role", "dialog");
    bar.setAttribute("aria-label", "Cookie consent");
    bar.style.cssText = "position:fixed;left:16px;right:16px;bottom:16px;z-index:9999;max-width:560px;margin:0 auto;background:#141414;border:1px solid #2A2A2A;border-radius:14px;padding:18px 20px;box-shadow:0 14px 40px rgba(0,0,0,0.5);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;opacity:0;transform:translateY(10px);transition:opacity .35s ease,transform .35s ease;";
    bar.innerHTML =
      '<p style="margin:0 0 14px;font-size:13.5px;line-height:1.6;color:#C9C4BA;">' +
      'We use cookies for Google Analytics to understand site traffic. ' +
      'See our <a href="/privacy" style="color:#C9A84C;text-decoration:none;border-bottom:1px solid rgba(201,168,76,0.4);">Privacy Policy</a>.' +
      '</p>' +
      '<div style="display:flex;gap:10px;justify-content:flex-end;">' +
      '<button id="gp-decline" style="cursor:pointer;font-size:12.5px;letter-spacing:0.04em;padding:9px 16px;border-radius:8px;border:1px solid #333;background:transparent;color:#9A9488;">Decline</button>' +
      '<button id="gp-accept" style="cursor:pointer;font-size:12.5px;letter-spacing:0.04em;padding:9px 18px;border-radius:8px;border:none;background:#C9A84C;color:#141414;font-weight:600;">Accept</button>' +
      '</div>';
    document.body.appendChild(bar);
    requestAnimationFrame(function () { bar.style.opacity = "1"; bar.style.transform = "translateY(0)"; });
    function close() { bar.style.opacity = "0"; bar.style.transform = "translateY(10px)"; setTimeout(function(){ bar.remove(); }, 350); }
    document.getElementById("gp-accept").onclick = function () { save("accepted"); loadGA(); close(); };
    document.getElementById("gp-decline").onclick = function () { save("declined"); close(); };
  }
  if (document.body) build();
  else document.addEventListener("DOMContentLoaded", build);
})();
