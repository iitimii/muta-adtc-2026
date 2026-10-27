(function initMutaAnimator(global) {
  "use strict";

  const VERSION = 1;
  const KIND = "lesson-animation";
  const STORAGE_KEY = "muta-lesson-animations-v1";
  const MAX_PROJECT_BYTES = 384 * 1024;
  const MAX_PROJECTS = 8;
  const MAX_SCENES = 10;
  const MIN_SCENE_MS = 900;
  const MAX_SCENE_MS = 10000;
  const MAX_TOTAL_MS = 60000;
  const LEVELS = new Set(["early-primary", "upper-primary", "secondary", "tertiary"]);
  const SCENE_KINDS = new Set(["fraction", "array", "function", "process", "vector"]);
  const PHASES = Object.freeze({
    fraction: new Set(["partition", "shade", "recap"]),
    array: new Set(["build", "addition", "equation"]),
  });
  const WORD_NUMBERS = Object.freeze({
    zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6,
    seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
  });
  const FRACTION_DENOMINATORS = Object.freeze({
    half: 2, halves: 2, third: 3, thirds: 3, quarter: 4, quarters: 4,
    fourth: 4, fourths: 4, fifth: 5, fifths: 5, sixth: 6, sixths: 6,
    eighth: 8, eighths: 8, tenth: 10, tenths: 10, twelfth: 12, twelfths: 12,
  });
  const mounted = new Set();

  const plainRecord = (value) => value !== null && typeof value === "object" && !Array.isArray(value)
    && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
  const onlyKeys = (value, keys) => plainRecord(value)
    && Object.keys(value).every((key) => keys.includes(key) && key !== "__proto__" && key !== "constructor" && key !== "prototype");
  const boundedText = (value, max, required = true) => typeof value === "string"
    && value.length <= max && (!required || value.trim().length > 0);
  const boundedVisibleText = (value, max) => boundedText(value, max)
    && !/[\p{Cc}\p{Cf}]/u.test(value) && /[\p{L}\p{N}\p{P}\p{S}]/u.test(value);
  const finite = (value, min, max) => typeof value === "number" && Number.isFinite(value) && value >= min && value <= max;
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const safeId = (value) => typeof value === "string" && /^[a-z0-9][a-z0-9-]{0,79}$/.test(value);
  const sumDuration = (scenes) => scenes.reduce((sum, scene) => sum + scene.duration_ms, 0);
  const stableValue = (value) => {
    if (Array.isArray(value)) return value.map(stableValue);
    if (!plainRecord(value)) return value;
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stableValue(value[key])]));
  };
  const sameStructure = (left, right) => JSON.stringify(stableValue(left)) === JSON.stringify(stableValue(right));
  const text = (key, variables = {}) => global.MutaI18n?.t?.(`learning.${key}`, variables) || key;
  const button = (label, className = "animation-secondary") => {
    const node = document.createElement("button");
    node.type = "button"; node.className = className; node.textContent = label;
    return node;
  };
  const field = (labelText, input) => {
    const label = document.createElement("label");
    const caption = document.createElement("span"); caption.textContent = labelText;
    label.append(caption, input); return label;
  };
  const uid = () => {
    const random = global.crypto?.getRandomValues ? global.crypto.getRandomValues(new Uint32Array(1))[0].toString(36) : Math.random().toString(36).slice(2, 10);
    return `lesson-${Date.now().toString(36)}-${random}`.slice(0, 78).replace(/[^a-z0-9-]/g, "-");
  };

  function validateScene(scene) {
    if (!onlyKeys(scene, ["id", "kind", "title", "narration", "duration_ms", "data"])) return "Scene fields are invalid.";
    if (!safeId(scene.id) || !SCENE_KINDS.has(scene.kind)) return "Scene identity or kind is invalid.";
    if (!boundedText(scene.title, 140) || !boundedText(scene.narration, 700) || !finite(scene.duration_ms, MIN_SCENE_MS, MAX_SCENE_MS)) return "Scene text or duration is invalid.";
    const data = scene.data;
    if (scene.kind === "fraction") {
      if (!onlyKeys(data, ["numerator", "denominator", "phase"]) || !Number.isInteger(data.numerator)
        || !Number.isInteger(data.denominator) || data.numerator < 0 || data.denominator < 2
        || data.numerator > data.denominator * 4 || data.denominator > 12 || !PHASES.fraction.has(data.phase)) return "Fraction scene is invalid.";
    } else if (scene.kind === "array") {
      if (!onlyKeys(data, ["rows", "columns", "phase"]) || !Number.isInteger(data.rows)
        || !Number.isInteger(data.columns) || data.rows < 1 || data.rows > 12 || data.columns < 1
        || data.columns > 12 || !PHASES.array.has(data.phase)) return "Array scene is invalid.";
    } else if (scene.kind === "function") {
      if (!onlyKeys(data, ["expression_ast", "expression_text", "domain", "variable", "output", "mode", "parameter", "bounds"])
        || !plainRecord(data.expression_ast) || typeof global.MutaViz?.validateExpressionV2 !== "function"
        || global.MutaViz.validateExpressionV2(data.expression_ast)
        || !Array.isArray(data.domain) || data.domain.length !== 2 || !data.domain.every((value) => finite(value, -1000, 1000))
        || data.domain[0] >= data.domain[1] || !["x", "t"].includes(data.variable)
        || !["y", "z", "s", "v"].includes(data.output) || !boundedText(data.expression_text, 180)
        || !["curve", "derivative", "integral"].includes(data.mode)) return "Function scene is invalid.";
      let parsedExpression;
      try { parsedExpression = global.MutaViz.parseExpressionV2(data.expression_text); } catch { return "Function expression text is invalid."; }
      if (!sameStructure(parsedExpression, data.expression_ast)
        || expressionVariables(parsedExpression).size !== 1
        || !expressionVariables(parsedExpression).has(data.variable)) return "Function expression text and typed expression must agree.";
      if (data.mode === "derivative" && (!finite(data.parameter, data.domain[0], data.domain[1]) || data.bounds != null)) return "Derivative probe is invalid.";
      if (data.mode === "integral" && (!Array.isArray(data.bounds) || data.bounds.length !== 2
        || !data.bounds.every((value) => finite(value, data.domain[0], data.domain[1])) || data.bounds[0] === data.bounds[1]
        || data.parameter != null)) return "Integral bounds are invalid.";
      if (data.mode === "curve" && (data.parameter != null || data.bounds != null)) return "Curve scenes do not accept calculus probes.";
    } else if (scene.kind === "process") {
      if (!onlyKeys(data, ["steps", "active"]) || !Array.isArray(data.steps) || data.steps.length < 2 || data.steps.length > 8
        || !data.steps.every((step) => boundedVisibleText(step, 120)) || !Number.isInteger(data.active)
        || data.active < 0 || data.active >= data.steps.length) return "Process scene is invalid.";
    } else if (scene.kind === "vector") {
      if (!onlyKeys(data, ["x", "y", "label"]) || !finite(data.x, -1000, 1000) || !finite(data.y, -1000, 1000)
        || !boundedText(data.label, 80)) return "Vector scene is invalid.";
    }
    return null;
  }

  function validateProject(project) {
    if (!onlyKeys(project, ["version", "kind", "id", "title", "topic", "level", "summary", "created_at", "updated_at", "scenes"])) return { ok: false, error: "Project fields are invalid." };
    if (project.version !== VERSION || project.kind !== KIND || !safeId(project.id)) return { ok: false, error: "Project identity is invalid." };
    if (!boundedText(project.title, 180) || !boundedText(project.topic, 240) || !LEVELS.has(project.level)
      || !boundedText(project.summary, 700) || !boundedText(project.created_at, 40) || !boundedText(project.updated_at, 40)) return { ok: false, error: "Project metadata is invalid." };
    if (!Array.isArray(project.scenes) || !project.scenes.length || project.scenes.length > MAX_SCENES) return { ok: false, error: "A project needs 1–10 scenes." };
    const ids = new Set();
    for (const scene of project.scenes) {
      const error = validateScene(scene);
      if (error) return { ok: false, error };
      if (ids.has(scene.id)) return { ok: false, error: "Scene identifiers must be unique." };
      ids.add(scene.id);
    }
    if (sumDuration(project.scenes) > MAX_TOTAL_MS) return { ok: false, error: "Project duration exceeds one minute." };
    let canonical;
    try { canonical = clone(project); } catch { return { ok: false, error: "Project cannot be copied safely." }; }
    if (new TextEncoder().encode(JSON.stringify(canonical)).length > MAX_PROJECT_BYTES) return { ok: false, error: "Project is too large." };
    return { ok: true, project: canonical };
  }

  function numberFromToken(token) {
    const value = String(token || "").toLowerCase();
    return Object.hasOwn(WORD_NUMBERS, value) ? WORD_NUMBERS[value] : Number.parseInt(value, 10);
  }

  function parseFraction(source) {
    const value = String(source || "").toLowerCase();
    let match = value.match(/\b(\d{1,2})\s*\/\s*(\d{1,2})\b/);
    if (match) return { numerator: Number(match[1]), denominator: Number(match[2]) };
    match = value.match(/\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(half|halves|thirds?|quarters?|fourths?|fifths?|sixths?|eighths?|tenths?|twelfths?)\b/);
    if (!match) return null;
    return { numerator: numberFromToken(match[1]), denominator: FRACTION_DENOMINATORS[match[2]] };
  }

  function parseArray(source) {
    const value = String(source || "").toLowerCase().replace(/[×·]/g, "x");
    let match = value.match(/\b(\d{1,2})\s*x\s*(\d{1,2})\b/);
    if (match) return { rows: Number(match[1]), columns: Number(match[2]) };
    match = value.match(/\b(\d{1,2}|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(?:groups?|rows?)\s+of\s+(\d{1,2}|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b/);
    if (!match) return null;
    return { rows: numberFromToken(match[1]), columns: numberFromToken(match[2]) };
  }

  function expressionVariables(node, output = new Set()) {
    if (node?.type === "variable") output.add(node.name);
    else if (node?.type === "unary") expressionVariables(node.arg, output);
    else if (node?.type === "binary") { expressionVariables(node.left, output); expressionVariables(node.right, output); }
    else if (node?.type === "call") node.args.forEach((argument) => expressionVariables(argument, output));
    return output;
  }

  function parseScalarExpression(source) {
    try { const ast = global.MutaViz.parseExpressionV2(source); if (expressionVariables(ast).size) return null; return global.MutaViz.evaluateExpressionV2(ast, {}); } catch { return null; }
  }

  function parseFunction(source) {
    const raw = String(source || "").replace(/[−–]/g, "-").replace(/⁰/g, "^0").replace(/¹/g, "^1").replace(/²/g, "^2").replace(/³/g, "^3").replace(/⁴/g, "^4").replace(/⁵/g, "^5");
    if (!global.MutaViz?.parseExpressionV2) return null;
    const scalar = "[+\\-]?(?:(?:\\d+(?:\\.\\d+)?(?:\\s*\\/\\s*\\d+(?:\\.\\d+)?)?)|(?:pi(?:\\s*\\/\\s*\\d+(?:\\.\\d+)?)?))";
    const rangePattern = new RegExp(`(?:from|between)\\s*(${scalar})\\s*(?:to|and)\\s*(${scalar})`, "i"); const rangeMatch = raw.match(rangePattern);
    let requestedRange = null;
    if (rangeMatch) { const start = parseScalarExpression(rangeMatch[1]); const end = parseScalarExpression(rangeMatch[2]); if (Number.isFinite(start) && Number.isFinite(end) && start !== end) requestedRange = [start, end]; }
    const equation = raw.match(/\b([yzsv])\s*=\s*([^\n;]+)/i); const naked = raw.match(/\b(?:plot|graph|trace)\s+(?:the\s+)?(?:function\s+)?([^\n;]+)/i);
    if (!equation && !naked) return null;
    const output = equation ? equation[1].toLowerCase() : "y"; let expressionText = (equation ? equation[2] : naked[1]).trim();
    expressionText = expressionText.replace(rangePattern, "").replace(/\s+(?:at|when)\s+[xt]\s*=\s*[+\-]?(?:\d+(?:\.\d+)?|pi(?:\s*\/\s*\d+(?:\.\d+)?)?)\b.*$/i, "")
      .replace(/\s+(?:with|and)\s+(?:show\s+)?(?:a\s+|the\s+)?(?:tangent|derivative|definite\s+integral|integral|area)\b.*$/i, "").trim();
    let expressionAst;
    try { expressionAst = global.MutaViz.parseExpressionV2(expressionText); } catch { return null; }
    const variables = [...expressionVariables(expressionAst)].filter((name) => ["x", "t"].includes(name));
    if (variables.length !== 1 || expressionVariables(expressionAst).size !== 1) return null;
    const variable = variables[0]; const lower = raw.toLowerCase();
    let domain = requestedRange ? [Math.min(...requestedRange), Math.max(...requestedRange)] : (/\b(?:sin|cos|tan)\s*\(/i.test(expressionText) ? [-2 * Math.PI, 2 * Math.PI]
      : /\bexp\s*\(/i.test(expressionText) ? [-4, 4] : expressionText.includes("/") ? [-6, 6]
        : /\^[3-9]/.test(expressionText) ? [-3, 3] : [-6, 6]);
    let mode = "curve"; let parameter; let bounds;
    if (/\b(?:derivative|differentiat(?:e|ed|es|ing|ion)?|tangent|gradient|rate\s+of\s+change)\b/i.test(lower)) {
      mode = "derivative"; const probe = lower.match(new RegExp(`(?:at|when)\\s+[xt]\\s*=\\s*(${scalar})`, "i")); parameter = probe ? parseScalarExpression(probe[1]) : 0;
      if (!Number.isFinite(parameter)) return null;
      const span = domain[1] - domain[0];
      if (parameter <= domain[0]) domain = [parameter - Math.max(1, span * .2), domain[1]];
      if (parameter >= domain[1]) domain = [domain[0], parameter + Math.max(1, span * .2)];
    } else if (/\b(?:definite\s+integral|integral|area\s+under)\b/i.test(lower)) {
      mode = "integral"; bounds = requestedRange ? [...requestedRange] : [Math.max(domain[0], 0), Math.min(domain[1], 1)];
      if (bounds[0] === bounds[1]) return null;
    }
    return { output, variable, expression_text: expressionText, expression_ast: expressionAst, domain, mode, ...(parameter !== undefined ? { parameter } : {}), ...(bounds ? { bounds } : {}) };
  }

  const parsePolynomial = parseFunction;

  function parseVector(source) {
    const match = String(source || "").match(/(?:vector|force|velocity|displacement)[^\d+\-]*\(?\s*([+\-]?\d+(?:\.\d+)?)\s*[,，]\s*([+\-]?\d+(?:\.\d+)?)\s*\)?/i);
    if (!match) return null;
    return { x: Number(match[1]), y: Number(match[2]), label: String(source).match(/vector|force|velocity|displacement/i)?.[0] || "vector" };
  }

  function parseProcess(requirements) {
    const raw = String(requirements || "").trim();
    if (!raw) return null;
    const explicit = raw.split(/\s*(?:→|->|=>|\n|;|\.(?=\s+[A-Z]))\s*/).map((item) => item.replace(/^\s*(?:\d+[.)]|[-•])\s*/, "").trim()).filter(Boolean);
    if (explicit.length < 2 || explicit.length > 8) return null;
    return explicit;
  }

  function makeScene(id, kind, title, narration, duration_ms, data) {
    return { id, kind, title, narration, duration_ms, data };
  }

  function levelPhrase(level) {
    return ({
      "early-primary": "Use one concrete idea at a time.",
      "upper-primary": "Connect the picture to the number sentence.",
      secondary: "Connect the representation, relationship, and result.",
      tertiary: "Connect the formal model, assumptions, and interpretation.",
    })[level];
  }

  function formatMathValue(value) {
    if (!Number.isFinite(value)) return "undefined";
    if (Math.abs(value) < 1e-10) return "0";
    for (const denominator of [1, 2, 3, 4, 6]) {
      const numerator = Math.round(value / Math.PI * denominator);
      if (numerator && Math.abs(value - numerator * Math.PI / denominator) < 1e-9) {
        const sign = numerator < 0 ? "−" : ""; const magnitude = Math.abs(numerator);
        const coefficient = magnitude === 1 ? "" : String(magnitude);
        return denominator === 1 ? `${sign}${coefficient}π` : `${sign}${coefficient}π/${denominator}`;
      }
    }
    return Number(value.toPrecision(5)).toString().replace("-", "−");
  }

  function planProject({ topic, level = "secondary", concept = "", requirements = "" }) {
    const cleanTopic = String(topic || concept || "Lesson animation").trim().slice(0, 240);
    const combined = `${topic || ""}\n${concept || ""}\n${requirements || ""}`;
    if (!cleanTopic || !LEVELS.has(level)) throw new Error("Add a topic and choose a learner level.");
    const normalizedNumeric = combined.replace(/[−–]/g, "-");
    if (/(?:^|[^\w])-\d{1,2}(?:\.\d+)?\s*(?:\/|x|×|groups?\s+of)\s*\d{1,2}(?:\.\d+)?/i.test(normalizedNumeric)
      || /\b(?:minus|negative)\s+(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(?:halves?|thirds?|quarters?|fourths?|fifths?|sixths?|eighths?|tenths?|twelfths?|groups?|rows?)/i.test(combined)) throw new Error("Signed fractions and signed array dimensions are not yet supported. Muta will not drop the negative sign; use a number-line or function lesson instead.");
    if (/\d+\.\d+\s*(?:\/|x|×)\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:\/|x|×)\s*\d+\.\d+/i.test(normalizedNumeric)) throw new Error("Decimal fractions and decimal array dimensions are not supported by these concrete models. Muta will not truncate a decimal; use a typed function lesson instead.");
    if ((normalizedNumeric.match(/\d+\s*\/\s*\d+/g) || []).length > 1 && /[+−-]/.test(normalizedNumeric.replace(/^\s*[−-]/, ""))) throw new Error("Arithmetic with multiple fractions needs a dedicated equation model. Muta will not discard an operand.");
    const unsupportedPresentation = String(requirements || "").match(/\b(?:red|blue|yellow|purple|orange|pink|colour|color|music|sound|voice[- ]?over|three[- ]dimensional|3d|rotate|rotation|\d+\s*(?:seconds?|minutes?))\b/i);
    if (unsupportedPresentation) throw new Error(`“${unsupportedPresentation[0]}” is not applied silently. Generate the semantic lesson first, then use the scene editor for timing; custom colours, audio, and 3D camera directions are not supported in this workspace yet.`);
    const fraction = parseFraction(combined);
    const array = parseArray(combined);
    const mathematicalFunction = parseFunction(combined);
    const vector = parseVector(combined);
    const process = parseProcess(requirements);
    let scenes; let summary;
    if (fraction && fraction.numerator > fraction.denominator * 4) throw new Error("This fraction needs more than four whole bars. Use an equivalent mixed number or a smaller numerator so the animation remains readable.");
    if (mathematicalFunction) {
      const relation = `${mathematicalFunction.output} = ${mathematicalFunction.expression_text}`;
      summary = `Plot ${relation} over a bounded domain using Muta's typed expression tree. ${levelPhrase(level)}`;
      const curveData = { ...mathematicalFunction, mode: "curve" }; delete curveData.parameter; delete curveData.bounds;
      scenes = [makeScene("function-shape", "function", "Trace the function", `Sample ${relation} safely from ${formatMathValue(mathematicalFunction.domain[0])} to ${formatMathValue(mathematicalFunction.domain[1])}, leaving undefined values as gaps.`, 3600, curveData)];
      if (mathematicalFunction.mode === "derivative") {
        const x0 = mathematicalFunction.parameter; const slope = numericalDerivative(mathematicalFunction.expression_ast, mathematicalFunction.variable, x0);
        if (!Number.isFinite(slope)) throw new Error(`The derivative is undefined at ${mathematicalFunction.variable} = ${x0}. Choose another point.`);
        scenes.push(makeScene("function-derivative", "function", "Follow the tangent and derivative", `At ${mathematicalFunction.variable} = ${x0}, the checked numerical slope is approximately ${slope.toFixed(4)}. The tangent shows the local rate of change.`, 4200, mathematicalFunction));
      } else if (mathematicalFunction.mode === "integral") {
        const area = numericalIntegral(mathematicalFunction.expression_ast, mathematicalFunction.variable, mathematicalFunction.bounds[0], mathematicalFunction.bounds[1]);
        if (!Number.isFinite(area)) throw new Error("The definite integral is undefined or does not converge reliably on these bounds. Choose one continuous bounded interval.");
        scenes.push(makeScene("function-integral", "function", "Accumulate signed area", `From ${mathematicalFunction.bounds[0]} to ${mathematicalFunction.bounds[1]}, the checked numerical estimate of the signed area is ${area.toFixed(4)}.`, 4400, mathematicalFunction));
      } else {
        scenes.push(makeScene("function-read", "function", "Read values and behaviour", `Use the labelled axes, domain, scale, and any visible gaps to connect input ${mathematicalFunction.variable} with output ${mathematicalFunction.output}.`, 3600, curveData));
      }
    } else if (fraction && fraction.denominator >= 2 && fraction.denominator <= 12 && fraction.numerator >= 0 && fraction.numerator <= fraction.denominator * 4) {
      const { numerator, denominator } = fraction;
      summary = `${numerator} out of every ${denominator} equal parts are selected. ${levelPhrase(level)}`;
      scenes = [
        makeScene("partition", "fraction", "Divide into equal parts", `Each whole is divided into ${denominator} equal parts.`, 2200, { numerator, denominator, phase: "partition" }),
        makeScene("shade", "fraction", `Show ${numerator}/${denominator}`, `${numerator} of those equal parts are selected.`, 2600, { numerator, denominator, phase: "shade" }),
        makeScene("fraction-recap", "fraction", "Read the fraction", `${numerator}/${denominator} means ${numerator} selected parts when each whole is split into ${denominator} equal parts.`, 2600, { numerator, denominator, phase: "recap" }),
      ];
    } else if (array && array.rows >= 1 && array.rows <= 12 && array.columns >= 1 && array.columns <= 12) {
      const { rows, columns } = array; const total = rows * columns;
      summary = `${rows} equal groups of ${columns} make ${total}. ${levelPhrase(level)}`;
      scenes = [
        makeScene("array-build", "array", `Build ${rows} groups`, `Arrange ${rows} rows with ${columns} in each row.`, 2800, { rows, columns, phase: "build" }),
        makeScene("array-add", "array", "Connect repeated addition", `${Array(rows).fill(columns).join(" + ")} = ${total}.`, 2800, { rows, columns, phase: "addition" }),
        makeScene("array-equation", "array", "Write the multiplication", `${rows} × ${columns} = ${total}.`, 2400, { rows, columns, phase: "equation" }),
      ];
    } else if (vector && Number.isFinite(vector.x) && Number.isFinite(vector.y)) {
      const magnitude = Math.hypot(vector.x, vector.y);
      summary = `The ${vector.label.toLowerCase()} has components (${vector.x}, ${vector.y}) and magnitude ${magnitude.toFixed(2)}. ${levelPhrase(level)}`;
      scenes = [
        makeScene("vector-components", "vector", "Resolve the components", `Move ${vector.x} along the horizontal axis and ${vector.y} along the vertical axis.`, 3200, vector),
        makeScene("vector-result", "vector", "Read the resultant", `The arrow joins the origin to (${vector.x}, ${vector.y}); its magnitude is ${magnitude.toFixed(2)}.`, 3200, vector),
      ];
    } else if (process) {
      summary = `A ${process.length}-stage storyboard based only on the ordered steps you supplied. ${levelPhrase(level)}`;
      scenes = process.map((step, index) => makeScene(`step-${index + 1}`, "process", `Stage ${index + 1}`, step, 2400, { steps: process, active: index }));
    } else {
      const error = new Error("Muta needs a bounded visual relationship: enter a fraction, multiplication array, typed one-variable function such as y = sin(x) or plot sin(x), 2D vector, or two or more ordered steps joined by arrows or new lines.");
      error.code = "planner_required"; throw error;
    }
    const now = new Date().toISOString();
    const project = {
      version: VERSION, kind: KIND, id: uid(), title: cleanTopic.slice(0, 180), topic: cleanTopic,
      level, summary, created_at: now, updated_at: now, scenes,
    };
    const result = validateProject(project);
    if (!result.ok) throw new Error(result.error);
    return result.project;
  }

  async function requestAnimationPlan(values, options = {}) {
    const fetchImpl = options.fetchImpl || global.fetch; const studentId = options.studentId || global.MutaChat?.studentId;
    if (typeof fetchImpl !== "function" || !studentId) throw new Error("The local planner is not ready. Wait for Muta to finish starting, then try again.");
    const response = await fetchImpl("/v1/animation/plan", {
      method: "POST", signal: options.signal,
      headers: { "content-type": "application/json", ...(options.headers || global.MutaChat?.authHeaders?.() || {}) },
      body: JSON.stringify({ student_id: studentId, topic: String(values.topic || "").trim(), level: values.level, concept: String(values.concept || "").trim(), requirements: String(values.requirements || "").trim() }),
    });
    let payload = null; try { payload = await response.json(); } catch { /* response has no JSON body */ }
    if (!response.ok) throw new Error(payload?.detail || "The local tutor could not create a valid animation plan. Edit the brief and try again.");
    const result = validateProject(payload?.project); if (!result.ok) throw new Error(`The local tutor returned an invalid project: ${result.error}`);
    return result.project;
  }

  function requestHeaders(options = {}) {
    return { "content-type": "application/json", ...(options.headers || global.MutaChat?.authHeaders?.() || {}) };
  }

  async function requestManimSource(project, options = {}) {
    const validated = validateProject(project); if (!validated.ok) throw new Error(validated.error);
    const fetchImpl = options.fetchImpl || global.fetch;
    if (typeof fetchImpl !== "function") throw new Error("The trusted scene-code service is not ready.");
    const response = await fetchImpl("/v1/animation/source", {
      method: "POST", signal: options.signal, headers: requestHeaders(options),
      body: JSON.stringify({ project: validated.project }),
    });
    let payload = null; try { payload = await response.json(); } catch { /* handled below */ }
    if (!response.ok || typeof payload?.source !== "string" || !payload.source.trim()) throw new Error(payload?.detail || "Muta could not generate trusted Manim scene code.");
    return { source: payload.source, filename: payload.filename || `${validated.project.id}-manim.py` };
  }

  async function requestManimCapability(options = {}) {
    const fetchImpl = options.fetchImpl || global.fetch;
    if (typeof fetchImpl !== "function") throw new Error("The offline Manim renderer is not ready.");
    const response = await fetchImpl("/v1/animation/render-capability", {
      method: "GET", signal: options.signal, headers: requestHeaders(options),
    });
    if (!response.ok) throw new Error("Muta could not check the offline Manim renderer.");
    const payload = await response.json();
    if (typeof payload?.available !== "boolean" || typeof payload?.detail !== "string" || !payload.detail.trim()) throw new Error("Muta received an invalid Manim capability response.");
    return { available: payload.available, detail: payload.detail, renderer: "manim" };
  }

  async function requestManimSourceRevision(project, revision, currentRevision, options = {}) {
    const generated = await requestManimSource(project, options);
    if (currentRevision() !== revision) {
      const error = new Error("The animation project changed while its Manim source was generated.");
      error.name = "AbortError";
      throw error;
    }
    return generated;
  }

  async function downloadManimSource(project, options = {}) {
    const generated = options.generated || await requestManimSource(project, options);
    downloadBlob(new Blob([generated.source], { type: "text/x-python;charset=utf-8" }), generated.filename);
    return generated;
  }

  async function exportManimVideo(project, options = {}) {
    const validated = validateProject(project); if (!validated.ok) throw new Error(validated.error);
    const fetchImpl = options.fetchImpl || global.fetch;
    if (typeof fetchImpl !== "function") throw new Error("The offline Manim renderer is not ready.");
    const response = await fetchImpl("/v1/animation/render", {
      method: "POST", signal: options.signal, headers: requestHeaders(options),
      body: JSON.stringify({ project: validated.project }),
    });
    if (!response.ok) {
      let payload = null; try { payload = await response.json(); } catch { /* use fallback */ }
      throw new Error(payload?.detail || "Muta could not render the Manim video.");
    }
    const mime = String(response.headers?.get?.("content-type") || "").split(";", 1)[0];
    if (mime !== "video/mp4") throw new Error("The offline renderer returned an unexpected file type.");
    const blob = await response.blob();
    if (!blob.size) throw new Error("The offline renderer returned an empty video.");
    if (typeof options.isCurrent === "function" && !options.isCurrent()) return { bytes: blob.size, mime, discarded: true };
    if (options.download === false) return { bytes: blob.size, mime, blob };
    downloadBlob(blob, `${validated.project.id}-manim.mp4`);
    return { bytes: blob.size, mime };
  }

  function expressionValue(expressionAst, variable, input) {
    try { return global.MutaViz.evaluateExpressionV2(expressionAst, { x: 0, y: 0, z: 0, t: 0, u: 0, v: 0, [variable]: input }); } catch { return null; }
  }

  function numericalDerivative(expressionAst, variable, input) {
    const centre = expressionValue(expressionAst, variable, input);
    if (centre === null) return NaN;
    const scale = Math.max(1, Math.abs(input)); const estimates = [];
    for (const ratio of [1e-2, 5e-3, 2.5e-3, 1.25e-3, 6.25e-4]) {
      const step = scale * ratio; const left = expressionValue(expressionAst, variable, input - step); const right = expressionValue(expressionAst, variable, input + step);
      if (left === null || right === null) return NaN;
      const leftSlope = (centre - left) / step; const rightSlope = (right - centre) / step; const central = (right - left) / (2 * step);
      if (![leftSlope, rightSlope, central].every(Number.isFinite)) return NaN;
      const agreement = Math.abs(leftSlope - rightSlope); const tolerance = Math.max(1e-4, Math.abs(central) * .01);
      estimates.push({ central, agreement, tolerance });
    }
    const recent = estimates.slice(-3);
    const agreementConverges = recent.at(-1).agreement <= recent.at(-1).tolerance
      || recent.at(-1).agreement <= recent[0].agreement * .35;
    if (!agreementConverges) return NaN;
    const spread = Math.max(...recent.map((item) => item.central)) - Math.min(...recent.map((item) => item.central));
    const estimate = recent.at(-1).central;
    return spread <= Math.max(1e-4, Math.abs(estimate) * .005) ? estimate : NaN;
  }

  function numericalIntegral(expressionAst, variable, start, end) {
    if (!Number.isFinite(start) || !Number.isFinite(end) || start === end) return NaN;
    const integrate = (intervals) => {
      const width = (end - start) / intervals; let total = 0; let previous = expressionValue(expressionAst, variable, start);
      if (previous === null || Math.abs(previous) > 1e10) return NaN;
      for (let index = 1; index <= intervals; index += 1) {
        const current = expressionValue(expressionAst, variable, start + index * width);
        if (current === null || Math.abs(current) > 1e10) return NaN;
        total += (previous + current) * width / 2; previous = current;
      }
      return total;
    };
    const estimates = [211, 307, 463, 701].map(integrate);
    if (!estimates.every(Number.isFinite)) return NaN;
    const recent = estimates.slice(-3); const estimate = recent.at(-1);
    const spread = Math.max(...recent) - Math.min(...recent);
    return spread <= Math.max(2e-4, Math.abs(estimate) * 2e-4) ? estimate : NaN;
  }

  function polynomialValue(coefficients, x) {
    return coefficients.reduceRight((value, coefficient) => value * x + coefficient, 0);
  }

  function projectDescription(project) {
    return `${project.title}. ${project.summary} ${project.scenes.map((scene, index) => `Scene ${index + 1}: ${scene.title}. ${scene.narration}`).join(" ")}`;
  }

  function loadProjects() {
    try {
      const parsed = JSON.parse(global.localStorage?.getItem(STORAGE_KEY) || "[]");
      if (!Array.isArray(parsed)) return [];
      return parsed.map((item) => validateProject(item)).filter((item) => item.ok).map((item) => item.project).slice(0, MAX_PROJECTS);
    } catch { return []; }
  }

  function saveProject(project) {
    const result = validateProject(project);
    if (!result.ok) throw new Error(result.error);
    const clean = result.project;
    const projects = loadProjects().filter((item) => item.id !== clean.id);
    projects.unshift(clean);
    const encoded = JSON.stringify(projects.slice(0, MAX_PROJECTS));
    if (new TextEncoder().encode(encoded).length > MAX_PROJECT_BYTES) throw new Error("Saved animation library is full. Export or remove an older project first.");
    global.localStorage?.setItem(STORAGE_KEY, encoded);
    global.dispatchEvent?.(new CustomEvent("muta:animation-projects", { detail: { id: clean.id } }));
    return clean;
  }

  function removeProject(id) {
    const projects = loadProjects().filter((item) => item.id !== id);
    global.localStorage?.setItem(STORAGE_KEY, JSON.stringify(projects));
    global.dispatchEvent?.(new CustomEvent("muta:animation-projects", { detail: { id } }));
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = filename; link.click();
    global.setTimeout(() => URL.revokeObjectURL(url), 1200);
  }

  function exportProject(project) {
    const result = validateProject(project); if (!result.ok) throw new Error(result.error);
    downloadBlob(new Blob([`${JSON.stringify(result.project, null, 2)}\n`], { type: "application/vnd.muta.animation+json" }), `${result.project.id}.mutaanim`);
  }

  function exportTranscript(project) {
    const result = validateProject(project); if (!result.ok) throw new Error(result.error);
    const lines = [result.project.title, result.project.summary, "", ...result.project.scenes.flatMap((scene, index) => [`${index + 1}. ${scene.title}`, scene.narration, ""])];
    downloadBlob(new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" }), `${result.project.id}-transcript.txt`);
  }

  function videoCapability() {
    if (!global.MediaRecorder || !global.HTMLCanvasElement?.prototype?.captureStream) return { supported: false, reason: "This browser cannot encode a canvas video." };
    const userAgent = global.navigator?.userAgent || ""; const webKit = /AppleWebKit/i.test(userAgent) && !/(?:Chrome|Chromium|Edg|OPR)/i.test(userAgent);
    const mp4 = ["video/mp4;codecs=avc1.42E01E", "video/mp4;codecs=h264", "video/mp4"]; const webm = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"];
    const candidates = webKit ? [...mp4, ...webm] : [...webm, ...mp4];
    const mime = candidates.find((value) => !global.MediaRecorder.isTypeSupported || global.MediaRecorder.isTypeSupported(value));
    return mime ? { supported: true, mime, extension: mime.includes("mp4") ? "mp4" : "webm" } : { supported: false, reason: "No playable offline video encoder is available in this browser." };
  }

  function canvasPalette(canvas) {
    const style = global.getComputedStyle?.(canvas) || { getPropertyValue: () => "" };
    const value = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
    return { bg: value("--card", "#fffdf8"), ink: value("--text", "#24231f"), muted: value("--muted", "#716f68"), accent: value("--accent-strong", "#187b63"), soft: value("--accent-soft", "#dff4ec"), border: value("--border", "#d8d5cc"), danger: value("--danger", "#a33838") };
  }

  function roundedRect(ctx, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2); ctx.beginPath();
    ctx.roundRect ? ctx.roundRect(x, y, width, height, r) : ctx.rect(x, y, width, height);
  }

  function fitCanvas(canvas, cssWidth, cssHeight) {
    const ratio = Math.min(2, Math.max(1, global.devicePixelRatio || 1));
    canvas.width = Math.max(1, Math.round(cssWidth * ratio)); canvas.height = Math.max(1, Math.round(cssHeight * ratio));
    canvas.style.width = `${cssWidth}px`; canvas.style.height = `${cssHeight}px`;
    const ctx = canvas.getContext("2d"); ctx.setTransform(ratio, 0, 0, ratio, 0, 0); return ctx;
  }

  function wrapText(ctx, value, maxWidth, maxLines = 3) {
    const words = String(value).split(/\s+/); const lines = []; let line = "";
    for (const word of words) {
      const candidate = line ? `${line} ${word}` : word;
      if (ctx.measureText(candidate).width > maxWidth && line) { lines.push(line); line = word; } else line = candidate;
      if (lines.length === maxLines - 1) break;
    }
    if (line && lines.length < maxLines) lines.push(line);
    if (lines.join(" ").length < String(value).length && lines.length) lines[lines.length - 1] = `${lines[lines.length - 1].replace(/[.…]+$/, "")}…`;
    return lines;
  }

  function drawFraction(ctx, scene, width, height, progress, palette) {
    const { numerator, denominator, phase } = scene.data; const wholes = Math.max(1, Math.ceil(numerator / denominator));
    const gap = 12; const areaWidth = Math.min(width - 72, 680); const barHeight = Math.min(104, Math.max(24, (height - 180 - (wholes - 1) * gap) / wholes));
    const x = (width - areaWidth) / 2; const startY = 96 + Math.max(0, (height - 190 - wholes * barHeight - (wholes - 1) * gap) / 2);
    const visibleParts = phase === "partition" ? Math.max(1, Math.ceil(denominator * progress)) : denominator;
    const selected = phase === "partition" ? 0 : Math.ceil(numerator * progress);
    for (let whole = 0; whole < wholes; whole += 1) {
      const y = startY + whole * (barHeight + gap); const cell = areaWidth / denominator;
      for (let part = 0; part < visibleParts; part += 1) {
        const index = whole * denominator + part; roundedRect(ctx, x + part * cell + 2, y, Math.max(2, cell - 4), barHeight, 8);
        ctx.fillStyle = index < selected ? palette.accent : palette.soft; ctx.fill(); ctx.strokeStyle = palette.border; ctx.lineWidth = 2; ctx.stroke();
      }
    }
    if (phase === "recap") { ctx.fillStyle = palette.ink; ctx.font = "700 34px Onest, sans-serif"; ctx.textAlign = "center"; ctx.fillText(`${numerator}/${denominator}`, width / 2, height - 46); }
  }

  function drawArray(ctx, scene, width, height, progress, palette) {
    const { rows, columns, phase } = scene.data; const total = rows * columns; const visible = phase === "build" ? Math.max(1, Math.ceil(total * progress)) : total;
    const availableW = Math.min(width - 80, 640); const availableH = Math.min(height - 190, 330); const step = Math.min(58, availableW / columns, availableH / rows); const radius = Math.max(5, Math.min(15, step * .24));
    const startX = width / 2 - ((columns - 1) * step) / 2; const startY = 100 + (availableH - (rows - 1) * step) / 2;
    for (let index = 0; index < visible; index += 1) {
      const row = Math.floor(index / columns); const column = index % columns;
      ctx.beginPath(); ctx.arc(startX + column * step, startY + row * step, radius, 0, Math.PI * 2); ctx.fillStyle = palette.accent; ctx.fill();
    }
    if (phase !== "build") {
      ctx.fillStyle = palette.ink; ctx.textAlign = "center"; ctx.font = `700 ${width < 500 ? 18 : 25}px Onest, sans-serif`;
      const equation = phase === "addition" ? `${Array(rows).fill(columns).join(" + ")} = ${total}` : `${rows} × ${columns} = ${total}`;
      ctx.fillText(equation, width / 2, height - 42, width - 40);
    }
  }

  function drawFunction(ctx, scene, width, height, progress, palette) {
    const { expression_ast: expressionAst, expression_text: expressionText, domain, variable, output, mode, parameter, bounds } = scene.data; const left = 64; const right = width - 30; const top = 86; const bottom = height - 60;
    const samples = 240; const values = Array.from({ length: samples + 1 }, (_, index) => { const x = domain[0] + (domain[1] - domain[0]) * index / samples; return [x, expressionValue(expressionAst, variable, x)]; });
    const finiteAbs = values.filter(([, y]) => y !== null).map(([, y]) => Math.abs(y)).sort((a, b) => a - b); const robust = finiteAbs[Math.floor(finiteAbs.length * .92)] || 1; const limit = Math.max(1, Math.pow(10, Math.ceil(Math.log10(robust))));
    const xScale = (x) => left + (x - domain[0]) / (domain[1] - domain[0]) * (right - left);
    const yScale = (y) => bottom - (y + limit) / (2 * limit) * (bottom - top);
    ctx.strokeStyle = palette.border; ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i += 1) { const y = top + (bottom - top) * i / 4; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke(); }
    ctx.strokeStyle = palette.muted; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(left, yScale(0)); ctx.lineTo(right, yScale(0)); ctx.moveTo(xScale(0), top); ctx.lineTo(xScale(0), bottom); ctx.stroke();
    if (mode === "integral") {
      const visibleEnd = bounds[0] + (bounds[1] - bounds[0]) * progress; const low = Math.min(bounds[0], visibleEnd); const high = Math.max(bounds[0], visibleEnd); const included = values.filter(([x, y]) => x >= low && x <= high && y !== null && Math.abs(y) <= limit * 1.3);
      if (included.length > 1) { ctx.fillStyle = palette.soft; ctx.beginPath(); ctx.moveTo(xScale(included[0][0]), yScale(0)); included.forEach(([x, y]) => ctx.lineTo(xScale(x), yScale(y))); ctx.lineTo(xScale(included.at(-1)[0]), yScale(0)); ctx.closePath(); ctx.fill(); }
    }
    ctx.strokeStyle = palette.accent; ctx.lineWidth = 4; ctx.lineJoin = "round"; ctx.beginPath(); let drawing = false;
    const count = Math.max(2, Math.ceil(samples * progress)); values.slice(0, count).forEach(([x, y]) => { if (y === null || Math.abs(y) > limit * 1.3) { drawing = false; return; } const px = xScale(x); const py = yScale(y); if (drawing) ctx.lineTo(px, py); else { ctx.moveTo(px, py); drawing = true; } }); ctx.stroke();
    if (mode === "derivative") {
      const y0 = expressionValue(expressionAst, variable, parameter); const slope = numericalDerivative(expressionAst, variable, parameter);
      if (y0 !== null && Number.isFinite(slope)) { const span = (domain[1] - domain[0]) * .18 * progress; const start = Math.max(domain[0], parameter - span); const end = Math.min(domain[1], parameter + span); ctx.strokeStyle = palette.danger; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(xScale(start), yScale(y0 + slope * (start - parameter))); ctx.lineTo(xScale(end), yScale(y0 + slope * (end - parameter))); ctx.stroke(); ctx.fillStyle = palette.danger; ctx.beginPath(); ctx.arc(xScale(parameter), yScale(y0), 6, 0, Math.PI * 2); ctx.fill(); }
    }
    ctx.fillStyle = palette.muted; ctx.font = "600 12px Onest, sans-serif"; ctx.textAlign = "center"; ctx.fillText(`${variable}: ${formatMathValue(domain[0])} to ${formatMathValue(domain[1])}`, (left + right) / 2, height - 24);
    ctx.save(); ctx.translate(18, (top + bottom) / 2); ctx.rotate(-Math.PI / 2); ctx.fillText(`${output}: −${limit} to ${limit}`, 0, 0); ctx.restore();
    ctx.fillStyle = palette.ink; ctx.textAlign = "right"; ctx.font = "700 15px Onest, sans-serif"; ctx.fillText(`${output} = ${expressionText}`, right, 54);
  }

  function drawProcess(ctx, scene, width, height, progress, palette) {
    const { steps, active } = scene.data; const horizontal = width >= 620; const pad = 42; const gap = 18; const pageSize = horizontal ? 3 : 3;
    const start = Math.max(0, Math.min(steps.length - pageSize, active - 1)); const visibleSteps = steps.slice(start, start + pageSize);
    const boxW = horizontal ? Math.min(210, (width - pad * 2 - gap * (visibleSteps.length - 1)) / visibleSteps.length) : Math.min(width - 64, 420);
    const boxH = horizontal ? 116 : Math.max(72, Math.min(96, (height - 164 - gap * (visibleSteps.length - 1)) / visibleSteps.length));
    visibleSteps.forEach((step, localIndex) => {
      const index = start + localIndex; const x = horizontal ? pad + localIndex * (boxW + gap) : (width - boxW) / 2; const y = horizontal ? (height - boxH) / 2 : 82 + localIndex * (boxH + gap);
      roundedRect(ctx, x, y, boxW, boxH, 12); ctx.fillStyle = index < active || (index === active && progress > .3) ? palette.soft : palette.bg; ctx.fill(); ctx.strokeStyle = index === active ? palette.accent : palette.border; ctx.lineWidth = index === active ? 3 : 1.5; ctx.stroke();
      ctx.fillStyle = palette.ink; ctx.textAlign = "center"; ctx.font = "650 13px Onest, sans-serif"; const lines = wrapText(ctx, step, boxW - 18, 3); lines.forEach((line, lineIndex) => ctx.fillText(line, x + boxW / 2, y + boxH / 2 + (lineIndex - (lines.length - 1) / 2) * 17 + 5));
      if (localIndex < visibleSteps.length - 1) { ctx.strokeStyle = palette.muted; ctx.lineWidth = 2; ctx.beginPath(); if (horizontal) { ctx.moveTo(x + boxW + 3, y + boxH / 2); ctx.lineTo(x + boxW + gap - 3, y + boxH / 2); } else { ctx.moveTo(x + boxW / 2, y + boxH + 3); ctx.lineTo(x + boxW / 2, y + boxH + gap - 3); } ctx.stroke(); }
    });
    ctx.fillStyle = palette.muted; ctx.font = "600 12px Onest, sans-serif"; ctx.textAlign = "right"; ctx.fillText(`Steps ${start + 1}–${start + visibleSteps.length} of ${steps.length}`, width - 24, height - 22);
  }

  function drawVector(ctx, scene, width, height, progress, palette) {
    const { x, y, label } = scene.data; const cx = width / 2; const cy = height / 2 + 24; const max = Math.max(1, Math.abs(x), Math.abs(y)); const scale = Math.min(width * .34, height * .34) / max;
    ctx.strokeStyle = palette.border; ctx.lineWidth = 1; for (let index = -4; index <= 4; index += 1) { const px = cx + index * Math.min(width, height) / 10; const py = cy + index * Math.min(width, height) / 10; ctx.beginPath(); ctx.moveTo(px, 70); ctx.lineTo(px, height - 40); ctx.stroke(); ctx.beginPath(); ctx.moveTo(35, py); ctx.lineTo(width - 35, py); ctx.stroke(); }
    ctx.strokeStyle = palette.muted; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(35, cy); ctx.lineTo(width - 35, cy); ctx.moveTo(cx, 70); ctx.lineTo(cx, height - 40); ctx.stroke();
    const tx = cx + x * scale * progress; const ty = cy - y * scale * progress; ctx.strokeStyle = palette.accent; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(tx, ty); ctx.stroke();
    const angle = Math.atan2(ty - cy, tx - cx); ctx.fillStyle = palette.accent; ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(tx - 15 * Math.cos(angle - .45), ty - 15 * Math.sin(angle - .45)); ctx.lineTo(tx - 15 * Math.cos(angle + .45), ty - 15 * Math.sin(angle + .45)); ctx.closePath(); ctx.fill();
    ctx.fillStyle = palette.ink; ctx.font = "700 15px Onest, sans-serif"; ctx.textAlign = "left"; ctx.fillText(`${label} (${x}, ${y})`, Math.min(width - 160, tx + 10), Math.max(84, ty - 8));
  }

  function drawFrame(canvas, project, sceneIndex, progress = 1, forcedSize = null) {
    const rect = canvas.getBoundingClientRect?.() || { width: 800, height: 450 };
    const width = forcedSize?.width || Math.max(280, Math.round(rect.width || 800)); const height = forcedSize?.height || Math.max(280, Math.round(rect.height || 450));
    const ctx = fitCanvas(canvas, width, height); const palette = canvasPalette(canvas); const scene = project.scenes[Math.max(0, Math.min(project.scenes.length - 1, sceneIndex))];
    ctx.clearRect(0, 0, width, height); ctx.fillStyle = palette.bg; ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = palette.ink; ctx.font = `700 ${width < 480 ? 18 : 22}px Onest, sans-serif`; ctx.textAlign = "left"; ctx.fillText(scene.title, 28, 38, width - 56);
    const p = Math.max(0, Math.min(1, progress));
    if (scene.kind === "fraction") drawFraction(ctx, scene, width, height, p, palette);
    else if (scene.kind === "array") drawArray(ctx, scene, width, height, p, palette);
    else if (scene.kind === "function") drawFunction(ctx, scene, width, height, p, palette);
    else if (scene.kind === "process") drawProcess(ctx, scene, width, height, p, palette);
    else if (scene.kind === "vector") drawVector(ctx, scene, width, height, p, palette);
    return { width, height, scene };
  }

  function drawExportCaption(canvas, scene, width, height) {
    const ctx = canvas.getContext("2d"); const palette = canvasPalette(canvas); const boxHeight = 94;
    ctx.fillStyle = "rgba(0,0,0,.76)"; ctx.fillRect(0, height - boxHeight, width, boxHeight);
    ctx.fillStyle = "#ffffff"; ctx.textAlign = "left"; ctx.font = "700 18px Onest, sans-serif"; ctx.fillText(scene.title, 28, height - 58, width - 56);
    ctx.font = "500 15px Onest, sans-serif"; const lines = wrapText(ctx, scene.narration, width - 56, 2);
    lines.forEach((line, index) => ctx.fillText(line, 28, height - 31 + index * 19, width - 56));
    ctx.fillStyle = palette.accent; ctx.fillRect(0, height - boxHeight, 6, boxHeight);
  }

  class Player {
    constructor(root, project, options = {}) {
      const result = validateProject(project); if (!result.ok) throw new Error(result.error);
      this.root = root; this.project = result.project; this.options = options; this.index = 0; this.elapsed = 0; this.poster = true; this.speed = 1; this.playing = false; this.raf = 0; this.lastTime = 0; this.visible = true; this.destroyed = false; this.exportStream = null; this.build(); mounted.add(this);
    }
    build() {
      this.root.replaceChildren(); this.root.classList.add("animation-player"); this.root.dataset.animationMount = "true";
      const header = document.createElement("header"); header.className = "animation-preview-header";
      const copy = document.createElement("div"); const kicker = document.createElement("span"); kicker.textContent = text("animationPreview");
      this.title = document.createElement("h4"); this.title.textContent = this.project.title; copy.append(kicker, this.title);
      const count = document.createElement("span"); count.className = "animation-scene-count"; count.textContent = text("animationSceneCount", { count: this.project.scenes.length }); header.append(copy, count);
      const stage = document.createElement("div"); stage.className = "animation-stage";
      this.canvas = document.createElement("canvas"); this.canvas.setAttribute("role", "img"); this.canvas.setAttribute("aria-label", projectDescription(this.project)); this.canvas.tabIndex = 0;
      this.caption = document.createElement("p"); this.caption.className = "animation-caption"; this.caption.setAttribute("aria-live", "polite"); stage.append(this.canvas, this.caption);
      this.timeline = document.createElement("div"); this.timeline.className = "animation-timeline"; this.timeline.setAttribute("role", "list");
      this.controls = document.createElement("div"); this.controls.className = "animation-controls";
      this.restart = button(text("animationRestart")); this.restart.setAttribute("aria-label", text("animationRestart"));
      this.previous = button(text("animationPrevious")); this.previous.setAttribute("aria-label", text("animationPrevious"));
      this.play = button(text("animationPlay"), "animation-primary"); this.play.setAttribute("aria-label", text("animationPlay")); this.play.setAttribute("aria-pressed", "false");
      this.next = button(text("animationNext")); this.next.setAttribute("aria-label", text("animationNext"));
      this.seek = document.createElement("input"); this.seek.type = "range"; this.seek.min = "0"; this.seek.max = String(sumDuration(this.project.scenes)); this.seek.step = "50"; this.seek.value = "0"; this.seek.setAttribute("aria-label", text("animationSeek"));
      this.speedSelect = document.createElement("select"); this.speedSelect.setAttribute("aria-label", text("animationSpeed"));
      [["0.5", "0.5×"], ["1", "1×"], ["1.5", "1.5×"], ["2", "2×"]].forEach(([value, label]) => { const option = document.createElement("option"); option.value = value; option.textContent = label; if (value === "1") option.selected = true; this.speedSelect.append(option); });
      this.controls.append(this.restart, this.previous, this.play, this.next, this.seek, this.speedSelect);
      this.transcript = document.createElement("details"); this.transcript.className = "animation-transcript"; const summary = document.createElement("summary"); summary.textContent = text("animationTranscript"); const list = document.createElement("ol"); this.project.scenes.forEach((scene) => { const item = document.createElement("li"); const strong = document.createElement("strong"); strong.textContent = scene.title; item.append(strong, document.createTextNode(` — ${scene.narration}`)); list.append(item); }); this.transcript.append(summary, list);
      this.root.append(header, stage, this.timeline, this.controls, this.transcript); this.bind(); this.renderTimeline(); this.resize(); this.render();
    }
    bind() {
      this.onPlay = () => this.toggle(); this.onRestart = () => this.restartPlayback(); this.onPrevious = () => this.goTo(Math.max(0, this.index - 1)); this.onNext = () => this.goTo(Math.min(this.project.scenes.length - 1, this.index + 1));
      this.onSeek = () => this.seekTo(Number(this.seek.value)); this.onSpeed = () => { this.speed = Number(this.speedSelect.value) || 1; };
      this.onKey = (event) => { if (event.target.matches("input, select, textarea, button")) return; if (event.key === " ") { event.preventDefault(); this.toggle(); } else if (event.key === "ArrowRight") { event.preventDefault(); this.onNext(); } else if (event.key === "ArrowLeft") { event.preventDefault(); this.onPrevious(); } else if (event.key === "Home") { event.preventDefault(); this.restartPlayback(); } };
      this.play.addEventListener("click", this.onPlay); this.restart.addEventListener("click", this.onRestart); this.previous.addEventListener("click", this.onPrevious); this.next.addEventListener("click", this.onNext); this.seek.addEventListener("input", this.onSeek); this.speedSelect.addEventListener("change", this.onSpeed); this.canvas.addEventListener("keydown", this.onKey);
      this.resizeObserver = global.ResizeObserver ? new ResizeObserver(() => this.resize()) : null; this.resizeObserver?.observe(this.root);
      this.intersectionObserver = global.IntersectionObserver ? new IntersectionObserver((entries) => { this.visible = entries[0]?.isIntersecting !== false; if (!this.visible) this.pause(); }, { threshold: .05 }) : null; this.intersectionObserver?.observe(this.root);
      this.visibility = () => { if (document.visibilityState !== "visible") this.pause(); }; document.addEventListener("visibilitychange", this.visibility);
    }
    resize() { const width = Math.max(280, Math.floor(this.root.getBoundingClientRect().width - 2)); const height = Math.max(300, Math.min(540, Math.round(width * .58))); this.canvas.parentElement.style.setProperty("--animation-height", `${height}px`); this.canvas.style.height = `${height}px`; this.render(); }
    renderTimeline() { this.timeline.replaceChildren(); this.project.scenes.forEach((scene, index) => { const item = document.createElement("div"); item.className = "animation-timeline-item"; item.setAttribute("role", "listitem"); const node = button(`${index + 1}. ${scene.title}`, "animation-timeline-step"); node.dataset.active = String(index === this.index); node.setAttribute("aria-current", index === this.index ? "step" : "false"); node.addEventListener("click", () => this.goTo(index)); item.append(node); this.timeline.append(item); }); }
    render() { const scene = this.project.scenes[this.index]; const progress = this.poster ? 1 : (scene.duration_ms ? this.elapsed / scene.duration_ms : 1); drawFrame(this.canvas, this.project, this.index, progress); this.caption.textContent = scene.narration; this.previous.disabled = this.index === 0; this.next.disabled = this.index === this.project.scenes.length - 1; this.updateSeek(); }
    updateSeek() { const prior = this.project.scenes.slice(0, this.index).reduce((sum, scene) => sum + scene.duration_ms, 0); this.seek.value = String(Math.min(Number(this.seek.max), prior + this.elapsed)); }
    toggle() { if (this.playing) this.pause(); else this.start(); }
    start() { if (this.playing || this.destroyed || !this.visible || document.visibilityState === "hidden") return; this.poster = false; if (global.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { this.elapsed = this.project.scenes[this.index].duration_ms; this.render(); return; } this.elapsed = Math.min(this.elapsed, this.project.scenes[this.index].duration_ms); this.playing = true; this.play.textContent = text("animationPause"); this.play.setAttribute("aria-label", text("animationPause")); this.play.setAttribute("aria-pressed", "true"); this.lastTime = performance.now(); this.raf = requestAnimationFrame((time) => this.tick(time)); }
    pause() { this.playing = false; cancelAnimationFrame(this.raf); this.raf = 0; if (this.play) { this.play.textContent = text("animationPlay"); this.play.setAttribute("aria-label", text("animationPlay")); this.play.setAttribute("aria-pressed", "false"); } }
    tick(time) { if (!this.playing || this.destroyed) return; const delta = Math.min(100, time - this.lastTime) * this.speed; this.lastTime = time; this.elapsed += delta; const duration = this.project.scenes[this.index].duration_ms; if (this.elapsed >= duration) { if (this.index < this.project.scenes.length - 1) { this.index += 1; this.elapsed = 0; this.renderTimeline(); } else { this.elapsed = duration; this.pause(); } } this.render(); if (this.playing) this.raf = requestAnimationFrame((next) => this.tick(next)); }
    restartPlayback() { this.pause(); this.index = 0; this.elapsed = 0; this.poster = false; this.renderTimeline(); this.render(); }
    goTo(index) { this.pause(); this.index = index; this.elapsed = 0; this.poster = true; this.renderTimeline(); this.render(); }
    seekTo(ms) { this.pause(); this.poster = false; let remaining = Math.max(0, Math.min(sumDuration(this.project.scenes), ms)); let index = 0; while (index < this.project.scenes.length - 1 && remaining > this.project.scenes[index].duration_ms) { remaining -= this.project.scenes[index].duration_ms; index += 1; } this.index = index; this.elapsed = Math.min(remaining, this.project.scenes[index].duration_ms); this.renderTimeline(); this.render(); }
    updateProject(project) { const result = validateProject(project); if (!result.ok) throw new Error(result.error); this.project = result.project; this.title.textContent = this.project.title; this.canvas.setAttribute("aria-label", projectDescription(this.project)); this.index = Math.min(this.index, this.project.scenes.length - 1); this.elapsed = 0; this.poster = true; this.seek.max = String(sumDuration(this.project.scenes)); this.transcript.querySelector("ol").replaceChildren(...this.project.scenes.map((scene) => { const item = document.createElement("li"); const strong = document.createElement("strong"); strong.textContent = scene.title; item.append(strong, document.createTextNode(` — ${scene.narration}`)); return item; })); this.renderTimeline(); this.render(); }
    destroy() { if (this.destroyed) return; this.destroyed = true; this.pause(); this.resizeObserver?.disconnect(); this.intersectionObserver?.disconnect(); document.removeEventListener("visibilitychange", this.visibility); this.play?.removeEventListener("click", this.onPlay); this.restart?.removeEventListener("click", this.onRestart); this.previous?.removeEventListener("click", this.onPrevious); this.next?.removeEventListener("click", this.onNext); this.seek?.removeEventListener("input", this.onSeek); this.speedSelect?.removeEventListener("change", this.onSpeed); this.canvas?.removeEventListener("keydown", this.onKey); this.exportStream?.getTracks?.().forEach((track) => track.stop()); mounted.delete(this); }
  }

  function deliverBrowserVideo(blob, project, capability, { isCurrent } = {}) {
    if (typeof isCurrent === "function" && !isCurrent()) return { bytes: blob.size, mime: capability.mime, discarded: true };
    downloadBlob(blob, `${project.id}.${capability.extension}`); return { bytes: blob.size, mime: capability.mime };
  }

  async function exportVideo(project, onProgress = () => {}, { signal, isCurrent } = {}) {
    const capability = videoCapability(); if (!capability.supported) throw new Error(capability.reason);
    const result = validateProject(project); if (!result.ok) throw new Error(result.error);
    const canvas = document.createElement("canvas"); canvas.style.cssText = "position:fixed;left:-9999px;top:-9999px;width:960px;height:540px"; document.body.append(canvas);
    let stream; let recorder; let frameId = 0;
    try {
      const initial = drawFrame(canvas, result.project, 0, 0, { width: 960, height: 540 }); drawExportCaption(canvas, initial.scene, initial.width, initial.height);
      stream = canvas.captureStream(24); const chunks = []; recorder = new MediaRecorder(stream, { mimeType: capability.mime, videoBitsPerSecond: 2_500_000 });
      recorder.addEventListener("dataavailable", (event) => { if (event.data?.size) chunks.push(event.data); });
      const done = new Promise((resolve, reject) => { recorder.addEventListener("stop", () => resolve(new Blob(chunks, { type: capability.mime })), { once: true }); recorder.addEventListener("error", () => reject(recorder.error || new Error("Video encoding failed.")), { once: true }); });
      recorder.start(500); const total = sumDuration(result.project.scenes); const start = performance.now();
      await new Promise((resolve, reject) => {
        const abort = () => { cancelAnimationFrame(frameId); const error = new Error("Video export was cancelled."); error.name = "AbortError"; reject(error); };
        const frame = (time) => { if (signal?.aborted) { abort(); return; } const elapsed = Math.min(total, time - start); let remaining = elapsed; let index = 0; while (index < result.project.scenes.length - 1 && remaining > result.project.scenes[index].duration_ms) { remaining -= result.project.scenes[index].duration_ms; index += 1; } const progress = remaining / result.project.scenes[index].duration_ms; const rendered = drawFrame(canvas, result.project, index, progress, { width: 960, height: 540 }); drawExportCaption(canvas, rendered.scene, rendered.width, rendered.height); onProgress(elapsed / total); if (elapsed >= total) { signal?.removeEventListener?.("abort", abort); resolve(); } else frameId = requestAnimationFrame(frame); };
        signal?.addEventListener?.("abort", abort, { once: true }); frameId = requestAnimationFrame(frame);
      });
      recorder.stop(); const blob = await done; if (!blob.size) throw new Error("The browser returned an empty video.");
      return deliverBrowserVideo(blob, result.project, capability, { isCurrent });
    } catch (error) {
      if (recorder?.state && recorder.state !== "inactive") { try { recorder.stop(); } catch { /* recorder already failed */ } }
      if (error.name === "AbortError") throw error;
      throw new Error(`Video export could not complete: ${error.message}`);
    } finally { cancelAnimationFrame(frameId); stream?.getTracks?.().forEach((track) => track.stop()); canvas.remove(); }
  }

  class Studio {
    constructor(root, options = {}) {
      this.root = root; this.options = options; this.player = null; this.project = null; this.projectRevision = 0; this.timers = []; this.destroyed = false; this.operationToken = 0;
      this.build(); mounted.add(this);
      if (options.project) this.showProject(options.project, { persist: false });
    }
    build() {
      this.root.replaceChildren(); this.root.classList.add("animation-studio-workspace"); this.root.dataset.animationMount = "true";
      const examples = document.createElement("div"); examples.className = "animation-examples";
      const exampleLabel = document.createElement("span"); exampleLabel.textContent = text("animationTryLesson"); examples.append(exampleLabel);
      [
        ["three-quarters", text("animationExampleFraction"), { topic: "Understanding three quarters", level: "early-primary", concept: "Explain 3/4", requirements: "Divide a bar into four equal parts -> shade three parts -> read the fraction" }],
        ["six-by-four", text("animationExampleArray"), { topic: "Six groups of four", level: "upper-primary", concept: "Build 6 × 4", requirements: "Build six rows of four -> connect repeated addition -> write the multiplication equation" }],
        ["cubic", text("animationExampleGraph"), { topic: "How a cubic function changes", level: "secondary", concept: "Plot y = x^3", requirements: "Trace the curve -> read the axes and scale" }],
        ["calculus", text("animationExampleCalculus"), { topic: "Tangent and derivative of a cubic", level: "tertiary", concept: "Plot y = x^3 and show the tangent at x = 2", requirements: "Trace the function -> reveal the tangent -> interpret the local rate of change" }],
      ].forEach(([id, label, values]) => { const chip = button(label, "animation-chip"); chip.dataset.example = id; chip.addEventListener("click", () => { this.topic.value = values.topic; this.level.value = values.level; this.concept.value = values.concept; this.requirements.value = values.requirements; this.updatePrompt(); this.topic.focus(); }); examples.append(chip); });

      const layout = document.createElement("div"); layout.className = "animation-authoring-layout";
      const brief = document.createElement("section"); brief.className = "animation-brief"; brief.setAttribute("aria-labelledby", "animation-brief-title");
      const briefTitle = document.createElement("h4"); briefTitle.id = "animation-brief-title"; briefTitle.textContent = text("animationBriefTitle");
      const briefHelp = document.createElement("p"); briefHelp.textContent = text("animationBriefHelp");
      this.topic = document.createElement("input"); this.topic.id = "animation-topic"; this.topic.maxLength = 240; this.topic.placeholder = text("animationTopicPlaceholder");
      this.level = document.createElement("select"); this.level.id = "animation-level";
      [["early-primary", text("animationLevelEarly")], ["upper-primary", text("animationLevelUpper")], ["secondary", text("animationLevelSecondary")], ["tertiary", text("animationLevelTertiary")]].forEach(([value, label]) => { const option = document.createElement("option"); option.value = value; option.textContent = label; if (value === "secondary") option.selected = true; this.level.append(option); });
      this.concept = document.createElement("input"); this.concept.id = "animation-concept"; this.concept.maxLength = 240; this.concept.placeholder = text("animationConceptPlaceholder");
      this.requirements = document.createElement("textarea"); this.requirements.id = "animation-requirements"; this.requirements.maxLength = 1000; this.requirements.rows = 5; this.requirements.placeholder = text("animationRequirementsPlaceholder");
      const prompt = document.createElement("details"); prompt.className = "animation-prompt"; const promptSummary = document.createElement("summary"); promptSummary.textContent = text("animationPromptShow"); this.promptText = document.createElement("pre"); prompt.append(promptSummary, this.promptText);
      this.generate = button(text("animationGenerate"), "animation-primary animation-generate"); this.generate.addEventListener("click", () => this.generateProject());
      this.cancelGenerate = button(text("animationCancelGeneration")); this.cancelGenerate.hidden = true; this.cancelGenerate.addEventListener("click", () => { this.operationToken += 1; this.plannerAbort?.abort(); this.plannerAbort = null; this.generate.disabled = false; this.cancelGenerate.hidden = true; this.progress.hidden = true; this.error.textContent = text("animationGenerationCancelled"); });
      const importButton = button(text("animationImport")); this.file = document.createElement("input"); this.file.type = "file"; this.file.accept = ".mutaanim,application/vnd.muta.animation+json,application/json"; this.file.hidden = true;
      importButton.addEventListener("click", () => this.file.click()); this.file.addEventListener("change", () => this.importSelected());
      const actions = document.createElement("div"); actions.className = "animation-brief-actions"; actions.append(this.generate, this.cancelGenerate, importButton, this.file);
      this.progress = document.createElement("div"); this.progress.className = "animation-generation-progress"; this.progress.hidden = true; this.progress.setAttribute("role", "status"); this.progress.setAttribute("aria-live", "polite");
      this.progressBar = document.createElement("span"); this.progressCopy = document.createElement("p"); this.progress.append(this.progressBar, this.progressCopy);
      this.error = document.createElement("p"); this.error.className = "animation-error"; this.error.setAttribute("role", "alert");
      brief.append(briefTitle, briefHelp, field(text("animationTopic"), this.topic), field(text("animationLevel"), this.level), field(text("animationConcept"), this.concept), field(text("animationRequirements"), this.requirements), prompt, actions, this.progress, this.error);

      const preview = document.createElement("section"); preview.className = "animation-preview-panel"; preview.setAttribute("aria-labelledby", "animation-preview-title");
      const previewTitle = document.createElement("h4"); previewTitle.id = "animation-preview-title"; previewTitle.textContent = text("animationPreviewTitle");
      this.previewRoot = document.createElement("div"); this.previewRoot.className = "animation-preview-root";
      this.empty = document.createElement("div"); this.empty.className = "animation-preview-empty"; const emptyTitle = document.createElement("strong"); emptyTitle.textContent = text("animationEmptyTitle"); const emptyCopy = document.createElement("p"); emptyCopy.textContent = text("animationEmptyHelp"); this.empty.append(emptyTitle, emptyCopy); this.previewRoot.append(this.empty);
      this.projectActions = document.createElement("div"); this.projectActions.className = "animation-project-actions"; this.projectActions.hidden = true;
      this.editor = document.createElement("details"); this.editor.className = "animation-editor"; this.editor.hidden = true; const editorSummary = document.createElement("summary"); editorSummary.textContent = text("animationEditScenes"); this.editorBody = document.createElement("div"); this.editorBody.className = "animation-editor-body"; this.editor.append(editorSummary, this.editorBody);
      preview.append(previewTitle, this.previewRoot, this.projectActions, this.editor);
      layout.append(brief, preview); this.root.append(examples, layout);
      [this.topic, this.level, this.concept, this.requirements].forEach((node) => node.addEventListener("input", () => this.updatePrompt())); this.updatePrompt();
    }
    updatePrompt() {
      const level = this.level.options[this.level.selectedIndex]?.textContent || this.level.value;
      this.promptText.textContent = `Topic: ${this.topic.value || "—"}\nLearner level: ${level}\nConcept or relationship: ${this.concept.value || "—"}\nRequired sequence: ${this.requirements.value || "—"}\nOutput: a validated local lesson-animation project; no executable code.`;
    }
    setProgress(copy, percent) { this.progress.hidden = false; this.progressCopy.textContent = copy; this.progressBar.style.width = `${percent}%`; }
    clearTimers() { this.timers.forEach((timer) => global.clearTimeout(timer)); this.timers = []; }
    async generateProject() {
      const token = ++this.operationToken; this.clearTimers(); this.plannerAbort?.abort(); this.error.textContent = ""; this.generate.disabled = true; this.cancelGenerate.hidden = false; this.setProgress(text("animationProgressUnderstand"), 22);
      const values = { topic: this.topic.value, level: this.level.value, concept: this.concept.value, requirements: this.requirements.value };
      try {
        await new Promise((resolve) => this.timers.push(global.setTimeout(resolve, 80)));
        if (this.destroyed || token !== this.operationToken) return;
        this.setProgress(text("animationProgressCompose"), 56);
        let project;
        try { project = planProject(values); }
        catch (error) {
          if (error.code !== "planner_required") throw error;
          this.setProgress(text("animationProgressLocalTutor"), 68); this.plannerAbort = new AbortController();
          project = await requestAnimationPlan(values, { signal: this.plannerAbort.signal });
        }
        if (this.destroyed || token !== this.operationToken) return;
        this.setProgress(text("animationProgressValidate"), 88); const result = validateProject(project); if (!result.ok) throw new Error(result.error);
        this.setProgress(text("animationProgressReady"), 100); this.showProject(result.project, { persist: true });
        this.timers.push(global.setTimeout(() => { if (!this.destroyed && token === this.operationToken) this.progress.hidden = true; }, 500));
      } catch (error) {
        if (this.destroyed || token !== this.operationToken || error.name === "AbortError") return;
        this.progress.hidden = true; this.error.textContent = error.message;
      } finally {
        if (!this.destroyed && token === this.operationToken) { this.generate.disabled = false; this.cancelGenerate.hidden = true; this.plannerAbort = null; }
      }
    }
    showProject(project, { persist = true } = {}) {
      const result = validateProject(project); if (!result.ok) { this.error.textContent = result.error; return; }
      this.project = result.project; this.projectRevision += 1; if (persist) saveProject(this.project); this.player?.destroy(); this.previewRoot.replaceChildren(); this.player = mountPlayer(this.previewRoot, this.project); this.projectActions.hidden = false; this.editor.hidden = false; this.renderProjectActions(); this.renderEditor(); this.options.onProject?.(this.project);
    }
    renderProjectActions() {
      this.clearRenderedManimVideo();
      this.manimAbort?.abort(); this.manimAbort = null;
      this.exportAbort?.abort(); this.exportAbort = null;
      this.manimCapabilityAbort?.abort(); this.manimCapabilityAbort = null;
      this.projectActions.replaceChildren();
      const save = button(text("animationSave"), "animation-primary"); save.addEventListener("click", () => { saveProject(this.project); this.error.textContent = text("animationSaved"); });
      const projectExport = button(text("animationExport")); projectExport.addEventListener("click", () => exportProject(this.project));
      const transcriptExport = button(text("animationTranscriptDownload")); transcriptExport.addEventListener("click", () => exportTranscript(this.project));
      this.projectActions.append(save, projectExport, transcriptExport);
      const projectSource = document.createElement("details"); projectSource.className = "animation-project-source"; const projectSourceSummary = document.createElement("summary"); projectSourceSummary.textContent = text("animationProjectSource"); const projectSourceText = document.createElement("pre"); projectSourceText.textContent = JSON.stringify(this.project, null, 2); projectSource.append(projectSourceSummary, projectSourceText); this.projectActions.append(projectSource);
      const manimSource = document.createElement("details"); manimSource.className = "animation-project-source animation-manim-source"; const manimSummary = document.createElement("summary"); manimSummary.textContent = text("animationManimSource"); const manimCode = document.createElement("pre"); manimCode.textContent = text("animationManimSourceLoading"); manimSource.append(manimSummary, manimCode); this.projectActions.append(manimSource);
      const sourceRevision = this.projectRevision; const sourceProject = clone(this.project); this.manimSource = null; this.manimSourceRevision = null; this.sourceAbort?.abort(); this.sourceAbort = new AbortController();
      const revisionNow = () => this.projectRevision;
      requestManimSourceRevision(sourceProject, sourceRevision, revisionNow, { signal: this.sourceAbort.signal }).then((generated) => { if (!this.destroyed && this.projectRevision === sourceRevision) { this.manimSource = generated; this.manimSourceRevision = sourceRevision; manimCode.textContent = generated.source; } }).catch((error) => { if (error.name !== "AbortError" && !this.destroyed && this.projectRevision === sourceRevision) manimCode.textContent = `${text("animationManimSourceUnavailable")} ${error.message}`; });
      const sourceDownload = button(text("animationDownloadManimSource")); sourceDownload.addEventListener("click", async () => { sourceDownload.disabled = true; try { const generated = this.manimSourceRevision === sourceRevision ? this.manimSource : await requestManimSourceRevision(sourceProject, sourceRevision, revisionNow); if (!generated || this.projectRevision !== sourceRevision) return; this.manimSource = generated; this.manimSourceRevision = sourceRevision; manimCode.textContent = generated.source; await downloadManimSource(sourceProject, { generated }); this.error.textContent = text("animationManimSourceReady"); } catch (error) { if (error.name !== "AbortError") this.error.textContent = error.message; } finally { sourceDownload.disabled = false; } }); this.projectActions.append(sourceDownload);
      const renderedVideo = document.createElement("video"); renderedVideo.className = "animation-rendered-video"; renderedVideo.controls = true; renderedVideo.playsInline = true; renderedVideo.preload = "metadata"; renderedVideo.hidden = true; renderedVideo.setAttribute("aria-label", text("animationManimVideoReady")); this.renderedManimVideo = renderedVideo; this.projectActions.append(renderedVideo);
      const downloadRendered = button(text("animationDownloadRenderedManimVideo")); downloadRendered.hidden = true; downloadRendered.addEventListener("click", () => { if (this.manimVideoBlob && this.manimVideoRevision === this.projectRevision) downloadBlob(this.manimVideoBlob, `${this.project.id}-manim.mp4`); }); this.projectActions.append(downloadRendered);
      const manimVideo = button(text("animationRenderManimVideo"), "animation-primary"); manimVideo.addEventListener("click", async () => { manimVideo.disabled = true; this.manimAbort?.abort(); const renderAbort = new AbortController(); const renderRevision = this.projectRevision; const renderProject = clone(this.project); const isCurrent = () => !this.destroyed && this.projectRevision === renderRevision && this.manimAbort === renderAbort; this.manimAbort = renderAbort; this.error.textContent = text("animationRenderingManimVideo"); try { const result = await exportManimVideo(renderProject, { signal: renderAbort.signal, isCurrent, download: false }); if (isCurrent() && !result.discarded) { this.clearRenderedManimVideo({ keepElement: true }); this.manimVideoBlob = result.blob; this.manimVideoRevision = renderRevision; this.manimVideoUrl = URL.createObjectURL(result.blob); renderedVideo.src = this.manimVideoUrl; renderedVideo.hidden = false; renderedVideo.load(); downloadRendered.hidden = false; this.error.textContent = text("animationManimVideoReady"); } } catch (error) { if (error.name !== "AbortError" && isCurrent()) this.error.textContent = error.message; } finally { manimVideo.disabled = false; if (this.manimAbort === renderAbort) this.manimAbort = null; } }); this.projectActions.append(manimVideo);
      const manimCapabilityNote = document.createElement("p"); manimCapabilityNote.className = "animation-export-note"; manimCapabilityNote.textContent = text("animationRenderCapabilityChecking"); this.projectActions.append(manimCapabilityNote); manimVideo.disabled = true;
      const capabilityRevision = this.projectRevision; const capabilityAbort = new AbortController(); this.manimCapabilityAbort = capabilityAbort;
      requestManimCapability({ signal: capabilityAbort.signal }).then((result) => { if (this.destroyed || this.projectRevision !== capabilityRevision || this.manimCapabilityAbort !== capabilityAbort) return; manimVideo.disabled = !result.available; manimCapabilityNote.hidden = result.available; manimCapabilityNote.textContent = result.detail; if (!result.available) manimVideo.title = result.detail; }).catch((error) => { if (error.name !== "AbortError" && !this.destroyed && this.projectRevision === capabilityRevision && this.manimCapabilityAbort === capabilityAbort) { manimVideo.disabled = true; manimCapabilityNote.hidden = false; manimCapabilityNote.textContent = error.message; manimVideo.title = error.message; } }).finally(() => { if (this.manimCapabilityAbort === capabilityAbort) this.manimCapabilityAbort = null; });
      const capability = videoCapability();
      if (capability.supported) { const video = button(text("animationDownloadVideo")); video.addEventListener("click", async () => { video.disabled = true; this.exportAbort?.abort(); const exportAbort = new AbortController(); const exportRevision = this.projectRevision; const exportProjectSnapshot = clone(this.project); const isCurrent = () => !this.destroyed && this.projectRevision === exportRevision && this.exportAbort === exportAbort; this.exportAbort = exportAbort; this.error.textContent = text("animationEncodingVideo"); try { const result = await exportVideo(exportProjectSnapshot, (progress) => { if (isCurrent()) this.error.textContent = text("animationEncodingProgress", { percent: Math.round(progress * 100) }); }, { signal: exportAbort.signal, isCurrent }); if (isCurrent() && !result.discarded) this.error.textContent = text("animationVideoReady"); } catch (error) { if (error.name !== "AbortError" && isCurrent()) this.error.textContent = error.message; } finally { video.disabled = false; if (this.exportAbort === exportAbort) this.exportAbort = null; } }); this.projectActions.append(video); }
      else { const note = document.createElement("p"); note.className = "animation-export-note"; note.textContent = text("animationVideoUnavailable"); this.projectActions.append(note); }
    }
    renderEditor() {
      this.editorBody.replaceChildren(); this.project.scenes.forEach((scene, index) => {
        const row = document.createElement("fieldset"); row.className = "animation-scene-editor"; const legend = document.createElement("legend"); legend.textContent = text("animationSceneLabel", { number: index + 1 });
        const titleInput = document.createElement("input"); titleInput.value = scene.title; titleInput.maxLength = 140; const narration = document.createElement("textarea"); narration.value = scene.narration; narration.maxLength = 700; narration.rows = 3;
        const duration = document.createElement("input"); duration.type = "number"; duration.min = String(MIN_SCENE_MS); duration.max = String(MAX_SCENE_MS); duration.step = "100"; duration.value = String(scene.duration_ms);
        const up = button(text("animationMoveUp")); up.disabled = index === 0; up.addEventListener("click", () => this.moveScene(index, -1)); const down = button(text("animationMoveDown")); down.disabled = index === this.project.scenes.length - 1; down.addEventListener("click", () => this.moveScene(index, 1));
        const apply = button(text("animationApplyScene"), "animation-primary"); apply.addEventListener("click", () => { const updated = clone(this.project); updated.scenes[index].title = titleInput.value.trim(); updated.scenes[index].narration = narration.value.trim(); updated.scenes[index].duration_ms = Number(duration.value); updated.updated_at = new Date().toISOString(); const result = validateProject(updated); if (!result.ok) { this.error.textContent = result.error; return; } this.error.textContent = ""; this.project = saveProject(result.project); this.projectRevision += 1; this.player.updateProject(this.project); this.renderProjectActions(); this.renderEditor(); this.options.onProject?.(this.project); });
        const controls = document.createElement("div"); controls.className = "animation-scene-editor-actions"; controls.append(up, down, apply);
        row.append(legend, field(text("animationSceneTitle"), titleInput), field(text("animationSceneNarration"), narration), field(text("animationSceneDuration"), duration), controls); this.editorBody.append(row);
      });
    }
    moveScene(index, delta) { const target = index + delta; if (target < 0 || target >= this.project.scenes.length) return; const updated = clone(this.project); [updated.scenes[index], updated.scenes[target]] = [updated.scenes[target], updated.scenes[index]]; updated.updated_at = new Date().toISOString(); this.project = saveProject(updated); this.projectRevision += 1; this.player.updateProject(this.project); this.renderProjectActions(); this.renderEditor(); this.options.onProject?.(this.project); }
    clearRenderedManimVideo({ keepElement = false } = {}) { this.renderedManimVideo?.pause?.(); if (this.renderedManimVideo) { this.renderedManimVideo.removeAttribute("src"); this.renderedManimVideo.load?.(); if (!keepElement) this.renderedManimVideo = null; } if (this.manimVideoUrl) URL.revokeObjectURL(this.manimVideoUrl); this.manimVideoUrl = null; this.manimVideoBlob = null; this.manimVideoRevision = null; }
    async importSelected() {
      const file = this.file.files?.[0]; this.file.value = ""; if (!file) return;
      if (file.size > MAX_PROJECT_BYTES) { this.error.textContent = text("animationImportTooLarge"); return; }
      const token = ++this.operationToken; this.clearTimers(); this.pendingProject = null; this.plannerAbort?.abort(); this.plannerAbort = null; this.generate.disabled = false; this.cancelGenerate.hidden = true; this.progress.hidden = true;
      try { const parsed = JSON.parse(await file.text()); if (this.destroyed || token !== this.operationToken) return; const result = validateProject(parsed); if (!result.ok) throw new Error(result.error); this.topic.value = result.project.topic; this.level.value = result.project.level; this.concept.value = result.project.title; this.requirements.value = result.project.summary; this.updatePrompt(); this.showProject(result.project, { persist: true }); this.error.textContent = text("animationImported"); } catch (error) { if (!this.destroyed && token === this.operationToken) this.error.textContent = `${text("animationImportFailed")} ${error.message}`; }
    }
    destroy() { if (this.destroyed) return; this.destroyed = true; this.operationToken += 1; this.exportAbort?.abort(); this.plannerAbort?.abort(); this.sourceAbort?.abort(); this.manimAbort?.abort(); this.manimCapabilityAbort?.abort(); this.clearRenderedManimVideo(); this.clearTimers(); this.player?.destroy(); mounted.delete(this); }
  }

  function mountStudio(root, options = {}) { return new Studio(root, options); }

  function mountPlayer(root, project, options = {}) { return new Player(root, project, options); }

  function cleanup(root = document) {
    for (const controller of [...mounted]) if (!root || root === document || root.contains?.(controller.root) || controller.root === root || !controller.root.isConnected) controller.destroy();
  }

  global.MutaAnimator = Object.freeze({
    VERSION, KIND, validateProject, planProject, requestAnimationPlan, parseFraction, parseArray, parsePolynomial, parseFunction, formatMathValue,
    parseVector, parseProcess, polynomialValue, expressionValue, numericalDerivative, numericalIntegral, projectDescription, loadProjects, saveProject,
    removeProject, exportProject, exportTranscript, deliverBrowserVideo, exportVideo, videoCapability, requestManimCapability, requestManimSource, requestManimSourceRevision, downloadManimSource, exportManimVideo, drawFrame, drawExportCaption,
    mountPlayer, mountStudio, cleanup,
  });
  if (typeof module !== "undefined" && module.exports) module.exports = global.MutaAnimator;
})(typeof globalThis !== "undefined" ? globalThis : window);
