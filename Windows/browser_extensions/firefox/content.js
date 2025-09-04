function isDownloadable(href) {
  if (!href || typeof href !== "string") return false;
  const lowers = href.toLowerCase();
  return [
    ".mp4",".mkv",".pdf",".zip",".rar",".mp3",".7z",".tar.gz"
  ].some(ext => lowers.includes(ext));
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
    transition: "background 0.3s, box-shadow 0.2s",
    zIndex: "2147483647"
  });

  btn.addEventListener("mouseenter", () => {
    btn.style.background = "linear-gradient(to right, rgba(0, 230, 100, 0.95), rgba(0, 180, 160, 0.95))";
    btn.style.boxShadow = "0 2px 6px rgba(0, 0, 0, 0.2)";
  });
  btn.addEventListener("mouseleave", () => {
    btn.style.background = "linear-gradient(to right, rgba(0, 200, 83, 0.85), rgba(0, 150, 136, 0.85))";
    btn.style.boxShadow = "none";
  });

  return btn;
}

function injectDownloadButtons(root = document) {
  const links = root.querySelectorAll("a[href]");
  links.forEach(link => {
    const href = link.getAttribute("href");
    // avoid duplicates
    if (link.dataset.omnipullButtonAttached === "1") return;

    const absUrl = link.href;
    if (!isDownloadable(absUrl)) return;

    const btn = createOmniPullButton();
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      console.log("[OmniPull] Button clicked. Sending:", absUrl);
      chrome.runtime.sendMessage({ url: absUrl }).catch?.(() => {});
    });

    // insert after link (if possible)
    if (link.parentElement) {
      link.parentElement.insertBefore(btn, link.nextSibling);
      link.dataset.omnipullButtonAttached = "1";
    }
  });
}

function injectOverlayOnVideos(root = document) {
  const videos = root.querySelectorAll("video");
  videos.forEach((video) => {
    if (video.dataset.omnipullInjected === "true") return;
    video.dataset.omnipullInjected = "true";

    // Ensure positioned parent
    const parent = video.parentElement || video;
    const style = getComputedStyle(parent);
    if (style.position === "static") parent.style.position = "relative";

    const overlay = document.createElement("div");
    overlay.style.position = "absolute";
    overlay.style.top = "10px";
    overlay.style.right = "10px";
    overlay.style.zIndex = "2147483647";
    overlay.style.pointerEvents = "auto";

    const btn = createOmniPullButton("Download Stream");
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const url = location.href; // stream page URL
      chrome.runtime.sendMessage({ url }).catch?.(() => {});
    });

    overlay.appendChild(btn);
    parent.appendChild(overlay);
  });
}

// Initial inject
injectDownloadButtons(document);
injectOverlayOnVideos(document);

// Observe dynamic changes (SPAs, lazy content)
const mo = new MutationObserver((mutations) => {
  for (const m of mutations) {
    m.addedNodes.forEach(node => {
      if (node.nodeType === Node.ELEMENT_NODE) {
        injectDownloadButtons(node);
        injectOverlayOnVideos(node);
      }
    });
  }
});
mo.observe(document.documentElement, { childList: true, subtree: true });

// Special case: YouTube navigation (SPA)
if (location.hostname.includes("youtube.com")) {
  let last = location.href;
  setInterval(() => {
    if (location.href !== last) {
      last = location.href;
      setTimeout(() => {
        injectOverlayOnVideos(document);
      }, 800);
    }
  }, 500);
}
