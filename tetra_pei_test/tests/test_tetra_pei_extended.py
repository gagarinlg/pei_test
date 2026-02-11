"""
Extended unit tests for tetra_pei.py to increase code coverage.
"""

import unittest
from unittest.mock import Mock, patch
from tetra_pei_test.core.tetra_pei import TetraPEI, PTTState
from tetra_pei_test.core.radio_connection import RadioConnection


class TestTetraPEIExtended(unittest.TestCase):
    """Extended test cases for TetraPEI class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock connection
        self.connection = Mock(spec=RadioConnection)
        self.connection.radio_id = "test_radio"
        self.connection.is_connected.return_value = True
        self.pei = TetraPEI(self.connection)
    
    def test_send_command_not_connected(self):
        """Test _send_command when connection is not connected."""
        self.connection.is_connected.return_value = False
        
        success, response = self.pei._send_command("AT")
        
        self.assertFalse(success)
        self.assertEqual(response, "")
    
    def test_send_command_send_failure(self):
        """Test _send_command when send fails."""
        self.connection.is_connected.return_value = True
        self.connection.send.return_value = False
        
        success, response = self.pei._send_command("AT")
        
        self.assertFalse(success)
        self.assertEqual(response, "")
    
    def test_send_command_no_wait_for_response(self):
        """Test _send_command with wait_for_response=False."""
        self.connection.is_connected.return_value = True
        self.connection.send.return_value = True
        
        success, response = self.pei._send_command("AT", wait_for_response=False)
        
        self.assertTrue(success)
        self.assertEqual(response, "")
    
    def test_send_command_error_response(self):
        """Test _send_command when receiving ERROR response."""
        self.connection.is_connected.return_value = True
        self.connection.send.return_value = True
        self.connection.receive_until.return_value = (False, "ERROR\r\n")
        
        success, response = self.pei._send_command("AT")
        
        self.assertFalse(success)
        self.assertIn("ERROR", response)
    
    def test_send_command_timeout(self):
        """Test _send_command when timeout waiting for response."""
        self.connection.is_connected.return_value = True
        self.connection.send.return_value = True
        self.connection.receive_until.return_value = (False, "")
        
        success, response = self.pei._send_command("AT")
        
        self.assertFalse(success)
    
    def test_register_to_network_failure(self):
        """Test register_to_network when command fails."""
        self.connection.is_connected.return_value = True
        self.connection.send.return_value = True
        self.connection.receive_until.return_value = (False, "ERROR\r\n")
        
        result = self.pei.register_to_network()
        
        self.assertFalse(result)
    
    def test_check_registration_status_failure(self):
        """Test check_registration_status when command fails."""
        self.connection.is_connected.return_value = True
        self.connection.send.return_value = False
        
        result = self.pei.check_registration_status()
        
        self.assertFalse(result)
    
    def test_send_text_message_group(self):
        """Test send_text_message to a group."""
        self.connection.is_connected.return_value = True
        self.connection.send.return_value = True
        self.connection.receive_until.return_value = (True, "OK\r\n")
        
        result = self.pei.send_text_message("9001", "Test message", is_group=True)
        
        self.assertTrue(result)
        # Verify the command includes group format with #
        call_args = self.connection.send.call_args[0][0]
        self.assertIn("9001#", call_args)
    
    def test_send_text_message_individual(self):
        """Test send_text_message to individual."""
        self.connection.is_connected.return_value = True
        self.connection.send.return_value = True
        self.connection.receive_until.return_value = (True, "OK\r\n")
        
        result = self.pei.send_text_message("2001", "Test message", is_group=False)
        
        self.assertTrue(result)
        call_args = self.connection.send.call_args[0][0]
        self.assertIn("2001", call_args)
        self.assertNotIn("2001#", call_args)
    
    def test_check_for_incoming_call_with_caller_id(self):
        """Test check_for_incoming_call extracts caller ID."""
        self.connection.receive.return_value = 'RING\r\n+CLIP: "1234567890",145\r\n'
        
        caller = self.pei.check_for_incoming_call(timeout=1.0)
        
        self.assertEqual(caller, "1234567890")
    
    def test_check_for_incoming_call_no_caller_id(self):
        """Test check_for_incoming_call returns UNKNOWN when no caller ID."""
        self.connection.receive.return_value = 'RING\r\n'
        
        caller = self.pei.check_for_incoming_call(timeout=1.0)
        
        self.assertEqual(caller, "UNKNOWN")
    
    def test_check_for_incoming_call_no_ring(self):
        """Test check_for_incoming_call returns None when no ring."""
        self.connection.receive.return_value = 'Some other data\r\n'
        
        caller = self.pei.check_for_incoming_call(timeout=1.0)
        
        self.assertIsNone(caller)
    
    def test_check_for_ptt_event_pressed(self):
        """Test check_for_ptt_event detects PTT pressed."""
        self.connection.receive.return_value = '+CTXD: 1\r\n'
        
        state = self.pei.check_for_ptt_event(timeout=1.0)
        
        self.assertEqual(state, PTTState.PRESSED)
    
    def test_check_for_ptt_event_released(self):
        """Test check_for_ptt_event detects PTT released."""
        self.connection.receive.return_value = '+CTXD: 0\r\n'
        
        state = self.pei.check_for_ptt_event(timeout=1.0)
        
        self.assertEqual(state, PTTState.RELEASED)
    
    def test_check_for_ptt_event_alternate_format(self):
        """Test check_for_ptt_event with alternate CPIN format."""
        self.connection.receive.return_value = '+CPIN: 1\r\n'
        
        state = self.pei.check_for_ptt_event(timeout=1.0)
        
        self.assertEqual(state, PTTState.PRESSED)
    
    def test_check_for_ptt_event_no_data(self):
        """Test check_for_ptt_event returns None with no data."""
        self.connection.receive.return_value = None
        
        state = self.pei.check_for_ptt_event(timeout=1.0)
        
        self.assertIsNone(state)
    
    def test_check_for_text_message_received(self):
        """Test check_for_text_message detects message."""
        self.connection.receive.return_value = '+CMTI: "SM",1\r\n'
        
        message = self.pei.check_for_text_message(timeout=1.0)
        
        self.assertIsNotNone(message)
        self.assertIn("sender", message)
        self.assertIn("message", message)
        self.assertIn("raw", message)
    
    def test_check_for_text_message_no_message(self):
        """Test check_for_text_message returns None with no message."""
        self.connection.receive.return_value = 'Some other data\r\n'
        
        message = self.pei.check_for_text_message(timeout=1.0)
        
        self.assertIsNone(message)
    
    def test_enable_unsolicited_notifications_failure(self):
        """Test enable_unsolicited_notifications returns False on command failure."""
        self.connection.is_connected.return_value = True
        self.connection.send.return_value = True
        # First command succeeds, second fails
        self.connection.receive_until.side_effect = [
            (True, "OK\r\n"),
            (False, "ERROR\r\n")
        ]
        
        result = self.pei.enable_unsolicited_notifications()
        
        self.assertFalse(result)
    
    def test_extract_response_value_with_value(self):
        """Test _extract_response_value extracts correct value."""
        response = "AT+CGMI\r\nManufacturer Name\r\nOK\r\n"
        
        value = self.pei._extract_response_value(response)
        
        self.assertEqual(value, "Manufacturer Name")
    
    def test_extract_response_value_empty(self):
        """Test _extract_response_value returns empty string when no value."""
        response = "AT\r\nOK\r\n"
        
        value = self.pei._extract_response_value(response)
        
        self.assertEqual(value, "")
    
    def test_get_last_response(self):
        """Test get_last_response returns last response."""
        self.pei._last_response = "Test response"
        
        response = self.pei.get_last_response()
        
        self.assertEqual(response, "Test response")


if __name__ == '__main__':
    unittest.main()
