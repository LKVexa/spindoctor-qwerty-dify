# SpinDoctor Qwerty for Dify 1.1.0 - tool provider
# Copyright (C) 2026 RUSSELL PHILIP SMITHSON <russellsmithson77@outlook.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. It is distributed WITHOUT ANY WARRANTY; see the LICENSE file for details.
from typing import Any

from dify_plugin import ToolProvider


class SpinDoctorQwertyProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        return None  # no credentials: the engine is fully local
