"""
AT Command State Machine

Implements an explicit state machine for parsing AT command responses.
This encapsulates the parsing logic previously embedded in TetraPEI._send_command()
and TetraPEI.send_message(), making the flow human-readable and maintainable.
"""

import logging
from enum import Enum, auto
from typing import List, Optional, Callable


logger = logging.getLogger(__name__)


class ATParserState(Enum):
    """States of the AT command response parser."""
    IDLE = auto()                   # No command in progress
    COMMAND_SENT = auto()           # Command sent, waiting for first line
    WAITING_RESPONSE = auto()       # Collecting response lines, looking for terminator
    WAITING_PROMPT = auto()         # Waiting for '>' prompt (multi-step commands)
    COLLECTING_MESSAGE_BODY = auto()  # After prompt, sending body, waiting for final response
    COMPLETE = auto()               # Final response received
    TIMEOUT = auto()                # Timed out waiting for response
    ERROR = auto()                  # Connection error or send failure


# Final response terminators (stripped of whitespace)
FINAL_TERMINATORS = frozenset([
    "OK",
    "ERROR",
    "NO CARRIER",
    "NO DIALTONE",
    "BUSY",
    "NO ANSWER",
])

# The prompt sequence used in multi-step commands (e.g. CTMGS)
PROMPT_STRINGS = ("> ", ">\r\n", ">")


class ATCommandStateMachine:
    """
    Explicit state machine for AT command response parsing.

    Drives transitions via ``process_line(line)`` or ``timeout()``/
    ``connection_error()`` events.  Unsolicited messages are detected,
    stored, and routed to an optional callback in every applicable state.

    Usage (simple command)::

        sm = ATCommandStateMachine(unsolicited_patterns, command_response_map)
        sm.start("AT+CGMI")
        while not sm.is_done():
            line = connection.readline(timeout=remaining)
            if line is None:
                sm.timeout()
            else:
                sm.process_line(line)
        success = sm.state == ATParserState.COMPLETE and sm.final_response == "OK"
        response = sm.build_response()

    Usage (prompt-based command like CTMGS)::

        sm = ATCommandStateMachine(unsolicited_patterns, command_response_map)
        sm.start("AT+CTMGS=...", expect_prompt=True)
        while not sm.is_done() and not sm.waiting_for_prompt():
            line = connection.readline(timeout=remaining)
            if line is None:
                sm.timeout()
            else:
                sm.process_line(line)
        # Now send message body, then continue reading final response
        sm.prompt_received()
        while not sm.is_done():
            line = connection.readline(timeout=remaining)
            ...
    """

    def __init__(
        self,
        unsolicited_patterns: List[str],
        command_response_map: dict,
        unsolicited_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialise the state machine.

        Args:
            unsolicited_patterns: List of string prefixes/substrings that
                identify unsolicited messages (e.g. ``['RING', '+CLIP:']``).
            command_response_map: Mapping from AT command string to list of
                expected response patterns that should *not* be treated as
                unsolicited (e.g. ``{'AT+CREG?': ['+CREG:']}'``).
            unsolicited_callback: Optional callable invoked immediately when
                an unsolicited message is detected.
        """
        self._unsolicited_patterns = unsolicited_patterns
        self._command_response_map = command_response_map
        self._unsolicited_callback = unsolicited_callback

        self.state: ATParserState = ATParserState.IDLE
        self._current_command: str = ""
        self._expected_patterns: List[str] = []
        self._response_lines: List[str] = []
        self._unsolicited_messages: List[str] = []
        self.final_response: Optional[str] = None  # e.g. "OK", "ERROR"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Return the state machine to IDLE, clearing all accumulated data."""
        self.state = ATParserState.IDLE
        self._current_command = ""
        self._expected_patterns = []
        self._response_lines = []
        self._unsolicited_messages = []
        self.final_response = None

    def start(self, command: str, expect_prompt: bool = False) -> None:
        """
        Begin parsing the response to *command*.

        Args:
            command: The AT command that was just sent (used to look up
                expected solicited patterns).
            expect_prompt: If True the machine enters WAITING_PROMPT and
                will not advance to WAITING_RESPONSE until
                ``prompt_received()`` is called.
        """
        self.reset()
        self._current_command = command
        self._expected_patterns = self._command_response_map.get(command, [])
        if expect_prompt:
            self.state = ATParserState.WAITING_PROMPT
        else:
            self.state = ATParserState.COMMAND_SENT

    def process_line(self, line: str) -> None:
        """
        Feed a raw line (including ``\\r\\n``) into the state machine.

        The machine advances its state according to the content of the line:
        - blank lines are skipped
        - final response terminators trigger COMPLETE
        - unsolicited messages are routed to the callback / buffer
        - everything else is accumulated as response data

        Args:
            line: A line as returned by ``RadioConnection.readline()``.
        """
        if self.state in (ATParserState.COMPLETE, ATParserState.TIMEOUT, ATParserState.ERROR):
            return

        stripped = line.strip()
        if not stripped:
            return

        # Transition COMMAND_SENT → WAITING_RESPONSE on first non-blank line
        if self.state == ATParserState.COMMAND_SENT:
            self.state = ATParserState.WAITING_RESPONSE

        if self.state == ATParserState.WAITING_RESPONSE:
            self._handle_waiting_response(stripped)
        elif self.state == ATParserState.COLLECTING_MESSAGE_BODY:
            self._handle_collecting_message_body(stripped)
        # WAITING_PROMPT: lines before the prompt are treated like normal
        # response lines (unsolicited filtering applies, but no terminator check)
        elif self.state == ATParserState.WAITING_PROMPT:
            self._handle_line_if_unsolicited(stripped)

    def process_prompt(self, data: str) -> bool:
        """
        Check whether *data* contains the '>' prompt.

        If a prompt is found and the machine is in WAITING_PROMPT the state
        transitions to COLLECTING_MESSAGE_BODY.

        Args:
            data: Raw data received (may contain the prompt string).

        Returns:
            True if prompt was found and state was updated.
        """
        if self.state != ATParserState.WAITING_PROMPT:
            return False
        for ps in PROMPT_STRINGS:
            if ps in data:
                self.prompt_received()
                return True
        return False

    def prompt_received(self) -> None:
        """
        Signal that the '>' prompt has been received.

        Transitions WAITING_PROMPT → COLLECTING_MESSAGE_BODY.
        """
        if self.state == ATParserState.WAITING_PROMPT:
            self.state = ATParserState.COLLECTING_MESSAGE_BODY

    def timeout(self) -> None:
        """Signal that a read timed out without receiving a final response."""
        if self.state not in (ATParserState.COMPLETE, ATParserState.ERROR):
            self.state = ATParserState.TIMEOUT

    def connection_error(self) -> None:
        """Signal that the connection was lost."""
        self.state = ATParserState.ERROR

    # ------------------------------------------------------------------
    # State query helpers
    # ------------------------------------------------------------------

    def is_done(self) -> bool:
        """Return True when no further lines need to be read."""
        return self.state in (
            ATParserState.COMPLETE,
            ATParserState.TIMEOUT,
            ATParserState.ERROR,
        )

    def waiting_for_prompt(self) -> bool:
        """Return True when the machine is waiting for the '>' prompt."""
        return self.state == ATParserState.WAITING_PROMPT

    def is_success(self) -> bool:
        """Return True iff the final response was ``OK``."""
        return self.state == ATParserState.COMPLETE and self.final_response == "OK"

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def build_response(self) -> str:
        """
        Build the full response string from accumulated lines.

        The final response terminator (e.g. ``OK``) is included.

        Returns:
            ``''`` if no final response was received (timeout/error), otherwise
            a ``\\r\\n``-joined string of data lines followed by the terminator,
            ending with ``\\r\\n``.
        """
        if self.final_response is None:
            return "\r\n".join(self._response_lines)
        all_lines = self._response_lines + [self.final_response]
        return "\r\n".join(all_lines) + "\r\n"

    def get_unsolicited_messages(self) -> List[str]:
        """Return a copy of unsolicited messages collected so far."""
        return list(self._unsolicited_messages)

    def take_unsolicited_messages(self) -> List[str]:
        """Return and clear the unsolicited messages buffer."""
        msgs = list(self._unsolicited_messages)
        self._unsolicited_messages.clear()
        return msgs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_waiting_response(self, stripped: str) -> None:
        """Process a stripped line while in WAITING_RESPONSE state."""
        if stripped in FINAL_TERMINATORS:
            self.final_response = stripped
            self.state = ATParserState.COMPLETE
            return
        is_unsolicited = self._handle_line_if_unsolicited(stripped)
        if not is_unsolicited:
            self._response_lines.append(stripped)

    def _handle_collecting_message_body(self, stripped: str) -> None:
        """Process a stripped line while in COLLECTING_MESSAGE_BODY state."""
        if stripped in FINAL_TERMINATORS:
            self.final_response = stripped
            self.state = ATParserState.COMPLETE
            return
        is_unsolicited = self._handle_line_if_unsolicited(stripped)
        if not is_unsolicited:
            self._response_lines.append(stripped)

    def _handle_line_if_unsolicited(self, line: str) -> bool:
        """
        Determine whether *line* is an unsolicited message and handle it.

        A line is unsolicited if it matches a known unsolicited pattern AND
        does not match the expected solicited patterns for the current command.

        When a line is identified as unsolicited it is appended to the internal
        buffer **and** the ``unsolicited_callback`` (if set) is invoked
        immediately before this method returns.

        Returns:
            True if the line was identified as unsolicited and handled.
        """
        for pattern in self._unsolicited_patterns:
            if pattern in line:
                is_expected = any(exp in line for exp in self._expected_patterns)
                if not is_expected:
                    self._unsolicited_messages.append(line)
                    logger.debug(f"Filtered unsolicited message: {line}")
                    if self._unsolicited_callback:
                        try:
                            self._unsolicited_callback(line)
                        except Exception as e:
                            logger.error(f"Error in unsolicited message callback: {e}")
                    return True
                else:
                    logger.debug(f"Keeping expected response: {line}")
                break
        return False
