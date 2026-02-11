"""
Radio Connection Handler

Manages TCP connections to TETRA radios and handles low-level communication.
"""

import socket
import logging
import time
from typing import Optional, Tuple
from threading import Lock


logger = logging.getLogger(__name__)


class RadioConnection:
    """
    Handles TCP connection to a single TETRA radio.
    
    This class manages the low-level TCP communication with a TETRA radio,
    including connection establishment, data sending/receiving, and error handling.
    """
    
    def __init__(self, radio_id: str, host: str, port: int, timeout: float = 5.0):
        """
        Initialize a radio connection.
        
        Args:
            radio_id: Unique identifier for this radio
            host: IP address or hostname of the radio
            port: TCP port number
            timeout: Socket timeout in seconds
        """
        self.radio_id = radio_id
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self._lock = Lock()
        
        logger.info(f"RadioConnection initialized for {radio_id} at {host}:{port}")
    
    def connect(self) -> bool:
        """
        Establish TCP connection to the radio.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self._lock:
                if self.connected:
                    logger.warning(f"Radio {self.radio_id} already connected")
                    return True
                
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(self.timeout)
                self.socket.connect((self.host, self.port))
                self.connected = True
                
                logger.info(f"Successfully connected to radio {self.radio_id}")
                return True
                
        except socket.timeout:
            logger.error(f"Timeout connecting to radio {self.radio_id} at {self.host}:{self.port}")
            return False
        except socket.error as e:
            logger.error(f"Socket error connecting to radio {self.radio_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to radio {self.radio_id}: {e}")
            return False
    
    def disconnect(self) -> None:
        """Close the TCP connection to the radio."""
        try:
            with self._lock:
                if self.socket:
                    self.socket.close()
                    self.socket = None
                self.connected = False
                logger.info(f"Disconnected from radio {self.radio_id}")
        except Exception as e:
            logger.error(f"Error disconnecting from radio {self.radio_id}: {e}")
    
    def send(self, data: str) -> bool:
        """
        Send data to the radio.
        
        Args:
            data: String data to send (will be encoded to bytes)
        
        Returns:
            True if send successful, False otherwise
        """
        if not self.connected or not self.socket:
            logger.error(f"Cannot send: radio {self.radio_id} not connected")
            return False
        
        try:
            # Ensure data ends with CR+LF as per AT command standard
            if not data.endswith('\r\n'):
                data += '\r\n'
            
            with self._lock:
                self.socket.sendall(data.encode('utf-8'))
            
            logger.debug(f"Sent to {self.radio_id}: {data.strip()}")
            return True
            
        except socket.timeout:
            logger.error(f"Timeout sending data to radio {self.radio_id}")
            return False
        except socket.error as e:
            logger.error(f"Socket error sending to radio {self.radio_id}: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending to radio {self.radio_id}: {e}")
            return False
    
    def receive(self, buffer_size: int = 4096, timeout: Optional[float] = None) -> Optional[str]:
        """
        Receive data from the radio.
        
        Args:
            buffer_size: Maximum number of bytes to receive
            timeout: Optional timeout override for this receive operation
        
        Returns:
            Received data as string, or None if error/timeout
        """
        if not self.connected or not self.socket:
            logger.error(f"Cannot receive: radio {self.radio_id} not connected")
            return None
        
        try:
            # Temporarily change timeout if specified
            original_timeout = None
            if timeout is not None:
                original_timeout = self.socket.gettimeout()
                self.socket.settimeout(timeout)
            
            with self._lock:
                data = self.socket.recv(buffer_size)
            
            # Restore original timeout
            if original_timeout is not None:
                self.socket.settimeout(original_timeout)
            
            if not data:
                logger.warning(f"Connection closed by radio {self.radio_id}")
                self.connected = False
                return None
            
            decoded_data = data.decode('utf-8', errors='replace')
            logger.debug(f"Received from {self.radio_id}: {decoded_data.strip()}")
            return decoded_data
            
        except socket.timeout:
            logger.debug(f"Timeout receiving from radio {self.radio_id}")
            return None
        except socket.error as e:
            logger.error(f"Socket error receiving from radio {self.radio_id}: {e}")
            self.connected = False
            return None
        except Exception as e:
            logger.error(f"Unexpected error receiving from radio {self.radio_id}: {e}")
            return None
    
    def receive_until(self, terminator: str = "OK\r\n", timeout: float = 5.0) -> Tuple[bool, str]:
        """
        Receive data until a terminator string is found or timeout.
        
        Args:
            terminator: String to wait for (e.g., "OK\r\n", "ERROR\r\n")
            timeout: Maximum time to wait in seconds
        
        Returns:
            Tuple of (success, accumulated_data)
        """
        accumulated = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            remaining_timeout = timeout - (time.time() - start_time)
            data = self.receive(timeout=min(remaining_timeout, 1.0))
            
            if data:
                accumulated += data
                if terminator in accumulated:
                    logger.debug(f"Found terminator '{terminator}' for {self.radio_id}")
                    return True, accumulated
            
            # Small sleep to prevent busy waiting
            time.sleep(0.01)
        
        logger.debug(f"Timeout waiting for '{terminator}' from {self.radio_id}")
        return False, accumulated
    
    def receive_until_any(self, terminators: list, timeout: float = 5.0) -> Tuple[bool, str, str]:
        """
        Receive data until any of the terminator strings is found or timeout.
        
        Valid AT command final responses are:
        - OK
        - ERROR
        - NO CARRIER
        - NO DIALTONE
        - BUSY
        - NO ANSWER
        
        Args:
            terminators: List of terminator strings to wait for
            timeout: Maximum time to wait in seconds
        
        Returns:
            Tuple of (success, accumulated_data, matched_terminator)
        """
        accumulated = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            remaining_timeout = timeout - (time.time() - start_time)
            data = self.receive(timeout=min(remaining_timeout, 1.0))
            
            if data:
                accumulated += data
                # Check for any terminator
                for terminator in terminators:
                    if terminator in accumulated:
                        logger.debug(f"Found terminator '{terminator}' for {self.radio_id}")
                        return True, accumulated, terminator
            
            # Small sleep to prevent busy waiting
            time.sleep(0.01)
        
        logger.debug(f"Timeout waiting for any of {terminators} from {self.radio_id}")
        return False, accumulated, ""
    
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self.connected
    
    def __repr__(self) -> str:
        """String representation of the connection."""
        status = "connected" if self.connected else "disconnected"
        return f"RadioConnection({self.radio_id}, {self.host}:{self.port}, {status})"
