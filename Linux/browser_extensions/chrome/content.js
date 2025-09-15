// content.js

function isDownloadable(href) {
  if (!href || typeof href !== "string") return false;
  const s = href.toLowerCase();
  return [
    ".mp4",".mkv",".pdf",".zip",".rar",".mp3",".7z",".tar.gz", ".exe",".dmg",
    ".deb",".avi",".mov",".wmv",".flv",".webm",".m4a",".aac",".ogg",
    ".epub",".mobi",".azw3", ".doc",".docx",".xls",".xlsx",".ppt",".pptx",
    ".txt",".rtf",".csv",".svg",".psd",".iso", ".apk", ".msi", ".bat",
    ".torrent", ".mpd", ".m3u8", ".flac", ".wav", ".wma", ".opus", ".aiff",
    ".m2ts", ".ts", ".vtt", ".srt"
  ].some(ext => s.includes(ext));
}

function createButton(label = "Download with OmniPull") {
  const btn = document.createElement("button");
  const ICON_URL = chrome.runtime.getURL("icons/logo4.png");

  const img = document.createElement("img");
  img.src = ICON_URL;
  img.style.width = "14px";
  img.style.height = "14px";
  img.style.verticalAlign = "middle";
  img.style.marginRight = "6px";

  const span = document.createElement("span");
  span.textContent = label;

  btn.append(img, span);
  Object.assign(btn.style, {
    display: "inline-flex",
    alignItems: "center",
    marginLeft: "10px",
    padding: "5px 10px",
    background: "linear-gradient(to right, rgba(0,200,83,.85), rgba(0,150,136,.85))",
    color: "#fff",
    border: "1px solid rgba(0,150,136,.6)",
    borderRadius: "5px",
    fontSize: "12.5px",
    cursor: "pointer",
    zIndex: "2147483647"
  });
  return btn;
}

function injectLinkButtons(root = document) {
  const links = root.querySelectorAll("a[href]");
  links.forEach(link => {
    if (link.dataset.omnipullAttached === "1") return;
    const url = link.href;
    if (!isDownloadable(url)) return;

    const btn = createButton();
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      try {
        const maybe = chrome.runtime.sendMessage({ url });
        if (maybe && typeof maybe.then === "function") {
          maybe.catch(() => {}); // quiet errors if the worker reloaded
        }
      } catch (_) {}
    });

    link.parentElement?.insertBefore(btn, link.nextSibling);
    link.dataset.omnipullAttached = "1";
  });
}

function injectVideoOverlay(root = document) {
  const videos = root.querySelectorAll("video");
  videos.forEach(v => {
    if (v.dataset.omnipullInjected === "1") return;
    v.dataset.omnipullInjected = "1";
    const parent = v.parentElement || v;
    const cs = getComputedStyle(parent);
    if (cs.position === "static") parent.style.position = "relative";
    const overlay = document.createElement("div");
    overlay.style.position = "absolute";
    overlay.style.top = "10px";
    overlay.style.right = "10px";
    overlay.style.zIndex = "2147483647";

    const btn = createButton("Download Stream");
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      try {
        const maybe = chrome.runtime.sendMessage({ url: location.href });
        if (maybe && typeof maybe.then === "function") {
          maybe.catch(() => {});
        }
      } catch (_) {}
    });

    overlay.appendChild(btn);
    parent.appendChild(overlay);
  });
}

injectLinkButtons(document);
injectVideoOverlay(document);

const mo = new MutationObserver(muts => {
  muts.forEach(m => m.addedNodes.forEach(node => {
    if (node.nodeType === Node.ELEMENT_NODE) {
      injectLinkButtons(node);
      injectVideoOverlay(node);
    }
  }));
});
mo.observe(document.documentElement, { childList: true, subtree: true });