"""
Unit tests for new TETRA PEI commands.

Tests all the newly implemented TETRA PEI commands:
- FLCASS, CMEE, CCLK, CTDCD, CTTCT, CTSP, PCSSI
- CNUMF, CNUMS, CNUMD, CTSDC, CTSDS, CTMGS
- CTICN, CTOCP, CTCC, CTCR, CTSDSR
"""

import unittest
import time
from tetra_pei_test.core.radio_connection import RadioConnection
from tetra_pei_test.core.tetra_pei import TetraPEI
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator


class TestNewTetraPEICommands(unittest.TestCase):
    """Test cases for new TETRA PEI commands."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15040,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15040)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_flash_class(self):
        """Test flash class set/get."""
        result = self.pei.set_flash_class(1)
        self.assertTrue(result)
        
        flash_class = self.pei.get_flash_class()
        self.assertIsNotNone(flash_class)
        self.assertIsInstance(flash_class, int)
    
    def test_error_reporting(self):
        """Test error reporting mode set/get."""
        result = self.pei.set_error_reporting(1)
        self.assertTrue(result)
        
        mode = self.pei.get_error_reporting()
        self.assertIsNotNone(mode)
        self.assertIsInstance(mode, int)
    
    def test_clock(self):
        """Test clock set/get."""
        result = self.pei.set_clock("26/02/11,21:00:00+00")
        self.assertTrue(result)
        
        clock = self.pei.get_clock()
        self.assertIsNotNone(clock)
        self.assertIsInstance(clock, str)
    
    def test_dcd_status(self):
        """Test DCD status get."""
        status = self.pei.get_dcd_status()
        self.assertIsNotNone(status)
        self.assertIn(status, [0, 1])
    
    def test_trunked_mode(self):
        """Test trunked/direct mode get."""
        mode = self.pei.get_trunked_mode()
        self.assertIsNotNone(mode)
        self.assertIn('mode', mode)
    
    def test_service_provider(self):
        """Test service provider set/get."""
        result = self.pei.set_service_provider("Test Provider")
        self.assertTrue(result)
        
        provider = self.pei.get_service_provider()
        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, str)
    
    def test_primary_channel(self):
        """Test primary channel get."""
        issi = self.pei.get_primary_channel()
        self.assertIsNotNone(issi)
        self.assertIsInstance(issi, int)
    
    def test_forwarding_number(self):
        """Test forwarding number set/get."""
        result = self.pei.set_forwarding_number("12345")
        self.assertTrue(result)
        
        number = self.pei.get_forwarding_number()
        self.assertIsNotNone(number)
        self.assertIsInstance(number, str)
    
    def test_subscriber_number(self):
        """Test subscriber number get."""
        number = self.pei.get_subscriber_number()
        self.assertIsNotNone(number)
        self.assertIsInstance(number, str)
    
    def test_dialing_number(self):
        """Test dialing number get."""
        number = self.pei.get_dialing_number()
        self.assertIsNotNone(number)
        self.assertIsInstance(number, str)
    
    def test_sds_configuration(self):
        """Test SDS configuration set/get."""
        result = self.pei.set_sds_configuration(1)
        self.assertTrue(result)
        
        config = self.pei.get_sds_configuration()
        self.assertIsNotNone(config)
        self.assertIsInstance(config, int)
    
    def test_sds_status(self):
        """Test SDS status get."""
        status = self.pei.get_sds_status()
        self.assertIsNotNone(status)
        self.assertIn('status', status)
    
    def test_send_message_ctmgs(self):
        """Test message send using CTMGS."""
        result = self.pei.send_message("2001", "Test message", priority=0)
        self.assertTrue(result)


class TestUnsolicitedMessages(unittest.TestCase):
    """Test cases for unsolicited message handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15041,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15041)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_unsolicited_patterns_include_new_commands(self):
        """Test that new unsolicited patterns are registered."""
        patterns = self.pei._unsolicited_patterns
        
        # Check all required unsolicited messages are in patterns
        required_patterns = [
            '+CREG:', '+CTTCT:', '+CNUMS:', '+CNUMD:',
            '+CTGS:', '+CTICN:', '+CTOCP:', '+CTCC:',
            '+CTCR:', '+CTSDSR:'
        ]
        
        for pattern in required_patterns:
            self.assertIn(pattern, patterns, 
                         f"Pattern {pattern} should be in unsolicited patterns")
    
    def test_command_response_map_includes_new_commands(self):
        """Test that new commands are in response map."""
        response_map = self.pei._command_response_map
        
        # Check all commands that can have unsolicited responses
        required_commands = [
            'AT+CREG?', 'AT+CTTCT?', 'AT+CNUMS?', 'AT+CNUMD?',
            'AT+CTGS?', 'AT+CTICN?', 'AT+CTOCP?', 'AT+CTCC?',
            'AT+CTCR?', 'AT+CTSDSR?'
        ]
        
        for cmd in required_commands:
            self.assertIn(cmd, response_map,
                         f"Command {cmd} should be in response map")
    
    def test_check_incoming_call_notification(self):
        """Test checking incoming call notification."""
        # Simulate unsolicited message
        self.pei._unsolicited_messages.append('+CTICN: 1,"2001"')
        
        notification = self.pei.check_incoming_call_notification()
        self.assertIsNotNone(notification)
        self.assertIn('call_type', notification)
        self.assertIn('calling_party', notification)
    
    def test_check_call_progress(self):
        """Test checking call progress."""
        self.pei._unsolicited_messages.append('+CTOCP: 1,"Calling"')
        
        progress = self.pei.check_call_progress()
        self.assertIsNotNone(progress)
        self.assertIn('progress_type', progress)
    
    def test_check_call_connected(self):
        """Test checking call connected."""
        self.pei._unsolicited_messages.append('+CTCC: 1,0')
        
        connected = self.pei.check_call_connected()
        self.assertIsNotNone(connected)
        self.assertIn('call_id', connected)
    
    def test_check_call_released(self):
        """Test checking call released."""
        self.pei._unsolicited_messages.append('+CTCR: 1,0')
        
        released = self.pei.check_call_released()
        self.assertIsNotNone(released)
        self.assertIn('call_id', released)
        self.assertIn('reason', released)
    
    def test_check_sds_report(self):
        """Test checking SDS report."""
        self.pei._unsolicited_messages.append('+CTSDSR: 123,0')
        
        report = self.pei.check_sds_report()
        self.assertIsNotNone(report)
        self.assertIn('message_id', report)
        self.assertIn('status', report)


if __name__ == '__main__':
    unittest.main()
