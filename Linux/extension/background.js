chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "sendToPyIconic",
    title: "Download with PyIconic",
    contexts: ["link"]
  });
});


chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.url) {
    chrome.runtime.sendNativeMessage("com.pyiconic.downloader", { url: message.url }, (response) => {
      if (chrome.runtime.lastError) {
        // App not running / native host not responding
        alert("⚠️ Can't connect to PyIconic. Please make sure the app is running and browser integration is enabled.");
        return;
      }

      if (response && response.status === "queued") {
        chrome.notifications.create({
          type: "basic",
          iconUrl: "icons/icon128.png",
          title: "PyIconic",
          message: `Download queued:\n${response.url}`
        });
      } else {
        chrome.notifications.create({
          type: "basic",
          iconUrl: "icons/icon128.png",
          title: "PyIconic Downloader",
          message: "Something went wrong while sending to PyIconic."
        });
      }
    });
  }
});


chrome.contextMenus.onClicked.addListener((info, tab) => {
  const message = { url: info.linkUrl };

  chrome.runtime.sendNativeMessage("com.pyiconic.downloader", message, (response) => {
    console.log("[PyIconic] Context menu triggered for:", message.url);
    
    if (chrome.runtime.lastError) {
      console.error("Native Messaging Error:", chrome.runtime.lastError.message);
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/icon128.png",
        title: "PyIconic Downloader",
        message: "Failed to send URL to PyIconic app."
      });
    } else {
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icons/icon128.png",
        title: "PyIconic",
        message: `Download started for:\n${response.url}`
      });
    }
  });
});


// chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
//   if (message.url) {
//     console.log("[PyIconic] Received message from content.js:", message.url); // ✅ Add this

//     chrome.runtime.sendNativeMessage("com.pyiconic.downloader", { url: message.url }, (response) => {
//       console.log("[PyIconic] Response from native app:", response); // ✅ Log this
//       if (!chrome.runtime.lastError && response.status === "queued") {
//         chrome.notifications.create({
//           type: "basic",
//           iconUrl: "icons/icon128.png",
//           title: "PyIconic",
//           message: `Download started for:\n${response.url}`
//         });
//       } else {
//         chrome.notifications.create({
//           type: "basic",
//           iconUrl: "icons/icon128.png",
//           title: "PyIconic Downloader",
//           message: "Failed to send URL to PyIconic app."
//         });
//       }
//     });
//   }
// });







  
  // chrome.contextMenus.onClicked.addListener((info, tab) => {
  //   const message = { url: info.linkUrl };
  //   chrome.runtime.sendNativeMessage("com.pyiconic.downloader", message, (response) => {
  //     if (chrome.runtime.lastError) {
  //       console.error("Native Messaging Error:", chrome.runtime.lastError.message);
  //     } else {
  //       console.log("Response from PyIconic:", response);
  //     }
  //   });
  // });
  