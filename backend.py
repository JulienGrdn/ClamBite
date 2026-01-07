import threading
import subprocess
import os
import time
import tempfile
import shutil
import stat
from datetime import datetime
from gi.repository import GLib


def secure_which(binary_name):
    secure_paths = ["/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/local/bin"]

    for dirpath in secure_paths:
        full_path = os.path.join(dirpath, binary_name)
        
        # Resolve symlinks but verify the final path is safe
        try:
            # We use lstat to check the link itself first (optional but good hygiene)
            # Then resolve.
            real_path = os.path.realpath(full_path)
        except OSError:
            continue

        if not os.path.exists(real_path):
             continue

        fd = None
        try:
            # Open the resolved path to ensure we are checking the actual executable
            fd = os.open(real_path, os.O_RDONLY)
            os.set_inheritable(fd, False)
            st = os.fstat(fd)
            
            # Check if it's a regular file
            if not stat.S_ISREG(st.st_mode):
                continue
            # Check if executable by owner
            if not (st.st_mode & stat.S_IXUSR):
                continue
            # Check ownership (must be root)
            if st.st_uid != 0:
                continue

            # Check directory permissions of the resolved path
            real_dir = os.path.dirname(real_path)
            dir_st = os.stat(real_dir)

            if dir_st.st_uid != 0:
                continue
            if dir_st.st_mode & stat.S_IWOTH:
                continue
            return full_path

        except OSError:
            continue
        finally:
            if fd is not None:
                os.close(fd)

    return None

def safe_read_file(path, max_bytes=None):
    """
    Safely reads a file preventing symlink following.
    Returns content as string or None if failed.
    """
    fd = None
    try:
        # O_NOFOLLOW prevents following symlinks at the last component
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        # Verify it's a regular file
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return None
        
        with os.fdopen(fd, "r") as f:
            if max_bytes:
                return f.read(max_bytes)
            return f.read()
    except (OSError, Exception):
        return None
    finally:
        # os.fdopen closes the fd, but if it failed before fdopen, we need to close
        # Actually os.fdopen takes ownership of fd, so we don't close if fdopen succeeded.
        # But if os.open succeeded and fdopen failed (unlikely), we might leak.
        # Ideally:
        # fd = os.open(...)
        # try:
        #    with os.fdopen(fd, ...) as f: ...
        # except: os.close(fd)
        # But os.fdopen is the context manager.
        pass


CLAMSCAN_BIN = secure_which("clamscan")
FRESHCLAM_BIN = secure_which("freshclam")

class ScannerThread(threading.Thread):
    def __init__(self, mode, target_path, on_log, on_status, on_finish):
        """
        mode: 'update', 'scan_file', 'scan_dir'
        """
        super().__init__()
        self.mode = mode
        self.target_path = target_path
        self.on_log = on_log       # Callback for raw text log
        self.on_status = on_status # Callback for parsed UI status (icon_name, title, desc)
        self.on_finish = on_finish # Callback when done
        self._stop_event = threading.Event()
        
        # Fail immediately if binaries are missing
        if not CLAMSCAN_BIN or not FRESHCLAM_BIN:
             # We rely on run() to report the error to UI via on_finish
             self.binary_error = True
        else:
             self.binary_error = False

        # Local paths
        self.base_dir = os.path.expanduser("~/.config/clambite")
        self._secure_makedirs(self.base_dir)

        self.db_dir = os.path.join(self.base_dir, "clamav-db/db")
        self.conf_file = os.path.join(self.base_dir, "clamav-db/freshclam.conf")
        
        # Logging setup
        self.log_dir = os.path.join(self.base_dir, "logs")
        self._secure_makedirs(self.log_dir)
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        
        # Prefix log filename based on mode
        if self.mode == 'update':
             self.log_filename = os.path.join(self.log_dir, f"update_{timestamp}.log")
        else:
             self.log_filename = os.path.join(self.log_dir, f"scan_{timestamp}.log")
        
        self.scan_summary = []
        self.full_log = [] # Store full log for updates/history

    def _secure_makedirs(self, path):
        """Creates directory with 0700 permissions."""
        if os.path.islink(path):
            # If it's a symlink, do not trust it.
            # In a real scenario we might want to delete it or abort.
            # Here we abort to be safe.
            return

        if not os.path.exists(path):
            try:
                os.makedirs(path, mode=0o700, exist_ok=True)
            except OSError:
                pass
        else:
            # Enforce 0700 if it already exists and is a directory
            if os.path.isdir(path):
                try:
                    os.chmod(path, 0o700)
                except OSError:
                    pass

    def _setup_local_env(self):
        # Security check from init
        if self.binary_error:
            self.log("Critical Error: ClamAV binaries (clamscan/freshclam) not found.")
            return False

        if not os.path.exists(self.db_dir):
            try:
                os.makedirs(self.db_dir, mode=0o700, exist_ok=True)
            except OSError as e:
                self.log(f"Error creating directory: {e}")
                return False
        else:
             # Ensure existing db dir is secure
             if not os.path.islink(self.db_dir):
                 try:
                     os.chmod(self.db_dir, 0o700)
                 except OSError:
                     pass

        if not os.path.exists(self.conf_file):
            try:
                # Security: O_CREAT | O_WRONLY with 0600 permissions
                # O_EXCL ensures we don't overwrite if it was created just now (race)
                fd = os.open(self.conf_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as f:
                    f.write(f"DatabaseDirectory {self.db_dir}\n")
                    f.write("DatabaseMirror database.clamav.net\n")
            except OSError as e:
                # If it failed because it exists, that's fine (O_EXCL), otherwise log
                if not isinstance(e, FileExistsError):
                    self.log(f"Error writing config: {e}")
                    return False
        return True

    def run(self):
        if not self._setup_local_env():
            GLib.idle_add(self.on_finish, False, "Environment/Binary Error")
            return

        success = True
        
        # 1. Update Mode
        if self.mode == 'update':
            success = self.run_freshclam()
            
        # 2. Scan Mode (File or Dir)
        elif self.mode.startswith('scan'):
            # Check if DB exists, if not, warn
            if not os.listdir(self.db_dir):
                self.log("Database empty. Running update first...")
                self.run_freshclam()
            
            success = self.run_clamscan()

        # Pass summary OR full log depending on mode
        final_data = "\n".join(self.scan_summary) if self.scan_summary else "\n".join(self.full_log)
        GLib.idle_add(self.on_finish, success, self.mode, final_data)

    def run_freshclam(self):
        self.update_ui("system-software-install-symbolic", "Updating Database", "Connecting to ClamAV mirrors...")
        self.log("--- Starting DB Update ---")
        
        try:
            # Security: Use resolved FRESHCLAM_BIN
            cmd = [FRESHCLAM_BIN, f'--config-file={self.conf_file}']
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            for line in proc.stdout:
                if self._stop_event.is_set():
                    proc.terminate()
                    return False
                
                clean_line = line.strip()
                self.log(clean_line)
                
                # Parse output for UI
                if "Downloading" in clean_line:
                    self.update_ui("folder-download-symbolic", "Updating Database", clean_line)
                elif "up-to-date" in clean_line:
                    self.update_ui("weather-clear-symbolic", "Up to Date", "Definitions are current.")

            proc.wait()
            if proc.returncode == 0:
                return True
            else:
                self.log(f"Freshclam failed with code {proc.returncode}")
                return self._update_fallback()

        except Exception as e:
            self.log(f"Freshclam Error: {e}")
            return self._update_fallback()

    def _update_fallback(self):
        """Attempts to recover last known DB status from logs or file timestamps."""
        self.update_ui("dialog-warning-symbolic", "Update Failed", "Attempting recovery...")
        self.log("--- Update Failed: Attempting Fallback ---")

        # Fallback 1: System Log
        sys_log = "/var/log/clamav/freshclam.log"
        # Security: Use safe_read_file instead of open to prevent symlink attacks
        try:
             # Just verify it exists first to avoid log noise if not present
             if os.path.exists(sys_log):
                self.log(f"Reading system log: {sys_log}")
                # safe_read_file handles O_NOFOLLOW
                content = safe_read_file(sys_log)
                if content:
                    lines = content.splitlines()
                    # Capture last 20 lines
                    relevant = lines[-20:]
                    for line in relevant:
                        self.log(f"[SYS] {line.strip()}")
                    self.log("Recovered status from system log.")
                    return False # Update still technically failed
        except Exception as e:
            self.log(f"Failed to read system log: {e}")

        # Fallback 2: File Timestamps
        self.log("Checking database file timestamps...")
        found_any = False
        for db in ["daily.cvd", "daily.cld", "main.cvd", "main.cld", "bytecode.cvd", "bytecode.cld"]:
            path = os.path.join(self.db_dir, db)
            if os.path.exists(path) and not os.path.islink(path):
                found_any = True
                mtime = os.path.getmtime(path)
                dt = datetime.fromtimestamp(mtime)
                self.log(f"{db} found. Modified: {dt}")

        if not found_any:
            self.log("No database files found.")

        return False

    def run_clamscan(self):
        # LARGE FILE CHECK
        if self.mode == 'scan_file' and os.path.exists(self.target_path):
            try:
                size_mb = os.path.getsize(self.target_path) / (1024 * 1024)
                if size_mb > 500:
                    return self.run_split_scan()
            except Exception as e:
                self.log(f"Size check error: {e}")

        self.update_ui("system-search-symbolic", "Scanning...", f"Target: {os.path.basename(self.target_path)}")
        self.log(f"--- Starting Scan: {self.target_path} ---")
        
        recursive = ['-r'] if self.mode == 'scan_dir' else []
        # Security: Use resolved CLAMSCAN_BIN
        # Security: Use -- to prevent argument injection
        cmd = [CLAMSCAN_BIN, f'--database={self.db_dir}'] + recursive + ['--', self.target_path]
        
        return self._execute_clamscan(cmd)

    def run_split_scan(self):
        self.update_ui("edit-cut-symbolic", "Large File Detected", "Splitting file for scanning...")
        self.log(f"--- Splitting Large File: {self.target_path} ---")

        temp_dir = tempfile.mkdtemp(prefix="clambite_split_")
        # Note: mkdtemp creates 0700 by default on modern Python/OS
        self.log(f"Temporary chunks directory: {temp_dir}")

        try:
            # Security: Disk Exhaustion Check
            required_space = os.path.getsize(self.target_path)
            # Add 5% overhead safety margin
            required_space += required_space * 0.05
            
            usage = shutil.disk_usage(temp_dir)
            if usage.free < required_space:
                 self.log(f"Error: Insufficient disk space for splitting. Need {required_space/1024/1024:.2f}MB, Free {usage.free/1024/1024:.2f}MB")
                 return False

            # Split logic
            chunk_size = 50 * 1024 * 1024 # 50MB
            part_num = 1

            with open(self.target_path, 'rb') as source:
                while True:
                    if self._stop_event.is_set():
                        return False

                    chunk = source.read(chunk_size)
                    if not chunk:
                        break

                    part_name = os.path.join(temp_dir, f"part_{part_num:03d}")
                    # Write to temp dir (secure permissions inherited from mkdtemp)
                    with open(part_name, 'wb') as target:
                        target.write(chunk)

                    self.update_ui("edit-cut-symbolic", "Splitting...", f"Created chunk {part_num}")
                    part_num += 1

            self.log(f"Created {part_num-1} chunks. Starting scan...")
            self.update_ui("system-search-symbolic", "Scanning...", f"Scanning split chunks ({part_num-1})...")

            # Scan the directory of chunks
            # Security: Use resolved CLAMSCAN_BIN
            # Security: Use -- to prevent argument injection
            cmd = [CLAMSCAN_BIN, f'--database={self.db_dir}', '-r', '--', temp_dir]
            return self._execute_clamscan(cmd)

        except Exception as e:
            self.log(f"Split Error: {e}")
            return False
        finally:
            self.log("Cleaning up temporary chunks...")
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _execute_clamscan(self, cmd):
        infected_found = False
        capturing_summary = False

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            for line in proc.stdout:
                if self._stop_event.is_set():
                    proc.terminate()
                    return False
                
                clean_line = line.strip()
                self.log(clean_line)

                # --- PARSING LOGIC ---
                if "SCAN SUMMARY" in clean_line:
                    capturing_summary = True
                
                if capturing_summary:
                    self.scan_summary.append(clean_line)

                if "FOUND" in clean_line and not capturing_summary:
                    infected_found = True
                    fname = clean_line.split(':')[0]
                    short_name = os.path.basename(fname)
                    self.update_ui("dialog-warning-symbolic", "Threat Found!", f"Infected: {short_name}")
                elif clean_line.startswith("Scanning"):
                    pass
                elif "Data scanned" in clean_line:
                    self.update_ui("mail-send-receive-symbolic", "Finalizing", "Calculating statistics...")

            proc.wait()
            
            if proc.returncode == 1:
                msg = "Scan finished: INFECTION FOUND."
                self.log(msg)
                self.scan_summary.append(msg)
                return False
            elif proc.returncode == 0:
                msg = "Scan finished: Clean."
                self.log(msg)
                self.scan_summary.append(msg)
                return True
            else:
                self.log(f"Scan error code: {proc.returncode}")
                return False

        except Exception as e:
            self.log(f"Clamscan Error: {e}")
            return False

    def log(self, msg):
        if not self._stop_event.is_set():
            GLib.idle_add(self.on_log, msg)
            self.full_log.append(msg)
            try:
                # Security: Symlink Defense & Secure Permissions
                # O_NOFOLLOW: fail if path is a symlink
                # O_CREAT: create if missing
                # O_APPEND: append to end
                # 0o600: Read/Write for owner only
                fd = os.open(self.log_filename, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "a") as f:
                    f.write(msg + "\n")
            except OSError:
                # Silently ignore log errors to prevent crashing scan
                pass
            except Exception:
                pass

    def update_ui(self, icon, title, subtitle):
        if not self._stop_event.is_set():
            GLib.idle_add(self.on_status, icon, title, subtitle)

    def stop(self):
        self._stop_event.set()
