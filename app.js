(() => {
  "use strict";

  const PAGE_SIZE = 12;
  const EXPECTED_SCHEMA = "1.0";
  const STALE_AFTER_MS = 48 * 60 * 60 * 1000;

  const elements = {
    search: document.querySelector("#search-input"),
    clearSearch: document.querySelector("#clear-search"),
    filtersForm: document.querySelector("#filters-form"),
    functionFilter: document.querySelector("#filter-function"),
    modeFilter: document.querySelector("#filter-mode"),
    locationFilter: document.querySelector("#filter-location"),
    experienceFilter: document.querySelector("#filter-experience"),
    sourceFilter: document.querySelector("#filter-source"),
    resetFilters: document.querySelector("#reset-filters"),
    sort: document.querySelector("#sort-order"),
    resultsCount: document.querySelector("#results-count"),
    jobs: document.querySelector("#jobs"),
    loadMore: document.querySelector("#load-more"),
    loading: document.querySelector("#loading-state"),
    error: document.querySelector("#error-state"),
    retry: document.querySelector("#retry-load"),
    empty: document.querySelector("#empty-state"),
    emptyTitle: document.querySelector("#empty-title"),
    emptyCopy: document.querySelector("#empty-copy"),
    emptyReset: document.querySelector("#empty-reset"),
    notices: document.querySelector("#notices"),
    freshness: document.querySelector("#freshness"),
    statTotal: document.querySelector("#stat-total"),
    statMarketing: document.querySelector("#stat-marketing"),
    statNew: document.querySelector("#stat-new"),
    statSources: document.querySelector("#stat-sources")
  };

  const state = { snapshot: null, jobs: [], filtered: [], visible: PAGE_SIZE, request: null };

  function text(value, fallback = "Unknown") {
    return typeof value === "string" && value.trim() ? value.trim() : fallback;
  }

  function httpsUrl(value) {
    try {
      const parsed = new URL(value);
      return parsed.protocol === "https:" ? parsed.href : null;
    } catch {
      return null;
    }
  }

  function parsedTime(value) {
    if (!value) return null;
    const time = Date.parse(value);
    return Number.isFinite(time) ? time : null;
  }

  function formatDate(value) {
    const time = parsedTime(value);
    if (time === null) return null;
    return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(time);
  }

  function formatDateTime(value) {
    const time = parsedTime(value);
    if (time === null) return "time unavailable";
    return `${new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" }).format(time)} IST`;
  }

  function titleCase(value) {
    return text(value).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function salaryLabel(salary) {
    if (!salary || (salary.min == null && salary.max == null)) return null;
    const currency = typeof salary.currency === "string" ? salary.currency : "";
    const formatter = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
    let amount;
    if (salary.min != null && salary.max != null) amount = `${formatter.format(salary.min)}–${formatter.format(salary.max)}`;
    else if (salary.min != null) amount = `From ${formatter.format(salary.min)}`;
    else amount = `Up to ${formatter.format(salary.max)}`;
    const period = salary.period ? ` / ${titleCase(salary.period).toLowerCase()}` : "";
    return `${currency} ${amount}${period}`.trim();
  }

  function isRenderable(job, generatedAt) {
    if (!job || job.availability_status !== "source_listed") return false;
    if (!httpsUrl(job.application_url) || !httpsUrl(job.source_url)) return false;
    const expiry = parsedTime(job.expires_at);
    const generated = parsedTime(generatedAt);
    return expiry === null || generated === null || expiry >= generated;
  }

  function assertSnapshot(data) {
    if (!data || data.schema_version !== EXPECTED_SCHEMA || !Array.isArray(data.jobs) || !Array.isArray(data.sources)) {
      throw new Error("Unsupported or malformed jobs snapshot");
    }
    return data;
  }

  function setOptions(select, values, labeler = titleCase) {
    while (select.options.length > 1) select.remove(1);
    [...new Set(values.filter(Boolean))]
      .sort((a, b) => String(a).localeCompare(String(b)))
      .forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = labeler(value);
        select.append(option);
      });
  }

  function configureFilters() {
    setOptions(elements.functionFilter, state.jobs.map((job) => job.function), (value) => value);
    setOptions(elements.modeFilter, state.jobs.map((job) => job.work_mode));
    setOptions(elements.locationFilter, state.jobs.map((job) => job.location_text), (value) => value);
    setOptions(elements.experienceFilter, state.jobs.map((job) => job.experience_level));
    setOptions(elements.sourceFilter, state.jobs.map((job) => job.source_key), (value) => {
      const match = state.snapshot.sources.find((source) => source.key === value);
      return match ? match.name : value;
    });
  }

  function renderSnapshotMeta() {
    const { snapshot } = state;
    const generated = parsedTime(snapshot.generated_at);
    const stale = generated === null || Date.now() - generated > STALE_AFTER_MS;
    const unhealthySources = snapshot.sources.filter((source) => source.status === "partial" || source.status === "failed");
    elements.freshness.textContent = `Data updated: ${formatDateTime(snapshot.generated_at)}`;
    elements.notices.replaceChildren();

    if (stale) addNotice("Listings may be outdated - verify on source.");
    if (unhealthySources.length) {
      const names = unhealthySources.map((source) => text(source.name, source.key)).join(", ");
      addNotice(`Source coverage is partial. Recent data was unavailable from: ${names}.`);
    }

    const stats = snapshot.stats || {};
    elements.statTotal.textContent = Number.isInteger(stats.total) ? String(stats.total) : String(state.jobs.length);
    elements.statMarketing.textContent = Number.isInteger(stats.marketing) ? String(stats.marketing) : String(state.jobs.filter((job) => job.function === "Marketing").length);
    elements.statNew.textContent = Number.isInteger(stats.new_last_7_days) ? String(stats.new_last_7_days) : "—";
    elements.statSources.textContent = Number.isInteger(stats.sources_ok) ? String(stats.sources_ok) : String(snapshot.sources.filter((source) => source.status === "ok").length);
  }

  function addNotice(message) {
    const notice = document.createElement("p");
    notice.className = "notice";
    notice.textContent = message;
    elements.notices.append(notice);
  }

  function matchesSearch(job, query) {
    if (!query) return true;
    return [job.title, job.company, job.summary, job.location_text, ...(Array.isArray(job.skills) ? job.skills : [])]
      .filter((value) => typeof value === "string")
      .join(" ")
      .toLocaleLowerCase()
      .includes(query);
  }

  function recentValue(job) {
    return parsedTime(job.posted_at) ?? Number.NEGATIVE_INFINITY;
  }

  function applyControls() {
    const query = elements.search.value.trim().toLocaleLowerCase();
    state.filtered = state.jobs.filter((job) =>
      matchesSearch(job, query) &&
      (!elements.functionFilter.value || job.function === elements.functionFilter.value) &&
      (!elements.modeFilter.value || job.work_mode === elements.modeFilter.value) &&
      (!elements.locationFilter.value || job.location_text === elements.locationFilter.value) &&
      (!elements.experienceFilter.value || job.experience_level === elements.experienceFilter.value) &&
      (!elements.sourceFilter.value || job.source_key === elements.sourceFilter.value)
    );

    state.filtered.sort((a, b) => {
      if (elements.sort.value === "marketing") {
        const score = (Number(b.marketing_priority_score) || 0) - (Number(a.marketing_priority_score) || 0);
        if (score) return score;
      }
      return recentValue(b) - recentValue(a);
    });
    state.visible = PAGE_SIZE;
    renderJobs();
  }

  function card(job, index) {
    const article = document.createElement("article");
    article.className = "job-card";
    article.style.animationDelay = `${Math.min(index, 8) * 25}ms`;

    const main = document.createElement("div");
    main.className = "job-main";
    const heading = document.createElement("h2");
    heading.className = "job-title";
    heading.textContent = text(job.title);
    const company = document.createElement("p");
    company.className = "company";
    company.textContent = text(job.company);

    const metadata = document.createElement("p");
    metadata.className = "metadata";
    [
      text(job.function),
      text(job.location_text),
      titleCase(job.work_mode),
      titleCase(job.experience_level),
      formatDate(job.posted_at) ? `Posted ${formatDate(job.posted_at)}` : null,
      salaryLabel(job.salary)
    ].filter(Boolean).forEach((value) => {
      const item = document.createElement("span");
      item.textContent = value;
      metadata.append(item);
    });

    main.append(heading, company, metadata);
    if (typeof job.summary === "string" && job.summary.trim()) {
      const summary = document.createElement("p");
      summary.className = "summary";
      summary.textContent = job.summary.trim();
      main.append(summary);
    }
    if (Array.isArray(job.skills) && job.skills.length) {
      const skills = document.createElement("ul");
      skills.className = "skills";
      skills.setAttribute("aria-label", "Skills");
      job.skills.slice(0, 5).forEach((skill) => {
        if (typeof skill !== "string" || !skill.trim()) return;
        const item = document.createElement("li");
        item.textContent = skill.trim();
        skills.append(item);
      });
      if (skills.childElementCount) main.append(skills);
    }

    const actions = document.createElement("div");
    actions.className = "job-action";
    const source = document.createElement("p");
    source.className = "source-credit";
    source.append(document.createTextNode("Source: "));
    const sourceLink = document.createElement("a");
    sourceLink.href = httpsUrl(job.source_url);
    sourceLink.target = "_blank";
    sourceLink.rel = "noopener noreferrer";
    sourceLink.textContent = text(job.source_name, job.source_key);
    source.append(sourceLink);

    const apply = document.createElement("a");
    apply.className = "apply-link";
    apply.href = httpsUrl(job.application_url);
    apply.target = "_blank";
    apply.rel = "noopener noreferrer";
    apply.textContent = "View & apply";
    apply.setAttribute("aria-label", `View and apply for ${text(job.title)} at ${text(job.company)}`);
    actions.append(source, apply);
    article.append(main, actions);
    return article;
  }

  function renderJobs() {
    const total = state.filtered.length;
    const visible = Math.min(state.visible, total);
    elements.jobs.replaceChildren(...state.filtered.slice(0, visible).map(card));
    elements.resultsCount.textContent = total ? `Showing 1–${visible} of ${total} listings` : "0 listings";
    elements.loadMore.hidden = visible >= total;
    elements.empty.hidden = total !== 0;
    if (total === 0) {
      const noPublished = state.jobs.length === 0;
      elements.emptyTitle.textContent = noPublished ? "No current listings are published" : "No listings match these filters";
      elements.emptyCopy.textContent = noPublished ? "The latest approved snapshot contains no current listings. Check again after the next data update." : "Try a broader search or reset the filters.";
      elements.emptyReset.hidden = noPublished;
    }
  }

  function resetControls() {
    elements.search.value = "";
    elements.filtersForm.reset();
    elements.sort.value = "marketing";
    applyControls();
    elements.search.focus();
  }

  function debounce(callback, delay) {
    let timer;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => callback(...args), delay);
    };
  }

  async function loadJobs() {
    if (state.request) state.request.abort();
    state.request = new AbortController();
    elements.loading.hidden = false;
    elements.error.hidden = true;
    elements.empty.hidden = true;
    elements.jobs.replaceChildren();
    elements.resultsCount.textContent = "Loading listings…";
    try {
      const response = await fetch("./data/jobs.json", { cache: "no-cache", signal: state.request.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.snapshot = assertSnapshot(await response.json());
      state.jobs = state.snapshot.jobs.filter((job) => isRenderable(job, state.snapshot.generated_at));
      configureFilters();
      renderSnapshotMeta();
      applyControls();
      elements.loading.hidden = true;
    } catch (error) {
      if (error.name === "AbortError") return;
      elements.loading.hidden = true;
      elements.error.hidden = false;
      elements.resultsCount.textContent = "Listings unavailable";
      elements.freshness.textContent = "Data update status unavailable";
      console.error("Jobs Radar failed to load the approved snapshot", error);
    } finally {
      state.request = null;
    }
  }

  const debouncedSearch = debounce(applyControls, 200);
  elements.search.addEventListener("input", debouncedSearch);
  elements.clearSearch.addEventListener("click", () => { elements.search.value = ""; applyControls(); elements.search.focus(); });
  elements.filtersForm.addEventListener("change", applyControls);
  elements.sort.addEventListener("change", applyControls);
  elements.resetFilters.addEventListener("click", resetControls);
  elements.emptyReset.addEventListener("click", resetControls);
  elements.retry.addEventListener("click", loadJobs);
  elements.loadMore.addEventListener("click", () => { state.visible += PAGE_SIZE; renderJobs(); });
  loadJobs();
})();
