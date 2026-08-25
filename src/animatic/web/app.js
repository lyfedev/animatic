/* Animatic demo shell.
 *
 * The one rule this file follows without exception: nothing on screen is
 * invented. The progress bar advances when the server says a shot finished,
 * never on a timer; the "cached" disclosure repeats what the server reported;
 * the per-shot badges come from /api/state. DR-02 and DR-03 are only true if
 * the client refuses to guess. */

const $ = (id) => document.getElementById(id);

/* Every URL below is relative to the document, never rooted at "/".
 *
 * The demo is served at "/" locally and behind a "/animatic" reverse proxy on
 * vockell.com. The proxy strips its prefix, so the app sees "/api/state"
 * either way — but the BROWSER has to ask for "/animatic/api/state", and an
 * absolute path would ask for "/api/state" and get the host's 404. Relative
 * paths resolve against the page, so both work with no server-side rewriting
 * and no build step. The one requirement is a trailing slash on the page URL,
 * which the proxy config enforces with a redirect. */

const STATE_LABEL = {
  footage: "real",
  animatic_motion: "motion",
  animatic_still: "",
  missing: "missing",
};

let currentState = null;

/* ---------- 1. Live beat parse ---------- */

$("parse-btn").addEventListener("click", async () => {
  const btn = $("parse-btn");
  const out = $("parse-out");
  btn.disabled = true;
  btn.textContent = "Parsing…";
  out.hidden = false;
  out.classList.remove("is-error");
  out.textContent = "Reading docs/rocky-1976.pdf and re-deriving every beat…";

  try {
    const res = await fetch("beats/parse", { method: "POST" });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || res.statusText);

    const lines = [
      `${body.total_beats} beats · ${body.total_duration_secs}s · ` +
        `${body.pct_motion_candidates}% motion candidates`,
      `written to ${body.s3_uri}`,
      "",
      ...body.scenes.map(
        (s) =>
          `scene ${s.scene}  ${String(s.beat_count).padStart(2)} beats  ` +
          `${String(s.duration_secs).padStart(6)}s  ` +
          `${s.action}a ${s.dialogue}d ${s.establishing}e`
      ),
    ];
    out.textContent = lines.join("\n");
  } catch (err) {
    out.classList.add("is-error");
    out.textContent = `Parse failed: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Parse beats";
  }
});

/* ---------- 2. Render, driven by server events ---------- */

$("render-btn").addEventListener("click", () => {
  const mode = document.querySelector('input[name="mode"]:checked').value;
  const btn = $("render-btn");
  const events = $("events");
  const line = $("progress-line");
  const fill = $("bar-fill");

  btn.disabled = true;
  btn.textContent = "Rendering…";
  $("progress").hidden = false;
  $("player-wrap").hidden = true;
  events.innerHTML = "";
  fill.style.width = "0%";
  line.textContent = "Planning shots…";

  const source = new EventSource(`api/render?mode=${encodeURIComponent(mode)}`);

  const finish = (label) => {
    source.close();
    btn.disabled = false;
    btn.textContent = "Render";
    if (label) line.textContent = label;
  };

  source.addEventListener("start", (e) => {
    const d = JSON.parse(e.data);
    const parts = Object.entries(d.sources)
      .map(([k, v]) => `${v} ${k}`)
      .join(", ");
    line.textContent = `0 / ${d.total_shots} shots · ${d.planned_secs}s planned · ${parts}`;
  });

  source.addEventListener("shot", (e) => {
    const d = JSON.parse(e.data);
    /* The bar is a ratio of shots the server has actually confirmed. */
    fill.style.width = `${(d.index / d.total) * 100}%`;
    line.textContent = `${d.index} / ${d.total} shots`;

    const li = document.createElement("li");
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = d.beat_id;
    const what = document.createElement("span");
    what.className = `src-${d.source}`;
    what.textContent = `${d.secs.toFixed(2)}s  ${d.source}`;
    li.append(who, what);
    events.append(li);
    events.scrollTop = events.scrollHeight;
  });

  source.addEventListener("done", (e) => {
    const d = JSON.parse(e.data);
    fill.style.width = "100%";
    finish(
      `${d.measured_secs}s rendered · ` +
        Object.entries(d.sources).map(([k, v]) => `${v} ${k}`).join(", ") +
        ` · ${d.real_footage_pct}% real footage`
    );

    const player = $("player");
    player.src = `${d.cut_url.replace(/^\//, "")}&t=${Date.now()}`;
    $("player-wrap").hidden = false;

    if (d.media_precomputed) {
      $("cache-tag").hidden = false;
      $("cache-tag").textContent = "media pre-computed";
      $("disclosure").textContent = d.cache_note;
    }
    refreshState();
  });

  source.addEventListener("error", (e) => {
    let detail = "the connection dropped";
    try {
      detail = JSON.parse(e.data).detail;
    } catch {
      /* EventSource also fires a bare `error` with no data on disconnect. */
    }
    finish(`Render failed: ${detail}`);
  });
});

/* ---------- 3. The shot strip ---------- */

async function refreshState() {
  try {
    const res = await fetch("api/state");
    if (!res.ok) throw new Error(res.statusText);
    currentState = await res.json();
  } catch (err) {
    $("strip").textContent = `Could not load state: ${err.message}`;
    return;
  }

  $("real-tag").textContent = `${currentState.real_footage_pct}% real`;
  const strip = $("strip");
  strip.innerHTML = "";

  for (const shot of currentState.shots) {
    strip.append(buildShot(shot));
  }
}

function buildShot(shot) {
  const el = document.createElement("div");
  el.className = `shot state-${shot.state}`;
  el.dataset.beatId = shot.beat_id;
  el.title = `${shot.beat_id} · ${shot.shot_secs}s\n${shot.shot_source_reason}`;

  const img = document.createElement("img");
  img.src = `api/panel/${shot.beat_id}`;
  img.alt = `Panel for ${shot.beat_id}`;
  img.loading = "lazy";

  const id = document.createElement("span");
  id.className = "shot-id";
  id.textContent = shot.beat_id;

  const badge = document.createElement("span");
  badge.className = "shot-badge";
  badge.textContent = STATE_LABEL[shot.state] || "";

  el.append(img, id, badge);

  el.addEventListener("dragover", (e) => {
    e.preventDefault();
    el.classList.add("is-over");
  });
  el.addEventListener("dragleave", () => el.classList.remove("is-over"));
  el.addEventListener("drop", async (e) => {
    e.preventDefault();
    el.classList.remove("is-over");
    const file = e.dataTransfer.files[0];
    if (file) await upload(shot.beat_id, file);
  });

  el.addEventListener("click", async () => {
    if (shot.is_real) {
      if (confirm(`Remove the real footage on ${shot.beat_id}?`)) {
        await removeFootage(shot.beat_id);
      }
      return;
    }
    pickFile(shot.beat_id);
  });

  return el;
}

function pickFile(beatId) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "video/mp4,video/quicktime,video/webm";
  input.addEventListener("change", async () => {
    if (input.files[0]) await upload(beatId, input.files[0]);
  });
  input.click();
}

async function upload(beatId, file) {
  const body = new FormData();
  body.append("file", file);
  try {
    const res = await fetch(`api/footage/${beatId}`, { method: "POST", body });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    await refreshState();
    noteStale();
  } catch (err) {
    alert(`Upload failed: ${err.message}`);
  }
}

async function removeFootage(beatId) {
  try {
    const res = await fetch(`api/footage/${beatId}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    await refreshState();
    noteStale();
  } catch (err) {
    alert(`Remove failed: ${err.message}`);
  }
}

function noteStale() {
  /* The shots changed, so whatever is in the player is now of a different
     cut. Say so rather than leaving a video playing that no longer matches. */
  if (!$("player-wrap").hidden) {
    $("disclosure").textContent =
      "The shots have changed since this was rendered — render again to see it.";
  }
}

refreshState();
