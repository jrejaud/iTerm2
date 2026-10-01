#!/usr/bin/env python3
"""Manual smoke test for iterm2.browser_eval_js (SC-6056).

Run against a dev build launched with `-suite claude-iterm2`:
    IT2_SUITE=claude-iterm2 IT2_APP_PATH=/path/to/iTerm2.app \
    PYTHONPATH=api/library/python/iterm2 python3 tests/browser_eval_smoke.py <url> [--login-github]

Opens a browser window on <url>, waits for it to load, reads document.title and the
signed-in GitHub user through Session.async_eval_javascript, and (with --login-github)
signs in by filling the form in the DOM — no clicks on the screen.
"""
import asyncio
import json
import subprocess
import sys

import iterm2

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.com/"
LOGIN = "--login-github" in sys.argv
OP_ITEM, OP_VAULT = "p5s2ut7io3zvjnlcdhmvxy5lbm", "Shared"


def op(*args):
    return subprocess.run(["op", "item", "get", OP_ITEM, "--vault", OP_VAULT, *args],
                          capture_output=True, text=True, check=True).stdout.strip()


async def wait_ready(session, timeout=30):
    for _ in range(timeout * 2):
        try:
            state = await session.async_eval_javascript("return document.readyState")
            if state == "complete":
                return True
        except Exception as e:  # page not committed yet
            last = e
        await asyncio.sleep(0.5)
    return False


async def page(session):
    return await session.async_eval_javascript(
        "return {title: document.title, url: location.href, "
        "user: document.querySelector('meta[name=user-login]')?.content || null}")


async def set_field(session, selector, value):
    # Native setter + input event, so the page sees a typed value.
    js = ("const e = document.querySelector(" + json.dumps(selector) + ");"
          "if (!e) return false;"
          "Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(e, " + json.dumps(value) + ");"
          "e.dispatchEvent(new Event('input', {bubbles: true}));"
          "return true;")
    return await session.async_eval_javascript(js)


async def main(connection):
    profile = iterm2.LocalWriteOnlyProfile()
    profile._simple_set("Custom Command", "Browser")
    profile._simple_set("Initial URL", URL)
    window = await iterm2.Window.async_create(connection, profile_customizations=profile)
    session = window.current_tab.current_session
    await asyncio.sleep(2)
    print("ready:", await wait_ready(session))
    print("before:", json.dumps(await page(session)))
    if LOGIN and (await page(session))["user"] is None:
        await session.async_load_url("https://github.com/login?return_to=" + URL)
        await wait_ready(session)
        await set_field(session, "#login_field", op("--fields", "username"))
        await set_field(session, "#password", op("--fields", "password", "--reveal"))
        await session.async_eval_javascript("document.querySelector('input[type=submit][name=commit]').click(); return true")
        await asyncio.sleep(4)
        await wait_ready(session)
        if await session.async_eval_javascript("return !!document.querySelector('#app_totp')"):
            await set_field(session, "#app_totp", op("--otp"))
            await session.async_eval_javascript(
                "const f = document.querySelector('#app_totp').form; (f.requestSubmit ? f.requestSubmit() : f.submit()); return true")
            await asyncio.sleep(4)
            await wait_ready(session)
        if not (await page(session))["url"].startswith(URL):
            await session.async_load_url(URL)
            await wait_ready(session)
        print("after:", json.dumps(await page(session)))
    await session.async_set_browser_inspectable(True)
    print("inspectable: ok")


# Get the API cookie from the test instance via osascript (IT2_APP_PATH picks the app).
# The default AppKit runner was refused on 2026-10-01; the command-line runner works.
import os
import iterm2.auth
_ck = iterm2.auth.request_cookie_and_key(False, "browser_eval_smoke", iterm2.auth.CommandLineApplescriptRunner).split(" ")
os.environ["ITERM2_COOKIE"], os.environ["ITERM2_KEY"] = _ck[0], _ck[1]
iterm2.run_until_complete(main)
