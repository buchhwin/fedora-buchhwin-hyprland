#!/usr/bin/env bash
# English strings — the source language. Every key must exist here; other
# languages fall back to this file, so a missing translation degrades to
# English instead of printing nothing.
#
# Placeholders are always %s, never %d — the values are passed as shell words.

declare -gA MSG=(
    # --- banner --------------------------------------------------------------
    [banner]="fedora-buchhwin-hyprland"
    [banner_sub]="flavour %s / accent %s / profile %s"
    [banner_dry]="Dry run: nothing will be changed."

    # --- generic errors ------------------------------------------------------
    [err_trap]="Stopped at line %s (exit code %s). Nothing further was attempted."
    [err_running_as_root]="Run this as your normal user, not as root. sudo is used where it is needed."
    [err_no_sudo]="sudo is required and the password was not accepted."
    [ok_sudo_passwordless]="sudo works without a password"
    [err_sudo_unattended]="Unattended mode needs passwordless sudo. Either run without --unattended, or add a NOPASSWD rule for this user."
    [err_aborted]="Aborted."

    # --- preflight -----------------------------------------------------------
    [sec_preflight]="Checking the system"
    [err_not_fedora]="This installer is for Fedora. Detected: %s"
    [ok_fedora]="Fedora %s"
    [warn_fedora_version]="Fedora %s found, this release targets Fedora %s. Package names may differ."
    [ask_continue_anyway]="Continue anyway?"
    [err_arch]="Unsupported architecture: %s"
    [err_no_network]="No connection to the Fedora mirrors."
    [ok_network]="Network reachable"
    [warn_low_space]="Only %s MB free on /. About 12 GB is needed."
    [ok_space]="%s GB free on /"
    [info_gpu_detected]="Graphics detected: %s"
    [info_vm_detected]="Running inside a virtual machine (%s)"
    [ok_log]="Log: %s"

    # --- repositories --------------------------------------------------------
    [sec_repos]="Repositories and codecs"
    [step_rpmfusion]="Adding RPM Fusion (free and nonfree)"
    [info_rpmfusion_present]="RPM Fusion already enabled"
    [fail_rpmfusion]="RPM Fusion could not be enabled"
    [step_copr]="Enabling COPR %s"
    [info_copr_present]="COPR %s already enabled"
    [fail_copr]="COPR %s could not be enabled"
    [info_minimal_skip_repos]="--minimal: skipping application repositories"
    [step_repo]="Adding the %s repository"
    [info_repo_present]="%s repository already present"
    [fail_repo]="The %s repository could not be added"
    [step_flathub]="Adding Flathub (system-wide)"
    [fail_flathub]="Flathub could not be added"
    [info_flatpak_disabled]="--no-flatpak: skipping Flatpaks"
    [step_codecs]="Enabling multimedia codecs"
    [info_ffmpeg_present]="Full ffmpeg already installed"
    [fail_ffmpeg]="ffmpeg-free could not be swapped for ffmpeg"
    [warn_multimedia]="The multimedia group did not update cleanly"
    [step_gpu]="Installing %s graphics drivers"
    [step_nvidia_build]="Building the NVIDIA kernel module"
    [warn_akmods]="akmods failed. The NVIDIA module is not built; do not reboot yet."
    [warn_dracut]="dracut failed. The initramfs was not regenerated."
    [warn_secureboot]="Secure Boot is enabled. The NVIDIA module must be signed and its key enrolled, otherwise the machine boots to a black screen."
    [info_gpu_none]="No dedicated graphics driver needed"

    # --- base ----------------------------------------------------------------
    [sec_base]="Base system"
    [step_update]="Updating installed packages"
    [warn_update]="The system update did not finish cleanly"
    [step_shell]="Setting up the shell"
    [info_shell_already]="zsh is already the login shell"
    [ok_shell]="zsh is now the login shell"
    [warn_chsh]="The login shell could not be changed. Run: chsh -s /usr/bin/zsh"

    # --- desktop -------------------------------------------------------------
    [sec_desktop]="Desktop"
    [ok_hyprland]="Hyprland %s"
    [fail_hyprland_old]="Hyprland %s is too old. The configuration in this repository is Lua, which needs 0.55 or newer."
    [step_sddm]="Enabling the login manager"
    [ok_session]="Session entry installed"

    # --- applications --------------------------------------------------------
    [sec_sysadmin]="Sysadmin toolkit"
    [sec_apps]="Applications"
    [info_minimal_skip_apps]="--minimal: skipping applications"
    [step_wireshark_group]="Adding you to the wireshark group"
    [info_relogin_needed]="Takes effect after the next login"
    [step_subuid]="Setting up subuid/subgid ranges for rootless containers"
    [step_flatpak]="Installing Flatpak %s"
    [fail_flatpak]="Flatpak %s could not be installed"
    [sec_webapps]="Web applications"
    [warn_no_browser]="No browser found, skipping the web applications"

    # --- theme ---------------------------------------------------------------
    [sec_theme]="Fonts and theme"
    [warn_download]="%s could not be downloaded"
    [step_nerd_font]="Installing JetBrainsMono Nerd Font %s"
    [info_font_present]="Nerd Font already installed"
    [ok_font]="Nerd Font installed"
    [fail_font]="The Nerd Font could not be installed. Icons in the bar and prompt will be missing."
    [step_cursors]="Installing the cursor theme %s"
    [info_cursor_present]="Cursor theme already installed"
    [ok_cursors]="Cursor theme installed"
    [step_icons]="Installing and recolouring icons"
    [warn_icons]="The icon theme could not be recoloured"
    [step_kvantum]="Installing the Qt (Kvantum) theme"
    [warn_kvantum]="Kvantum theme %s not found"
    [step_sddm_theme]="Installing the greeter theme %s"
    [ok_sddm_theme]="Greeter theme installed"
    [step_render_theme]="Rendering all configurations for %s / %s"
    [fail_theme]="The theme could not be rendered"

    # --- dotfiles ------------------------------------------------------------
    [sec_dotfiles]="Configuration"
    [step_backup]="Moving %s aside to %s"
    [warn_missing_src]="Missing in the repository: %s"
    [step_settings_seed]="Creating settings.lua from the example"
    [info_settings_kept]="Existing settings.lua kept"
    [step_bhctl]="Installing the bhctl command"
    [step_session_env]="Writing the session environment"
    [ok_dotfiles]="Configuration in place"

    # --- services ------------------------------------------------------------
    [sec_services]="Background services"
    [step_enable_units]="Enabling user services"
    [warn_unit]="Service %s could not be enabled"
    [ok_services]="Services enabled"

    # --- virtual machine -----------------------------------------------------
    [sec_vm]="Virtual machine"
    [info_vm_explain]="No GPU available: rendering happens on the CPU. Blur and animations are switched off, and can be switched back on in the settings."
    [step_vm_effects]="Switching off the expensive effects"
    [warn_vm_effects]="The effect settings could not be written"
    [ok_vm]="Adjusted for the virtual machine"

    # --- packages ------------------------------------------------------------
    [warn_missing_list]="Package list not found: %s"
    [info_all_present]="Everything already installed"
    [step_installing]="Installing %s packages"
    [fail_dnf_group]="The group install failed; retrying one package at a time"
    [fail_pkg]="Package could not be installed: %s"

    # --- summary -------------------------------------------------------------
    [sec_summary]="Summary"
    [sum_installed]="installed"
    [sum_skipped]="already there"
    [sum_warnings]="warnings"
    [sum_failures]="failures"
    [sum_warn_header]="Warnings:"
    [sum_fail_header]="Failures:"
    [sum_log]="Full log: %s"
    [sum_dry_run]="Dry run finished. Nothing was changed."
    [sum_incomplete]="Finished with failures. See the log before rebooting."
    [sum_done]="Done."
    [sum_next_reboot]="Reboot, then pick the \"Hyprland (Buchhwin)\" session at the login screen."
    [sum_next_keys]="SUPER+/ shows every keyboard shortcut."
    [sum_next_settings]="SUPER+I opens the settings."
)
