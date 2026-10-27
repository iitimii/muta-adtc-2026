"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const storage = new Map();
global.localStorage = {
  getItem: (key) => storage.get(key) || null,
  setItem: (key, value) => storage.set(key, value),
};

global.MutaViz = require("../visualizations.js");
const animator = require("../animation-studio.js");

function plan(concept, level = "secondary", requirements = "") {
  return animator.planProject({ topic: `Lesson: ${concept}`, concept, level, requirements });
}

test("fraction family changes semantic geometry for 3/4 and 2/5", () => {
  const threeQuarters = plan("Explain 3/4", "early-primary");
  const twoFifths = plan("Explain 2/5", "upper-primary");
  assert.deepEqual(threeQuarters.scenes[1].data, { numerator: 3, denominator: 4, phase: "shade" });
  assert.deepEqual(twoFifths.scenes[1].data, { numerator: 2, denominator: 5, phase: "shade" });
  assert.match(twoFifths.scenes[2].narration, /2\/5/);
});

test("fraction parser recognizes natural-language quantities", () => {
  assert.deepEqual(animator.parseFraction("Please explain three quarters"), { numerator: 3, denominator: 4 });
  assert.deepEqual(animator.parseFraction("show two fifths"), { numerator: 2, denominator: 5 });
});

test("array family changes rows, columns, addition, and total", () => {
  const sixByFour = plan("Build 6 × 4", "upper-primary");
  const threeBySeven = plan("Build 3 x 7", "upper-primary");
  assert.deepEqual(sixByFour.scenes[0].data, { rows: 6, columns: 4, phase: "build" });
  assert.equal(sixByFour.scenes[1].narration, "4 + 4 + 4 + 4 + 4 + 4 = 24.");
  assert.deepEqual(threeBySeven.scenes[2].data, { rows: 3, columns: 7, phase: "equation" });
  assert.equal(threeBySeven.scenes[2].narration, "3 × 7 = 21.");
});

test("array parser recognizes groups in words", () => {
  assert.deepEqual(animator.parseArray("Build six groups of four"), { rows: 6, columns: 4 });
});

test("safe polynomial parser creates coefficients without executing source", () => {
  const cubic = animator.parseFunction("Plot y = x^3");
  assert.equal(cubic.output, "y"); assert.equal(cubic.variable, "x"); assert.equal(cubic.expression_text, "x^3"); assert.deepEqual(cubic.domain, [-3, 3]);
  assert.equal(animator.expressionValue(cubic.expression_ast, "x", 2), 8);
  assert.equal(animator.parseFunction("y = Math.sin(x)"), null);
  assert.equal(animator.parseFunction("y = (() => 7)()"), null);
});

test("polynomial samples preserve known cubic invariants", () => {
  const project = plan("plot y = x^3");
  const { expression_ast: ast, variable } = project.scenes[0].data;
  assert.equal(animator.expressionValue(ast, variable, -2), -8);
  assert.equal(animator.expressionValue(ast, variable, 0), 0);
  assert.equal(animator.expressionValue(ast, variable, 2), 8);
});

test("typed expression bridge supports trigonometric exponential and rational curves", () => {
  const sine = plan("plot y = sin(x)");
  const nakedSine = plan("plot sin(x)");
  const exponential = plan("plot y = exp(-x^2)");
  const rational = plan("plot y = 1/(x-1)");
  assert.ok(Math.abs(animator.expressionValue(sine.scenes[0].data.expression_ast, "x", Math.PI / 2) - 1) < 1e-10);
  assert.ok(Math.abs(animator.expressionValue(nakedSine.scenes[0].data.expression_ast, "x", Math.PI / 2) - 1) < 1e-10);
  assert.equal(animator.expressionValue(exponential.scenes[0].data.expression_ast, "x", 0), 1);
  assert.equal(animator.expressionValue(rational.scenes[0].data.expression_ast, "x", 1), null);
  const bounded = plan("Plot y = sin(x) from -pi to pi");
  assert.ok(Math.abs(bounded.scenes[0].data.domain[0] + Math.PI) < 1e-10);
  assert.ok(Math.abs(bounded.scenes[0].data.domain[1] - Math.PI) < 1e-10);
});

test("Unicode pi and common scalar range forms stay on the typed function path", () => {
  const exact = animator.planProject({
    topic: "A sine wave",
    concept: "Plot y = sin(x) from -π to π",
    level: "secondary",
    requirements: "Draw labelled axes and trace the sine curve.",
  });
  assert.deepEqual(exact.scenes.map((scene) => scene.kind), ["function", "function"]);
  assert.deepEqual(exact.scenes[0].data.domain, [-Math.PI, Math.PI]);
  assert.equal(exact.scenes[0].data.expression_text, "sin(x)");

  const cases = [
    ["Plot y = sin(x) from −π through π", [-Math.PI, Math.PI]],
    ["Plot y = sin(x) between −π and π", [-Math.PI, Math.PI]],
    ["Plot y = sin(x) from −2π to 2π", [-2 * Math.PI, 2 * Math.PI]],
    ["Plot y = sin(x) from -2pi to 2pi", [-2 * Math.PI, 2 * Math.PI]],
    ["Plot y = sin(x) on the interval [−2π, 2π]", [-2 * Math.PI, 2 * Math.PI]],
    ["Plot y = cos(x) for x ∈ [−π/2, π/2]", [-Math.PI / 2, Math.PI / 2]],
    ["Plot y = sin(x) for −π ≤ x ≤ π", [-Math.PI, Math.PI]],
    ["Plot y = sin(x) for −π < x < π", [-Math.PI, Math.PI]],
    ["Graph y = sin(x), −π ≤ x ≤ π", [-Math.PI, Math.PI]],
  ];
  for (const [prompt, domain] of cases) {
    const parsed = animator.parseFunction(prompt);
    assert.ok(parsed, prompt);
    assert.ok(Math.abs(parsed.domain[0] - domain[0]) < 1e-10, prompt);
    assert.ok(Math.abs(parsed.domain[1] - domain[1]) < 1e-10, prompt);
    assert.ok(["sin(x)", "cos(x)"].includes(parsed.expression_text), prompt);
    assert.ok(Math.abs(animator.expressionValue(parsed.expression_ast, "x", Math.PI / 2)) <= 1, prompt);
  }

  const rationalDomain = plan("Plot y = 1.5*x from -1/2 to 1/2");
  assert.deepEqual(rationalDomain.scenes[0].data.domain, [-0.5, 0.5]);
  assert.equal(rationalDomain.scenes[0].data.expression_text, "1.5*x");
  assert.equal(animator.expressionValue(rationalDomain.scenes[0].data.expression_ast, "x", 0.5), 0.75);

  const negativeFraction = plan("Plot y = -1/2*x");
  assert.equal(animator.expressionValue(negativeFraction.scenes[0].data.expression_ast, "x", 4), -2);
  const decimalCoefficient = plan("Plot y = 0.5*x");
  assert.equal(animator.expressionValue(decimalCoefficient.scenes[0].data.expression_ast, "x", 4), 2);
  const wholeNumberQuotient = plan("Plot y = 10/2*x");
  assert.equal(wholeNumberQuotient.scenes[0].data.expression_text, "10/2*x");
  assert.equal(animator.expressionValue(wholeNumberQuotient.scenes[0].data.expression_ast, "x", 4), 20);
  const negativeWholeNumberQuotient = plan("Plot y = -10/2*x");
  assert.equal(animator.expressionValue(negativeWholeNumberQuotient.scenes[0].data.expression_ast, "x", 4), -20);
  const quotientDomain = plan("Plot y = x from -10/2 to 1/2");
  assert.deepEqual(quotientDomain.scenes[0].data.domain, [-5, 0.5]);

  const unsupportedEndpointArithmetic = [
    "Plot y = sin(x) from -2π to 2π+1",
    "Plot y = sin(x) from -2π to 2π - 1",
    "Plot y = sin(x) from -2π to 2π*2",
    "Plot y = sin(x) from -2π to 2π × 2",
    "Plot y = sin(x) from -2π to 2π/x",
    "Plot y = sin(x) from -2π to 2π^2",
    "Plot y = sin(x) from -π to π/2+1",
    "Plot y = sin(x) between -π and π+pi",
    "Plot y = sin(x) on the interval [-π, π*pi]",
    "Plot y = sin(x) for -π ≤ x ≤ π/pi",
  ];
  for (const prompt of unsupportedEndpointArithmetic) {
    assert.equal(animator.parseFunction(prompt), null, prompt);
    assert.throws(() => plan(prompt), /could not safely resolve that explicit function/, prompt);
  }
});

test("Unicode exponent runs preserve one exponent instead of chaining powers", () => {
  const multiDigit = animator.parseFunction("Plot y = x²³");
  assert.equal(multiDigit.expression_text, "x^23");
  assert.equal(animator.expressionValue(multiDigit.expression_ast, "x", 2), 8388608);
  const negative = animator.parseFunction("Plot y = x⁻²");
  assert.equal(negative.expression_text, "x^-2");
  assert.equal(animator.expressionValue(negative.expression_ast, "x", 2), 0.25);
  assert.equal(animator.parseFunction("Plot y = x²⁻³"), null);
});

test("tertiary derivative and definite-integral workflows compute real quantities", () => {
  const derivative = plan("plot y = x^3 and show the tangent at x = 2", "tertiary");
  assert.equal(derivative.scenes[1].data.mode, "derivative");
  assert.ok(Math.abs(animator.numericalDerivative(derivative.scenes[1].data.expression_ast, "x", 2) - 12) < 1e-5);
  assert.match(derivative.scenes[1].narration, /12\.0000/);
  const integral = plan("plot y = x^2 and show the definite integral from 0 to 1", "tertiary");
  assert.equal(integral.scenes[1].data.mode, "integral");
  assert.ok(Math.abs(animator.numericalIntegral(integral.scenes[1].data.expression_ast, "x", 0, 1) - 1 / 3) < 1e-4);
  assert.match(integral.scenes[1].narration, /0\.3333/);
  const naturalDerivative = plan("Derivative y = x^2 at x = 2", "tertiary");
  assert.equal(naturalDerivative.scenes[1].data.parameter, 2);
  assert.ok(Math.abs(animator.numericalDerivative(naturalDerivative.scenes[1].data.expression_ast, "x", 2) - 4) < 1e-5);
  const piDerivative = plan("Derivative y = x^2 at x = 2π", "tertiary");
  assert.equal(piDerivative.scenes[0].data.expression_text, "x^2");
  assert.ok(Math.abs(piDerivative.scenes[1].data.parameter - 2 * Math.PI) < 1e-10);
  assert.ok(Math.abs(animator.numericalDerivative(piDerivative.scenes[1].data.expression_ast, "x", 2 * Math.PI) - 4 * Math.PI) < 1e-4);
  const decimalDerivative = plan("Derivative y = x^2 at x = .5", "tertiary");
  assert.equal(decimalDerivative.scenes[0].data.expression_text, "x^2");
  assert.equal(decimalDerivative.scenes[1].data.parameter, 0.5);
  const naturalIntegral = plan("Integral y = x^2 from 0 to 1", "tertiary");
  assert.deepEqual(naturalIntegral.scenes[1].data.bounds, [0, 1]);
});

test("tertiary vector scenes preserve components and magnitude", () => {
  const project = plan("Show force (3, 4)", "tertiary");
  assert.deepEqual(project.scenes[0].data, { x: 3, y: 4, label: "force" });
  assert.match(project.summary, /magnitude 5\.00/);
});

test("ordered process requirements preserve order and active stage", () => {
  const project = plan("Photosynthesis pathway", "secondary", "roots absorb water -> stem carries water -> leaves combine water and carbon dioxide");
  assert.equal(project.scenes.length, 3);
  assert.deepEqual(project.scenes[2].data.steps, ["roots absorb water", "stem carries water", "leaves combine water and carbon dioxide"]);
  assert.equal(project.scenes[2].data.active, 2);
});

test("ambiguous prompts fail honestly instead of selecting an unrelated visual", () => {
  assert.throws(() => plan("Explain consciousness", "tertiary"), /needs a bounded visual relationship/);
  assert.throws(() => animator.planProject({ topic: "Fractions", concept: "Explain 2/5", level: "upper-primary", requirements: "Use blue shading" }), /not applied silently/);
  assert.throws(() => plan("Explain -3/4", "upper-primary"), /will not drop the negative sign/);
  assert.throws(() => plan("Explain -3 x 4", "upper-primary"), /will not drop the negative sign/);
  assert.throws(() => plan("Explain negative three quarters", "upper-primary"), /will not drop the negative sign/);
  assert.throws(() => plan("Explain 48/2", "upper-primary"), /more than four whole bars/);
  assert.throws(() => plan("Explain −3/4", "upper-primary"), /will not drop the negative sign/);
  assert.throws(() => plan("Explain 1.5/2", "upper-primary"), /will not truncate a decimal/);
  assert.throws(() => plan("Build 1.5 x 4", "upper-primary"), /will not truncate a decimal/);
  assert.throws(() => plan("Explain 3/4 + 1/4", "upper-primary"), /will not discard an operand/);
  assert.throws(
    () => animator.planProject({ topic: "Unresolved graph", concept: "Plot y = mystery(x) from −π to π", level: "secondary", requirements: "start -> peak -> finish" }),
    /could not safely resolve that explicit function/,
  );
  assert.throws(() => animator.planProject({ topic: "Unresolved equation", concept: "x = mystery(t)", level: "secondary", requirements: "start -> finish" }), /could not safely resolve that explicit function/);
  assert.throws(() => animator.planProject({ topic: "Unresolved function", concept: "f(x) = mystery(x)", level: "secondary", requirements: "start -> finish" }), /could not safely resolve that explicit function/);
  assert.throws(() => plan("Plot y = ∫x dx from −π to π"), /could not safely resolve that explicit function/);
});

test("calculus parsing preserves requested points orientation and rational bounds", () => {
  const differentiate = plan("Differentiate y = x^2 at x = 2", "tertiary");
  assert.equal(differentiate.scenes[1].data.mode, "derivative");
  assert.equal(differentiate.scenes[1].data.parameter, 2);
  const farProbe = plan("Derivative y = x^2 at x = 10", "tertiary");
  assert.equal(farProbe.scenes[1].data.parameter, 10);
  assert.ok(farProbe.scenes[1].data.domain[1] > 10);
  const reversed = plan("Integral y = x^2 from 1 to 0", "tertiary");
  assert.deepEqual(reversed.scenes[1].data.bounds, [1, 0]);
  assert.match(reversed.scenes[1].narration, /-0\.3333/);
  const rationalDomain = plan("Plot y=x^2 from 1/2 to 3/4", "tertiary");
  assert.deepEqual(rationalDomain.scenes[0].data.domain, [0.5, 0.75]);
  const rationalFunction = plan("Plot y = 3/4*x", "tertiary");
  assert.equal(rationalFunction.scenes[0].kind, "function");
});

test("numerical calculus rejects cusps poles divergence and sampling aliases", () => {
  const ast = (source) => global.MutaViz.parseExpressionV2(source);
  assert.ok(Number.isNaN(animator.numericalDerivative(ast("abs(x)"), "x", 0)));
  assert.ok(Number.isNaN(animator.numericalDerivative(ast("1/x"), "x", 0)));
  assert.ok(Math.abs(animator.numericalDerivative(ast("x^2"), "x", 2) - 4) < 1e-4);
  assert.ok(Math.abs(animator.numericalDerivative(ast("x^2"), "x", 0)) < 1e-8);
  assert.ok(Math.abs(animator.numericalDerivative(ast("sin(x)"), "x", Math.PI / 2)) < 1e-6);
  assert.ok(Math.abs(animator.numericalDerivative(ast("exp(-x^2)"), "x", 0)) < 1e-6);
  assert.ok(Number.isNaN(animator.numericalIntegral(ast("1/(x-0.123)"), "x", 0, 1)));
  assert.ok(Math.abs(animator.numericalIntegral(ast("cos(480*pi*x)"), "x", 0, 1)) < 1e-6);
});

test("function imports require expression text AST and declared variable to agree", () => {
  const project = plan("Plot y = x^3", "tertiary");
  const mismatched = structuredClone(project); mismatched.scenes[0].data.expression_text = "x^2";
  assert.match(animator.validateProject(mismatched).error, /must agree/);
  const wrongVariable = structuredClone(project); wrongVariable.scenes[0].data.variable = "t";
  assert.match(animator.validateProject(wrongVariable).error, /must agree/);
  const curveWithProbe = structuredClone(project); curveWithProbe.scenes[0].data.parameter = 1;
  assert.match(animator.validateProject(curveWithProbe).error, /do not accept calculus probes/);
  const derivativeWithBounds = plan("plot y = x^3 and show the tangent at x = 2", "tertiary");
  derivativeWithBounds.scenes[1].data.bounds = [-1, 1];
  assert.match(animator.validateProject(derivativeWithBounds).error, /Derivative probe/);
  const integralWithParameter = plan("integral y = x^2 from 0 to 1", "tertiary");
  integralWithParameter.scenes[1].data.parameter = 0.5;
  assert.match(animator.validateProject(integralWithParameter).error, /Integral bounds/);
});

test("pi ranges use concise educational labels", () => {
  assert.equal(animator.formatMathValue(-Math.PI), "−π");
  assert.equal(animator.formatMathValue(Math.PI / 2), "π/2");
  const project = plan("Plot y = sin(x) from -pi to pi");
  assert.match(project.scenes[0].narration, /−π to π/);
});

test("novel local planner response is validated before use", async () => {
  const project = plan("Photosynthesis", "secondary", "water enters -> carbon dioxide enters -> glucose forms");
  const fetchImpl = async () => ({ ok: true, json: async () => ({ project }) });
  const received = await animator.requestAnimationPlan({ topic: "Photosynthesis", level: "secondary" }, { fetchImpl, studentId: "learner" });
  assert.equal(received.kind, "lesson-animation");
  await assert.rejects(
    animator.requestAnimationPlan({ topic: "Unsafe", level: "secondary" }, { fetchImpl: async () => ({ ok: true, json: async () => ({ project: { ...project, source: "alert(1)" } }) }), studentId: "learner" }),
    /invalid project/,
  );
  await assert.rejects(
    animator.requestAnimationPlan({ topic: "Novel", level: "secondary" }, { fetchImpl: async () => ({ ok: false, json: async () => ({ detail: "Local model unavailable" }) }), studentId: "learner" }),
    /Local model unavailable/,
  );
});

test("trusted Manim source and MP4 use only the authenticated project endpoints", async () => {
  const project = plan("plot y = x^3 and show the tangent at x = 2", "tertiary");
  const requests = [];
  const fetchImpl = async (url, options) => {
    requests.push({ url, options });
    if (url.endsWith("/source")) return { ok: true, json: async () => ({ source: "from manim import *\nclass MutaLesson(Scene): pass\n", filename: "lesson.py" }) };
    return { ok: true, headers: { get: () => "video/mp4" }, blob: async () => new Blob(["video"]) };
  };
  const generated = await animator.requestManimSource(project, { fetchImpl, headers: { authorization: "Bearer local" } });
  assert.match(generated.source, /MutaLesson/);

  const originalDocument = global.document; const originalCreate = URL.createObjectURL; const originalRevoke = URL.revokeObjectURL;
  global.document = { body: { appendChild() {} }, createElement: () => ({ click() {}, remove() {} }) };
  URL.createObjectURL = () => "blob:trusted"; URL.revokeObjectURL = () => {};
  try { assert.deepEqual(await animator.exportManimVideo(project, { fetchImpl }), { bytes: 5, mime: "video/mp4" }); }
  finally { global.document = originalDocument; URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; }
  assert.deepEqual(requests.map((item) => item.url), ["/v1/animation/source", "/v1/animation/render"]);
  for (const request of requests) {
    assert.equal(request.options.method, "POST");
    assert.deepEqual(JSON.parse(request.options.body).project, project);
  }
});

test("Manim capability keeps source available while disabling only unsupported rendering", async () => {
  const unavailable = await animator.requestManimCapability({
    fetchImpl: async (url, options) => {
      assert.equal(url, "/v1/animation/render-capability");
      assert.equal(options.method, "GET");
      return { ok: true, json: async () => ({ available: false, renderer: "manim", detail: "Offline Manim rendering requires macOS 14 or later." }) };
    },
  });
  assert.deepEqual(unavailable, { available: false, renderer: "manim", detail: "Offline Manim rendering requires macOS 14 or later." });
  await assert.rejects(
    animator.requestManimCapability({ fetchImpl: async () => ({ ok: true, json: async () => ({ available: "yes", detail: "bad" }) }) }),
    /invalid Manim capability/,
  );
});

test("trusted render endpoints fail closed on invalid files and empty video", async () => {
  const project = plan("Explain 3/4", "early-primary");
  await assert.rejects(
    animator.requestManimSource(project, { fetchImpl: async () => ({ ok: true, json: async () => ({ source: "" }) }) }),
    /could not generate/,
  );
  await assert.rejects(
    animator.exportManimVideo(project, { fetchImpl: async () => ({ ok: true, headers: { get: () => "text/html" } }) }),
    /unexpected file type/,
  );
});

test("a stale same-ID Manim render is discarded before download", async () => {
  const project = plan("Explain 3/4", "early-primary");
  let current = true;
  let clicks = 0;
  const originalDocument = global.document; const originalCreate = URL.createObjectURL; const originalRevoke = URL.revokeObjectURL;
  global.document = { body: { appendChild() {} }, createElement: () => ({ click() { clicks += 1; }, remove() {} }) };
  URL.createObjectURL = () => "blob:stale"; URL.revokeObjectURL = () => {};
  try {
    const result = await animator.exportManimVideo(project, {
      isCurrent: () => current,
      fetchImpl: async () => ({
        ok: true,
        headers: { get: () => "video/mp4" },
        blob: async () => { current = false; return new Blob(["old video"]); },
      }),
    });
    assert.equal(result.discarded, true);
    assert.equal(clicks, 0);
  } finally { global.document = originalDocument; URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; }
});

test("Studio Manim rendering can return an inline MP4 blob without forced download", async () => {
  const project = plan("Explain 3/4", "early-primary");
  let clicks = 0;
  const originalDocument = global.document; const originalCreate = URL.createObjectURL; const originalRevoke = URL.revokeObjectURL;
  global.document = { body: { appendChild() {} }, createElement: () => ({ click() { clicks += 1; }, remove() {} }) };
  URL.createObjectURL = () => "blob:inline"; URL.revokeObjectURL = () => {};
  try {
    const result = await animator.exportManimVideo(project, {
      download: false,
      isCurrent: () => true,
      fetchImpl: async () => ({ ok: true, headers: { get: () => "video/mp4" }, blob: async () => new Blob(["video"]) }),
    });
    assert.ok(result.blob instanceof Blob);
    assert.equal(result.mime, "video/mp4");
    assert.equal(clicks, 0);
  } finally { global.document = originalDocument; URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; }
});

test("a stale same-ID browser export is discarded before download", () => {
  const project = plan("Explain 3/4", "early-primary");
  let clicks = 0;
  const originalDocument = global.document; const originalCreate = URL.createObjectURL; const originalRevoke = URL.revokeObjectURL;
  global.document = { body: { appendChild() {} }, createElement: () => ({ click() { clicks += 1; }, remove() {} }) };
  URL.createObjectURL = () => "blob:stale-browser-export"; URL.revokeObjectURL = () => {};
  try {
    const result = animator.deliverBrowserVideo(new Blob(["old video"]), project, { mime: "video/webm", extension: "webm" }, { isCurrent: () => false });
    assert.equal(result.discarded, true);
    assert.equal(clicks, 0);
  } finally { global.document = originalDocument; URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke; }
});

test("Manim source requests reject stale same-ID revisions and preserve edited scene order", async () => {
  const original = plan("Explain 3/4", "early-primary");
  const edited = structuredClone(original);
  edited.scenes[0].narration = "Edited narration for the same project ID.";
  [edited.scenes[0], edited.scenes[1]] = [edited.scenes[1], edited.scenes[0]];
  let resolveOld;
  let revision = 1;
  const oldFetch = async (_url, options) => {
    assert.equal(JSON.parse(options.body).project.id, original.id);
    return new Promise((resolve) => { resolveOld = () => resolve({ ok: true, json: async () => ({ source: "old source", filename: "old.py" }) }); });
  };
  const pending = animator.requestManimSourceRevision(original, 1, () => revision, { fetchImpl: oldFetch });
  await new Promise((resolve) => setImmediate(resolve));
  revision = 2;
  resolveOld();
  await assert.rejects(pending, (error) => error.name === "AbortError");

  let received;
  const generated = await animator.requestManimSourceRevision(edited, 2, () => revision, { fetchImpl: async (_url, options) => {
    received = JSON.parse(options.body).project;
    return { ok: true, json: async () => ({ source: "new source", filename: "new.py" }) };
  } });
  assert.equal(generated.source, "new source");
  assert.equal(received.id, original.id);
  assert.equal(received.scenes[0].id, original.scenes[1].id);
  assert.equal(received.scenes[1].narration, "Edited narration for the same project ID.");
});

test("strict schema rejects unknown fields, invalid dimensions, and over-budget duration", () => {
  const project = plan("Explain 3/4", "early-primary");
  assert.equal(animator.validateProject({ ...project, executable: "alert(1)" }).ok, false);
  const invalid = structuredClone(project); invalid.scenes[0].data.denominator = 0;
  assert.equal(animator.validateProject(invalid).ok, false);
  const long = structuredClone(project); long.scenes = Array.from({ length: 10 }, (_, index) => ({ ...structuredClone(project.scenes[0]), id: `long-${index}`, duration_ms: 10000 }));
  assert.equal(animator.validateProject(long).ok, false);
});

test("process-step imports reject control format and invisible-only text", () => {
  const project = plan("Photosynthesis", "secondary", "water enters -> glucose forms");
  for (const step of ["A\u0000B", "\u200b", "\u2060", "\u0301", "   "]) {
    const invalid = structuredClone(project); invalid.scenes[0].data.steps[0] = step;
    assert.equal(animator.validateProject(invalid).ok, false, JSON.stringify(step));
  }
});

test("source-shaped multilingual labels remain inert data", () => {
  const project = plan("Explain 2/5", "upper-primary");
  project.title = "<img src=x onerror=alert(1)> — ìmọ̀ ìṣirò";
  project.scenes[0].narration = "Await fetch('/x'); لكن هذا نص فقط";
  const result = animator.validateProject(project);
  assert.equal(result.ok, true);
  assert.equal(result.project.title, project.title);
  assert.equal(result.project.scenes[0].narration, project.scenes[0].narration);
});

test("saved-project roundtrip validates and keeps a bounded recent library", () => {
  storage.clear();
  const first = animator.saveProject(plan("Explain 3/4", "early-primary"));
  assert.equal(animator.loadProjects()[0].id, first.id);
  for (let index = 0; index < 11; index += 1) animator.saveProject(plan(`plot y = ${index + 1}x^2`, "secondary"));
  assert.equal(animator.loadProjects().length, 8);
  animator.removeProject(animator.loadProjects()[0].id);
  assert.equal(animator.loadProjects().length, 7);
});

test("validated clone is independent from caller mutation", () => {
  const project = plan("Build 3 x 7", "upper-primary");
  const result = animator.validateProject(project);
  project.scenes[0].data.rows = 99;
  assert.equal(result.project.scenes[0].data.rows, 3);
});

test("project descriptions expose every scene to assistive technology", () => {
  const project = plan("Explain 2/5", "upper-primary");
  const description = animator.projectDescription(project);
  project.scenes.forEach((scene) => { assert.match(description, new RegExp(scene.title)); assert.match(description, new RegExp(scene.narration.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))); });
});

test("video export detection is fail-closed when native recording is unavailable", () => {
  assert.deepEqual(animator.videoCapability(), { supported: false, reason: "This browser cannot encode a canvas video." });
});

test("production module contains no executable source sink", () => {
  const source = require("node:fs").readFileSync(require("node:path").join(__dirname, "..", "animation-studio.js"), "utf8");
  assert.doesNotMatch(source, /\beval\s*\(/);
  assert.doesNotMatch(source, /new\s+Function\s*\(/);
  assert.doesNotMatch(source, /\.innerHTML\s*=/);
  assert.doesNotMatch(source, /document\.write\s*\(/);
  assert.doesNotMatch(source, /https?:\/\//);
  assert.match(source, /renderedVideo\.controls = true/);
  assert.match(source, /renderedVideo\.playsInline = true/);
  assert.match(source, /URL\.revokeObjectURL\(this\.manimVideoUrl\)/);
  assert.match(source, /this\.exportAbort\?\.abort\(\); this\.exportAbort = null/);
  assert.match(source, /this\.exportAbort === exportAbort/);
  assert.match(source, /this\.manimCapabilityAbort\?\.abort\(\); this\.manimCapabilityAbort = null/);
  assert.match(source, /manimVideo\.disabled = !result\.available/);
  assert.match(source, /item\.setAttribute\("role", "listitem"\)/);
  assert.doesNotMatch(source, /node\.setAttribute\("role", "listitem"\)/);
  assert.doesNotMatch(source, /renderedVideo\.autoplay/);
});
