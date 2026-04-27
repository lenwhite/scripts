This is a collections of one-off scripts written; stored for future reference or usage.

Some are vibe coded, some aren't. Some are reusable, some need some tweaking to work properly.

Scripts are intended to be aliased for usage — naming is intentionally long for ease of browsing.

## Aliasing

**bash** (`~/.bashrc`):
```bash
alias my-script='/path/to/scripts/some_script.sh'
```

**zsh** (`~/.zshrc`):
```zsh
alias my-script='/path/to/scripts/some_script.sh'
```

**fish** (`~/.config/fish/config.fish`):
```fish
alias my-script '/path/to/scripts/some_script.sh'
# or permanently:
alias --save my-script '/path/to/scripts/some_script.sh'
```

Reload the shell after editing (`source ~/.bashrc`, `source ~/.zshrc`, `exec fish`).

### Git subcommand alias

To invoke a script as `git <name>`:

```bash
git config --global alias.<name> '!/path/to/scripts/some_script.sh'
```

The `!` prefix tells git to run the command as a shell command rather than a built-in. After this, `git <name>` will execute the script.
