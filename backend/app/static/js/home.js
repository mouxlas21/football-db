(function () {
  const season = window.__SEASON__ || "";

  // Helper: add season to a URL if present
  function withSeason(url) {
    if (!season) return url;
    const hasQuery = url.includes("?");
    return url + (hasQuery ? "&" : "?") + "season=" + encodeURIComponent(season);
    }
  function setHref(id, url) {
    const a = document.getElementById(id);
    if (a) a.href = withSeason(url);
  }

  // Wire season into “View all” links
  setHref("link-matches-today", "/matches?date=today");
  setHref("link-leagues", "/leagues");
  setHref("link-clubs", "/clubs?sort=trending");
  setHref("link-stats", "/stats");

  // Update season select -> reload page with ?season=
  const seasonSelect = document.getElementById("season");
  if (seasonSelect) {
    seasonSelect.addEventListener("change", () => {
      const s = seasonSelect.value;
      const base = window.location.pathname;
      const next = s ? `${base}?season=${encodeURIComponent(s)}` : base;
      window.location.assign(next);
    });
  }

  // Fetch helper with graceful failure
  async function getJSON(url) {
    try {
      const res = await fetch(withSeason(url), { headers: { "Accept": "application/json" }});
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (e) {
      console.warn("Fetch failed:", url, e);
      return null;
    }
  }

  // --- Today’s Matches ---
  (async function loadMatchesToday() {
    const root = document.querySelector("#card-matches-today [data-role='list']");
    if (!root) return;
    const data = await getJSON("/api/matches?date=today&limit=10");
    root.innerHTML = "";
    if (!data || !Array.isArray(data) || data.length === 0) {
      root.innerHTML = `<li>No matches found for today.</li>`;
      return;
    }
    data.forEach(m => {
      // Adjust fields to your schema
      const id = m.id || m.match_id || m.uuid;
      const home = m.home_name || m.home || m.home_team?.name || "Home";
      const away = m.away_name || m.away || m.away_team?.name || "Away";
      const time = m.kickoff || m.start_time || m.date || "";
      const href = withSeason(`/matches/${id}`);
      const li = document.createElement("li");
      li.innerHTML = `<a href="${href}">${home} vs ${away}</a> ${time ? "— " + time : ""}`;
      root.appendChild(li);
    });
  })();

  // --- Top Leagues (active) ---
  (async function loadTopLeagues() {
    const root = document.querySelector("#card-top-leagues [data-role='chips']");
    if (!root) return;
    const data = await getJSON("/api/leagues?active=true&limit=5");
    root.innerHTML = "";
    if (!data || !Array.isArray(data) || data.length === 0) {
      root.innerHTML = `<span>No active leagues.</span>`;
      return;
    }
    data.forEach(lg => {
      const id = lg.id || lg.league_id || lg.uuid;
      const name = lg.name || lg.league_name || "League";
      const a = document.createElement("a");
      a.href = withSeason(`/leagues/${id}`);
      a.textContent = name;
      root.appendChild(a);
    });
  })();

  // --- Trending Clubs ---
  (async function loadTrendingClubs() {
    const root = document.querySelector("#card-trending-clubs [data-role='list']");
    if (!root) return;
    const data = await getJSON("/api/clubs?sort=recent_activity&limit=6");
    root.innerHTML = "";
    if (!data || !Array.isArray(data) || data.length === 0) {
      root.innerHTML = `<li>No trending clubs right now.</li>`;
      return;
    }
    data.forEach(cl => {
      const id = cl.id || cl.club_id || cl.uuid;
      const name = cl.name || cl.club_name || "Club";
      const a = withSeason(`/clubs/${id}`);
      const li = document.createElement("li");
      li.innerHTML = `<a href="${a}">${name}</a>`;
      root.appendChild(li);
    });
  })();

  // --- Leaderboards (tabs) ---
  const lbRoot = document.querySelector("#card-leaderboards [data-role='list']");
  const tabs = document.querySelectorAll("#card-leaderboards .tabs button");
  let currentTab = "scorers";

  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      tabs.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentTab = btn.dataset.tab;
      loadLeaderboard(currentTab);
    });
  });

  async function loadLeaderboard(kind) {
    if (!lbRoot) return;
    lbRoot.innerHTML = `<li>Loading…</li>`;
    const endpointMap = {
      scorers: "/api/stats/top_scorers?limit=5",
      assists: "/api/stats/top_assists?limit=5",
      clean_sheets: "/api/stats/clean_sheets?limit=5"
    };
    const data = await getJSON(endpointMap[kind] || endpointMap.scorers);
    lbRoot.innerHTML = "";
    if (!data || !Array.isArray(data) || data.length === 0) {
      lbRoot.innerHTML = `<li>No data.</li>`;
      return;
    }
    data.forEach((row, idx) => {
      const player = row.player_name || row.name || row.player?.name || "Player";
      const club = row.club_name || row.team || row.club?.name || "";
      const val = row.value || row.goals || row.assists || row.clean_sheets || 0;
      const a = withSeason(row.player_id ? `/players/${row.player_id}` : "#");
      const li = document.createElement("li");
      li.innerHTML = `<span>${idx + 1}.</span> <a href="${a}">${player}</a>${club ? " – " + club : ""} <strong>${val}</strong>`;
      lbRoot.appendChild(li);
    });
  }
  loadLeaderboard(currentTab);
})();
