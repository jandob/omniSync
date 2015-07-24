#!/usr/bin/env python3
import signal
import math
import functools
from PyQt4 import QtGui
from PyQt4 import QtCore


class AnimationFunctions:
    """
    Predefined animation functions.
        @progress: the progress of the animation (0.0-1.0)
        @pixmap_original: the original image
    Note:
        Options for the animation can be provided via keyword arguments.
    """
    @staticmethod
    def shrink(pixmap_original, progress, minimum=0.4):
        shrink_factor = (1.0 - math.sin(progress * math.pi) ** 2)
        shrink_factor = minimum + ((1 - minimum) * shrink_factor)
        x = max(1, int(pixmap_original.width() * shrink_factor))
        return pixmap_original.scaled(
            x, x, transformMode=QtCore.Qt.SmoothTransformation
        )

    @staticmethod
    def rotate(pixmap_original, progress):
        width = pixmap_original.width()
        height = pixmap_original.height()

        rotated = QtGui.QPixmap(pixmap_original.transformed(
            QtGui.QTransform().rotateRadians(progress * 2 * math.pi)
        ))

        xoffset = (rotated.width() - width) / 2
        yoffset = (rotated.height() - height) / 2

        return rotated.copy(xoffset, yoffset, width, height)


class AnimatedSystemTrayIcon(QtGui.QSystemTrayIcon):
    def __init__(self, icon_file_name, parent=None):
        super().__init__(parent)
        self._pixmap = QtGui.QPixmap(icon_file_name)
        self.setIcon(QtGui.QIcon(self._pixmap))

    def _initialize_animation(self, animation_length_seconds):
        frames_per_second = 24.0
        self._frame_length_milliseconds = int(1000 / frames_per_second)
        self._frames = int(animation_length_seconds * frames_per_second)

    def _animate(self, animation_function):
        self._timer = QtCore.QTimer()
        self._repeat = True
        self._frame = 0

        def advance_frame():
            # animation progress from 0-1
            progress = self._frame / float(self._frames)
            self.setIcon(QtGui.QIcon(
                animation_function(self._pixmap, progress)
            ))
            if self._frame < self._frames:
                self._frame += 1
            elif self._repeat:
                self._frame = 0
            else:
                self._timer.stop()

        self._timer.timeout.connect(advance_frame)
        self._timer.start(self._frame_length_milliseconds)

    def stop_animation(self):
        self._repeat = False

    def get_animator(
        self, animation_function, animation_length_seconds=1, **kwargs
    ):
        """ returns a function that animates the icon when invoked"""
        def animator():
            self._initialize_animation(animation_length_seconds)
            if callable(animation_function):
                self._animate(animation_function)
            else:
                self._animate(functools.partial(
                    getattr(AnimationFunctions, animation_function), **kwargs
                ))
        return animator


class App():
    def __init__(self):
        app = QtGui.QApplication([])
        window = QtGui.QWidget()

        tray_icon = AnimatedSystemTrayIcon('icon.svg', parent=window)

        menu = QtGui.QMenu()
        for (entry, action) in [
            ('start rotate', tray_icon.get_animator('rotate')),
            ('start shrink', tray_icon.get_animator('shrink', minimum=0.4)),
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
