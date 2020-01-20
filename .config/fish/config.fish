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

alias gl 'git log'
alias gs 'git status'
alias gc 'git commit'
alias gd 'git diff'
alias gdt 'git difftool'
alias gdtd 'git difftool --dir-diff'
alias gdtdc 'git difftool --dir-diff --cached'
alias gmnf 'git merge --no-ff'
alias gmt 'git mergetool'
alias gdc 'git diff --cached'
alias gau 'git add -u'
alias grph 'git rev-parse HEAD'

alias h heroku

function gaus
    gau $argv
    gs
end

set --export PIPX_BIN_DIR ~/.local/bin/pipx
set --export PATH /epc/bin ~/.local/bin ~/.local/bin_pipx ~/.local/phabricator/arcanist/bin $PATH
set --export PYTHONDONTWRITEBYTECODE 1
set --export EDITOR vim
set --export JDK_HOME /usr/lib/jvm/java-8-openjdk-amd64

# https://github.com/pyenv/pyenv/issues/32#issuecomment-482980350
set --export PYENV_ROOT $HOME/.pyenv
set --export PATH $PYENV_ROOT/bin $PATH
status --is-interactive; and . (pyenv init -|psub)
status --is-interactive; and . (pyenv virtualenv-init -|psub)

# chips
if [ -e ~/.config/chips/build.fish ] ; . ~/.config/chips/build.fish ; end
