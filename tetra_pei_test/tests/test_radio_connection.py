"""
Unit tests for RadioConnection class.
"""

import unittest
import time
import threading
from tetra_pei_test.core.radio_connection import RadioConnection
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator


class TestRadioConnection(unittest.TestCase):
    """Test cases for RadioConnection class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Start a simulator
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15000,
            issi="9999"
        )
        self.simulator.start()
        time.sleep(0.5)  # Give simulator time to start
        
        # Create connection
        self.connection = RadioConnection(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15000,
            timeout=5.0
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_connect_success(self):
        """Test successful connection."""
        result = self.connection.connect()
        self.assertTrue(result)
        self.assertTrue(self.connection.is_connected())
    
    def test_connect_already_connected(self):
        """Test connecting when already connected."""
        self.connection.connect()
        result = self.connection.connect()
        self.assertTrue(result)
    
    def test_disconnect(self):
        """Test disconnection."""
        self.connection.connect()
        self.connection.disconnect()
        self.assertFalse(self.connection.is_connected())
    
    def test_send_receive(self):
        """Test sending and receiving data."""
        self.connection.connect()
        
        # Send AT command
        self.assertTrue(self.connection.send("AT"))
        
        # Receive response
        time.sleep(0.1)
        response = self.connection.receive(timeout=2.0)
        self.assertIsNotNone(response)
        self.assertIn("OK", response)
    
    def test_receive_until(self):
        """Test receive_until method."""
        self.connection.connect()
        
        self.connection.send("AT")
        success, data = self.connection.receive_until("OK\r\n", timeout=3.0)
        
        self.assertTrue(success)
        self.assertIn("OK", data)
    
    def test_send_when_not_connected(self):
        """Test sending when not connected."""
        result = self.connection.send("AT")
        self.assertFalse(result)
    
    def test_receive_when_not_connected(self):
        """Test receiving when not connected."""
        result = self.connection.receive()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
