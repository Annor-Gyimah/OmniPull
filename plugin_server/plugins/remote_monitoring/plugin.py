#######################################################################################
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

#   © 2024 Emmanuel Gyimah Annor. All rights reserved.
#####################################################################################



__plugin_meta__ = {
    "name": "Remote Monitoring",
    "version": "1.0.2",
    "author": "OmniPull Team",
    "description": (
        "FastAPI server that exposes real-time download progress over HTTP. "
        "View from any device on the same network via a polished dashboard."
    ),
    "icon": "📡",
}

import asyncio
import json
import qrcode
import socket
import threading
from io import BytesIO
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import List, Dict, Any



# ── Optional dependency guards ────────────────────────────────────────────────
try:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

try:
    from modules.utils import log
except ImportError:
    def log(msg, log_level=1, context="REMOTE-MON"):
        print(f"[{context}] {msg}")


# ── Module-level state (shared across threads) ────────────────────────────────
_d_list: list = []
_main_q: Queue = None
_server_thread: threading.Thread = None  # the ONE server thread
_server_ref = [None]                      # uvicorn.Server instance
_loop_ref   = [None]                      # the ONE asyncio event loop

_HOST = "0.0.0.0"
_PORT = 7432


# ── Entry-point ───────────────────────────────────────────────────────────────
def initialize_plugin(d_list: list, main_q: Queue) -> None:
    global _d_list, _main_q, _server_thread

    _d_list  = d_list
    _main_q  = main_q

    if not _HAS_FASTAPI:
        log(
            "Remote Monitoring plugin requires 'fastapi' and 'uvicorn'.\n"
            "  pip install fastapi uvicorn",
            log_level=2, context="REMOTE-MON",
        )
        return

    if _server_thread and _server_thread.is_alive():
        log("Server already running.", context="REMOTE-MON")
        return

    _server_thread = threading.Thread(
        target=_run_server,
        daemon=True,          # daemon=True so it never blocks process exit
        name="remote-mon-server",
    )
    _server_thread.start()
    log(f"Remote Monitoring dashboard → http://localhost:{_PORT}", context="REMOTE-MON")


def teardown_plugin() -> None:
    """Called by PluginManager.unload() – stop uvicorn then wait for thread."""
    global _server_thread

    log("Remote Monitoring plugin teardown requested.", context="REMOTE-MON")

    server = _server_ref[0]
    loop   = _loop_ref[0]

    # Step 1: tell uvicorn to exit via its own flag (thread-safe, no coroutine needed)
    if server is not None:
        server.should_exit = True

    # Step 2: if the loop is still alive poke it so it wakes up and sees the flag
    if loop is not None and not loop.is_closed():
        try:
            loop.call_soon_threadsafe(lambda: None)  # no-op wakeup
        except Exception:
            pass

    # Step 3: wait for the server thread (it owns the loop)
    if _server_thread and _server_thread.is_alive():
        _server_thread.join(timeout=6)
        if _server_thread.is_alive():
            log("Server thread still alive after 6 s — continuing anyway.",
                log_level=2, context="REMOTE-MON")

    # Step 4: close the loop from THIS thread now that the server thread is done
    if loop is not None and not loop.is_closed():
        try:
            # Cancel any lingering tasks
            pending = asyncio.all_tasks(loop)
            for t in pending:
                t.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            log("Event loop closed.", context="REMOTE-MON")
        except Exception as e:
            log(f"Loop close error (non-fatal): {e}", log_level=1, context="REMOTE-MON")

    _loop_ref[0]   = None
    _server_ref[0] = None
    log("Teardown complete.", context="REMOTE-MON")


def get_local_ip():
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  try:
      s.connect(("8.8.8.8", 80))
      return s.getsockname()[0]
  except Exception:
      return "127.0.0.1"
  finally:
      s.close()

def make_qr_pixmap(url):
  from PySide6.QtGui import QPixmap
  
  qr = qrcode.QRCode(border=2)
  qr.add_data(url)
  qr.make(fit=True)

  img = qr.make_image(fill_color="black", back_color="white")

  if hasattr(img, "get_image"):
      img = img.get_image()

  buffer = BytesIO()
  img.save(buffer, format="PNG")

  pixmap = QPixmap()
  pixmap.loadFromData(buffer.getvalue(), "PNG")
  return pixmap

def open_ui(parent=None) -> None:
    """
    Show the Remote Monitoring control dashboard (Qt window).
    Called when the user clicks the plugin icon in the sidebar.
    """
    try:
      from PySide6.QtCore import Qt, QUrl
      from PySide6.QtGui import QDesktopServices
      from PySide6.QtWidgets import (
          QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
          QFrame, QGridLayout, QApplication
      )
      
      server  = _server_ref[0]
      running = _server_thread is not None and _server_thread.is_alive() and server is not None

      local_ip = get_local_ip()
      external_url = f"http://{local_ip}:{_PORT}"

      dlg = QDialog(parent)
      dlg.setWindowTitle("Remote Monitoring — Control Panel")
      dlg.setMinimumWidth(480)
      dlg.setModal(False)

      root = QVBoxLayout(dlg)
      root.setSpacing(16)
      root.setContentsMargins(20, 20, 20, 20)

      # ── Header ────────────────────────────────────────────────────────────
      hdr = QHBoxLayout()
      icon_lbl = QLabel("📡")
      icon_lbl.setStyleSheet("font-size: 32px;")
      title_col = QVBoxLayout()
      title_col.setSpacing(2)
      name_lbl = QLabel("Remote Monitoring")
      name_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
      sub_lbl  = QLabel("v1.0.2  ·  OmniPull Team")
      sub_lbl.setStyleSheet("font-size: 11px; color: #888;")
      title_col.addWidget(name_lbl)
      title_col.addWidget(sub_lbl)
      hdr.addWidget(icon_lbl)
      hdr.addSpacing(10)
      hdr.addLayout(title_col, 1)
      root.addLayout(hdr)

      # ── Divider ───────────────────────────────────────────────────────────
      line = QFrame()
      line.setFrameShape(QFrame.HLine)
      line.setFrameShadow(QFrame.Sunken)
      root.addWidget(line)

      # ── Status card ───────────────────────────────────────────────────────
      status_frame = QFrame()
      status_frame.setFrameShape(QFrame.StyledPanel)
      status_layout = QGridLayout(status_frame)
      status_layout.setContentsMargins(14, 12, 14, 12)
      status_layout.setHorizontalSpacing(16)
      status_layout.setVerticalSpacing(8)

      def _row(label, value_widget, row):
          lbl = QLabel(label)
          lbl.setStyleSheet("font-weight: bold; color: #aaa; font-size: 11px;")
          status_layout.addWidget(lbl, row, 0)
          status_layout.addWidget(value_widget, row, 1)

      # Status indicator
      dot_color = "#4CAF50" if running else "#f44336"
      dot_text  = "● Running" if running else "● Stopped"
      status_val = QLabel(dot_text)
      status_val.setStyleSheet(f"color: {dot_color}; font-weight: bold;")
      _row("STATUS", status_val, 0)

      # Address
      # url_val = QLabel(f"http://localhost:{_PORT}" if running else "—")
      url_val = QLabel(external_url if running else "—")
      url_val.setStyleSheet("font-family: monospace;")
      _row("ADDRESS", url_val, 1)

      # Active downloads
      active_count = sum(
          1 for d in _d_list
          if str(getattr(d, "status", "")).lower() == "downloading"
      )
      active_val = QLabel(f"{active_count} active  /  {len(_d_list)} total")
      _row("DOWNLOADS", active_val, 2)

      # Description
      desc_val = QLabel(
          "Exposes real-time download progress over HTTP.\n"
          "Access the dashboard from any device on the same network."
      )
      desc_val.setWordWrap(True)
      desc_val.setStyleSheet("color: #aaa; font-size: 11px;")
      _row("ABOUT", desc_val, 3)

      root.addWidget(status_frame)

      if running:
        qr_container = QVBoxLayout()

        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignCenter)
        qr_label.setPixmap(
            make_qr_pixmap(external_url).scaled(
                180, 180,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

        qr_text = QLabel("Scan with your phone")
        qr_text.setAlignment(Qt.AlignCenter)
        qr_text.setStyleSheet("color: #888; font-size: 11px;")

        qr_container.addWidget(qr_label)
        qr_container.addWidget(qr_text)

        root.addLayout(qr_container)

      # ── Actions ───────────────────────────────────────────────────────────
      btn_row = QHBoxLayout()

      open_btn = QPushButton("🌐  Open Dashboard")
      open_btn.setEnabled(running)
      open_btn.setToolTip(f"Open http://localhost:{_PORT} in your browser")
      open_btn.clicked.connect(
          lambda: QDesktopServices.openUrl(QUrl(f"http://localhost:{_PORT}"))
      )

      copy_btn = QPushButton("📋  Copy URL")
      copy_btn.setEnabled(running)
      copy_btn.setToolTip("Copy dashboard URL to clipboard")
      def _copy():
          from PySide6.QtWidgets import QApplication
          QApplication.clipboard().setText(f"http://localhost:{_PORT}")
      copy_btn.clicked.connect(_copy)

      close_btn = QPushButton("Close")
      close_btn.clicked.connect(dlg.accept)

      btn_row.addWidget(open_btn)
      btn_row.addWidget(copy_btn)
      btn_row.addStretch()
      btn_row.addWidget(close_btn)
      root.addLayout(btn_row)

      dlg.exec()

    except ImportError as e:
        log(f"Missing dependency for control panel: {e}", log_level=2, context="REMOTE-MON")
        import webbrowser
        webbrowser.open(f"http://localhost:{_PORT}")
    except Exception as e:
        log(f"Control panel error: {e}", log_level=2, context="REMOTE-MON")
        import traceback
        log(traceback.format_exc(), log_level=2, context="REMOTE-MON")
        import webbrowser
        webbrowser.open(f"http://localhost:{_PORT}")


# ── Data helpers ──────────────────────────────────────────────────────────────
def _safe_float(val, default=0.0) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return default


def _build_stats() -> Dict[str, Any]:
    """Snapshot _d_list into a JSON-serialisable dict."""
    items = []
    total_speed = 0.0

    for d in _d_list:
        try:
            speed = _safe_float(getattr(d, "_speed", 0))
            total_speed += speed
            progress = _safe_float(getattr(d, "_progress", getattr(d, "progress", 0)))

            items.append({
                "id":         getattr(d, "id", 0),
                "name":       str(getattr(d, "name", "Unknown")),
                "status":     str(getattr(d, "status", "unknown")),
                "progress":   round(progress, 1),
                "speed":      speed,
                "size":       _safe_float(getattr(d, "size", 0)),
                "downloaded": _safe_float(getattr(d, "downloaded", 0)),
                "engine":     str(getattr(d, "engine", "?")),
                "folder":     str(getattr(d, "folder", "")),
                "eta":        _safe_float(getattr(d, "remaining_time", 0)),
            })
        except Exception:
            pass

    active  = sum(1 for i in items if i["status"] == "downloading")
    done    = sum(1 for i in items if i["status"] == "completed")
    errored = sum(1 for i in items if i["status"] in ("error", "failed"))

    return {
        "timestamp":   datetime.utcnow().isoformat() + "Z",
        "total":       len(items),
        "active":      active,
        "completed":   done,
        "errored":     errored,
        "total_speed": total_speed,
        "items":       items,
    }


# ── FastAPI app ───────────────────────────────────────────────────────────────
def _build_app() -> "FastAPI":
    app = FastAPI(title="OmniPull Remote Monitor", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_DASHBOARD_HTML, status_code=200)

    @app.get("/api/stats")
    async def stats():
        return JSONResponse(_build_stats())

    @app.get("/api/stream")
    async def sse_stream():
        """Server-Sent Events endpoint — pushes updates every second."""
        async def event_generator():
            while True:
                data = json.dumps(_build_stats())
                yield f"data: {data}\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control":               "no-cache",
                "X-Accel-Buffering":           "no",
                "Access-Control-Allow-Origin": "*",
            }
        )

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "plugin": "remote_monitoring"}

    return app


# REPLACE the entire _run_server function (lines 271–298)

def _run_server():
    
    """Runs in its own thread. Owns the asyncio event loop for its lifetime."""
    global _server_ref, _loop_ref

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _loop_ref[0] = loop

    try:
        app    = _build_app()
        config = uvicorn.Config(
            app,
            host=_HOST,
            port=_PORT,
            log_level="warning",
            log_config=None,  # Disable uvicorn's logging config (fixes frozen app issues)
            loop="none",      # we supply our own loop
            lifespan="off",
        )
        server = uvicorn.Server(config)
        _server_ref[0] = server
        loop.run_until_complete(server.serve())
    except asyncio.CancelledError:
        pass   # normal shutdown path — not an error
    except Exception as e:
        log(f"Server error: {e}", log_level=2, context="REMOTE-MON")
    finally:
        _server_ref[0] = None
        _loop_ref[0]   = None
        if not loop.is_closed():
            loop.close()


# ── Dashboard HTML ─────────────────────────────────────────────────────────────
# A complete, self-contained, responsive Tailwind CSS page.
# Fetches data from /api/stream (SSE) and updates the DOM in real-time.
_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>OmniPull Remote Monitor</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:       #0d0f14;
    --surface:  #13161d;
    --card:     #1a1e27;
    --border:   #252a35;
    --muted:    #4a5366;
    --text:     #d4daf0;
    --accent:   #3b82f6;
    --green:    #22c55e;
    --red:      #ef4444;
    --amber:    #f59e0b;
    --purple:   #a855f7;
  }
  * { box-sizing: border-box; margin: 0; }
  body {
    font-family: 'Inter', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    overflow-x: hidden;
  }
  .mono { font-family: 'JetBrains Mono', monospace; }

  /* ── Animated background grid ── */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(var(--border) 1px, transparent 1px),
      linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 40px 40px;
    opacity: 0.35;
    pointer-events: none;
    z-index: 0;
  }

  .z1 { position: relative; z-index: 1; }

  /* ── Cards ── */
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px 22px;
    transition: border-color .2s;
  }
  .card:hover { border-color: #354060; }

  /* ── Stat badge ── */
  .stat-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: .4px;
  }

  /* ── Progress bar ── */
  .prog-track {
    background: #1e2535;
    border-radius: 99px;
    height: 6px;
    overflow: hidden;
    margin-top: 8px;
  }
  .prog-fill {
    height: 100%;
    border-radius: 99px;
    transition: width .5s ease;
  }

  /* ── Status dot ── */
  .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .dot-active  { background: var(--accent); box-shadow: 0 0 6px var(--accent); animation: pulse 1.4s infinite; }
  .dot-done    { background: var(--green); }
  .dot-error   { background: var(--red); }
  .dot-pending { background: var(--amber); }
  .dot-idle    { background: var(--muted); }

  @keyframes pulse {
    0%,100% { opacity: 1; }
    50%      { opacity: .4; }
  }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  /* ── Speed sparkle animation ── */
  @keyframes shimmer {
    0%   { background-position: -200% center; }
    100% { background-position:  200% center; }
  }
  .speed-text {
    background: linear-gradient(90deg, var(--accent), #818cf8, var(--accent));
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 2.5s linear infinite;
  }

  /* ── Fade-in rows ── */
  @keyframes fadeSlide {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .row-item { animation: fadeSlide .3s ease; }

  /* ── Connection indicator ── */
  #conn-ring {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
    transition: background .4s, box-shadow .4s;
  }
  #conn-ring.lost {
    background: var(--red);
    box-shadow: 0 0 8px var(--red);
    animation: none;
  }
</style>
</head>
<body>

<!-- ── Header ─────────────────────────────────────────────────────────────── -->
<header class="z1 sticky top-0" style="background:rgba(13,15,20,.88);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);z-index:50;">
  <div class="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
    <div class="flex items-center gap-3">
      <span style="font-size:22px">📡</span>
      <span class="font-semibold text-sm tracking-tight" style="color:var(--text)">OmniPull</span>
      <span class="text-xs" style="color:var(--muted)">/ Remote Monitor</span>
    </div>
    <div class="flex items-center gap-3">
      <!-- Live indicator -->
      <div class="flex items-center gap-2">
        <div id="conn-ring"></div>
        <span id="conn-txt" class="text-xs mono" style="color:var(--muted)">LIVE</span>
      </div>
      <!-- Clock -->
      <span id="clock" class="mono text-xs" style="color:var(--muted)">--:--:--</span>
    </div>
  </div>
</header>

<main class="z1 max-w-6xl mx-auto px-4 py-6 space-y-6">

  <!-- ── KPI Row ─────────────────────────────────────────────────────────── -->
  <div id="kpi-row" class="grid grid-cols-2 sm:grid-cols-4 gap-4">
    <div class="card" id="kpi-total">
      <p class="text-xs uppercase tracking-widest mb-1" style="color:var(--muted)">Total</p>
      <p class="text-3xl font-bold mono" id="kpi-total-val">—</p>
    </div>
    <div class="card" id="kpi-active">
      <p class="text-xs uppercase tracking-widest mb-1" style="color:var(--muted)">Downloading</p>
      <p class="text-3xl font-bold mono" id="kpi-active-val" style="color:var(--accent)">—</p>
    </div>
    <div class="card">
      <p class="text-xs uppercase tracking-widest mb-1" style="color:var(--muted)">Completed</p>
      <p class="text-3xl font-bold mono" id="kpi-done-val" style="color:var(--green)">—</p>
    </div>
    <div class="card">
      <p class="text-xs uppercase tracking-widest mb-1" style="color:var(--muted)">Total Speed</p>
      <p class="text-2xl font-bold speed-text mono" id="kpi-speed-val">—</p>
    </div>
  </div>

  <!-- ── Download list ────────────────────────────────────────────────────── -->
  <div class="card" style="padding:0;overflow:hidden;">
    <div class="flex items-center justify-between px-5 py-3" style="border-bottom:1px solid var(--border);">
      <h2 class="font-semibold text-sm" style="color:var(--text)">Downloads</h2>
      <span id="list-count" class="text-xs mono" style="color:var(--muted)"></span>
    </div>
    <div id="dl-list" class="divide-y" style="border-color:var(--border);max-height:60vh;overflow-y:auto;">
      <p class="px-5 py-6 text-sm text-center" style="color:var(--muted)">Connecting…</p>
    </div>
  </div>

</main>

<!-- ── Footer ─────────────────────────────────────────────────────────────── -->
<footer class="z1 text-center py-4 text-xs mono" style="color:var(--muted);">
  OmniPull Remote Monitor · port 7432
</footer>

<script>
// ── Helpers ──────────────────────────────────────────────────────────────────
function fmtBytes(b) {
  if (!b || b === 0) return '0 B';
  const u = ['B','KB','MB','GB','TB'];
  const i = Math.floor(Math.log(b) / Math.log(1024));
  return (b / Math.pow(1024, i)).toFixed(1) + ' ' + u[i];
}
function fmtSpeed(bps) {
  return fmtBytes(bps) + '/s';
}
function fmtETA(secs) {
  if (!secs || secs <= 0) return '';
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.floor(secs % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function dotClass(status) {
  const s = (status || '').toLowerCase();
  if (s === 'downloading')   return 'dot dot-active';
  if (s === 'completed')     return 'dot dot-done';
  if (s === 'error' || s === 'failed') return 'dot dot-error';
  if (s === 'queued' || s === 'pending') return 'dot dot-pending';
  return 'dot dot-idle';
}

function barColor(status, pct) {
  const s = (status || '').toLowerCase();
  if (s === 'completed')               return '#22c55e';
  if (s === 'error' || s === 'failed') return '#ef4444';
  if (s === 'downloading')             return '#3b82f6';
  if (s === 'merging_audio')           return '#f59e0b';
  return '#4a5366';
}

function statusBadge(status) {
  const s = (status || '').toLowerCase();
  const cfg = {
    downloading:   ['#1d3461','#3b82f6'],
    completed:     ['#14301e','#22c55e'],
    error:         ['#3a1515','#ef4444'],
    failed:        ['#3a1515','#ef4444'],
    cancelled:     ['#2a1a00','#f59e0b'],
    queued:        ['#1e1532','#a855f7'],
    pending:       ['#1e1532','#a855f7'],
    merging_audio: ['#2a1f00','#f59e0b'],
    stitching:     ['#2a1f00','#f59e0b'],
  };
  const [bg, col] = cfg[s] || ['#1e2535','#4a5366'];
  return `<span class="stat-badge" style="background:${bg};color:${col};">${status}</span>`;
}

// ── Clock ─────────────────────────────────────────────────────────────────────
function updateClock() {
  document.getElementById('clock').textContent =
    new Date().toLocaleTimeString('en-US', {hour12: false});
}
setInterval(updateClock, 1000);
updateClock();

// ── Render ────────────────────────────────────────────────────────────────────
function render(data) {
  // KPIs — update only if changed
  function setText(id, val) {
    const el = document.getElementById(id);
    if (el && el.textContent !== String(val)) el.textContent = val;
  }

  setText('kpi-total-val',  data.total ?? 0);
  setText('kpi-active-val', data.active ?? 0);
  setText('kpi-done-val',   data.completed ?? 0);
  setText('kpi-speed-val',  fmtSpeed(data.total_speed ?? 0));
  setText('list-count',     (data.total ?? 0) + ' item(s)');

  const items = data.items || [];
  const list  = document.getElementById('dl-list');

  if (!items.length) {
    if (list.dataset.empty !== '1') {
      list.innerHTML = '<p class="px-5 py-8 text-sm text-center" style="color:var(--muted)">No downloads yet.</p>';
      list.dataset.empty = '1';
    }
    return;
  }

  list.dataset.empty = '0';

  // Sort: downloading first, then progress desc
  items.sort((a, b) =>
    (b.status === 'downloading' ? 1 : 0) - (a.status === 'downloading' ? 1 : 0)
    || (b.progress || 0) - (a.progress || 0)
  );

  // Map existing rows
  const existingRows = {};
  list.querySelectorAll('[data-id]').forEach(el => {
    existingRows[el.dataset.id] = el;
  });

  const seenIds = new Set();

  items.forEach(it => {
    const id  = String(it.id ?? it.name); // ✅ SAFE fallback
    seenIds.add(id);

    const pct = Math.min(100, Math.max(0, it.progress || 0));
    const eta = fmtETA(it.eta);

    let row = existingRows[id];

    if (!row) {
      // Create new row
      row = document.createElement('div');
      row.className = 'row-item px-5 py-4';
      row.dataset.id = id;
      row.style.cssText = 'border-bottom:1px solid var(--border);transition:background .2s';

      row.onmouseenter = () => row.style.background = '#1e2535';
      row.onmouseleave = () => row.style.background = '';

      row.innerHTML = _rowHTML(it, pct, eta);
      list.appendChild(row);

    } else {
      // Patch existing row
      const fillEl = row.querySelector('.prog-fill');
      if (fillEl) {
        fillEl.style.width = pct + '%';
        fillEl.style.background = barColor(it.status, pct);
      }

      const pctEl = row.querySelector('[data-pct]');
      if (pctEl && pctEl.textContent !== pct.toFixed(1) + '%') {
        pctEl.textContent = pct.toFixed(1) + '%';
      }

      const bigEl = row.querySelector('[data-bigpct]');
      if (bigEl && bigEl.firstChild && bigEl.firstChild.textContent !== pct.toFixed(0)) {
        bigEl.firstChild.textContent = pct.toFixed(0);
      }

      const spdEl = row.querySelector('[data-speed]');
      if (spdEl) {
        const newSpd = it.status === 'downloading' ? fmtSpeed(it.speed) : '';
        if (spdEl.textContent !== newSpd) spdEl.textContent = newSpd;
      }

      const etaEl = row.querySelector('[data-eta]');
      if (etaEl) {
        const newEta = eta ? 'ETA ' + eta : '';
        if (etaEl.textContent !== newEta) etaEl.textContent = newEta;
      }

      // Status dot update
      const dotEl  = row.querySelector('.dot');
      const newCls = dotClass(it.status);
      if (dotEl && dotEl.className !== newCls) dotEl.className = newCls;
    }
  });

  // Remove stale rows
  Object.keys(existingRows).forEach(id => {
    if (!seenIds.has(id)) existingRows[id].remove();
  });
}


// Helper: initial row HTML
function _rowHTML(it, pct, eta) {
  return `
    <div class="flex items-start gap-3">
      <div class="${dotClass(it.status)}" style="margin-top:5px"></div>

      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 flex-wrap mb-1">
          <span class="text-sm font-medium truncate"
                style="color:var(--text);max-width:320px"
                title="${it.name}">
            ${it.name}
          </span>

          ${statusBadge(it.status)}

          <span class="text-xs mono" style="color:var(--muted)">
            ${it.engine}
          </span>
        </div>

        <div class="prog-track">
          <div class="prog-fill"
               style="width:${pct}%;background:${barColor(it.status, pct)}">
          </div>
        </div>

        <div class="flex items-center gap-4 mt-2 flex-wrap">
          <span class="mono text-xs"
                style="color:var(--accent)"
                data-pct>
            ${pct.toFixed(1)}%
          </span>

          <span class="mono text-xs" style="color:var(--muted)">
            ${fmtBytes(it.downloaded)} / ${fmtBytes(it.size)}
          </span>

          <span class="mono text-xs"
                style="color:var(--green)"
                data-speed>
            ${it.status === 'downloading' ? fmtSpeed(it.speed) : ''}
          </span>

          <span class="mono text-xs"
                style="color:var(--amber)"
                data-eta>
            ${eta ? 'ETA ' + eta : ''}
          </span>
        </div>
      </div>

      <div class="hidden sm:block text-right" data-bigpct>
        <span class="mono text-xl font-bold"
              style="color:${barColor(it.status, pct)}">
          ${pct.toFixed(0)}
          <span style="font-size:12px;color:var(--muted)">%</span>
        </span>
      </div>
    </div>`;
}

// ── SSE connection ─────────────────────────────────────────────────────────────
let evtSource;

function connect() {
  evtSource = new EventSource('/api/stream');

  evtSource.onmessage = e => {
    try {
      const data = JSON.parse(e.data);
      render(data);
      // Live indicator
      const ring = document.getElementById('conn-ring');
      const txt  = document.getElementById('conn-txt');
      ring.classList.remove('lost');
      ring.style.background = '';
      txt.textContent = 'LIVE';
    } catch(err) {}
  };

  evtSource.onerror = () => {
    const ring = document.getElementById('conn-ring');
    const txt  = document.getElementById('conn-txt');
    ring.classList.add('lost');
    txt.textContent = 'RECONNECTING…';
    // Reconnect after 3s
    evtSource.close();
    setTimeout(connect, 3000);
  };
}

connect();
</script>
</body>
</html>
"""
