// Create the context menu on install/update
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "sendToOmniPull",
    title: "Download with OmniPull",
    contexts: ["link"]
  });
});

// Content script → background
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Guard against undefined / non-object messages
  if (!message || typeof message !== "object" || !message.url) {
    // Respond with a small, cloneable error
    sendResponse?.({ ok: false, error: "invalid_message" });
    return; // synchronous listener, no async pending
  }

  const payload = { url: String(message.url) };

  chrome.runtime.sendNativeMessage("com.omnipull.downloader", payload, (response) => {
    const lastErr = chrome.runtime.lastError;
    if (lastErr) {
      console.error("[OmniPull] Native host error:", lastErr.message);
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/logo4.png",
        title: "OmniPull",
        message: "Can't connect to OmniPull native app."
      });
      sendResponse?.({ ok: false, error: "native_host_unavailable" });
      return;
    }

    // keep responses tiny & plain
    if (response && response.status === "queued") {
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/logo4.png",
        title: "OmniPull",
        message: `Queued:\n${payload.url}`
      });
      sendResponse?.({ ok: true });
    } else {
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/logo4.png",
        title: "OmniPull",
        message: "Native host responded unexpectedly."
      });
      sendResponse?.({ ok: false, error: "unexpected_native_response" });
    }
  });

  // Tell Firefox we'll reply asynchronously
  return true;
});

// Context-menu → background
chrome.contextMenus.onClicked.addListener((info, tab) => {
  const url = info && info.linkUrl ? String(info.linkUrl) : "";
  if (!url) return;

  chrome.runtime.sendNativeMessage("com.omnipull.downloader", { url }, (response) => {
    if (chrome.runtime.lastError) {
      console.error("[OmniPull] Native Messaging Error:", chrome.runtime.lastError.message);
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/logo4.png",
        title: "OmniPull",
        message: "Failed to send URL to OmniPull app."
      });
      return;
    }

    chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/logo4.png",
      title: "OmniPull",
      message: `Queued:\n${url}`
    });
  });
});