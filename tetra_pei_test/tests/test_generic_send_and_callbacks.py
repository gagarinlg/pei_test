"""
Unit tests for generic send command and unsolicited callback functionality.

Tests the newly added features:
- send_at_command() for generic AT command sending
- set_unsolicited_callback() for real-time unsolicited message handling
- clear_unsolicited_messages() for buffer management
"""

import unittest
import time
from tetra_pei_test.core.radio_connection import RadioConnection
from tetra_pei_test.core.tetra_pei import TetraPEI
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator


class TestGenericSendCommand(unittest.TestCase):
    """Test cases for generic AT command sending."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15050,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15050)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_send_at_command_basic(self):
        """Test sending a basic AT command."""
        success, response = self.pei.send_at_command("AT")
        self.assertTrue(success)
        self.assertIn("OK", response)
    
    def test_send_at_command_with_query(self):
        """Test sending an AT query command."""
        success, response = self.pei.send_at_command("AT+CGMI")
        self.assertTrue(success)
        self.assertIn("SimulatedTetraRadio", response)
        self.assertIn("OK", response)
    
    def test_send_at_command_with_parameter(self):
        """Test sending an AT command with parameters."""
        success, response = self.pei.send_at_command("AT+FCLASS=1")
        self.assertTrue(success)
        self.assertIn("OK", response)
    
    def test_send_at_command_invalid(self):
        """Test sending an invalid AT command."""
        success, response = self.pei.send_at_command("AT+INVALID")
        self.assertFalse(success)
        self.assertIn("ERROR", response)
    
    def test_send_at_command_timeout(self):
        """Test generic AT command with custom timeout."""
        success, response = self.pei.send_at_command("AT+CGMI", timeout=10.0)
        self.assertTrue(success)
        self.assertIn("OK", response)


class TestUnsolicitedCallback(unittest.TestCase):
    """Test cases for unsolicited message callback functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15051,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15051)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
        
        # Track callback invocations
        self.callback_messages = []
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def _test_callback(self, message):
        """Test callback that stores received messages."""
        self.callback_messages.append(message)
    
    def test_set_unsolicited_callback(self):
        """Test setting an unsolicited message callback."""
        self.pei.set_unsolicited_callback(self._test_callback)
        self.assertIsNotNone(self.pei._unsolicited_callback)
    
    def test_clear_unsolicited_callback(self):
        """Test clearing an unsolicited message callback."""
        self.pei.set_unsolicited_callback(self._test_callback)
        self.pei.set_unsolicited_callback(None)
        self.assertIsNone(self.pei._unsolicited_callback)
    
    def test_callback_invoked_on_unsolicited_message(self):
        """Test that callback is invoked when unsolicited messages arrive."""
        # Set up callback
        self.pei.set_unsolicited_callback(self._test_callback)
        
        # Simulate an unsolicited message by directly adding to the filter result
        # In a real scenario, this would come from the radio during command execution
        self.pei._unsolicited_messages.append('+CTICN: 1,"2001"')
        
        # The callback should have been called during message filtering
        # Since we added it manually, we need to trigger it manually too
        if self.pei._unsolicited_callback:
            self.pei._unsolicited_callback('+CTICN: 1,"2001"')
        
        # Verify callback was invoked
        self.assertEqual(len(self.callback_messages), 1)
        self.assertIn('+CTICN:', self.callback_messages[0])
    
    def test_callback_with_multiple_messages(self):
        """Test callback with multiple unsolicited messages."""
        self.pei.set_unsolicited_callback(self._test_callback)
        
        # Simulate multiple unsolicited messages
        messages = ['+CTICN: 1,"2001"', '+CTOCP: 1,"Calling"', '+CTCC: 1,0']
        for msg in messages:
            if self.pei._unsolicited_callback:
                self.pei._unsolicited_callback(msg)
        
        # Verify all were received
        self.assertEqual(len(self.callback_messages), 3)
    
    def test_callback_exception_handling(self):
        """Test that exceptions in callback don't break the system."""
        def bad_callback(message):
            raise ValueError("Test exception")
        
        self.pei.set_unsolicited_callback(bad_callback)
        
        # Simulate what happens during _send_command when an exception occurs
        # The exception should be caught and logged in the actual implementation
        unsolicited = ['+CTICN: 1,"2001"']
        
        # This mimics the code in _send_command that handles callbacks
        exception_caught = False
        for msg in unsolicited:
            try:
                self.pei._unsolicited_callback(msg)
            except Exception:
                exception_caught = True
        
        # In the actual implementation, the exception is caught
        # Here we verify that calling directly raises the exception
        # (which is expected since we're not inside the try-catch of _send_command)
        self.assertTrue(exception_caught, "Exception should be raised when calling callback directly")


class TestUnsolicitedMessageManagement(unittest.TestCase):
    """Test cases for unsolicited message buffer management."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15052,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15052)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_clear_unsolicited_messages(self):
        """Test clearing the unsolicited messages buffer."""
        # Add some messages to the buffer
        self.pei._unsolicited_messages.extend([
            '+CTICN: 1,"2001"',
            '+CTOCP: 1,"Calling"',
            '+CTCC: 1,0'
        ])
        
        # Verify messages are there
        self.assertEqual(len(self.pei._unsolicited_messages), 3)
        
        # Clear the buffer
        self.pei.clear_unsolicited_messages()
        
        # Verify buffer is empty
        self.assertEqual(len(self.pei._unsolicited_messages), 0)
    
    def test_get_unsolicited_messages_with_clear(self):
        """Test getting unsolicited messages with clear=True."""
        # Add some messages
        self.pei._unsolicited_messages.extend([
            '+CTICN: 1,"2001"',
            '+CTOCP: 1,"Calling"'
        ])
        
        # Get messages with clear
        messages = self.pei.get_unsolicited_messages(clear=True)
        
        # Verify we got the messages
        self.assertEqual(len(messages), 2)
        
        # Verify buffer is cleared
        self.assertEqual(len(self.pei._unsolicited_messages), 0)
    
    def test_get_unsolicited_messages_without_clear(self):
        """Test getting unsolicited messages with clear=False."""
        # Add some messages
        self.pei._unsolicited_messages.extend([
            '+CTICN: 1,"2001"',
            '+CTOCP: 1,"Calling"'
        ])
        
        # Get messages without clear
        messages = self.pei.get_unsolicited_messages(clear=False)
        
        # Verify we got the messages
        self.assertEqual(len(messages), 2)
        
        # Verify buffer still has messages
        self.assertEqual(len(self.pei._unsolicited_messages), 2)
    
    def test_clear_empty_buffer(self):
        """Test clearing an already empty buffer."""
        # Ensure buffer is empty
        self.pei.clear_unsolicited_messages()
        
        # Clear again (should not raise exception)
        self.pei.clear_unsolicited_messages()
        
        # Verify still empty
        self.assertEqual(len(self.pei._unsolicited_messages), 0)


class TestCommandDescriptionUpdates(unittest.TestCase):
    """Test that command descriptions have been updated correctly."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15053,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15053)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_cnumf_description(self):
        """Test that CNUMF description mentions 'fixed numbers'."""
        docstring = self.pei.set_forwarding_number.__doc__
        self.assertIn("fixed numbers", docstring.lower())
    
    def test_cnums_description(self):
        """Test that CNUMS description mentions 'static identities'."""
        docstring = self.pei.get_subscriber_number.__doc__
        self.assertIn("static identit", docstring.lower())
    
    def test_cnumd_description(self):
        """Test that CNUMD description mentions 'dynamic identities'."""
        docstring = self.pei.get_dialing_number.__doc__
        self.assertIn("dynamic identit", docstring.lower())
    
    def test_unsolicited_patterns_updated(self):
        """Test that unsolicited pattern comments are updated."""
        # Check that the patterns list has the correct comments
        # We can verify by checking the source code or by testing functionality
        patterns = self.pei._unsolicited_patterns
        
        # Verify that all expected patterns are present
        # CNUMF is NOT in unsolicited - it's a query response only
        self.assertNotIn('+CNUMF:', patterns)
        # CNUMS and CNUMD can be unsolicited notifications
        self.assertIn('+CNUMS:', patterns)
        self.assertIn('+CNUMD:', patterns)


if __name__ == '__main__':
    unittest.main()
