function isDownloadable(link) {
    const downloadableExtensions = ['.mp4', '.mkv', '.pdf', '.zip', '.rar', '.mp3', '.7z', '.tar.gz'];
    return downloadableExtensions.some(ext => link.href && link.href.includes(ext));
  }

  function createOmniPullButton(text = "Download with OmniPull") {
    const btn = document.createElement("button");
    const ICON_URL = chrome.runtime.getURL("icons/logo4.png");
    btn.innerHTML = `<img src="${ICON_URL}" style="width:16px; height:16px; vertical-align:middle; margin-right:6px;"> ${text}`;
    btn.style.display = "inline-flex";
    btn.style.alignItems = "center";
    btn.style.marginLeft = "10px";
    btn.style.padding = "6px 10px";
    btn.style.backgroundColor = "#1e88e5";
    btn.style.color = "white";
    btn.style.border = "none";
    btn.style.borderRadius = "4px";
    btn.style.fontSize = "13px";
    btn.style.cursor = "pointer";
    return btn;
  }
  
  
  function injectDownloadButtons() {
    const links = document.querySelectorAll('a');
    const ICON_URL = chrome.runtime.getURL("icons/logo4.png"); // Use the icon URL from the extension
  
    links.forEach(link => {
      if (isDownloadable(link)) {
        const btn = createOmniPullButton();

        // btn.innerHTML = `<img src="${ICON_URL}" style="width:16px; height:16px; vertical-align:middle; margin-right:6px;"> ${text}`;
        // btn.style.display = "inline-flex";
        // btn.style.alignItems = "center";
        // btn.style.marginLeft = "10px";
        // btn.style.padding = "6px 10px";
        // btn.style.backgroundColor = "#1e88e5";
        // btn.style.color = "white";
        // btn.style.border = "none";
        // btn.style.borderRadius = "4px";
        // btn.style.fontSize = "13px";
        // btn.style.cursor = "pointer";
        
  
        btn.onclick = () => {
          console.log("[OmniPull] Button clicked. Sending:", link.href); // ✅ Log this
          chrome.runtime.sendMessage({ url: link.href });
        };
  
        link.parentElement.insertBefore(btn, link.nextSibling);
      }
    });
  }
  
  injectDownloadButtons();

  

  function injectYouTubeOverlay() {
    // const container = document.querySelector("#info-contents");  // YouTube video title section
    // const container = document.querySelector("#top-row") || document.querySelector("h1.title");
    const container = document.querySelector("#info-contents") 
    || document.querySelector("#top-row") 
    || document.querySelector("h1.title");


  
    if (container && !document.getElementById("OmniPull-yt-btn")) {
      const btn = createOmniPullButton("Download with OmniPull");
      btn.id = "OmniPull-yt-btn";

      // const btn = document.createElement("button");
      // btn.id = "OmniPull-yt-btn";
      // btn.textContent = "Download with OmniPull";
      // btn.style.marginLeft = "10px";
      // btn.style.padding = "6px 10px";
      // btn.style.backgroundColor = "#e53935";
      // btn.style.color = "white";
      // btn.style.border = "none";
      // btn.style.borderRadius = "3px";
      // btn.style.cursor = "pointer";
  
      btn.onclick = () => {
        const url = window.location.href;
        chrome.runtime.sendMessage({ url });
      };
  
      container.appendChild(btn);
    }
  }
  
  // Handle dynamic loading (YouTube’s single page app)
  const observer = new MutationObserver(() => {
    if (window.location.href.includes("youtube.com/watch")) {
        console.log("[OmniPull] YouTube video detected:", window.location.href);
        console.log("[OmniPull] YouTube MutationObserver triggered");


        setTimeout(() => {
            injectYouTubeOverlay();
          }, 1000
        );
          
       console.log("[OmniPull] Trying to inject YouTube button");

    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
  
