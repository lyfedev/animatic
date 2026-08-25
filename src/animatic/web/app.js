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
  daily: "daily",
  footage: "real",
  animatic_motion: "motion",
  animatic_edited: "edited",
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
  refreshBudget();
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

  /* Click SELECTS the shot for the editor below. Dragging a video onto it
     still swaps in footage, and a shot that already has footage offers to
     give it back — but a bare click no longer opens a file dialog, because
     that made the commonest gesture the one destructive thing on the page. */
  el.addEventListener("click", async () => {
    if (shot.is_real) {
      if (confirm(`Remove the real footage on ${shot.beat_id}?`)) {
        await removeFootage(shot.beat_id);
        return;
      }
    }
    await selectBeat(shot.beat_id);
  });

  el.addEventListener("dblclick", (e) => {
    e.preventDefault();
    pickFile(shot.beat_id);
  });

  if (shot.beat_id === selectedBeat) el.classList.add("is-selected");

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

/* ============================ steering ============================
 *
 * Same rule as everything above: nothing here is invented. Every cost shown
 * on a button is the number the server reported for that action, and the
 * budget is labelled an estimate because that is what it is — it counts this
 * machine only, and a CLI run spends from the same cap invisibly. */

let selectedBeat = null;

const jget = async (url) => {
  const res = await fetch(url);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body;
};

const jsend = async (url, method, body) => {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
};

const costTag = (calls) => {
  const el = document.createElement("span");
  el.className = calls === 0 ? "row-cost is-free" : "row-cost";
  el.textContent = calls === 0 ? "free" : `${calls} call${calls === 1 ? "" : "s"}`;
  return el;
};

/* ---- budget ---- */

async function refreshBudget() {
  let data;
  try {
    data = await jget("api/budget");
  } catch {
    return;
  }

  const wrap = $("budget");
  wrap.innerHTML = "";
  let lowest = Infinity;

  for (const [label, m] of Object.entries(data.models)) {
    lowest = Math.min(lowest, m.remaining_estimate);
    const card = document.createElement("div");
    card.className = "budget-model";

    const h = document.createElement("h3");
    h.textContent = label;

    const n = document.createElement("span");
    n.className = m.remaining_estimate < 20 ? "budget-count is-low" : "budget-count";
    n.textContent = m.remaining_estimate;

    const of = document.createElement("span");
    of.className = "budget-of";
    of.textContent = ` of ${m.cap} left`;

    card.append(h, n, of);
    wrap.append(card);
  }

  $("budget-tag").textContent = `~${lowest} calls left`;

  const note = document.createElement("p");
  note.className = "budget-note";
  note.textContent = data.note;
  wrap.append(note);
}

/* ---- characters ---- */

async function refreshCharacters() {
  let data;
  try {
    data = await jget("api/characters");
  } catch (err) {
    $("characters").textContent = `Could not load characters: ${err.message}`;
    return;
  }

  $("chars-tag").textContent = `${data.characters.length} speaking parts`;
  const wrap = $("characters");
  wrap.innerHTML = "";

  if (!data.available_model_sheets.length) {
    const note = document.createElement("p");
    note.className = "budget-note";
    note.textContent =
      "No model sheets yet. Put images in assets/reference-art/<slot_id>/ — " +
      "one folder per character — and they appear here.";
    wrap.append(note);
  }

  for (const c of data.characters) {
    const row = document.createElement("div");
    row.className = "row";

    const name = document.createElement("span");
    name.className = "row-name";
    name.textContent = c.display_name;

    const meta = document.createElement("span");
    meta.className = "row-meta";
    meta.textContent =
      `${c.panel_count} panel${c.panel_count === 1 ? "" : "s"}` +
      (c.model_sheet ? " · model sheet set" : "");

    row.append(name, meta);

    if (data.available_model_sheets.length) {
      const select = document.createElement("select");
      const none = document.createElement("option");
      none.textContent = "no model sheet";
      none.value = "";
      select.append(none);
      for (const sheet of data.available_model_sheets) {
        const opt = document.createElement("option");
        opt.value = sheet.slot_id;
        opt.textContent = `${sheet.slot_id} (${sheet.image_count} images)`;
        opt.selected = c.model_sheet && c.model_sheet.endsWith(sheet.slot_id);
        select.append(opt);
      }
      row.append(select);
    }

    /* The cost the server reported for THIS character, not an average. */
    row.append(costTag(c.redraw_cost_calls));
    wrap.append(row);
  }
}

/* ---- the per-shot editor ---- */

async function selectBeat(beatId) {
  selectedBeat = beatId;
  const shot = currentState?.shots.find((s) => s.beat_id === beatId);
  const editor = $("editor");
  editor.innerHTML = "";

  const head = document.createElement("div");
  head.className = "editor-head";
  const img = document.createElement("img");
  img.src = `api/panel/${beatId}?t=${Date.now()}`;
  img.alt = `Panel for ${beatId}`;
  const info = document.createElement("div");
  info.innerHTML =
    `<strong>${beatId}</strong><br>` +
    `<span class="row-meta">${shot ? `${shot.shot_secs}s · ${shot.state}` : ""}</span>`;
  head.append(img, info);
  editor.append(head);

  editor.append(holdField(beatId, shot));
  editor.append(editField(beatId));
  editor.append(uploadField(beatId, shot));

  document.getElementById("editor").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function holdField(beatId, shot) {
  const field = document.createElement("div");
  field.className = "editor-field";
  field.innerHTML =
    `<label>Hold this shot longer</label>` +
    `<p class="hint">Adds time without re-timing any other beat. Costs nothing.</p>`;

  const actions = document.createElement("div");
  actions.className = "editor-actions";
  const input = document.createElement("input");
  input.type = "number";
  input.min = "0.5";
  input.max = "120";
  input.step = "0.5";
  input.value = shot ? shot.shot_secs : 5;

  const set = document.createElement("button");
  set.className = "btn-sm";
  set.textContent = "Hold";
  set.addEventListener("click", async () => {
    try {
      await jsend(`api/beat/${beatId}/hold`, "PUT", { hold_secs: Number(input.value) });
      await refreshState();
      noteStale();
      set.textContent = "Held ✓";
      setTimeout(() => (set.textContent = "Hold"), 1600);
    } catch (err) {
      alert(`Could not hold: ${err.message}`);
    }
  });

  const clear = document.createElement("button");
  clear.className = "btn-sm btn-danger";
  clear.textContent = "Clear";
  clear.addEventListener("click", async () => {
    try {
      await jsend(`api/beat/${beatId}/hold`, "DELETE");
      await refreshState();
      noteStale();
    } catch (err) {
      alert(err.message);
    }
  });

  actions.append(input, set, clear, costTag(0));
  field.append(actions);
  return field;
}

function editField(beatId) {
  const field = document.createElement("div");
  field.className = "editor-field";
  field.innerHTML =
    `<label>Describe a change</label>` +
    `<p class="hint">The drawing is redrawn in place, keeping the room and the framing. ` +
    `Phrases like &ldquo;no other people&rdquo; are rewritten before they are sent &mdash; ` +
    `a negation gets drawn, so it is turned into a statement about what the frame holds.</p>`;

  const box = document.createElement("textarea");
  box.placeholder = "singing into a hairbrush alone in the room";

  const actions = document.createElement("div");
  actions.className = "editor-actions";
  const go = document.createElement("button");
  go.className = "btn-sm";
  go.textContent = "Redraw";

  const rewrite = document.createElement("p");
  rewrite.className = "rewrite";
  rewrite.hidden = true;

  go.addEventListener("click", async () => {
    if (!box.value.trim()) return;
    go.disabled = true;
    go.textContent = "Redrawing…";
    try {
      const res = await jsend(`api/panel/${beatId}/edit`, "POST", {
        instruction: box.value.trim(),
      });
      rewrite.hidden = false;
      rewrite.textContent = res.negations_rewritten.length
        ? `Sent instead: ${res.negations_rewritten.join("; ")}`
        : "Sent as written.";
      await refreshState();
      await refreshBudget();
      await selectBeat(beatId);
      noteStale();
    } catch (err) {
      alert(`Redraw failed: ${err.message}`);
    } finally {
      go.disabled = false;
      go.textContent = "Redraw";
    }
  });

  const revert = document.createElement("button");
  revert.className = "btn-sm btn-danger";
  revert.textContent = "Revert";
  revert.addEventListener("click", async () => {
    try {
      await jsend(`api/panel/${beatId}/edit`, "DELETE");
      await refreshState();
      await selectBeat(beatId);
      noteStale();
    } catch (err) {
      alert(err.message);
    }
  });

  actions.append(go, revert, costTag(1));
  field.append(box, actions, rewrite);
  return field;
}

function uploadField(beatId) {
  const field = document.createElement("div");
  field.className = "editor-field";
  field.innerHTML =
    `<label>Or drop in a version you edited yourself</label>` +
    `<p class="hint">Takes priority over the generated panel and is never overwritten ` +
    `by a regeneration. Costs nothing &mdash; the file is the result.</p>`;

  const actions = document.createElement("div");
  actions.className = "editor-actions";
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/png,image/jpeg";
  input.addEventListener("change", async () => {
    if (!input.files[0]) return;
    const body = new FormData();
    body.append("file", input.files[0]);
    try {
      const res = await fetch(`api/panel/${beatId}/upload`, { method: "POST", body });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      await refreshState();
      await selectBeat(beatId);
      noteStale();
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    }
  });

  actions.append(input, costTag(0));
  field.append(actions);
  return field;
}

/* ---- dailies ---- */

$("daily-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const start = $("daily-start").value.trim();
  const end = $("daily-end").value.trim();
  const file = $("daily-file").files[0];
  if (!file) return;

  const body = new FormData();
  body.append("file", file);
  try {
    const res = await fetch(`api/daily/${start}/${end}`, { method: "POST", body });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    $("daily-form").reset();
    await refreshDailies();
    await refreshState();
    noteStale();
  } catch (err) {
    alert(`Could not splice: ${err.message}`);
  }
});

async function refreshDailies() {
  let data;
  try {
    data = await jget("api/dailies");
  } catch (err) {
    $("dailies").textContent = err.message;
    return;
  }

  const wrap = $("dailies");
  wrap.innerHTML = "";
  if (!data.dailies.length) {
    const p = document.createElement("p");
    p.className = "row-meta";
    p.textContent = "No dailies spliced in.";
    wrap.append(p);
    return;
  }

  for (const d of data.dailies) {
    const row = document.createElement("div");
    row.className = "row";
    const name = document.createElement("span");
    name.className = "row-name";
    name.textContent = d.span_id;
    const meta = document.createElement("span");
    meta.className = "row-meta";
    meta.textContent = `${d.beat_count} beats · ${d.path}`;
    const remove = document.createElement("button");
    remove.className = "btn-sm btn-danger";
    remove.textContent = "Remove";
    remove.addEventListener("click", async () => {
      try {
        await jsend(`api/daily/${d.span_id}`, "DELETE");
        await refreshDailies();
        await refreshState();
        noteStale();
      } catch (err) {
        alert(err.message);
      }
    });
    row.append(name, meta, remove);
    wrap.append(row);
  }
}

refreshBudget();
refreshCharacters();
refreshDailies();
