-- Buchhwin Control Center — user settings
--
-- This file holds every value the settings GUI owns. It is plain data: no
-- logic, no function calls. The GUI reads and rewrites it wholesale, which is
-- why it must stay a simple table — the GUI never parses hand-written Lua.
--
-- Edit it by hand if you like; the GUI will keep your values and only change
-- the ones you change there. It is copied here once on install and then left
-- alone by updates, so `bhctl update` can never overwrite your preferences.

return {
    -- =====================================================================
    -- Look
    -- =====================================================================
    look = {
        border_size       = 2,
        gaps_in           = 5,
        gaps_out          = 12,
        rounding          = 12,

        -- Gap when only ONE window is open. Small rather than zero: flush
        -- against the screen edge looks broken, not roomy. Fullscreen still
        -- has no gap at all — that is what fullscreen is for.
        gaps_single       = 4,

        -- Mouse pointer. Any theme under /usr/share/icons with a cursors/
        -- directory works. breeze_cursors is KDE's dark Breeze — the package
        -- ships exactly two, "breeze_cursors" and "Breeze_Light", so the dark
        -- one is the unsuffixed name and not "Breeze_Dark".
        cursor_theme      = "breeze_cursors",
        cursor_size       = 24,

        -- Transparency: visible, but text stays fully legible everywhere.
        -- The focused window is never transparent — you read that one.
        active_opacity    = 1.00,
        inactive_opacity  = 0.94,
        terminal_opacity  = 0.90,

        -- Blur only on the bar, menus and the terminal. Blurring every window
        -- costs real performance for no visual gain.
        blur              = true,
        blur_size         = 6,
        blur_passes       = 2,

        shadow            = true,
        shadow_range      = 12,

        animations        = true,
        -- "work" is quick and restrained, "showcase" is slower with more blur
        -- for screenshots and video.
        profile           = "work",
    },

    -- =====================================================================
    -- Theme
    -- =====================================================================
    theme = {
        flavour = "mocha",     -- mocha | macchiato | frappe | latte
        accent  = "mauve",     -- any Catppuccin colour name
    },

    -- =====================================================================
    -- Input
    -- =====================================================================
    input = {
        kb_layout      = "de",
        kb_variant     = "",
        kb_options     = "",
        follow_mouse   = 1,
        sensitivity    = 0,
        repeat_rate    = 40,
        repeat_delay   = 300,
        natural_scroll = true,
        tap_to_click   = true,
        accel_profile  = "adaptive",
    },

    -- =====================================================================
    -- Idle and lock (seconds; 0 disables that step)
    -- =====================================================================
    idle = {
        dim_after   = 300,
        lock_after  = 600,
        screen_off  = 900,
        suspend_after = 0,       -- 0: never suspend on its own
    },

    -- =====================================================================
    -- Night light
    -- =====================================================================
    nightlight = {
        enabled     = true,
        day_temp    = 6500,
        night_temp  = 4000,
    },

    -- =====================================================================
    -- Programs the key bindings refer to
    -- =====================================================================
    programs = {
        terminal      = "kitty",
        browser       = "brave-origin",
        file_manager  = "nemo",
        editor        = "code",
        launcher      = "rofi -show drun",
        calendar      = "gnome-calendar",
        mail          = "evolution",
        image_viewer  = "loupe",
        music         = "flatpak run com.spotify.Client",
    },

    -- =====================================================================
    -- Key bindings
    --
    -- action is one of:
    --   "exec"      arg = command line
    --   "dispatch"  arg = name of an entry in binds.lua's dispatch table
    -- Anything the GUI does not recognise is passed through untouched.
    -- =====================================================================
    binds = {
        -- your six fixed ones
        { key = "SUPER + Return",       action = "exec",     arg = "@terminal",     desc = "Terminal" },
        { key = "SUPER + Q",            action = "dispatch", arg = "close",         desc = "Close window" },
        { key = "SUPER + S",            action = "exec",     arg = "@screenshot region", desc = "Screenshot: region" },
        { key = "SUPER + V",            action = "exec",     arg = "@clipboard",    desc = "Clipboard history" },
        { key = "SUPER + B",            action = "exec",     arg = "@browser",      desc = "Browser" },
        { key = "SUPER + E",            action = "exec",     arg = "@file_manager", desc = "File manager" },

        -- launcher and menus
        { key = "SUPER + Space",        action = "exec",     arg = "@launcher",     desc = "Application launcher" },
        { key = "SUPER + R",            action = "exec",     arg = "@launcher",     desc = "Application launcher" },
        { key = "SUPER + Tab",          action = "exec",     arg = "@windowmenu",   desc = "Window switcher" },
        { key = "SUPER + W",            action = "exec",     arg = "@wallpapermenu",desc = "Wallpaper picker" },
        { key = "SUPER + period",       action = "exec",     arg = "@emojimenu",    desc = "Emoji picker" },
        { key = "SUPER + slash",        action = "exec",     arg = "@keysmenu",     desc = "Keyboard shortcuts" },
        { key = "SUPER + I",            action = "exec",     arg = "buchhwin-control-center", desc = "Settings" },
        { key = "SUPER + N",            action = "exec",     arg = "swaync-client -t -sw", desc = "Notification panel" },
        { key = "SUPER + M",            action = "exec",     arg = "wlogout",       desc = "Power menu" },
        { key = "SUPER + L",            action = "exec",     arg = "hyprlock",      desc = "Lock screen" },

        -- capture
        { key = "SUPER + SHIFT + S",    action = "exec",     arg = "@screenshot screen", desc = "Screenshot: whole screen" },
        { key = "SUPER + CTRL + S",     action = "exec",     arg = "@screenshot window", desc = "Screenshot: active window" },
        { key = "Print",                action = "exec",     arg = "@screenshot screen", desc = "Screenshot: whole screen" },
        { key = "SUPER + SHIFT + V",    action = "exec",     arg = "@record",       desc = "Screen recording on/off" },
        { key = "SUPER + C",            action = "exec",     arg = "@colorpicker",  desc = "Colour picker" },

        -- windows
        { key = "SUPER + F",            action = "dispatch", arg = "fullscreen",    desc = "Fullscreen" },
        { key = "SUPER + SHIFT + F",    action = "dispatch", arg = "float",         desc = "Floating on/off" },
        { key = "SUPER + P",            action = "dispatch", arg = "pin",           desc = "Pin window" },
        { key = "SUPER + J",            action = "dispatch", arg = "togglesplit",   desc = "Toggle split direction" },
        { key = "SUPER + G",            action = "exec",     arg = "@togglegaps",   desc = "Gaps on/off" },
        { key = "SUPER + T",            action = "exec",     arg = "@toggletheme",  desc = "Light / dark" },
        { key = "SUPER + SHIFT + R",    action = "exec",     arg = "@reload",       desc = "Reload configuration" },

        -- work
        { key = "SUPER + SHIFT + C",    action = "exec",     arg = "@editor",       desc = "Editor" },
        { key = "SUPER + SHIFT + E",    action = "exec",     arg = "@rootfiles",    desc = "File manager as root" },
        { key = "SUPER + odiaeresis",   action = "dispatch", arg = "scratchpad",    desc = "Drop-down terminal" },
        { key = "SUPER + SHIFT + odiaeresis", action = "dispatch", arg = "to_scratchpad", desc = "Move window to scratchpad" },

        { key = "ALT + F4",             action = "dispatch", arg = "close",         desc = "Close window" },
        { key = "ALT + Space",          action = "exec",     arg = "@search",       desc = "Search everything" },

        -- Arrows MOVE the window; snapping is one modifier along. Listed here
        -- so they appear in the cheat sheet and the settings app; the bindings
        -- themselves live in binds.lua because they are structural.
        { key = "SUPER + Left",         action = "info", arg = "move left",         desc = "Move window left" },
        { key = "SUPER + Right",        action = "info", arg = "move right",        desc = "Move window right" },
        { key = "SUPER + Up",           action = "info", arg = "move up",           desc = "Move window up" },
        { key = "SUPER + Down",         action = "info", arg = "move down",         desc = "Move window down" },
        { key = "SUPER + CTRL + Left",  action = "info", arg = "@snap smart-left",  desc = "Snap: left half" },
        { key = "SUPER + CTRL + Right", action = "info", arg = "@snap smart-right", desc = "Snap: right half" },
        { key = "SUPER + CTRL + Up",    action = "info", arg = "@snap smart-up",    desc = "Snap: maximize" },
        { key = "SUPER + CTRL + Down",  action = "info", arg = "@snap smart-down",  desc = "Snap: restore" },
        { key = "SUPER + SHIFT + Left", action = "info", arg = "@snap top-left",    desc = "Quarter: top left" },
        { key = "SUPER + SHIFT + Right",action = "info", arg = "@snap top-right",   desc = "Quarter: top right" },
        { key = "SUPER + SHIFT + Down", action = "info", arg = "@snap bottom-left", desc = "Quarter: bottom left" },
        { key = "SUPER + SHIFT + Up",   action = "info", arg = "@snap maximize",    desc = "Quarter: maximize" },
        { key = "SUPER + ALT + 1…9",    action = "info", arg = "move to workspace", desc = "Move window to a workspace" },
        { key = "SUPER + SHIFT + Space",action = "info", arg = "@floatws",          desc = "Workspace: tiling / floating" },
    },

    -- =====================================================================
    -- Workspaces
    -- Named rather than numbered, so the bar tells you what is where.
    -- =====================================================================
    workspaces = {
        { id = 1, name = "term" },
        { id = 2, name = "web"  },
        { id = 3, name = "code" },
        { id = 4, name = "mon"  },
        { id = 5, name = "chat" },
        { id = 6, name = "6"    },
        { id = 7, name = "7"    },
        { id = 8, name = "8"    },
        { id = 9, name = "9"    },
        { id = 10, name = "10"  },
    },

    -- =====================================================================
    -- Monitors
    --
    -- Empty means "detect everything automatically", which is right for a
    -- single screen and for the test VM.
    --
    -- Screens are identified by DESCRIPTION, not by DP-1 / HDMI-A-1. Connector
    -- names change when you move a cable; the description does not. Get yours
    -- with: hyprctl -j monitors | jq -r '.[].description'
    --
    -- { desc = "Dell Inc. DELL U2720Q", mode = "3840x2160@60",
    --   position = "auto", scale = 1.5, primary = true, enabled = true }
    -- =====================================================================
    monitors = {},

    -- Which workspaces live on which screen. Fixed assignment: 1-5 on the
    -- primary, 6-10 on the second, so SUPER+3 always lands in the same place.
    -- With one screen all ten are simply there.
    workspace_layout = "fixed",   -- "fixed" | "dynamic"

    -- =====================================================================
    -- Wallpaper
    --
    -- "static"    one picture, chosen with the file picker
    -- "slideshow" everything in a folder, in turn
    -- =====================================================================
    wallpaper = {
        mode        = "slideshow",
        path        = "",            -- static: the file
        folder      = "",            -- slideshow: the folder (searched recursively)
        interval    = 1800,          -- seconds between changes; 0 = only at login
        order       = "random",      -- "random" | "alphabetical"
        transition  = "grow",
        per_monitor = false,         -- a different picture on each screen
        follow_theme = true,         -- pick one matching the flavour when none is set
    },

    -- =====================================================================
    -- Layout and window behaviour
    --
    -- Tiling is the default. Any workspace listed in floating_workspaces
    -- behaves like Windows instead: windows float, drag freely, and snap
    -- magnetically to edges and to each other.
    -- =====================================================================
    layout = {
        default             = "dwindle",   -- "dwindle" | "master"
        snap                = true,        -- magnetic snapping for floating windows
        snap_window_gap     = 12,
        snap_monitor_gap    = 12,
        floating_workspaces = {},          -- e.g. { 5 }

        -- Drag a window's edge to resize it. Off, because Hyprland's grab area
        -- reaches 15px past the border and swallows clicks meant for the close
        -- button. SUPER + right-drag resizes regardless of this setting.
        resize_on_border    = false,
    },

    -- =====================================================================
    -- Drives — written by the settings GUI, read by scripts/drives.py
    --
    -- Cloud entries are rclone remotes; network entries are gvfs mounts.
    -- Neither ever contains a password: those live in the keyring.
    -- =====================================================================
    drives = {
        -- { kind = "cloud",   name = "GoogleDrive", provider = "drive",
        --   mount = "~/Drives/GoogleDrive", automount = true },
        -- { kind = "network", name = "NAS", type = "smb",
        --   host = "nas.local", share = "data", user = "jan", automount = true },
    },

    -- =====================================================================
    -- Autostart — extra programs, on top of the systemd user services
    -- =====================================================================
    autostart = {
        "nm-applet --indicator",
        "blueman-applet",
    },

    -- =====================================================================
    -- Bar
    -- =====================================================================
    bar = {
        position = "top",
        floating = true,            -- floating island vs. edge-to-edge
        height   = 38,
        modules_left   = { "custom/logo", "hyprland/workspaces", "hyprland/submap" },
        modules_center = { "hyprland/window" },
        modules_right  = { "tray", "pulseaudio", "bluetooth", "network",
                           "cpu", "memory", "battery", "clock", "custom/power" },
    },
}
