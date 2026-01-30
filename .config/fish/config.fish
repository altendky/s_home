function ct
    cd /epc/t/$argv
end

function cr
    cd /epc/repos/$argv
end

function cdr
    cd ~/repos/$argv
end

function cg
    cd /epc/g/$argv
end

function confish
    eval $EDITOR ~/.config/fish/config.fish
end
alias fource 'source ~/.config/fish/config.fish'

function dmesgrun
    sudo bash -c "echo about to run: $argv > /dev/kmsg"
    eval $argv
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

alias h heroku

function gaus
    gau $argv
    gs
end

set --export PIPX_BIN_DIR ~/.local/bin/pipx
set --export PATH /epc/bin ~/.local/bin ~/.local/bin_pipx ~/.local/phabricator/arcanist/bin $PATH
set --export PYTHONDONTWRITEBYTECODE 1
set --export PYTHON_CONFIGURE_OPTS --enable-shared
set --export EDITOR vim
set --export JDK_HOME /usr/lib/jvm/java-8-openjdk-amd64

# https://github.com/pyenv/pyenv/issues/32#issuecomment-482980350
set --export PYENV_ROOT $HOME/.pyenv
set --export PATH $PYENV_ROOT/bin $PATH
status --is-interactive; and pyenv init - | source
status --is-interactive; and pyenv virtualenv-init - | source

ssh-add ~/.ssh/id_rsa.github
ssh-add ~/.ssh/id_ed25519.github
ssh-add ~/.ssh/id_rsa.qt_gerrit

# chips
if [ -e ~/.config/chips/build.fish ] ; . ~/.config/chips/build.fish ; end
