import threading
import subprocess
import os
import time

from gi.repository import GLib

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
        
        # Local paths
        self.base_dir = os.path.expanduser("~/.config/clambite")
        if not os.path.exists(self.base_dir):
            try:
                os.makedirs(self.base_dir, exist_ok=True)
            except OSError:
                pass

        self.db_dir = os.path.join(self.base_dir, "clamav-db/db")
        self.conf_file = os.path.join(self.base_dir, "clamav-db/freshclam.conf")
        
        # Logging setup
        self.log_dir = os.path.join(self.base_dir, "logs")
        if not os.path.exists(self.log_dir):
            try:
                os.makedirs(self.log_dir, exist_ok=True)
            except OSError:
                pass
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        
        # Prefix log filename based on mode
        if self.mode == 'update':
             self.log_filename = os.path.join(self.log_dir, f"update_{timestamp}.log")
        else:
             self.log_filename = os.path.join(self.log_dir, f"scan_{timestamp}.log")
        
        self.scan_summary = []
        self.full_log = [] # Store full log for updates/history

    def _setup_local_env(self):
        if not os.path.exists(self.db_dir):
            try:
                os.makedirs(self.db_dir, exist_ok=True)
            except OSError as e:
                self.log(f"Error creating directory: {e}")
                return False

        if not os.path.exists(self.conf_file):
            try:
                with open(self.conf_file, "w") as f:
                    f.write(f"DatabaseDirectory {self.db_dir}\n")
                    f.write("DatabaseMirror database.clamav.net\n")
            except OSError as e:
                self.log(f"Error writing config: {e}")
                return False
        return True

    def run(self):
        if not self._setup_local_env():
            GLib.idle_add(self.on_finish, False, "Environment Error")
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
            cmd = ['freshclam', f'--config-file={self.conf_file}']
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
            return proc.returncode == 0
        except Exception as e:
            self.log(f"Freshclam Error: {e}")
            return False

    def run_clamscan(self):
        self.update_ui("system-search-symbolic", "Scanning...", f"Target: {os.path.basename(self.target_path)}")
        self.log(f"--- Starting Scan: {self.target_path} ---")
        
        recursive = ['-r'] if self.mode == 'scan_dir' else []
        cmd = ['clamscan', f'--database={self.db_dir}'] + recursive + [self.target_path]
        
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
                    # Clamscan doesn't always output "Scanning file..." by default without verbose, 
                    # but if it does, or if we process filenames:
                    pass
                elif "Data scanned" in clean_line:
                    self.update_ui("mail-send-receive-symbolic", "Finalizing", "Calculating statistics...")

            proc.wait()
            
            # Return True if clean (0) or False if infected (1) or error (2)
            # We treat Infected as a "Successful scan" but with bad news.
            if proc.returncode == 1:
                msg = "Scan finished: INFECTION FOUND."
                self.log(msg)
                self.scan_summary.append(msg)
                return False # Flag as "not clean"
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
                with open(self.log_filename, "a") as f:
                    f.write(msg + "\n")
            except Exception:
                pass

    def update_ui(self, icon, title, subtitle):
        if not self._stop_event.is_set():
            GLib.idle_add(self.on_status, icon, title, subtitle)

    def stop(self):
        self._stop_event.set()
