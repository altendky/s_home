# export NVM_DIR="$HOME/.nvm"
# [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
# function nvm
#     bash -c "source ~/.nvm/nvm.sh; nvm $argv"
# end
# https://gist.github.com/calle2010/b3f0054c1d4b72394d0fda7f22d47b38
function load_nvm --on-variable PWD
  set -l default_node_version (nvm version default)
  set -l node_version (nvm version)
  set -l nvmrc_path (nvm_find_nvmrc)
  if test -n "$nvmrc_path"
    set -l nvmrc_node_version (nvm version (cat $nvmrc_path))
    if test "$nvmrc_node_version" = "N/A"
      nvm install (cat $nvmrc_path)
    else if test "$nvmrc_node_version" != "$node_version"
      nvm use $nvmrc_node_version
    end
  else if test "$node_version" != "$default_node_version"
    echo "Reverting to default Node version"
    nvm use default
  end
end

function nvm
  set -x current_path (mktemp)
  bash -c "source ~/.nvm/nvm.sh --no-use; nvm $argv; dirname \$(nvm which current) >$current_path"
  fish_add_path -m (cat $current_path)
  rm $current_path
end

function nvm_find_nvmrc
  bash -c "source ~/.nvm/nvm.sh --no-use; nvm_find_nvmrc"
end

#alias npm="socket npm"
#alias npx="socket npx"
#alias socket-nvm-install="nvm ls --no-colors --no-alias | sed -n 's/.*v\(.*\) .*/\1/p' | xargs -i'{}' bash -lc 'nvm exec {} npm install --global @socketsecurity/cli'"

#function ct
#    cd /epc/t/$argv
#end

function td
    sudo tailscale down
end

function tu
    sudo tailscale down
    sudo tailscale up --reset --accept-routes --shields-up
end

function tun
    sudo tailscale down
    sudo tailscale up --reset --accept-routes --shields-up --exit-node 100.96.223.31
end

function fix-mouse
    # qdbus org.kde.kded5 /modules/kded_touchpad org.kde.touchpad.disable
    sudo rmmod psmouse
    sudo modprobe psmouse
    sleep 5
    sudo udevadm trigger -s input
    # xinput disable "Synaptics TM3512-010"
    # sleep 2
    # xinput enable "Synaptics TM3512-010"
    sleep 2
    xinput set-prop "Synaptics TM3512-010" "libinput Tapping Enabled" 1
    # sleep 2
    # qdbus org.kde.kded5 /modules/kded_touchpad org.kde.touchpad.reloadSettings
    # sleep 2
    # qdbus org.kde.kded5 /modules/kded_touchpad org.kde.touchpad.enable
end

function fix-kde
    killall plasmashell kwin
    kstart5 kwin
    sleep 5
    kstart5 plasmashell
end

function fix-fiio
    bluetoothctl disconnect 40:ED:98:1A:99:B4
    systemctl restart bluetooth
    fuser -v /dev/snd/*
    bluetoothctl connect 40:ED:98:1A:99:B4
    pactl list cards
end

function cr
    cd /epc/repos/$argv
end

function cdr
    cd ~/repos/$argv
end

function cg
    cd /home/altendky/repos/gw/$argv
end

function confish
    eval $EDITOR ~/.config/fish/config.fish
end
alias fource 'source ~/.config/fish/config.fish'

function dmesgrun
    sudo bash -c "echo about to run: $argv > /dev/kmsg"
    eval $argv
end

function byebyedocker
    docker stop (docker ps -qa)
    docker rm (docker ps -qa)
    docker rmi -f (docker images -qa)
    docker volume rm (docker volume ls -q)
    docker network rm (docker network ls -q)
    docker system prune --all --force
    docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
end

function renice-rust
    sudo -v
    set REFRESH_TIME (sudo sudo -V | awk '/Authentication timestamp timeout:/ {printf "%d%s\n", $4 / 2, substr($5, 1, 1)}')
    while true
        echo "    refreshing sudo (every $REFRESH_TIME)"
        sudo -v
        timeout --signal=kill "$REFRESH_TIME" sudo execsnoop-bpfcc -u altendky 2>/dev/null | sed --unbuffered -nE 's/^(cargo|sccache|rustc|cc|ld)\s+([0-9]+)\s.*/\2/p' | xargs --replace={} sudo renice -n -20 {} || true
    end
end

function renice-python
    while true
        sudo -v
        sudo renice -n -20 (ps aux | grep -E '(python .*pytest|chia_data_layer)' | grep -v grep | awk -F ' ' '{print($2)}')
        sleep 1
    end
end

function gwts
    cdm
    gwt switch $argv
end

function journal-vac
    df -h /var/log/journal
    du -hs /var/log/journal
    sudo journalctl --vacuum-size=500M
    df -h /var/log/journal
    du -hs /var/log/journal
end

function target-vac
    cd /home/altendky/repos/gw/monorepo.gwt/
    df -h .
    find . -type d -name target | xargs -I {} rm -rf {}
    df -h .
end

# https://github.com/xtendo-org/chips#gnulinux-x64
alias get_chips 'curl -Lo ~/.local/bin/chips --create-dirs
    https://github.com/xtendo-org/chips/releases/download/1.1.2/chips_gnulinux
    ; and chmod +x ~/.local/bin/chips'

alias cdm 'cd ~/repos/gw/monorepo/'
alias gfm "fish -c 'cdm && git pull'"
alias o 'opencode'
alias ai-cli 'opencode run'
#alias aicli 'claude'
alias oc 'ai-cli /commit'
alias odp 'ai-cli /describe_pr'
#alias cdp 'mv ~/.gitignore ~/.gitignore.moved || true && claude /describe_pr && mv ~/.gitignore.moved ~/.gitignore'

alias gda 'git-dag --all'

alias gl 'git log --graph'
alias gl1 "git log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold green)(%ar)%C(reset) %C(white)%s%C(reset) %C(dim white)- %an%C(reset)%C(auto)%d%C(reset)'"
alias gl2 "git log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold cyan)%aD%C(reset) %C(bold green)(%ar)%C(reset)%C(auto)%d%C(reset)%n''          %C(white)%s%C(reset) %C(dim white)- %an%C(reset)'"
alias gl3 "git log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold cyan)%aD%C(reset) %C(bold green)(%ar)%C(reset) %C(bold cyan)(committed: %cD)%C(reset) %C(auto)%d%C(reset)%n''          %C(white)%s%C(reset)%n''          %C(dim white)- %an <%ae> %C(reset) %C(dim white)(committer: %cn <%ce>)%C(reset)'"
alias gl1f "gl1 --first-parent"
alias gl2f "gl2 --first-parent"
alias gl3f "gl3 --first-parent"
alias gs 'git status'
alias gc 'git commit'
alias gp 'git pull --rebase'
alias gco 'git checkout'
alias gd 'git diff'
alias gdt 'git difftool'
alias gdtd 'git difftool --dir-diff'
alias gdtdc 'git difftool --dir-diff --cached'
alias gmnf 'git merge --no-ff'
alias gmt 'git mergetool'
alias gdc 'git diff --cached'
alias gau 'git add -u'
alias grph 'git rev-parse HEAD'
alias gsu 'git submodule update --init'
alias gsp 'git stash && git pull --rebase && git stash pop'
alias gfi 'git checkout develop && git flow init --defaults && git checkout -'
alias gcan 'gc --amend --no-edit'
alias gb "git reflog show --grep-reflog='checkout: moving' --format='%gs' |
  sed -n 's/.*to //p' |
  awk '!seen[\$0]++'"

alias xcs 'sed -z '"'"'$ s/\n$//'"'"' | xclip -selection clipboard'

alias h heroku
alias sr 'ssh ubuntu@pi'
alias srr 'ssh -p 2205 ubuntu@home.fstab.net'
alias sc 'ssh chia@chia'
alias scr 'ssh -p 2203 chia@home.fstab.net'
alias mr 'mosh ubuntu@pi'
alias mrr 'mosh --ssh="ssh -p 2204" --server=mosh-server-upnp ubuntu@home.fstab.net'
alias mc 'mosh chia@chia'
alias mcr 'mosh --ssh="ssh -p 2203" --server=mosh-server-upnp chia@home.fstab.net'
alias mw 'mosh altendky@w550s'
#alias mwr 'mosh --ssh="ssh -p 2203" --server=mosh-server-upnp chia@home.fstab.net'
alias ms 'mosh altendky@server'
alias msr 'mosh --ssh="ssh -p 2204" --server=mosh-server-upnp altendky@home.fstab.net'
alias brewon 'eval (/home/linuxbrew/.linuxbrew/bin/brew shellenv)'

alias debuf 'stdbuf -i0 -o0 -e0'
alias debuf-line 'stdbuf -i0 -oL -eL'

alias byebyeew 'bash -c \'sudo rm -rf .simulator/ && git clean -ffdx && ../copy-env.sh && docker compose up simulator; sudo chown -R $(id -u).$(id -g) .simulator && $(which npm) i && npm run build\''

function keybase-hide
    echo '{"method": "list"}' | keybase chat api | jq --raw-output '.result.conversations[] | select(.channel.members_type == "impteamnative" and .unread == false) | .channel.name' | xargs --no-run-if-empty --max-lines=1 --max-procs=10 keybase chat hide
    echo '{"method": "list"}' | keybase chat api | jq --raw-output '.result.conversations[] | select(.channel.members_type == "team" and .unread == false) | (.channel.topic_name + "\n" + .channel.name)' | xargs --no-run-if-empty --max-lines=2 --max-procs=10 keybase chat hide --channel
end

function gaus
    gau $argv
    gs
end

set --export _INTELLIJ_FORCE_PREPEND_PATH ''
set --export PIPX_BIN_DIR ~/.local/bin/pipx
set --export PYTHONDONTWRITEBYTECODE 1
set --export PYTHON_CONFIGURE_OPTS --enable-shared
set --export PIP_REQUIRE_VIRTUALENV 1
set --export EDITOR vim
#set --export JDK_HOME /usr/lib/jvm/java-8-openjdk-amd64

# https://github.com/pyenv/pyenv/issues/32#issuecomment-482980350
set --export PYENV_ROOT $HOME/.pyenv
#set -Ux PYENV_ROOT $HOME/.pyenv
#set -U fish_user_paths $PYENV_ROOT/bin $fish_user_paths

set --export N_PREFIX $HOME/.n

#status is-login; and pyenv init --path | source
#pyenv init - | source

#set --export PYENV_ROOT $HOME/.pyenv
#status --is-interactive; and pyenv init - | source
#status --is-interactive; and pyenv virtualenv-init - | source

#ssh-add ~/.ssh/id_rsa.github
#ssh-add ~/.ssh/id_rsa.qt_gerrit
#ssh-add ~/.ssh/w550s
#ssh-add ~/.ssh/id_ed25519.server
#ssh-add ~/.ssh/id_ed25519.pi

# chips
if [ -e ~/.config/chips/build.fish ] ; . ~/.config/chips/build.fish ; end

# Added by Krypton
#set -x GPG_TTY (tty)

# GWT setup
source "/home/altendky/.local/bin/gwt.fish"
set -gx GWT_GIT_DIR "/home/altendky/repos/gw/monorepo"

# bun
set --export BUN_INSTALL "$HOME/.bun"

set -gx CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR 1
set -gx MAX_THINKING_TOKENS 32000
set -gx ENABLE_LSP_TOOLS 1

set -gx OPENCODE_DISABLE_AUTOCOMPACT 1
# set -gx OPENCODE_DISABLE_PRUNE 1

source ~/.secrets.env

set -gx CARGO_INCREMENTAL 1

set -gx CARGO_BUILD_JOBS (math (lscpu -p=CORE | grep -v '^#' | sort -u | wc -l) - 2)

if [ "$ALTENDKY_FISH_CONFIGURED" = "1" ]
    exit 0
end
set --export ALTENDKY_FISH_CONFIGURED "1"

set --export PATH $BUN_INSTALL/bin $PATH
set --export PATH $PYENV_ROOT/shims $PYENV_ROOT/bin $PATH
#set --export PATH /epc/bin ~/.local/bin ~/.local/bin_pipx ~/.local/phabricator/arcanist/bin $PATH
set --export PATH ~/.local/bin ~/.local/bin/pipx $PATH
set --export PATH ~/.cargo/bin $PATH
set --export PATH $N_PREFIX/bin $PATH
#set --export PATH $PYENV_ROOT/bin $PATH
set --export PATH $PATH /home/altendky/.local/bin/pipx

# pnpm
set -gx PNPM_HOME "/home/altendky/.local/share/pnpm"
if not string match -q -- $PNPM_HOME $PATH
  set -gx PATH "$PNPM_HOME" $PATH
end
# pnpm end
