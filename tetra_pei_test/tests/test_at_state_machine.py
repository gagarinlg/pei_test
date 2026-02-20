"""
Comprehensive unit tests for ATCommandStateMachine.

Covers:
- Every state and every valid transition
- Unsolicited message filtering in each state
- Timeout and connection-error events
- Multi-step command flow (prompt → message body → final response)
- Interleaved unsolicited messages during multi-step flows
- Error/edge cases (connection lost mid-parse, unexpected responses, empty lines)
- Correct identification of all final response types
"""

import unittest
from tetra_pei_test.core.at_state_machine import (
    ATCommandStateMachine,
    ATParserState,
    FINAL_TERMINATORS,
    PROMPT_STRINGS,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

UNSOLICITED_PATTERNS = [
    "RING",
    "+CLIP:",
    "+CTXD:",
    "+CMTI:",
    "+CREG:",
    "+CMGS:",
    "+CTICN:",
]

COMMAND_RESPONSE_MAP = {
    "AT+CREG?": ["+CREG:"],
    "AT+CTXD?": ["+CTXD:"],
    "AT+CMGS": ["+CMGS:"],
}


def _make_sm(callback=None):
    return ATCommandStateMachine(
        UNSOLICITED_PATTERNS,
        COMMAND_RESPONSE_MAP,
        callback,
    )


# ---------------------------------------------------------------------------
# 1. Initial state / reset
# ---------------------------------------------------------------------------

class TestInitialState(unittest.TestCase):
    """State machine starts in IDLE and can be reset."""

    def test_initial_state_is_idle(self):
        sm = _make_sm()
        self.assertEqual(sm.state, ATParserState.IDLE)

    def test_initial_final_response_is_none(self):
        sm = _make_sm()
        self.assertIsNone(sm.final_response)

    def test_initial_response_lines_empty(self):
        sm = _make_sm()
        self.assertEqual(sm.build_response(), "")

    def test_initial_unsolicited_empty(self):
        sm = _make_sm()
        self.assertEqual(sm.get_unsolicited_messages(), [])

    def test_reset_returns_to_idle(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("OK\r\n")
        sm.reset()
        self.assertEqual(sm.state, ATParserState.IDLE)
        self.assertIsNone(sm.final_response)
        self.assertEqual(sm.build_response(), "")
        self.assertEqual(sm.get_unsolicited_messages(), [])


# ---------------------------------------------------------------------------
# 2. start() transitions
# ---------------------------------------------------------------------------

class TestStartTransition(unittest.TestCase):

    def test_start_without_prompt_sets_command_sent(self):
        sm = _make_sm()
        sm.start("AT")
        self.assertEqual(sm.state, ATParserState.COMMAND_SENT)

    def test_start_with_prompt_sets_waiting_prompt(self):
        sm = _make_sm()
        sm.start('AT+CTMGS="123",0', expect_prompt=True)
        self.assertEqual(sm.state, ATParserState.WAITING_PROMPT)

    def test_start_clears_previous_data(self):
        sm = _make_sm()
        sm.start("AT+CGMI")
        sm.process_line("SimulatedTetraRadio\r\n")
        sm.process_line("OK\r\n")
        sm.start("AT")
        self.assertEqual(sm.state, ATParserState.COMMAND_SENT)
        self.assertIsNone(sm.final_response)
        self.assertEqual(sm.get_unsolicited_messages(), [])


# ---------------------------------------------------------------------------
# 3. COMMAND_SENT → WAITING_RESPONSE on first non-blank line
# ---------------------------------------------------------------------------

class TestCommandSentTransition(unittest.TestCase):

    def test_blank_line_does_not_advance_state(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("\r\n")
        self.assertEqual(sm.state, ATParserState.COMMAND_SENT)

    def test_whitespace_only_line_does_not_advance(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("   \r\n")
        self.assertEqual(sm.state, ATParserState.COMMAND_SENT)

    def test_first_data_line_moves_to_waiting_response(self):
        sm = _make_sm()
        sm.start("AT+CGMI")
        sm.process_line("SimulatedTetraRadio\r\n")
        self.assertEqual(sm.state, ATParserState.WAITING_RESPONSE)

    def test_terminator_as_first_line_completes(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("OK\r\n")
        self.assertEqual(sm.state, ATParserState.COMPLETE)
        self.assertEqual(sm.final_response, "OK")


# ---------------------------------------------------------------------------
# 4. All final response terminators recognised
# ---------------------------------------------------------------------------

class TestFinalResponseTerminators(unittest.TestCase):

    def _assert_completes(self, terminator_line):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line(terminator_line)
        self.assertEqual(sm.state, ATParserState.COMPLETE,
                         f"Expected COMPLETE for {terminator_line!r}")
        self.assertEqual(sm.final_response, terminator_line.strip())

    def test_ok(self):
        self._assert_completes("OK\r\n")

    def test_error(self):
        self._assert_completes("ERROR\r\n")

    def test_no_carrier(self):
        self._assert_completes("NO CARRIER\r\n")

    def test_no_dialtone(self):
        self._assert_completes("NO DIALTONE\r\n")

    def test_busy(self):
        self._assert_completes("BUSY\r\n")

    def test_no_answer(self):
        self._assert_completes("NO ANSWER\r\n")

    def test_is_success_true_only_for_ok(self):
        for term in ["ERROR\r\n", "NO CARRIER\r\n", "NO DIALTONE\r\n", "BUSY\r\n", "NO ANSWER\r\n"]:
            sm = _make_sm()
            sm.start("AT")
            sm.process_line(term)
            self.assertFalse(sm.is_success(), f"is_success() should be False for {term!r}")

    def test_is_success_true_for_ok(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("OK\r\n")
        self.assertTrue(sm.is_success())


# ---------------------------------------------------------------------------
# 5. build_response() output
# ---------------------------------------------------------------------------

class TestBuildResponse(unittest.TestCase):

    def test_single_line_data_then_ok(self):
        sm = _make_sm()
        sm.start("AT+CGMI")
        sm.process_line("SimulatedTetraRadio\r\n")
        sm.process_line("OK\r\n")
        resp = sm.build_response()
        self.assertEqual(resp, "SimulatedTetraRadio\r\nOK\r\n")

    def test_multi_line_data_then_ok(self):
        sm = _make_sm()
        sm.start("AT+INFO")
        sm.process_line("line1\r\n")
        sm.process_line("line2\r\n")
        sm.process_line("line3\r\n")
        sm.process_line("OK\r\n")
        resp = sm.build_response()
        self.assertEqual(resp, "line1\r\nline2\r\nline3\r\nOK\r\n")

    def test_timeout_response_has_no_terminator(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("partial data\r\n")
        sm.timeout()
        resp = sm.build_response()
        self.assertEqual(resp, "partial data")
        self.assertNotIn("OK", resp)

    def test_empty_response_ok(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("OK\r\n")
        resp = sm.build_response()
        self.assertEqual(resp, "OK\r\n")


# ---------------------------------------------------------------------------
# 6. Timeout event
# ---------------------------------------------------------------------------

class TestTimeout(unittest.TestCase):

    def test_timeout_sets_timeout_state(self):
        sm = _make_sm()
        sm.start("AT")
        sm.timeout()
        self.assertEqual(sm.state, ATParserState.TIMEOUT)

    def test_is_done_after_timeout(self):
        sm = _make_sm()
        sm.start("AT")
        sm.timeout()
        self.assertTrue(sm.is_done())

    def test_process_line_after_timeout_is_noop(self):
        sm = _make_sm()
        sm.start("AT")
        sm.timeout()
        sm.process_line("OK\r\n")  # should not change state
        self.assertEqual(sm.state, ATParserState.TIMEOUT)

    def test_timeout_does_not_overwrite_complete(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("OK\r\n")
        sm.timeout()  # too late
        self.assertEqual(sm.state, ATParserState.COMPLETE)

    def test_is_success_false_after_timeout(self):
        sm = _make_sm()
        sm.start("AT")
        sm.timeout()
        self.assertFalse(sm.is_success())


# ---------------------------------------------------------------------------
# 7. Connection error event
# ---------------------------------------------------------------------------

class TestConnectionError(unittest.TestCase):

    def test_connection_error_sets_error_state(self):
        sm = _make_sm()
        sm.start("AT")
        sm.connection_error()
        self.assertEqual(sm.state, ATParserState.ERROR)

    def test_is_done_after_connection_error(self):
        sm = _make_sm()
        sm.start("AT")
        sm.connection_error()
        self.assertTrue(sm.is_done())

    def test_process_line_after_error_is_noop(self):
        sm = _make_sm()
        sm.start("AT")
        sm.connection_error()
        sm.process_line("OK\r\n")
        self.assertEqual(sm.state, ATParserState.ERROR)


# ---------------------------------------------------------------------------
# 8. Unsolicited message filtering — WAITING_RESPONSE
# ---------------------------------------------------------------------------

class TestUnsolicitedFiltering(unittest.TestCase):

    def test_unsolicited_line_not_in_response(self):
        sm = _make_sm()
        sm.start("AT+CGMI")
        sm.process_line("SimulatedTetraRadio\r\n")
        sm.process_line("RING\r\n")
        sm.process_line("OK\r\n")
        resp = sm.build_response()
        self.assertNotIn("RING", resp)
        self.assertIn("SimulatedTetraRadio", resp)

    def test_unsolicited_stored_in_buffer(self):
        sm = _make_sm()
        sm.start("AT+CGMI")
        sm.process_line("RING\r\n")
        sm.process_line("OK\r\n")
        msgs = sm.get_unsolicited_messages()
        self.assertEqual(len(msgs), 1)
        self.assertIn("RING", msgs[0])

    def test_multiple_unsolicited_stored(self):
        sm = _make_sm()
        sm.start("AT+CGMI")
        sm.process_line("RING\r\n")
        sm.process_line("+CLIP: \"9999\",145\r\n")
        sm.process_line("OK\r\n")
        msgs = sm.get_unsolicited_messages()
        self.assertEqual(len(msgs), 2)

    def test_solicited_creg_not_filtered(self):
        sm = _make_sm()
        sm.start("AT+CREG?")
        sm.process_line("+CREG: 0,1\r\n")
        sm.process_line("OK\r\n")
        resp = sm.build_response()
        self.assertIn("+CREG:", resp)
        self.assertEqual(sm.get_unsolicited_messages(), [])

    def test_unsolicited_creg_during_other_command(self):
        sm = _make_sm()
        sm.start("AT+CGMI")
        sm.process_line("SimulatedTetraRadio\r\n")
        sm.process_line("+CREG: 0,5\r\n")
        sm.process_line("OK\r\n")
        resp = sm.build_response()
        self.assertNotIn("+CREG:", resp)
        msgs = sm.get_unsolicited_messages()
        self.assertTrue(any("+CREG:" in m for m in msgs))

    def test_callback_invoked_for_unsolicited(self):
        captured = []
        sm = _make_sm(callback=lambda m: captured.append(m))
        sm.start("AT+CGMI")
        sm.process_line("RING\r\n")
        sm.process_line("OK\r\n")
        self.assertEqual(len(captured), 1)
        self.assertIn("RING", captured[0])

    def test_callback_not_invoked_for_solicited(self):
        captured = []
        sm = _make_sm(callback=lambda m: captured.append(m))
        sm.start("AT+CREG?")
        sm.process_line("+CREG: 0,1\r\n")
        sm.process_line("OK\r\n")
        self.assertEqual(len(captured), 0)

    def test_callback_exception_does_not_propagate(self):
        def bad_callback(msg):
            raise RuntimeError("boom")

        sm = _make_sm(callback=bad_callback)
        sm.start("AT")
        # Should not raise
        sm.process_line("RING\r\n")
        sm.process_line("OK\r\n")
        self.assertEqual(sm.state, ATParserState.COMPLETE)

    def test_non_matching_line_kept_in_response(self):
        sm = _make_sm()
        sm.start("AT+CGMI")
        sm.process_line("ArbitraryData\r\n")
        sm.process_line("OK\r\n")
        resp = sm.build_response()
        self.assertIn("ArbitraryData", resp)
        self.assertEqual(sm.get_unsolicited_messages(), [])


# ---------------------------------------------------------------------------
# 9. Unsolicited filtering in WAITING_PROMPT state
# ---------------------------------------------------------------------------

class TestUnsolicitedInWaitingPrompt(unittest.TestCase):

    def test_unsolicited_during_prompt_wait_stored(self):
        captured = []
        sm = _make_sm(callback=lambda m: captured.append(m))
        sm.start('AT+CTMGS="123",0', expect_prompt=True)
        self.assertEqual(sm.state, ATParserState.WAITING_PROMPT)
        # An unsolicited message arrives before the '>' prompt
        sm.process_line("RING\r\n")
        self.assertEqual(sm.state, ATParserState.WAITING_PROMPT)
        msgs = sm.get_unsolicited_messages()
        self.assertTrue(any("RING" in m for m in msgs))
        self.assertEqual(len(captured), 1)

    def test_non_unsolicited_line_during_prompt_wait_ignored(self):
        """Non-unsolicited lines during WAITING_PROMPT are not accumulated."""
        sm = _make_sm()
        sm.start('AT+CTMGS="123",0', expect_prompt=True)
        sm.process_line("some junk\r\n")
        self.assertEqual(sm.state, ATParserState.WAITING_PROMPT)
        # junk is neither unsolicited nor final; just ignored
        self.assertEqual(sm.get_unsolicited_messages(), [])


# ---------------------------------------------------------------------------
# 10. prompt_received() / process_prompt()
# ---------------------------------------------------------------------------

class TestPromptReceived(unittest.TestCase):

    def test_prompt_received_advances_state(self):
        sm = _make_sm()
        sm.start('AT+CTMGS="123",0', expect_prompt=True)
        sm.prompt_received()
        self.assertEqual(sm.state, ATParserState.COLLECTING_MESSAGE_BODY)

    def test_prompt_received_noop_when_not_waiting(self):
        sm = _make_sm()
        sm.start("AT")
        sm.prompt_received()  # should not change state
        self.assertEqual(sm.state, ATParserState.COMMAND_SENT)

    def test_process_prompt_detects_greater_than_space(self):
        sm = _make_sm()
        sm.start('AT+CTMGS="123",0', expect_prompt=True)
        found = sm.process_prompt("> ")
        self.assertTrue(found)
        self.assertEqual(sm.state, ATParserState.COLLECTING_MESSAGE_BODY)

    def test_process_prompt_detects_greater_than_crlf(self):
        sm = _make_sm()
        sm.start('AT+CTMGS="123",0', expect_prompt=True)
        found = sm.process_prompt(">\r\n")
        self.assertTrue(found)
        self.assertEqual(sm.state, ATParserState.COLLECTING_MESSAGE_BODY)

    def test_process_prompt_returns_false_when_no_prompt(self):
        sm = _make_sm()
        sm.start('AT+CTMGS="123",0', expect_prompt=True)
        found = sm.process_prompt("some other data")
        self.assertFalse(found)
        self.assertEqual(sm.state, ATParserState.WAITING_PROMPT)

    def test_process_prompt_returns_false_in_wrong_state(self):
        sm = _make_sm()
        sm.start("AT")
        found = sm.process_prompt("> ")
        self.assertFalse(found)


# ---------------------------------------------------------------------------
# 11. Multi-step command flow (COLLECTING_MESSAGE_BODY)
# ---------------------------------------------------------------------------

class TestCollectingMessageBody(unittest.TestCase):

    def _setup_after_prompt(self, callback=None):
        sm = _make_sm(callback)
        sm.start('AT+CTMGS="123",0', expect_prompt=True)
        sm.prompt_received()
        return sm

    def test_ok_after_prompt_completes(self):
        sm = self._setup_after_prompt()
        sm.process_line("OK\r\n")
        self.assertEqual(sm.state, ATParserState.COMPLETE)
        self.assertEqual(sm.final_response, "OK")
        self.assertTrue(sm.is_success())

    def test_error_after_prompt_completes_with_error(self):
        sm = self._setup_after_prompt()
        sm.process_line("ERROR\r\n")
        self.assertEqual(sm.state, ATParserState.COMPLETE)
        self.assertFalse(sm.is_success())

    def test_response_line_before_ok_in_message_body(self):
        sm = self._setup_after_prompt()
        sm.process_line("+CMGS: 1\r\n")  # +CMGS: is also an unsolicited pattern
        sm.process_line("OK\r\n")
        # +CMGS: for AT+CTMGS is NOT in expected map, so it would be unsolicited
        # (unless the command key maps it). That's OK — the important thing is
        # that the machine completes correctly.
        self.assertEqual(sm.state, ATParserState.COMPLETE)

    def test_unsolicited_during_message_body_stored(self):
        captured = []
        sm = self._setup_after_prompt(callback=lambda m: captured.append(m))
        sm.process_line("RING\r\n")
        sm.process_line("OK\r\n")
        msgs = sm.get_unsolicited_messages()
        self.assertTrue(any("RING" in m for m in msgs))
        self.assertEqual(len(captured), 1)

    def test_timeout_during_message_body(self):
        sm = self._setup_after_prompt()
        sm.timeout()
        self.assertEqual(sm.state, ATParserState.TIMEOUT)
        self.assertTrue(sm.is_done())


# ---------------------------------------------------------------------------
# 12. Full multi-step flow with interleaved unsolicited messages
# ---------------------------------------------------------------------------

class TestFullMultiStepFlow(unittest.TestCase):

    def test_ctmgs_with_unsolicited_before_and_after_prompt(self):
        """Full CTMGS flow: unsolicited before prompt, after prompt, then OK."""
        captured = []
        sm = _make_sm(callback=lambda m: captured.append(m))
        sm.start('AT+CTMGS="123",0', expect_prompt=True)

        # Unsolicited before prompt
        sm.process_line("RING\r\n")
        self.assertEqual(sm.state, ATParserState.WAITING_PROMPT)

        # Prompt received
        sm.prompt_received()
        self.assertEqual(sm.state, ATParserState.COLLECTING_MESSAGE_BODY)

        # Unsolicited after prompt
        sm.process_line("+CLIP: \"9999\",145\r\n")

        # Final response
        sm.process_line("OK\r\n")

        self.assertEqual(sm.state, ATParserState.COMPLETE)
        self.assertTrue(sm.is_success())
        self.assertEqual(len(captured), 2)
        self.assertTrue(any("RING" in m for m in captured))
        self.assertTrue(any("+CLIP:" in m for m in captured))

    def test_ctmgs_error_flow(self):
        sm = _make_sm()
        sm.start('AT+CTMGS="123",0', expect_prompt=True)
        sm.prompt_received()
        sm.process_line("ERROR\r\n")
        self.assertFalse(sm.is_success())
        self.assertEqual(sm.final_response, "ERROR")


# ---------------------------------------------------------------------------
# 13. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):

    def test_empty_line_skipped(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("\r\n")
        sm.process_line("OK\r\n")
        self.assertEqual(sm.state, ATParserState.COMPLETE)

    def test_line_with_only_spaces_skipped(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("   \r\n")
        sm.process_line("OK\r\n")
        self.assertEqual(sm.state, ATParserState.COMPLETE)

    def test_process_line_in_idle_is_noop(self):
        sm = _make_sm()
        sm.process_line("OK\r\n")
        self.assertEqual(sm.state, ATParserState.IDLE)

    def test_connection_error_mid_parse(self):
        sm = _make_sm()
        sm.start("AT+CGMI")
        sm.process_line("SimulatedTetraRadio\r\n")
        sm.connection_error()
        self.assertEqual(sm.state, ATParserState.ERROR)
        self.assertTrue(sm.is_done())

    def test_take_unsolicited_clears_buffer(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("RING\r\n")
        sm.process_line("OK\r\n")
        msgs1 = sm.take_unsolicited_messages()
        msgs2 = sm.get_unsolicited_messages()
        self.assertEqual(len(msgs1), 1)
        self.assertEqual(len(msgs2), 0)

    def test_multiple_consecutive_unsolicited(self):
        sm = _make_sm()
        sm.start("AT+CGMI")
        sm.process_line("RING\r\n")
        sm.process_line("RING\r\n")
        sm.process_line("+CLIP: \"1234\",145\r\n")
        sm.process_line("+CMTI: \"SM\",1\r\n")
        sm.process_line("OK\r\n")
        msgs = sm.get_unsolicited_messages()
        self.assertEqual(len(msgs), 4)

    def test_repeated_unsolicited_triggers_callback_each_time(self):
        """Each occurrence of the same unsolicited message invokes the callback once."""
        captured = []
        sm = _make_sm(callback=lambda m: captured.append(m))
        sm.start("AT+CGMI")
        sm.process_line("RING\r\n")
        sm.process_line("RING\r\n")
        sm.process_line("RING\r\n")
        sm.process_line("OK\r\n")
        self.assertEqual(len(captured), 3,
                         "Callback should be invoked once per unsolicited occurrence")

    def test_response_with_only_terminator(self):
        sm = _make_sm()
        sm.start("AT")
        sm.process_line("OK\r\n")
        self.assertEqual(sm.build_response(), "OK\r\n")

    def test_waiting_for_prompt_helper(self):
        sm = _make_sm()
        sm.start('AT+CTMGS="123",0', expect_prompt=True)
        self.assertTrue(sm.waiting_for_prompt())
        sm.prompt_received()
        self.assertFalse(sm.waiting_for_prompt())

    def test_is_done_for_all_terminal_states(self):
        for state in (ATParserState.COMPLETE, ATParserState.TIMEOUT, ATParserState.ERROR):
            sm = _make_sm()
            sm.state = state
            self.assertTrue(sm.is_done(), f"is_done() should be True for {state}")

    def test_is_done_false_for_non_terminal_states(self):
        for state in (ATParserState.IDLE, ATParserState.COMMAND_SENT,
                      ATParserState.WAITING_RESPONSE, ATParserState.WAITING_PROMPT,
                      ATParserState.COLLECTING_MESSAGE_BODY):
            sm = _make_sm()
            sm.state = state
            self.assertFalse(sm.is_done(), f"is_done() should be False for {state}")

    def test_no_carrier_is_not_success(self):
        sm = _make_sm()
        sm.start("AT+CHUP")
        sm.process_line("NO CARRIER\r\n")
        self.assertFalse(sm.is_success())
        self.assertEqual(sm.final_response, "NO CARRIER")

    def test_response_lines_exclude_unsolicited(self):
        sm = _make_sm()
        sm.start("AT+CGMI")
        sm.process_line("ManufacturerName\r\n")
        sm.process_line("RING\r\n")
        sm.process_line("ModelInfo\r\n")
        sm.process_line("OK\r\n")
        resp = sm.build_response()
        self.assertIn("ManufacturerName", resp)
        self.assertIn("ModelInfo", resp)
        self.assertNotIn("RING", resp)


# ---------------------------------------------------------------------------
# 14. FINAL_TERMINATORS constant
# ---------------------------------------------------------------------------

class TestFinalTerminatorsConstant(unittest.TestCase):

    def test_contains_ok(self):
        self.assertIn("OK", FINAL_TERMINATORS)

    def test_contains_error(self):
        self.assertIn("ERROR", FINAL_TERMINATORS)

    def test_contains_no_carrier(self):
        self.assertIn("NO CARRIER", FINAL_TERMINATORS)

    def test_contains_no_dialtone(self):
        self.assertIn("NO DIALTONE", FINAL_TERMINATORS)

    def test_contains_busy(self):
        self.assertIn("BUSY", FINAL_TERMINATORS)

    def test_contains_no_answer(self):
        self.assertIn("NO ANSWER", FINAL_TERMINATORS)

    def test_terminators_are_stripped(self):
        for t in FINAL_TERMINATORS:
            self.assertEqual(t, t.strip())


# ---------------------------------------------------------------------------
# 15. ATParserState enum
# ---------------------------------------------------------------------------

class TestATParserStateEnum(unittest.TestCase):

    def test_all_required_states_exist(self):
        required = {
            "IDLE", "COMMAND_SENT", "WAITING_RESPONSE", "WAITING_PROMPT",
            "COLLECTING_MESSAGE_BODY", "COMPLETE", "TIMEOUT", "ERROR",
        }
        actual = {s.name for s in ATParserState}
        self.assertEqual(required, actual)

    def test_states_are_distinct(self):
        values = [s.value for s in ATParserState]
        self.assertEqual(len(values), len(set(values)))


if __name__ == "__main__":
    unittest.main()
