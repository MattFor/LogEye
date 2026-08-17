import sys

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent

if str(_ROOT) not in sys.path:
	sys.path.insert(0, str(_ROOT))

from logeye import config  # noqa: E402
from logeye import watcher  # noqa: E402
from logeye.formatting import reset_output_formatter  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_logeye_state():
	yield

	watcher._uninstall_global_trace()
	watcher._reset_watch_state()

	sys.settrace(None)

	reset_output_formatter()

	config._pop_display((None, None, None, None))

	config._g_enabled = True
	config._g_deco_only = False
	config._g_log_mode = "full"
	config._g_show_time = True
	config._g_show_file = True
	config._g_show_lineno = True
	config._g_show_message_meta = True
	config._g_path_mode = "file"
	config._g_log_file = None
	config._g_log_file_enabled = True
