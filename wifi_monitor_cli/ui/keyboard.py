"""Non-blocking keyboard input handling for terminal."""

import sys
import select
import termios
import tty
from contextlib import contextmanager


class KeyboardHandler:
    """Handle non-blocking keyboard input in raw terminal mode."""

    def __init__(self):
        self.old_settings = None
        self.fd = sys.stdin.fileno()

    def enable_raw_mode(self):
        """Enable raw terminal mode for single keypress detection."""
        try:
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        except termios.error:
            self.old_settings = None

    def disable_raw_mode(self):
        """Restore normal terminal mode."""
        if self.old_settings is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            except termios.error:
                pass

    def get_key(self, timeout=0.1):
        """
        Get a single keypress without blocking.

        Args:
            timeout: Max time to wait in seconds

        Returns:
            str: The key pressed, or None if no input
        """
        try:
            if select.select([sys.stdin], [], [], timeout)[0]:
                key = sys.stdin.read(1)
                # Handle escape sequences (arrow keys, etc.)
                if key == '\x1b':
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        key += sys.stdin.read(2)
                return key
        except (select.error, IOError):
            pass
        return None

    @contextmanager
    def raw_mode(self):
        """Context manager for raw terminal mode."""
        self.enable_raw_mode()
        try:
            yield self
        finally:
            self.disable_raw_mode()


# Key constants
KEY_UP = '\x1b[A'
KEY_DOWN = '\x1b[B'
KEY_RIGHT = '\x1b[C'
KEY_LEFT = '\x1b[D'
KEY_ENTER = '\r'
KEY_ESCAPE = '\x1b'
KEY_BACKSPACE = '\x7f'
