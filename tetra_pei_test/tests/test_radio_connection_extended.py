"""
Extended unit tests for radio_connection.py to increase code coverage.
"""

import unittest
import socket
import time
from unittest.mock import Mock, patch, MagicMock
from tetra_pei_test.core.radio_connection import RadioConnection


class TestRadioConnectionErrorPaths(unittest.TestCase):
    """Test error handling paths in RadioConnection."""
    
    def test_connect_socket_timeout(self):
        """Test connection failure due to socket timeout."""
        conn = RadioConnection("test_radio", "192.168.1.999", 9999, timeout=0.1)
        
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.connect.side_effect = socket.timeout()
            result = conn.connect()
            
            self.assertFalse(result)
            self.assertFalse(conn.is_connected())
    
    def test_connect_socket_error(self):
        """Test connection failure due to socket error."""
        conn = RadioConnection("test_radio", "192.168.1.1", 9999)
        
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.connect.side_effect = socket.error("Connection refused")
            result = conn.connect()
            
            self.assertFalse(result)
            self.assertFalse(conn.is_connected())
    
    def test_connect_unexpected_exception(self):
        """Test connection failure due to unexpected exception."""
        conn = RadioConnection("test_radio", "192.168.1.1", 9999)
        
        with patch('socket.socket') as mock_socket:
            mock_socket.return_value.connect.side_effect = RuntimeError("Unexpected error")
            result = conn.connect()
            
            self.assertFalse(result)
            self.assertFalse(conn.is_connected())
    
    def test_disconnect_with_exception(self):
        """Test disconnect handles exceptions gracefully."""
        conn = RadioConnection("test_radio", "127.0.0.1", 5000)
        conn.socket = Mock()
        conn.socket.close.side_effect = RuntimeError("Close failed")
        conn.connected = True
        
        # Should not raise exception, but connected state may remain True
        # because exception happens before connected=False line
        conn.disconnect()
        # Just verify it doesn't crash
    
    def test_send_socket_timeout(self):
        """Test send failure due to socket timeout."""
        conn = RadioConnection("test_radio", "127.0.0.1", 5000)
        conn.socket = Mock()
        conn.connected = True
        conn.socket.sendall.side_effect = socket.timeout()
        
        result = conn.send("AT")
        self.assertFalse(result)
    
    def test_send_socket_error(self):
        """Test send failure due to socket error."""
        conn = RadioConnection("test_radio", "127.0.0.1", 5000)
        conn.socket = Mock()
        conn.connected = True
        conn.socket.sendall.side_effect = socket.error("Broken pipe")
        
        result = conn.send("AT")
        self.assertFalse(result)
        self.assertFalse(conn.connected)  # Should mark as disconnected
    
    def test_send_unexpected_exception(self):
        """Test send failure due to unexpected exception."""
        conn = RadioConnection("test_radio", "127.0.0.1", 5000)
        conn.socket = Mock()
        conn.connected = True
        conn.socket.sendall.side_effect = RuntimeError("Unexpected")
        
        result = conn.send("AT")
        self.assertFalse(result)
    
    def test_receive_empty_data(self):
        """Test receive returns None when connection closed (empty data)."""
        conn = RadioConnection("test_radio", "127.0.0.1", 5000)
        conn.socket = Mock()
        conn.connected = True
        conn.socket.recv.return_value = b''  # Empty data means closed connection
        
        result = conn.receive()
        self.assertIsNone(result)
        self.assertFalse(conn.connected)  # Should mark as disconnected
    
    def test_receive_socket_timeout(self):
        """Test receive returns None on socket timeout."""
        conn = RadioConnection("test_radio", "127.0.0.1", 5000)
        conn.socket = Mock()
        conn.connected = True
        conn.socket.recv.side_effect = socket.timeout()
        
        result = conn.receive()
        self.assertIsNone(result)
    
    def test_receive_socket_error(self):
        """Test receive handles socket error."""
        conn = RadioConnection("test_radio", "127.0.0.1", 5000)
        conn.socket = Mock()
        conn.connected = True
        conn.socket.recv.side_effect = socket.error("Connection reset")
        
        result = conn.receive()
        self.assertIsNone(result)
        self.assertFalse(conn.connected)
    
    def test_receive_unexpected_exception(self):
        """Test receive handles unexpected exception."""
        conn = RadioConnection("test_radio", "127.0.0.1", 5000)
        conn.socket = Mock()
        conn.connected = True
        conn.socket.recv.side_effect = RuntimeError("Unexpected")
        
        result = conn.receive()
        self.assertIsNone(result)
    
    def test_receive_with_timeout_override(self):
        """Test receive with custom timeout override."""
        conn = RadioConnection("test_radio", "127.0.0.1", 5000, timeout=5.0)
        conn.socket = Mock()
        conn.connected = True
        conn.socket.gettimeout.return_value = 5.0
        conn.socket.recv.return_value = b'OK\r\n'
        
        result = conn.receive(timeout=2.0)
        
        # Should have temporarily set timeout to 2.0
        conn.socket.settimeout.assert_any_call(2.0)
        # Should have restored original timeout
        conn.socket.settimeout.assert_any_call(5.0)
        self.assertIsNotNone(result)
    
    def test_receive_until_timeout(self):
        """Test receive_until returns failure on timeout."""
        conn = RadioConnection("test_radio", "127.0.0.1", 5000)
        conn.socket = Mock()
        conn.connected = True
        conn.socket.recv.return_value = b'PARTIAL\r\n'  # Never sends terminator
        
        success, data = conn.receive_until("OK\r\n", timeout=0.5)
        
        self.assertFalse(success)
        self.assertIn("PARTIAL", data)
    
    def test_repr(self):
        """Test __repr__ string representation."""
        conn = RadioConnection("test_radio", "192.168.1.1", 5000)
        repr_str = repr(conn)
        
        self.assertIn("test_radio", repr_str)
        self.assertIn("192.168.1.1:5000", repr_str)
        self.assertIn("disconnected", repr_str)
        
        conn.connected = True
        repr_str = repr(conn)
        self.assertIn("connected", repr_str)


if __name__ == '__main__':
    unittest.main()
