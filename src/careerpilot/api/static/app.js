"use strict";
// Dashboard for the CareerPilot API. All server data is rendered with textContent only.
(function () {
  const $ = (id) => document.getElementById(id);
  const state = {
    config: null, profiles: {}, jobs: {}, current: null, cursor: 0, timer: null, tab: "overview"
  };

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function headers() {
    const h = { "Content-Type": "application/json" };
    const key = $("apikey").value.trim();
    if (key) h["X-API-Key"] = key;
    return h;
  }

  async function api(path, options) {
    const res = await fetch(path, Object.assign({ headers: headers() }, options || {}));
    const ctype = res.headers.get("content-type") || "";
    const body = ctype.includes("json") ? await res.json() : await res.text();
    if (!res.ok) {
      let detail = body && body.detail !== undefined ? body.detail : body;
      if (Array.isArray(detail)) detail = detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
      throw new Error(res.status + ": " + (typeof detail === "string" ? detail : JSON.stringify(detail)));
    }
    return body;
  }

  function setStatus(text) { $("status").textContent = text; }

  function writeHash() {
    if (!state.current) return;
    history.replaceState(null, "", "#analyze=" + state.current.id + "&tab=" + state.tab);
  }

  function readHash() {
    const id = /(?:^|[&#])analyze=([A-Za-z0-9_-]+)/.exec(location.hash);
    const tab = /(?:^|[&#])tab=([a-z]+)/.exec(location.hash);
    return { id: id ? id[1] : null, tab: tab ? tab[1] : "overview" };
  }

  async function init() {
    try {
      state.config = await api("/api/config");
    } catch (err) { setStatus(err.message); return; }
    const cfg = state.config;
    $("mode").textContent = cfg.access_mode + " | v" + cfg.version + (cfg.sync_runs ? " | sync" : "");
    $("banner").hidden = !cfg.simulated;
    $("key-wrap").hidden = !cfg.auth_required;
    $("custom-wrap").hidden = !cfg.custom_inputs_allowed;
    $("apikey").value = sessionStorage.getItem("careerpilot-key") || "";
    if (cfg.auth_required && !$("apikey").value) { setStatus("Enter an API key to continue."); }
    await loadCatalog();
    const hash = readHash();
    if (hash.id) {
      state.tab = hash.tab;
      openAnalyze(hash.id);
    }
  }

  async function loadCatalog() {
    try {
      const [profiles, jobs] = await Promise.all([api("/api/profiles"), api("/api/jobs")]);
      const pSelect = $("profile");
      const jSelect = $("job");
      pSelect.replaceChildren();
      jSelect.replaceChildren();
      state.profiles = {};
      state.jobs = {};
      profiles.profiles.forEach((p) => {
        state.profiles[p.id] = p;
        const opt = el("option", null, p.name + " (" + p.id + ")");
        opt.value = p.id;
        pSelect.appendChild(opt);
      });
      jobs.jobs.forEach((j) => {
        state.jobs[j.id] = j;
        const opt = el("option", null, j.title + " @ " + j.company);
        opt.value = j.id;
        jSelect.appendChild(opt);
      });
      if (state.config.custom_inputs_allowed) {
        const pOpt = el("option", null, "Custom profile (JSON below)");
        pOpt.value = "__custom";
        pSelect.appendChild(pOpt);
        const jOpt = el("option", null, "Custom job (JSON below)");
        jOpt.value = "__custom";
        jSelect.appendChild(jOpt);
      }
      showHints();
      refreshHistory();
    } catch (err) { setStatus(err.message); }
  }

  function showHints() {
    const p = state.profiles[$("profile").value];
    const j = state.jobs[$("job").value];
    $("profile-hint").textContent = p ? p.headline : "Paste a profile JSON below.";
    $("job-hint").textContent = j
      ? j.title + " @ " + j.company + (j.location ? " · " + j.location : "")
      : "Paste a job JSON below.";
    if ($("profile").value === "__custom" || $("job").value === "__custom") {
      $("custom-wrap").open = true;
    }
  }

  async function run() {
    const body = {};
    const pChoice = $("profile").value;
    const jChoice = $("job").value;
    if (pChoice === "__custom" || jChoice === "__custom") {
      try {
        body.profile = JSON.parse($("custom-profile").value);
        body.job = JSON.parse($("custom-job").value);
      } catch (err) {
        setStatus("Custom profile/job JSON is not valid.");
        return;
      }
    } else {
      body.profile_id = pChoice;
      body.job_id = jChoice;
    }
    sessionStorage.setItem("careerpilot-key", $("apikey").value.trim());
    $("run").disabled = true;
    setStatus("Analyzing...");
    try {
      const created = await api("/api/analyze", { method: "POST", body: JSON.stringify(body) });
      await startView(created);
      if (created.state === "finished" || created.state === "error") {
        (created.events || []).forEach(addEvent);
        finish(created);
      } else {
        poll();
      }
    } catch (err) {
      setStatus(err.message);
      $("run").disabled = false;
    }
  }

  async function openAnalyze(id) {
    try {
      const detail = await api("/api/analyze/" + encodeURIComponent(id));
      await startView(detail);
      switchTab(state.tab);
      poll();
    } catch (err) { setStatus(err.message); }
  }

  async function startView(detail) {
    clearTimeout(state.timer);
    state.current = { id: detail.id, brief: null };
    state.cursor = 0;
    writeHash();
    $("result").hidden = false;
    $("progress").replaceChildren();
    $("skills").replaceChildren();
    $("flags").replaceChildren();
    $("gaps").replaceChildren();
    $("interview").replaceChildren();
    $("application").replaceChildren();
    $("brief").textContent = "";
    $("headline").textContent = "Analyzing: " + detail.profile_name + " → " + detail.job_title;
    if (detail.profile_id && state.profiles[detail.profile_id]) {
      $("profile").value = detail.profile_id;
    }
    if (detail.job_id && state.jobs[detail.job_id]) {
      $("job").value = detail.job_id;
    }
    showHints();
  }

  async function poll() {
    const cur = state.current;
    if (!cur) return;
    try {
      const page = await api("/api/analyze/" + cur.id + "/events?since=" + state.cursor);
      page.events.forEach(addEvent);
      state.cursor = page.next_cursor;
      if (page.done) {
        finish(await api("/api/analyze/" + cur.id));
        return;
      }
    } catch (err) { setStatus(err.message); }
    state.timer = setTimeout(poll, 500);
  }

  function addEvent(ev) {
    const li = el("li");
    const bits = [ev.stage];
    if (ev.data && ev.data.score !== undefined) bits.push("score " + ev.data.score);
    if (ev.data && ev.data.count !== undefined) bits.push("count " + ev.data.count);
    if (ev.data && ev.data.provider) bits.push(ev.data.provider);
    li.textContent = bits.join(" · ");
    $("progress").appendChild(li);
  }

  function scoreClass(score) {
    if (score >= 70) return "score-high";
    if (score >= 40) return "score-mid";
    return "score-low";
  }

  function finish(detail) {
    $("run").disabled = false;
    refreshHistory();
    if (detail.state === "error" || !detail.brief) {
      $("headline").textContent = "Analysis failed: " + (detail.error || "unknown error");
      setStatus("");
      return;
    }
    const brief = detail.brief;
    state.current.brief = brief;
    setStatus(detail.simulated ? "Done (simulated)." : "Done.");
    const head = $("headline");
    head.replaceChildren();
    head.appendChild(el("div", null, brief.profile_name + " → " + brief.job_title + " @ " + brief.job_company));
    const score = el("strong", scoreClass(brief.fit.score), String(brief.fit.score) + "/100");
    head.appendChild(score);
    head.appendChild(el("p", "small", brief.fit.summary));
    renderSkills(brief);
    renderFlags(brief);
    renderGaps(brief);
    renderInterview(brief);
    renderApplication(brief);
    loadBriefMarkdown();
  }

  function renderSkills(brief) {
    const root = $("skills");
    root.replaceChildren();
    const matched = el("div");
    matched.appendChild(el("h3", null, "Matched skills"));
    const mList = el("div", "chip-list");
    (brief.fit.matched_skills || []).forEach((s) => mList.appendChild(el("span", "chip matched", s)));
    if (!brief.fit.matched_skills.length) mList.appendChild(el("span", "small", "None"));
    matched.appendChild(mList);
    const missing = el("div");
    missing.appendChild(el("h3", null, "Missing skills"));
    const xList = el("div", "chip-list");
    (brief.fit.missing_skills || []).forEach((s) => xList.appendChild(el("span", "chip missing", s)));
    if (!brief.fit.missing_skills.length) xList.appendChild(el("span", "small", "None"));
    missing.appendChild(xList);
    root.appendChild(matched);
    root.appendChild(missing);
  }

  function renderFlags(brief) {
    const root = $("flags");
    root.replaceChildren();
    if (!brief.security_flags || !brief.security_flags.length) return;
    root.appendChild(el("h3", null, "Security flags"));
    const ul = el("ul");
    brief.security_flags.forEach((f) => ul.appendChild(el("li", "flag", f)));
    root.appendChild(ul);
  }

  function renderGaps(brief) {
    const root = $("gaps");
    root.replaceChildren();
    if (!brief.gaps.length) {
      root.appendChild(el("p", "small", "No required-skill gaps."));
      return;
    }
    brief.gaps.forEach((g) => {
      const card = el("div", "gap-card");
      card.appendChild(el("div", "pri", g.priority + " priority"));
      card.appendChild(el("strong", null, g.skill));
      card.appendChild(el("p", "small", g.why));
      card.appendChild(el("p", null, g.practice_plan));
      root.appendChild(card);
    });
  }

  function sectionList(root, title, items) {
    if (!items || !items.length) return;
    root.appendChild(el("h3", null, title));
    const ul = el("ul");
    items.forEach((t) => ul.appendChild(el("li", null, t)));
    root.appendChild(ul);
  }

  function renderInterview(brief) {
    const root = $("interview");
    root.replaceChildren();
    sectionList(root, "Behavioural", brief.interview.behavioral);
    sectionList(root, "Technical", brief.interview.technical);
    sectionList(root, "Talking points", brief.interview.suggested_talking_points);
  }

  function renderApplication(brief) {
    const root = $("application");
    root.replaceChildren();
    sectionList(root, "Tailored bullets", brief.application.tailored_bullets);
    (brief.application.cover_outline || []).forEach((sec) => {
      root.appendChild(el("h3", null, sec.heading));
      const ul = el("ul");
      (sec.points || []).forEach((p) => ul.appendChild(el("li", null, p)));
      root.appendChild(ul);
    });
    if (brief.application.keywords_to_mirror && brief.application.keywords_to_mirror.length) {
      root.appendChild(el("h3", null, "Keywords to mirror"));
      const chips = el("div", "chip-list");
      brief.application.keywords_to_mirror.forEach((k) => chips.appendChild(el("span", "chip", k)));
      root.appendChild(chips);
    }
  }

  async function loadBriefMarkdown() {
    if (!state.current) return;
    try {
      const md = await api("/api/analyze/" + state.current.id + "/brief.md");
      $("brief").textContent = md;
    } catch (err) { $("brief").textContent = "Could not load Markdown: " + err.message; }
  }

  async function copyBrief() {
    try {
      await navigator.clipboard.writeText($("brief").textContent);
      setStatus("Brief copied.");
    } catch (err) { setStatus("Copy failed: " + err.message); }
  }

  async function downloadBrief() {
    try {
      const blob = new Blob([$("brief").textContent], { type: "text/markdown" });
      const a = el("a");
      a.href = URL.createObjectURL(blob);
      a.download = state.current.id + "-brief.md";
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    } catch (err) { setStatus("Download failed: " + err.message); }
  }

  async function refreshHistory() {
    try {
      const list = await api("/api/analyze?limit=10");
      const ul = $("history");
      ul.replaceChildren();
      if (!list.analyses.length) ul.appendChild(el("li", "small", "No analyses yet."));
      list.analyses.forEach((d) => {
        const li = el("li");
        const a = el("a", null, d.profile_name + " → " + d.job_title);
        a.href = "#analyze=" + d.id + "&tab=overview";
        a.addEventListener("click", (e) => {
          e.preventDefault();
          state.tab = "overview";
          openAnalyze(d.id);
        });
        li.appendChild(a);
        li.appendChild(el("span", "small", "  " + d.state +
          (d.score !== null && d.score !== undefined ? " · " + d.score + "/100" : "")));
        ul.appendChild(li);
      });
    } catch (err) { /* history is optional */ }
  }

  function switchTab(name) {
    const allowed = ["overview", "gaps", "interview", "application", "brief"];
    if (allowed.indexOf(name) < 0) name = "overview";
    state.tab = name;
    document.querySelectorAll(".tabs button").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === name);
    });
    allowed.forEach((t) => { $("tab-" + t).hidden = t !== name; });
    writeHash();
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("profile").addEventListener("change", showHints);
    $("job").addEventListener("change", showHints);
    $("run").addEventListener("click", run);
    $("copy").addEventListener("click", copyBrief);
    $("download").addEventListener("click", downloadBrief);
    $("apikey").addEventListener("change", loadCatalog);
    document.querySelectorAll(".tabs button").forEach((b) => {
      b.addEventListener("click", () => switchTab(b.dataset.tab));
    });
    init();
  });
})();
