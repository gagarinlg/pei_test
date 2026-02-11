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
