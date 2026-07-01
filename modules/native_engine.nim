


# import nimpy
# import os, times
# import winlean
# import nimcrypto
# # import std/[sequtils, strutils]

# # Fix: Use PDWORD (or ptr DWORD) to satisfy the Nim compiler
# proc PyEval_SaveThread(): pointer {.cdecl, importc: "PyEval_SaveThread", dynlib: "python3.dll".}
# proc PyEval_RestoreThread(state: pointer) {.cdecl, importc: "PyEval_RestoreThread", dynlib: "python3.dll".}

# template pyAllowThreads*(body: untyped) =
#   let state = PyEval_SaveThread()
#   try:
#     body
#   finally:
#     PyEval_RestoreThread(state)

# # Windows API definitions
# proc deviceIoControl*(hDevice: Handle; dwIoControlCode: DWORD; lpInBuffer: pointer; nInBufferSize: DWORD;
#   lpOutBuffer: pointer; nOutBufferSize: DWORD; lpBytesReturned: ptr DWORD; # Fixed type
#   lpOverlapped: pointer): cint {.stdcall, importc: "DeviceIoControl", dynlib: "kernel32".}

# type
#   LARGE_INTEGER* {.union, importc: "LARGE_INTEGER", header: "<windows.h>".} = object
#     QuadPart*: int64

# proc setFilePointerEx*(hFile: Handle; liDistanceToMove: LARGE_INTEGER; lpNewFilePointer: ptr LARGE_INTEGER;
#   dwMoveMethod: DWORD): cint {.stdcall, importc: "SetFilePointerEx", dynlib: "kernel32".}

# proc setEndOfFile*(hFile: Handle): cint {.stdcall, importc: "SetEndOfFile", dynlib: "kernel32".}

# # --- SPARSE FILE PRE-ALLOCATION ---
# when defined(windows):
#   const 
#     FSCTL_SET_SPARSE: DWORD = 0x000900C4
#     FILE_BEGIN: DWORD = 0
#     CREATE_ALWAYS: DWORD = 2 # Atomic: Overwrites existing or creates new

#   proc preallocate_file*(path: string, size: int64): bool {.exportpy.} =
#     ## Instant Sparse Pre-allocation
#     pyAllowThreads:
#       try:
#         let handle = createFileW(
#           path.newWideCString(),
#           cast[DWORD](GENERIC_READ or GENERIC_WRITE),
#           0,
#           nil,
#           CREATE_ALWAYS,
#           FILE_ATTRIBUTE_NORMAL,
#           0
#         )
        
#         if handle == INVALID_HANDLE_VALUE: return false
#         defer: discard closeHandle(handle)
        
#         # Mark as Sparse to skip zero-filling
#         var bytes_returned: DWORD
#         discard deviceIoControl(handle, FSCTL_SET_SPARSE, nil, 0, nil, 0, addr bytes_returned, nil)
        
#         # Set the size metadata
#         var liSize: LARGE_INTEGER
#         liSize.QuadPart = size
#         if setFilePointerEx(handle, liSize, nil, FILE_BEGIN) == 0: return false
#         if setEndOfFile(handle) == 0: return false
        
#         return true
#       except:
#         return false

# # --- STATS ENGINE ---
# proc calculate_stats*(segment_data: seq[PyObject]): PyObject {.exportpy.} =
#   var total_speed = 0.0
#   var total_downloaded: int64 = 0
#   var total_size: int64 = 0
#   var active_workers = 0

#   for seg in segment_data:
#     let speed = seg["speed"].to(float)
#     total_speed += speed
#     total_downloaded += seg["downloaded"].to(int64)
#     total_size += seg["size"].to(int64)
    
#     if speed > 0.1:
#       inc active_workers

#   let remaining = total_size - total_downloaded
#   var eta: float64 = -1.0
#   if total_speed > 0:
#     eta = float64(remaining) / total_speed

#   let progress = if total_size > 0: (float64(total_downloaded) / float64(total_size)) * 100.0 else: 0.0

#   let res = pyDict() 
#   res["total_speed"] = total_speed
#   res["eta_seconds"] = eta
#   res["active_count"] = float64(active_workers)
#   res["progress"] = progress
  
#   return res



# proc append_segment*(dest_path: string, src_path: string) {.exportpy.} =

#   ## Native stitcher that releases the Python GIL during I/O.
#   ## This allows the PySide6 GUI to stay responsive during 7GB merges.

#   pyAllowThreads:
#     let src = open(src_path, fmRead)
#     let dest = open(dest_path, fmAppend)
    
#     # Increased buffer to 1MB (1024 * 1024)
#     # This reduces the number of syscalls significantly
#     var buffer = newSeq[byte](2 * 1024 * 1024) 
    
#     while not src.endOfFile:
#       let bytesRead = src.readBuffer(addr(buffer[0]), buffer.len)
#       if bytesRead > 0:
#         discard dest.writeBuffer(addr(buffer[0]), bytesRead)
        
#     src.close()
#     dest.close()

# # --- STRAGGLER DETECTION ---
# proc find_struggler*(worker_data: seq[PyObject], threshold_multiplier: float64 = 3.0): int {.exportpy.} =
#   var max_ttc = 0.0
#   var total_ttc = 0.0
#   var active_count = 0
#   var candidate_index = -1

#   for i, w in worker_data:
#     let speed = w["speed"].to(float64)
#     let downloaded = w["downloaded"].to(float64)
#     let size = w["size"].to(float64)
#     let can_split = w["can_split"].to(bool)

#     if speed > 100.0 and can_split:
#       let remaining = size - downloaded
#       let ttc = remaining / speed
      
#       total_ttc += ttc
#       active_count.inc
      
#       if ttc > max_ttc:
#         max_ttc = ttc
#         candidate_index = i

#   if active_count > 1:
#     let avg_ttc = total_ttc / float64(active_count)
#     if max_ttc > (avg_ttc * threshold_multiplier) and max_ttc > 20.0:
#       return candidate_index

#   return -1

# # --- NATIVE WRITER (Sparse Pre-allocation Support) ---
# type
#   NativeWriter* = ref object
#     file: File
#     offset: int64  # Starting offset for this writer
#     downloaded*: int64  # Bytes written via this writer
#     last_check_time: float
#     last_check_bytes: int64
#     current_speed*: float

# proc new_native_writer*(path: string, offset: int64 = 0): NativeWriter {.exportpy.} =
#   ## Opens file at 'path' in read-write mode and seeks to 'offset'.
#   ## Each worker gets its own writer pre-positioned to its segment start.
#   ## Returns nil if file doesn't exist or can't be opened.
#   try:
#     let f = open(path, fmReadWriteExisting)
    
#     # Seek to the starting offset for this writer
#     if offset > 0:
#       f.setFilePos(offset)
    
#     result = NativeWriter(
#       file: f,
#       offset: offset,
#       downloaded: 0,
#       last_check_time: cpuTime(),
#       last_check_bytes: 0,
#       current_speed: 0.0
#     )
#   except:
#     result = nil



# proc write_data*(wr: NativeWriter, data: PyObject): int {.exportpy.} =
#   if wr == nil:
#     return -1
#   try:
#     let bytesData = data.to(seq[byte])  # must happen BEFORE releasing GIL (Python object)
#     let bytesCount = bytesData.len
#     if bytesCount > 0:
#       pyAllowThreads:  # ← ADD THIS — releases GIL during actual disk write
#         discard wr.file.writeBuffer(unsafeAddr(bytesData[0]), bytesCount)
#       wr.downloaded += bytesCount
#     return bytesCount
#   except:
#     return -1

# proc get_downloaded*(wr: NativeWriter): int64 {.exportpy.} =
#   ## Returns absolute byte position: offset + downloaded bytes.
#   if wr == nil:
#     return 0
#   return wr.offset + wr.downloaded

# proc get_relative_downloaded*(wr: NativeWriter): int64 {.exportpy.} =
#   ## Returns relative bytes downloaded (without offset).
#   if wr == nil:
#     return 0
#   return wr.downloaded

# proc get_speed*(wr: NativeWriter): float {.exportpy.} =
#   if wr == nil:
#     return 0.0
  
#   let now = cpuTime()
#   let duration = now - wr.last_check_time
#   if duration >= 0.4:
#     let diff = wr.downloaded - wr.last_check_bytes
#     wr.current_speed = float(diff) / duration
#     wr.last_check_time = now
#     wr.last_check_bytes = wr.downloaded
#   return wr.current_speed


# proc flush_file*(wr: NativeWriter): bool {.exportpy.} =
#   if wr == nil: return false
#   try:
#     pyAllowThreads:
#       wr.file.flushFile()
#     return true
#   except: return false

# proc close_file*(wr: NativeWriter) {.exportpy.} =
#   if wr != nil and wr.file != nil:
#     pyAllowThreads:
#       wr.file.close()


# proc compute_sha256*(path: string): string {.exportpy.} =
#   ## High-speed native SHA256 computation
#   if not fileExists(path):
#     return "Error: File not found"

#   pyAllowThreads:
#     var ctx: sha256
#     ctx.init()

#     let f = open(path, fmRead)

#     # 1MB buffer
#     var buffer = newSeq[byte](1024 * 1024)

#     while not f.endOfFile:
#       let bytesRead = f.readBuffer(addr(buffer[0]), buffer.len)
#       if bytesRead > 0:
#         ctx.update(addr(buffer[0]), uint(bytesRead))

#     f.close()

#     result = ctx.finish().data.toHex()



import nimpy
import os, times
import nimcrypto
import posix

# ── Platform-specific imports ─────────────────────────────────────────────────
when defined(windows):
  import winlean

# =============================================================================
# GIL MANAGEMENT
# =============================================================================
# Rule: only release the GIL during genuinely long-running I/O (append_segment,
# compute_sha256, large writes).  For short ops like preallocate_file and
# new_native_writer we do NOT release the GIL — the overhead of
# PyGILState_Ensure / PyEval_SaveThread on a re-entrant main thread causes
# deadlocks in single-threaded test scripts on Linux.
#
# NEVER use  dynlib: "libc"  on Linux — libc cannot be dlopen()'d by name.
# Use  header: "<...>"  instead so the linker resolves the symbol at build time.
# =============================================================================

when defined(windows):
  proc PyGILState_Ensure(): cint
    {.cdecl, importc: "PyGILState_Ensure", dynlib: "python3.dll".}
  proc PyGILState_Release(state: cint)
    {.cdecl, importc: "PyGILState_Release", dynlib: "python3.dll".}
  proc PyEval_SaveThread(): pointer
    {.cdecl, importc: "PyEval_SaveThread", dynlib: "python3.dll".}
  proc PyEval_RestoreThread(state: pointer)
    {.cdecl, importc: "PyEval_RestoreThread", dynlib: "python3.dll".}

elif defined(macosx):
  proc PyGILState_Ensure(): cint
    {.cdecl, importc: "PyGILState_Ensure", dynlib: "libpython3(|.dylib)".}
  proc PyGILState_Release(state: cint)
    {.cdecl, importc: "PyGILState_Release", dynlib: "libpython3(|.dylib)".}
  proc PyEval_SaveThread(): pointer
    {.cdecl, importc: "PyEval_SaveThread", dynlib: "libpython3(|.dylib)".}
  proc PyEval_RestoreThread(state: pointer)
    {.cdecl, importc: "PyEval_RestoreThread", dynlib: "libpython3(|.dylib)".}

else: # Linux
  proc PyGILState_Ensure(): cint
    {.cdecl, importc: "PyGILState_Ensure",
      dynlib: "libpython3(|.so|.so.1|.12.so.1|.11.so.1|.10.so.1)".}
  proc PyGILState_Release(state: cint)
    {.cdecl, importc: "PyGILState_Release",
      dynlib: "libpython3(|.so|.so.1|.12.so.1|.11.so.1|.10.so.1)".}
  proc PyEval_SaveThread(): pointer
    {.cdecl, importc: "PyEval_SaveThread",
      dynlib: "libpython3(|.so|.so.1|.12.so.1|.11.so.1|.10.so.1)".}
  proc PyEval_RestoreThread(state: pointer)
    {.cdecl, importc: "PyEval_RestoreThread",
      dynlib: "libpython3(|.so|.so.1|.12.so.1|.11.so.1|.10.so.1)".}

template pyAllowThreads*(body: untyped) =
  ## Releases the GIL for heavy I/O, then re-acquires it safely.
  ## PyGILState_Ensure guarantees we hold the GIL before SaveThread releases it.
  let gilState = PyGILState_Ensure()
  let tState   = PyEval_SaveThread()
  try:
    body
  finally:
    PyEval_RestoreThread(tState)
    PyGILState_Release(gilState)


# =============================================================================
# SPARSE / PRE-ALLOCATION
# =============================================================================

when defined(windows):
  # ── Windows: instant sparse file via DeviceIoControl ──────────────────────
  proc deviceIoControl(
      hDevice: Handle; dwIoControlCode: DWORD;
      lpInBuffer: pointer; nInBufferSize: DWORD;
      lpOutBuffer: pointer; nOutBufferSize: DWORD;
      lpBytesReturned: ptr DWORD; lpOverlapped: pointer): cint
    {.stdcall, importc: "DeviceIoControl", dynlib: "kernel32".}

  type
    LARGE_INTEGER {.union, importc: "LARGE_INTEGER", header: "<windows.h>".} = object
      QuadPart: int64

  proc setFilePointerEx(
      hFile: Handle; liDistanceToMove: LARGE_INTEGER;
      lpNewFilePointer: ptr LARGE_INTEGER; dwMoveMethod: DWORD): cint
    {.stdcall, importc: "SetFilePointerEx", dynlib: "kernel32".}

  proc setEndOfFile(hFile: Handle): cint
    {.stdcall, importc: "SetEndOfFile", dynlib: "kernel32".}

  const
    FSCTL_SET_SPARSE: DWORD = 0x000900C4
    FILE_BEGIN:       DWORD = 0
    CREATE_ALWAYS:    DWORD = 2

  proc preallocate_file*(path: string, size: int64): bool {.exportpy.} =
    ## Creates a sparse file of `size` bytes instantly — no zero-fill on disk.
    # No GIL release needed: CreateFile is fast and we're already on a worker.
    try:
      let handle = createFileW(
        path.newWideCString(),
        cast[DWORD](GENERIC_READ or GENERIC_WRITE),
        0, nil, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0)
      if handle == INVALID_HANDLE_VALUE: return false
      defer: discard closeHandle(handle)

      var bytesReturned: DWORD
      discard deviceIoControl(handle, FSCTL_SET_SPARSE,
        nil, 0, nil, 0, addr bytesReturned, nil)

      var liSize: LARGE_INTEGER
      liSize.QuadPart = size
      if setFilePointerEx(handle, liSize, nil, FILE_BEGIN) == 0: return false
      if setEndOfFile(handle) == 0: return false
      return true
    except:
      return false

elif defined(linux):
  # ── Linux: fallocate via header (linker resolves, no dlopen of libc) ───────
  #
  # Key points:
  #   • Use posix.open / posix.close — NOT Nim's file open() which is for
  #     the Nim File type and doesn't accept O_WRONLY flags.
  #   • mode = 0 (no flags): allocates space AND extends file size.
  #     FALLOC_FL_KEEP_SIZE (= 1) intentionally keeps the file size at 0,
  #     which would prevent workers from seeking into the file — DON'T use it.
  #   • header: "<fcntl.h>" → compile-time resolution, no runtime dlopen.

  proc fallocate(fd: cint; mode: cint; offset: int64; len: int64): cint
    {.importc: "fallocate", header: "<fcntl.h>".}

  proc preallocate_file*(path: string, size: int64): bool {.exportpy.} =
    ## Allocates `size` bytes for `path` using fallocate(2).
    ## The file is created (or truncated) and its size is set to `size`.
    ## Workers can then open it with fmReadWriteExisting and seek freely.
    try:
      # posix.open returns a file descriptor (cint), not a Nim File.
      let fd = posix.open(
        cstring(path),
        posix.O_WRONLY or posix.O_CREAT or posix.O_TRUNC,
        posix.S_IRUSR or posix.S_IWUSR or posix.S_IRGRP or posix.S_IROTH)

      if fd == -1: return false

      # mode = 0  →  preallocate AND extend file size to `size` bytes.
      # This is the only mode that lets fmReadWriteExisting + setFilePos work.
      let rc = fallocate(fd, 0.cint, 0.int64, size)

      # If fallocate is not supported by the filesystem (tmpfs, NFS, FAT…),
      # fall back to ftruncate which achieves the same logical result.
      let ok =
        if rc == 0:
          true
        else:
          posix.ftruncate(fd, size) == 0

      discard posix.close(fd)
      return ok
    except:
      return false

elif defined(macosx):
  # ── macOS: ftruncate (fallocate does not exist on macOS) ──────────────────
  

  proc preallocate_file*(path: string, size: int64): bool {.exportpy.} =
    try:
      let fd = posix.open(
        cstring(path),
        posix.O_WRONLY or posix.O_CREAT or posix.O_TRUNC,
        posix.S_IRUSR or posix.S_IWUSR or posix.S_IRGRP or posix.S_IROTH)
      if fd == -1: return false
      let rc = posix.ftruncate(fd, size)
      discard posix.close(fd)
      return rc == 0
    except:
      return false

else:
  # ── Generic POSIX fallback ─────────────────────────────────────────────────
  

  proc preallocate_file*(path: string, size: int64): bool {.exportpy.} =
    try:
      let fd = posix.open(
        cstring(path),
        posix.O_WRONLY or posix.O_CREAT or posix.O_TRUNC,
        posix.S_IRUSR or posix.S_IWUSR)
      if fd == -1: return false
      let rc = posix.ftruncate(fd, size)
      discard posix.close(fd)
      return rc == 0
    except:
      return false


# =============================================================================
# STATS ENGINE
# =============================================================================

proc calculate_stats*(segment_data: seq[PyObject]): PyObject {.exportpy.} =
  ## Aggregates speed, progress and ETA across all active segments.
  ## Called frequently from the GUI thread — no GIL release needed.
  var totalSpeed:    float   = 0.0
  var totalDl:       int64   = 0
  var totalSz:       int64   = 0
  var activeWorkers: int     = 0

  for seg in segment_data:
    let speed = seg["speed"].to(float)
    totalSpeed += speed
    totalDl    += seg["downloaded"].to(int64)
    totalSz    += seg["size"].to(int64)
    if speed > 0.1: inc activeWorkers

  let remaining = totalSz - totalDl
  var eta = -1.0
  if totalSpeed > 0.0:
    eta = float64(remaining) / totalSpeed

  let progress =
    if totalSz > 0: (float64(totalDl) / float64(totalSz)) * 100.0
    else: 0.0

  let res = pyDict()
  res["total_speed"]  = totalSpeed
  res["eta_seconds"]  = eta
  res["active_count"] = float64(activeWorkers)
  res["progress"]     = progress
  return res


# =============================================================================
# SEGMENT STITCHER  (heavy I/O — release GIL)
# =============================================================================

proc append_segment*(dest_path: string, src_path: string) {.exportpy.} =
  ## Appends src_path onto dest_path using a 2 MB buffer.
  ## Releases the GIL so the Qt UI stays responsive during multi-GB merges.
  pyAllowThreads:
    let src  = open(src_path,  fmRead)
    let dest = open(dest_path, fmAppend)
    var buf  = newSeq[byte](2 * 1024 * 1024)
    while not src.endOfFile:
      let n = src.readBuffer(addr buf[0], buf.len)
      if n > 0: discard dest.writeBuffer(addr buf[0], n)
    src.close()
    dest.close()


# =============================================================================
# STRAGGLER DETECTION
# =============================================================================

proc find_struggler*(worker_data: seq[PyObject],
                     threshold_multiplier: float64 = 3.0): int {.exportpy.} =
  ## Returns the index of the slowest worker if it is threshold_multiplier×
  ## slower than the average and can be split; otherwise returns -1.
  var maxTtc      = 0.0
  var totalTtc    = 0.0
  var activeCount = 0
  var candidate   = -1

  for i, w in worker_data:
    let speed      = w["speed"].to(float64)
    let downloaded = w["downloaded"].to(float64)
    let size       = w["size"].to(float64)
    let canSplit   = w["can_split"].to(bool)

    if speed > 100.0 and canSplit:
      let ttc = (size - downloaded) / speed
      totalTtc += ttc
      inc activeCount
      if ttc > maxTtc:
        maxTtc    = ttc
        candidate = i

  if activeCount > 1:
    let avgTtc = totalTtc / float64(activeCount)
    if maxTtc > (avgTtc * threshold_multiplier) and maxTtc > 20.0:
      return candidate

  return -1


# =============================================================================
# NATIVE WRITER
# =============================================================================
# Each download worker gets its own NativeWriter pre-positioned to its segment's
# byte offset inside the pre-allocated file.  Writes go directly to disk at the
# correct position without any locking — workers own non-overlapping ranges.

type
  NativeWriter* = ref object
    file:           File
    offset:         int64   ## Absolute byte offset where this writer starts
    downloaded*:    int64   ## Bytes written through this writer instance
    lastCheckTime:  float
    lastCheckBytes: int64
    currentSpeed*:  float

proc new_native_writer*(path: string, offset: int64 = 0): NativeWriter {.exportpy.} =
  ## Opens `path` in read-write mode (file must already exist — call
  ## preallocate_file first) and seeks to `offset`.
  ## Returns nil on any error so the caller can fall back to Python I/O.
  try:
    let f = open(path, fmReadWriteExisting)
    if offset > 0:
      f.setFilePos(offset)
    result = NativeWriter(
      file:           f,
      offset:         offset,
      downloaded:     0,
      lastCheckTime:  cpuTime(),
      lastCheckBytes: 0,
      currentSpeed:   0.0)
  except:
    result = nil

proc write_data*(wr: NativeWriter, data: PyObject): int {.exportpy.} =
  ## Writes `data` bytes to the pre-allocated file at the current position.
  ##
  ## NOTE: Do NOT release the GIL here.  write_data is called from pycurl's
  ## WRITEFUNCTION callback which already runs with the GIL held on the worker
  ## thread.  Calling PyGILState_Ensure + PyEval_SaveThread from multiple
  ## concurrent worker threads on Linux causes a pthread mutex deadlock because
  ## the recursive GIL acquire semantics differ from Windows.  The writeBuffer
  ## call is fast (kernel page-cache write), so holding the GIL is acceptable.
  if wr == nil: return -1
  try:
    let bytesData  = data.to(seq[byte])
    let bytesCount = bytesData.len
    if bytesCount > 0:
      discard wr.file.writeBuffer(unsafeAddr bytesData[0], bytesCount)
      wr.downloaded += bytesCount
    return bytesCount
  except:
    return -1

proc get_downloaded*(wr: NativeWriter): int64 {.exportpy.} =
  ## Absolute byte position written so far: starting offset + bytes written.
  if wr == nil: return 0
  return wr.offset + wr.downloaded

proc get_relative_downloaded*(wr: NativeWriter): int64 {.exportpy.} =
  ## Bytes written by this writer only (without the starting offset).
  if wr == nil: return 0
  return wr.downloaded

proc get_speed*(wr: NativeWriter): float {.exportpy.} =
  ## Returns instantaneous write speed in bytes/sec, sampled every 400 ms.
  if wr == nil: return 0.0
  let now = cpuTime()
  let dt  = now - wr.lastCheckTime
  if dt >= 0.4:
    let diff        = wr.downloaded - wr.lastCheckBytes
    wr.currentSpeed   = float(diff) / dt
    wr.lastCheckTime  = now
    wr.lastCheckBytes = wr.downloaded
  return wr.currentSpeed

proc flush_file*(wr: NativeWriter): bool {.exportpy.} =
  ## Flushes OS write buffers.
  ##
  ## NOTE: No GIL release here — same reasoning as write_data.  flushFile is a
  ## fast syscall and is called from worker threads that already hold the GIL.
  ## Using pyAllowThreads here caused deadlocks on Linux with multiple workers.
  if wr == nil: return false
  try:
    wr.file.flushFile()
    return true
  except:
    return false

proc close_file*(wr: NativeWriter) {.exportpy.} =
  ## Closes the file handle.
  ##
  ## NOTE: No GIL release here — same reasoning as write_data and flush_file.
  ## close() is a fast syscall; pyAllowThreads caused Linux deadlocks.
  if wr != nil:
    try:
      wr.file.close()
    except:
      discard


# =============================================================================
# SHA-256 CHECKSUM  (heavy I/O — release GIL)
# =============================================================================

proc compute_sha256*(path: string): string {.exportpy.} =
  if not fileExists(path):
    return "Error: File not found"

  pyAllowThreads:
    var ctx: sha256
    ctx.init()

    let fd = posix.open(cstring(path), posix.O_RDONLY)
    if fd < 0:
      result = "Error: Cannot open file"
      return

    var buf = newSeq[byte](1024 * 1024)

    while true:
      let n = posix.read(fd, addr buf[0], buf.len)
      if n <= 0:
        break
      ctx.update(addr buf[0], uint(n))

    discard posix.close(fd)

    result = ctx.finish().data.toHex()


# =============================================================================
# PER-DOWNLOAD BYTE COUNTER
# =============================================================================
# Workers call counter_add() in place of the Python `d.downloaded += n` setter.
# pycurl WRITEFUNCTION callbacks are invoked with the GIL held, so a plain
# int64 field is safe — no OS-level atomics needed.  The GUI tick reads the
# total once per ~250 ms via counter_get() and writes it to d._downloaded.

type
  DownloadCounter* = ref object
    total*: int64

proc new_download_counter*(): DownloadCounter {.exportpy.} =
  result = DownloadCounter(total: 0)

proc counter_add*(ctr: DownloadCounter, n: int64) {.exportpy.} =
  if ctr != nil: ctr.total += n

proc counter_get*(ctr: DownloadCounter): int64 {.exportpy.} =
  if ctr == nil: return 0
  return ctr.total

proc counter_reset*(ctr: DownloadCounter, value: int64 = 0) {.exportpy.} =
  if ctr != nil: ctr.total = value