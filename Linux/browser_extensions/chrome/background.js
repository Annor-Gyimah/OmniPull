// background.js (MV3, Chrome, "type": "module")

// --- Build/version marker ---
const VERSION = chrome.runtime.getManifest().version;
console.log(`[OmniPull BG] loaded, version=${VERSION}`);

// --- Helpers ---
function notify(message, title = "OmniPull") {
  chrome.notifications.create(
    {
      type: "basic",
      iconUrl: chrome.runtime.getURL("icons/logo4.png"),
      title,
      message,
      priority: 2
    },
    () => {
      if (chrome.runtime.lastError) {
        console.warn("[OmniPull] notification error:", chrome.runtime.lastError.message);
      }
    }
  );
}

function flashBadge(text = "✓", ms = 1200) {
  if (!chrome.action) return;
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color: [0, 128, 0, 255] });
  setTimeout(() => chrome.action.setBadgeText({ text: "" }), ms);
}

// Native host response helpers
function isNativeError(resp) {
  if (!resp) return false;
  if (typeof resp === "object") {
    if (resp.status && String(resp.status).toLowerCase() === "error") return true;
    if (resp.error) return true;
  }
  return false;
}

function isNativeSuccess(resp) {
  if (isNativeError(resp)) return false;
  if (resp == null) return true; // treat empty as success if no lastError
  if (typeof resp === "string") return /queued|ok|success/i.test(resp);
  if (typeof resp === "object") {
    if (resp.ok === true || resp.success === true) return true;
    if (typeof resp.status === "string" && /queued|ok|success/i.test(resp.status)) return true;
    if (typeof resp.result === "string" && /queued|ok|success/i.test(resp.result)) return true;
    if ("id" in resp || "jobId" in resp || "queueId" in resp) return true;
  }
  return false;
}

function successMessage(resp, url) {
  if (resp && typeof resp === "object") {
    const id = resp.id ?? resp.jobId ?? resp.queueId;
    if (id) return `Queued (#${id}):\n${url}`;
    if (typeof resp.message === "string" && resp.message.trim()) return resp.message;
  } else if (typeof resp === "string" && resp.trim()) {
    return resp;
  }
  return `Queued:\n${url}`;
}

function errorMessage(resp, fallback = "Native app error") {
  if (typeof resp === "string") return resp;
  if (resp && typeof resp === "object") {
    if (typeof resp.message === "string" && resp.message.trim()) return resp.message;
    if (typeof resp.error === "string" && resp.error.trim()) return resp.error;
  }
  return fallback;
}

// --- Context menu setup (idempotent) ---
const MENU_ID = "sendToOmniPull";

function ensureContextMenus() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create(
      { id: MENU_ID, title: "Download with OmniPull", contexts: ["link"] },
      () => {
        const err = chrome.runtime.lastError;
        if (err) console.warn("[OmniPull] contextMenus.create error:", err.message);
        else console.log("[OmniPull] context menu ensured");
      }
    );
  });
}

chrome.runtime.onInstalled.addListener(() => {
  console.log("[OmniPull] onInstalled");
  ensureContextMenus();
});
chrome.runtime.onStartup.addListener(() => {
  console.log("[OmniPull] onStartup");
  ensureContextMenus();
});
self.addEventListener("activate", () => {
  console.log("[OmniPull] activate");
  ensureContextMenus();
});

// --- Content script -> background bridge ---
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object" || !message.url) {
    sendResponse?.({ ok: false, error: "invalid_message" });
    return; // sync path
  }

  const url = String(message.url);
  console.log("[OmniPull] CS request:", { url, fromTab: sender?.tab?.id });

  chrome.runtime.sendNativeMessage("com.omnipull.downloader", { url }, (resp) => {
    const err = chrome.runtime.lastError;
    try { console.log("[OmniPull] native resp (CS):", typeof resp, resp); } catch {}

    if (err) {
      console.error("[OmniPull] Native host error:", err.message);
      notify("Can't connect to OmniPull native app.");
      sendResponse?.({ ok: false, error: "native_host_unavailable" });
      return;
    }

    if (isNativeError(resp)) {
      const msg = errorMessage(resp, "Native app reported an error.");
      notify(`OmniPull error:\n${msg}`);
      sendResponse?.({ ok: false, error: "native_error", resp });
      return;
    }

    if (isNativeSuccess(resp)) {
      notify(successMessage(resp, url));
      flashBadge("✓");
      sendResponse?.({ ok: true, resp });
    } else {
      notify("Unexpected reply from OmniPull app. See service worker console.");
      sendResponse?.({ ok: false, error: "unexpected_native_response", resp });
    }
  });

  return true; // keep the channel open for async sendResponse
});

// --- Context menu -> background ---
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== MENU_ID) return;

  const url = info?.linkUrl ? String(info.linkUrl) : "";
  if (!url) {
    console.warn("[OmniPull] menu clicked but no linkUrl found");
    return;
  }

  console.log("[OmniPull] menu click:", { url, tabId: tab?.id });

  chrome.runtime.sendNativeMessage("com.omnipull.downloader", { url }, (resp) => {
    const err = chrome.runtime.lastError;
    try { console.log("[OmniPull] native resp (menu):", typeof resp, resp); } catch {}

    if (err) {
      console.error("[OmniPull] Native Messaging Error:", err.message);
      notify("Failed to send URL to OmniPull app.");
      return;
    }

    if (isNativeError(resp)) {
      const msg = errorMessage(resp, "Native app reported an error.");
      notify(`OmniPull error:\n${msg}`);
      return;
    }

    if (isNativeSuccess(resp)) {
      notify(successMessage(resp, url));
      flashBadge("✓");
    } else {
      notify("Unexpected reply from OmniPull app. See service worker console.");
    }
  });
});