function ct
    cd /epc/t/$argv
end

function cg
    cd /epc/g/$argv
end

function confish
    eval $EDITOR ~/.config/fish/config.fish
end
alias fource 'source ~/.config/fish/config.fish'

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

set PATH ~/.local/bin $PATH
