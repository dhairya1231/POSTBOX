const state = {
  emails: [],
  selectedId: null,
  replyTo: null,      // { to, subject, threadId } when replying
};

// ---------- Init ----------

async function init() {
  const res = await fetch("/auth/status");
  const { logged_in } = await res.json();

  if (logged_in) {
    document.getElementById("login-screen").classList.add("hidden");
    document.getElementById("app").classList.remove("hidden");
    loadInbox();
  } else {
    document.getElementById("login-screen").classList.remove("hidden");
    document.getElementById("app").classList.add("hidden");
  }
}

document.getElementById("login-btn").addEventListener("click", () => {
  window.location.href = "/auth/login";
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/auth/logout", { method: "POST" });
  window.location.reload();
});

// ---------- Tabs ----------

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`${btn.dataset.tab}-view`).classList.add("active");
  });
});

function goToComposeTab() {
  document.querySelector('[data-tab="compose"]').click();
}

// ---------- Inbox ----------

async function loadInbox(query = "") {
  const list = document.getElementById("mail-list");
  list.innerHTML = `<div class="empty-state">Loading your inbox…</div>`;

  try {
    const res = await fetch(`/api/emails?max_results=25&q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error((await res.json()).detail || "Failed to load inbox");
    state.emails = await res.json();
    renderMailList();
  } catch (err) {
    list.innerHTML = `<div class="empty-state">${escapeHtml(err.message)}</div>`;
  }
}

function renderMailList() {
  const list = document.getElementById("mail-list");
  if (state.emails.length === 0) {
    list.innerHTML = `<div class="empty-state">No mail found.</div>`;
    return;
  }

  list.innerHTML = "";
  state.emails.forEach((mail) => {
    const item = document.createElement("div");
    item.className = "mail-item" + (mail.unread ? " unread" : "") + (mail.id === state.selectedId ? " active" : "");
    item.innerHTML = `
      <div class="mail-from">${escapeHtml(shortenSender(mail.from))}</div>
      <div class="mail-subject">${escapeHtml(mail.subject)}</div>
      <div class="mail-snippet">${escapeHtml(mail.snippet)}</div>
    `;
    item.addEventListener("click", () => openMail(mail.id));
    list.appendChild(item);
  });
}

function shortenSender(from) {
  const match = from.match(/^(.*?)</);
  return match ? match[1].trim() : from;
}

async function openMail(id) {
  state.selectedId = id;
  renderMailList();

  document.getElementById("reading-empty").classList.add("hidden");
  document.getElementById("reading-content").classList.remove("hidden");
  document.getElementById("reading-subject").textContent = "Loading…";
  document.getElementById("reading-body").textContent = "";

  const res = await fetch(`/api/emails/${id}`);
  if (!res.ok) {
    document.getElementById("reading-subject").textContent = "Couldn't load this email.";
    return;
  }
  const mail = await res.json();

  document.getElementById("reading-subject").textContent = mail.subject;
  document.getElementById("reading-from").textContent = mail.from;
  document.getElementById("reading-date").textContent = mail.date;
  document.getElementById("reading-body").textContent = stripHtml(mail.body);

  document.getElementById("reply-btn").onclick = () => {
    state.replyTo = {
      to: extractEmail(mail.from),
      subject: mail.subject.startsWith("Re:") ? mail.subject : `Re: ${mail.subject}`,
      threadId: mail.threadId,
    };
    document.getElementById("compose-to").value = state.replyTo.to;
    document.getElementById("compose-subject").value = state.replyTo.subject;
    document.getElementById("compose-context").value = `Reply to this email:\n"${stripHtml(mail.body).slice(0, 500)}"\n\nMy reply should say: `;
    goToComposeTab();
    document.getElementById("compose-context").focus();
  };
}

function extractEmail(from) {
  const match = from.match(/<(.+?)>/);
  return match ? match[1] : from;
}

function stripHtml(text) {
  const div = document.createElement("div");
  div.innerHTML = text;
  return div.textContent || div.innerText || "";
}

document.getElementById("refresh-btn").addEventListener("click", () => loadInbox(document.getElementById("search-input").value));
document.getElementById("search-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadInbox(e.target.value);
});

// ---------- Compose ----------

document.getElementById("draft-btn").addEventListener("click", async () => {
  const context = document.getElementById("compose-context").value.trim();
  const tone = document.getElementById("compose-tone").value.trim();
  const to = document.getElementById("compose-to").value.trim();
  const statusEl = document.getElementById("draft-status");
  const btn = document.getElementById("draft-btn");

  if (!context) {
    statusEl.textContent = "Add some context first — what should this email say?";
    statusEl.className = "status-line error";
    return;
  }

  btn.disabled = true;
  statusEl.className = "status-line";
  statusEl.textContent = "Drafting…";

  try {
    const res = await fetch("/api/compose/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context, recipient_hint: to, tone }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Drafting failed");
    const draft = await res.json();

    document.getElementById("compose-subject").value = draft.subject;
    document.getElementById("compose-body").value = draft.body;
    statusEl.textContent = "Draft ready — review and edit before sending.";
    statusEl.className = "status-line success";
  } catch (err) {
    statusEl.textContent = err.message;
    statusEl.className = "status-line error";
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("send-btn").addEventListener("click", async () => {
  const to = document.getElementById("compose-to").value.trim();
  const subject = document.getElementById("compose-subject").value.trim();
  const body = document.getElementById("compose-body").value.trim();
  const statusEl = document.getElementById("send-status");
  const btn = document.getElementById("send-btn");

  if (!to || !subject || !body) {
    statusEl.textContent = "To, subject, and body are all required.";
    statusEl.className = "status-line error";
    return;
  }

  btn.disabled = true;
  statusEl.className = "status-line";
  statusEl.textContent = "Sending…";

  try {
    const res = await fetch("/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to, subject, body,
        thread_id: state.replyTo ? state.replyTo.threadId : null,
      }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Send failed");

    statusEl.textContent = "Sent.";
    statusEl.className = "status-line success";
    state.replyTo = null;
    document.getElementById("compose-to").value = "";
    document.getElementById("compose-subject").value = "";
    document.getElementById("compose-body").value = "";
    document.getElementById("compose-context").value = "";
    document.getElementById("compose-tone").value = "";
  } catch (err) {
    statusEl.textContent = err.message;
    statusEl.className = "status-line error";
  } finally {
    btn.disabled = false;
  }
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

init();
