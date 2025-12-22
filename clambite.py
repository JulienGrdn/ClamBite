#!/usr/bin/env python3

import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gio, Adw

from ui import MainWindow

class ClamAVApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.github.juliengrdn.clambite",
                         flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.target_file = None

    def do_activate(self):
        win = self.props.active_window
        
        if not win:
            # First launch: Pass the file to __init__
            win = MainWindow(self, self.target_file)
        elif self.target_file:
            # App already running: Manually pass the file to the existing window
            if hasattr(win, 'handle_external_request'):
                win.handle_external_request(self.target_file)
        
        win.present()
        
        # Important: Clear the file so we don't re-scan it if you just click the dock icon later
        self.target_file = None

    def do_open(self, files, n_files, hint):
        if n_files > 0:
            self.target_file = files[0].get_path()
        self.activate()

    def do_command_line(self, command_line):
        args = command_line.get_arguments()
        if len(args) > 1:
            self.target_file = args[1]
        self.activate()
        return 0

if __name__ == "__main__":
    app = ClamAVApp()
    app.run(sys.argv)
