#!/usr/bin/env python3
"""

.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html
   http://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_google.html
"""
import signal
from PyQt4 import QtGui
from PyQt4 import QtCore

from file_watcher import FileQueue
from sync_api import Rsync
from sync_api import Dropbox
from animated_system_tray import AnimatedSystemTrayIcon


class App(QtGui.QApplication):

    # signals need to be class variables
    start_animation = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__([])
        self.window = QtGui.QWidget()

        self.file_queue = FileQueue()
        self.rsync = Rsync(
            self.file_queue, progress_callback=self.handle_sync_progress)
        self.rsync.start()
        self.dropbox = Dropbox(
            self.file_queue, progress_callback=self.handle_sync_progress)
        self.dropbox.start()

        self.tray_icon = AnimatedSystemTrayIcon('icon.svg', parent=self.window)

        # We need to do this with a signal because the animation must be
        # triggered from the main thread.
        self.start_animation.connect(
            #self.tray_icon.get_animator('shrink', minimum=0.4))
            self.tray_icon.get_animator('rotate'))

        self.build_gui()

    def handle_sync_progress(self, progress):
        if progress == 0.0:
            self.start_animation.emit()
        elif progress == 1.0:
            self.tray_icon.stop_animation()

    def build_gui(self):
        menu = QtGui.QMenu()
        for (entry, action) in [
            ('start rotate', self.tray_icon.get_animator('rotate')),
            ('stop animation', self.tray_icon.stop_animation),
            ('quit', self.quit),
        ]:
            q_action = QtGui.QAction(entry, self)
            q_action.triggered.connect(action)
            menu.addAction(q_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def quit(self, *args, **kwargs):
        self.file_queue.stop()
        self.rsync.stop()
        self.dropbox.stop()
        QtGui.qApp.quit()


if __name__ == '__main__':
    app = App()

    # handle sigint gracefully
    signal.signal(signal.SIGINT, app.quit)
    # needed to catch the signal (http://stackoverflow.com/a/4939113/2972353)
    timer = QtCore.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.

    # start the app
    app.exec_()
