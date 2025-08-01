chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "sendToPyIconic",
    title: "Download with OmniPull",
    contexts: ["link"]
  });
});


chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.url) {
    chrome.runtime.sendNativeMessage("com.omnipull.downloader", { url: message.url }, (response) => {
      if (chrome.runtime.lastError) {
        // App not running / native host not responding
        alert("⚠️ Can't connect to OmniPull. Please make sure the app is running and browser integration is enabled.");
        return;
      }

      if (response && response.status === "queued") {
        chrome.notifications.create({
          type: "basic",
          iconUrl: "icons/logo4.png",
          title: "OmniPull",
          message: `Download queued:\n${response.url}`
        });
      } else {
        chrome.notifications.create({
          type: "basic",
          iconUrl: "icons/logo4.png",
          title: "OmniPull Downloader",
          message: "Something went wrong while sending to OmniPull."
        });
      }
    });
  }
});


chrome.contextMenus.onClicked.addListener((info, tab) => {
  const message = { url: info.linkUrl };

  chrome.runtime.sendNativeMessage("com.omnipull.downloader", message, (response) => {
    console.log("[OmniPull] Context menu triggered for:", message.url);
    
    if (chrome.runtime.lastError) {
      console.error("Native Messaging Error:", chrome.runtime.lastError.message);
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/logo4.png",
        title: "OmniPull Downloader",
        message: "Failed to send URL to OmniPull app."
      });
    } else {
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/logo4.png",
        title: "OmniPull",
        message: `Download started for:\n${response.url}`
      });
    }
  });
});

  