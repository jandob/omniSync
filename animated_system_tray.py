#!/usr/bin/env python3
"""

.. _Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html
   http://sphinxcontrib-napoleon.readthedocs.org/en/latest/example_google.html
"""
import math
import functools
from PyQt4 import QtGui
from PyQt4 import QtCore


class AnimationFunctions:
    """
    Predefined animation functions.

    The functions are called with the following positional arguments:
    Args:
        progress(float): The progress of the animation (0.0-1.0).
        pixmap_original(QPixmap): The original image.
        **kwargs: Can be used to provide customizable animations.
    Returns:
        Qpixmap: A new pixmap that corresponds to the animation `progress`,
            `pixmap_original` should not be altered.

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
        self._original_pixmap = QtGui.QPixmap(icon_file_name)
        self.setIcon(QtGui.QIcon(self._original_pixmap))
        self.animating = False

    def _initialize_animation(self, animation_length_seconds):
        frames_per_second = 24.0
        self._frame_length_milliseconds = int(1000 / frames_per_second)
        self._frames = int(animation_length_seconds * frames_per_second)

    def _animate(self, animation_function):
        if self.animating: return
        self.animating = True
        self._timer = QtCore.QTimer()
        self._repeat = True
        self._frame = 0

        def advance_frame():
            # animation progress from 0-1
            progress = self._frame / float(self._frames)
            self.setIcon(QtGui.QIcon(
                animation_function(self._original_pixmap, progress)
            ))
            if self._frame < self._frames:
                self._frame += 1
            elif self._repeat:
                self._frame = 0
            else:
                self._timer.stop()
                self.animating = False

        self._timer.timeout.connect(advance_frame)
        self._timer.start(self._frame_length_milliseconds)

    def stop_animation(self):
        self._repeat = False

    def get_animator(
        self, animation_function, animation_length_seconds=1.0, **kwargs
    ):
        """ Creates a function thath animates the icon when invoked.

        Args:
            animation_function (string or callable): The function that animates
                the icon. If not callable it is used as key to access a
                predefined animation function from `AnimationFunctions`.
            animation_length_seconds (Optional[float]): Defaults to 1.0.
                Length in seconds the animation runs (one loop).
            **kwargs: Keyword arguments are passed to the `animation_function`.

        Returns:
            callable: When invoked starts the animation.
        """
        def animator():
            self._initialize_animation(animation_length_seconds)
            if callable(animation_function):
                self._animate(animation_function)
            else:
                self._animate(functools.partial(
                    getattr(AnimationFunctions, animation_function), **kwargs
                ))
        return animator
