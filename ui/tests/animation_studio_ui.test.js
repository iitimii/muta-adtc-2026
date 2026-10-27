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
  const studio = animator.mountStudio(root);
  studio.concept.value = "Explain 12 ÷ 3";
  studio.level.value = "upper-primary";
  return studio;
}

const capability = (available = true) => ({ ok: true, json: async () => ({ available, detail: available ? "Ready" : "Requires macOS 14 or later." }) });
const video = () => ({ ok: true, headers: { get: () => "video/mp4" }, blob: async () => new Blob(["real video fixture"], { type: "video/mp4" }) });
const project = () => animator.planProject({ topic: "Division", concept: "14 ÷ 4", level: "upper-primary" });
const settle = () => new Promise((resolve) => setImmediate(resolve));

test("Generate finishes in one MP4 stage, without Canvas or automatic playback", async () => {
  const calls = [];
  const studio = fixture(async (url) => { calls.push(url); return url.endsWith("render-capability") ? capability() : video(); });
  assert.equal(studio.tools.hidden, true);
  await studio.generateProject();
  assert.equal(studio.project.scenes[0].kind, "division");
  assert.deepEqual(calls, ["/v1/animation/render-capability", "/v1/animation/render"]);
  assert.equal(studio.renderedManimVideo.parentElement, studio.previewRoot);
  assert.equal(studio.renderedManimVideo.hidden, false);
  assert.equal(studio.renderedManimVideo.controls, true);
  assert.equal(studio.renderedManimVideo.autoplay, undefined);
  assert.equal(studio.draftRoot.hidden, true);
  assert.equal(studio.player, null);
  assert.equal(studio.downloadRendered.hidden, false);
  assert.equal(studio.renderButton.hidden, true);
  assert.equal(studio.tools.open, undefined);
  assert.equal(studio.generate.disabled, false);
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

test("visible concept alone supplies the required topic for a novel local-tutor plan", async () => {
  let requestBody;
  global.MutaChat = { studentId: "test-learner" };
  const studio = fixture(async (url, options) => {
    if (url.endsWith("/plan")) {
      requestBody = JSON.parse(options.body);
      return { ok: true, json: async () => ({ project: animator.planProject({ topic: "Growing a seed", requirements: "Seed absorbs water -> Root emerges -> Leaves open" }) }) };
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
  const studio = fixture(async (url) => url.endsWith("render-capability") ? capability() : video());
  studio.concept.value = "Plot sin(x)"; await studio.generateProject();
  studio.concept.value = "Plot cos(x)"; await studio.generateProject();
  assert.equal(studio.project.scenes[0].data.expression_text, "cos(x)");
  assert.equal(studio.topic.value, ""); studio.destroy();
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
