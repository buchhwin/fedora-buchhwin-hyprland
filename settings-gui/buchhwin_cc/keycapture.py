"""Press the combination instead of typing its name."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk  # noqa: E402


class KeyCaptureDialog(Adw.Window):
    """Press the combination instead of typing its name.

    Typing "SUPER + odiaeresis" from memory is exactly the kind of thing nobody
    should have to do, and the usual source of shortcuts that silently do not
    work.
    """

    MODS = [
        (Gdk.ModifierType.SUPER_MASK, "SUPER"),
        (Gdk.ModifierType.CONTROL_MASK, "CTRL"),
        (Gdk.ModifierType.ALT_MASK, "ALT"),
        (Gdk.ModifierType.SHIFT_MASK, "SHIFT"),
    ]

    def __init__(self, parent, on_captured):
        super().__init__(transient_for=parent, modal=True,
                         default_width=420, default_height=200)
        self.on_captured = on_captured
        self.set_title(_("Press a key combination"))

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=24, margin_bottom=24,
                      margin_start=24, margin_end=24)
        box.append(Adw.HeaderBar(show_end_title_buttons=False))
        self.label = Gtk.Label(label=_("Waiting…"))
        self.label.add_css_class("title-1")
        box.append(self.label)
        hint = Gtk.Label(label=_("Escape cancels."))
        hint.add_css_class("dim-label")
        box.append(hint)
        self.set_content(box)

        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key)
        self.add_controller(controller)

    def _on_key(self, _c, keyval, _code, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        name = Gdk.keyval_name(keyval)
        # Ignore the modifiers themselves; the user is still on their way to
        # the real key.
        if name in ("Super_L", "Super_R", "Control_L", "Control_R",
                    "Alt_L", "Alt_R", "Shift_L", "Shift_R", "ISO_Level3_Shift"):
            return True
        parts = [label for mask, label in self.MODS if state & mask]
        parts.append(name)
        combo = " + ".join(parts)
        self.label.set_label(combo)
        self.on_captured(combo)
        GLib.timeout_add(350, self.close)
        return True


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
