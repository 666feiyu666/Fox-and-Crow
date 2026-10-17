(() => {
  "use strict";

  const I18N = {
    en: {
      restart: "Restart",
      storyTitle: "The Fox and the Crow",
      subtitle: "A Day in Loop",
      languageLabel: "中文",
      switchLanguage: "Switch language",
      day: "Day",
      morning: "morning",
      afternoon: "afternoon",
      evening: "evening",
      remaining: "of the day left",
      say: "Say",
      do: "Do",
      placeholderSay: "One line the fox says…",
      placeholderDo: "One action the fox attempts…",
      send: "Send",
      thinking: "The Storyteller is judging your line…",
      tryNext: "Could try",
      newMorning: "Another morning",
      endingTitle: "The loop has ended",
      endingText:
        "The day moves forward again. Start a new story to meet the crow once more.",
      ended: "This story has ended. Restart to begin a new one.",
      error: "The story could not continue. Try again.",
      note:
        "A storyteller reads each line and decides what it changes. Nothing is scripted in advance.",
    },
    zh: {
      restart: "重新开始",
      storyTitle: "狐狸与乌鸦",
      subtitle: "循环中的一天",
      languageLabel: "English",
      switchLanguage: "切换语言",
      day: "第",
      morning: "清晨",
      afternoon: "午后",
      evening: "黄昏",
      remaining: "日内剩余时间",
      say: "说",
      do: "做",
      placeholderSay: "狐狸说一句话……",
      placeholderDo: "狐狸尝试一个动作……",
      send: "继续",
      thinking: "讲故事的人正在裁定你这一句……",
      tryNext: "可以试试",
      newMorning: "又一个清晨",
      endingTitle: "循环结束了",
      endingText: "时间重新向前走。若要再见到乌鸦，请重新开始一个故事。",
      ended: "这个故事已经结束，重新开始才能继续。",
      error: "故事暂时无法继续，请再试一次。",
      note: "讲故事的人读你写的每一句，再决定它改变了什么。故事没有任何预写剧本。",
    },
  };

  const TOTAL_UNITS = 6;
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
  const subtitle = document.getElementById("story-subtitle");
  const storyTitle = document.getElementById("story-title");
  const languageButton = document.getElementById("language");
  const note = document.getElementById("note");
  const modeButtons = Array.from(document.querySelectorAll("[data-mode]"));

  let language = document.documentElement.lang === "zh" ? "zh" : "en";
  let sessionId = null;
  let mode = "say";
  let busy = false;
  let hasTurns = false;
  let messageKey = null;
  let state = { loop: 1, elapsedUnits: 0, remainingUnits: TOTAL_UNITS, phase: "morning", ended: false };

  const t = (key) => (I18N[language][key] ?? I18N.en[key] ?? key);

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

  function paintChrome() {
    document.documentElement.lang = language;
    restartButton.textContent = t("restart");
    storyTitle.textContent = t("storyTitle");
    subtitle.textContent = t("subtitle");
    document.title = `${t("storyTitle")}: ${t("subtitle")}`;
    languageButton.textContent = t("languageLabel");
    languageButton.setAttribute("aria-label", t("switchLanguage"));
    actionBox.placeholder = mode === "say" ? t("placeholderSay") : t("placeholderDo");
    sendButton.textContent = t("send");
    note.textContent = t("note");
    modeButtons.forEach((button) => {
      const label = button.dataset.mode === "say" ? "say" : "do";
      button.textContent = t(label);
      button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
    });
    endingTitle.textContent = t("endingTitle");
    endingText.textContent = t("endingText");
    renderStatus();
    if (state.ended) {
      setMessage("ended");
    } else if (messageKey) {
      message.textContent = t(messageKey);
    }
  }

  function renderStatus() {
    dayLabel.textContent =
      language === "zh" ? `第${state.loop}天` : `${t("day")} ${state.loop}`;
    phaseLabel.textContent = t(state.phase);
    remainingLabel.textContent = `${state.remainingUnits} / ${TOTAL_UNITS} ${t("remaining")}`;
    clock.replaceChildren(
      ...Array.from({ length: TOTAL_UNITS }, (_, index) => {
        const pip = document.createElement("span");
        pip.className = index < state.elapsedUnits ? "pip used" : "pip";
        return pip;
      }),
    );
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
    const article = document.createElement("article");
    article.className = "entry";
    const body = document.createElement("div");
    body.className = "narration";
    renderParagraphs(body, text);
    article.appendChild(body);
    log.appendChild(article);
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
      state = data.playerState;
      addOpening(data.opening.text);
      renderStatus();
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
      const data = await request("/api/turn", {
        sessionId,
        type: chosenType,
        text,
      });
      pending.remove();
      if ((data.events || []).includes("day_reset")) {
        addDivider(t("newMorning"));
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
    }
  });

  paintChrome();
  start();
})();
