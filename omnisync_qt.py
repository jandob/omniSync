#!/usr/bin/env python3
import signal
import math
from PyQt4 import QtGui
from PyQt4 import QtCore


class AnimatedSystemTrayIcon(QtGui.QSystemTrayIcon):
    def __init__(self, icon_file_name, parent=None):
        super().__init__(parent)
        self._pixmap_original = QtGui.QPixmap(icon_file_name)
        self.setIcon(QtGui.QIcon(self._pixmap_original))

    def _initialize_animation(self):
        animation_length_seconds = 1
        frames_per_second = 24.0
        self._frame_length_milliseconds = int(1000 / frames_per_second)
        self._frames = int(animation_length_seconds * frames_per_second)

    def _start_animation(self, calculate_frame):
        # Create a QTimer
        self._timer = QtCore.QTimer()
        self._repeat = True
        self._frame = 0

        def advance_frame():
            # animation progress from 0-1
            progress = self._frame / float(self._frames)
            self.setIcon(calculate_frame(progress))
            if self._frame < self._frames:
                self._frame += 1
            elif self._repeat:
                self._frame = 0
            else:
                self._timer.stop()

        self._timer.timeout.connect(advance_frame)
        self._timer.start(self._frame_length_milliseconds)

    def stop_animation(self, *args):
        self._repeat = False

    def shrink(self, *args):
        self._initialize_animation()

        def calculate_frame(progress):
            minimum = 0.4
            shrink_factor = (1.0 - math.sin(progress * math.pi) ** 2)
            shrink_factor = minimum + ((1 - minimum) * shrink_factor)
            x = max(1, int(self._pixmap_original.width() * shrink_factor))
            return QtGui.QIcon(self._pixmap_original.scaled(
                x, x, transformMode=QtCore.Qt.SmoothTransformation
            ))
        self._start_animation(calculate_frame)

    def rotate(self):
        self._initialize_animation()

        def calculate_frame(progress):
            width = self._pixmap_original.width()
            height = self._pixmap_original.height()

            rotated = QtGui.QPixmap(self._pixmap_original.transformed(
                QtGui.QTransform().rotateRadians(progress * 2 * math.pi)
            ))

            xoffset = (rotated.width() - width) / 2
            yoffset = (rotated.height() - height) / 2

            rotated = rotated.copy(xoffset, yoffset, width, height)
            return QtGui.QIcon(rotated)
        self._start_animation(calculate_frame)

class App():
    def __init__(self):
        app = QtGui.QApplication([])
        window = QtGui.QWidget()

        tray_icon = AnimatedSystemTrayIcon('icon.svg', parent=window)

        menu = QtGui.QMenu()
        for (entry, action) in [
            ('start animation', tray_icon.rotate),
            ('stop animation', tray_icon.stop_animation),
            ('quit', QtGui.qApp.quit),
        ]:
            q_action = QtGui.QAction(entry, app)
            q_action.triggered.connect(action)
            menu.addAction(q_action)

        tray_icon.setContextMenu(menu)
        tray_icon.show()

        app.exec_()

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    App()
