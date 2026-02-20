"""
Unit tests for line-by-line response parsing and buffer preservation.

Tests the two key improvements:
1. Data after a final command response is not lost (buffer preservation)
2. Unsolicited messages are available while waiting for a final response
   (immediate handling), not only after receiving the final response
"""

import unittest
import time
import threading
import socket
from tetra_pei_test.core.radio_connection import RadioConnection
from tetra_pei_test.core.tetra_pei import TetraPEI
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator


class TestRadioConnectionBuffer(unittest.TestCase):
    """Test RadioConnection buffer and readline functionality."""

    def setUp(self):
        """Set up a simulator and connection."""
        self.simulator = TetraRadioSimulator(
            radio_id="buf_radio",
            host="127.0.0.1",
            port=15010,
            issi="1010"
        )
        self.simulator.start()
        time.sleep(0.5)
        self.connection = RadioConnection("buf_radio", "127.0.0.1", 15010)
        self.connection.connect()

    def tearDown(self):
        """Clean up."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)

    def test_readline_returns_complete_line(self):
        """Test that readline returns a complete line terminated by \\r\\n."""
        # Send AT command, simulator responds with OK\r\n
        self.connection.send("AT")
        line = self.connection.readline(timeout=5.0)
        self.assertIsNotNone(line)
        self.assertTrue(line.endswith('\r\n'))
        self.assertEqual(line.strip(), 'OK')

    def test_readline_preserves_buffer(self):
        """Test that readline preserves unread data in the buffer."""
        # Send AT+CGMI which returns two lines: SimulatedTetraRadio\r\n OK\r\n
        self.connection.send("AT+CGMI")
        line1 = self.connection.readline(timeout=5.0)
        self.assertIsNotNone(line1)
        self.assertEqual(line1.strip(), 'SimulatedTetraRadio')
        # Second line should be available from buffer or socket
        line2 = self.connection.readline(timeout=5.0)
        self.assertIsNotNone(line2)
        self.assertEqual(line2.strip(), 'OK')

    def test_readline_timeout_returns_none(self):
        """Test that readline returns None on timeout with no data."""
        # Don't send any command, so no data arrives
        line = self.connection.readline(timeout=0.5)
        self.assertIsNone(line)

    def test_drain_buffer_returns_buffered_lines(self):
        """Test that drain_buffer returns complete lines from the buffer."""
        # Manually populate the buffer
        self.connection._recv_buffer = "+CMTI: \"SM\",1\r\n+CTXD: 1\r\n"
        lines = self.connection.drain_buffer()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].strip(), '+CMTI: "SM",1')
        self.assertEqual(lines[1].strip(), '+CTXD: 1')
        # Buffer should be empty now
        self.assertEqual(self.connection._recv_buffer, "")

    def test_drain_buffer_preserves_partial_line(self):
        """Test that drain_buffer preserves incomplete lines in the buffer."""
        self.connection._recv_buffer = "+CMTI: \"SM\",1\r\npartial"
        lines = self.connection.drain_buffer()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].strip(), '+CMTI: "SM",1')
        # Partial line should remain
        self.assertEqual(self.connection._recv_buffer, "partial")

    def test_drain_buffer_empty_returns_empty(self):
        """Test that drain_buffer returns empty list when buffer is empty."""
        self.connection._recv_buffer = ""
        lines = self.connection.drain_buffer()
        self.assertEqual(len(lines), 0)

    def test_disconnect_clears_buffer(self):
        """Test that disconnect clears the receive buffer."""
        self.connection._recv_buffer = "some data\r\n"
        self.connection.disconnect()
        self.assertEqual(self.connection._recv_buffer, "")

    def test_receive_returns_buffered_data_first(self):
        """Test that receive() returns buffered data before reading from socket."""
        self.connection._recv_buffer = "buffered data"
        data = self.connection.receive(timeout=0.5)
        self.assertEqual(data, "buffered data")
        self.assertEqual(self.connection._recv_buffer, "")


class TestDataAfterFinalResponse(unittest.TestCase):
    """Test that data after a final command response is not lost."""

    def setUp(self):
        """Set up test fixtures with a raw TCP server for precise control."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("127.0.0.1", 15011))
        self.server_socket.listen(1)
        self.server_socket.settimeout(5.0)

        self.connection = RadioConnection("test_radio", "127.0.0.1", 15011)
        self.connection.connect()
        self.client_socket, _ = self.server_socket.accept()

        self.pei = TetraPEI(self.connection)

    def tearDown(self):
        """Clean up."""
        try:
            self.client_socket.close()
        except Exception:
            pass
        try:
            self.connection.disconnect()
        except Exception:
            pass
        try:
            self.server_socket.close()
        except Exception:
            pass
        time.sleep(0.3)

    def _send_from_server(self, data: str) -> None:
        """Send data from the simulated server to the client."""
        self.client_socket.sendall(data.encode('utf-8'))

    def test_unsolicited_after_ok_in_same_packet(self):
        """Test that unsolicited data after OK in the same TCP packet is captured."""
        def server_response():
            # Wait for the client to send a command
            self.client_socket.recv(4096)
            # Send response with unsolicited data AFTER OK in the same packet
            self._send_from_server(
                "SimulatedTetraRadio\r\nOK\r\n+CMTI: \"SM\",1\r\n"
            )

        thread = threading.Thread(target=server_response)
        thread.start()

        success, response = self.pei._send_command("AT+CGMI", timeout=5.0)
        thread.join()

        self.assertTrue(success)
        self.assertIn("SimulatedTetraRadio", response)
        self.assertIn("OK", response)
        # The +CMTI after OK should be captured as unsolicited
        unsolicited = self.pei.get_unsolicited_messages()
        self.assertTrue(
            any("+CMTI:" in msg for msg in unsolicited),
            f"Expected +CMTI in unsolicited messages, got: {unsolicited}"
        )

    def test_multiple_unsolicited_after_ok(self):
        """Test that multiple unsolicited messages after OK are all captured."""
        def server_response():
            self.client_socket.recv(4096)
            self._send_from_server(
                "OK\r\nRING\r\n+CLIP: \"9999\",145\r\n"
            )

        thread = threading.Thread(target=server_response)
        thread.start()

        success, response = self.pei._send_command("AT", timeout=5.0)
        thread.join()

        self.assertTrue(success)
        unsolicited = self.pei.get_unsolicited_messages()
        self.assertTrue(
            any("RING" in msg for msg in unsolicited),
            f"Expected RING in unsolicited, got: {unsolicited}"
        )
        self.assertTrue(
            any("+CLIP:" in msg for msg in unsolicited),
            f"Expected +CLIP in unsolicited, got: {unsolicited}"
        )

    def test_data_after_ok_preserved_for_next_command(self):
        """Test that non-unsolicited data after OK is preserved in the buffer."""
        def server_response():
            self.client_socket.recv(4096)
            # Send OK followed by some data
            self._send_from_server("OK\r\n+CMTI: \"SM\",1\r\n")

        thread = threading.Thread(target=server_response)
        thread.start()

        success, _ = self.pei._send_command("AT", timeout=5.0)
        thread.join()

        self.assertTrue(success)
        # The data after OK should have been captured as unsolicited
        unsolicited = self.pei.get_unsolicited_messages()
        self.assertTrue(len(unsolicited) > 0)

    def test_data_after_error_response_preserved(self):
        """Test that data after an ERROR response is preserved."""
        def server_response():
            self.client_socket.recv(4096)
            self._send_from_server("ERROR\r\n+CMTI: \"SM\",2\r\n")

        thread = threading.Thread(target=server_response)
        thread.start()

        success, response = self.pei._send_command("AT+INVALID", timeout=5.0)
        thread.join()

        self.assertFalse(success)
        self.assertIn("ERROR", response)
        unsolicited = self.pei.get_unsolicited_messages()
        self.assertTrue(
            any("+CMTI:" in msg for msg in unsolicited),
            f"Expected +CMTI in unsolicited after ERROR, got: {unsolicited}"
        )


class TestUnsolicitedDuringWait(unittest.TestCase):
    """Test that unsolicited messages are available while waiting for a response."""

    def setUp(self):
        """Set up test fixtures with a raw TCP server for precise timing control."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("127.0.0.1", 15012))
        self.server_socket.listen(1)
        self.server_socket.settimeout(5.0)

        self.connection = RadioConnection("test_radio", "127.0.0.1", 15012)
        self.connection.connect()
        self.client_socket, _ = self.server_socket.accept()

        self.pei = TetraPEI(self.connection)
        self.callback_messages = []
        self.callback_times = []

    def tearDown(self):
        """Clean up."""
        try:
            self.client_socket.close()
        except Exception:
            pass
        try:
            self.connection.disconnect()
        except Exception:
            pass
        try:
            self.server_socket.close()
        except Exception:
            pass
        time.sleep(0.3)

    def _send_from_server(self, data: str) -> None:
        """Send data from the simulated server to the client."""
        self.client_socket.sendall(data.encode('utf-8'))

    def _unsolicited_callback(self, message):
        """Record unsolicited messages and their arrival times."""
        self.callback_messages.append(message)
        self.callback_times.append(time.time())

    def test_callback_invoked_before_final_response(self):
        """Test that unsolicited callback is invoked before the final OK arrives."""
        self.pei.set_unsolicited_callback(self._unsolicited_callback)

        ok_sent_time = [None]

        def server_response():
            self.client_socket.recv(4096)
            # Send unsolicited message first
            self._send_from_server("RING\r\n")
            time.sleep(0.2)
            # Then send the actual response
            ok_sent_time[0] = time.time()
            self._send_from_server("SimulatedTetraRadio\r\nOK\r\n")

        thread = threading.Thread(target=server_response)
        thread.start()

        success, response = self.pei._send_command("AT+CGMI", timeout=5.0)
        thread.join()

        self.assertTrue(success)
        # Callback should have been invoked for RING
        self.assertTrue(
            any("RING" in msg for msg in self.callback_messages),
            f"Expected RING callback, got: {self.callback_messages}"
        )
        # RING callback should have been invoked BEFORE the OK was sent
        if self.callback_times and ok_sent_time[0] is not None:
            ring_time = self.callback_times[0]
            self.assertLess(
                ring_time, ok_sent_time[0],
                "Unsolicited callback should fire before final response arrives"
            )

    def test_unsolicited_stored_during_wait(self):
        """Test that unsolicited messages are stored while waiting for response."""
        stored_during_wait = []

        def check_callback(message):
            """Callback that also checks current unsolicited buffer."""
            stored_during_wait.append(message)

        self.pei.set_unsolicited_callback(check_callback)

        def server_response():
            self.client_socket.recv(4096)
            # Send unsolicited message before the response data
            self._send_from_server("+CMTI: \"SM\",1\r\n")
            time.sleep(0.1)
            self._send_from_server("SimulatedTetraRadio\r\nOK\r\n")

        thread = threading.Thread(target=server_response)
        thread.start()

        success, response = self.pei._send_command("AT+CGMI", timeout=5.0)
        thread.join()

        self.assertTrue(success)
        self.assertIn("SimulatedTetraRadio", response)
        # The unsolicited message should have been stored during the wait
        self.assertTrue(
            any("+CMTI:" in msg for msg in stored_during_wait),
            f"Expected +CMTI stored during wait, got: {stored_during_wait}"
        )

    def test_multiple_unsolicited_during_wait(self):
        """Test that multiple unsolicited messages during wait are all handled."""
        self.pei.set_unsolicited_callback(self._unsolicited_callback)

        def server_response():
            self.client_socket.recv(4096)
            self._send_from_server("RING\r\n")
            time.sleep(0.05)
            self._send_from_server("+CLIP: \"8888\",145\r\n")
            time.sleep(0.05)
            self._send_from_server("+CREG: 0,1\r\nOK\r\n")

        thread = threading.Thread(target=server_response)
        thread.start()

        # AT+CGMI doesn't expect +CREG:, so it should be filtered as unsolicited
        success, response = self.pei._send_command("AT+CGMI", timeout=5.0)
        thread.join()

        self.assertTrue(success)
        # All three should be captured as unsolicited (RING, CLIP, CREG for non-CREG command)
        self.assertEqual(len(self.callback_messages), 3,
                         f"Expected 3 callbacks, got: {self.callback_messages}")
        self.assertTrue(any("RING" in msg for msg in self.callback_messages))
        self.assertTrue(any("+CLIP:" in msg for msg in self.callback_messages))
        self.assertTrue(any("+CREG:" in msg for msg in self.callback_messages))

    def test_solicited_not_treated_as_unsolicited(self):
        """Test that solicited responses are not filtered as unsolicited."""
        self.pei.set_unsolicited_callback(self._unsolicited_callback)

        def server_response():
            self.client_socket.recv(4096)
            self._send_from_server("+CREG: 0,1\r\nOK\r\n")

        thread = threading.Thread(target=server_response)
        thread.start()

        # AT+CREG? expects +CREG: so it should NOT be filtered
        success, response = self.pei._send_command("AT+CREG?", timeout=5.0)
        thread.join()

        self.assertTrue(success)
        self.assertIn("+CREG:", response)
        # No unsolicited callback should have been invoked
        self.assertEqual(len(self.callback_messages), 0,
                         f"Expected no callbacks for solicited response, got: {self.callback_messages}")

    def test_mixed_solicited_and_unsolicited_during_wait(self):
        """Test mix of solicited and unsolicited responses during wait."""
        self.pei.set_unsolicited_callback(self._unsolicited_callback)

        def server_response():
            self.client_socket.recv(4096)
            # RING is unsolicited during AT+CREG?
            self._send_from_server("RING\r\n")
            time.sleep(0.05)
            # +CREG: is solicited for AT+CREG?
            self._send_from_server("+CREG: 0,1\r\n")
            time.sleep(0.05)
            self._send_from_server("OK\r\n")

        thread = threading.Thread(target=server_response)
        thread.start()

        success, response = self.pei._send_command("AT+CREG?", timeout=5.0)
        thread.join()

        self.assertTrue(success)
        # Solicited +CREG: should be in the response
        self.assertIn("+CREG:", response)
        # RING should NOT be in the response
        self.assertNotIn("RING", response)
        # Only RING should be in unsolicited
        self.assertEqual(len(self.callback_messages), 1)
        self.assertIn("RING", self.callback_messages[0])


class TestHandleLineIfUnsolicited(unittest.TestCase):
    """Test the _handle_line_if_unsolicited helper method."""

    def setUp(self):
        """Set up a PEI instance with a mock connection."""
        self.simulator = TetraRadioSimulator(
            radio_id="helper_radio",
            host="127.0.0.1",
            port=15013,
            issi="1013"
        )
        self.simulator.start()
        time.sleep(0.5)
        self.connection = RadioConnection("helper_radio", "127.0.0.1", 15013)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)

    def tearDown(self):
        """Clean up."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)

    def test_unsolicited_pattern_returns_true(self):
        """Test that known unsolicited patterns are detected."""
        result = self.pei._handle_line_if_unsolicited("RING", [])
        self.assertTrue(result)
        self.assertEqual(len(self.pei._unsolicited_messages), 1)
        self.assertIn("RING", self.pei._unsolicited_messages[0])

    def test_expected_pattern_returns_false(self):
        """Test that expected solicited patterns are not treated as unsolicited."""
        result = self.pei._handle_line_if_unsolicited("+CREG: 0,1", ["+CREG:"])
        self.assertFalse(result)
        self.assertEqual(len(self.pei._unsolicited_messages), 0)

    def test_non_matching_line_returns_false(self):
        """Test that lines not matching any unsolicited pattern return False."""
        result = self.pei._handle_line_if_unsolicited("SimulatedTetraRadio", [])
        self.assertFalse(result)
        self.assertEqual(len(self.pei._unsolicited_messages), 0)

    def test_callback_invoked_for_unsolicited(self):
        """Test that callback is invoked for unsolicited messages."""
        callback_messages = []
        self.pei.set_unsolicited_callback(lambda msg: callback_messages.append(msg))
        self.pei._handle_line_if_unsolicited("+CMTI: \"SM\",1", [])
        self.assertEqual(len(callback_messages), 1)
        self.assertIn("+CMTI:", callback_messages[0])

    def test_callback_not_invoked_for_expected(self):
        """Test that callback is NOT invoked for expected solicited responses."""
        callback_messages = []
        self.pei.set_unsolicited_callback(lambda msg: callback_messages.append(msg))
        self.pei._handle_line_if_unsolicited("+CREG: 0,1", ["+CREG:"])
        self.assertEqual(len(callback_messages), 0)

    def test_callback_exception_does_not_propagate(self):
        """Test that callback exceptions don't crash the parser."""
        def bad_callback(msg):
            raise ValueError("Callback error")

        self.pei.set_unsolicited_callback(bad_callback)
        # Should not raise
        result = self.pei._handle_line_if_unsolicited("RING", [])
        self.assertTrue(result)
        self.assertEqual(len(self.pei._unsolicited_messages), 1)


class TestDrainBufferedUnsolicited(unittest.TestCase):
    """Test the _drain_buffered_unsolicited helper method."""

    def setUp(self):
        """Set up a PEI instance."""
        self.simulator = TetraRadioSimulator(
            radio_id="drain_radio",
            host="127.0.0.1",
            port=15014,
            issi="1014"
        )
        self.simulator.start()
        time.sleep(0.5)
        self.connection = RadioConnection("drain_radio", "127.0.0.1", 15014)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)

    def tearDown(self):
        """Clean up."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)

    def test_drain_processes_buffered_unsolicited(self):
        """Test that drain processes buffered lines as unsolicited."""
        self.connection._recv_buffer = "+CMTI: \"SM\",1\r\nRING\r\n"
        self.pei._drain_buffered_unsolicited()
        unsolicited = self.pei.get_unsolicited_messages()
        self.assertEqual(len(unsolicited), 2)

    def test_drain_with_empty_buffer(self):
        """Test that drain with empty buffer does nothing."""
        self.connection._recv_buffer = ""
        self.pei._drain_buffered_unsolicited()
        unsolicited = self.pei.get_unsolicited_messages()
        self.assertEqual(len(unsolicited), 0)

    def test_drain_invokes_callback(self):
        """Test that drain invokes callback for each unsolicited line."""
        callback_msgs = []
        self.pei.set_unsolicited_callback(lambda msg: callback_msgs.append(msg))
        self.connection._recv_buffer = "+CMTI: \"SM\",1\r\n"
        self.pei._drain_buffered_unsolicited()
        self.assertEqual(len(callback_msgs), 1)


class TestIntegrationWithSimulator(unittest.TestCase):
    """Integration tests using the radio simulator."""

    def setUp(self):
        """Set up simulator and connection."""
        self.simulator = TetraRadioSimulator(
            radio_id="integ_radio",
            host="127.0.0.1",
            port=15015,
            issi="1015"
        )
        self.simulator.start()
        time.sleep(0.5)
        self.connection = RadioConnection("integ_radio", "127.0.0.1", 15015)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)

    def tearDown(self):
        """Clean up."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)

    def test_unsolicited_during_info_query(self):
        """Test unsolicited messages during a real AT+CGMI query.
        
        Note: With the simulator on loopback, the command response arrives
        almost instantly, so the unsolicited message may arrive after
        _send_command returns. The test verifies that it's still captured
        (either during the command or picked up by a subsequent read).
        The precise timing behavior is thoroughly tested in
        TestUnsolicitedDuringWait using a raw TCP server.
        """
        callback_msgs = []
        self.pei.set_unsolicited_callback(lambda msg: callback_msgs.append(msg))

        def inject_unsolicited():
            time.sleep(0.05)
            self.simulator.simulate_incoming_call("7777")

        thread = threading.Thread(target=inject_unsolicited)
        thread.start()

        success, response = self.pei._send_command("AT+CGMI", timeout=5.0)

        # Wait for the unsolicited message to be injected
        thread.join()

        # The response should be correct regardless of unsolicited timing
        self.assertTrue(success)
        self.assertIn("SimulatedTetraRadio", response)

        # Give a brief window for the unsolicited to arrive via socket
        time.sleep(0.2)
        # Try reading any remaining data from the socket that arrived after the command
        remaining = self.connection.receive(timeout=0.5)
        if remaining:
            self.connection._recv_buffer += remaining
            self.pei._drain_buffered_unsolicited()

        all_unsolicited = self.pei.get_unsolicited_messages(clear=False)
        all_captured = all_unsolicited + callback_msgs
        self.assertTrue(
            any("RING" in msg for msg in all_captured),
            f"Expected RING in unsolicited messages or callbacks, got: {all_captured}"
        )

    def test_sequential_commands_preserve_state(self):
        """Test that sequential commands don't lose unsolicited messages."""
        success1, _ = self.pei._send_command("AT")
        self.assertTrue(success1)

        success2, response2 = self.pei._send_command("AT+CGMI")
        self.assertTrue(success2)
        self.assertIn("SimulatedTetraRadio", response2)

        success3, response3 = self.pei._send_command("AT+CREG?")
        self.assertTrue(success3)
        self.assertIn("+CREG:", response3)


if __name__ == '__main__':
    unittest.main()
