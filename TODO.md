# TODO

## Halo 2: next mission still loads after a win

After winning a Halo 2 mission, the DLL returns to the menu, but Halo 2 first loads
the next mission (e.g. The Heretic → The Armory). Halo 3, Halo 4 and Reach return
to the menu cleanly.

Not a logic leak: the launcher ignores chapter, skull and completion reports from
missions the player doesn't have access to, so a briefly loaded locked mission gives
no checks. It's cosmetic and slows things down.

What's known:
- MCC makes no shell-command or level-load calls into the Halo 2 engine between the
  win and the next map. Halo 2 advances to the next mission inside `halo2.dll`.
- Clearing the "won" byte (`+0x1818` in the game globals) doesn't stop it.
- The next map's path (`scenarios\solo\01a_…`) is written into the pending game
  options before the DLL's quit arrives.
- The main loop launches a pending map from the request flag at `halo2+0xE70D8A`
  through `halo2+0x6B0260`. The DLL now hooks that launch and swallows one request
  in the post-win window. On the last test it fired (`next mission launch after the
  win blocked` in the DLL log), yet The Armory still loaded, so the load goes through
  another path as well.

Next steps:
- In a debug session, break on the next-map path write after the win and follow the
  code from there to whatever actually starts the load; hook or skip that instead.
- Check whether the quit is better sent from inside the win hook instead of on the
  next DLL tick (it currently races the load).

See `Docs/hook-map-h2-h3-h4-reach.md` for the Halo 2 addresses.
