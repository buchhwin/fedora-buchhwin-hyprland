#!/usr/bin/env python3
"""Read and write ~/.config/hypr/settings.lua.

settings.lua is the single source of truth for everything the settings GUI
owns. It stays Lua — not JSON — so Hyprland can `require` it directly and so it
can still be edited by hand.

Reading it is delegated to the `lua` interpreter rather than a home-grown
parser: the file is real Lua, and a hand-rolled parser would be wrong the first
time somebody writes a comment in an unusual place. Writing it back is done
here, in a fixed layout, because that layout is ours to define.

    settings.py get look.rounding
    settings.py set look.rounding=16 theme.accent=blue
    settings.py dump                     # the whole thing as JSON
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
SETTINGS = CONFIG_HOME / "hypr" / "settings.lua"

# A minimal JSON encoder in Lua. Emitted as a here-doc so no extra Lua package
# is needed. Arrays and maps are distinguished the way Lua does it: a table
# with a [1] and no other keys is an array.
LUA_TO_JSON = r"""
local function esc(s)
  s = s:gsub('\\', '\\\\'):gsub('"', '\\"'):gsub('\n', '\\n'):gsub('\r', '\\r'):gsub('\t', '\\t')
  return s
end
local function enc(v)
  local t = type(v)
  if t == 'nil' then return 'null'
  elseif t == 'boolean' then return tostring(v)
  elseif t == 'number' then
    if v == math.floor(v) and math.abs(v) < 2^53 then return string.format('%d', v) end
    return tostring(v)
  elseif t == 'string' then return '"' .. esc(v) .. '"'
  elseif t == 'table' then
    local n = 0
    for _ in pairs(v) do n = n + 1 end
    local isArray = (n == #v)
    local out = {}
    if isArray then
      for _, x in ipairs(v) do out[#out+1] = enc(x) end
      return '[' .. table.concat(out, ',') .. ']'
    else
      local keys = {}
      for k in pairs(v) do keys[#keys+1] = tostring(k) end
      table.sort(keys)
      for _, k in ipairs(keys) do
        -- Deliberately not `v[k] ~= nil and v[k] or v[tonumber(k)]`: that
        -- idiom collapses on a value of `false`, silently turning every
        -- disabled setting into null.
        local val = v[k]
        if val == nil then val = v[tonumber(k)] end
        out[#out+1] = '"' .. esc(k) .. '":' .. enc(val)
      end
      return '{' .. table.concat(out, ',') .. '}'
    end
  end
  return 'null'
end
io.write(enc(dofile(os.getenv("BH_SETTINGS_PATH"))))
"""


def read(path: Path = SETTINGS) -> dict:
    """Return settings.lua as a Python dict."""
    if not path.exists():
        raise SystemExit(f"not found: {path}")
    lua = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
    if lua is None:
        raise SystemExit("the 'lua' interpreter is required to read settings.lua")
    env = {**os.environ, "BH_SETTINGS_PATH": str(path)}
    proc = subprocess.run([lua, "-e", LUA_TO_JSON],
                          capture_output=True, text=True, env=env, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"settings.lua is not valid Lua:\n{proc.stderr.strip()}")
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------
def _lua_value(v, indent: int) -> str:
    pad = "    " * indent
    inner = "    " * (indent + 1)
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "nil"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, list):
        if not v:
            return "{}"
        parts = [inner + _lua_value(x, indent + 1) + "," for x in v]
        return "{\n" + "\n".join(parts) + "\n" + pad + "}"
    if isinstance(v, dict):
        if not v:
            return "{}"
        parts = []
        for k, val in v.items():
            key = k if str(k).isidentifier() else f'["{k}"]'
            parts.append(f"{inner}{key} = {_lua_value(val, indent + 1)},")
        return "{\n" + "\n".join(parts) + "\n" + pad + "}"
    return "nil"


HEADER = """-- Buchhwin Control Center — user settings
--
-- Rewritten by the settings GUI and by `bhctl`. Hand edits are kept: the file
-- is read, changed and written back as a whole, so anything you add survives
-- as long as it is plain data.
--
-- Comments, however, do NOT survive a write from the GUI — Lua comments are
-- not part of the data. Put anything you want to keep in ~/.config/hypr/
-- settings.local.lua instead.

"""


def write(data: dict, path: Path = SETTINGS) -> None:
    # Write to a temporary file and move it into place: a crash halfway through
    # must never leave a truncated settings.lua, which would cost you the
    # desktop on the next reload.
    tmp = path.with_suffix(".lua.tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(HEADER + "return " + _lua_value(data, 0) + "\n")

    lua = shutil.which("lua") or shutil.which("lua5.4")
    if lua:
        check = subprocess.run(
            [lua, "-e", 'dofile(os.getenv("BH_SETTINGS_PATH"))'],
            capture_output=True, text=True, check=False,
            env={**os.environ, "BH_SETTINGS_PATH": str(tmp)})
        if check.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise SystemExit(f"refusing to write invalid Lua:\n{check.stderr.strip()}")

    if path.exists():
        shutil.copy2(path, path.with_suffix(".lua.bak"))
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Dotted paths
# ---------------------------------------------------------------------------
def get_path(data: dict, dotted: str):
    node = data
    for part in dotted.split("."):
        if isinstance(node, list):
            node = node[int(part)]
        else:
            node = node[part]
    return node


def set_path(data: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def parse_value(raw: str):
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("nil", "null"):
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    # Lists and tables, as JSON. The writer has always been able to put a list
    # into settings.lua — `monitors` is one — but this function could not READ
    # one, so `set dock.pinned=["kitty"]` stored the six characters of the text
    # and the dock then had one pinned application called `["kitty"]`.
    #
    # Tried after the numbers, and only for text that starts like a container,
    # so an ordinary string is never handed to a JSON parser by accident.
    if raw[:1] in ("[", "{"):
        try:
            return json.loads(raw)
        except ValueError:
            pass
    return raw


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]

    if cmd == "dump":
        print(json.dumps(read(), indent=2))
        return 0

    if cmd == "get":
        data = read()
        for dotted in argv[2:]:
            # A key that is not in settings.lua is the normal case, not a
            # crash: a setting nobody has touched yet simply has no entry, and
            # every caller here already treats empty output as "use the
            # default". Printing a KeyError traceback for it put a wall of
            # Python into an installer log that was otherwise clean.
            try:
                value = get_path(data, dotted)
            except (KeyError, IndexError, TypeError):
                print()
                continue
            print(value if not isinstance(value, (dict, list))
                  else json.dumps(value, indent=2))
        return 0

    if cmd == "set":
        data = read()
        for pair in argv[2:]:
            if "=" not in pair:
                raise SystemExit(f"expected key=value, got: {pair}")
            key, _, raw = pair.partition("=")
            set_path(data, key.strip(), parse_value(raw.strip()))
        write(data)
        print(f"  settings: {len(argv) - 2} value(s) updated")
        return 0

    raise SystemExit(f"unknown command: {cmd}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
