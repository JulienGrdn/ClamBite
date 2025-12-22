import os, time
import re
import gi
from datetime import datetime, timedelta
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio, GObject, Pango, Gdk
from backend import ScannerThread
from parsers import ScanParser, UpdateParser

class LogWindow(Adw.Window):
    def __init__(self, parent_window, buffer):
        super().__init__(title="Scan Logs", transient_for=parent_window, modal=True)
        self.set_default_size(600, 400)
        
        # Toolbar
        tb_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        tb_view.add_top_bar(header)
        
        # Content
        scrolled = Gtk.ScrolledWindow()
        text_view = Gtk.TextView(buffer=buffer)
        text_view.set_editable(False)
        text_view.set_monospace(True)
        text_view.set_left_margin(10)
        text_view.set_right_margin(10)
        text_view.set_top_margin(10)
        text_view.set_bottom_margin(10)
        
        scrolled.set_child(text_view)
        tb_view.set_content(scrolled)
        self.set_content(tb_view)
        
        
class ScanResultPage(Adw.NavigationPage):
    def __init__(self, summary_text):
        super().__init__(title="Scan Results", tag="result_page")
        
        # Parse data
        data = ScanParser.parse(summary_text)

        # Toolbar
        tb_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        tb_view.add_top_bar(header)
        
        # --- LAYOUT SETUP ---
        
        # 1. Main container
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tb_view.set_content(root_box)
        self.set_child(tb_view)

        # 2. COMPACT Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header_box.set_margin_top(18)
        header_box.set_margin_bottom(18)
        
        # Elements for the header
        icon = Gtk.Image()
        icon.set_pixel_size(64)
        
        title_label = Gtk.Label()
        title_label.add_css_class("title-2")
        
        desc_label = Gtk.Label()
        desc_label.add_css_class("body")
        desc_label.set_margin_top(4)

        # Status Logic
        if data["status"] == "Clean":
            icon.set_from_icon_name("security-high-symbolic")
            icon.add_css_class("success") # Color the icon green
            title_label.set_label("Scan Clean")
            desc_label.set_label("No threats found.")
        elif data["status"] == "Infected":
            icon.set_from_icon_name("dialog-warning-symbolic")
            icon.add_css_class("error")   # Color the icon red
            title_label.set_label("Threats Found")
            desc_label.set_label(f"{data['infected_files']} infected files detected.")
        else:
            icon.set_from_icon_name("dialog-question-symbolic")
            title_label.set_label("Scan Complete")
        
        # Assemble Header
        header_box.append(icon)
        header_box.append(title_label)
        header_box.append(desc_label)
        
        # Add Header to Root (Fixed at top)
        root_box.append(header_box)

        # 3. Scrollable Body
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True) 
        root_box.append(scrolled_window)

        # Clamp & Content Box
        clamp = Adw.Clamp(maximum_size=600)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(0) # Removed top margin since header has bottom margin
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        
        clamp.set_child(content_box)
        scrolled_window.set_child(clamp)

        # --- CONTENT ITEMS ---

        # Metrics Group
        grp_metrics = Adw.PreferencesGroup(title="Scan Metrics")
        content_box.append(grp_metrics)

        # Duration
        row_time = Adw.ActionRow(title="Duration", subtitle=data.get("time", "N/A"))
        row_time.add_prefix(Gtk.Image.new_from_icon_name("alarm-symbolic"))
        grp_metrics.add(row_time)

        # Engine
        row_ver = Adw.ActionRow(title="Engine Version", subtitle=data.get("engine_version", "N/A"))
        row_ver.add_prefix(Gtk.Image.new_from_icon_name("system-run-symbolic"))
        grp_metrics.add(row_ver)
        
        # DB
        row_db = Adw.ActionRow(title="Known Viruses", subtitle=str(data.get("known_viruses", "N/A")))
        row_db.add_prefix(Gtk.Image.new_from_icon_name("software-update-available-symbolic"))
        grp_metrics.add(row_db)

        # Data Stats Group
        grp_data = Adw.PreferencesGroup(title="Data Statistics")
        content_box.append(grp_data)
        
        # Read
        row_read = Adw.ActionRow(title="Data Read", subtitle=data.get("data_read", "N/A"))
        row_read.add_prefix(Gtk.Image.new_from_icon_name("text-x-generic-symbolic"))
        grp_data.add(row_read)

        # Scanned
        row_scanned = Adw.ActionRow(title="Data Scanned", subtitle=data.get("data_scanned", "N/A"))
        row_scanned.add_prefix(Gtk.Image.new_from_icon_name("drive-harddisk-symbolic"))
        grp_data.add(row_scanned)
        
        # Files
        row_files = Adw.ActionRow(title="Files Scanned", subtitle=str(data.get("scanned_files", "0")))
        grp_data.add(row_files)

        # Raw Output
        inner_scrolled = Gtk.ScrolledWindow()
        inner_scrolled.set_min_content_height(150)
        buffer = Gtk.TextBuffer()
        buffer.set_text(summary_text if summary_text else "")
        tv = Gtk.TextView(buffer=buffer)
        tv.set_editable(False)
        tv.set_monospace(True)
        tv.set_left_margin(10)
        tv.set_right_margin(10)
        tv.set_top_margin(10)
        tv.set_bottom_margin(10)
        inner_scrolled.set_child(tv)
        
        raw_expander = Gtk.Expander(label="Raw Output")
        raw_expander.set_child(inner_scrolled)
        content_box.append(raw_expander)        


class UpdateResultPage(Adw.NavigationPage):
    def __init__(self, log_text):
        super().__init__(title="Update Results", tag="update_page")
        
        data = UpdateParser.parse(log_text)
        
        # Toolbar
        tb_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        tb_view.add_top_bar(header)
        
        # Main Layout
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tb_view.set_content(root_box)
        self.set_child(tb_view)

        # Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header_box.set_margin_top(24)
        header_box.set_margin_bottom(24)
        
        icon = Gtk.Image()
        icon.set_pixel_size(64)
        
        title_lbl = Gtk.Label()
        title_lbl.add_css_class("title-2")
        desc_lbl = Gtk.Label()
        desc_lbl.add_css_class("body")
        
        # Status Logic
        if data["status"] == "Success":
            icon.set_from_icon_name("weather-clear-symbolic")
            icon.add_css_class("success")
            title_lbl.set_label("Update Successful")
            desc_lbl.set_label("Database definitions updated.")
        elif data["status"] == "Up-to-date":
            icon.set_from_icon_name("checkmark-symbolic")
            icon.add_css_class("success")
            title_lbl.set_label("Up to Date")
            desc_lbl.set_label("No new updates were found.")
        else:
            icon.set_from_icon_name("dialog-error-symbolic")
            icon.add_css_class("error")
            title_lbl.set_label("Update Failed")
            desc_lbl.set_label("Check logs for details.")

        header_box.append(icon)
        header_box.append(title_lbl)
        header_box.append(desc_lbl)
        root_box.append(header_box)
        
        # Scrollable Content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        root_box.append(scrolled)
        
        clamp = Adw.Clamp(maximum_size=600)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content_box.set_margin_top(0)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        
        clamp.set_child(content_box)
        scrolled.set_child(clamp)
        
        # DB List Group
        grp = Adw.PreferencesGroup(title="Databases")
        content_box.append(grp)
        
        for db in data["databases"]:
            title = f"{db['name'].capitalize()} Database"
            subtitle = f"Version: {db['version']}"
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            
            if db['status'] == 'Updated':
                row.add_suffix(Gtk.Label(label="Updated", css_classes=["accent"]))
            elif db['status'] == 'Up-to-date':
                row.add_suffix(Gtk.Label(label="Current", css_classes=["dim-label"]))
            
            grp.add(row)
            
        # Raw Log Viewer
        grp_logs = Adw.PreferencesGroup(title="Diagnostics")
        content_box.append(grp_logs)
        
        expander = Adw.ExpanderRow(title="Update Log", subtitle="View raw output")
        expander.set_icon_name("text-x-generic-symbolic")
        
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_min_content_height(200)
        log_scroll.set_propagate_natural_height(True)
        
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_monospace(True)
        text_view.set_left_margin(12)
        text_view.set_right_margin(12)
        text_view.set_top_margin(12)
        text_view.set_bottom_margin(12)
        text_view.get_buffer().set_text(log_text if log_text else "")
        
        log_scroll.set_child(text_view)
        expander.add_row(log_scroll)
        grp_logs.add(expander)


class DatabasePage(Adw.NavigationPage):
    def __init__(self, nav_view, on_update_callback):
        super().__init__(title="Database", tag="database_page")
        self.nav_view = nav_view
        self.on_update_callback = on_update_callback
        
        # Toolbar
        tb_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        tb_view.add_top_bar(header)
        
        # Main Container
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tb_view.set_content(root_box)
        self.set_child(tb_view)

        # --- HEADER SECTION ---
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header_box.set_margin_top(24)
        header_box.set_margin_bottom(24)
        
        self.status_icon = Gtk.Image()
        self.status_icon.set_pixel_size(64)
        
        self.status_title = Gtk.Label()
        self.status_title.add_css_class("title-2")
        
        self.status_desc = Gtk.Label()
        self.status_desc.add_css_class("body")
        self.status_desc.add_css_class("dim-label")
        
        header_box.append(self.status_icon)
        header_box.append(self.status_title)
        header_box.append(self.status_desc)
        root_box.append(header_box)

        # --- SCROLLABLE CONTENT ---
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        root_box.append(scrolled)
        
        clamp = Adw.Clamp(maximum_size=600)
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content_box.set_margin_top(0)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        
        clamp.set_child(content_box)
        scrolled.set_child(clamp)

        # Group 1: Action
        grp_action = Adw.PreferencesGroup()
        content_box.append(grp_action)
        
        action_row = Adw.ActionRow(title="Check for Updates", subtitle="Download latest signatures")
        
        # Update Button
        self.btn_update = Gtk.Button(label="Update Now")
        self.btn_update.add_css_class("suggested-action")
        self.btn_update.add_css_class("pill")
        self.btn_update.set_valign(Gtk.Align.CENTER)
        self.btn_update.connect("clicked", self.on_update_clicked)
        
        action_row.add_suffix(self.btn_update)
        grp_action.add(action_row)

        # Group 2: Database Details
        grp_details = Adw.PreferencesGroup(title="Signature Details")
        content_box.append(grp_details)
        
        # Placeholders
        self.lbl_daily = self._create_db_row(grp_details, "Daily Database")
        self.lbl_main = self._create_db_row(grp_details, "Main Database")
        self.lbl_bytecode = self._create_db_row(grp_details, "Bytecode Database")

        # Group 3: Raw Log
        grp_logs = Adw.PreferencesGroup(title="Diagnostics")
        content_box.append(grp_logs)
        
        expander = Adw.ExpanderRow(title="Last Update Log", subtitle="View raw output")
        expander.set_icon_name("text-x-generic-symbolic")
        
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_min_content_height(200)
        log_scroll.set_propagate_natural_height(True)
        
        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_view.set_left_margin(12)
        self.log_view.set_right_margin(12)
        self.log_view.set_top_margin(12)
        self.log_view.set_bottom_margin(12)
        
        log_scroll.set_child(self.log_view)
        expander.add_row(log_scroll)
        grp_logs.add(expander)

        # Load initial data
        self.refresh()

    def _create_db_row(self, group, title):
        row = Adw.ActionRow(title=title)
        row.set_icon_name("network-server-symbolic")
        lbl = Gtk.Label(label="...")
        lbl.add_css_class("accent")
        lbl.set_valign(Gtk.Align.CENTER)
        row.add_suffix(lbl)
        group.add(row)
        return lbl

    def on_update_clicked(self, btn):
        # Set loading state
        self.btn_update.set_sensitive(False)
        self.btn_update.set_label("Updating...")
        # Trigger the callback in MainWindow
        self.on_update_callback()

    def refresh(self):
        """Reloads the log file and updates all UI labels"""
        raw_log = self.get_last_update_log()
        db_info = self.parse_log_data(raw_log)
        
        # 1. Update Header
        style = self.get_recency_style(db_info['timestamp'])
        
        self.status_icon.set_from_icon_name(style['icon'])
        # Reset classes
        for c in ["success", "warning", "error", "dim-label"]:
            self.status_icon.remove_css_class(c)
        self.status_icon.add_css_class(style['color_class'])
        
        self.status_title.set_label(style['title'])
        self.status_desc.set_label(style['subtitle'])
        
        # 2. Update Details
        self.lbl_daily.set_label(f"v{db_info['versions'].get('daily', '?')}")
        self.lbl_main.set_label(f"v{db_info['versions'].get('main', '?')}")
        self.lbl_bytecode.set_label(f"v{db_info['versions'].get('bytecode', '?')}")
        
        # 3. Update Log
        self.log_view.get_buffer().set_text(raw_log if raw_log else "No logs found.")
        
        # Reset button state
        self.btn_update.set_sensitive(True)
        self.btn_update.set_label("Update Now")


    # --- PARSING HELPERS --- Should be in parser but ok
    def get_recency_style(self, timestamp):
        if not timestamp:
            return {"title": "Never Updated", "subtitle": "No history found", "icon": "dialog-question-symbolic", "color_class": "dim-label"}
        now = datetime.now()
        delta = now - timestamp
        time_str = timestamp.strftime("%b %d, %H:%M")
        if delta < timedelta(hours=24):
            return {"title": "Signatures Current", "subtitle": f"Last updated: {time_str}", "icon": "security-high-symbolic", "color_class": "success"}
        elif delta < timedelta(days=3):
            return {"title": "Signatures Aging", "subtitle": f"Last updated: {time_str}", "icon": "dialog-warning-symbolic", "color_class": "warning"}
        else:
            return {"title": "Out of Date", "subtitle": f"Last updated: {time_str}", "icon": "dialog-error-symbolic", "color_class": "error"}

    def parse_log_data(self, log_text):
        data = {"timestamp": None, "versions": {}}
        if not log_text: return data
        date_match = re.search(r"started at (.*)", log_text)
        if date_match:
            try: data["timestamp"] = datetime.strptime(date_match.group(1).strip(), "%a %b %d %H:%M:%S %Y")
            except ValueError: pass
        for line in log_text.splitlines():
            if "version:" in line:
                ver = re.search(r"version: (\d+)", line)
                v = ver.group(1) if ver else "?"
                if "daily" in line: data["versions"]["daily"] = v
                elif "main" in line: data["versions"]["main"] = v
                elif "bytecode" in line: data["versions"]["bytecode"] = v
        return data

    def get_last_update_log(self):
        base_dir = os.path.expanduser("~/.config/clambite")
        log_dir = os.path.join(base_dir, "logs")
        if not os.path.exists(log_dir): return ""
        update_logs = [f for f in os.listdir(log_dir) if f.startswith("update_") and f.endswith(".log")]
        if not update_logs: return ""
        update_logs.sort(reverse=True)
        try:
            with open(os.path.join(log_dir, update_logs[0]), "r") as f: return f.read()
        except: return ""
        
    def on_update_activated(self, content):
        try:
            page = UpdateResultPage(content)  
            self.nav_view.push(page)
        except Exception as e:
            print(f"Error reading log: {e}")

class HistoryPage(Adw.NavigationPage):
    def __init__(self, nav_view, log_dir):
        super().__init__(title="Scan History", tag="history_page")
        self.nav_view = nav_view
        self.log_dir = log_dir
        
        # Toolbar
        tb_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        
        # View Switcher in Header Title
        self.stack = Adw.ViewStack()
        switcher_title = Adw.ViewSwitcherTitle()
        switcher_title.set_stack(self.stack)
        switcher_title.set_title("History")
        header.set_title_widget(switcher_title)
        
        tb_view.add_top_bar(header)
        
        # --- 1. SETUP SCANS TAB ---
        # Icon for empty state inside the page
        scans_content = self._create_list_page(log_dir, "scan_", "Scans", "edit-find-symbolic")
        
        # Add to stack and capture the page object
        page_scans = self.stack.add_titled(scans_content, "scans", "Scans")
        
        # Set the icon for the Header Switcher explicitly
        page_scans.set_icon_name("edit-find-symbolic")
        
        # --- 2. SETUP UPDATES TAB ---
        # Icon for empty state inside the page
        updates_content = self._create_list_page(log_dir, "update_", "Updates", "view-refresh-symbolic")
        
        # Add to stack and capture the page object
        page_updates = self.stack.add_titled(updates_content, "updates", "Updates")
        
        # Set the icon for the Header Switcher explicitly
        page_updates.set_icon_name("view-refresh-symbolic")

        # Main Layout
        tb_view.set_content(self.stack)
        self.set_child(tb_view)

    def _create_list_page(self, log_dir, prefix, empty_msg, icon_name):
        clamp = Adw.Clamp(maximum_size=600)
        scrolled = Gtk.ScrolledWindow()
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        
        scrolled.set_child(box)
        clamp.set_child(scrolled)
        
        grp = Adw.PreferencesGroup()
        box.append(grp)
        
        if os.path.exists(log_dir):
            files = sorted([f for f in os.listdir(log_dir) if f.startswith(prefix) and f.endswith(".log")], reverse=True)
            if not files:
                 status = Adw.StatusPage()
                 status.set_icon_name(icon_name)
                 status.set_title("No History")
                 status.set_description(f"No {empty_msg.lower()} found.")
                 return status
            
            for f in files:
                # Get title (target name or timestamp if target not found)
                display_name = self.get_card_title(log_dir, f, prefix)
                
                # Subtitle (Date)
                # Format: scan_YYYYMMDD-HHMMSS.log
                ts_str = f.replace(prefix, "").replace(".log", "")
                subtitle = ts_str
                parts = ts_str.split("-")
                if len(parts) == 2:
                    date_part = f"{parts[0][0:4]}-{parts[0][4:6]}-{parts[0][6:8]}"
                    time_part = f"{parts[1][0:2]}:{parts[1][2:4]}"
                    subtitle = f"{date_part} at {time_part}"
                
                row = Adw.ActionRow(title=display_name, subtitle=subtitle)
                row.set_activatable(True)
                row.connect("activated", self.on_row_activated, f)
                row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
                grp.add(row)
        else:
             grp.set_description("Log directory not found.")
             
        return clamp

    def get_card_title(self, log_dir, filename, prefix):
        if not filename.startswith("scan_"):
            return "Database Update"
            
        try:
            with open(os.path.join(log_dir, filename), "r") as f:
                # Read first few lines to find target
                for i in range(5):
                    line = f.readline()
                    if "Starting Scan:" in line:
                        # Format: --- Starting Scan: /path/to/target ---
                        return line.split("Starting Scan:")[1].replace("---", "").strip()
        except:
            pass
            
        return filename.replace(prefix, "").replace(".log", "")

    def on_row_activated(self, row, filename):
        path = os.path.join(self.log_dir, filename)
        try:
            with open(path, "r") as f:
                content = f.read()
                
                if filename.startswith("scan_"):
                    page = ScanResultPage(content)
                else:
                    page = UpdateResultPage(content)
                    
                self.nav_view.push(page)
        except Exception as e:
            print(f"Error reading log: {e}")

class MainWindow(Adw.Window):
    def __init__(self, app, target_path=None):
        super().__init__(application=app, title="ClamBite")
        self.set_default_size(450, 700)
        self.target_path = target_path

        # Navigation View
        self.nav_view = Adw.NavigationView()
        self.set_content(self.nav_view)

        # --- HOME PAGE ---
        self.home_page = Adw.NavigationPage(title="ClamBite", tag="home_page")
        
        # Toolbar View for Home
        tb_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        tb_view.add_top_bar(header)
        
        # Content Area
        clamp = Adw.Clamp(maximum_size=400)
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_vbox.set_margin_top(24)
        main_vbox.set_margin_bottom(24)
        main_vbox.set_margin_start(12)
        main_vbox.set_margin_end(12)
        clamp.set_child(main_vbox)
        
        tb_view.set_content(clamp)
        self.home_page.set_child(tb_view)
        
        self.nav_view.add(self.home_page)

        # 1. Branding (Logo + Status)
        logo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        logo_box.set_vexpand(True)
        logo_box.set_valign(Gtk.Align.CENTER)

        # Get the absolute path to the directory where this script (ui.py) is located
        base_dir = os.path.dirname(os.path.realpath(__file__))
        local_icon_path = os.path.join(base_dir, "clambite.svg")
        
        img = Gtk.Image()
        
        # Priority 1: Check if the svg exists next to the script (installed location)
        if os.path.exists(local_icon_path):
            img.set_from_file(local_icon_path)
            img.set_pixel_size(256)
            
        # Priority 2: Check if the icon is installed in the system theme
        elif Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).has_icon("clambite"):
            img.set_from_icon_name("clambite")
            img.set_pixel_size(256)
            
        # Priority 3: Fallback generic icon
        else:
            img.set_from_icon_name("security-high-symbolic")
            img.set_pixel_size(96)
            
        logo_box.append(img)
        
        # Status Text
        self.lbl_status = Gtk.Label(label=self.get_database_age_string())
        self.lbl_status.add_css_class("dim-label")
        logo_box.append(self.lbl_status)
        
        main_vbox.append(logo_box)

        # 2. Progress Bar (Hidden by default)
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_visible(False)
        main_vbox.append(self.progress_bar)

        # 3. Action Grid (2x2)
        grid = Gtk.Grid(column_spacing=6, row_spacing=6)
        grid.set_column_homogeneous(True)
        grid.set_row_homogeneous(True)
        
        # Scan File
        btn_content_file = Adw.ButtonContent(icon_name="document-open-symbolic", label="Scan File")
        self.btn_scan_file = Gtk.Button()
        self.btn_scan_file.add_css_class("suggested-action")
        self.btn_scan_file.set_child(btn_content_file)
        self.btn_scan_file.connect("clicked", self.on_scan_file_clicked)
        grid.attach(self.btn_scan_file, 0, 0, 1, 1)
        
        # Scan Folder
        btn_content_folder = Adw.ButtonContent(icon_name="folder-open-symbolic", label="Scan Folder")
        self.btn_scan_folder = Gtk.Button()
        self.btn_scan_folder.add_css_class("suggested-action")
        self.btn_scan_folder.set_child(btn_content_folder)
        self.btn_scan_folder.connect("clicked", self.on_scan_folder_clicked)
        grid.attach(self.btn_scan_folder, 1, 0, 1, 1)
        
        # Database
        btn_content_db = Adw.ButtonContent(icon_name="network-server-symbolic", label="Database")
        self.btn_db = Gtk.Button()
        self.btn_db.set_child(btn_content_db)
        self.btn_db.connect("clicked", self.on_database_clicked)
        grid.attach(self.btn_db, 0, 1, 1, 1)
        
        # History
        btn_content_log = Adw.ButtonContent(icon_name="document-properties-symbolic", label="History")
        self.btn_logs = Gtk.Button()
        self.btn_logs.set_child(btn_content_log)
        self.btn_logs.connect("clicked", self.on_history_clicked)
        grid.attach(self.btn_logs, 1, 1, 1, 1)
        
        main_vbox.append(grid)

        # Stop Button (Hidden initially, replaces grid or appended?)
        self.btn_stop = Gtk.Button(label="Stop Operation")
        self.btn_stop.add_css_class("destructive-action")
        self.btn_stop.set_visible(False)
        self.btn_stop.connect("clicked", self.on_stop_clicked)
        main_vbox.append(self.btn_stop)
        
        self.btn_view_log = Gtk.Button(label="View Current Log")
        self.btn_view_log.add_css_class("flat")
        self.btn_view_log.set_tooltip_text("View detailed execution logs for current session")
        self.btn_view_log.connect("clicked", self.on_view_log_clicked)
        main_vbox.append(self.btn_view_log)

        # Logic helpers
        self.log_buffer = Gtk.TextBuffer()
        self.scanner_thread = None

        # Auto-start if command line arg provided
        if self.target_path:
            self.start_operation('scan_file', self.target_path)

    # --- Actions ---

    def on_scan_file_clicked(self, btn):
        self.choose_target(folder=False)

    def on_scan_folder_clicked(self, btn):
        self.choose_target(folder=True)

    def on_database_clicked(self, btn):
        # Open Database View
        page = DatabasePage(self.nav_view, lambda: self.start_operation('update', None))
        self.nav_view.push(page)
        
    def on_update_clicked(self, btn):
        self.start_operation('update', None)

    def on_stop_clicked(self, btn):
        if self.scanner_thread and self.scanner_thread.is_alive():
            self.scanner_thread.stop()

    def on_history_clicked(self, btn):
        base_dir = os.path.expanduser("~/.config/clambite")
        log_dir = os.path.join(base_dir, "logs")
        page = HistoryPage(self.nav_view, log_dir)
        self.nav_view.push(page)

    def on_view_log_clicked(self, btn):
        log_win = LogWindow(self, self.log_buffer)
        log_win.present()

    def choose_target(self, folder=False):
        dialog = Gtk.FileChooserNative(
            title="Select Target",
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER if folder else Gtk.FileChooserAction.OPEN
        )
        
        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                f = d.get_file()
                path = f.get_path()
                mode = 'scan_dir' if folder else 'scan_file'
                
                # Check update freshness logic
                if self.is_database_fresh():
                    self.start_operation(mode, path)
                else:
                    self.prompt_update_before_scan(mode, path)
            d.destroy()
            
        dialog.connect("response", on_response)
        dialog.show()

    def handle_external_request(self, path):
        if not os.path.exists(path):
            return

        self.present()
        self.nav_view.pop_to_tag("home_page")

        is_folder = os.path.isdir(path)
        mode = 'scan_dir' if is_folder else 'scan_file'
        
        if self.is_database_fresh():
            self.start_operation(mode, path)
        else:
            self.prompt_update_before_scan(mode, path)

    def is_database_fresh(self):
        base_dir = os.path.expanduser("~/.config/clambite")
        log_dir = os.path.join(base_dir, "logs")
        
        if not os.path.exists(log_dir):
            return False
            
        # Get all update logs
        update_logs = [f for f in os.listdir(log_dir) if f.startswith("update_") and f.endswith(".log")]
        if not update_logs:
            return False
            
        # Sort descending so newest (or weird names) are first
        update_logs.sort(reverse=True)
        
        now = datetime.now()
        
        # Loop through files to find the first VALID timestamp
        for log_file in update_logs:
            try:
                # Filename format: update_20251221-162531.log
                ts_str = log_file.replace("update_", "").replace(".log", "")
                
                # Skip files that definitely aren't timestamps (e.g. "update_latest.log")
                # Format YYYYMMDD-HHMMSS is 15 characters
                if len(ts_str) != 15:
                    continue

                last_date = datetime.strptime(ts_str, "%Y%m%d-%H%M%S")
                
                # We found a valid date! Check if it is fresh.
                delta = now - last_date
                
                # Returns True if younger than 5 days, False otherwise
                return delta.days < 5
                
            except ValueError:
                # This file wasn't a valid date, try the next one in the list
                continue
        
        # If we checked all files and none were valid dates
        return False

    def get_database_age_string(self):
        base_dir = os.path.expanduser("~/.config/clambite")
        log_dir = os.path.join(base_dir, "logs")
        
        if not os.path.exists(log_dir):
            return "Database never updated."
            
        # Filter strictly for update files
        update_logs = [f for f in os.listdir(log_dir) if f.startswith("update_") and f.endswith(".log")]
        if not update_logs:
            return "Database never updated."
            
        update_logs.sort(reverse=True)
        last_log = update_logs[0]
        
        try:
            # Filename format: update_20251221-162531.log
            # Strip prefix and extension
            ts_str = last_log.replace("update_", "").replace(".log", "")
            
            # Parse time
            last_date_full = datetime.strptime(ts_str, "%Y%m%d-%H%M%S")
            now_full = datetime.now()
            
            # Compare strictly by calendar date, ignoring the time of day
            last_date = last_date_full.date()
            today = now_full.date()
            
            delta_days = (today - last_date).days
            
            if delta_days == 0:
                return "Database updated today."
            elif delta_days == 1:
                return "Database updated yesterday."
            else:
                return f"Database updated {delta_days} days ago."
        except Exception as e:
            print(f"Date Parse Error: {e}")
            return "Status available (Check logs)"

    def prompt_update_before_scan(self, mode, path):
        dialog = Adw.MessageDialog(
            heading="Update Database?",
            body="Would you like to update the virus database before scanning?",
            transient_for=self
        )
        
        dialog.add_response("skip", "No (Scan Now)")
        dialog.add_response("update", "Yes (Update & Scan)")
        
        self.timeout_seconds = 5
        base_body = dialog.get_body()
        
        def update_countdown():
            if self.timeout_seconds > 0:
                dialog.set_body(f"{base_body}\n\nAuto-skip in {self.timeout_seconds}s...")
                self.timeout_seconds -= 1
                return True
            else:
                dialog.response("skip") 
                return False

        timer_id = GLib.timeout_add(1000, update_countdown)
        update_countdown() 

        def on_dialog_response(d, response):
            GLib.source_remove(timer_id)
            should_update = (response == "update")
            d.close()
            
            if should_update:
                self.start_operation('update', None, next_op=(mode, path))
            else:
                self.start_operation(mode, path)

        dialog.connect("response", on_dialog_response)
        dialog.present()

    def start_operation(self, mode, path, next_op=None):
        self.set_controls_sensitive(False)
        self.btn_stop.set_visible(True)
        self.progress_bar.set_visible(True)
        self.progress_bar.pulse()
        
        self.log_buffer.set_text("")
        self.current_next_op = next_op 
        
        # --- NAVIGATE TO DB PAGE IF UPDATING ---
        if mode == "update":
            # Get the currently visible page
            current_page = self.nav_view.get_visible_page()
            
            # If we are NOT already on the DatabasePage, go there.
            if not isinstance(current_page, DatabasePage):
                self.on_database_clicked(None)
        # ---------------------------------------

        self.scanner_thread = ScannerThread(
            mode=mode,
            target_path=path,
            on_log=self.log_message,
            on_status=self.update_status_display,
            on_finish=self.on_operation_finished
        )
        self.scanner_thread.start()
        
        self.pulse_timer = GLib.timeout_add(100, self.pulse_progress)


    def pulse_progress(self):
        if self.scanner_thread and self.scanner_thread.is_alive():
            self.progress_bar.pulse()
            return True
        return False

    def update_status_display(self, icon, title, subtitle):
        # Removed
        pass
        
    def log_message(self, message):
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, message + "\n")

    def on_operation_finished(self, success, context, summary=None):
        self.set_controls_sensitive(True)
        self.btn_stop.set_visible(False)
        self.progress_bar.set_visible(False)
        
        if context == 'update':
            # 1. Update the small status text on Home Page
            self.lbl_status.set_text(self.get_database_age_string())
            
            # 2. Update the DatabasePage labels in the background
            current_page = self.nav_view.get_visible_page()
            if isinstance(current_page, DatabasePage):
                current_page.refresh()

            # 3. Show the Result Page
            if not self.current_next_op:
                page = UpdateResultPage(summary)
                self.nav_view.push(page)

            # 4. Handle scheduled next operation (e.g. Scan after Update)
            if hasattr(self, 'current_next_op') and self.current_next_op:
                if success:
                    next_mode, next_path = self.current_next_op
                    self.current_next_op = None
                    GLib.timeout_add(500, self.start_operation, next_mode, next_path, None)
                else:
                    self.current_next_op = None
        else:
            # Scan finished logic
            self.current_next_op = None
            page = ScanResultPage(summary)
            self.nav_view.push(page)
            
            
    def set_controls_sensitive(self, sensitive):
        self.btn_scan_file.set_sensitive(sensitive)
        self.btn_scan_folder.set_sensitive(sensitive)
        self.btn_db.set_sensitive(sensitive)
        self.btn_logs.set_sensitive(sensitive)
