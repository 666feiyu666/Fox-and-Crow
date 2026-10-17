(() => {
  "use strict";

  const I18N = {
    en: {
      railStories: "Stories",
      railRuns: "Past runs",
      railEmpty: "Nothing played yet.",
      railToggle: "Past runs",
      settings: "Settings",
      settingsTitle: "Settings",
      uiLanguageLabel: "Interface language",
      storyKeyLabel: "Story API key",
      storyKeyNote:
        "Saved to .env.local beside the server, and never shown again. It only ever lives on this machine.",
      saveKey: "Save key",
      close: "Close",
      keyReady: "A key is configured.",
      keyMissing: "No key yet. Turns fail until one is saved.",
      keySaved: "Saved. New turns use this key.",
      runDelete: "Delete this run",
      runConfirm: "Delete this run? The stored story cannot be recovered.",
      metaJoin: ", ",
      languageName: "English",
      loopShort: "loop {n}",
      turnShort: "turn {n}",
      endedShort: "ended",
      timeNow: "just now",
      timeMinutes: "{n} min ago",
      timeHours: "{n} h ago",
      timeDays: "{n} d ago",
      shelfTitle: "Playable stories",
      shelfLede:
        "Every story here arrives as a bare tale. Before you begin, it is read once: the role you take, the world around you and the first passage all come from the words that were already there.",
      readThis: "Choose a story",
      back: "All stories",
      shelfEmpty: "No stories are on the shelf yet.",
      shelfError: "The shelf could not be opened. Try again.",
      pickLede:
        "Choose the language this story will be told in. The choice holds for this whole run, and a past run keeps the language it was started in.",
      pickLanguageLabel: "Tell it in",
      resumeFailed: "This run could not be opened.",
      restart: "Restart",
      youAre: "You are {name}",
      loopCount: "Loop {n}",
      turnCount: "Turn {n}",
      labelShelf: "Shelf",
      labelChoose: "Choose",
      labelOpening: "Opening",
      labelTurn: "Turn {n}",
      pageOf: "{page} / {pages}",
      again: "Another beginning",
      ended: "The story has ended. Restart to begin again.",
      inputLabel: "Your line or action",
      prevPage: "Previous page",
      nextPage: "Next page",
      say: "Say",
      do: "Do",
      placeholderSay: "One line you say…",
      placeholderDo: "One action you attempt…",
      send: "Send",
      thinking: "The storyteller is thinking…",
      understandingTitle: "The understander is reading this case…",
      understandingBody:
        "It reads the original tale you passed in and derives who you are, the world, and the opening.",
      understandingSlow: "The first pass reads the whole source, so this can take a moment.",
      tryNext: "Could try",
      error: "The story could not continue. Try again.",
      note: "Nothing is scripted. Every line you write is answered by the storyteller.",
    },
    zh: {
      railStories: "故事",
      railRuns: "存档",
      railEmpty: "还没有存档。",
      railToggle: "存档",
      settings: "设置",
      settingsTitle: "设置",
      uiLanguageLabel: "界面语言",
      storyKeyLabel: "故事 API key",
      storyKeyNote: "保存到服务器旁的 .env.local，页面不会再次显示它；这个 key 只留在这台机器上。",
      saveKey: "保存 key",
      close: "关闭",
      keyReady: "已经配置了 key。",
      keyMissing: "还没有 key，保存之前回合会失败。",
      keySaved: "已保存，新的回合会用这个 key。",
      runDelete: "删除这个存档",
      runConfirm: "删除这个存档？存下来的故事无法恢复。",
      metaJoin: "，",
      languageName: "中文",
      loopShort: "第 {n} 次",
      turnShort: "第 {n} 轮",
      endedShort: "已结束",
      timeNow: "刚刚",
      timeMinutes: "{n} 分钟前",
      timeHours: "{n} 小时前",
      timeDays: "{n} 天前",
      shelfTitle: "玩故事",
      shelfLede:
        "这里的每个故事都只带来原文。开始之前，它会被读一次：你扮演谁、周围是怎样的世界、开场那一段，都从那几行原文里长出来。",
      readThis: "选一个故事",
      back: "所有故事",
      shelfEmpty: "书架上还没有故事。",
      shelfError: "书架没有打开，请再试一次。",
      pickLede: "选择这个故事用什么语言讲。选定后这一局都不能再改，旧的存档保留它当时的语言。",
      pickLanguageLabel: "用它来讲",
      resumeFailed: "这个存档打不开。",
      restart: "重新开始",
      youAre: "你扮演 {name}",
      loopCount: "第 {n} 次",
      turnCount: "第 {n} 轮",
      labelShelf: "书架",
      labelChoose: "选择",
      labelOpening: "开场",
      labelTurn: "第 {n} 轮",
      pageOf: "{page} / {pages}",
      again: "又一次开始",
      ended: "故事结束了。重新开始可以再来一次。",
      inputLabel: "你说的话，或你做的事",
      prevPage: "上一页",
      nextPage: "下一页",
      say: "说",
      do: "做",
      placeholderSay: "你说一句话……",
      placeholderDo: "你尝试一个动作……",
      send: "继续",
      thinking: "讲故事的人正在想……",
      understandingTitle: "understander 正在读你传入的这个故事……",
      understandingBody: "它读你传入的原故事，推导出你扮演谁、世界是什么样，以及开场。",
      understandingSlow: "第一次要通读原文，可能要等一会儿。",
      tryNext: "可以试试",
      error: "故事暂时无法继续，请再试一次。",
      note: "没有任何预写剧本。你写的每一句，都会由讲故事的人接着讲下去。",
    },
  };

  const SVG_NS = "http://www.w3.org/2000/svg";
  const UI_LANGUAGE_KEY = "storyteller.ui";
  const PICK_ROUTE = /^#\/pick\/([^/]+)$/;
  const STORY_ROUTE = /^#\/story\/([^/]+)\/([^/]+)$/;
  const RUN_ROUTE = /^#\/run\/([^/]+)$/;
  const UNDERSTANDING_SLOW_MS = 2500;
  const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

  const rail = document.getElementById("rail");
  const railToggle = document.getElementById("rail-toggle");
  const railRuns = document.getElementById("rail-runs");
  const railRunsTitle = document.getElementById("rail-runs-title");
  const railEmpty = document.getElementById("rail-empty");
  const railHome = document.getElementById("rail-home");
  const settingsOpen = document.getElementById("settings-open");
  const settingsDialog = document.getElementById("settings");
  const settingsForm = document.getElementById("settings-form");
  const settingsTitle = document.getElementById("settings-title");
  const settingsLanguageLabel = document.getElementById("settings-language-label");
  const settingsLanguages = document.getElementById("settings-languages");
  const settingsKeyLabel = document.getElementById("settings-key-label");
  const settingsNote = document.getElementById("settings-note");
  const apiKeyLabel = document.getElementById("api-key-label");
  const apiKeyInput = document.getElementById("api-key");
  const settingsStatus = document.getElementById("settings-status");
  const settingsSave = document.getElementById("settings-save");
  const settingsClose = document.getElementById("settings-close");

  const shelfView = document.getElementById("shelf-view");
  const shelfTitle = document.getElementById("shelf-title");
  const shelfLede = document.getElementById("shelf-lede");
  const shelfList = document.getElementById("shelf-list");
  const shelfMessage = document.getElementById("shelf-message");
  const shelfLeafTitle = document.getElementById("shelf-leaf-title");
  const shelfLeafState = document.getElementById("shelf-leaf-state");
  const shelfLeafLabel = document.getElementById("shelf-leaf-label");

  const pickView = document.getElementById("pick-view");
  const pickBack = document.getElementById("pick-back");
  const pickTitle = document.getElementById("pick-title");
  const pickQuote = document.getElementById("pick-quote");
  const pickLede = document.getElementById("pick-lede");
  const pickLanguages = document.getElementById("pick-languages");
  const pickMessage = document.getElementById("pick-message");
  const pickLeafTitle = document.getElementById("pick-leaf-title");
  const pickLeafState = document.getElementById("pick-leaf-state");
  const pickLeafLabel = document.getElementById("pick-leaf-label");

  const storyView = document.getElementById("story-view");
  const book = document.getElementById("book");
  const leafTitle = document.getElementById("leaf-title");
  const leafState = document.getElementById("leaf-state");
  const leafLabel = document.getElementById("leaf-label");
  const leafGauge = document.getElementById("leaf-gauge");
  const log = document.getElementById("log");
  const pagePrev = document.getElementById("page-prev");
  const pageNext = document.getElementById("page-next");
  const pagerCount = document.getElementById("pager-count");
  const actionBox = document.getElementById("action");
  const sendButton = document.getElementById("send");
  const message = document.getElementById("message");
  const hints = document.getElementById("hints");
  const restartButton = document.getElementById("restart");
  const backLink = document.getElementById("back");
  const note = document.getElementById("note");
  const inputLabel = document.getElementById("input-label");
  const modeButtons = Array.from(document.querySelectorAll("[data-mode]"));

  let uiLanguage = readUiLanguage();
  let storyLanguage = "en";
  let sessionId = null;
  let activeRunId = null;
  let caseInfo = null;
  let mode = "say";
  let busy = false;
  let messageKey = null;
  let loop = 1;
  let turn = 0;
  let ended = false;
  let shelfEntries = null;
  let passages = [];
  let pageIndex = 0;
  let turning = false;

  function readUiLanguage() {
    try {
      const stored = window.localStorage.getItem(UI_LANGUAGE_KEY);
      if (stored === "en" || stored === "zh") {
        return stored;
      }
    } catch (error) {
      /* storage can be unavailable; fall through to the page language */
    }
    return document.documentElement.lang === "zh" ? "zh" : "en";
  }

  function t(key, vars) {
    const template = I18N[uiLanguage][key] ?? I18N.en[key] ?? key;
    if (!vars) {
      return template;
    }
    return template.replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ""));
  }

  function fromTable(key, language_ = uiLanguage) {
    return I18N[language_][key] ?? I18N.en[key] ?? key;
  }

  function caseText(table, language_ = storyLanguage) {
    return (table && (table[language_] || table.en)) || "";
  }

  function languageName(language_) {
    return fromTable("languageName", language_);
  }

  function roman(number) {
    const steps = [
      [1000, "M"], [900, "CM"], [500, "D"], [400, "CD"], [100, "C"], [90, "XC"],
      [50, "L"], [40, "XL"], [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"],
    ];
    let remaining = Math.max(1, Math.round(number));
    let glyphs = "";
    for (const [value, glyph] of steps) {
      while (remaining >= value) {
        glyphs += glyph;
        remaining -= value;
      }
    }
    return glyphs || "I";
  }

  function setMessage(key, text, tone) {
    messageKey = key;
    message.textContent = key ? t(key) : text || "";
    if (tone) {
      message.dataset.tone = tone;
    } else {
      delete message.dataset.tone;
    }
  }

  /* Label text lives in its own slot so the icon beside it survives repaints. */

  function setLabel(el, text) {
    if (!el) {
      return;
    }
    const slot = el.querySelector("[data-label]");
    if (slot) {
      slot.textContent = text;
    } else {
      el.textContent = text;
    }
  }

  function icon(name, className = "icon") {
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("class", className);
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const use = document.createElementNS(SVG_NS, "use");
    use.setAttribute("href", `#i-${name}`);
    svg.appendChild(use);
    return svg;
  }

  function setBusy(value) {
    busy = value;
    sendButton.disabled = value || ended;
    actionBox.disabled = value || ended;
    modeButtons.forEach((button) => {
      button.disabled = value || ended;
    });
  }

  function renderParagraphs(container, text) {
    text
      .split(/\n{2,}/)
      .map((part) => part.trim())
      .filter(Boolean)
      .forEach((part) => {
        const paragraph = document.createElement("p");
        paragraph.textContent = part;
        container.appendChild(paragraph);
      });
  }

  /* One page of the book: the opening, or one turn (your line and its answer). */

  function pageLabel(passage) {
    if (!passage || passage.kind === "opening") {
      return t("labelOpening");
    }
    return t("labelTurn", { n: passage.turn ?? turn });
  }

  function renderLeafChrome() {
    const total = Math.max(1, passages.length);
    leafTitle.textContent = caseInfo ? caseText(caseInfo.title) : t("shelfTitle");
    leafState.textContent = `${t("loopCount", { n: loop })} · ${t("turnCount", { n: turn })}`;
    leafLabel.textContent = pageLabel(passages[pageIndex]);
    leafGauge.textContent = roman(pageIndex + 1);
    pagerCount.textContent = t("pageOf", { page: pageIndex + 1, pages: total });
    pagePrev.disabled = pageIndex <= 0;
    pageNext.disabled = pageIndex >= total - 1;
  }

  function renderPage() {
    const passage = passages[pageIndex];
    log.replaceChildren();
    if (!passage) {
      renderLeafChrome();
      return;
    }
    if (passage.kind === "opening") {
      const block = document.createElement("div");
      block.className = "page-opening";
      renderParagraphs(block, passage.text);
      log.appendChild(block);
    } else {
      const line = document.createElement("p");
      line.className = "action";
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = t(passage.type);
      line.append(
        tag,
        document.createTextNode(passage.type === "say" ? `“${passage.text}”` : passage.text),
      );
      const body = document.createElement("div");
      body.className = "narration";
      renderParagraphs(body, passage.narration);
      log.append(line, body);
    }
    renderLeafChrome();
  }

  async function turnPage(apply, forward) {
    const origin = forward ? "-1" : "1";
    const out = book.animate(
      [
        { transform: "rotateY(0deg)", opacity: 1 },
        { transform: `rotateY(${forward ? -16 : 16}deg) translateX(${origin}rem)`, opacity: 0 },
      ],
      { duration: 190, easing: "ease-in", fill: "forwards" },
    );
    try {
      await out.finished;
    } catch (error) {
      out.cancel();
      apply();
      return;
    }
    apply();
    const back = book.animate(
      [
        { transform: `rotateY(${forward ? 14 : -14}deg) translateX(${forward ? "1" : "-1"}rem)`, opacity: 0 },
        { transform: "rotateY(0deg) translateX(0)", opacity: 1 },
      ],
      { duration: 250, easing: "ease-out", fill: "forwards" },
    );
    try {
      await back.finished;
    } catch (error) {
      /* the page is already readable */
    }
    out.cancel();
    back.cancel();
  }

  async function goToPage(index, animate = true) {
    const next = Math.max(0, Math.min(index, passages.length - 1));
    if (next === pageIndex || turning) {
      return;
    }
    const forward = next > pageIndex;
    const apply = () => {
      pageIndex = next;
      renderPage();
    };
    if (!animate || REDUCED_MOTION.matches) {
      apply();
      return;
    }
    turning = true;
    try {
      await turnPage(apply, forward);
    } finally {
      turning = false;
    }
  }

  function paintStoryChrome() {
    setLabel(restartButton, t("restart"));
    restartButton.title = t("restart");
    setLabel(backLink, t("back"));
    actionBox.placeholder = fromTable(mode === "say" ? "placeholderSay" : "placeholderDo");
    setLabel(sendButton, t("send"));
    sendButton.title = t("send");
    inputLabel.textContent = t("inputLabel");
    note.textContent = t("note");
    modeButtons.forEach((button) => {
      setLabel(button, fromTable(button.dataset.mode === "say" ? "say" : "do"));
      button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
    });
    renderLeafChrome();
    if (messageKey) {
      message.textContent = t(messageKey);
    }
  }

  function paintStatic() {
    document.documentElement.lang = uiLanguage;
    setLabel(railHome, t("railStories"));
    setLabel(railToggle, t("railToggle"));
    railToggle.title = t("railToggle");
    setLabel(railRunsTitle, t("railRuns"));
    railEmpty.textContent = t("railEmpty");
    setLabel(settingsOpen, t("settings"));
    setLabel(settingsTitle, t("settingsTitle"));
    setLabel(settingsLanguageLabel, t("uiLanguageLabel"));
    setLabel(settingsKeyLabel, t("storyKeyLabel"));
    settingsNote.textContent = t("storyKeyNote");
    apiKeyLabel.textContent = t("storyKeyLabel");
    setLabel(settingsSave, t("saveKey"));
    settingsSave.title = t("saveKey");
    setLabel(settingsClose, t("close"));
    shelfTitle.textContent = t("shelfTitle");
    shelfLede.textContent = t("shelfLede");
    shelfList.setAttribute("aria-label", t("shelfTitle"));
    shelfLeafTitle.textContent = t("railStories");
    shelfLeafState.textContent = t("shelfTitle");
    shelfLeafLabel.textContent = t("labelShelf");
    setLabel(pickBack, t("back"));
    pickLede.textContent = t("pickLede");
    pagePrev.setAttribute("aria-label", t("prevPage"));
    pagePrev.title = t("prevPage");
    pageNext.setAttribute("aria-label", t("nextPage"));
    pageNext.title = t("nextPage");
    paintStoryChrome();
    renderSettingsLanguages();
  }

  function renderSettingsLanguages() {
    settingsLanguages.replaceChildren(
      ...[
        ["en", "English"],
        ["zh", "中文"],
      ].map(([code, label]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        button.dataset.uiLanguage = code;
        button.setAttribute("aria-pressed", String(uiLanguage === code));
        button.addEventListener("click", () => setUiLanguage(code));
        return button;
      }),
    );
  }

  function setUiLanguage(next) {
    if (next === uiLanguage) {
      return;
    }
    uiLanguage = next;
    try {
      window.localStorage.setItem(UI_LANGUAGE_KEY, next);
    } catch (error) {
      /* the choice still applies to this page */
    }
    paintStatic();
    if (!shelfView.hidden) {
      renderShelf();
    }
    if (!pickView.hidden) {
      const caseId = pickRoute();
      if (caseId) {
        renderPick(caseId);
      }
    }
    if (!storyView.hidden) {
      renderPage();
    }
    refreshRail();
  }

  function setHints(items) {
    hints.replaceChildren(
      ...(items || []).map((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.append(icon("bulb"), document.createTextNode(item));
        button.addEventListener("click", () => {
          actionBox.value = item;
          actionBox.focus();
        });
        return button;
      }),
    );
  }

  async function request(path, body) {
    const init =
      body === undefined
        ? { method: "GET" }
        : {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          };
    let response;
    try {
      response = await fetch(path, init);
    } catch (error) {
      const failure = new Error(t("error"));
      failure.key = "error";
      throw failure;
    }
    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      data = {};
    }
    if (!response.ok) {
      throw new Error(data.error || t("error"));
    }
    return data;
  }

  function relativeTime(seconds) {
    const delta = Date.now() / 1000 - seconds;
    if (delta < 60) {
      return t("timeNow");
    }
    if (delta < 3600) {
      return t("timeMinutes", { n: Math.round(delta / 60) });
    }
    if (delta < 86400) {
      return t("timeHours", { n: Math.round(delta / 3600) });
    }
    if (delta < 86400 * 7) {
      return t("timeDays", { n: Math.round(delta / 86400) });
    }
    return new Date(seconds * 1000).toLocaleDateString(uiLanguage === "zh" ? "zh-CN" : "en-GB");
  }

  function runItem(run) {
    const item = document.createElement("li");
    item.className = "run";

    const link = document.createElement("a");
    link.className = "run-link";
    link.href = `#/run/${encodeURIComponent(run.id)}`;
    if (run.id === activeRunId) {
      link.setAttribute("aria-current", "true");
    }

    const name = document.createElement("span");
    name.className = "run-name";
    name.textContent = caseText(run.title, run.language);

    const meta = document.createElement("span");
    meta.className = "run-meta";
    const parts = [
      languageName(run.language),
      t("loopShort", { n: run.loop }),
      t("turnShort", { n: run.turn }),
      relativeTime(run.updated),
    ];
    if (run.ended) {
      parts.unshift(t("endedShort"));
    }
    meta.textContent = parts.join(t("metaJoin"));

    link.append(name, meta);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "run-delete";
    remove.append(icon("trash"));
    remove.title = t("runDelete");
    remove.setAttribute("aria-label", t("runDelete"));
    remove.addEventListener("click", () => deleteRun(run.id));

    item.append(link, remove);
    return item;
  }

  async function refreshRail() {
    let runs = [];
    try {
      const data = await request("/api/runs");
      runs = data.runs || [];
    } catch (error) {
      runs = [];
    }
    railRuns.replaceChildren(...runs.map(runItem));
    railEmpty.hidden = runs.length > 0;
    railEmpty.textContent = t("railEmpty");
  }

  async function deleteRun(runId) {
    if (!window.confirm(t("runConfirm"))) {
      return;
    }
    try {
      await request("/api/runs/delete", { runId });
    } catch (error) {
      /* the list below is the source of truth */
    }
    if (activeRunId === runId) {
      window.location.hash = "#/";
      return;
    }
    refreshRail();
  }

  function shelfItem(entry) {
    const item = document.createElement("li");
    item.className = "story-item";
    const link = document.createElement("a");
    link.className = "story-link";
    link.href = `#/pick/${encodeURIComponent(entry.id)}`;
    const name = document.createElement("h2");
    name.className = "story-name";
    name.textContent = caseText(entry.title, uiLanguage);
    const quote = document.createElement("p");
    quote.className = "story-quote";
    quote.textContent = `“${caseText(entry.excerpt, uiLanguage)}”`;
    const open = document.createElement("span");
    open.className = "story-open";
    open.append(document.createTextNode(t("readThis")), icon("arrow-right"));
    link.append(name, quote, open);
    item.appendChild(link);
    return item;
  }

  async function renderShelf() {
    shelfMessage.textContent = "";
    delete shelfMessage.dataset.tone;
    if (shelfEntries === null) {
      try {
        const data = await request("/api/cases");
        shelfEntries = data.cases || [];
      } catch (error) {
        shelfEntries = null;
        shelfMessage.textContent = t("shelfError");
        shelfMessage.dataset.tone = "warn";
        return;
      }
    }
    shelfList.replaceChildren(...shelfEntries.map(shelfItem));
    if (!shelfEntries.length) {
      shelfMessage.textContent = t("shelfEmpty");
    }
  }

  function pickRoute() {
    const match = PICK_ROUTE.exec(window.location.hash);
    return match ? decodeURIComponent(match[1]) : null;
  }

  function storyRoute() {
    const match = STORY_ROUTE.exec(window.location.hash);
    if (!match) {
      return null;
    }
    const language_ = decodeURIComponent(match[2]);
    if (language_ !== "en" && language_ !== "zh") {
      return null;
    }
    return { caseId: decodeURIComponent(match[1]), language: language_ };
  }

  function runRoute() {
    const match = RUN_ROUTE.exec(window.location.hash);
    return match ? decodeURIComponent(match[1]) : null;
  }

  async function ensureShelf() {
    if (shelfEntries === null) {
      try {
        const data = await request("/api/cases");
        shelfEntries = data.cases || [];
      } catch (error) {
        shelfEntries = null;
      }
    }
    return shelfEntries || [];
  }

  async function renderPick(caseId) {
    pickMessage.textContent = "";
    pickLanguages.replaceChildren();
    const entries = await ensureShelf();
    const entry = entries.find((item) => item.id === caseId);
    pickTitle.textContent = entry ? caseText(entry.title, uiLanguage) : caseId;
    pickQuote.textContent = entry ? `“${caseText(entry.excerpt, uiLanguage)}”` : "";
    pickLeafTitle.textContent = pickTitle.textContent;
    pickLeafState.textContent = t("pickLanguageLabel");
    pickLeafLabel.textContent = t("labelChoose");
    document.title = pickTitle.textContent;
    const label = document.createElement("p");
    label.className = "sr-only";
    label.textContent = t("pickLanguageLabel");
    const group = document.createElement("div");
    group.className = "pick-languages";
    ["en", "zh"].forEach((code) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = fromTable("languageName", code);
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => {
        window.location.hash = `#/story/${encodeURIComponent(caseId)}/${code}`;
      });
      group.appendChild(button);
    });
    pickLanguages.append(label, group);
  }

  function discardSession() {
    const stale = sessionId;
    sessionId = null;
    if (!stale) {
      return;
    }
    fetch("/api/session/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: stale }),
    }).catch(() => {});
  }

  function showShelf() {
    discardSession();
    activeRunId = null;
    caseInfo = null;
    storyView.hidden = true;
    pickView.hidden = true;
    shelfView.hidden = false;
    document.title = t("shelfTitle");
    renderShelf();
    refreshRail();
  }

  async function showPick(caseId) {
    discardSession();
    activeRunId = null;
    storyView.hidden = true;
    shelfView.hidden = true;
    pickView.hidden = false;
    await renderPick(caseId);
  }

  function showStory() {
    shelfView.hidden = true;
    pickView.hidden = true;
    storyView.hidden = false;
  }

  function route() {
    const story = storyRoute();
    if (story) {
      showStory();
      startStory(story.caseId, story.language);
      return;
    }
    const runId = runRoute();
    if (runId) {
      showStory();
      resumeRun(runId);
      return;
    }
    const caseId = pickRoute();
    if (caseId) {
      showPick(caseId);
      return;
    }
    showShelf();
  }

  async function startStory(caseId, language_) {
    storyLanguage = language_;
    passages = [];
    pageIndex = 0;
    turn = 0;
    setMessage("understandingTitle");
    setHints([]);
    setBusy(true);
    renderLeafChrome();
    const slowTimer = setTimeout(() => {
      if (busy) {
        setMessage("understandingSlow");
      }
    }, UNDERSTANDING_SLOW_MS);
    try {
      const data = await request("/api/session", { language: language_, case: caseId });
      sessionId = data.sessionId;
      activeRunId = data.sessionId;
      caseInfo = data.case;
      loop = data.playerState.loop;
      turn = data.playerState.turn;
      ended = data.playerState.ended;
      passages = [{ kind: "opening", text: data.opening }];
      pageIndex = 0;
      renderPage();
      setMessage(null);
      refreshRail();
    } catch (error) {
      setMessage(error.key || null, error.message || t("error"), "warn");
    } finally {
      clearTimeout(slowTimer);
      setBusy(false);
    }
    actionBox.focus();
  }

  async function resumeRun(runId) {
    passages = [];
    pageIndex = 0;
    setMessage(null);
    setHints([]);
    setBusy(true);
    renderLeafChrome();
    try {
      const data = await request("/api/runs/resume", { runId });
      sessionId = data.sessionId;
      activeRunId = data.sessionId;
      caseInfo = data.case;
      storyLanguage = data.playerState.language;
      loop = data.playerState.loop;
      turn = data.playerState.turn;
      ended = data.playerState.ended;
      passages = (data.passages || []).map((passage) =>
        passage.kind === "opening"
          ? { kind: "opening", text: passage.text }
          : {
              kind: "turn",
              type: passage.type,
              text: passage.text,
              narration: passage.narration,
              turn: passage.turn,
              loop: passage.loop,
            },
      );
      pageIndex = Math.max(0, passages.length - 1);
      renderPage();
      setMessage(ended ? "ended" : null, undefined, ended ? "done" : undefined);
      refreshRail();
    } catch (error) {
      setMessage(error.key || null, error.message || t("resumeFailed"), "warn");
    } finally {
      setBusy(false);
    }
    actionBox.focus();
  }

  async function takeTurn() {
    if (busy || ended || !sessionId) {
      return;
    }
    const text = actionBox.value.trim();
    if (!text) {
      actionBox.focus();
      return;
    }

    const chosenType = mode;
    actionBox.value = "";
    setBusy(true);
    setMessage("thinking");
    setHints([]);

    try {
      const data = await request("/api/turn", { sessionId, type: chosenType, text });
      loop = data.playerState.loop;
      turn = data.playerState.turn;
      ended = data.playerState.ended;
      passages.push({
        kind: "turn",
        type: chosenType,
        text,
        narration: data.narration,
        turn,
        loop,
      });
      setHints(ended ? [] : data.hints);
      setMessage(ended ? "ended" : null, undefined, ended ? "done" : undefined);
      await goToPage(passages.length - 1);
      refreshRail();
    } catch (error) {
      setMessage(error.key || null, error.message || t("error"), "warn");
    } finally {
      setBusy(false);
      if (!ended) {
        actionBox.focus();
      }
    }
  }

  function setMode(next) {
    mode = next;
    paintStoryChrome();
    actionBox.focus();
  }

  async function openSettings() {
    settingsStatus.textContent = "";
    settingsDialog.showModal();
    try {
      const data = await request("/api/settings");
      settingsStatus.textContent = data.configured ? t("keyReady") : t("keyMissing");
    } catch (error) {
      settingsStatus.textContent = t("error");
    }
    apiKeyInput.focus();
  }

  async function saveKey(event) {
    event.preventDefault();
    const value = apiKeyInput.value.trim();
    if (!value) {
      settingsStatus.textContent = t("keyMissing");
      return;
    }
    settingsSave.disabled = true;
    try {
      const data = await request("/api/settings", { apiKey: value });
      apiKeyInput.value = "";
      settingsStatus.textContent = data.configured ? t("keySaved") : t("keyMissing");
    } catch (error) {
      settingsStatus.textContent = error.message || t("error");
    } finally {
      settingsSave.disabled = false;
    }
  }

  modeButtons.forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.mode));
  });

  sendButton.addEventListener("click", takeTurn);

  actionBox.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      takeTurn();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (storyView.hidden || event.target === actionBox) {
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      goToPage(pageIndex - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      goToPage(pageIndex + 1);
    }
  });

  pagePrev.addEventListener("click", () => goToPage(pageIndex - 1));
  pageNext.addEventListener("click", () => goToPage(pageIndex + 1));

  restartButton.addEventListener("click", () => {
    const story = storyRoute();
    const caseId = story ? story.caseId : caseInfo && caseInfo.id;
    if (!caseId) {
      return;
    }
    discardSession();
    startStory(caseId, storyLanguage);
  });

  railToggle.addEventListener("click", () => {
    const open = rail.hasAttribute("data-open");
    rail.toggleAttribute("data-open", !open);
    railToggle.setAttribute("aria-expanded", String(!open));
  });

  settingsOpen.addEventListener("click", openSettings);
  settingsClose.addEventListener("click", () => settingsDialog.close());
  settingsForm.addEventListener("submit", saveKey);
  window.addEventListener("hashchange", route);

  paintStatic();
  route();
  refreshRail();
})();
