"""
Unit tests for advanced TETRA PEI commands.

Tests emergency calls, encryption, volume control, network operations, etc.
"""

import unittest
import time
from tetra_pei_test.core.radio_connection import RadioConnection
from tetra_pei_test.core.tetra_pei import TetraPEI
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator


class TestEmergencyCalls(unittest.TestCase):
    """Test cases for emergency call functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15030,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15030)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_emergency_individual_call(self):
        """Test making an emergency individual call."""
        result = self.pei.make_individual_call("2001", emergency=True)
        self.assertTrue(result)
        self.assertEqual(self.pei.get_last_response_type(), "OK")
    
    def test_emergency_group_call(self):
        """Test making an emergency group call."""
        result = self.pei.make_group_call("9001", emergency=True)
        self.assertTrue(result)
        self.assertEqual(self.pei.get_last_response_type(), "OK")
    
    def test_normal_vs_emergency_call(self):
        """Test difference between normal and emergency calls."""
        # Normal call
        result1 = self.pei.make_individual_call("2001", emergency=False)
        self.assertTrue(result1)
        self.pei.end_call()
        time.sleep(0.5)
        
        # Emergency call
        result2 = self.pei.make_individual_call("2001", emergency=True)
        self.assertTrue(result2)
        self.pei.end_call()


class TestAudioControl(unittest.TestCase):
    """Test cases for audio control functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15031,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15031)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_set_audio_volume(self):
        """Test setting audio volume."""
        result = self.pei.set_audio_volume(75)
        self.assertTrue(result)
    
    def test_set_audio_volume_invalid(self):
        """Test setting invalid audio volume."""
        result = self.pei.set_audio_volume(150)
        self.assertFalse(result)
    
    def test_get_audio_volume(self):
        """Test getting audio volume."""
        volume = self.pei.get_audio_volume()
        self.assertIsNotNone(volume)
        self.assertGreaterEqual(volume, 0)
        self.assertLessEqual(volume, 100)


class TestEncryption(unittest.TestCase):
    """Test cases for encryption functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15032,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15032)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_enable_encryption(self):
        """Test enabling encryption."""
        result = self.pei.enable_encryption(key_id=1)
        self.assertTrue(result)
    
    def test_disable_encryption(self):
        """Test disabling encryption."""
        result = self.pei.disable_encryption()
        self.assertTrue(result)
    
    def test_get_encryption_status(self):
        """Test getting encryption status."""
        status = self.pei.get_encryption_status()
        self.assertIsNotNone(status)
        self.assertIn('enabled', status)
        self.assertIn('mode', status)
        self.assertIn('key_id', status)


class TestNetworkOperations(unittest.TestCase):
    """Test cases for network operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15033,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15033)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_get_signal_strength(self):
        """Test getting signal strength."""
        rssi = self.pei.get_signal_strength()
        self.assertIsNotNone(rssi)
        self.assertGreaterEqual(rssi, 0)
        self.assertLessEqual(rssi, 99)
    
    def test_attach_to_network(self):
        """Test attaching to network."""
        result = self.pei.attach_to_network()
        self.assertTrue(result)
    
    def test_detach_from_network(self):
        """Test detaching from network."""
        result = self.pei.detach_from_network()
        self.assertTrue(result)
    
    def test_get_network_attachment_status(self):
        """Test getting network attachment status."""
        status = self.pei.get_network_attachment_status()
        self.assertIsNotNone(status)
        self.assertIsInstance(status, bool)


class TestMessageOperations(unittest.TestCase):
    """Test cases for message operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15034,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15034)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_send_text_message_normal_priority(self):
        """Test sending text message with normal priority."""
        result = self.pei.send_text_message("2001", "Test message", priority=0)
        self.assertTrue(result)
    
    def test_send_text_message_high_priority(self):
        """Test sending text message with high priority."""
        result = self.pei.send_text_message("2001", "Urgent message", priority=1)
        self.assertTrue(result)
    
    def test_send_text_message_emergency_priority(self):
        """Test sending text message with emergency priority."""
        result = self.pei.send_text_message("2001", "Emergency message", priority=2)
        self.assertTrue(result)
    
    def test_read_sds_message(self):
        """Test reading SDS message."""
        message = self.pei.read_sds_message(1)
        self.assertIsNotNone(message)
        self.assertIn('index', message)
    
    def test_delete_sds_message(self):
        """Test deleting SDS message."""
        result = self.pei.delete_sds_message(1)
        self.assertTrue(result)


class TestAdvancedFeatures(unittest.TestCase):
    """Test cases for advanced features."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15035,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15035)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_set_operating_mode_tmo(self):
        """Test setting TMO operating mode."""
        result = self.pei.set_operating_mode('TMO')
        self.assertTrue(result)
    
    def test_set_operating_mode_dmo(self):
        """Test setting DMO operating mode."""
        result = self.pei.set_operating_mode('DMO')
        self.assertTrue(result)
    
    def test_set_operating_mode_invalid(self):
        """Test setting invalid operating mode."""
        result = self.pei.set_operating_mode('INVALID')
        self.assertFalse(result)
    
    def test_send_location_info(self):
        """Test sending location information."""
        result = self.pei.send_location_info(51.5074, -0.1278)
        self.assertTrue(result)
    
    def test_set_ambient_listening_enable(self):
        """Test enabling ambient listening."""
        result = self.pei.set_ambient_listening(True)
        self.assertTrue(result)
    
    def test_set_ambient_listening_disable(self):
        """Test disabling ambient listening."""
        result = self.pei.set_ambient_listening(False)
        self.assertTrue(result)
    
    def test_set_dgna_mode(self):
        """Test setting DGNA mode."""
        result = self.pei.set_dgna_mode(1)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
