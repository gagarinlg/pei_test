"""
AT Command State Machine

Table-driven implementation.  Each state's behaviour is declared as an ordered
list of ``Transition`` rows — analogous to the ``EVENT`` / ``GDEVT`` macros in
the problem statement:

    EVENT(event, next_state, handler)
    GDEVT(event, next_state, handler, guard)   # fires only when guard is True

The dispatch engine iterates the rows for the current state, finds the first
row whose event matches *and* whose guard (if any) returns True, invokes the
handler, and moves to ``next_state`` (``NOCHANGE`` / ``None`` = stay).

Adding a new multi-step command protocol requires only adding new states and
transition rows to ``_TRANSITION_TABLE`` — no changes to the dispatch engine.
"""

import logging
from enum import Enum, auto
from typing import Callable, Dict, List, Optional
from typing import NamedTuple


logger = logging.getLogger(__name__)


class ATParserState(Enum):
    """States of the AT command response parser."""
    IDLE = auto()                    # No command in progress
    COMMAND_SENT = auto()            # Command sent, waiting for first line
    WAITING_RESPONSE = auto()        # Collecting response lines
    WAITING_PROMPT = auto()          # Waiting for '>' prompt (multi-step commands)
    COLLECTING_MESSAGE_BODY = auto() # After prompt received; waiting for final response
    COMPLETE = auto()                # Final response received
    TIMEOUT = auto()                 # Timed out
    ERROR = auto()                   # Connection error


class ATEvent(Enum):
    """
    Events that drive the AT command response parser.

    ``BLANK_LINE``       – Empty or whitespace-only line received.
    ``FINAL_RESPONSE``   – Terminal line: OK, ERROR, NO CARRIER, etc.
    ``LINE``             – Any other non-blank line (data or unsolicited;
                           the table uses GDEVT guards to distinguish them).
    ``PROMPT``           – The '>' prompt for multi-step commands.
    ``TIMEOUT``          – A read timed out without a final response.
    ``CONNECTION_ERROR`` – The connection was lost.
    """
    BLANK_LINE = auto()
    FINAL_RESPONSE = auto()
    LINE = auto()
    PROMPT = auto()
    TIMEOUT = auto()
    CONNECTION_ERROR = auto()


# Final response terminators (stripped of whitespace)
FINAL_TERMINATORS = frozenset([
    "OK", "ERROR", "NO CARRIER", "NO DIALTONE", "BUSY", "NO ANSWER",
])

# Prompt strings for multi-step commands
PROMPT_STRINGS = ("> ", ">\r\n", ">")

# Sentinel: no state transition (stay in current state)
NOCHANGE = None


class Transition(NamedTuple):
    """
    One row in a state's event table.

    Analogous to::

        EVENT(event, next_state, handler)
        GDEVT(event, next_state, handler, guard)   # fires only when guard(sm, line) is True

    Fields:
        event:      The ``ATEvent`` that triggers this row.
        next_state: The state to enter after the handler runs.
                    ``None`` (``NOCHANGE``) means stay in the current state.
        handler:    ``Callable(sm: ATCommandStateMachine, line: str) -> None``.
        guard:      Optional ``Callable(sm, line) -> bool``.  When supplied the
                    row only fires if the guard returns ``True``; otherwise the
                    engine tries the next matching row.
    """
    event: ATEvent
    next_state: Optional[ATParserState]  # None (NOCHANGE) = stay in current state
    handler: Callable                    # handler(sm, line)
    guard: Optional[Callable] = None     # guard(sm, line) -> bool; GDEVT when set


class ATCommandStateMachine:
    """
    Table-driven AT command response parser.

    The full transition logic lives in ``_TRANSITION_TABLE`` (defined after
    the class).  The ``_dispatch`` engine iterates the table for the current
    state, finds the first row whose event matches and whose guard (if any)
    passes, calls the handler, and updates the state.

    Usage (simple command)::

        sm = ATCommandStateMachine(unsolicited_patterns, command_response_map)
        sm.start("AT+CGMI")
        while not sm.is_done():
            line = connection.readline(timeout=remaining)
            if line is None:
                sm.timeout()
            else:
                sm.process_line(line)
        success = sm.is_success()
        response = sm.build_response()

    Usage (prompt-based command like CTMGS)::

        sm = ATCommandStateMachine(unsolicited_patterns, command_response_map)
        sm.start("AT+CTMGS=...", expect_prompt=True)
        # Use connection.receive_until_any to wait for '>' prompt, then:
        sm.prompt_received()
        while not sm.is_done():
            line = connection.readline(timeout=remaining)
            if line is None:
                sm.timeout()
            else:
                sm.process_line(line)
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
            unsolicited_patterns: Substrings that identify unsolicited messages.
            command_response_map: Maps AT command → list of expected solicited
                response patterns that should not be treated as unsolicited.
            unsolicited_callback: Invoked immediately for each unsolicited message.
        """
        self._unsolicited_patterns = unsolicited_patterns
        self._command_response_map = command_response_map
        self._unsolicited_callback = unsolicited_callback

        self.state: ATParserState = ATParserState.IDLE
        self._current_command: str = ""
        self._expected_patterns: List[str] = []
        self._response_lines: List[str] = []
        self._unsolicited_messages: List[str] = []
        self.final_response: Optional[str] = None

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
            command:       The AT command string (used for solicited-pattern lookup).
            expect_prompt: When True the machine enters WAITING_PROMPT instead of
                           COMMAND_SENT; call ``prompt_received()`` after '>' arrives.
        """
        self.reset()
        self._current_command = command
        self._expected_patterns = self._command_response_map.get(command, [])
        self.state = (
            ATParserState.WAITING_PROMPT if expect_prompt
            else ATParserState.COMMAND_SENT
        )

    def process_line(self, line: str) -> None:
        """
        Feed a raw line (including ``\\r\\n``) into the state machine.

        The line is stripped; blank lines raise ``BLANK_LINE``, final
        terminators raise ``FINAL_RESPONSE``, and everything else raises
        ``LINE`` (the table uses GDEVT guards to route ``LINE`` events to the
        appropriate unsolicited or data handler).
        """
        stripped = line.strip()
        event = ATEvent.BLANK_LINE if not stripped else self._classify_line(stripped)
        self._dispatch(event, stripped)

    def process_prompt(self, data: str) -> bool:
        """
        Check *data* for the '>' prompt and fire the PROMPT event if found.

        Returns:
            True if the prompt was found and the PROMPT event was dispatched.
        """
        if self.state != ATParserState.WAITING_PROMPT:
            return False
        for ps in PROMPT_STRINGS:
            if ps in data:
                self._dispatch(ATEvent.PROMPT, "")
                return True
        return False

    def prompt_received(self) -> None:
        """Directly signal that the '>' prompt has been received."""
        self._dispatch(ATEvent.PROMPT, "")

    def timeout(self) -> None:
        """Signal that a read timed out without receiving a final response."""
        self._dispatch(ATEvent.TIMEOUT, "")

    def connection_error(self) -> None:
        """Signal that the connection was lost."""
        self._dispatch(ATEvent.CONNECTION_ERROR, "")

    # ------------------------------------------------------------------
    # State query helpers
    # ------------------------------------------------------------------

    def is_done(self) -> bool:
        """True when no further input is needed (COMPLETE, TIMEOUT, or ERROR)."""
        return self.state in (
            ATParserState.COMPLETE,
            ATParserState.TIMEOUT,
            ATParserState.ERROR,
        )

    def waiting_for_prompt(self) -> bool:
        """True while waiting for the '>' prompt."""
        return self.state == ATParserState.WAITING_PROMPT

    def is_success(self) -> bool:
        """True iff the machine completed with an OK final response."""
        return self.state == ATParserState.COMPLETE and self.final_response == "OK"

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def build_response(self) -> str:
        """
        Assemble the full response string from accumulated data lines.

        The final response terminator is appended when present.
        Returns an empty string (or lines joined without terminator) on
        timeout/error.
        """
        if self.final_response is None:
            return "\r\n".join(self._response_lines)
        return "\r\n".join(self._response_lines + [self.final_response]) + "\r\n"

    def get_unsolicited_messages(self) -> List[str]:
        """Return a snapshot of captured unsolicited messages."""
        return list(self._unsolicited_messages)

    def take_unsolicited_messages(self) -> List[str]:
        """Return and clear the captured unsolicited messages."""
        msgs = list(self._unsolicited_messages)
        self._unsolicited_messages.clear()
        return msgs

    # ------------------------------------------------------------------
    # Dispatch engine
    # ------------------------------------------------------------------

    def _classify_line(self, stripped: str) -> ATEvent:
        """Map a non-empty stripped line to FINAL_RESPONSE or LINE."""
        if stripped in FINAL_TERMINATORS:
            return ATEvent.FINAL_RESPONSE
        return ATEvent.LINE

    def _dispatch(self, event: ATEvent, line: str) -> None:
        """
        Core dispatch engine.

        Iterates the transition table for the current state.  For each row:

        - Rows whose event does not match are skipped.
        - For matching rows *with* a guard, the row is skipped if
          ``guard(self, line)`` returns ``False``.
        - The first row that passes calls its handler and applies the state
          transition, then returns.

        Unknown events (no matching row) are silently ignored.
        """
        for trans in self._TRANSITION_TABLE.get(self.state, ()):
            if trans.event != event:
                continue
            if trans.guard is not None and not trans.guard(self, line):
                continue
            trans.handler(self, line)
            if trans.next_state is not None:
                self.state = trans.next_state
            return

    # ------------------------------------------------------------------
    # Action handlers (called via _dispatch)
    # ------------------------------------------------------------------

    def _nop(self, line: str) -> None:
        """No-operation action."""
        pass

    def _on_final_response(self, line: str) -> None:
        """Record the final response terminator."""
        self.final_response = line

    def _on_data_line(self, line: str) -> None:
        """Accumulate a solicited response data line."""
        self._response_lines.append(line)
        logger.debug(f"Keeping expected response: {line}")

    def _on_unsolicited(self, line: str) -> None:
        """Store an unsolicited message and invoke the callback."""
        self._unsolicited_messages.append(line)
        logger.debug(f"Filtered unsolicited message: {line}")
        if self._unsolicited_callback:
            try:
                self._unsolicited_callback(line)
            except Exception as e:
                logger.error(f"Error in unsolicited message callback: {e}")

    # ------------------------------------------------------------------
    # Guard predicates (used in GDEVT-style Transition entries)
    # ------------------------------------------------------------------

    def _is_unsolicited(self, line: str) -> bool:
        """
        Guard: True when *line* matches a known unsolicited pattern AND is
        not in the expected solicited-response patterns for the current command.
        """
        for pattern in self._unsolicited_patterns:
            if pattern in line:
                return not any(exp in line for exp in self._expected_patterns)
        return False


# ---------------------------------------------------------------------------
# Transition table
#
# Defined after the class so that ATCommandStateMachine method references are
# valid.  Each entry mirrors either EVENT or GDEVT from the problem statement:
#
#   EVENT(event, next_state, handler)
#   GDEVT(event, next_state, handler, guard)   ← fires only when guard is True
#
# NOCHANGE (None) as next_state means the state does not change.
# Terminal states (COMPLETE, TIMEOUT, ERROR) have empty tables; all events
# are silently ignored once the machine has finished.
# ---------------------------------------------------------------------------

ATCommandStateMachine._TRANSITION_TABLE: Dict[ATParserState, List[Transition]] = {

    # No transitions; all events ignored while idle.
    ATParserState.IDLE: [],

    # ── COMMAND_SENT ──────────────────────────────────────────────────────
    # The first non-blank line triggers the move to WAITING_RESPONSE.
    ATParserState.COMMAND_SENT: [
        Transition(ATEvent.BLANK_LINE,       NOCHANGE,                        ATCommandStateMachine._nop),
        Transition(ATEvent.FINAL_RESPONSE,   ATParserState.COMPLETE,          ATCommandStateMachine._on_final_response),
        # GDEVT: first line is unsolicited → route and move to WAITING_RESPONSE
        Transition(ATEvent.LINE, ATParserState.WAITING_RESPONSE, ATCommandStateMachine._on_unsolicited, ATCommandStateMachine._is_unsolicited),
        # EVENT: first line is data → accumulate and move to WAITING_RESPONSE
        Transition(ATEvent.LINE, ATParserState.WAITING_RESPONSE, ATCommandStateMachine._on_data_line),
        Transition(ATEvent.TIMEOUT,          ATParserState.TIMEOUT,           ATCommandStateMachine._nop),
        Transition(ATEvent.CONNECTION_ERROR, ATParserState.ERROR,             ATCommandStateMachine._nop),
    ],

    # ── WAITING_RESPONSE ──────────────────────────────────────────────────
    ATParserState.WAITING_RESPONSE: [
        Transition(ATEvent.BLANK_LINE,       NOCHANGE,               ATCommandStateMachine._nop),
        Transition(ATEvent.FINAL_RESPONSE,   ATParserState.COMPLETE, ATCommandStateMachine._on_final_response),
        # GDEVT: unsolicited line → store and invoke callback
        Transition(ATEvent.LINE, NOCHANGE, ATCommandStateMachine._on_unsolicited, ATCommandStateMachine._is_unsolicited),
        # EVENT: data line → accumulate as response
        Transition(ATEvent.LINE, NOCHANGE, ATCommandStateMachine._on_data_line),
        Transition(ATEvent.TIMEOUT,          ATParserState.TIMEOUT,  ATCommandStateMachine._nop),
        Transition(ATEvent.CONNECTION_ERROR, ATParserState.ERROR,    ATCommandStateMachine._nop),
    ],

    # ── WAITING_PROMPT ────────────────────────────────────────────────────
    ATParserState.WAITING_PROMPT: [
        Transition(ATEvent.BLANK_LINE,       NOCHANGE,                              ATCommandStateMachine._nop),
        Transition(ATEvent.FINAL_RESPONSE,   NOCHANGE,                              ATCommandStateMachine._nop),
        # GDEVT: unsolicited line during prompt wait → store and invoke callback
        Transition(ATEvent.LINE, NOCHANGE, ATCommandStateMachine._on_unsolicited, ATCommandStateMachine._is_unsolicited),
        # EVENT: other lines while waiting for prompt → ignore
        Transition(ATEvent.LINE,             NOCHANGE,                              ATCommandStateMachine._nop),
        Transition(ATEvent.PROMPT,           ATParserState.COLLECTING_MESSAGE_BODY, ATCommandStateMachine._nop),
        Transition(ATEvent.TIMEOUT,          ATParserState.TIMEOUT,                 ATCommandStateMachine._nop),
        Transition(ATEvent.CONNECTION_ERROR, ATParserState.ERROR,                   ATCommandStateMachine._nop),
    ],

    # ── COLLECTING_MESSAGE_BODY ───────────────────────────────────────────
    ATParserState.COLLECTING_MESSAGE_BODY: [
        Transition(ATEvent.BLANK_LINE,       NOCHANGE,               ATCommandStateMachine._nop),
        Transition(ATEvent.FINAL_RESPONSE,   ATParserState.COMPLETE, ATCommandStateMachine._on_final_response),
        # GDEVT: unsolicited line while collecting message body
        Transition(ATEvent.LINE, NOCHANGE, ATCommandStateMachine._on_unsolicited, ATCommandStateMachine._is_unsolicited),
        # EVENT: data line → accumulate
        Transition(ATEvent.LINE, NOCHANGE, ATCommandStateMachine._on_data_line),
        Transition(ATEvent.TIMEOUT,          ATParserState.TIMEOUT,  ATCommandStateMachine._nop),
        Transition(ATEvent.CONNECTION_ERROR, ATParserState.ERROR,    ATCommandStateMachine._nop),
    ],

    # Terminal states: no transitions; all events silently ignored.
    ATParserState.COMPLETE: [],
    ATParserState.TIMEOUT:  [],
    ATParserState.ERROR:    [],
}

