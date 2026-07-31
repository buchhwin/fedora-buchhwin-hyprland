-- Key bindings.
--
-- The bindings themselves live in settings.lua as plain data, so the settings
-- GUI can rewrite them without ever touching this file. This file is the
-- translation layer: it turns each { key, action, arg } entry into a real
-- hl.bind() call, and it owns everything that is structural rather than a
-- preference (workspace numbers, focus movement, media keys).

local S = require("settings")
local P = S.programs or {}
local SCRIPTS = os.getenv("HOME") .. "/.local/share/fedora-buchhwin-hyprland/scripts"

------------------------------------------------------------------------------
-- @-tokens
--
-- settings.lua refers to programs and helper scripts by name (@terminal,
-- @screenshot region). Keeping the real command lines here means changing your
-- terminal is one edit in one place, and the GUI can offer a friendly list
-- instead of asking for a shell command.
------------------------------------------------------------------------------
local tokens = {
    terminal      = P.terminal or "kitty",
    browser       = P.browser or "brave-origin",
    file_manager  = P.file_manager or "nemo",
    editor        = P.editor or "code",
    launcher      = P.launcher or "rofi -show drun",

    windowmenu    = "rofi -show window",
    clipboard     = SCRIPTS .. "/clipboard-menu.sh",
    emojimenu     = SCRIPTS .. "/emoji-menu.sh",
    wallpapermenu = SCRIPTS .. "/wallpaper-menu.sh",
    keysmenu      = SCRIPTS .. "/keybinds-menu.sh",
    screenshot    = SCRIPTS .. "/screenshot.sh",
    record        = SCRIPTS .. "/record.sh",
    colorpicker   = SCRIPTS .. "/colorpicker.sh",
    togglegaps    = SCRIPTS .. "/toggle-gaps.sh",
    toggletheme   = "bhctl theme toggle",
    reload        = SCRIPTS .. "/reload.sh",
    -- Root file manager: pkexec so the polkit agent asks properly, and a
    -- distinct window class so rules.lua can mark it red. Running a whole GUI
    -- as root is a blunt instrument, but it is the honest one for the job.
    rootfiles     = "pkexec env DISPLAY=$DISPLAY WAYLAND_DISPLAY=$WAYLAND_DISPLAY " ..
                    "XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR nemo",
}

local function expand(arg)
    if type(arg) ~= "string" then return arg end
    -- "@screenshot region" -> "<path>/screenshot.sh region"
    local name, rest = arg:match("^@([%w_]+)(.*)$")
    if name and tokens[name] then
        return tokens[name] .. rest
    end
    return arg
end

------------------------------------------------------------------------------
-- Dispatch actions available to settings.lua
------------------------------------------------------------------------------
local dispatch = {
    close          = function() return hl.dsp.window.close() end,
    fullscreen     = function() return hl.dsp.window.fullscreen() end,
    float          = function() return hl.dsp.window.float({ action = "toggle" }) end,
    pin            = function() return hl.dsp.window.pin() end,
    pseudo         = function() return hl.dsp.window.pseudo() end,
    togglesplit    = function() return hl.dsp.layout("togglesplit") end,
    scratchpad     = function() return hl.dsp.workspace.toggle_special("scratch") end,
    to_scratchpad  = function() return hl.dsp.window.move({ workspace = "special:scratch" }) end,
    exit           = function() return hl.dsp.exit() end,
}

------------------------------------------------------------------------------
-- Bindings from settings.lua
------------------------------------------------------------------------------
for _, b in ipairs(S.binds or {}) do
    if b.action == "exec" then
        hl.bind(b.key, hl.dsp.exec_cmd(expand(b.arg)))
    elseif b.action == "dispatch" and dispatch[b.arg] then
        hl.bind(b.key, dispatch[b.arg]())
    end
end

------------------------------------------------------------------------------
-- Structural bindings
--
-- Not in settings.lua on purpose: these are the grammar of the window manager,
-- not preferences. Exposing ten workspace switches in a settings list would
-- only be noise.
------------------------------------------------------------------------------

-- focus
local dirs = { h = "left", j = "down", k = "up", l = "right",
               left = "left", down = "down", up = "up", right = "right" }
for key, dir in pairs(dirs) do
    hl.bind("SUPER + " .. key,           hl.dsp.focus({ direction = dir }))
    hl.bind("SUPER + SHIFT + " .. key,   hl.dsp.window.move({ direction = dir }))
end

-- resize, in a submap so you can hold and adjust rather than tap repeatedly
hl.bind("SUPER + CTRL + h", hl.dsp.window.resize({ x = -60, y = 0 }), { repeating = true })
hl.bind("SUPER + CTRL + l", hl.dsp.window.resize({ x =  60, y = 0 }), { repeating = true })
hl.bind("SUPER + CTRL + k", hl.dsp.window.resize({ x = 0, y = -60 }), { repeating = true })
hl.bind("SUPER + CTRL + j", hl.dsp.window.resize({ x = 0, y =  60 }), { repeating = true })

-- workspaces
for i = 1, 10 do
    local key = i % 10
    hl.bind("SUPER + " .. key,         hl.dsp.focus({ workspace = i }))
    hl.bind("SUPER + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }))
end
hl.bind("SUPER + mouse_down", hl.dsp.focus({ workspace = "e+1" }))
hl.bind("SUPER + mouse_up",   hl.dsp.focus({ workspace = "e-1" }))

-- mouse
hl.bind("SUPER + mouse:272", hl.dsp.window.drag(),   { mouse = true })
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true })

------------------------------------------------------------------------------
-- Media and hardware keys
--
-- locked = true so they still work on the lock screen, which is where you most
-- often want to mute something in a hurry.
------------------------------------------------------------------------------
local mk = { locked = true, repeating = true }
hl.bind("XF86AudioRaiseVolume",  hl.dsp.exec_cmd("wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 5%+"), mk)
hl.bind("XF86AudioLowerVolume",  hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), mk)
hl.bind("XF86AudioMute",         hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true })
hl.bind("XF86AudioMicMute",      hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), { locked = true })
hl.bind("XF86MonBrightnessUp",   hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%+"), mk)
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%-"), mk)
hl.bind("XF86AudioNext",         hl.dsp.exec_cmd("playerctl next"), { locked = true })
hl.bind("XF86AudioPrev",         hl.dsp.exec_cmd("playerctl previous"), { locked = true })
hl.bind("XF86AudioPlay",         hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPause",        hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
