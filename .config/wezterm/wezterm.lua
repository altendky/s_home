local wezterm = require 'wezterm'
local config = wezterm.config_builder()

config.font_size = 10.0
config.initial_cols = 120
config.initial_rows = 42

-- Session resurrection: save/restore windows, tabs, panes, cwd, and scrollback.
-- Plugin is auto-cloned by wezterm on first launch.
local resurrect = wezterm.plugin.require('https://github.com/MLFlexer/resurrect.wezterm')

-- Auto-save the current workspace every 15 minutes (default interval).
resurrect.state_manager.periodic_save()

-- On wezterm startup, restore the most recently saved workspace state,
-- including pane scrollback text.
wezterm.on('gui-startup', function(cmd)
  local mux = wezterm.mux
  local _, _, window = mux.spawn_window(cmd or {})
  local workspace_name = mux.get_active_workspace()
  local ok, state = pcall(resurrect.state_manager.load_state, workspace_name, 'workspace')
  if ok and state then
    resurrect.workspace_state.restore_workspace(state, {
      window = window,
      relative = true,
      restore_text = true,
      on_pane_restore = resurrect.tab_state.default_on_pane_restore,
    })
  end
end)

-- Alt+W: manually save the current workspace state.
config.keys = {
  {
    key = 'w',
    mods = 'ALT',
    action = wezterm.action_callback(function(win, pane)
      resurrect.state_manager.save_state(resurrect.workspace_state.get_workspace_state())
      win:toast_notification('wezterm', 'workspace saved', nil, 3000)
    end),
  },
}

return config
