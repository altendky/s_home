#!/usr/bin/env bash

# Stow all packages to $HOME
for dir in */; do
    # Skip non-stow directories
    [[ "$dir" == ".git/" ]] && continue

    pkg="${dir%/}"
    printf "Stowing %s\n" "$pkg"
    stow --target="$HOME" -R "$pkg"
done
