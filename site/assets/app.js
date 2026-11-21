/* FashionGraph site behaviour. Progressive enhancement: every page works without this file. */
(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // mobile menu (same links, same order on every page)
  const btn = document.querySelector(".menu-btn");
  const nav = document.querySelector("nav");
  if (btn && nav) {
    const set = (open) => { nav.classList.toggle("open", open); btn.setAttribute("aria-expanded", String(open)); };
    btn.addEventListener("click", () => set(!nav.classList.contains("open")));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && nav.classList.contains("open")) { set(false); btn.focus(); } });
  }

  // charts draw when they scroll into view (a response to the reader scrolling, not decoration)
  const targets = document.querySelectorAll(".bar, .sbar, .schedule, .chart");
  if ("IntersectionObserver" in window && !reduce) {
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }), { threshold: 0.35 });
    targets.forEach((t) => io.observe(t));
  } else {
    targets.forEach((t) => t.classList.add("in"));
  }

  // hero graph: one staged sequence. One Wikidata node, then ghosts, then ten verified shows.
  const g = document.querySelector("svg.graph");
  if (!g) return;
  const shows = [...g.querySelectorAll(".node.show")];
  const edition = g.querySelector(".node.edition");
  const root = g.querySelector(".node.root");
  const edges = [...g.querySelectorAll(".edge")];
  const count = document.getElementById("hero-count");
  const detail = document.getElementById("node-detail");
  const replay = document.getElementById("replay");
  const idle = detail ? detail.textContent : "";
  let timers = [];

  const later = (fn, ms) => timers.push(setTimeout(fn, ms));
  const edge = (i) => edges.find((e) => e.dataset.i === String(i));
  const setCount = (n) => { if (count) count.textContent = `${n} of ${shows.length} shows verified from CNMI`; };

  function finalState() {
    timers.forEach(clearTimeout); timers = [];
    g.classList.remove("pre", "ghosts");
    [root, edition, ...shows].forEach((n) => n.classList.add("on"));
    edges.forEach((e) => e.classList.add("on"));
    setCount(shows.length);
  }

  function play() {
    timers.forEach(clearTimeout); timers = [];
    g.classList.add("pre"); g.classList.remove("ghosts");
    [edition, ...shows].forEach((n) => n.classList.remove("on"));
    edges.forEach((e) => e.classList.remove("on"));
    root.classList.add("on");
    setCount(0);
    if (detail) detail.textContent = "In Wikidata, Milan Fashion Week is one node. Its edition and shows are missing (dashed).";
    later(() => g.classList.add("ghosts"), 450);
    later(() => { edition.classList.add("on"); edge(-1).classList.add("on"); }, 2300);
    shows.forEach((s, i) => later(() => { s.classList.add("on"); edge(i).classList.add("on"); setCount(i + 1); }, 3000 + i * 260));
    later(() => { if (detail) detail.textContent = idle; }, 3000 + shows.length * 260 + 600);
  }

  shows.forEach((s) => {
    const show = () => { if (detail) detail.textContent = s.dataset.detail; };
    s.addEventListener("mouseenter", show);
    s.addEventListener("focus", show);
    s.addEventListener("click", show);
  });

  if (reduce) { finalState(); if (replay) replay.hidden = true; }
  else {
    play();
    if (replay) replay.addEventListener("click", play);
  }
})();
