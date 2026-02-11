"""
Unit tests for unsolicited message handling during AT command execution.
"""

import unittest
import time
import threading
from tetra_pei_test.core.radio_connection import RadioConnection
from tetra_pei_test.core.tetra_pei import TetraPEI
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator


class TestUnsolicitedMessages(unittest.TestCase):
    """Test cases for handling unsolicited messages during AT commands."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Start simulator
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15002,
            issi="1002"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        # Create connection and PEI
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15002)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_unsolicited_message_before_ok(self):
        """Test that unsolicited messages before OK are handled correctly."""
        # Test with a crafted response that has unsolicited before OK
        test_response = "AT+CGMM\r\nModel-test_radio\r\n+CMTI: \"SM\",1\r\nOK\r\n"
        
        filtered, unsolicited = self.pei._filter_unsolicited_messages(test_response)
        
        # Should filter out CMTI
        self.assertNotIn("+CMTI:", filtered)
        # Should keep the command echo and response
        self.assertIn("Model-test_radio", filtered)
        self.assertIn("OK", filtered)
        # Should capture the unsolicited message
        self.assertEqual(len(unsolicited), 1)
        self.assertIn("+CMTI:", unsolicited[0])
    
    def test_multiple_unsolicited_messages(self):
        """Test handling multiple unsolicited messages during command."""
        # Test with a response that has multiple unsolicited messages
        test_response = "+CTXD: 1\r\nSimulatedTetraRadio\r\n+CTXD: 0\r\nOK\r\n"
        
        filtered, unsolicited = self.pei._filter_unsolicited_messages(test_response)
        
        # Should filter out both CTXD messages
        self.assertNotIn("+CTXD:", filtered)
        # Should keep the actual response
        self.assertIn("SimulatedTetraRadio", filtered)
        self.assertIn("OK", filtered)
        # Should capture both unsolicited messages
        self.assertEqual(len(unsolicited), 2)
        self.assertIn("+CTXD: 1", unsolicited[0])
        self.assertIn("+CTXD: 0", unsolicited[1])
    
    def test_unsolicited_message_stored(self):
        """Test that unsolicited messages are stored for later retrieval."""
        # Test the filter function directly with a known response
        test_response = "SimulatedTetraRadio\r\nRING\r\n+CLIP: \"9999\",145\r\nOK\r\n"
        
        filtered, unsolicited = self.pei._filter_unsolicited_messages(test_response)
        
        # Should filter out RING and CLIP
        self.assertNotIn("RING", filtered)
        self.assertNotIn("CLIP", filtered)
        # Should keep the actual response
        self.assertIn("SimulatedTetraRadio", filtered)
        self.assertIn("OK", filtered)
        # Should capture unsolicited messages
        self.assertEqual(len(unsolicited), 2)
        self.assertIn("RING", unsolicited[0])
        self.assertIn("CLIP", unsolicited[1])
    
    def test_command_response_not_polluted(self):
        """Test that command response doesn't contain unsolicited messages."""
        # Inject unsolicited message during command execution
        # We need to ensure it arrives BEFORE the OK response
        def send_unsolicited():
            time.sleep(0.02)  # Very short delay
            self.simulator.simulate_incoming_call("9999")
            time.sleep(0.02)  # Give it time to be sent
        
        thread = threading.Thread(target=send_unsolicited)
        thread.start()
        
        # Add a small delay to processing in the simulator by using a slower command
        # Use AT+COPS which has longer timeout
        success, response = self.pei._send_command("AT+COPS=0", timeout=5.0)
        
        thread.join()
        
        self.assertTrue(success)
        # Response should contain OK
        self.assertIn("OK", response)
        # But should NOT contain RING or CLIP
        self.assertNotIn("RING", response, "Unsolicited RING message should not be in command response")
        self.assertNotIn("CLIP", response, "Unsolicited CLIP message should not be in command response")
        
        # If unsolicited messages were captured, verify them
        unsolicited = self.pei.get_unsolicited_messages(clear=False)
        if len(unsolicited) > 0:
            # Check that RING is in the unsolicited messages
            self.assertTrue(any("RING" in msg for msg in unsolicited), "RING should be in unsolicited messages")
    
    def test_unsolicited_after_multiple_commands(self):
        """Test unsolicited message handling across multiple commands."""
        # Send first command
        success1, _ = self.pei._send_command("AT")
        self.assertTrue(success1)
        
        # Send unsolicited message
        def send_unsolicited():
            time.sleep(0.1)
            self.simulator.simulate_text_message("9999", "Test")
        
        thread = threading.Thread(target=send_unsolicited)
        thread.start()
        
        # Send second command
        success2, response2 = self.pei._send_command("AT+CGMM")
        
        thread.join()
        
        self.assertTrue(success2)
        self.assertIn("OK", response2)


if __name__ == '__main__':
    unittest.main()
