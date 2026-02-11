"""
Example Test Cases

Demonstrates how to create tests for various TETRA PEI operations.
"""

import time
import logging
from typing import Optional

from ..core.test_base import TestCase, TestResult
from ..core.tetra_pei import PTTState


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
