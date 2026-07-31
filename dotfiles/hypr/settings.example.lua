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
        terminal     = "kitty",
        browser      = "brave-origin",
        file_manager = "nemo",
        editor       = "code",
        launcher     = "rofi -show drun",
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
    -- Empty means "detect everything automatically", which is right for a
    -- single screen and for the test VM.
    -- =====================================================================
    monitors = {},

    -- =====================================================================
    -- Wallpaper
    -- =====================================================================
    wallpaper = {
        path         = "",          -- empty: pick the one matching the flavour
        transition   = "grow",
        follow_theme = true,
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
