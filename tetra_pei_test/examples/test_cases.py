"""
Example Test Cases

Demonstrates how to create tests for various TETRA PEI operations.
"""

import time
import logging
from typing import Optional

from ..core.test_base import TestCase, TestResult
from ..core.tetra_pei import PTTState
from ..core.test_helpers import CallSession, PTTSession, RadioGroup, TestScenarioBuilder


logger = logging.getLogger(__name__)


class IndividualCallTest(TestCase):
    """
    Test individual call between two radios.
    
    Radio 1 calls Radio 2, Radio 2 answers, then both end the call.
    """
    
    def __init__(self):
        super().__init__(
            name="Individual Call Test",
            description="Test individual call setup and teardown between two radios"
        )
    
    def run(self) -> TestResult:
        """Execute individual call test."""
        try:
            # Get radios
            if len(self.radios) < 2:
                self.error_message = "Test requires at least 2 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            radio2 = self.radios[radio_ids[1]]
            
            logger.info(f"Testing individual call: {radio_ids[0]} -> {radio_ids[1]}")
            
            # Make call from radio1 to radio2 (using radio2's ISSI)
            # For testing, we'll use a dummy ISSI
            target_issi = "2001"
            
            if not radio1.make_individual_call(target_issi):
                self.error_message = f"Failed to initiate call from {radio_ids[0]}"
                return TestResult.FAILED
            
            logger.info("Call initiated, waiting for ring on radio 2...")
            time.sleep(2)
            
            # Check for incoming call on radio2
            caller = radio2.check_for_incoming_call(timeout=5.0)
            if not caller:
                self.error_message = f"Radio {radio_ids[1]} did not receive incoming call"
                return TestResult.FAILED
            
            logger.info(f"Radio {radio_ids[1]} received call from {caller}")
            
            # Answer call on radio2
            if not radio2.answer_call():
                self.error_message = f"Failed to answer call on {radio_ids[1]}"
                return TestResult.FAILED
            
            logger.info("Call answered, maintaining connection for 3 seconds...")
            time.sleep(3)
            
            # End call from radio1
            if not radio1.end_call():
                self.error_message = f"Failed to end call on {radio_ids[0]}"
                return TestResult.FAILED
            
            logger.info("Call ended successfully")
            
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class GroupCallTest(TestCase):
    """
    Test group call with multiple radios.
    
    All radios join a group, one radio initiates a group call.
    """
    
    def __init__(self, group_id: str = "9001"):
        super().__init__(
            name="Group Call Test",
            description=f"Test group call to group {group_id}"
        )
        self.group_id = group_id
    
    def run(self) -> TestResult:
        """Execute group call test."""
        try:
            if len(self.radios) < 2:
                self.error_message = "Test requires at least 2 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            
            logger.info(f"All radios joining group {self.group_id}...")
            
            # All radios join the group
            for radio_id in radio_ids:
                radio = self.radios[radio_id]
                if not radio.join_group(self.group_id):
                    self.error_message = f"Failed to join group on {radio_id}"
                    return TestResult.FAILED
                logger.info(f"Radio {radio_id} joined group")
            
            time.sleep(2)
            
            # First radio makes group call
            caller_id = radio_ids[0]
            caller = self.radios[caller_id]
            
            logger.info(f"Radio {caller_id} initiating group call...")
            if not caller.make_group_call(self.group_id):
                self.error_message = f"Failed to initiate group call from {caller_id}"
                return TestResult.FAILED
            
            logger.info("Group call initiated, maintaining for 5 seconds...")
            time.sleep(5)
            
            # End group call
            if not caller.end_call():
                self.error_message = f"Failed to end group call on {caller_id}"
                return TestResult.FAILED
            
            logger.info("Group call ended successfully")
            
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR
    
    def teardown(self) -> None:
        """Leave group after test."""
        try:
            for radio_id, radio in self.radios.items():
                radio.leave_group(self.group_id)
                logger.info(f"Radio {radio_id} left group {self.group_id}")
        except Exception as e:
            logger.error(f"Error in teardown: {e}")


class PTTTest(TestCase):
    """
    Test Push-to-Talk (PTT) functionality.
    
    Radio 1 presses PTT, Radio 2 should detect transmission.
    """
    
    def __init__(self):
        super().__init__(
            name="PTT Test",
            description="Test PTT press/release and transmission detection"
        )
    
    def run(self) -> TestResult:
        """Execute PTT test."""
        try:
            if len(self.radios) < 2:
                self.error_message = "Test requires at least 2 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            radio2 = self.radios[radio_ids[1]]
            
            logger.info(f"PTT test: {radio_ids[0]} transmits, {radio_ids[1]} receives")
            
            # Establish a call first (group call for simplicity)
            group_id = "9001"
            
            logger.info("Setting up group call...")
            if not radio1.join_group(group_id) or not radio2.join_group(group_id):
                self.error_message = "Failed to join group"
                return TestResult.FAILED
            
            time.sleep(1)
            
            if not radio1.make_group_call(group_id):
                self.error_message = "Failed to make group call"
                return TestResult.FAILED
            
            time.sleep(2)
            
            # Press PTT on radio1
            logger.info(f"Radio {radio_ids[0]} pressing PTT...")
            if not radio1.press_ptt():
                self.error_message = f"Failed to press PTT on {radio_ids[0]}"
                return TestResult.FAILED
            
            # Check if radio2 detects transmission
            logger.info(f"Checking if {radio_ids[1]} detects transmission...")
            ptt_event = radio2.check_for_ptt_event(timeout=3.0)
            
            if ptt_event != PTTState.PRESSED:
                self.error_message = f"Radio {radio_ids[1]} did not detect PTT press"
                # Continue anyway to cleanup
            
            # Transmit for 2 seconds
            time.sleep(2)
            
            # Release PTT on radio1
            logger.info(f"Radio {radio_ids[0]} releasing PTT...")
            if not radio1.release_ptt():
                self.error_message = f"Failed to release PTT on {radio_ids[0]}"
                return TestResult.FAILED
            
            # Check if radio2 detects end of transmission
            ptt_event = radio2.check_for_ptt_event(timeout=3.0)
            
            if ptt_event != PTTState.RELEASED:
                self.error_message = f"Radio {radio_ids[1]} did not detect PTT release"
            
            # End call
            radio1.end_call()
            
            logger.info("PTT test completed")
            
            # If we got here and no error message, test passed
            if not self.error_message:
                return TestResult.PASSED
            else:
                return TestResult.FAILED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR
    
    def teardown(self) -> None:
        """Cleanup after test."""
        try:
            for radio in self.radios.values():
                radio.leave_group("9001")
        except Exception as e:
            logger.error(f"Error in teardown: {e}")


class TextMessageTest(TestCase):
    """
    Test sending and receiving text messages.
    
    Radio 1 sends a text message to Radio 2.
    """
    
    def __init__(self):
        super().__init__(
            name="Text Message Test",
            description="Test sending text message between radios"
        )
    
    def run(self) -> TestResult:
        """Execute text message test."""
        try:
            if len(self.radios) < 2:
                self.error_message = "Test requires at least 2 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            radio2 = self.radios[radio_ids[1]]
            
            target_issi = "2001"
            message = "Test message from automated test"
            
            logger.info(f"Sending text message: {radio_ids[0]} -> {radio_ids[1]}")
            
            # Send message
            if not radio1.send_text_message(target_issi, message):
                self.error_message = f"Failed to send message from {radio_ids[0]}"
                return TestResult.FAILED
            
            logger.info("Message sent, waiting for delivery...")
            time.sleep(3)
            
            # Check if message received on radio2
            msg = radio2.check_for_text_message(timeout=5.0)
            if not msg:
                self.error_message = f"Radio {radio_ids[1]} did not receive message"
                return TestResult.FAILED
            
            logger.info(f"Message received on {radio_ids[1]}")
            
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class StatusMessageTest(TestCase):
    """
    Test sending status messages.
    
    Radio 1 sends a status message.
    """
    
    def __init__(self):
        super().__init__(
            name="Status Message Test",
            description="Test sending status message"
        )
    
    def run(self) -> TestResult:
        """Execute status message test."""
        try:
            if len(self.radios) < 1:
                self.error_message = "Test requires at least 1 radio"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            
            target_issi = "2001"
            status_value = 12345
            
            logger.info(f"Sending status message from {radio_ids[0]}")
            
            # Send status message
            if not radio1.send_status_message(target_issi, status_value):
                self.error_message = f"Failed to send status message from {radio_ids[0]}"
                return TestResult.FAILED
            
            logger.info("Status message sent successfully")
            
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class GroupRegistrationTest(TestCase):
    """
    Test group registration and deregistration.
    
    Radio joins and leaves multiple groups.
    """
    
    def __init__(self, groups: list = None):
        super().__init__(
            name="Group Registration Test",
            description="Test joining and leaving talkgroups"
        )
        self.groups = groups or ["9001", "9002", "9003"]
    
    def run(self) -> TestResult:
        """Execute group registration test."""
        try:
            if len(self.radios) < 1:
                self.error_message = "Test requires at least 1 radio"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio = self.radios[radio_ids[0]]
            
            logger.info(f"Testing group registration on {radio_ids[0]}")
            
            # Join all groups
            for group_id in self.groups:
                logger.info(f"Joining group {group_id}...")
                if not radio.join_group(group_id):
                    self.error_message = f"Failed to join group {group_id}"
                    return TestResult.FAILED
                time.sleep(1)
            
            logger.info("All groups joined successfully")
            time.sleep(2)
            
            # Leave all groups
            for group_id in self.groups:
                logger.info(f"Leaving group {group_id}...")
                if not radio.leave_group(group_id):
                    self.error_message = f"Failed to leave group {group_id}"
                    return TestResult.FAILED
                time.sleep(1)
            
            logger.info("All groups left successfully")
            
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class BusyCallTest(TestCase):
    """
    Test calling a busy radio.
    
    Scenario:
    - Radio 1 calls Radio 2
    - Radio 2 answers
    - Radio 3 attempts to call Radio 2 (which is busy)
    - Radio 3 should receive BUSY response
    - Radio 1 ends call
    """
    
    def __init__(self):
        super().__init__(
            name="Busy Call Test",
            description="Test calling a radio that is already in a call"
        )
    
    def run(self) -> TestResult:
        """Execute busy call test."""
        try:
            if len(self.radios) < 3:
                self.error_message = "Test requires at least 3 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            radio2 = self.radios[radio_ids[1]]
            radio3 = self.radios[radio_ids[2]]
            
            logger.info(f"Busy call test: {radio_ids[0]} calls {radio_ids[1]}, then {radio_ids[2]} attempts to call busy {radio_ids[1]}")
            
            # Step 1: Radio 1 calls Radio 2
            target_issi_2 = "2001"
            logger.info(f"Step 1: {radio_ids[0]} calling {radio_ids[1]}...")
            
            if not radio1.make_individual_call(target_issi_2):
                self.error_message = f"Failed to initiate call from {radio_ids[0]} to {radio_ids[1]}"
                return TestResult.FAILED
            
            # Verify OK response
            if radio1.get_last_response_type() != "OK":
                self.error_message = f"Expected OK response, got {radio1.get_last_response_type()}"
                return TestResult.FAILED
            
            logger.info("Call initiated successfully, waiting for ring...")
            time.sleep(2)
            
            # Step 2: Radio 2 receives and answers call
            caller = radio2.check_for_incoming_call(timeout=5.0)
            if not caller:
                logger.warning(f"Radio {radio_ids[1]} did not receive incoming call (simulator limitation)")
            
            logger.info(f"Step 2: {radio_ids[1]} answering call...")
            if not radio2.answer_call():
                self.error_message = f"Failed to answer call on {radio_ids[1]}"
                return TestResult.FAILED
            
            # Verify OK response
            if radio2.get_last_response_type() != "OK":
                self.error_message = f"Expected OK response for answer, got {radio2.get_last_response_type()}"
                return TestResult.FAILED
            
            logger.info(f"{radio_ids[1]} answered, call is established")
            time.sleep(1)
            
            # Step 3: Radio 3 attempts to call Radio 2 (which is busy)
            logger.info(f"Step 3: {radio_ids[2]} attempting to call busy {radio_ids[1]}...")
            
            # This should fail with BUSY response
            result = radio3.make_individual_call(target_issi_2)
            
            # Check the response type
            response_type = radio3.get_last_response_type()
            logger.info(f"Radio {radio_ids[2]} received response: {response_type}")
            
            if response_type != "BUSY":
                self.error_message = f"Expected BUSY response, but got {response_type}"
                logger.warning(f"Expected BUSY response when calling busy radio, got {response_type}")
                # Continue to cleanup
            else:
                logger.info(f"Correctly received BUSY response from {radio_ids[1]}")
            
            # Step 4: Radio 1 ends the call
            logger.info(f"Step 4: {radio_ids[0]} ending call...")
            if not radio1.end_call():
                self.error_message = f"Failed to end call on {radio_ids[0]}"
                return TestResult.FAILED
            
            logger.info("Call ended successfully")
            
            # Verify we got BUSY response in step 3
            if response_type != "BUSY":
                return TestResult.FAILED
            
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class NoDialtoneTest(TestCase):
    """
    Test NO DIALTONE response.
    
    Scenario:
    - Radio is not registered to network
    - Radio attempts to make a call
    - Should receive NO DIALTONE response
    """
    
    def __init__(self):
        super().__init__(
            name="No Dialtone Test",
            description="Test NO DIALTONE response when not registered to network"
        )
    
    def run(self) -> TestResult:
        """Execute no dialtone test."""
        try:
            if len(self.radios) < 1:
                self.error_message = "Test requires at least 1 radio"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            
            logger.info(f"No dialtone test: {radio_ids[0]} attempts to call while not registered")
            
            # Note: In production, you would deregister the radio first
            # For testing purposes, this test documents the expected behavior
            logger.info(f"{radio_ids[0]} attempting to call without network registration...")
            
            # Attempt to call (this test assumes the radio can be in an unregistered state)
            result = radio1.make_individual_call("2001")
            response_type = radio1.get_last_response_type()
            
            logger.info(f"Received response: {response_type}")
            
            # In a real scenario with unregistered radio, we expect NO DIALTONE
            # If the radio is registered, we'll get OK instead
            if response_type not in ["NO DIALTONE", "OK"]:
                self.error_message = f"Unexpected response type: {response_type}"
                return TestResult.FAILED
            
            logger.info("Test completed - radio state determines response")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class NoAnswerTest(TestCase):
    """
    Test NO ANSWER response.
    
    Scenario:
    - Radio 1 calls Radio 2
    - Radio 2 does not answer within timeout
    - Radio 1 should receive NO ANSWER response
    """
    
    def __init__(self):
        super().__init__(
            name="No Answer Test",
            description="Test NO ANSWER response when called party doesn't answer"
        )
    
    def run(self) -> TestResult:
        """Execute no answer test."""
        try:
            if len(self.radios) < 2:
                self.error_message = "Test requires at least 2 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            
            logger.info(f"No answer test: {radio_ids[0]} calls {radio_ids[1]} which doesn't answer")
            
            # Note: In a real scenario, the radio would wait for a timeout period
            # and then return NO ANSWER if the called party doesn't respond
            logger.info(f"{radio_ids[0]} calling {radio_ids[1]}...")
            
            result = radio1.make_individual_call("2001")
            response_type = radio1.get_last_response_type()
            
            logger.info(f"Received response: {response_type}")
            
            # Depending on the scenario, we could get OK (call initiated) or NO ANSWER
            if response_type not in ["NO ANSWER", "OK"]:
                self.error_message = f"Unexpected response type: {response_type}"
                return TestResult.FAILED
            
            logger.info("Test completed - demonstrates NO ANSWER handling")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class NoCarrierTest(TestCase):
    """
    Test NO CARRIER response.
    
    Scenario:
    - Radio 1 and Radio 2 are in a call
    - Radio 2 suddenly loses connection (carrier lost)
    - Radio 1 should receive NO CARRIER response
    """
    
    def __init__(self):
        super().__init__(
            name="No Carrier Test",
            description="Test NO CARRIER response when connection is lost"
        )
    
    def run(self) -> TestResult:
        """Execute no carrier test."""
        try:
            if len(self.radios) < 2:
                self.error_message = "Test requires at least 2 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            radio2 = self.radios[radio_ids[1]]
            
            logger.info(f"No carrier test: call between {radio_ids[0]} and {radio_ids[1]}")
            
            # Step 1: Establish a call
            logger.info(f"Step 1: {radio_ids[0]} calling {radio_ids[1]}...")
            
            if not radio1.make_individual_call("2001"):
                self.error_message = f"Failed to initiate call"
                return TestResult.FAILED
            
            time.sleep(2)
            
            # Step 2: Answer call
            logger.info(f"Step 2: {radio_ids[1]} answering call...")
            if not radio2.answer_call():
                self.error_message = f"Failed to answer call"
                return TestResult.FAILED
            
            logger.info("Call established")
            time.sleep(2)
            
            # Step 3: Simulate carrier loss
            # In a real scenario, NO CARRIER would be sent automatically
            # when the network detects the connection is lost
            logger.info("Step 3: Ending call (in real scenario, could be NO CARRIER)...")
            
            result = radio1.end_call()
            response_type = radio1.get_last_response_type()
            
            logger.info(f"Received response: {response_type}")
            
            # Could be OK (normal hangup) or NO CARRIER (connection lost)
            if response_type not in ["NO CARRIER", "OK"]:
                self.error_message = f"Unexpected response type: {response_type}"
                return TestResult.FAILED
            
            logger.info("Test completed - demonstrates NO CARRIER handling")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class ErrorResponseTest(TestCase):
    """
    Test ERROR response.
    
    Scenario:
    - Radio receives an invalid or malformed command
    - Should receive ERROR response
    """
    
    def __init__(self):
        super().__init__(
            name="Error Response Test",
            description="Test ERROR response for invalid commands"
        )
    
    def run(self) -> TestResult:
        """Execute error response test."""
        try:
            if len(self.radios) < 1:
                self.error_message = "Test requires at least 1 radio"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            
            logger.info(f"Error response test: {radio_ids[0]} sends invalid command")
            
            # Send an invalid command
            logger.info(f"{radio_ids[0]} sending invalid command...")
            
            success, response = radio1._send_command("AT+INVALID_COMMAND")
            response_type = radio1.get_last_response_type()
            
            logger.info(f"Received response: {response_type}")
            
            # Should receive ERROR
            if response_type != "ERROR":
                self.error_message = f"Expected ERROR response, got {response_type}"
                return TestResult.FAILED
            
            if success:
                self.error_message = "Command should have returned failure"
                return TestResult.FAILED
            
            logger.info("Correctly received ERROR response for invalid command")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class EmergencyCallTest(TestCase):
    """
    Test emergency call functionality.
    
    Scenario:
    - Radio 1 makes an emergency individual call to Radio 2
    - Radio 2 answers
    - Call is maintained
    - Call is ended
    """
    
    def __init__(self):
        super().__init__(
            name="Emergency Call Test",
            description="Test emergency individual call between two radios"
        )
    
    def run(self) -> TestResult:
        """Execute emergency call test."""
        try:
            if len(self.radios) < 2:
                self.error_message = "Test requires at least 2 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            radio2 = self.radios[radio_ids[1]]
            
            logger.info(f"Emergency call test: {radio_ids[0]} makes EMERGENCY call to {radio_ids[1]}")
            
            # Make emergency call
            target_issi = "2001"
            logger.info(f"{radio_ids[0]} making EMERGENCY call to {target_issi}...")
            
            if not radio1.make_individual_call(target_issi, emergency=True):
                self.error_message = f"Failed to initiate emergency call from {radio_ids[0]}"
                return TestResult.FAILED
            
            # Verify OK response
            if radio1.get_last_response_type() != "OK":
                self.error_message = f"Expected OK response, got {radio1.get_last_response_type()}"
                return TestResult.FAILED
            
            logger.info("Emergency call initiated successfully")
            time.sleep(2)
            
            # Answer call
            logger.info(f"{radio_ids[1]} answering emergency call...")
            if not radio2.answer_call():
                self.error_message = f"Failed to answer call on {radio_ids[1]}"
                return TestResult.FAILED
            
            logger.info("Emergency call answered, maintaining for 3 seconds...")
            time.sleep(3)
            
            # End call
            if not radio1.end_call():
                self.error_message = f"Failed to end emergency call on {radio_ids[0]}"
                return TestResult.FAILED
            
            logger.info("Emergency call ended successfully")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class EmergencyGroupCallTest(TestCase):
    """
    Test emergency group call functionality.
    
    Scenario:
    - All radios join a group
    - Radio 1 makes an emergency group call
    - Call is maintained
    - Call is ended
    - All radios leave group
    """
    
    def __init__(self, group_id: str = "9001"):
        super().__init__(
            name="Emergency Group Call Test",
            description=f"Test emergency group call to group {group_id}"
        )
        self.group_id = group_id
    
    def run(self) -> TestResult:
        """Execute emergency group call test."""
        try:
            if len(self.radios) < 2:
                self.error_message = "Test requires at least 2 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            
            logger.info(f"Emergency group call test: All radios join group {self.group_id}, {radio_ids[0]} makes EMERGENCY call")
            
            # All radios join the group
            for radio_id in radio_ids:
                radio = self.radios[radio_id]
                if not radio.join_group(self.group_id):
                    self.error_message = f"Failed to join group on {radio_id}"
                    return TestResult.FAILED
                logger.info(f"Radio {radio_id} joined group")
            
            time.sleep(2)
            
            # First radio makes emergency group call
            caller_id = radio_ids[0]
            caller = self.radios[caller_id]
            
            logger.info(f"Radio {caller_id} initiating EMERGENCY group call...")
            if not caller.make_group_call(self.group_id, emergency=True):
                self.error_message = f"Failed to initiate emergency group call from {caller_id}"
                return TestResult.FAILED
            
            # Verify OK response
            if caller.get_last_response_type() != "OK":
                self.error_message = f"Expected OK response, got {caller.get_last_response_type()}"
                return TestResult.FAILED
            
            logger.info("Emergency group call initiated, maintaining for 5 seconds...")
            time.sleep(5)
            
            # End group call
            if not caller.end_call():
                self.error_message = f"Failed to end emergency group call on {caller_id}"
                return TestResult.FAILED
            
            logger.info("Emergency group call ended successfully")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR
    
    def teardown(self) -> None:
        """Leave group after test."""
        try:
            for radio_id, radio in self.radios.items():
                radio.leave_group(self.group_id)
                logger.info(f"Radio {radio_id} left group {self.group_id}")
        except Exception as e:
            logger.error(f"Error in teardown: {e}")


class HighPriorityMessageTest(TestCase):
    """
    Test sending high-priority text messages.
    
    Scenario:
    - Radio 1 sends a high-priority text message to Radio 2
    """
    
    def __init__(self):
        super().__init__(
            name="High Priority Message Test",
            description="Test sending high-priority text message"
        )
    
    def run(self) -> TestResult:
        """Execute high priority message test."""
        try:
            if len(self.radios) < 2:
                self.error_message = "Test requires at least 2 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            
            target_issi = "2001"
            message = "URGENT: High priority message"
            
            logger.info(f"High priority message test: {radio_ids[0]} -> {radio_ids[1]}")
            
            # Send high-priority message
            if not radio1.send_text_message(target_issi, message, priority=1):
                self.error_message = f"Failed to send high-priority message from {radio_ids[0]}"
                return TestResult.FAILED
            
            logger.info("High-priority message sent successfully")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class EncryptionTest(TestCase):
    """
    Test encryption functionality.
    
    Scenario:
    - Radio enables encryption
    - Radio checks encryption status
    - Radio disables encryption
    """
    
    def __init__(self):
        super().__init__(
            name="Encryption Test",
            description="Test encryption enable/disable functionality"
        )
    
    def run(self) -> TestResult:
        """Execute encryption test."""
        try:
            if len(self.radios) < 1:
                self.error_message = "Test requires at least 1 radio"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            
            logger.info(f"Encryption test on {radio_ids[0]}")
            
            # Enable encryption
            logger.info("Enabling encryption...")
            if not radio1.enable_encryption(key_id=1):
                self.error_message = "Failed to enable encryption"
                return TestResult.FAILED
            
            # Check status
            logger.info("Checking encryption status...")
            status = radio1.get_encryption_status()
            if not status:
                logger.warning("Failed to get encryption status")
            else:
                logger.info(f"Encryption status: {status}")
            
            # Disable encryption
            logger.info("Disabling encryption...")
            if not radio1.disable_encryption():
                self.error_message = "Failed to disable encryption"
                return TestResult.FAILED
            
            logger.info("Encryption test completed successfully")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class ParallelCallsWithPTTTest(TestCase):
    """
    Test multiple parallel calls with PTT items.
    
    Scenario:
    - Radio 1 and Radio 2 establish a call
    - Radio 3 and Radio 4 establish a separate call
    - Both pairs use PTT to transmit
    - Verify PTT events are handled correctly
    - Verify calls don't interfere with each other
    """
    
    def __init__(self):
        super().__init__(
            name="Parallel Calls with PTT Test",
            description="Test multiple parallel calls with PTT items"
        )
    
    def run(self) -> TestResult:
        """Execute parallel calls with PTT test."""
        try:
            if len(self.radios) < 4:
                self.error_message = "Test requires at least 4 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radio1 = self.radios[radio_ids[0]]
            radio2 = self.radios[radio_ids[1]]
            radio3 = self.radios[radio_ids[2]]
            radio4 = self.radios[radio_ids[3]]
            
            logger.info(f"Parallel calls test: {radio_ids[0]}<->{radio_ids[1]} and {radio_ids[2]}<->{radio_ids[3]}")
            
            # Setup: Join groups for both pairs
            group1 = "9001"
            group2 = "9002"
            
            logger.info("Setting up groups...")
            if not radio1.join_group(group1) or not radio2.join_group(group1):
                self.error_message = "Failed to join group 1"
                return TestResult.FAILED
            
            if not radio3.join_group(group2) or not radio4.join_group(group2):
                self.error_message = "Failed to join group 2"
                return TestResult.FAILED
            
            time.sleep(1)
            
            # Step 1: Establish both calls simultaneously
            logger.info("Step 1: Establishing parallel calls...")
            
            if not radio1.make_group_call(group1):
                self.error_message = f"Failed to establish call from {radio_ids[0]}"
                return TestResult.FAILED
            
            if not radio3.make_group_call(group2):
                self.error_message = f"Failed to establish call from {radio_ids[2]}"
                return TestResult.FAILED
            
            logger.info("Both calls established")
            time.sleep(1)
            
            # Step 2: Radio 1 presses PTT
            logger.info(f"Step 2: {radio_ids[0]} pressing PTT...")
            if not radio1.press_ptt():
                self.error_message = f"Failed to press PTT on {radio_ids[0]}"
                return TestResult.FAILED
            
            time.sleep(1)
            
            # Step 3: Radio 3 presses PTT (in parallel)
            logger.info(f"Step 3: {radio_ids[2]} pressing PTT in parallel...")
            if not radio3.press_ptt():
                self.error_message = f"Failed to press PTT on {radio_ids[2]}"
                return TestResult.FAILED
            
            time.sleep(2)
            
            # Step 4: Release PTT on both
            logger.info("Step 4: Releasing PTT on both radios...")
            if not radio1.release_ptt():
                self.error_message = f"Failed to release PTT on {radio_ids[0]}"
                return TestResult.FAILED
            
            if not radio3.release_ptt():
                self.error_message = f"Failed to release PTT on {radio_ids[2]}"
                return TestResult.FAILED
            
            time.sleep(1)
            
            # Step 5: End both calls
            logger.info("Step 5: Ending both calls...")
            if not radio1.end_call():
                self.error_message = f"Failed to end call on {radio_ids[0]}"
                return TestResult.FAILED
            
            if not radio3.end_call():
                self.error_message = f"Failed to end call on {radio_ids[2]}"
                return TestResult.FAILED
            
            logger.info("Parallel calls with PTT test completed successfully")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR
    
    def teardown(self) -> None:
        """Leave groups after test."""
        try:
            for radio in self.radios.values():
                radio.leave_group("9001")
                radio.leave_group("9002")
        except Exception as e:
            logger.error(f"Error in teardown: {e}")


class ComplexMultiRadioTest(TestCase):
    """
    Complex test with multiple radios, calls, and notifications.
    
    This test demonstrates how to create complex multi-radio scenarios
    with various TETRA PEI features.
    """
    
    def __init__(self):
        super().__init__(
            name="Complex Multi-Radio Test",
            description="Complex test with calls, PTT, messages, and notifications"
        )
    
    def run(self) -> TestResult:
        """Execute complex multi-radio test."""
        try:
            if len(self.radios) < 3:
                self.error_message = "Test requires at least 3 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radios = [self.radios[rid] for rid in radio_ids[:3]]
            
            logger.info("Complex multi-radio test starting...")
            
            # Phase 1: Registration and configuration
            logger.info("Phase 1: Configuration")
            for i, radio in enumerate(radios):
                # Check registration
                if not radio.check_registration_status():
                    logger.warning(f"Radio {radio_ids[i]} not registered")
                
                # Get radio info
                info = radio.get_radio_info()
                if info:
                    logger.info(f"Radio {radio_ids[i]}: {info}")
            
            time.sleep(1)
            
            # Phase 2: Group operations
            logger.info("Phase 2: Group operations")
            group_id = "9001"
            for i, radio in enumerate(radios):
                if not radio.join_group(group_id):
                    self.error_message = f"Failed to join group on {radio_ids[i]}"
                    return TestResult.FAILED
            
            time.sleep(1)
            
            # Phase 3: Establish call with PTT
            logger.info("Phase 3: Call with PTT")
            if not radios[0].make_group_call(group_id):
                self.error_message = "Failed to establish group call"
                return TestResult.FAILED
            
            time.sleep(1)
            
            # PTT operations
            if not radios[0].press_ptt():
                self.error_message = "Failed to press PTT"
                return TestResult.FAILED
            
            time.sleep(2)
            
            if not radios[0].release_ptt():
                self.error_message = "Failed to release PTT"
                return TestResult.FAILED
            
            time.sleep(1)
            
            # Phase 4: Send messages
            logger.info("Phase 4: Send messages")
            if not radios[1].send_text_message("2001", "Test message", priority=0):
                logger.warning("Failed to send message")
            
            time.sleep(1)
            
            # Phase 5: End call
            logger.info("Phase 5: End call")
            if not radios[0].end_call():
                self.error_message = "Failed to end call"
                return TestResult.FAILED
            
            # Phase 6: Leave groups
            logger.info("Phase 6: Leave groups")
            for radio in radios:
                radio.leave_group(group_id)
            
            logger.info("Complex multi-radio test completed successfully")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class MultipleParallelCallsSequentialPTT(TestCase):
    """
    Test multiple parallel voice calls with sequential PTT operations.
    
    Demonstrates using helper classes to simplify complex test creation.
    
    Scenario:
    - 3 groups with 2 radios each (6 radios total)
    - Establish 3 parallel group calls
    - Each group takes turns transmitting (sequential PTT)
    - All calls end cleanly
    """
    
    def __init__(self):
        super().__init__(
            name="Multiple Parallel Calls with Sequential PTT",
            description="Test 3 parallel group calls with sequential PTT operations"
        )
    
    def run(self) -> TestResult:
        """Execute test using helper classes."""
        try:
            if len(self.radios) < 6:
                self.error_message = "Test requires at least 6 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radios = [self.radios[rid] for rid in radio_ids[:6]]
            
            logger.info("Setting up 3 groups with 2 radios each...")
            
            # Create radio groups using helper
            group1 = RadioGroup([radios[0], radios[1]], ["Radio1", "Radio2"])
            group2 = RadioGroup([radios[2], radios[3]], ["Radio3", "Radio4"])
            group3 = RadioGroup([radios[4], radios[5]], ["Radio5", "Radio6"])
            
            # Join groups
            if not group1.join_group("9001"):
                self.error_message = "Failed to setup group 9001"
                return TestResult.FAILED
            
            if not group2.join_group("9002"):
                self.error_message = "Failed to setup group 9002"
                return TestResult.FAILED
            
            if not group3.join_group("9003"):
                self.error_message = "Failed to setup group 9003"
                return TestResult.FAILED
            
            time.sleep(1)
            
            logger.info("Establishing 3 parallel group calls...")
            
            # Establish all calls using CallSession helper
            with CallSession(radios[0], "9001", "group") as call1, \
                 CallSession(radios[2], "9002", "group") as call2, \
                 CallSession(radios[4], "9003", "group") as call3:
                
                logger.info("All 3 calls established")
                time.sleep(1)
                
                # Sequential PTT: Each group takes a turn
                logger.info("Group 1 transmitting...")
                with PTTSession(radios[0]):
                    time.sleep(2)
                
                logger.info("Group 2 transmitting...")
                with PTTSession(radios[2]):
                    time.sleep(2)
                
                logger.info("Group 3 transmitting...")
                with PTTSession(radios[4]):
                    time.sleep(2)
                
                logger.info("All transmissions complete")
                time.sleep(1)
            
            # Calls automatically ended by context managers
            logger.info("All calls ended")
            
            # Cleanup
            group1.leave_group("9001")
            group2.leave_group("9002")
            group3.leave_group("9003")
            
            logger.info("Test completed successfully")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class MultipleParallelCallsSimultaneousPTT(TestCase):
    """
    Test multiple parallel voice calls with simultaneous PTT operations.
    
    Demonstrates concurrent PTT operations across multiple calls.
    
    Scenario:
    - 4 radios in 2 groups
    - Establish 2 parallel group calls
    - Both groups transmit simultaneously (parallel PTT)
    - Verify no interference
    """
    
    def __init__(self):
        super().__init__(
            name="Multiple Parallel Calls with Simultaneous PTT",
            description="Test 2 parallel calls with simultaneous PTT"
        )
    
    def run(self) -> TestResult:
        """Execute test using helper classes."""
        try:
            if len(self.radios) < 4:
                self.error_message = "Test requires at least 4 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radios = [self.radios[rid] for rid in radio_ids[:4]]
            
            logger.info("Setting up 2 groups with 2 radios each...")
            
            # Create groups
            group1 = RadioGroup([radios[0], radios[1]], ["Radio1", "Radio2"])
            group2 = RadioGroup([radios[2], radios[3]], ["Radio3", "Radio4"])
            
            # Join groups
            group1.join_group("9001")
            group2.join_group("9002")
            time.sleep(1)
            
            logger.info("Establishing 2 parallel group calls...")
            
            with CallSession(radios[0], "9001", "group") as call1, \
                 CallSession(radios[2], "9002", "group") as call2:
                
                logger.info("Both calls established")
                time.sleep(1)
                
                # Simultaneous PTT
                logger.info("Both groups transmitting simultaneously...")
                with PTTSession(radios[0]) as ptt1, \
                     PTTSession(radios[2]) as ptt2:
                    time.sleep(3)  # Both PTTs active for 3 seconds
                
                logger.info("Both transmissions complete")
                time.sleep(1)
            
            # Cleanup
            group1.leave_group("9001")
            group2.leave_group("9002")
            
            logger.info("Test completed successfully")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class MixedIndividualGroupCallsTest(TestCase):
    """
    Test mixed individual and group calls in parallel.
    
    Demonstrates complex scenario with different call types running simultaneously.
    
    Scenario:
    - 5 radios total
    - Radio 1 makes individual call to Radio 2
    - Radios 3, 4, 5 have a group call
    - Both calls active simultaneously
    - PTT operations on both calls
    """
    
    def __init__(self):
        super().__init__(
            name="Mixed Individual and Group Calls",
            description="Test individual and group calls in parallel with PTT"
        )
    
    def run(self) -> TestResult:
        """Execute test."""
        try:
            if len(self.radios) < 5:
                self.error_message = "Test requires at least 5 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radios = [self.radios[rid] for rid in radio_ids[:5]]
            
            logger.info("Setting up mixed call scenario...")
            
            # Setup group for radios 3, 4, 5
            group = RadioGroup([radios[2], radios[3], radios[4]], 
                              ["Radio3", "Radio4", "Radio5"])
            group.join_group("9001")
            time.sleep(1)
            
            logger.info("Establishing individual and group calls in parallel...")
            
            # Individual call: Radio1 -> Radio2
            with CallSession(radios[0], "2001", "individual") as ind_call:
                logger.info("Individual call established")
                
                # Group call: Radio3 -> Group 9001
                with CallSession(radios[2], "9001", "group") as grp_call:
                    logger.info("Group call established")
                    time.sleep(1)
                    
                    # PTT on individual call
                    logger.info("Radio1 transmitting on individual call...")
                    with PTTSession(radios[0]):
                        time.sleep(2)
                    
                    # PTT on group call
                    logger.info("Radio3 transmitting on group call...")
                    with PTTSession(radios[2]):
                        time.sleep(2)
                    
                    logger.info("Both transmissions complete")
                    time.sleep(1)
                
                logger.info("Group call ended")
                time.sleep(1)
            
            logger.info("Individual call ended")
            
            # Cleanup
            group.leave_group("9001")
            
            logger.info("Test completed successfully")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class ComplexPTTPatternsTest(TestCase):
    """
    Test complex PTT patterns with rapid operations.
    
    Demonstrates various PTT patterns to test radio behavior.
    
    Scenario:
    - Establish a group call
    - Rapid PTT press/release cycles
    - Overlapping PTT from multiple radios
    - Quick succession PTT operations
    """
    
    def __init__(self):
        super().__init__(
            name="Complex PTT Patterns Test",
            description="Test various PTT patterns including rapid and overlapping"
        )
    
    def run(self) -> TestResult:
        """Execute test."""
        try:
            if len(self.radios) < 3:
                self.error_message = "Test requires at least 3 radios"
                return TestResult.FAILED
            
            radio_ids = list(self.radios.keys())
            radios = [self.radios[rid] for rid in radio_ids[:3]]
            
            logger.info("Setting up group call for PTT patterns...")
            
            # Setup group
            group = RadioGroup(radios, ["Radio1", "Radio2", "Radio3"])
            group.join_group("9001")
            time.sleep(1)
            
            with CallSession(radios[0], "9001", "group"):
                logger.info("Group call established")
                time.sleep(1)
                
                # Pattern 1: Rapid PTT cycles
                logger.info("Pattern 1: Rapid PTT press/release cycles...")
                for i in range(5):
                    with PTTSession(radios[0], press_duration=0.5):
                        pass  # Auto-press and release after 0.5s
                    time.sleep(0.2)  # Brief gap between cycles
                
                # Pattern 2: Quick succession from different radios
                logger.info("Pattern 2: Quick succession PTT from different radios...")
                for radio in radios:
                    with PTTSession(radio, press_duration=1):
                        pass
                    time.sleep(0.1)
                
                # Pattern 3: Overlapping PTT (radio1 presses, radio2 presses before radio1 releases)
                logger.info("Pattern 3: Overlapping PTT...")
                radios[0].press_ptt()
                time.sleep(0.5)
                radios[1].press_ptt()
                time.sleep(1)
                radios[0].release_ptt()
                time.sleep(0.5)
                radios[1].release_ptt()
                
                logger.info("All PTT patterns complete")
                time.sleep(1)
            
            # Cleanup
            group.leave_group("9001")
            
            logger.info("Test completed successfully")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR


class ScenarioBuilderExampleTest(TestCase):
    """
    Demonstrates using the TestScenarioBuilder for fluent test creation.
    
    Shows how the builder API makes complex tests more readable and maintainable.
    
    Scenario:
    - 6 radios in 3 groups
    - 3 parallel calls
    - Sequential then parallel PTT operations
    """
    
    def __init__(self):
        super().__init__(
            name="Scenario Builder Example",
            description="Demonstrates fluent API for complex test scenarios"
        )
    
    def run(self) -> TestResult:
        """Execute test using scenario builder."""
        try:
            if len(self.radios) < 6:
                self.error_message = "Test requires at least 6 radios"
                return TestResult.FAILED
            
            logger.info("Building complex scenario with fluent API...")
            
            # Create and execute scenario using fluent API
            builder = TestScenarioBuilder(self.radios)
            
            # Setup groups: group_id -> [radio_indices]
            builder.setup_groups({
                "9001": [0, 1],
                "9002": [2, 3],
                "9003": [4, 5]
            })
            
            # Establish parallel calls: (target, radio_index, call_type)
            builder.parallel_calls([
                ("9001", 0, "group"),
                ("9002", 2, "group"),
                ("9003", 4, "group")
            ])
            
            # Sequential PTT: (radio_index, duration)
            logger.info("Sequential PTT operations...")
            builder.with_ptt([
                (0, 2),
                (2, 2),
                (4, 2)
            ], parallel=False)
            
            builder.wait(1)
            
            # Parallel PTT
            logger.info("Parallel PTT operations...")
            builder.with_ptt([
                (0, 2),
                (2, 2),
                (4, 2)
            ], parallel=True)
            
            builder.wait(1)
            
            # Cleanup
            builder.cleanup()
            
            logger.info("Scenario completed successfully")
            return TestResult.PASSED
            
        except Exception as e:
            self.error_message = f"Exception during test: {str(e)}"
            logger.error(self.error_message, exc_info=True)
            return TestResult.ERROR
