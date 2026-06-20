# shellcheck shell=sh
# Sourced from /etc/profile.d; no shebang.
if [ -s /rw/config/split-ssh-default-agent ]; then
    QUBES_SSH_AGENT=$(cat /rw/config/split-ssh-default-agent)
    export QUBES_SSH_AGENT
    export SSH_AUTH_SOCK="$HOME/.split-ssh/${QUBES_SSH_AGENT}.sock"
fi
