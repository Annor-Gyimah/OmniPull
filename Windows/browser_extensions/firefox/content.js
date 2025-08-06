function isDownloadable(link) {
    const downloadableExtensions = ['.mp4', '.mkv', '.pdf', '.zip', '.rar', '.mp3', '.7z', '.tar.gz'];
    return downloadableExtensions.some(ext => link.href && link.href.includes(ext));
  }

  function createOmniPullButton(text = "Download with OmniPull") {
    const btn = document.createElement("button");

    const ICON_URL = chrome.runtime.getURL("icons/logo4.png");
    const img = document.createElement("img");
    img.src = ICON_URL;
    img.style.width = "14px";
    img.style.height = "14px";
    img.style.verticalAlign = "middle";
    img.style.marginRight = "6px";

    const span = document.createElement("span");
    span.textContent = text;

    btn.appendChild(img);
    btn.appendChild(span);

    Object.assign(btn.style, {
      display: "inline-flex",
      alignItems: "center",
      marginLeft: "10px",
      padding: "5px 10px",
      background: "linear-gradient(to right, rgba(0, 200, 83, 0.85), rgba(0, 150, 136, 0.85))",
      color: "#fff",
      border: "1px solid rgba(0, 150, 136, 0.6)",
      borderRadius: "5px",
      fontSize: "12.5px",
      fontWeight: "500",
      fontFamily: "'Segoe UI', sans-serif",
      cursor: "pointer",
      backdropFilter: "blur(2px)",
      transition: "background 0.3s, box-shadow 0.2s"
    });

    btn.onmouseenter = () => {
      btn.style.background = "linear-gradient(to right, rgba(0, 230, 100, 0.95), rgba(0, 180, 160, 0.95))";
      btn.style.boxShadow = "0 2px 6px rgba(0, 0, 0, 0.2)";
    };

    btn.onmouseleave = () => {
      btn.style.background = "linear-gradient(to right, rgba(0, 200, 83, 0.85), rgba(0, 150, 136, 0.85))";
      btn.style.boxShadow = "none";
    };

    return btn;
  }

  
  function injectDownloadButtons() {
    const links = document.querySelectorAll('a');
    const ICON_URL = chrome.runtime.getURL("icons/logo4.png"); // Use the icon URL from the extension
  
    links.forEach(link => {
      if (isDownloadable(link)) {
        const btn = createOmniPullButton();

        
  
        btn.onclick = () => {
          console.log("[OmniPull] Button clicked. Sending:", link.href); // ✅ Log this
          chrome.runtime.sendMessage({ url: link.href });
        };
  
        link.parentElement.insertBefore(btn, link.nextSibling);
      }
    });
  }
  
  injectDownloadButtons();

  

  function injectOverlayOnVideos() {
    const videos = document.querySelectorAll("video");

    videos.forEach((video, index) => {
      if (video.dataset.omnipullInjected) return; // Avoid duplicates
      video.dataset.omnipullInjected = "true";

      const overlay = document.createElement("div");
      overlay.style.position = "absolute";
      overlay.style.top = "10px";
      overlay.style.right = "10px";
      overlay.style.zIndex = "9999";
      overlay.style.pointerEvents = "auto";

      // Make sure video’s container is positioned
      const parent = video.parentElement;
      if (getComputedStyle(parent).position === "static") {
        parent.style.position = "relative";
      }

        const btn = createOmniPullButton("Download Stream");
        btn.onclick = () => {
          const url = window.location.href;
          chrome.runtime.sendMessage({ url });
        };

        overlay.appendChild(btn);
        parent.appendChild(overlay);
      });
    }

    // Observe for dynamic video loading
    const videoObserver = new MutationObserver(() => {
      injectOverlayOnVideos();
    });

    videoObserver.observe(document.body, { childList: true, subtree: true });


  

  // Handle dynamic loading (YouTube’s single page app)
  const observer = new MutationObserver(() => {
    if (window.location.href.includes("youtube.com/watch")) {
      console.log("[OmniPull] YouTube video detected:", window.location.href);
      console.log("[OmniPull] YouTube MutationObserver triggered");

      setTimeout(() => {
        injectOverlayOnVideos();
      }, 1000); // Delay to ensure video is loaded
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });