#!/usr/bin/env python3

import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gio, Adw

from ui import MainWindow

class ClamAVApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.github.julienGrdn.ClamBite",
                         flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.target_file = None

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(self, self.target_file)
        win.present()

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
