"""
TETRA Radio Simulator

Simulates a TETRA radio responding to PEI AT commands for testing purposes.
"""

import socket
import threading
import logging
import time
from typing import Optional, Dict, Set
from enum import Enum


logger = logging.getLogger(__name__)


class RadioState(Enum):
    """Radio operational states."""
    IDLE = "idle"
    IN_CALL = "in_call"
    TRANSMITTING = "transmitting"
    RECEIVING = "receiving"


class TetraRadioSimulator:
    """
    Simulates a TETRA radio with PEI interface.
    
    This simulator responds to AT commands and can simulate various
    radio behaviors for testing purposes.
    """
    
    def __init__(self, radio_id: str, host: str = "127.0.0.1", port: int = 5000,
                 issi: str = "1001"):
        """
        Initialize radio simulator.
        
        Args:
            radio_id: Unique radio identifier
            host: Host to bind to
            port: Port to listen on
            issi: Radio ISSI (Individual Short Subscriber Identity)
        """
        self.radio_id = radio_id
        self.host = host
        self.port = port
        self.issi = issi
        
        self.state = RadioState.IDLE
        self.registered = True  # Default to registered
        self.joined_groups: Set[str] = set()
        self.in_call_with: Optional[str] = None
        self.ptt_pressed = False
        
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.running = False
        self.server_thread: Optional[threading.Thread] = None
        
        # Configuration
        self.auto_register = True
        self.call_response_delay = 0.5
        self.simulate_no_answer = False  # Set to True to simulate NO ANSWER
        self.simulate_no_carrier = False  # Set to True to simulate NO CARRIER on hangup
        
        # State for multi-stage commands (like CTMGS)
        self.waiting_for_message_text = False
        self.ctmgs_target = None
        self.ctmgs_priority = None
        
        logger.info(f"TetraRadioSimulator initialized: {radio_id} (ISSI: {issi})")
    
    def start(self) -> bool:
        """
        Start the simulator server.
        
        Returns:
            True if started successfully, False otherwise
        """
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            
            self.running = True
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()
            
            logger.info(f"Radio simulator {self.radio_id} started on {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start simulator {self.radio_id}: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the simulator server."""
        self.running = False
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        if self.server_thread:
            self.server_thread.join(timeout=2.0)
        
        logger.info(f"Radio simulator {self.radio_id} stopped")
    
    def _server_loop(self) -> None:
        """Main server loop to accept and handle connections."""
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                self.client_socket, addr = self.server_socket.accept()
                logger.info(f"Simulator {self.radio_id} accepted connection from {addr}")
                
                self._handle_client()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error in server loop for {self.radio_id}: {e}")
    
    def _handle_client(self) -> None:
        """Handle client connection and process commands."""
        buffer = ""
        
        while self.running:
            try:
                self.client_socket.settimeout(1.0)
                data = self.client_socket.recv(4096)
                
                if not data:
                    logger.info(f"Client disconnected from {self.radio_id}")
                    break
                
                buffer += data.decode('utf-8', errors='replace')
                
                # Check if waiting for message text (CTMGS)
                if self.waiting_for_message_text:
                    # Look for Ctrl+Z (0x1A) terminator
                    if '\x1A' in buffer:
                        message_text, buffer = buffer.split('\x1A', 1)
                        logger.info(f"Received message text for CTMGS: {message_text}")
                        self.waiting_for_message_text = False
                        self.ctmgs_target = None
                        self.ctmgs_priority = None
                        self._send_response("OK")
                    continue
                
                # Process complete commands (terminated by \r\n)
                while '\r\n' in buffer:
                    command, buffer = buffer.split('\r\n', 1)
                    command = command.strip()
                    
                    if command:
                        self._process_command(command)
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error handling client for {self.radio_id}: {e}")
                break
        
        # Cleanup
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
    
    def _send_response(self, response: str) -> None:
        """
        Send response to client.
        
        Args:
            response: Response string (will be terminated with \r\n)
        """
        if self.client_socket:
            try:
                if not response.endswith('\r\n'):
                    response += '\r\n'
                self.client_socket.sendall(response.encode('utf-8'))
                logger.debug(f"Simulator {self.radio_id} sent: {response.strip()}")
            except Exception as e:
                logger.error(f"Error sending response from {self.radio_id}: {e}")
    
    def _process_command(self, command: str) -> None:
        """
        Process an AT command and generate appropriate response.
        
        Args:
            command: AT command to process
        """
        logger.debug(f"Simulator {self.radio_id} received command: {command}")
        
        # Basic AT test
        if command == "AT":
            self._send_response("OK")
        
        # Get manufacturer
        elif command == "AT+CGMI":
            self._send_response("SimulatedTetraRadio")
            self._send_response("OK")
        
        # Get model
        elif command == "AT+CGMM":
            self._send_response(f"Model-{self.radio_id}")
            self._send_response("OK")
        
        # Get revision
        elif command == "AT+CGMR":
            self._send_response("Rev-1.0.0")
            self._send_response("OK")
        
        # Get serial/IMEI
        elif command == "AT+CGSN":
            self._send_response(self.issi)
            self._send_response("OK")
        
        # Network registration
        elif command.startswith("AT+COPS"):
            if self.auto_register:
                self.registered = True
                self._send_response("OK")
            else:
                self._send_response("ERROR")
        
        # Check registration status
        elif command == "AT+CREG?":
            status = 1 if self.registered else 0
            self._send_response(f"+CREG: 0,{status}")
            self._send_response("OK")
        
        # Enable CLIP (calling line identification)
        elif command.startswith("AT+CLIP"):
            self._send_response("OK")
        
        # Enable CRC (extended ring format)
        elif command.startswith("AT+CRC"):
            self._send_response("OK")
        
        # Enable new message indications
        elif command.startswith("AT+CNMI"):
            self._send_response("OK")
        
        # Dial - make call
        elif command.startswith("ATD"):
            self._handle_dial(command)
        
        # Answer call
        elif command == "ATA":
            self.state = RadioState.IN_CALL
            self._send_response("OK")
        
        # Hangup
        elif command == "ATH":
            # Check if we should simulate NO CARRIER (call dropped)
            if self.simulate_no_carrier:
                logger.info(f"Simulator {self.radio_id} simulating NO CARRIER on hangup")
                self._send_response("NO CARRIER")
                self.simulate_no_carrier = False  # Reset flag
            else:
                self._send_response("OK")
            
            self.state = RadioState.IDLE
            self.in_call_with = None
        
        # PTT press/release
        elif command.startswith("AT+CTXD"):
            self._handle_ptt(command)
        
        # Join group
        elif command.startswith("AT+CTGS"):
            self._handle_join_group(command)
        
        # Leave group
        elif command.startswith("AT+CTGL"):
            self._handle_leave_group(command)
        
        # Send status message
        elif command.startswith("AT+CTSDSR"):
            self._send_response("OK")
        
        # Send text message
        elif command.startswith("AT+CMGS"):
            self._send_response("OK")
        
        # Audio volume commands
        elif command.startswith("AT+CLVL="):
            # Set volume
            self._send_response("OK")
        elif command.startswith("AT+CLVL?"):
            # Get volume
            self._send_response("+CLVL: 50")
            self._send_response("OK")
        
        # Encryption commands
        elif command.startswith("AT+CTENC="):
            self._send_response("OK")
        elif command.startswith("AT+CTENC?"):
            self._send_response("+CTENC: 0,0")
            self._send_response("OK")
        
        # Signal strength
        elif command.startswith("AT+CSQ"):
            self._send_response("+CSQ: 25,0")
            self._send_response("OK")
        
        # Network attachment
        elif command.startswith("AT+CGATT="):
            self._send_response("OK")
        elif command.startswith("AT+CGATT?"):
            state = 1 if self.registered else 0
            self._send_response(f"+CGATT: {state}")
            self._send_response("OK")
        
        # Operating mode
        elif command.startswith("AT+CTOM="):
            self._send_response("OK")
        
        # DGNA mode
        elif command.startswith("AT+CTDGNA="):
            self._send_response("OK")
        
        # Location info
        elif command.startswith("AT+CTLOC="):
            self._send_response("OK")
        
        # Ambient listening
        elif command.startswith("AT+CTAL="):
            self._send_response("OK")
        
        # Read/delete messages
        elif command.startswith("AT+CMGR="):
            self._send_response("+CMGR: 0,\"1234\",\"Test Message\"")
            self._send_response("OK")
        elif command.startswith("AT+CMGD="):
            self._send_response("OK")
        
        # New TETRA PEI Commands
        # Flash class
        elif command.startswith("AT+FCLASS="):
            self._send_response("OK")
        elif command.startswith("AT+FCLASS?"):
            self._send_response("+FCLASS: 0")
            self._send_response("OK")
        
        # Error reporting
        elif command.startswith("AT+CMEE="):
            self._send_response("OK")
        elif command.startswith("AT+CMEE?"):
            self._send_response("+CMEE: 0")
            self._send_response("OK")
        
        # Clock
        elif command.startswith("AT+CCLK="):
            self._send_response("OK")
        elif command.startswith("AT+CCLK?"):
            self._send_response('+CCLK: "26/02/11,21:00:00+00"')
            self._send_response("OK")
        
        # DCD status
        elif command.startswith("AT+CTDCD?"):
            self._send_response("+CTDCD: 0")
            self._send_response("OK")
        
        # Trunked/Direct mode
        elif command.startswith("AT+CTTCT?"):
            self._send_response("+CTTCT: 0,TMO")
            self._send_response("OK")
        
        # Service provider
        elif command.startswith("AT+CTSP="):
            self._send_response("OK")
        elif command.startswith("AT+CTSP?"):
            self._send_response('+CTSP: "Test Provider"')
            self._send_response("OK")
        
        # Primary channel
        elif command.startswith("AT+PCSSI?"):
            self._send_response("+PCSSI: 1001")
            self._send_response("OK")
        
        # Forwarding number
        elif command.startswith("AT+CNUMF="):
            self._send_response("OK")
        elif command.startswith("AT+CNUMF?"):
            self._send_response('+CNUMF: "12345"')
            self._send_response("OK")
        
        # Subscriber number
        elif command.startswith("AT+CNUMS?"):
            self._send_response('+CNUMS: "1001"')
            self._send_response("OK")
        
        # Dialing number
        elif command.startswith("AT+CNUMD?"):
            self._send_response('+CNUMD: "2001"')
            self._send_response("OK")
        
        # SDS configuration
        elif command.startswith("AT+CTSDC="):
            self._send_response("OK")
        elif command.startswith("AT+CTSDC?"):
            self._send_response("+CTSDC: 0")
            self._send_response("OK")
        
        # SDS status
        elif command.startswith("AT+CTSDS?"):
            self._send_response("+CTSDS: 0,Ready")
            self._send_response("OK")
        
        # Message send (CTMGS)
        elif command.startswith("AT+CTMGS="):
            # Parse target and priority
            import re
            match = re.match(r'AT\+CTMGS="([^"]+)",(\d+)', command)
            if match:
                self.ctmgs_target = match.group(1)
                self.ctmgs_priority = int(match.group(2))
                self.waiting_for_message_text = True
                # Send prompt for message text
                self._send_response("> ")
        
        # Unknown command
        else:
            logger.warning(f"Unknown command for {self.radio_id}: {command}")
            self._send_response("ERROR")
    
    def _handle_dial(self, command: str) -> None:
        """
        Handle dial command.
        
        Returns appropriate response based on radio state:
        - OK: Call initiated successfully (radio is idle)
        - BUSY: Called party is busy (already in a call)
        - NO ANSWER: Simulated no answer scenario
        - NO DIALTONE: Simulated no network scenario
        
        Supports:
        - Individual calls: ATD<number>;
        - Group calls: ATD<number>#
        - Emergency individual: ATD<number>!;
        - Emergency group: ATD<number>!#
        """
        # Extract target from ATD command
        target = None
        is_group_call = False
        is_emergency = False
        
        # Check for emergency flag
        if '!' in command:
            is_emergency = True
        
        if '!#' in command:
            # Emergency group call
            target = command.replace("ATD", "").replace("!#", "").strip()
            is_group_call = True
        elif '!;' in command:
            # Emergency individual call
            target = command.replace("ATD", "").replace("!;", "").strip()
            is_group_call = False
        elif ';' in command:
            # Individual call
            target = command.replace("ATD", "").replace(";", "").strip()
            is_group_call = False
        elif '#' in command:
            # Group call
            target = command.replace("ATD", "").replace("#", "").strip()
            is_group_call = True
        
        # Check if this radio is already in a call
        if self.state == RadioState.IN_CALL or self.state == RadioState.TRANSMITTING:
            # Radio is busy
            logger.info(f"Simulator {self.radio_id} is busy, cannot make call to {target}")
            self._send_response("BUSY")
            return
        
        # Check if not registered (simulate no dialtone)
        if not self.registered:
            logger.info(f"Simulator {self.radio_id} not registered, returning NO DIALTONE")
            self._send_response("NO DIALTONE")
            return
        
        # Check if we should simulate no answer
        if self.simulate_no_answer:
            logger.info(f"Simulator {self.radio_id} simulating NO ANSWER for call to {target}")
            self._send_response("NO ANSWER")
            return
        
        # Successful call
        self.state = RadioState.IN_CALL
        self.in_call_with = target
        
        call_type = "EMERGENCY " if is_emergency else ""
        if is_group_call:
            logger.info(f"Simulator {self.radio_id} making {call_type}group call to {target}")
        else:
            logger.info(f"Simulator {self.radio_id} making {call_type}individual call to {target}")
        
        self._send_response("OK")
    
    def _handle_ptt(self, command: str) -> None:
        """Handle PTT press/release."""
        if "=1" in command:
            self.ptt_pressed = True
            self.state = RadioState.TRANSMITTING
            logger.info(f"Simulator {self.radio_id} PTT pressed")
        elif "=0" in command:
            self.ptt_pressed = False
            if self.state == RadioState.TRANSMITTING:
                self.state = RadioState.IN_CALL if self.in_call_with else RadioState.IDLE
            logger.info(f"Simulator {self.radio_id} PTT released")
        
        self._send_response("OK")
    
    def _handle_join_group(self, command: str) -> None:
        """Handle join group command."""
        # AT+CTGS=<group_id>
        parts = command.split('=')
        if len(parts) == 2:
            group_id = parts[1].strip()
            self.joined_groups.add(group_id)
            logger.info(f"Simulator {self.radio_id} joined group {group_id}")
        self._send_response("OK")
    
    def _handle_leave_group(self, command: str) -> None:
        """Handle leave group command."""
        # AT+CTGL=<group_id>
        parts = command.split('=')
        if len(parts) == 2:
            group_id = parts[1].strip()
            self.joined_groups.discard(group_id)
            logger.info(f"Simulator {self.radio_id} left group {group_id}")
        self._send_response("OK")
    
    def simulate_incoming_call(self, caller_issi: str) -> None:
        """
        Simulate an incoming call.
        
        Args:
            caller_issi: ISSI of the caller
        """
        if self.client_socket:
            self._send_response("RING")
            self._send_response(f'+CLIP: "{caller_issi}",145')
            logger.info(f"Simulator {self.radio_id} simulated incoming call from {caller_issi}")
    
    def simulate_ptt_event(self, pressed: bool) -> None:
        """
        Simulate PTT event notification.
        
        Args:
            pressed: True for PTT pressed, False for released
        """
        if self.client_socket:
            state = 1 if pressed else 0
            self._send_response(f"+CTXD: {state}")
            logger.info(f"Simulator {self.radio_id} simulated PTT {'pressed' if pressed else 'released'}")
    
    def simulate_text_message(self, sender_issi: str, message: str) -> None:
        """
        Simulate receiving a text message.
        
        Args:
            sender_issi: ISSI of sender
            message: Message content
        """
        if self.client_socket:
            self._send_response('+CMTI: "SM",1')
            logger.info(f"Simulator {self.radio_id} simulated text message from {sender_issi}")
    
    def set_busy_state(self, target: str = "9999") -> None:
        """
        Put the radio in a busy state (in a call).
        
        Args:
            target: ISSI or GSSI of the party in call with
        """
        self.state = RadioState.IN_CALL
        self.in_call_with = target
        logger.info(f"Simulator {self.radio_id} set to busy state (in call with {target})")
    
    def clear_busy_state(self) -> None:
        """Clear the busy state and return to idle."""
        self.state = RadioState.IDLE
        self.in_call_with = None
        logger.info(f"Simulator {self.radio_id} cleared busy state")
    
    def get_state(self) -> Dict[str, any]:
        """Get current simulator state."""
        return {
            'radio_id': self.radio_id,
            'issi': self.issi,
            'state': self.state.value,
            'registered': self.registered,
            'joined_groups': list(self.joined_groups),
            'in_call_with': self.in_call_with,
            'ptt_pressed': self.ptt_pressed
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return f"TetraRadioSimulator({self.radio_id}, {self.host}:{self.port}, state={self.state.value})"
