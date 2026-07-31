# zsh — interactive shell.
#
# zsh rather than fish: fish is nicer out of the box, but it is not POSIX, so
# every snippet from a vendor doc or a wiki has to be translated before it runs.
# For a sysadmin that trade is not worth it.
#
# starship rather than powerlevel10k: p10k has been in limited support since
# 2024, and its config is a ~1700 line zsh script that cannot be templated.
# starship is one toml file, so the prompt recolours with the rest of the
# desktop instead of being the one thing left behind.
#
# The two completion plugins come from Fedora packages, not git clones, so they
# update with everything else.

# ---------------------------------------------------------------------------
# History — generous, shared, deduplicated
# ---------------------------------------------------------------------------
HISTFILE="${XDG_STATE_HOME:-$HOME/.local/state}/zsh/history"
HISTSIZE=100000
SAVEHIST=100000
mkdir -p "${HISTFILE:h}"

setopt EXTENDED_HISTORY          # timestamps, so `atuin` and `fc` agree
setopt INC_APPEND_HISTORY        # write as you go, not on exit
setopt SHARE_HISTORY             # every terminal sees every command
setopt HIST_IGNORE_ALL_DUPS
setopt HIST_IGNORE_SPACE         # a leading space keeps it out of history
setopt HIST_REDUCE_BLANKS
setopt HIST_VERIFY               # expand !! before running it, not after

# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------
setopt AUTO_CD
setopt AUTO_PUSHD
setopt PUSHD_IGNORE_DUPS
setopt INTERACTIVE_COMMENTS
setopt NO_BEEP
setopt CORRECT

# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------
autoload -Uz compinit
# Only rebuild the completion dump once a day; compinit on every shell is the
# usual reason zsh feels slow to start.
_zcompdump="${XDG_CACHE_HOME:-$HOME/.cache}/zsh/zcompdump"
mkdir -p "${_zcompdump:h}"
if [[ -n ${_zcompdump}(#qN.mh+24) ]]; then
    compinit -d "$_zcompdump"
else
    compinit -C -d "$_zcompdump"
fi

zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}' 'r:|=*' 'l:|=* r:|=*'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*' group-name ''
zstyle ':completion:*:descriptions' format '%F{yellow}-- %d --%f'

# ---------------------------------------------------------------------------
# Plugins (Fedora packages)
# ---------------------------------------------------------------------------
[[ -f /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]] \
    && source /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh
# Syntax highlighting must be sourced LAST of the two, or it does not wrap the
# widgets the other plugin installs.
[[ -f /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]] \
    && source /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

# ---------------------------------------------------------------------------
# Key bindings
# ---------------------------------------------------------------------------
bindkey -e                                   # emacs keys; vi mode fights fzf
bindkey '^[[A' history-search-backward
bindkey '^[[B' history-search-forward
bindkey '^[[1;5C' forward-word
bindkey '^[[1;5D' backward-word
bindkey '^[[3~' delete-char
bindkey '^[[H' beginning-of-line
bindkey '^[[F' end-of-line

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
command -v starship >/dev/null && eval "$(starship init zsh)"
command -v zoxide   >/dev/null && eval "$(zoxide init zsh --cmd cd)"
command -v direnv   >/dev/null && eval "$(direnv hook zsh)"

# atuin replaces Ctrl-R with a searchable, synced history. --disable-up-arrow
# keeps the plain up-arrow behaving the way muscle memory expects.
command -v atuin >/dev/null && eval "$(atuin init zsh --disable-up-arrow)"

if command -v fzf >/dev/null; then
    source <(fzf --zsh) 2>/dev/null
    command -v fd >/dev/null && export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
fi

# Colours for fzf, bat and eza. Generated from the active palette, so the shell
# follows a theme switch instead of staying on the Mocha hex values that used
# to be written out here by hand.
[[ -r "${XDG_CONFIG_HOME:-$HOME/.config}/buchhwin/shell-colors.sh" ]] \
    && source "${XDG_CONFIG_HOME:-$HOME/.config}/buchhwin/shell-colors.sh"

# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------
if command -v eza >/dev/null; then
    alias ls='eza --group-directories-first --icons'
    alias ll='eza -l --group-directories-first --icons --git'
    alias la='eza -la --group-directories-first --icons --git'
    alias lt='eza --tree --level=2 --icons'
else
    alias ll='ls -lh --color=auto'
    alias la='ls -lha --color=auto'
fi

# BAT_THEME comes from shell-colors.sh above. It used to say "Catppuccin Mocha"
# — a theme that was never installed, so bat warned on every call.
command -v bat >/dev/null && alias cat='bat --paging=never' 
command -v fd  >/dev/null && alias find='fd'
command -v rg  >/dev/null && alias grep='rg'
command -v duf >/dev/null && alias df='duf'
command -v lazygit >/dev/null && alias lg='lazygit'
command -v yazi >/dev/null && alias y='yazi'

alias ..='cd ..'
alias ...='cd ../..'
alias mkdir='mkdir -p'
alias ip='ip -color=auto'

# systemd, which is most of the job
alias sc='systemctl'
alias scu='systemctl --user'
alias jc='journalctl'
alias jcf='journalctl -f'
alias jce='journalctl -p err -b'

# containers
alias pps='podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
alias pim='podman images'

# this project
alias bh='bhctl'

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
export EDITOR="${EDITOR:-nvim}"
command -v nvim >/dev/null || export EDITOR=vim
export VISUAL="$EDITOR"
export PAGER=less
export LESS='-R --mouse'
export MANROFFOPT='-c'
command -v bat >/dev/null && export MANPAGER="sh -c 'col -bx | bat -l man -p'"

# ---------------------------------------------------------------------------
# Local overrides — never tracked, never overwritten by an update
# ---------------------------------------------------------------------------
[[ -f ~/.zshrc.local ]] && source ~/.zshrc.local
