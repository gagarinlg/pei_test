"""
Unit tests for TetraPEI class.
"""

import unittest
import time
from tetra_pei_test.core.radio_connection import RadioConnection
from tetra_pei_test.core.tetra_pei import TetraPEI
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator


class TestTetraPEI(unittest.TestCase):
    """Test cases for TetraPEI class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Start simulator
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15001,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        # Create connection and PEI
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15001)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_test_connection(self):
        """Test basic AT command."""
        result = self.pei.test_connection()
        self.assertTrue(result)
    
    def test_get_radio_info(self):
        """Test getting radio information."""
        info = self.pei.get_radio_info()
        self.assertIsNotNone(info)
        self.assertIn('manufacturer', info)
        self.assertIn('model', info)
        self.assertEqual(info['manufacturer'], 'SimulatedTetraRadio')
    
    def test_register_to_network(self):
        """Test network registration."""
        result = self.pei.register_to_network()
        # Simulator auto-registers
        self.assertTrue(result)
    
    def test_check_registration_status(self):
        """Test checking registration status."""
        self.simulator.registered = True
        result = self.pei.check_registration_status()
        self.assertTrue(result)
    
    def test_make_individual_call(self):
        """Test making individual call."""
        result = self.pei.make_individual_call("2001")
        self.assertTrue(result)
    
    def test_make_group_call(self):
        """Test making group call."""
        result = self.pei.make_group_call("9001")
        self.assertTrue(result)
    
    def test_answer_call(self):
        """Test answering call."""
        result = self.pei.answer_call()
        self.assertTrue(result)
    
    def test_end_call(self):
        """Test ending call."""
        result = self.pei.end_call()
        self.assertTrue(result)
    
    def test_press_release_ptt(self):
        """Test PTT press and release."""
        result = self.pei.press_ptt()
        self.assertTrue(result)
        
        result = self.pei.release_ptt()
        self.assertTrue(result)
    
    def test_join_leave_group(self):
        """Test joining and leaving group."""
        result = self.pei.join_group("9001")
        self.assertTrue(result)
        self.assertIn("9001", self.simulator.joined_groups)
        
        result = self.pei.leave_group("9001")
        self.assertTrue(result)
        self.assertNotIn("9001", self.simulator.joined_groups)
    
    def test_send_status_message(self):
        """Test sending status message."""
        result = self.pei.send_status_message("2001", 12345)
        self.assertTrue(result)
    
    def test_send_text_message(self):
        """Test sending text message."""
        result = self.pei.send_text_message("2001", "Test message")
        self.assertTrue(result)
    
    def test_enable_unsolicited_notifications(self):
        """Test enabling notifications."""
        result = self.pei.enable_unsolicited_notifications()
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
