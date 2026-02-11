"""
TETRA PEI Protocol Handler

Implements TETRA PEI (Peripheral Equipment Interface) protocol using AT commands.
"""

import logging
import re
import time
from typing import Optional, Dict, List, Tuple
from enum import Enum

from .radio_connection import RadioConnection


logger = logging.getLogger(__name__)


class CallType(Enum):
    """Types of TETRA calls."""
    INDIVIDUAL = "individual"
    GROUP = "group"
    EMERGENCY = "emergency"


class PTTState(Enum):
    """Push-to-Talk states."""
    PRESSED = "pressed"
    RELEASED = "released"


class ATCommandResponse(Enum):
    """Valid AT command final responses."""
    OK = "OK"
    ERROR = "ERROR"
    NO_CARRIER = "NO CARRIER"
    NO_DIALTONE = "NO DIALTONE"
    BUSY = "BUSY"
    NO_ANSWER = "NO ANSWER"


class TetraPEI:
    """
    TETRA PEI protocol implementation using AT commands.
    
    This class provides high-level methods for controlling a TETRA radio
    through PEI commands over TCP connection.
    
    Unsolicited Message Handling:
    ==============================
    When sending AT commands, unsolicited messages (like incoming calls, PTT events,
    text messages, etc.) can arrive from the radio at any time, including while
    waiting for a command response. This class automatically filters out unsolicited
    messages from command responses and stores them separately for later retrieval.
    
    Use get_unsolicited_messages() to retrieve stored unsolicited messages.
    
    AT Command Response Handling:
    =============================
    All AT commands return one of the following final responses:
    - OK: Command executed successfully
    - ERROR: Command syntax error or execution failure
    - NO CARRIER: Call disconnected by remote party
    - NO DIALTONE: No network or dial tone available
    - BUSY: Called party is busy
    - NO ANSWER: Called party did not answer
    """
    
    # Valid AT command final response terminators
    VALID_RESPONSE_TERMINATORS = [
        "OK\r\n",
        "ERROR\r\n",
        "NO CARRIER\r\n",
        "NO DIALTONE\r\n",
        "BUSY\r\n",
        "NO ANSWER\r\n"
    ]
    
    def __init__(self, connection: RadioConnection):
        """
        Initialize TETRA PEI handler.
        
        Args:
            connection: RadioConnection instance for this radio
        """
        self.connection = connection
        self.radio_id = connection.radio_id
        self._last_response = ""
        self._last_response_type = None
        self._unsolicited_messages = []
        
        # Patterns that identify unsolicited messages
        # These are messages that appear without being requested
        self._unsolicited_patterns = [
            'RING',       # Incoming call
            '+CLIP:',     # Caller ID (unsolicited)
            '+CTXD:',     # PTT event (unsolicited)
            '+CMTI:',     # New text message notification
            '+CPIN:',     # PTT event alternative
            '+CTSDSI:',   # Status message received (unsolicited)
            '+CREG:',     # Network registration status change (unsolicited)
            '+CMGS:',     # Message send confirmation (can be unsolicited)
        ]
        
        # Mapping of commands to their expected response patterns
        # Only include commands whose response patterns can ALSO appear as unsolicited messages
        # If a response matches both unsolicited pattern AND expected response for current command,
        # it's considered solicited
        self._command_response_map = {
            'AT+CREG?': ['+CREG:'],   # Query registration status
            'AT+COPS?': ['+COPS:'],   # Query operator selection
            'AT+CTXD?': ['+CTXD:'],   # Query PTT status
            'AT+CMGS': ['+CMGS:'],    # Send message (confirmation)
        }
        
        logger.info(f"TetraPEI initialized for radio {self.radio_id}")
    
    def _send_command(self, command: str, wait_for_response: bool = True, 
                     timeout: float = 5.0) -> Tuple[bool, str]:
        """
        Send an AT command and wait for response.
        
        Args:
            command: AT command to send (without CR+LF)
            wait_for_response: Whether to wait for final response
            timeout: Response timeout in seconds
        
        Returns:
            Tuple of (success, response_data)
            
        Notes:
            Success is True for OK response, False for ERROR, NO CARRIER, NO DIALTONE, BUSY, NO ANSWER
        """
        if not self.connection.is_connected():
            logger.error(f"Cannot send command to {self.radio_id}: not connected")
            return False, ""
        
        # Send the command
        if not self.connection.send(command):
            logger.error(f"Failed to send command to {self.radio_id}: {command}")
            return False, ""
        
        if not wait_for_response:
            return True, ""
        
        # Wait for any valid final response
        success, response, matched_terminator = self.connection.receive_until_any(
            self.VALID_RESPONSE_TERMINATORS, timeout
        )
        
        if not success:
            logger.error(f"Timeout waiting for response from {self.radio_id}: {command}")
            self._last_response_type = None
            return False, response
        
        # Determine response type
        response_type = None
        for terminator in self.VALID_RESPONSE_TERMINATORS:
            if matched_terminator == terminator:
                response_type = terminator.strip()
                break
        
        self._last_response_type = response_type
        
        # Filter out unsolicited messages from the response
        filtered_response, unsolicited = self._filter_unsolicited_messages(response, command)
        
        # Store unsolicited messages for later retrieval
        if unsolicited:
            self._unsolicited_messages.extend(unsolicited)
            logger.debug(f"Captured {len(unsolicited)} unsolicited message(s) during command: {command}")
        
        self._last_response = filtered_response
        
        # Determine success based on response type
        is_success = response_type == "OK"
        
        if response_type == "OK":
            logger.debug(f"Command successful for {self.radio_id}: {command}")
        else:
            logger.warning(f"Command returned {response_type} for {self.radio_id}: {command}")
        
        return is_success, filtered_response
    
    def _filter_unsolicited_messages(self, response: str, command: str = "") -> Tuple[str, List[str]]:
        """
        Filter unsolicited messages from a command response.
        
        This method is context-aware: it knows which responses are expected for
        a given command. For example, +CREG: is solicited when responding to AT+CREG?
        but unsolicited when it arrives due to network status change.
        
        Args:
            response: Raw response from radio
            command: The AT command that was sent (used to determine expected responses)
        
        Returns:
            Tuple of (filtered_response, list_of_unsolicited_messages)
        """
        lines = response.split('\r\n')
        filtered_lines = []
        unsolicited = []
        
        # Get expected response patterns for this command
        expected_patterns = self._command_response_map.get(command, [])
        
        for line in lines:
            # Check if this line is an unsolicited message
            is_unsolicited = False
            
            for pattern in self._unsolicited_patterns:
                if pattern in line:
                    # Check if this response is expected for the current command
                    is_expected = False
                    for expected in expected_patterns:
                        if expected in line:
                            is_expected = True
                            break
                    
                    # Only mark as unsolicited if it's not an expected response
                    if not is_expected:
                        is_unsolicited = True
                        unsolicited.append(line)
                        logger.debug(f"Filtered unsolicited message: {line}")
                    else:
                        logger.debug(f"Keeping expected response: {line} for command: {command}")
                    break
            
            # Keep the line if it's not unsolicited
            if not is_unsolicited:
                filtered_lines.append(line)
        
        filtered_response = '\r\n'.join(filtered_lines)
        return filtered_response, unsolicited
    
    def get_unsolicited_messages(self, clear: bool = True) -> List[str]:
        """
        Get stored unsolicited messages.
        
        Args:
            clear: If True, clear the buffer after returning messages
        
        Returns:
            List of unsolicited message strings
        """
        messages = self._unsolicited_messages.copy()
        if clear:
            self._unsolicited_messages.clear()
        return messages
    
    def test_connection(self) -> bool:
        """
        Test the connection with a simple AT command.
        
        Returns:
            True if radio responds correctly, False otherwise
        """
        logger.info(f"Testing connection to {self.radio_id}")
        success, _ = self._send_command("AT")
        return success
    
    def get_radio_info(self) -> Optional[Dict[str, str]]:
        """
        Get radio information (manufacturer, model, version, etc.).
        
        Returns:
            Dictionary with radio info, or None if failed
        """
        info = {}
        
        # Get manufacturer
        success, response = self._send_command("AT+CGMI")
        if success:
            info['manufacturer'] = self._extract_response_value(response)
        
        # Get model
        success, response = self._send_command("AT+CGMM")
        if success:
            info['model'] = self._extract_response_value(response)
        
        # Get revision
        success, response = self._send_command("AT+CGMR")
        if success:
            info['revision'] = self._extract_response_value(response)
        
        # Get IMEI/serial
        success, response = self._send_command("AT+CGSN")
        if success:
            info['serial'] = self._extract_response_value(response)
        
        logger.info(f"Radio {self.radio_id} info: {info}")
        return info if info else None
    
    def register_to_network(self) -> bool:
        """
        Register the radio to the TETRA network.
        
        Returns:
            True if registration successful, False otherwise
        """
        logger.info(f"Registering {self.radio_id} to network")
        success, _ = self._send_command("AT+COPS=0", timeout=30.0)
        
        if success:
            # Wait a bit for registration to complete
            time.sleep(2)
            # Check registration status
            return self.check_registration_status()
        
        return False
    
    def check_registration_status(self) -> bool:
        """
        Check if radio is registered to the network.
        
        Returns:
            True if registered, False otherwise
        """
        success, response = self._send_command("AT+CREG?")
        if success:
            # Parse response: +CREG: <n>,<stat>
            # stat: 0=not registered, 1=registered home, 5=registered roaming
            match = re.search(r'\+CREG:\s*\d+,(\d+)', response)
            if match:
                status = int(match.group(1))
                registered = status in [1, 5]
                logger.info(f"Radio {self.radio_id} registration status: {status} ({'registered' if registered else 'not registered'})")
                return registered
        
        return False
    
    def make_individual_call(self, target_issi: str) -> bool:
        """
        Make an individual call to another radio.
        
        Args:
            target_issi: ISSI (Individual Short Subscriber Identity) of target radio
        
        Returns:
            True if call initiated successfully, False otherwise
        """
        logger.info(f"Radio {self.radio_id} making individual call to {target_issi}")
        success, _ = self._send_command(f"ATD{target_issi};", timeout=10.0)
        return success
    
    def make_group_call(self, group_id: str) -> bool:
        """
        Make a group call.
        
        Args:
            group_id: Group GSSI (Group Short Subscriber Identity)
        
        Returns:
            True if call initiated successfully, False otherwise
        """
        logger.info(f"Radio {self.radio_id} making group call to group {group_id}")
        success, _ = self._send_command(f"ATD{group_id}#", timeout=10.0)
        return success
    
    def answer_call(self) -> bool:
        """
        Answer an incoming call.
        
        Returns:
            True if call answered successfully, False otherwise
        """
        logger.info(f"Radio {self.radio_id} answering call")
        success, _ = self._send_command("ATA")
        return success
    
    def end_call(self) -> bool:
        """
        End the current call.
        
        Returns:
            True if call ended successfully, False otherwise
        """
        logger.info(f"Radio {self.radio_id} ending call")
        success, _ = self._send_command("ATH")
        return success
    
    def press_ptt(self) -> bool:
        """
        Press PTT (Push-To-Talk) button to start transmitting.
        
        Returns:
            True if PTT pressed successfully, False otherwise
        """
        logger.info(f"Radio {self.radio_id} pressing PTT")
        success, _ = self._send_command("AT+CTXD=1")
        return success
    
    def release_ptt(self) -> bool:
        """
        Release PTT button to stop transmitting.
        
        Returns:
            True if PTT released successfully, False otherwise
        """
        logger.info(f"Radio {self.radio_id} releasing PTT")
        success, _ = self._send_command("AT+CTXD=0")
        return success
    
    def join_group(self, group_id: str) -> bool:
        """
        Join a talkgroup.
        
        Args:
            group_id: Group GSSI to join
        
        Returns:
            True if joined successfully, False otherwise
        """
        logger.info(f"Radio {self.radio_id} joining group {group_id}")
        success, _ = self._send_command(f"AT+CTGS={group_id}")
        return success
    
    def leave_group(self, group_id: str) -> bool:
        """
        Leave a talkgroup.
        
        Args:
            group_id: Group GSSI to leave
        
        Returns:
            True if left successfully, False otherwise
        """
        logger.info(f"Radio {self.radio_id} leaving group {group_id}")
        success, _ = self._send_command(f"AT+CTGL={group_id}")
        return success
    
    def send_status_message(self, target: str, status_value: int) -> bool:
        """
        Send a status message.
        
        Args:
            target: Target ISSI or GSSI
            status_value: Status value to send (0-65535)
        
        Returns:
            True if sent successfully, False otherwise
        """
        logger.info(f"Radio {self.radio_id} sending status {status_value} to {target}")
        success, _ = self._send_command(f"AT+CTSDSR={target},{status_value}")
        return success
    
    def send_text_message(self, target: str, message: str, is_group: bool = False) -> bool:
        """
        Send a text (SDS) message.
        
        Args:
            target: Target ISSI or GSSI
            message: Text message content
            is_group: True if sending to group, False for individual
        
        Returns:
            True if sent successfully, False otherwise
        """
        logger.info(f"Radio {self.radio_id} sending text message to {target}: {message}")
        
        # Escape message if needed
        escaped_message = message.replace('"', '\\"')
        
        # Different command format for group vs individual
        if is_group:
            success, _ = self._send_command(f'AT+CMGS="{target}#","{escaped_message}"')
        else:
            success, _ = self._send_command(f'AT+CMGS="{target}","{escaped_message}"')
        
        return success
    
    def check_for_incoming_call(self, timeout: float = 1.0) -> Optional[str]:
        """
        Check for incoming call notification.
        
        Args:
            timeout: How long to wait for notification
        
        Returns:
            Caller ID if call detected, None otherwise
        """
        data = self.connection.receive(timeout=timeout)
        if data and "RING" in data:
            # Try to extract caller ID: +CLIP: "caller_id"
            match = re.search(r'\+CLIP:\s*"([^"]+)"', data)
            if match:
                caller_id = match.group(1)
                logger.info(f"Radio {self.radio_id} received call from {caller_id}")
                return caller_id
            logger.info(f"Radio {self.radio_id} received call (no caller ID)")
            return "UNKNOWN"
        return None
    
    def check_for_ptt_event(self, timeout: float = 1.0) -> Optional[PTTState]:
        """
        Check for PTT event notification.
        
        Args:
            timeout: How long to wait for notification
        
        Returns:
            PTTState if PTT event detected, None otherwise
        """
        data = self.connection.receive(timeout=timeout)
        if data:
            if "+CTXD: 1" in data or "+CPIN: 1" in data:
                logger.info(f"Radio {self.radio_id} detected PTT pressed")
                return PTTState.PRESSED
            elif "+CTXD: 0" in data or "+CPIN: 0" in data:
                logger.info(f"Radio {self.radio_id} detected PTT released")
                return PTTState.RELEASED
        return None
    
    def check_for_text_message(self, timeout: float = 1.0) -> Optional[Dict[str, str]]:
        """
        Check for incoming text message.
        
        Args:
            timeout: How long to wait for message
        
        Returns:
            Dictionary with message details if received, None otherwise
        """
        data = self.connection.receive(timeout=timeout)
        if data and "+CMTI:" in data:
            # Message received notification: +CMTI: "SM",<index>
            # We would need to read the message with AT+CMGR=<index>
            logger.info(f"Radio {self.radio_id} received text message notification")
            return {"sender": "UNKNOWN", "message": "Message received", "raw": data}
        return None
    
    def enable_unsolicited_notifications(self) -> bool:
        """
        Enable unsolicited result codes for events.
        
        Returns:
            True if enabled successfully, False otherwise
        """
        logger.info(f"Enabling notifications for {self.radio_id}")
        
        # Enable various notifications
        commands = [
            "AT+CLIP=1",  # Calling line identification
            "AT+CRC=1",   # Extended format for incoming call indication
            "AT+CNMI=2,1",  # New message indications
        ]
        
        for cmd in commands:
            success, _ = self._send_command(cmd)
            if not success:
                return False
        
        return True
    
    def _extract_response_value(self, response: str) -> str:
        """
        Extract value from AT command response.
        
        Args:
            response: Full response string
        
        Returns:
            Extracted value (first non-empty line before OK)
        """
        lines = response.split('\r\n')
        for line in lines:
            line = line.strip()
            if line and line != 'OK' and not line.startswith('AT'):
                return line
        return ""
    
    def get_last_response(self) -> str:
        """Get the last response received from the radio."""
        return self._last_response
    
    def get_last_response_type(self) -> Optional[str]:
        """
        Get the type of the last response received from the radio.
        
        Returns:
            One of: "OK", "ERROR", "NO CARRIER", "NO DIALTONE", "BUSY", "NO ANSWER", or None
        """
        return self._last_response_type
