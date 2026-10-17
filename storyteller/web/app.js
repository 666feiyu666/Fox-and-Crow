(() => {
  "use strict";

  const I18N = {
    en: {
      shelfTitle: "Playable stories",
      shelfLede:
        "Every story here arrives as a bare tale. Before you begin, it is read once: the role you take, the world around you and the first passage all come from the words that were already there.",
      readThis: "Read this one",
      back: "All stories",
      shelfEmpty: "No stories are on the shelf yet.",
      shelfError: "The shelf could not be opened. Try again.",
      restart: "Restart",
      languageLabel: "中文",
      switchLanguage: "Switch language",
      youAre: "You are {name}",
      loopCount: "Loop {n}",
      turnCount: "Turn {n}",
      again: "Another beginning",
      ended: "The story has ended. Restart to begin again.",
      inputLabel: "Your line or action",
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
      understandingReused: "Opening the story…",
      tryNext: "Could try",
      error: "The story could not continue. Try again.",
      note: "Nothing is scripted. Every line you write is answered by the storyteller.",
    },
    zh: {
      shelfTitle: "讲故事的人",
      shelfLede:
        "这里的每个故事都只带来原文。开始之前，它会被读一次：你扮演谁、周围是怎样的世界、开场那一段，都从那几行原文里长出来。",
      readThis: "读这一篇",
      back: "所有故事",
      shelfEmpty: "书架上还没有故事。",
      shelfError: "书架没有打开，请再试一次。",
      restart: "重新开始",
      languageLabel: "English",
      switchLanguage: "切换语言",
      youAre: "你扮演 {name}",
      loopCount: "第 {n} 次",
      turnCount: "第 {n} 轮",
      again: "又一次开始",
      ended: "故事结束了。重新开始可以再来一次。",
      inputLabel: "你说的话，或你做的事",
      say: "说",
      do: "做",
      placeholderSay: "你说一句话……",
      placeholderDo: "你尝试一个动作……",
      send: "继续",
      thinking: "讲故事的人正在想……",
      understandingTitle: "understander 正在读你传入的这个故事……",
      understandingBody: "它读你传入的原故事，推导出你扮演谁、世界是什么样，以及开场。",
      understandingSlow: "第一次要通读原文，可能要等一会儿。",
      understandingReused: "正在打开这个故事……",
      tryNext: "可以试试",
      error: "故事暂时无法继续，请再试一次。",
      note: "没有任何预写剧本。你写的每一句，都会由讲故事的人接着讲下去。",
    },
  };

  const STORY_ROUTE = /^#\/story\/([^/]+)$/;

  const shelfView = document.getElementById("shelf-view");
  const shelfTitle = document.getElementById("shelf-title");
  const shelfLede = document.getElementById("shelf-lede");
  const shelfList = document.getElementById("shelf-list");
  const shelfMessage = document.getElementById("shelf-message");
  const shelfLanguage = document.getElementById("shelf-language");
  const storyView = document.getElementById("story-view");
  const log = document.getElementById("log");
  const actionBox = document.getElementById("action");
  const sendButton = document.getElementById("send");
  const message = document.getElementById("message");
  const hints = document.getElementById("hints");
  const loopLabel = document.getElementById("loop-label");
  const turnLabel = document.getElementById("turn-label");
  const restartButton = document.getElementById("restart");
  const languageButton = document.getElementById("language");
  const backButton = document.getElementById("back");
  const note = document.getElementById("note");
  const storyTitle = document.getElementById("story-title");
  const inputLabel = document.getElementById("input-label");
  const subtitle = document.getElementById("story-subtitle");
  const modeButtons = Array.from(document.querySelectorAll("[data-mode]"));

  let language = document.documentElement.lang === "zh" ? "zh" : "en";
  let sessionId = null;
  let caseInfo = null;
  let mode = "say";
  let busy = false;
  let messageKey = null;
  let loop = 1;
  let turn = 0;
  let ended = false;
  let shelfEntries = null;
  const derivedLanguages = new Set();
  const UNDERSTANDING_SLOW_MS = 2500;

  function t(key, vars) {
    const template = I18N[language][key] ?? I18N.en[key] ?? key;
    if (!vars) {
      return template;
    }
    return template.replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ""));
  }

  function fromTable(key, language_ = language) {
    return I18N[language_][key] ?? I18N.en[key] ?? key;
  }

  function setMessage(key, text) {
    messageKey = key;
    message.textContent = key ? t(key) : text || "";
  }

  function setBusy(value) {
    busy = value;
    sendButton.disabled = value || ended;
    actionBox.disabled = value || ended;
    modeButtons.forEach((button) => {
      button.disabled = value || ended;
    });
  }

  function renderStatus() {
    loopLabel.textContent = t("loopCount", { n: loop });
    turnLabel.textContent = t("turnCount", { n: turn });
  }

  function caseText(table) {
    return (table && (table[language] || table.en)) || "";
  }

  function applyCase() {
    if (!caseInfo) {
      return;
    }
    const title = caseText(caseInfo.title);
    storyTitle.textContent = title;
    subtitle.textContent = t("youAre", { name: caseInfo.player || "" });
    document.title = title;
  }

  function paintChrome() {
    document.documentElement.lang = language;
    restartButton.textContent = t("restart");
    languageButton.textContent = t("languageLabel");
    languageButton.setAttribute("aria-label", t("switchLanguage"));
    backButton.textContent = t("back");
    actionBox.placeholder = fromTable(mode === "say" ? "placeholderSay" : "placeholderDo");
    sendButton.textContent = t("send");
    inputLabel.textContent = t("inputLabel");
    note.textContent = t("note");
    modeButtons.forEach((button) => {
      button.textContent = fromTable(button.dataset.mode === "say" ? "say" : "do");
      button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
    });
    applyCase();
    renderStatus();
    if (messageKey) {
      message.textContent = t(messageKey);
    }
  }

  function paintShelf() {
    shelfTitle.textContent = t("shelfTitle");
    shelfLede.textContent = t("shelfLede");
    shelfLanguage.textContent = t("languageLabel");
    shelfLanguage.setAttribute("aria-label", t("switchLanguage"));
    shelfList.setAttribute("aria-label", t("shelfTitle"));
  }

  function addEntry(className) {
    const article = document.createElement("article");
    article.className = `entry ${className}`;
    log.appendChild(article);
    return article;
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

  function addOpening(text) {
    const article = addEntry("opening");
    const body = document.createElement("div");
    body.className = "narration";
    renderParagraphs(body, text);
    article.appendChild(body);
  }

  function addUnderstandingNotice(language_) {
    const article = addEntry("understanding");
    const derived = derivedLanguages.has(language_);
    const heading = document.createElement("p");
    heading.className = "understanding-heading";
    heading.textContent = t(derived ? "understandingReused" : "understandingTitle");
    article.appendChild(heading);
    if (derived) {
      return { article, slowLine: null };
    }
    const body = document.createElement("p");
    body.textContent = t("understandingBody");
    const slowLine = document.createElement("p");
    slowLine.className = "understanding-slow";
    slowLine.textContent = t("understandingSlow");
    slowLine.hidden = true;
    article.append(body, slowLine);
    return { article, slowLine };
  }

  function addAction(type, text) {
    const article = addEntry("turn");
    const line = document.createElement("p");
    line.className = "action";
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = t(type);
    line.append(tag, document.createTextNode(type === "say" ? `“${text}”` : text));
    article.appendChild(line);
  }

  function addNarration(text) {
    const article = addEntry("turn fresh");
    const body = document.createElement("div");
    body.className = "narration";
    renderParagraphs(body, text);
    article.appendChild(body);
  }

  function addDivider(text) {
    const divider = document.createElement("div");
    divider.className = "divider";
    divider.textContent = text;
    log.appendChild(divider);
  }

  function setHints(items) {
    hints.replaceChildren(
      ...(items || []).map((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = item;
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

  function storyCaseId() {
    const match = STORY_ROUTE.exec(window.location.hash);
    return match ? decodeURIComponent(match[1]) : null;
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

  function shelfItem(entry) {
    const item = document.createElement("li");
    item.className = "story-item";
    const link = document.createElement("a");
    link.className = "story-link";
    link.href = `#/story/${encodeURIComponent(entry.id)}`;
    const name = document.createElement("h2");
    name.className = "story-name";
    name.textContent = caseText(entry.title);
    const quote = document.createElement("p");
    quote.className = "story-quote";
    quote.textContent = `“${caseText(entry.excerpt)}”`;
    const open = document.createElement("span");
    open.className = "story-open";
    open.textContent = t("readThis");
    link.append(name, quote, open);
    item.appendChild(link);
    return item;
  }

  async function renderShelf() {
    paintShelf();
    shelfMessage.textContent = "";
    if (shelfEntries === null) {
      try {
        const data = await request("/api/cases");
        shelfEntries = data.cases || [];
      } catch (error) {
        shelfEntries = null;
        shelfMessage.textContent = t("shelfError");
        return;
      }
    }
    shelfList.replaceChildren(...shelfEntries.map(shelfItem));
    if (!shelfEntries.length) {
      shelfMessage.textContent = t("shelfEmpty");
    }
  }

  function showShelf() {
    discardSession();
    sessionId = null;
    caseInfo = null;
    storyView.hidden = true;
    shelfView.hidden = false;
    document.title = t("shelfTitle");
    renderShelf();
  }

  function showStory(caseId) {
    shelfView.hidden = true;
    storyView.hidden = false;
    start(caseId);
  }

  function route() {
    const caseId = storyCaseId();
    if (caseId) {
      showStory(caseId);
    } else {
      showShelf();
    }
  }

  async function start(caseId) {
    const requested = language;
    log.replaceChildren();
    hints.replaceChildren();
    turn = 0;
    setMessage(null);
    setBusy(true);
    const notice = addUnderstandingNotice(requested);
    const slowTimer = notice.slowLine
      ? setTimeout(() => {
          notice.slowLine.hidden = false;
        }, UNDERSTANDING_SLOW_MS)
      : null;
    try {
      const data = await request("/api/session", { language: requested, case: caseId });
      sessionId = data.sessionId;
      caseInfo = data.case;
      loop = data.playerState.loop;
      turn = data.playerState.turn;
      ended = data.playerState.ended;
      if (data.understandingSource === "derived") {
        derivedLanguages.add(`${caseId}/${requested}`);
      }
      addOpening(data.opening);
      paintChrome();
    } catch (error) {
      setMessage(error.key || null, error.message || t("error"));
    } finally {
      if (slowTimer !== null) {
        clearTimeout(slowTimer);
      }
      notice.article.remove();
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
    addAction(chosenType, text);
    const pending = addEntry("pending");
    const pendingBody = document.createElement("div");
    pendingBody.className = "narration";
    pendingBody.textContent = t("thinking");
    pending.appendChild(pendingBody);

    try {
      const data = await request("/api/turn", { sessionId, type: chosenType, text });
      pending.remove();
      addNarration(data.narration);
      loop = data.playerState.loop;
      turn = data.playerState.turn;
      ended = data.playerState.ended;
      if (data.restart) {
        addDivider(t("again"));
      }
      renderStatus();
      setHints(ended ? [] : data.hints);
      setMessage(ended ? "ended" : null);
    } catch (error) {
      pending.remove();
      setMessage(error.key || null, error.message || t("error"));
    } finally {
      setBusy(false);
      if (!ended) {
        actionBox.focus();
      }
    }
  }

  function setMode(next) {
    mode = next;
    paintChrome();
    actionBox.focus();
  }

  function switchLanguage() {
    language = language === "en" ? "zh" : "en";
    paintChrome();
    paintShelf();
    const caseId = storyCaseId();
    if (caseId) {
      discardSession();
      start(caseId);
    } else {
      renderShelf();
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

  restartButton.addEventListener("click", () => {
    const caseId = storyCaseId();
    if (!caseId) {
      return;
    }
    discardSession();
    start(caseId);
  });

  backButton.addEventListener("click", () => {
    window.location.hash = "#/";
  });

  languageButton.addEventListener("click", switchLanguage);
  shelfLanguage.addEventListener("click", switchLanguage);
  window.addEventListener("hashchange", route);

  paintChrome();
  paintShelf();
  route();
})();
