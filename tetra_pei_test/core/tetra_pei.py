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
from .at_state_machine import ATCommandStateMachine, ATParserState


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
        self._unsolicited_callback = None  # Optional callback for real-time unsolicited messages
        
        # Pre-compute the set of final response terminators (stripped)
        self._final_terminators = {t.strip() for t in self.VALID_RESPONSE_TERMINATORS}
        
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
            '+CTTCT:',    # Trunked/Direct mode change notification
            '+CNUMS:',    # Static identities notification
            '+CNUMD:',    # Dynamic identities notification
            '+CTGS:',     # Group selection notification
            '+CTICN:',    # Incoming call notification
            '+CTOCP:',    # Outgoing call progress
            '+CTCC:',     # Call connected notification
            '+CTCR:',     # Call released notification
            '+CTSDSR:',   # SDS report notification
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
            'AT+CTTCT?': ['+CTTCT:'], # Query trunked/direct mode
            'AT+CNUMS?': ['+CNUMS:'], # Query subscriber number
            'AT+CNUMD?': ['+CNUMD:'], # Query dialing number
            'AT+CTGS?': ['+CTGS:'],   # Query group selection
            'AT+CTICN?': ['+CTICN:'], # Query incoming call
            'AT+CTOCP?': ['+CTOCP:'], # Query call progress
            'AT+CTCC?': ['+CTCC:'],   # Query call connected
            'AT+CTCR?': ['+CTCR:'],   # Query call released
            'AT+CTSDSR?': ['+CTSDSR:'], # Query SDS report
        }
        
        logger.info(f"TetraPEI initialized for radio {self.radio_id}")
    
    def _send_command(self, command: str, wait_for_response: bool = True, 
                     timeout: float = 5.0) -> Tuple[bool, str]:
        """
        Send an AT command and wait for response.
        
        Parses the response buffer line by line, immediately handling any
        unsolicited messages as they arrive (storing them and invoking the
        callback) so that they are available before the final response.
        
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
        
        # Use the state machine to parse the response
        sm = ATCommandStateMachine(
            self._unsolicited_patterns,
            self._command_response_map,
            self._unsolicited_callback,
        )
        sm.start(command)

        start_time = time.time()
        while not sm.is_done():
            remaining = timeout - (time.time() - start_time)
            if remaining <= 0:
                sm.timeout()
                break
            line = self.connection.readline(timeout=remaining)
            if line is None:
                sm.timeout()
                break
            sm.process_line(line)

        # Drain any buffered data after the final response
        self._drain_buffered_unsolicited()

        # Merge unsolicited messages from the state machine into our buffer
        self._unsolicited_messages.extend(sm.get_unsolicited_messages())

        self._last_response_type = sm.final_response
        filtered = sm.build_response()
        self._last_response = filtered

        if sm.state == ATParserState.TIMEOUT:
            logger.error(f"Timeout waiting for response from {self.radio_id}: {command}")
            return False, filtered

        is_success = sm.is_success()
        if is_success:
            logger.debug(f"Command successful for {self.radio_id}: {command}")
        else:
            logger.warning(f"Command returned {sm.final_response} for {self.radio_id}: {command}")

        return is_success, filtered
    
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
    
    def _handle_line_if_unsolicited(self, line: str, expected_patterns: List[str]) -> bool:
        """
        Check if a line is an unsolicited message and handle it immediately.
        
        If the line matches a known unsolicited pattern and is not an expected
        response for the current command, it is stored and the callback is invoked.
        
        Args:
            line: Stripped line to check
            expected_patterns: Expected response patterns for the current command
        
        Returns:
            True if the line was unsolicited and handled, False otherwise
        """
        for pattern in self._unsolicited_patterns:
            if pattern in line:
                # Check if this response is expected for the current command
                is_expected = any(exp in line for exp in expected_patterns)
                if not is_expected:
                    self._unsolicited_messages.append(line)
                    logger.debug(f"Filtered unsolicited message: {line}")
                    if self._unsolicited_callback:
                        try:
                            self._unsolicited_callback(line)
                        except Exception as e:
                            logger.error(f"Error in unsolicited message callback: {e}")
                    return True
                else:
                    logger.debug(f"Keeping expected response: {line}")
                break
        return False
    
    def _drain_buffered_unsolicited(self) -> None:
        """
        Process any complete lines remaining in the connection buffer
        after a final command response has been received.
        
        All data after the final response is treated as unsolicited since
        it was not part of the command/response exchange.
        """
        buffered_lines = self.connection.drain_buffer()
        for line_with_crlf in buffered_lines:
            stripped = line_with_crlf.strip()
            if not stripped:
                continue
            # Everything after the final response is unsolicited
            self._unsolicited_messages.append(stripped)
            logger.debug(f"Captured post-response unsolicited data: {stripped}")
            if self._unsolicited_callback:
                try:
                    self._unsolicited_callback(stripped)
                except Exception as e:
                    logger.error(f"Error in unsolicited message callback: {e}")
    
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
    
    def set_unsolicited_callback(self, callback) -> None:
        """
        Set a callback function to be called when unsolicited messages are received.
        
        The callback will be invoked immediately when an unsolicited message is received
        during command execution, allowing real-time processing of unsolicited events
        (like incoming calls, PTT events, etc.) without waiting for the command to complete.
        
        Args:
            callback: A callable that takes one argument (the unsolicited message string).
                     Set to None to remove the callback.
        
        Example:
            def handle_unsolicited(message):
                if 'RING' in message:
                    print("Incoming call!")
                elif '+CTXD:' in message:
                    print(f"PTT event: {message}")
            
            pei.set_unsolicited_callback(handle_unsolicited)
            # Now handle_unsolicited will be called for each unsolicited message
            
            # To remove the callback:
            pei.set_unsolicited_callback(None)
        """
        self._unsolicited_callback = callback
        logger.info(f"Unsolicited callback {'set' if callback else 'cleared'} for {self.radio_id}")
    
    def clear_unsolicited_messages(self) -> None:
        """
        Clear the stored unsolicited messages buffer.
        
        This can be useful to start fresh before running a series of commands,
        ensuring you only see new unsolicited messages.
        """
        count = len(self._unsolicited_messages)
        self._unsolicited_messages.clear()
        logger.debug(f"Cleared {count} unsolicited message(s) from buffer for {self.radio_id}")
    
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
    
    def make_individual_call(self, target_issi: str, emergency: bool = False) -> bool:
        """
        Make an individual call to another radio.
        
        Args:
            target_issi: ISSI (Individual Short Subscriber Identity) of target radio
            emergency: If True, make an emergency call
        
        Returns:
            True if call initiated successfully, False otherwise
        """
        if emergency:
            logger.info(f"Radio {self.radio_id} making EMERGENCY individual call to {target_issi}")
            # Emergency call uses ! suffix
            success, _ = self._send_command(f"ATD{target_issi}!;", timeout=10.0)
        else:
            logger.info(f"Radio {self.radio_id} making individual call to {target_issi}")
            success, _ = self._send_command(f"ATD{target_issi};", timeout=10.0)
        return success
    
    def make_group_call(self, group_id: str, emergency: bool = False) -> bool:
        """
        Make a group call.
        
        Args:
            group_id: Group GSSI (Group Short Subscriber Identity)
            emergency: If True, make an emergency group call
        
        Returns:
            True if call initiated successfully, False otherwise
        """
        if emergency:
            logger.info(f"Radio {self.radio_id} making EMERGENCY group call to group {group_id}")
            # Emergency group call uses !# suffix
            success, _ = self._send_command(f"ATD{group_id}!#", timeout=10.0)
        else:
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
    
    def send_text_message(self, target: str, message: str, is_group: bool = False, 
                          priority: int = 0) -> bool:
        """
        Send a text (SDS) message.
        
        Args:
            target: Target ISSI or GSSI
            message: Text message content
            is_group: True if sending to group, False for individual
            priority: Message priority (0=normal, 1=high, 2=emergency)
        
        Returns:
            True if sent successfully, False otherwise
        """
        logger.info(f"Radio {self.radio_id} sending text message to {target}: {message} (priority={priority})")
        
        # Escape message if needed
        escaped_message = message.replace('"', '\\"')
        
        # Different command format for group vs individual
        if is_group:
            success, _ = self._send_command(f'AT+CMGS="{target}#","{escaped_message}",{priority}')
        else:
            success, _ = self._send_command(f'AT+CMGS="{target}","{escaped_message}",{priority}')
        
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
    
    def set_audio_volume(self, volume: int) -> bool:
        """
        Set audio volume level.
        
        Args:
            volume: Volume level (0-100)
        
        Returns:
            True if successful, False otherwise
        """
        if not 0 <= volume <= 100:
            logger.error(f"Invalid volume level: {volume}. Must be 0-100")
            return False
        
        logger.info(f"Radio {self.radio_id} setting audio volume to {volume}")
        success, _ = self._send_command(f"AT+CLVL={volume}")
        return success
    
    def get_audio_volume(self) -> Optional[int]:
        """
        Get current audio volume level.
        
        Returns:
            Volume level (0-100) or None if failed
        """
        success, response = self._send_command("AT+CLVL?")
        if success:
            # Parse response: +CLVL: <level>
            match = re.search(r'\+CLVL:\s*(\d+)', response)
            if match:
                volume = int(match.group(1))
                logger.info(f"Radio {self.radio_id} volume level: {volume}")
                return volume
        return None
    
    def enable_encryption(self, key_id: int = 1) -> bool:
        """
        Enable encryption for calls.
        
        Args:
            key_id: Encryption key ID to use
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} enabling encryption with key {key_id}")
        success, _ = self._send_command(f"AT+CTENC={key_id}")
        return success
    
    def disable_encryption(self) -> bool:
        """
        Disable encryption for calls.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} disabling encryption")
        success, _ = self._send_command("AT+CTENC=0")
        return success
    
    def get_encryption_status(self) -> Optional[Dict[str, any]]:
        """
        Get current encryption status.
        
        Returns:
            Dictionary with encryption info or None if failed
        """
        success, response = self._send_command("AT+CTENC?")
        if success:
            # Parse response: +CTENC: <mode>,<key_id>
            match = re.search(r'\+CTENC:\s*(\d+),(\d+)', response)
            if match:
                mode = int(match.group(1))
                key_id = int(match.group(2))
                info = {
                    'enabled': mode > 0,
                    'mode': mode,
                    'key_id': key_id
                }
                logger.info(f"Radio {self.radio_id} encryption status: {info}")
                return info
        return None
    
    def set_operating_mode(self, mode: str) -> bool:
        """
        Set radio operating mode.
        
        Args:
            mode: Operating mode ('TMO' for Trunked Mode Operation, 'DMO' for Direct Mode Operation)
        
        Returns:
            True if successful, False otherwise
        """
        if mode not in ['TMO', 'DMO']:
            logger.error(f"Invalid operating mode: {mode}. Must be 'TMO' or 'DMO'")
            return False
        
        logger.info(f"Radio {self.radio_id} setting operating mode to {mode}")
        success, _ = self._send_command(f"AT+CTOM={mode}")
        return success
    
    def get_signal_strength(self) -> Optional[int]:
        """
        Get current signal strength.
        
        Returns:
            Signal strength (0-31, 99=unknown) or None if failed
        """
        success, response = self._send_command("AT+CSQ")
        if success:
            # Parse response: +CSQ: <rssi>,<ber>
            match = re.search(r'\+CSQ:\s*(\d+),(\d+)', response)
            if match:
                rssi = int(match.group(1))
                logger.info(f"Radio {self.radio_id} signal strength: {rssi}")
                return rssi
        return None
    
    def scan_for_networks(self) -> Optional[List[Dict[str, str]]]:
        """
        Scan for available TETRA networks.
        
        Returns:
            List of network dictionaries or None if failed
        """
        logger.info(f"Radio {self.radio_id} scanning for networks")
        success, response = self._send_command("AT+COPS=?", timeout=30.0)
        
        if success:
            networks = []
            # Parse response: +COPS: (status,"name","short","numeric"),...
            pattern = r'\((\d+),"([^"]+)","([^"]+)","([^"]+)"\)'
            for match in re.finditer(pattern, response):
                networks.append({
                    'status': match.group(1),
                    'name': match.group(2),
                    'short_name': match.group(3),
                    'numeric': match.group(4)
                })
            logger.info(f"Radio {self.radio_id} found {len(networks)} networks")
            return networks
        return None
    
    def read_sds_message(self, index: int) -> Optional[Dict[str, str]]:
        """
        Read a stored SDS message.
        
        Args:
            index: Message index
        
        Returns:
            Dictionary with message details or None if failed
        """
        logger.info(f"Radio {self.radio_id} reading SDS message at index {index}")
        success, response = self._send_command(f"AT+CMGR={index}")
        
        if success:
            # Parse message (format varies by radio)
            return {
                'index': index,
                'raw': response
            }
        return None
    
    def delete_sds_message(self, index: int) -> bool:
        """
        Delete a stored SDS message.
        
        Args:
            index: Message index to delete
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} deleting SDS message at index {index}")
        success, _ = self._send_command(f"AT+CMGD={index}")
        return success
    
    def set_dgna_mode(self, mode: int) -> bool:
        """
        Set DGNA (Dynamic Group Number Assignment) mode.
        
        Args:
            mode: DGNA mode (0=disabled, 1=enabled)
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} setting DGNA mode to {mode}")
        success, _ = self._send_command(f"AT+CTDGNA={mode}")
        return success
    
    def attach_to_network(self) -> bool:
        """
        Attach to TETRA network (similar to register but more explicit).
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} attaching to network")
        success, _ = self._send_command("AT+CGATT=1", timeout=30.0)
        return success
    
    def detach_from_network(self) -> bool:
        """
        Detach from TETRA network.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} detaching from network")
        success, _ = self._send_command("AT+CGATT=0")
        return success
    
    def get_network_attachment_status(self) -> Optional[bool]:
        """
        Get network attachment status.
        
        Returns:
            True if attached, False if not attached, None if failed
        """
        success, response = self._send_command("AT+CGATT?")
        if success:
            # Parse response: +CGATT: <state>
            match = re.search(r'\+CGATT:\s*(\d+)', response)
            if match:
                state = int(match.group(1))
                attached = state == 1
                logger.info(f"Radio {self.radio_id} network attachment: {attached}")
                return attached
        return None
    
    def send_location_info(self, latitude: float, longitude: float) -> bool:
        """
        Send location information (GPS coordinates).
        
        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} sending location: {latitude}, {longitude}")
        # Format: AT+CTLOC=<lat>,<lon>
        success, _ = self._send_command(f"AT+CTLOC={latitude},{longitude}")
        return success
    
    def set_ambient_listening(self, enable: bool) -> bool:
        """
        Enable or disable ambient listening mode.
        
        Args:
            enable: True to enable, False to disable
        
        Returns:
            True if successful, False otherwise
        """
        mode = 1 if enable else 0
        logger.info(f"Radio {self.radio_id} {'enabling' if enable else 'disabling'} ambient listening")
        success, _ = self._send_command(f"AT+CTAL={mode}")
        return success
    
    # Additional TETRA PEI Commands
    
    def set_flash_class(self, flash_class: int) -> bool:
        """
        Set flash class (FCLASS).
        
        Args:
            flash_class: Flash class value
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} setting flash class to {flash_class}")
        success, _ = self._send_command(f"AT+FCLASS={flash_class}")
        return success
    
    def get_flash_class(self) -> Optional[int]:
        """
        Get current flash class.
        
        Returns:
            Flash class value or None if failed
        """
        success, response = self._send_command("AT+FCLASS?")
        if success:
            match = re.search(r'\+FCLASS:\s*(\d+)', response)
            if match:
                flash_class = int(match.group(1))
                logger.info(f"Radio {self.radio_id} flash class: {flash_class}")
                return flash_class
        return None
    
    def set_error_reporting(self, mode: int) -> bool:
        """
        Set mobile equipment error reporting mode (CMEE).
        
        Args:
            mode: 0=disable, 1=numeric, 2=verbose
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} setting error reporting mode to {mode}")
        success, _ = self._send_command(f"AT+CMEE={mode}")
        return success
    
    def get_error_reporting(self) -> Optional[int]:
        """
        Get current error reporting mode.
        
        Returns:
            Error reporting mode or None if failed
        """
        success, response = self._send_command("AT+CMEE?")
        if success:
            match = re.search(r'\+CMEE:\s*(\d+)', response)
            if match:
                mode = int(match.group(1))
                logger.info(f"Radio {self.radio_id} error reporting mode: {mode}")
                return mode
        return None
    
    def set_clock(self, datetime_str: str) -> bool:
        """
        Set radio clock (CCLK).
        
        Args:
            datetime_str: Date/time string in format "YY/MM/DD,HH:MM:SS+TZ"
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} setting clock to {datetime_str}")
        success, _ = self._send_command(f'AT+CCLK="{datetime_str}"')
        return success
    
    def get_clock(self) -> Optional[str]:
        """
        Get current radio clock.
        
        Returns:
            Date/time string or None if failed
        """
        success, response = self._send_command("AT+CCLK?")
        if success:
            match = re.search(r'\+CCLK:\s*"([^"]+)"', response)
            if match:
                clock = match.group(1)
                logger.info(f"Radio {self.radio_id} clock: {clock}")
                return clock
        return None
    
    def get_dcd_status(self) -> Optional[int]:
        """
        Get DCD (Data Carrier Detect) status (CTDCD).
        
        Returns:
            DCD status (0=off, 1=on) or None if failed
        """
        success, response = self._send_command("AT+CTDCD?")
        if success:
            match = re.search(r'\+CTDCD:\s*(\d+)', response)
            if match:
                status = int(match.group(1))
                logger.info(f"Radio {self.radio_id} DCD status: {status}")
                return status
        return None
    
    def get_trunked_mode(self) -> Optional[Dict[str, any]]:
        """
        Get trunked/direct mode information (CTTCT).
        
        Returns:
            Dictionary with mode info or None if failed
        """
        success, response = self._send_command("AT+CTTCT?")
        if success:
            # Parse response: +CTTCT: <mode>,<info>
            match = re.search(r'\+CTTCT:\s*(\d+)(?:,(.+))?', response)
            if match:
                mode = int(match.group(1))
                info = match.group(2) if match.group(2) else ""
                result = {
                    'mode': mode,
                    'info': info
                }
                logger.info(f"Radio {self.radio_id} trunked mode: {result}")
                return result
        return None
    
    def set_service_provider(self, provider: str) -> bool:
        """
        Set service provider (CTSP).
        
        Args:
            provider: Service provider string
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} setting service provider to {provider}")
        success, _ = self._send_command(f'AT+CTSP="{provider}"')
        return success
    
    def get_service_provider(self) -> Optional[str]:
        """
        Get service provider.
        
        Returns:
            Service provider string or None if failed
        """
        success, response = self._send_command("AT+CTSP?")
        if success:
            match = re.search(r'\+CTSP:\s*"([^"]+)"', response)
            if match:
                provider = match.group(1)
                logger.info(f"Radio {self.radio_id} service provider: {provider}")
                return provider
        return None
    
    def get_primary_channel(self) -> Optional[int]:
        """
        Get primary channel ISSI (PCSSI).
        
        Returns:
            Primary channel ISSI or None if failed
        """
        success, response = self._send_command("AT+PCSSI?")
        if success:
            match = re.search(r'\+PCSSI:\s*(\d+)', response)
            if match:
                issi = int(match.group(1))
                logger.info(f"Radio {self.radio_id} primary channel ISSI: {issi}")
                return issi
        return None
    
    def set_forwarding_number(self, number: str) -> bool:
        """
        Set fixed numbers (CNUMF).
        
        Args:
            number: Fixed number
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} setting fixed number to {number}")
        success, _ = self._send_command(f'AT+CNUMF="{number}"')
        return success
    
    def get_forwarding_number(self) -> Optional[str]:
        """
        Get fixed numbers.
        
        Returns:
            Fixed number or None if failed
        """
        success, response = self._send_command("AT+CNUMF?")
        if success:
            match = re.search(r'\+CNUMF:\s*"([^"]+)"', response)
            if match:
                number = match.group(1)
                logger.info(f"Radio {self.radio_id} fixed number: {number}")
                return number
        return None
    
    def get_subscriber_number(self) -> Optional[str]:
        """
        Get static identities (CNUMS).
        
        Returns:
            Static identity or None if failed
        """
        success, response = self._send_command("AT+CNUMS?")
        if success:
            match = re.search(r'\+CNUMS:\s*"([^"]+)"', response)
            if match:
                number = match.group(1)
                logger.info(f"Radio {self.radio_id} static identity: {number}")
                return number
        return None
    
    def get_dialing_number(self) -> Optional[str]:
        """
        Get dynamic identities (CNUMD).
        
        Returns:
            Dynamic identity or None if failed
        """
        success, response = self._send_command("AT+CNUMD?")
        if success:
            match = re.search(r'\+CNUMD:\s*"([^"]+)"', response)
            if match:
                number = match.group(1)
                logger.info(f"Radio {self.radio_id} dynamic identity: {number}")
                return number
        return None
    
    def set_sds_configuration(self, config: int) -> bool:
        """
        Set SDS configuration (CTSDC).
        
        Args:
            config: SDS configuration value
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} setting SDS configuration to {config}")
        success, _ = self._send_command(f"AT+CTSDC={config}")
        return success
    
    def get_sds_configuration(self) -> Optional[int]:
        """
        Get SDS configuration.
        
        Returns:
            SDS configuration value or None if failed
        """
        success, response = self._send_command("AT+CTSDC?")
        if success:
            match = re.search(r'\+CTSDC:\s*(\d+)', response)
            if match:
                config = int(match.group(1))
                logger.info(f"Radio {self.radio_id} SDS configuration: {config}")
                return config
        return None
    
    def check_incoming_call_notification(self) -> Optional[Dict[str, str]]:
        """
        Check for incoming call notification (CTICN).
        
        Returns:
            Dictionary with call info or None if no notification
        """
        # Check unsolicited messages for CTICN
        messages = self.get_unsolicited_messages(clear=False)
        for msg in messages:
            if '+CTICN:' in msg:
                # Parse: +CTICN: <call_type>,<calling_party>
                match = re.search(r'\+CTICN:\s*(\d+),"?([^",]+)"?', msg)
                if match:
                    result = {
                        'call_type': match.group(1),
                        'calling_party': match.group(2)
                    }
                    logger.info(f"Radio {self.radio_id} incoming call notification: {result}")
                    # Remove this message from unsolicited
                    self._unsolicited_messages.remove(msg)
                    return result
        return None
    
    def check_call_progress(self) -> Optional[Dict[str, str]]:
        """
        Check outgoing call progress (CTOCP).
        
        Returns:
            Dictionary with call progress info or None if no notification
        """
        messages = self.get_unsolicited_messages(clear=False)
        for msg in messages:
            if '+CTOCP:' in msg:
                # Parse: +CTOCP: <progress_type>,<info>
                match = re.search(r'\+CTOCP:\s*(\d+)(?:,"?([^",]+)"?)?', msg)
                if match:
                    result = {
                        'progress_type': match.group(1),
                        'info': match.group(2) if match.group(2) else ""
                    }
                    logger.info(f"Radio {self.radio_id} call progress: {result}")
                    self._unsolicited_messages.remove(msg)
                    return result
        return None
    
    def check_call_connected(self) -> Optional[Dict[str, str]]:
        """
        Check for call connected notification (CTCC).
        
        Returns:
            Dictionary with call info or None if no notification
        """
        messages = self.get_unsolicited_messages(clear=False)
        for msg in messages:
            if '+CTCC:' in msg:
                # Parse: +CTCC: <call_id>,<call_type>
                match = re.search(r'\+CTCC:\s*(\d+)(?:,(\d+))?', msg)
                if match:
                    result = {
                        'call_id': match.group(1),
                        'call_type': match.group(2) if match.group(2) else ""
                    }
                    logger.info(f"Radio {self.radio_id} call connected: {result}")
                    self._unsolicited_messages.remove(msg)
                    return result
        return None
    
    def check_call_released(self) -> Optional[Dict[str, str]]:
        """
        Check for call released notification (CTCR).
        
        Returns:
            Dictionary with call info or None if no notification
        """
        messages = self.get_unsolicited_messages(clear=False)
        for msg in messages:
            if '+CTCR:' in msg:
                # Parse: +CTCR: <call_id>,<reason>
                match = re.search(r'\+CTCR:\s*(\d+)(?:,(\d+))?', msg)
                if match:
                    result = {
                        'call_id': match.group(1),
                        'reason': match.group(2) if match.group(2) else ""
                    }
                    logger.info(f"Radio {self.radio_id} call released: {result}")
                    self._unsolicited_messages.remove(msg)
                    return result
        return None
    
    def get_sds_status(self) -> Optional[Dict[str, str]]:
        """
        Get SDS status (CTSDS).
        
        Returns:
            Dictionary with SDS status or None if failed
        """
        success, response = self._send_command("AT+CTSDS?")
        if success:
            # Parse: +CTSDS: <status>,<info>
            match = re.search(r'\+CTSDS:\s*(\d+)(?:,(.+))?', response)
            if match:
                result = {
                    'status': match.group(1),
                    'info': match.group(2) if match.group(2) else ""
                }
                logger.info(f"Radio {self.radio_id} SDS status: {result}")
                return result
        return None
    
    def send_message(self, target: str, message: str, priority: int = 0) -> bool:
        """
        Send message using CTMGS command.
        
        The CTMGS command sends the message content on the next line after the command.
        Format:
        1. Send AT+CTMGS=<target>,<priority>
        2. Wait for '>' prompt
        3. Send message text
        4. Send Ctrl+Z (0x1A) to end message
        5. Wait for OK
        
        Args:
            target: Target ISSI or GSSI
            message: Message text
            priority: Message priority (0=normal, 1=high, 2=emergency)
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Radio {self.radio_id} sending message to {target}: {message}")
        
        if not self.connection.is_connected():
            logger.error(f"Cannot send message from {self.radio_id}: not connected")
            return False
        
        # Send the CTMGS command
        command = f'AT+CTMGS="{target}",{priority}'
        if not self.connection.send(command):
            logger.error(f"Failed to send CTMGS command to {self.radio_id}")
            return False
        
        # Use the state machine — start in WAITING_PROMPT mode
        sm = ATCommandStateMachine(
            self._unsolicited_patterns,
            self._command_response_map,
            self._unsolicited_callback,
        )
        sm.start(command, expect_prompt=True)

        # Wait for '>' prompt
        success, response, _ = self.connection.receive_until_any(["> ", ">\r\n"], timeout=5.0)
        if not success:
            logger.error(f"Timeout waiting for '>' prompt from {self.radio_id}")
            sm.timeout()
            self._unsolicited_messages.extend(sm.get_unsolicited_messages())
            return False
        
        # Prompt received — advance state machine
        sm.prompt_received()

        # Send message text followed by Ctrl+Z
        message_data = message + "\x1A"
        if not self.connection.send(message_data):
            logger.error(f"Failed to send message text to {self.radio_id}")
            sm.connection_error()
            self._unsolicited_messages.extend(sm.get_unsolicited_messages())
            return False
        
        # Read lines until the state machine reaches a terminal state
        start_time = time.time()
        prompt_timeout = 5.0
        while not sm.is_done():
            remaining = prompt_timeout - (time.time() - start_time)
            if remaining <= 0:
                sm.timeout()
                break
            line = self.connection.readline(timeout=remaining)
            if line is None:
                sm.timeout()
                break
            sm.process_line(line)

        # Merge unsolicited messages
        self._unsolicited_messages.extend(sm.get_unsolicited_messages())

        is_success = sm.is_success()

        if is_success:
            logger.info(f"Message sent successfully from {self.radio_id}")
        else:
            logger.warning(f"Message send returned {sm.final_response} from {self.radio_id}")
        
        return is_success
    
    def check_sds_report(self) -> Optional[Dict[str, str]]:
        """
        Check for SDS report notification (CTSDSR).
        
        Returns:
            Dictionary with SDS report info or None if no notification
        """
        messages = self.get_unsolicited_messages(clear=False)
        for msg in messages:
            if '+CTSDSR:' in msg:
                # Parse: +CTSDSR: <message_id>,<status>
                match = re.search(r'\+CTSDSR:\s*(\d+)(?:,(\d+))?', msg)
                if match:
                    result = {
                        'message_id': match.group(1),
                        'status': match.group(2) if match.group(2) else ""
                    }
                    logger.info(f"Radio {self.radio_id} SDS report: {result}")
                    self._unsolicited_messages.remove(msg)
                    return result
        return None
    
    def send_at_command(self, command: str, timeout: float = 5.0) -> Tuple[bool, str]:
        """
        Send a generic AT command to the radio.
        
        This is a public wrapper around _send_command that allows sending
        any AT command that is not already wrapped by a specific method.
        Use this for sending commands that don't have dedicated methods.
        
        Args:
            command: The AT command to send (without CR+LF, e.g., "AT+CGSN")
            timeout: Response timeout in seconds (default: 5.0)
        
        Returns:
            Tuple of (success, response_data)
            - success: True if command returned OK, False for ERROR or timeout
            - response_data: The full response including any intermediate data
        
        Example:
            success, response = pei.send_at_command("AT+CGSN")
            if success:
                print(f"Serial number: {response}")
        """
        logger.info(f"Radio {self.radio_id} sending generic AT command: {command}")
        return self._send_command(command, wait_for_response=True, timeout=timeout)
