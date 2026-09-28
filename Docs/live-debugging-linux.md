# Live-debugging MCC on Linux (Proton + x64dbg)

`./mcc-dbg.sh` starts unmodded MCC with `-no-eac` plus x64dbg in the same Proton prefix.
Attach from the MCC main menu, then connect the MCP server with
`connect_remote 127.0.0.1 27066 27067`. Pitfalls hit while mapping the hooks in `hook-map-h2-h3-h4-reach.md`:

- Proton's `runinprefix` skips its DXVK setup, so the script sets the DXVK/vkd3d
  `WINEDLLOVERRIDES` for MCC only. Without them MCC falls back to wined3d, which is very slow
  and crashes H4. With the overrides also applied to x64dbg, attaching crashed both processes.
- `SetThreadName` exception `0x406D1388` must be swallowed by the debugger
  (x64dbg.ini `IgnoreRange`), otherwise MCC dies.
- Use logging-only breakpoints (`SetBreakpointLog` + `SetBreakpointCondition x, 0`).
- A `findallmem` over the whole address space takes about 20 s and times out the MCP connection;
  scope it to a module (`findallmem mod:0, "hex", size`) instead.
