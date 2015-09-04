#!/usr/bin/env python3
"""

.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html
   http://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_google.html
"""
import signal
from PyQt4 import QtGui
from PyQt4 import QtCore

import sys
sys.dont_write_bytecode = True

import config
from file_watcher import FileQueue
from file_watcher import FileWatcher
from sync_api import SyncManager
from animated_system_tray import AnimatedSystemTrayIcon


class App(QtGui.QApplication):

    # signals need to be class variables
    start_animation = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__([])
        self.window = QtGui.QWidget()
        self.tray_icon = AnimatedSystemTrayIcon('icon.svg', parent=self.window)

        self.file_queue = FileQueue()
        self.watchers = []
        self.progress = {}
        self.progress_menu_items = {}
        for watch_config in config.data['watches']:
            if not watch_config.get('disabled'):
                self.watchers.append(
                    FileWatcher(self.file_queue, watch_config))
        self.sync_manager = SyncManager(
            self.file_queue, progress_callback=self.handle_sync_progress)

        self.progress = {syncer: 1.0 for syncer in
                         self.sync_manager.syncers.values()}

        # We need to do this with a signal because the animation must be
        # triggered from the main thread.
        self.start_animation.connect(
            #self.tray_icon.get_animator('shrink', minimum=0.4))
            self.tray_icon.get_animator('rotate'))

        self.build_gui()

    def show_progress(self):
        for syncer, val in self.progress.items():
            item = self.progress_menu_items.get(syncer.name, None)
            if item:
                item.setText(
                    '%s: %0.0f%% (queue: %s)'
                    % (syncer.name, val * 100, syncer.queue.qsize())
                )

    def handle_sync_progress(self, syncer, file, progress):
        self.progress[syncer] = progress
        progresses = self.progress.values()
        if any([val == 0.0 for val in progresses]):
            self.start_animation.emit()
        if all([val == 1.0 for val in progresses]):
            self.tray_icon.stop_animation()
        self.show_progress()

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

        menu.addSeparator()
        menu.setSeparatorsCollapsible(True)
        for syncer in self.progress:
            q_action = QtGui.QAction(syncer.name, self)
            self.progress_menu_items[syncer.name] = q_action
            menu.addAction(q_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def quit(self, *args, **kwargs):
        [w.stop() for w in self.watchers]
        self.sync_manager.stop()
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
