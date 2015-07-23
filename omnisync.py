#!/usr/bin/env python2
import signal
import math
from gi.repository import Gtk as gtk
from gi.repository import GLib as glib
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository.GdkPixbuf import InterpType


class AnimatedStatusIcon(gtk.StatusIcon):
    def __init__(self, image_file):
        gtk.StatusIcon.__init__(self)
        self.icon = Pixbuf.new_from_file(image_file)
        self.set_from_pixbuf(self.icon)

    def _initialize_animation(self):
        animation_length_seconds = 0.5
        frames_per_second = 24.0
        self._frame_length_milliseconds = int(1000 / frames_per_second)
        self._frames = int(animation_length_seconds * frames_per_second)

    def _start_animation(self, calculate_frame):
        self._repeat = True
        self._frame = 0

        def advance_frame():
            # animation progress from 0-1
            progress = self._frame / float(self._frames)
            self.set_from_pixbuf(calculate_frame(progress))
            if self._frame < self._frames:
                self._frame += 1
                return True
            elif self._repeat:
                self._frame = 0
                return True
            else:
                # return False -> cancel timeout_add
                return False
        glib.timeout_add(self._frame_length_milliseconds, advance_frame)

    def stop_animation(self, *args):
        self._repeat = False

    def shrink(self, *args):
        self._initialize_animation()

        def calculate_frame(progress):
            x = max(1, int(
                self.icon.get_width() *
                (1.0 - math.sin(progress * math.pi) ** 2)
            ))
            return self.icon.scale_simple(x, x, InterpType.BILINEAR)
        self._start_animation(calculate_frame)


class App:
    def __init__(self):
        self.status_icon = AnimatedStatusIcon('icon.svg')
        self.status_icon.connect("popup-menu", self.right_click_event)

        window = gtk.Window()
        window.connect("destroy", gtk.main_quit)
        #window.show_all() # only needed if a main window is implemented

    def right_click_event(self, icon, button, time):
        self.menu = gtk.Menu()
        for (entry, action) in [
            ('start animation', self.status_icon.shrink),
            ('stop animation', self.status_icon.stop_animation),
            ('about', self.show_about_dialog),
            ('quit', gtk.main_quit),
        ]:
            menu_item = gtk.MenuItem()
            menu_item.set_label(entry)
            menu_item.connect('activate', action)
            self.menu.append(menu_item)

        self.menu.popup(
            parent_menu_shell=None, parent_menu_item=None,
            func=gtk.StatusIcon.position_menu,
            data=self.status_icon,
            button=button, activate_time=time
        )

        self.menu.show_all()

    def show_about_dialog(self, widget):
        about_dialog = gtk.AboutDialog()

        about_dialog.set_logo(Pixbuf.new_from_file('icon.svg'))
        about_dialog.set_destroy_with_parent(True)
        about_dialog.set_program_name("OmniSync")
        about_dialog.set_website("http://github.com/jandob/omniSync")
        about_dialog.set_version("0.1")
        about_dialog.set_authors(["Janosch Dobler", "Torben Sickert"])

        about_dialog.run()
        about_dialog.destroy()

App()
signal.signal(signal.SIGINT, signal.SIG_DFL)  # close app on ctrl-c
gtk.main()
