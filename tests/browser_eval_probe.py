#!/usr/bin/env python3
"""Evaluate one JavaScript function body in the newest browser session of a dev build.

    IT2_SUITE=claude-iterm2 IT2_APP_PATH=... PYTHONPATH=api/library/python/iterm2 \
    python3 tests/browser_eval_probe.py 'return location.href'
"""
import json
import os
import sys

import iterm2
import iterm2.auth

JS = sys.argv[1] if len(sys.argv) > 1 else "return document.title"


async def main(connection):
    app = await iterm2.async_get_app(connection)
    sessions = [s for w in app.terminal_windows for t in w.tabs for s in t.sessions]
    for s in reversed(sessions):
        try:
            print(json.dumps(await s.async_eval_javascript(JS)))
            return
        except Exception as e:
            last = e
    print("no browser session answered:", last)


_ck = iterm2.auth.request_cookie_and_key(False, "browser_eval_probe", iterm2.auth.CommandLineApplescriptRunner).split(" ")
os.environ["ITERM2_COOKIE"], os.environ["ITERM2_KEY"] = _ck[0], _ck[1]
iterm2.run_until_complete(main)
