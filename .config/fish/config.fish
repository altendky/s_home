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
    sudo rmmod psmouse
    sudo modprobe psmouse
    sleep 5
    sudo udevadm trigger -s input
end

function fix-kde
    killall plasmashell kwin
    kstart5 kwin
    sleep 5
    kstart5 plasmashell
end

function cr
    cd /epc/repos/$argv
end

function cdr
    cd ~/repos/$argv
end

#function cg
#    cd /epc/g/$argv
#end

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
end


# https://github.com/xtendo-org/chips#gnulinux-x64
alias get_chips 'curl -Lo ~/.local/bin/chips --create-dirs
    https://github.com/xtendo-org/chips/releases/download/1.1.2/chips_gnulinux
    ; and chmod +x ~/.local/bin/chips'

alias gda 'git-dag --all'

alias gl 'git log --graph'
alias gl1 "git log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold green)(%ar)%C(reset) %C(white)%s%C(reset) %C(dim white)- %an%C(reset)%C(auto)%d%C(reset)'"
alias gl2 "git log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold cyan)%aD%C(reset) %C(bold green)(%ar)%C(reset)%C(auto)%d%C(reset)%n''          %C(white)%s%C(reset) %C(dim white)- %an%C(reset)'"
alias gl3 "git log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold cyan)%aD%C(reset) %C(bold green)(%ar)%C(reset) %C(bold cyan)(committed: %cD)%C(reset) %C(auto)%d%C(reset)%n''          %C(white)%s%C(reset)%n''          %C(dim white)- %an <%ae> %C(reset) %C(dim white)(committer: %cn <%ce>)%C(reset)'"
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

alias xcs 'xclip -selection clipboard'

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

if [ "$ALTENDKY_FISH_CONFIGURED" = "1" ]
    exit 0
end
set --export ALTENDKY_FISH_CONFIGURED "1"

set --export PATH $PYENV_ROOT/shims $PYENV_ROOT/bin $PATH
#set --export PATH /epc/bin ~/.local/bin ~/.local/bin_pipx ~/.local/phabricator/arcanist/bin $PATH
set --export PATH ~/.local/bin ~/.local/bin/pipx $PATH
set --export PATH ~/.cargo/bin $PATH
set --export PATH $N_PREFIX/bin $PATH
#set --export PATH $PYENV_ROOT/bin $PATH
set --export PATH $PATH /home/altendky/.local/bin/pipx
