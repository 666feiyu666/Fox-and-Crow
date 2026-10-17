(() => {
  "use strict";

  const I18N = {
    en: {
      restart: "Restart",
      languageLabel: "中文",
      switchLanguage: "Switch language",
      youAre: "You are {name}",
      day: "Day {n}",
      turnLabel: "Turn {n}",
      morning: "morning",
      afternoon: "afternoon",
      evening: "evening",
      remaining: "of the day left",
      say: "Say",
      do: "Do",
      placeholderSay: "One line you say…",
      placeholderDo: "One action you attempt…",
      send: "Send",
      thinking: "The Storyteller is judging your line…",
      tryNext: "Could try",
      newMorning: "Another morning",
      dayClosed: "The day ends",
      endingTitle: "The story has ended",
      endingText: "Start a new story to play again.",
      ended: "This story has ended. Restart to begin a new one.",
      error: "The story could not continue. Try again.",
      note:
        "A storyteller reads each line and decides what it changes. Nothing is scripted in advance.",
    },
    zh: {
      restart: "重新开始",
      languageLabel: "English",
      switchLanguage: "切换语言",
      youAre: "你扮演{name}",
      day: "第{n}天",
      turnLabel: "第 {n} 轮",
      morning: "清晨",
      afternoon: "午后",
      evening: "黄昏",
      remaining: "日内剩余时间",
      say: "说",
      do: "做",
      placeholderSay: "你说一句话……",
      placeholderDo: "你尝试一个动作……",
      send: "继续",
      thinking: "讲故事的人正在裁定你这一句……",
      tryNext: "可以试试",
      newMorning: "又一个清晨",
      dayClosed: "这一天结束了",
      endingTitle: "故事结束了",
      endingText: "重新开始，可以再玩一次。",
      ended: "这个故事已经结束，重新开始才能继续。",
      error: "故事暂时无法继续，请再试一次。",
      note: "讲故事的人读你写的每一句，再决定它改变了什么。故事没有任何预写剧本。",
    },
  };

  const log = document.getElementById("log");
  const actionBox = document.getElementById("action");
  const sendButton = document.getElementById("send");
  const message = document.getElementById("message");
  const hints = document.getElementById("hints");
  const ending = document.getElementById("ending");
  const endingTitle = document.getElementById("ending-title");
  const endingText = document.getElementById("ending-text");
  const dayLabel = document.getElementById("day-label");
  const phaseLabel = document.getElementById("phase-label");
  const clock = document.getElementById("clock");
  const remainingLabel = document.getElementById("remaining-label");
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
  let state = { turn: 0, day: 1, hasClock: false, ended: false };

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
    sendButton.disabled = value || state.ended;
    actionBox.disabled = value || state.ended;
    modeButtons.forEach((button) => {
      button.disabled = value || state.ended;
    });
  }

  function applyCase() {
    if (!caseInfo) {
      return;
    }
    const title = caseInfo.title?.[language] || caseInfo.title?.en || "";
    storyTitle.textContent = title;
    subtitle.textContent = t("youAre", { name: caseInfo.playerCharacter });
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
    endingTitle.textContent = t("endingTitle");
    endingText.textContent = t("endingText");
    applyCase();
    renderStatus();
    if (state.ended) {
      setMessage("ended");
    } else if (messageKey) {
      message.textContent = t(messageKey);
    }
  }

  function renderStatus() {
    if (state.hasClock) {
      dayLabel.textContent = t("day", { n: state.day });
      phaseLabel.textContent = t(state.phase);
      phaseLabel.hidden = false;
      clock.hidden = false;
      clock.replaceChildren(
        ...Array.from({ length: state.totalUnits }, (_, index) => {
          const pip = document.createElement("span");
          pip.className = index < state.elapsedUnits ? "pip used" : "pip";
          return pip;
        }),
      );
      remainingLabel.textContent = `${state.remainingUnits} / ${state.totalUnits} ${t("remaining")}`;
      return;
    }
    dayLabel.textContent = t("turnLabel", { n: state.turn });
    phaseLabel.hidden = true;
    clock.hidden = true;
    clock.replaceChildren();
    remainingLabel.textContent = "";
  }

  function addBlock(className) {
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
    const article = addBlock("opening");
    const body = document.createElement("div");
    body.className = "narration";
    renderParagraphs(body, text);
    article.appendChild(body);
    log.appendChild(article);
  }

  function addAction(type, text) {
    const article = addBlock("turn");
    const line = document.createElement("p");
    line.className = "action";
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = t(type);
    line.append(tag, document.createTextNode(type === "say" ? `“${text}”` : text));
    article.appendChild(line);
  }

  function addNarration(text) {
    const article = addBlock("turn");
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

  function showEnding() {
    ending.hidden = false;
    setHints([]);
    setMessage("ended");
    sendButton.disabled = true;
    actionBox.disabled = true;
    modeButtons.forEach((button) => {
      button.disabled = true;
    });
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
    ending.hidden = true;
    hasTurns = false;
    setMessage(null);
    setBusy(true);
    try {
      const data = await request("/api/session", { language });
      sessionId = data.sessionId;
      caseInfo = data.case;
      state = data.playerState;
      addOpening(data.opening.text);
      paintChrome();
    } catch (error) {
      setMessage(error.key || null, error.message || t("error"));
    } finally {
      setBusy(false);
    }
    actionBox.focus();
  }

  async function takeTurn() {
    if (busy || state.ended || !sessionId) {
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
    const pending = addBlock("pending");
    const pendingBody = document.createElement("div");
    pendingBody.className = "narration";
    pendingBody.textContent = t("thinking");
    pending.appendChild(pendingBody);

    try {
      const data = await request("/api/turn", { sessionId, type: chosenType, text });
      pending.remove();
      const events = data.events || [];
      if (events.includes("day_reset")) {
        addDivider(t("newMorning"));
      }
      if (events.includes("day_closed")) {
        addDivider(t("dayClosed"));
      }
      addNarration(data.narration);
      state = data.playerState;
      hasTurns = true;
      renderStatus();
      setHints(data.hints);
      setMessage(null);
      if (state.ended) {
        showEnding();
      }
    } catch (error) {
      pending.remove();
      setMessage(error.key || null, error.message || t("error"));
    } finally {
      setBusy(false);
      if (!state.ended) {
        actionBox.focus();
      }
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
