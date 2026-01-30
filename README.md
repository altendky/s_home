# s_home

Dotfiles managed with [GNU Stow](https://www.gnu.org/software/stow/).

## Requirements

- `stow` package (e.g., `pacman -S stow`, `apt install stow`)

## Installation

```bash
./install.sh
```

## Troubleshooting

### "File already exists" errors

If stow reports that a file already exists, remove the original file and let stow manage it:

```bash
rm ~/.config/fish/config.fish  # example
./install.sh
```

Stow creates symlinks from your home directory pointing back to this repo. If real files already exist at those locations, stow won't overwrite them.
