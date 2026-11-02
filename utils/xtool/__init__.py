# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

"""The implementation of ./x, forge's developer entry point. x.py at the repository root runs it.

Everything here runs on the Python standard library, except download.py (setup and pin) and
lit_runner.py, which run inside .forge/venv.
"""
