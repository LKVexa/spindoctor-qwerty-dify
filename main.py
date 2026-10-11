# SpinDoctor Qwerty for Dify 1.1.0 - plugin entry point (Dify Python runner, meta.runner.entrypoint=main)
# Copyright (C) 2026 RUSSELL PHILIP SMITHSON <russellsmithson77@outlook.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. It is distributed WITHOUT ANY WARRANTY; see the LICENSE file for details.
from dify_plugin import DifyPluginEnv, Plugin

# Long simulations (e.g. q.folder with 128 files) can take minutes.
plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=600))

if __name__ == "__main__":
    plugin.run()
