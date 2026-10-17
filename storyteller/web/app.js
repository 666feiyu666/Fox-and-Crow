(() => {
  "use strict";

  const I18N = {
    en: {
      restart: "Restart",
      languageLabel: "中文",
      switchLanguage: "Switch language",
      youAre: "You are {name}",
      turnLabel: "Turn {n}",
      say: "Say",
      do: "Do",
      placeholderSay: "One line you say…",
      placeholderDo: "One action you attempt…",
      send: "Send",
      thinking: "The storyteller is thinking…",
      tryNext: "Could try",
      error: "The story could not continue. Try again.",
      note: "Nothing is scripted. Every line you write is answered by the storyteller.",
    },
    zh: {
      restart: "重新开始",
      languageLabel: "English",
      switchLanguage: "切换语言",
      youAre: "你扮演{name}",
      turnLabel: "第 {n} 轮",
      say: "说",
      do: "做",
      placeholderSay: "你说一句话……",
      placeholderDo: "你尝试一个动作……",
      send: "继续",
      thinking: "讲故事的人正在想……",
      tryNext: "可以试试",
      error: "故事暂时无法继续，请再试一次。",
      note: "没有任何预写剧本。你写的每一句，都会由讲故事的人接着讲下去。",
    },
  };

  const log = document.getElementById("log");
  const actionBox = document.getElementById("action");
  const sendButton = document.getElementById("send");
  const message = document.getElementById("message");
  const hints = document.getElementById("hints");
  const turnLabel = document.getElementById("turn-label");
  const restartButton = document.getElementById("restart");
  const languageButton = document.getElementById("language");
  const note = document.getElementById("note");
  const storyTitle = document.getElementById("story-title");
  const subtitle = document.getElementById("story-subtitle");
  const modeButtons = Array.from(document.querySelectorAll("[data-mode]"));

  let language = document.documentElement.lang === "zh" ? "zh" : "en";
  let sessionId = null;
  let caseInfo = null;
  let mode = "say";
  let busy = false;
  let hasTurns = false;
  let messageKey = null;
  let turn = 0;

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
    sendButton.disabled = value;
    actionBox.disabled = value;
    modeButtons.forEach((button) => {
      button.disabled = value;
    });
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
    subtitle.textContent = t("youAre", { name: caseText(caseInfo.player) });
    document.title = title;
  }

  function paintChrome() {
    document.documentElement.lang = language;
    restartButton.textContent = t("restart");
    languageButton.textContent = t("languageLabel");
    languageButton.setAttribute("aria-label", t("switchLanguage"));
    actionBox.placeholder = fromTable(mode === "say" ? "placeholderSay" : "placeholderDo");
    sendButton.textContent = t("send");
    note.textContent = t("note");
    modeButtons.forEach((button) => {
      button.textContent = fromTable(button.dataset.mode === "say" ? "say" : "do");
      button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
    });
    applyCase();
    turnLabel.textContent = t("turnLabel", { n: turn });
    if (messageKey) {
      message.textContent = t(messageKey);
    }
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
    const article = addEntry("turn");
    const body = document.createElement("div");
    body.className = "narration";
    renderParagraphs(body, text);
    article.appendChild(body);
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
    let response;
    try {
      response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
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

  async function start() {
    log.replaceChildren();
    hints.replaceChildren();
    hasTurns = false;
    turn = 0;
    setMessage(null);
    setBusy(true);
    try {
      const data = await request("/api/session", { language });
      sessionId = data.sessionId;
      caseInfo = data.case;
      turn = data.playerState.turn;
      addOpening(data.opening);
      paintChrome();
    } catch (error) {
      setMessage(error.key || null, error.message || t("error"));
    } finally {
      setBusy(false);
    }
    actionBox.focus();
  }

  async function takeTurn() {
    if (busy || !sessionId) {
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
      turn = data.playerState.turn;
      hasTurns = true;
      turnLabel.textContent = t("turnLabel", { n: turn });
      setHints(data.hints);
      setMessage(null);
    } catch (error) {
      pending.remove();
      setMessage(error.key || null, error.message || t("error"));
    } finally {
      setBusy(false);
      actionBox.focus();
    }
  }

  function setMode(next) {
    mode = next;
    paintChrome();
    actionBox.focus();
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
    if (sessionId) {
      const stale = sessionId;
      sessionId = null;
      fetch("/api/session/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: stale }),
      }).catch(() => {});
    }
    start();
  });

  languageButton.addEventListener("click", () => {
    language = language === "en" ? "zh" : "en";
    paintChrome();
    if (hasTurns) {
      restartButton.click();
    } else if (!sessionId) {
      start();
    }
  });

  paintChrome();
  start();
})();
