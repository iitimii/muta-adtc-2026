"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
global.MutaViz = require("../visualizations.js");
const animator = require("../animation-studio.js");

// Small DOM fixture: exercise the real controller, not source-text implementation guesses.
class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.listeners = new Map(); this.attributes = new Map();
    this.hidden = false; this.value = ""; this.selectedIndex = 2; this.dataset = {}; this.style = { setProperty() {} };
    this.classList = { add() {} }; this.isConnected = true;
  }
  append(...nodes) { for (const node of nodes) { node.parentElement = this; this.children.push(node); } }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  get options() { return this.children; }
  addEventListener(type, callback) { this.listeners.set(type, callback); }
  removeEventListener(type) { this.listeners.delete(type); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  removeAttribute(name) { this.attributes.delete(name); }
  getBoundingClientRect() { return { width: 640, height: 360 }; }
  getContext() { return new Proxy({ measureText: (value) => ({ width: value.length * 8 }) }, { get: (target, key) => target[key] || (() => {}) }); }
  querySelector(tag) { return this.children.find((node) => node.tagName === tag) || this.children.map((node) => node.querySelector(tag)).find(Boolean); }
  pause() { this.paused = true; }
  load() { this.loads = (this.loads || 0) + 1; }
  focus() {}
  fire(type) { return this.listeners.get(type)?.({ target: this }); }
}

function fixture(fetchImpl) {
  const root = new Element("root");
  global.document = { createElement: (tag) => new Element(tag), createTextNode: (text) => Object.assign(new Element("text"), { textContent: text }), visibilityState: "visible", addEventListener() {}, removeEventListener() {} };
  global.cancelAnimationFrame = () => {};
  global.localStorage = { getItem: () => null, setItem() {} };
  global.fetch = fetchImpl;
  global.MutaChat = { studentId: "test-learner" };
  const studio = animator.mountStudio(root);
  studio.concept.value = "Explain 12 ÷ 3";
  studio.level.value = "upper-primary";
  return studio;
}

const capability = (available = true) => ({ ok: true, json: async () => ({ available, detail: available ? "Ready" : "Requires macOS 14 or later.", program_available: available, program_detail: "Verified sandbox unavailable" }) });
const video = () => ({ ok: true, headers: { get: () => "video/mp4" }, blob: async () => new Blob(["real video fixture"], { type: "video/mp4" }) });
const project = () => animator.planProject({ topic: "Division", concept: "14 ÷ 4", level: "upper-primary" });
const settle = () => new Promise((resolve) => setImmediate(resolve));
const program = (caption = "Model scene") => ({ version: 1, kind: "manim-program", id: "program-0123456789abcdef01234567", title: caption, level: "secondary", source: `from manim import *\nclass MutaLesson(Scene):\n    def construct(self):\n        self.play(Write(Text("${caption}")), run_time=2)\n`, source_sha256: "a".repeat(64), model_id: "test-local-model", generation_token: "b".repeat(64), created_at: new Date().toISOString(), brief: "Original brief" });
const authored = (value = program()) => ({ ok: true, json: async () => ({ program: value }) });

test("Generate finishes in one MP4 stage, without Canvas or automatic playback", async () => {
  const calls = [];
  const studio = fixture(async (url) => { calls.push(url); return url.endsWith("render-capability") ? capability() : url.endsWith("/program") ? authored() : video(); });
  assert.equal(studio.tools.hidden, true);
  await studio.generateProject();
  assert.equal(studio.project.kind, "manim-program");
  assert.deepEqual(calls, ["/v1/animation/render-capability", "/v1/animation/program", "/v1/animation/program/render"]);
  assert.equal(studio.renderedManimVideo.parentElement, studio.previewRoot);
  assert.equal(studio.renderedManimVideo.hidden, false);
  assert.equal(studio.renderedManimVideo.controls, true);
  assert.equal(studio.renderedManimVideo.autoplay, undefined);
  assert.equal(studio.draftRoot, undefined);
  assert.equal(studio.player, null);
  assert.equal(studio.downloadRendered.hidden, false);
  assert.equal(studio.renderButton.hidden, true);
  assert.equal(studio.tools.open, false);
  assert.equal(studio.generate.disabled, false);
  studio.destroy();
});

test("a full library preserves every saved project while the new video stays downloadable and exportable", async () => {
  const studio = fixture(async (url) => url.endsWith("render-capability") ? capability() : url.endsWith("/program") ? authored() : video());
  const saved = Array.from({ length: 8 }, (_, index) => ({ ...program(`Saved ${index}`), id: `program-${String(index).padStart(24, "0")}` }));
  saved[0] = project(); // Preserve a mixed library of legacy lessons and model-authored programs.
  const before = JSON.stringify(saved); let encoded = before; let writes = 0;
  global.localStorage = { getItem: () => encoded, setItem: (key, value) => { writes += 1; encoded = value; } };
  await studio.generateProject();
  assert.equal(encoded, before); assert.equal(writes, 0); assert.equal(animator.loadProjects().length, 8);
  assert.equal(studio.renderedManimVideo.hidden, false); assert.equal(studio.downloadRendered.hidden, false);
  assert.equal(studio.tools.hidden, false); assert.equal(studio.generate.disabled, false);
  assert.match(studio.error.textContent, /library is full/);
  assert.ok(studio.toolsBody.children.some((node) => node.textContent === "animationExport" && node.listeners.has("click")));
  studio.destroy();
});

test("unavailable renderer and render failure use the same stage, with honest fallback and retry", async () => {
  for (const mode of ["unavailable", "failed"]) {
    let retry = false;
    const studio = fixture(async (url) => {
      if (url.endsWith("render-capability")) return capability(mode !== "unavailable" || retry);
      if (!retry) throw new Error("Worker unavailable");
      return video();
    });
    await studio.showProject(project());
    assert.equal(studio.renderedManimVideo.hidden, true);
    assert.equal(studio.draftRoot.hidden, false);
    assert.ok(studio.player);
    assert.equal(studio.downloadRendered.hidden, true);
    assert.equal(studio.renderButton.hidden, false);
    if (mode === "unavailable") assert.match(studio.stageMessage.textContent, /macOS 14/);
    retry = true;
    await studio.renderVideo();
    assert.equal(studio.renderedManimVideo.hidden, false);
    assert.equal(studio.draftRoot.hidden, true);
    assert.equal(studio.player, null);
    studio.destroy();
  }
});

test("cancellation retains the project but a late old render cannot replace a new one", async () => {
  const pending = [];
  const studio = fixture(async (url) => url.endsWith("render-capability") ? capability() : new Promise((resolve) => pending.push(resolve)));
  const first = studio.showProject(project());
  await settle();
  const original = studio.project.id;
  studio.cancelWork();
  assert.equal(studio.project.id, original);
  assert.equal(studio.draftRoot.hidden, false);
  assert.equal(studio.generate.disabled, false);
  const second = studio.renderVideo();
  await settle();
  const secondController = studio.manimAbort;
  pending[0](video()); await first;
  assert.equal(studio.manimAbort, secondController);
  assert.equal(studio.renderedManimVideo.hidden, true);
  pending[1](video()); await second;
  assert.equal(studio.renderedManimVideo.hidden, false);
  assert.equal(studio.manimVideoRevision, studio.projectRevision);
  studio.destroy();
});

test("edits revoke the old output and do not silently render or show two transports", async () => {
  let calls = 0;
  const studio = fixture(async (url) => { calls += 1; return url.endsWith("render-capability") ? capability() : video(); });
  await studio.showProject(project());
  const oldUrl = studio.manimVideoUrl;
  const oldRevision = studio.projectRevision;
  studio.moveScene(0, 1);
  assert.equal(calls, 2);
  assert.equal(studio.projectRevision, oldRevision + 1);
  assert.equal(studio.manimVideoUrl, null);
  assert.equal(studio.manimVideoBlob, null);
  assert.notEqual(studio.renderedManimVideo.src, oldUrl);
  assert.equal(studio.renderedManimVideo.hidden, true);
  assert.equal(studio.draftRoot.hidden, false);
  assert.equal(studio.downloadRendered.hidden, true);
  studio.destroy();
});

test("source requests are lazy, and a stale opened disclosure cannot overwrite revised source", async () => {
  let resolveSource;
  const studio = fixture(async (url) => {
    if (url.endsWith("render-capability")) return capability();
    if (url.endsWith("/source")) return new Promise((resolve) => { resolveSource = resolve; });
    return video();
  });
  await studio.showProject(project());
  assert.equal(studio.manimSource, null);
  const sourceDetails = studio.toolsBody.children.find((node) => node.className?.includes("animation-manim-source"));
  sourceDetails.open = true; sourceDetails.fire("toggle"); await settle();
  studio.moveScene(0, 1);
  resolveSource({ ok: true, json: async () => ({ source: "stale source", filename: "lesson.py" }) });
  await settle(); await settle();
  assert.equal(studio.manimSource, null);
  studio.destroy();
});

test("visible concept alone supplies the required topic for actual model-code authoring", async () => {
  let requestBody;
  global.MutaChat = { studentId: "test-learner" };
  const studio = fixture(async (url, options) => {
    if (url.endsWith("/program")) {
      requestBody = JSON.parse(options.body);
      return authored();
    }
    return url.endsWith("render-capability") ? capability() : video();
  });
  studio.concept.value = "Explain how a seed becomes a plant";
  await studio.generateProject();
  assert.equal(requestBody.topic, studio.concept.value);
  assert.equal(studio.renderedManimVideo.hidden, false);
  assert.equal(studio.topic.value, "");
  studio.destroy(); delete global.MutaChat;
});

test("regenerating from the visible concept does not reintroduce a hidden stale equation", async () => {
  const briefs = [];
  const studio = fixture(async (url, options) => {
    if (url.endsWith("/program")) { const brief = JSON.parse(options.body); briefs.push(brief); return authored(program(brief.concept)); }
    return url.endsWith("render-capability") ? capability() : video();
  });
  studio.concept.value = "Plot sin(x)"; await studio.generateProject();
  studio.concept.value = "Plot cos(x)"; await studio.generateProject();
  assert.equal(studio.project.title, "Plot cos(x)");
  assert.equal(briefs.length, 2); assert.equal(briefs[1].concept, "Plot cos(x)"); assert.equal(briefs[1].previous_source, "");
  assert.equal(studio.topic.value, ""); studio.destroy();
});

test("a simple radius prompt always calls the model and shows exactly its returned source", async () => {
  const calls = []; const returned = program("A novel offset circle");
  const studio = fixture(async (url, options) => { calls.push([url, options]); return url.endsWith("render-capability") ? capability() : url.endsWith("/program") ? authored(returned) : video(); });
  studio.concept.value = "Draw a circle radius 5.6 centred at (2, -1)";
  await studio.generateProject();
  assert.equal(calls.filter(([url]) => url.endsWith("/program")).length, 1);
  assert.equal(studio.project.source, returned.source);
  assert.equal(studio.toolsBody.querySelector("pre").textContent, returned.source);
  assert.equal(studio.tools.open, false); assert.equal(studio.player, null);
  studio.destroy();
});

test("render feedback reaches bounded model repair with the original brief and actual rejected source", async () => {
  const requests = []; let renders = 0; const original = program();
  const studio = fixture(async (url, options) => {
    if (url.endsWith("render-capability")) return capability();
    if (url.endsWith("/program")) { requests.push(JSON.parse(options.body)); return authored(original); }
    if (++renders === 1) return { ok: false, status: 422, json: async () => ({ detail: "NameError in scene" }) };
    return video();
  });
  studio.concept.value = "Draw a circle radius 5.6"; await studio.generateProject();
  assert.equal(requests.length, 2); assert.equal(requests[1].concept, requests[0].concept);
  assert.equal(requests[1].previous_source, original.source); assert.equal(requests[1].feedback, "NameError in scene");
  assert.equal(studio.renderedManimVideo.hidden, false); studio.destroy();
});

test("three failed code attempts stop honestly with no substitute Canvas or video", async () => {
  let attempts = 0;
  const studio = fixture(async (url) => {
    if (url.endsWith("render-capability")) return capability();
    attempts += 1; return { ok: false, status: 422, json: async () => ({ detail: { message: "Invalid source", source: "actual rejected source", repairable: true } }) };
  });
  await studio.generateProject(); assert.equal(attempts, 3); assert.equal(studio.player, null);
  assert.equal(studio.renderedManimVideo == null, true); assert.equal(studio.generate.disabled, false);
  assert.equal(studio.error.textContent, "Invalid source"); studio.destroy();
});

test("missing isolation fails closed before model calls and never shows the legacy draft", async () => {
  const calls = []; const studio = fixture(async (url) => { calls.push(url); return capability(false); });
  await studio.generateProject(); assert.equal(calls.length, 1); assert.equal(studio.player, null);
  assert.equal(studio.error.textContent, "Verified sandbox unavailable"); studio.destroy();
});

test("choosing an example cancels authoring and refuses a late old response", async () => {
  let resolve, signal;
  const studio = fixture(async (url, options) => {
    if (url.endsWith("render-capability")) return capability();
    signal = options.signal; return new Promise((finish) => { resolve = finish; });
  });
  const pending = studio.generateProject(); await settle();
  function find(node) { if (node.dataset?.example === "cubic") return node; return node.children.map(find).find(Boolean); }
  find(studio.root).fire("click");
  assert.equal(signal.aborted, true); assert.equal(studio.concept.value, "Plot y = x^3");
  resolve(authored()); await pending;
  assert.equal(studio.manimVideoBlob, null); assert.equal(studio.generate.disabled, false); studio.destroy();
});

test("multiline visible concept uses a single-line fallback title without losing the prompt", async () => {
  let sent;
  const studio = fixture(async (url, options) => {
    if (url.endsWith("render-capability")) return capability();
    if (url.endsWith("/program")) { sent = JSON.parse(options.body); return authored(program(sent.topic)); }
    return video();
  });
  studio.concept.value = "Draw a circle\nLabel its radius"; await studio.generateProject();
  assert.equal(sent.topic, "Draw a circle Label its radius"); assert.equal(sent.concept, "Draw a circle\nLabel its radius");
  assert.equal(studio.renderedManimVideo.hidden, false); studio.destroy();
});

test("imported program restores its complete editable brief for regeneration", async () => {
  const studio = fixture(async () => video());
  const imported = program("Circle lesson");
  imported.brief = JSON.stringify({ topic: "Circle lesson", concept: "Radius 5.6 cm centred at (2,-1)", requirements: "Show cm units and centre", level: "secondary" });
  studio.file.files = [{ size: 3000, text: async () => JSON.stringify(imported) }];
  await studio.importSelected();
  assert.equal(studio.concept.value, "Radius 5.6 cm centred at (2,-1)");
  assert.equal(studio.requirements.value, "Show cm units and centre"); assert.equal(studio.topic.value, "Circle lesson"); studio.destroy();
});

test("a corrupt import cancels current work rather than hiding the only cancel control", async () => {
  let finish;
  const studio = fixture(async (url) => url.endsWith("render-capability") ? capability() : new Promise((resolve) => { finish = resolve; }));
  const pending = studio.showProject(project()); await settle();
  const oldController = studio.manimAbort;
  studio.file.files = [{ size: 8, text: async () => "not json" }];
  await studio.importSelected();
  assert.equal(oldController.signal.aborted, true);
  assert.equal(studio.manimAbort, null);
  assert.equal(studio.draftRoot.hidden, false);
  assert.equal(studio.generate.disabled, false);
  finish(video()); await pending;
  assert.equal(studio.renderedManimVideo.hidden, true);
  studio.destroy();
});
