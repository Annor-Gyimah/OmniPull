function isDownloadable(link) {
    const downloadableExtensions = ['.mp4', '.mkv', '.pdf', '.zip', '.rar', '.mp3', '.7z', '.tar.gz'];
    return downloadableExtensions.some(ext => link.href && link.href.includes(ext));
  }
  
  function injectDownloadButtons() {
    const links = document.querySelectorAll('a');
  
    links.forEach(link => {
      if (isDownloadable(link)) {
        const btn = document.createElement("button");
        btn.textContent = "↓ PyIconic";
        btn.style.marginLeft = "10px";
        btn.style.padding = "2px 6px";
        btn.style.backgroundColor = "#1e88e5";
        btn.style.color = "white";
        btn.style.border = "none";
        btn.style.borderRadius = "3px";
        btn.style.fontSize = "12px";
        btn.style.cursor = "pointer";
  
        btn.onclick = () => {
          console.log("[PyIconic] Button clicked. Sending:", link.href); // ✅ Log this
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


  
    if (container && !document.getElementById("pyiconic-yt-btn")) {
      const btn = document.createElement("button");
      btn.id = "pyiconic-yt-btn";
      btn.textContent = "Download with PyIconic";
      btn.style.marginLeft = "10px";
      btn.style.padding = "6px 10px";
      btn.style.backgroundColor = "#e53935";
      btn.style.color = "white";
      btn.style.border = "none";
      btn.style.borderRadius = "3px";
      btn.style.cursor = "pointer";
  
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
        console.log("[PyIconic] YouTube video detected:", window.location.href);
        console.log("[PyIconic] YouTube MutationObserver triggered");


        setTimeout(() => {
            injectYouTubeOverlay();
          }, 1000
        );
          
       console.log("[PyIconic] Trying to inject YouTube button");

    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
  
