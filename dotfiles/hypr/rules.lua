-- Window and workspace rules.
--
-- Two jobs here:
--   1. make the desktop behave (dialogs float, pickers centre, nothing steals
--      focus at the wrong moment);
--   2. put applications where they belong, so a fresh login lands in a working
--      layout instead of one pile of windows on workspace 1.

local S = require("settings")
local look = S.look or {}
local layout = S.layout or {}

------------------------------------------------------------------------------
-- Workspaces
------------------------------------------------------------------------------
for _, ws in ipairs(S.workspaces or {}) do
    hl.workspace_rule({ workspace = tostring(ws.id), default_name = ws.name })
end

-- Fixed assignment across screens: 1-5 belong to the primary, 6-10 to the
-- second. SUPER+3 therefore always lands on the same screen, which is the
-- whole point — with a wandering assignment you never know where a window
-- will appear.
--
-- The rules only bind if that screen exists, so a single-monitor machine keeps
-- all ten workspaces without a special case anywhere in the code.
if (S.workspace_layout or "fixed") == "fixed" then
    local primary, secondary
    for _, m in ipairs(S.monitors or {}) do
        if m.enabled ~= false then
            if m.primary and not primary then primary = "desc:" .. (m.desc or "")
            elseif not secondary and m.desc then secondary = "desc:" .. m.desc end
        end
    end
    if primary then
        for i = 1, 5 do
            hl.workspace_rule({ workspace = tostring(i), monitor = primary })
        end
    end
    if secondary then
        for i = 6, 10 do
            hl.workspace_rule({ workspace = tostring(i), monitor = secondary })
        end
    end
end

-- Workspaces that behave like Windows: everything floats, and general.snap
-- makes dragged windows click into place.
for _, id in ipairs(layout.floating_workspaces or {}) do
    hl.workspace_rule({ workspace = tostring(id), default_float = true })
end

-- Smart gaps: a single tiled window gets the whole screen. Nice on a laptop,
-- and it makes screenshots of one window look deliberate rather than cropped.
hl.workspace_rule({ workspace = "w[tv1]", gaps_out = 0, gaps_in = 0 })
hl.workspace_rule({ workspace = "f[1]",   gaps_out = 0, gaps_in = 0 })
hl.window_rule({
    name = "no-gaps-single", match = { float = false, workspace = "w[tv1]" },
    border_size = 0, rounding = 0,
})
hl.window_rule({
    name = "no-gaps-fullscreen", match = { float = false, workspace = "f[1]" },
    border_size = 0, rounding = 0,
})

------------------------------------------------------------------------------
-- Sanity
------------------------------------------------------------------------------
hl.window_rule({
    name = "suppress-maximize", match = { class = ".*" },
    suppress_event = "maximize",
})

-- XWayland drag-and-drop leaves stray unnamed windows behind; without this
-- they steal focus mid-drag.
hl.window_rule({
    name = "fix-xwayland-drags",
    match = { class = "^$", title = "^$", xwayland = true,
              float = true, fullscreen = false, pin = false },
    no_focus = true,
})

------------------------------------------------------------------------------
-- Transparency
--
-- Only the terminal and file manager are see-through. An editor or a browser
-- with the wallpaper showing through the text is the classic rice mistake:
-- looks good in one screenshot, unreadable after ten minutes of work.
------------------------------------------------------------------------------
-- `opacity` is declared as a string in WINDOW_RULE_EFFECT_DESCS, so it takes
-- the classic "<active> <inactive>" rule string, not a Lua table.
local term_op = look.terminal_opacity or 0.90
hl.window_rule({ name = "term-opacity", match = { class = "^(kitty)$" },
                 opacity = string.format("%.2f %.2f", term_op, term_op - 0.04) })
hl.window_rule({ name = "files-opacity", match = { class = "^(nemo)$" },
                 opacity = "0.96 0.92" })
-- Never make these transparent, whatever the global setting says.
hl.window_rule({ name = "opaque-media",
                 match = { class = "^(vlc|mpv|obs|Gimp|krita|firefox|brave-origin)$" },
                 opacity = "1.0 1.0" })

------------------------------------------------------------------------------
-- Floating dialogs
------------------------------------------------------------------------------
local floaters = {
    "^(pavucontrol)$", "^(blueman-manager)$", "^(nm-connection-editor)$",
    "^(org.kde.polkit-kde-authentication-agent-1)$", "^(hyprpolkitagent)$",
    "^(qt6ct)$", "^(kvantummanager)$", "^(buchhwin-control-center)$",
    "^(org.gnome.Calculator)$", "^(file-roller)$", "^(xdg-desktop-portal-gtk)$",
}
for i, cls in ipairs(floaters) do
    hl.window_rule({ name = "float-" .. i, match = { class = cls },
                     float = true, center = true })
end

hl.window_rule({ name = "float-dialogs",
                 match = { title = "^(Open|Save|Select|Choose|Print)( .*)?$" },
                 float = true, center = true, size = "980 640" })

-- The settings window: fixed, comfortable size, centred.
hl.window_rule({ name = "settings-size", match = { class = "^(buchhwin-control-center)$" },
                 size = "1000 700", float = true, center = true })

------------------------------------------------------------------------------
-- Running something as root should be impossible to miss
------------------------------------------------------------------------------
hl.window_rule({
    name = "root-warning",
    match = { class = "^(nemo)$", title = ".*(root|Root).*" },
    border_size = 4,
    -- Catppuccin red, deliberately hard-coded: this warning must not change
    -- colour with the flavour.
    border_color = "rgba(f38ba8ff)",
})

------------------------------------------------------------------------------
-- Where applications open
------------------------------------------------------------------------------
local placement = {
    { class = "^(brave-origin|firefox)$",            workspace = "2" },
    { class = "^(code|Code|jetbrains-.*)$",          workspace = "3" },
    { class = "^(btop|nvtop)$",                      workspace = "4" },
    { class = "^(discord|vesktop|Slack)$",           workspace = "5" },
    { class = "^(Spotify|spotify)$",                 workspace = "5" },
    { class = "^(virt-manager|Remmina|wireshark)$",  workspace = "4" },
    -- The web apps get their own homes too, otherwise they land wherever.
    { class = "^(brave-origin-teams)$",              workspace = "5" },
    { class = "^(brave-origin-chatgpt)$",            workspace = "5" },
    { class = "^(brave-origin-claude)$",             workspace = "5" },
    { class = "^(brave-origin-whatsapp)$",           workspace = "5" },
    { class = "^(brave-origin-outlook)$",            workspace = "2" },
    { class = "^(brave-origin-microsoft-365)$",      workspace = "2" },
    { class = "^(gnome-calendar|org.gnome.Calendar)$", workspace = "4" },
}
for i, p in ipairs(placement) do
    hl.window_rule({ name = "place-" .. i, match = { class = p.class },
                     workspace = p.workspace })
end

------------------------------------------------------------------------------
-- Picture-in-picture: always visible, out of the way, never tiled
------------------------------------------------------------------------------
hl.window_rule({
    name = "pip",
    match = { title = "^(Picture[- ]in[- ][Pp]icture)$" },
    float = true, pin = true, size = "480 270",
    move = "monitor_w-500 monitor_h-290",
})

------------------------------------------------------------------------------
-- Layers: the bar, menus and notifications get blur, not shadows
------------------------------------------------------------------------------
hl.layer_rule({ name = "blur-bar",    match = { namespace = "^waybar$" },  blur = true, ignore_alpha = 0.2 })
hl.layer_rule({ name = "blur-rofi",   match = { namespace = "^rofi$" },    blur = true, ignore_alpha = 0.2 })
hl.layer_rule({ name = "blur-notify", match = { namespace = "^swaync-(control-center|notification-window)$" },
                blur = true, ignore_alpha = 0.2 })
hl.layer_rule({ name = "blur-logout", match = { namespace = "^wlogout$" }, blur = true })

------------------------------------------------------------------------------
-- Scratchpad terminal
------------------------------------------------------------------------------
hl.workspace_rule({ workspace = "special:scratch", on_created_empty = (S.programs or {}).terminal or "kitty" })
