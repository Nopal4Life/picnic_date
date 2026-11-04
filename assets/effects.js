// Runs inside the components.html iframe, so reach into the parent Streamlit page.
(function () {
  const win = window.parent;
  const doc = win.document;
  const reduceMotion = win.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const HEART_SVG =
    '<svg viewBox="0 0 24 24"><path d="M12 21s-7.5-4.6-10-9.5C0.4 8 2.3 4 6 4c2.2 0 3.7 1.2 6 3.4C14.3 5.2 15.8 4 18 4c3.7 0 5.6 4 4 7.5C19.5 16.4 12 21 12 21z"/></svg>';
  const SPARKLE_SVG =
    '<svg viewBox="0 0 24 24"><path d="M12 0C13 7 17 11 24 12C17 13 13 17 12 24C11 17 7 13 0 12C7 11 11 7 12 0Z"/></svg>';
  const CLOUD_SVG =
    '<svg viewBox="0 0 64 32"><g><circle cx="18" cy="20" r="10"/><circle cx="32" cy="14" r="13"/><circle cx="46" cy="20" r="10"/><rect x="8" y="20" width="48" height="10"/></g></svg>';

  const PINKS = ["#ff8fc0", "#e8559a", "#ffb3d4", "#ff6fa8"];
  const GLINTS = ["#ffffff", "#ffe066", "#ffb3d4", "#a9ddf2"];

  const rand = (min, max) => min + Math.random() * (max - min);
  const pick = (list) => list[Math.floor(Math.random() * list.length)];

  // A rerun can re-mount this iframe: tear down the previous run's listeners and timers first.
  if (win.__kittyFxCleanup) win.__kittyFxCleanup();
  const cleanups = [];
  win.__kittyFxCleanup = () => cleanups.forEach((fn) => fn());

  function listen(target, type, fn, opts) {
    target.addEventListener(type, fn, opts);
    cleanups.push(() => target.removeEventListener(type, fn, opts));
  }

  function every(ms, fn) {
    const id = win.setInterval(fn, ms);
    cleanups.push(() => win.clearInterval(id));
  }

  function span(cls, html) {
    const el = doc.createElement("span");
    el.className = cls;
    if (html) el.innerHTML = html;
    return el;
  }

  function layer(id, host) {
    let el = doc.getElementById(id);
    if (!el && host) {
      el = doc.createElement("div");
      el.id = id;
      host.prepend(el);
    }
    return el;
  }

  // ---------- jumping kitty: floating hearts (the sprite itself is rendered by app.py) ----------
  function decorate(box) {
    const kitty = box.querySelector(".kitty");
    if (!kitty || kitty.querySelector(".float-heart")) return;

    for (let i = 0; i < 6; i++) {
      const h = span("float-heart", HEART_SVG);
      h.style.setProperty("--c", i % 2 ? "#ffb3d4" : "#ff6fa8");
      h.style.setProperty("--x", 15 + Math.random() * 70 + "%");
      h.style.setProperty("--size", 0.7 + Math.random() * 0.5 + "rem");
      h.style.setProperty("--delay", i * 0.4 + "s");
      h.style.setProperty("--drift", Math.random() * 60 - 30 + "px");
      kitty.appendChild(h);
    }
  }

  function scan() {
    doc.querySelectorAll(".st-key-jump_gif").forEach(decorate);
    ensureAmbient();
  }

  // The yes screen renders after a rerun, so watch for it.
  const observer = new MutationObserver(scan);
  observer.observe(doc.body, { childList: true, subtree: true });
  cleanups.push(() => observer.disconnect());

  // ---------- drifting hearts, clouds and sparkles (CSS keyframes animate, JS spawns) ----------
  function ensureAmbient() {
    const host = doc.querySelector(".stApp");
    return host ? layer("kitty-ambient", host) : null;
  }

  function drift(kind, cap, setup) {
    const amb = ensureAmbient();
    if (!amb || doc.hidden || amb.querySelectorAll(".amb-" + kind).length >= cap) return;
    const html = { heart: HEART_SVG, sparkle: SPARKLE_SVG, cloud: CLOUD_SVG }[kind];
    const node = span("amb amb-" + kind, html);
    setup(node.style);
    node.addEventListener("animationend", () => node.remove());
    amb.appendChild(node);
  }

  function spawnHeart() {
    drift("heart", 14, (s) => {
      s.setProperty("--x", rand(2, 96) + "vw");
      s.setProperty("--s", rand(14, 30) + "px");
      s.setProperty("--dur", rand(9, 16) + "s");
      s.setProperty("--drift", rand(-50, 50) + "px");
      s.setProperty("--c", pick(PINKS));
    });
  }

  function spawnSparkle() {
    drift("sparkle", 18, (s) => {
      s.setProperty("--x", rand(2, 96) + "vw");
      s.setProperty("--y", rand(4, 92) + "vh");
      s.setProperty("--s", rand(8, 18) + "px");
      s.setProperty("--dur", rand(2.5, 4.5) + "s");
      s.setProperty("--c", pick(GLINTS));
    });
  }

  function spawnCloud(midway) {
    drift("cloud", 3, (s) => {
      const dur = rand(45, 80);
      s.setProperty("--y", rand(3, 38) + "vh");
      s.setProperty("--s", rand(70, 140) + "px");
      s.setProperty("--dur", dur + "s");
      // negative delay starts it partway across so the sky isn't empty on load
      s.setProperty("--delay", midway ? -rand(0, dur * 0.8) + "s" : "0s");
    });
  }

  if (!reduceMotion) {
    spawnCloud(true);
    spawnCloud(true);
    every(1200, spawnHeart);
    every(700, spawnSparkle);
    every(9000, () => spawnCloud(false));
  }

  // ---------- finger sparkle trail + tap bursts ----------
  function particle(x, y, html, size, color, dx, dy, spin, ms) {
    const fx = layer("kitty-fx", doc.body);
    const p = span("fx-particle", html);
    p.style.cssText = `left:${x}px;top:${y}px;width:${size}px;height:${size}px;fill:${color}`;
    fx.appendChild(p);
    const anim = p.animate(
      [
        { transform: "translate(-50%, -50%) scale(0.3) rotate(0deg)", opacity: 1 },
        {
          transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(1) rotate(${spin}deg)`,
          opacity: 0,
        },
      ],
      { duration: ms, easing: "ease-out" }
    );
    anim.onfinish = () => p.remove();
  }

  let lastX = 0;
  let lastY = 0;
  let lastT = 0;
  listen(doc, "pointermove", (e) => {
    if (reduceMotion) return;
    const now = win.performance.now();
    if (now - lastT < 45 || Math.hypot(e.clientX - lastX, e.clientY - lastY) < 14) return;
    lastT = now;
    lastX = e.clientX;
    lastY = e.clientY;
    particle(
      e.clientX, e.clientY,
      Math.random() < 0.3 ? HEART_SVG : SPARKLE_SVG,
      rand(8, 14), pick(GLINTS.concat(PINKS)),
      rand(-14, 14), rand(14, 34), rand(-120, 120), rand(600, 850)
    );
  });

  listen(doc, "pointerdown", (e) => {
    if (reduceMotion) return;
    const n = 10;
    for (let i = 0; i < n; i++) {
      const angle = (i / n) * Math.PI * 2 + rand(-0.2, 0.2);
      const r = rand(40, 85);
      particle(
        e.clientX, e.clientY,
        i % 2 ? HEART_SVG : SPARKLE_SVG,
        rand(10, 18), i % 2 ? pick(PINKS) : pick(GLINTS),
        Math.cos(angle) * r, Math.sin(angle) * r, rand(-90, 90), rand(550, 800)
      );
    }
  });

  // ---------- "No" flees the finger ----------
  // The press still counts as a No (so Yes keeps growing), then the button hops away.
  let letNext = false;
  let swallowNative = false;
  let swallowTimer = 0;

  function flee(e, btn) {
    const box = btn.closest(".st-key-no_btn");
    const card = doc.querySelector(".block-container");
    if (!box || !card) return;

    const c = card.getBoundingClientRect();
    const r = box.getBoundingClientRect();
    const curX = parseFloat(box.dataset.fx || "0");
    const curY = parseFloat(box.dataset.fy || "0");
    const homeX = r.left + r.width / 2 - curX;
    const homeY = r.top + r.height / 2 - curY;

    const minX = c.left + r.width / 2 + 12;
    const maxX = c.right - r.width / 2 - 12;
    const minY = Math.max(c.top + r.height / 2 + 12, homeY - 80);
    const maxY = Math.min(c.bottom - r.height / 2 - 12, homeY + 90);

    // never land on top of the Yes button
    const yesEl = doc.querySelector(".st-key-yes_btn button");
    const yes = yesEl ? yesEl.getBoundingClientRect() : null;
    const hitsYes = (x, y) =>
      yes &&
      x + r.width / 2 + 16 > yes.left && x - r.width / 2 - 16 < yes.right &&
      y + r.height / 2 + 16 > yes.top && y - r.height / 2 - 16 < yes.bottom;

    // random spot at least 120px from the finger; else the far side of the card
    let tx = e.clientX < (minX + maxX) / 2 ? maxX : minX;
    let ty = homeY;
    for (let i = 0; i < 60; i++) {
      const x = rand(minX, Math.max(minX, maxX));
      const y = rand(minY, Math.max(minY, maxY));
      if (Math.hypot(x - e.clientX, y - e.clientY) >= 120 && !hitsYes(x, y)) {
        tx = x;
        ty = y;
        break;
      }
    }

    box.dataset.fx = tx - homeX;
    box.dataset.fy = ty - homeY;
    box.style.translate = `${tx - homeX}px ${ty - homeY}px`;
  }

  listen(doc, "pointerdown", (e) => {
    const btn = e.target.closest && e.target.closest(".st-key-no_btn button");
    if (!btn) return;
    flee(e, btn);
    letNext = true;
    btn.click(); // register the "No" before it escapes
    letNext = false;
    swallowNative = true; // ...and ignore the real click if it still lands
    win.clearTimeout(swallowTimer);
    swallowTimer = win.setTimeout(() => (swallowNative = false), 700);
  }, true);

  listen(doc, "click", (e) => {
    if (letNext || !swallowNative) return;
    if (e.target.closest && e.target.closest(".st-key-no_btn button")) {
      swallowNative = false;
      e.stopPropagation();
      e.preventDefault();
    }
  }, true);

  // ---------- confetti finale (python decides when: window.parent.kittyConfetti()) ----------
  const CONFETTI_COLORS = ["#ff8fc0", "#e8559a", "#a9ddf2", "#c4eb9a", "#ffffff", "#ffe066"];

  function kittyConfetti() {
    if (reduceMotion || !window.confetti) return;

    let canvas = doc.getElementById("kitty-confetti");
    if (!canvas) {
      canvas = doc.createElement("canvas");
      canvas.id = "kitty-confetti";
      doc.body.appendChild(canvas);
    }
    canvas.width = win.innerWidth;
    canvas.height = win.innerHeight;

    // draws onto the parent page's canvas (the library itself lives in this iframe)
    const fire = window.confetti.create(canvas, { resize: false, useWorker: false });
    const heart = window.confetti.shapeFromPath({
      path: "M167 72c19,-38 37,-56 75,-56 42,0 76,33 76,75 0,76 -76,151 -151,227 -76,-76 -151,-151 -151,-227 0,-42 33,-75 75,-75 38,0 57,18 76,56z",
    });
    const base = { colors: CONFETTI_COLORS, shapes: ["square", "circle", heart], scalar: 1.4 };

    fire({ ...base, particleCount: 120, spread: 90, startVelocity: 55, origin: { x: 0.5, y: 0.7 } });

    // two side cannons for a couple of seconds
    const end = Date.now() + 2000;
    (function cannons() {
      fire({ ...base, particleCount: 4, angle: 60, spread: 60, origin: { x: 0, y: 0.8 } });
      fire({ ...base, particleCount: 4, angle: 120, spread: 60, origin: { x: 1, y: 0.8 } });
      if (Date.now() < end) win.requestAnimationFrame(cannons);
    })();
  }
  win.kittyConfetti = kittyConfetti;

  scan();
})();
