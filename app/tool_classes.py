"""What each MCP tool is allowed to be, and the notes that are not notes.

Its own module, importing NOTHING, because two processes need it: `app/agent.py`, which registers the
tools, and `app/agent_loop.py`, which hands a subset of them to the local model. Importing `agent.py`
from the loop would drag the whole MCP server into a process that does not serve MCP, and would make
every test that stubs `mcp` stub more of it.
"""
from __future__ import annotations

# The strings this repository has itself used where a human's words should have been: agent.py's own
# default until v0.63, the Telegram handler's fallback, and the Reticulum bridge's. A note that is one of
# these is the absence of a note wearing a word.
PLACEHOLDER_NOTES = {"acted", "acted (via reticulum)", "acknowledged", "done", "ok", "n/a", "-"}

# ---------------------------------------------------------------- what each tool is allowed to be
#
# NO TOOL IS REMOVED BY THIS TABLE. A remote agent operated by a person — a keeper in Claude Desktop over
# the tailnet — may still need `settings_set`, and taking it away would make the node worse for the case
# the MCP surface was built for. The table exists so that the LOCAL model's loop can be given a subset
# (app/agent_loop.py::LOCAL_TOOLS) and so that `planetai agent` can print what each one is.
#
#   read   asks the node a question. Nothing changes.
#   act    records that a HUMAN did something. The one write a model may make, and only with the
#          human's own words — see act() below.
#   admin  changes the node, runs code on it, or makes it speak to the household unprompted.
#
# `report_now` is admin and the review's list of three did not have it. It writes a report AND SENDS IT:
# a model calling it is the node interrupting a household because a model felt like it. That is an
# admin act however small the diff.
#
# `settings_get` is read: it hands over chat ids and sensor hostnames but changes nothing, and the local
# model is already on the machine those facts describe.
TOOL_CLASS = {
    "status": "read", "health_check": "read", "sensors": "read", "context": "read", "readings": "read",
    "report_latest": "read", "report_bundle": "read", "history": "read", "alerts": "read",
    "settings_get": "read", "packs": "read", "cells": "read", "issues": "read", "series": "read",
    "export_day": "read", "learned": "read",
    "act": "act",
    "settings_set": "admin", "run_pack_script": "admin", "maintenance": "admin", "report_now": "admin",
}
