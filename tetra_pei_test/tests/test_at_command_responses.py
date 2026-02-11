"""
Unit tests for AT command response handling.

Tests all valid AT command final responses:
- OK
- ERROR
- NO CARRIER
- NO DIALTONE
- BUSY
- NO ANSWER
"""

import unittest
import time
from tetra_pei_test.core.radio_connection import RadioConnection
from tetra_pei_test.core.tetra_pei import TetraPEI, ATCommandResponse
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator


class TestATCommandResponses(unittest.TestCase):
    """Test cases for AT command response handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Start simulator
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15010,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        # Create connection and PEI
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15010)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_ok_response(self):
        """Test OK response."""
        result = self.pei.test_connection()
        self.assertTrue(result)
        self.assertEqual(self.pei.get_last_response_type(), "OK")
    
    def test_error_response(self):
        """Test ERROR response."""
        # Send invalid command
        success, response = self.pei._send_command("AT+INVALID_COMMAND")
        self.assertFalse(success)
        self.assertEqual(self.pei.get_last_response_type(), "ERROR")
    
    def test_busy_response(self):
        """Test BUSY response when calling a busy radio."""
        # Make radio busy
        self.simulator.set_busy_state("9999")
        
        # Try to make a call (should get BUSY)
        result = self.pei.make_individual_call("2001")
        self.assertFalse(result)
        self.assertEqual(self.pei.get_last_response_type(), "BUSY")
        
        # Clear busy state
        self.simulator.clear_busy_state()
    
    def test_no_dialtone_response(self):
        """Test NO DIALTONE response when not registered."""
        # Unregister the radio
        self.simulator.registered = False
        
        # Try to make a call (should get NO DIALTONE)
        result = self.pei.make_individual_call("2001")
        self.assertFalse(result)
        self.assertEqual(self.pei.get_last_response_type(), "NO DIALTONE")
        
        # Re-register
        self.simulator.registered = True
    
    def test_no_answer_response(self):
        """Test NO ANSWER response when called party doesn't answer."""
        # Configure simulator to return NO ANSWER
        self.simulator.simulate_no_answer = True
        
        # Try to make a call (should get NO ANSWER)
        result = self.pei.make_individual_call("2001")
        self.assertFalse(result)
        self.assertEqual(self.pei.get_last_response_type(), "NO ANSWER")
        
        # Reset flag
        self.simulator.simulate_no_answer = False
    
    def test_no_carrier_response(self):
        """Test NO CARRIER response when call is dropped."""
        # Make a call first
        result = self.pei.make_individual_call("2001")
        self.assertTrue(result)
        self.assertEqual(self.pei.get_last_response_type(), "OK")
        
        # Configure simulator to return NO CARRIER on hangup
        self.simulator.simulate_no_carrier = True
        
        # End call (should get NO CARRIER)
        result = self.pei.end_call()
        self.assertFalse(result)
        self.assertEqual(self.pei.get_last_response_type(), "NO CARRIER")
    
    def test_response_type_enum(self):
        """Test ATCommandResponse enum values."""
        self.assertEqual(ATCommandResponse.OK.value, "OK")
        self.assertEqual(ATCommandResponse.ERROR.value, "ERROR")
        self.assertEqual(ATCommandResponse.NO_CARRIER.value, "NO CARRIER")
        self.assertEqual(ATCommandResponse.NO_DIALTONE.value, "NO DIALTONE")
        self.assertEqual(ATCommandResponse.BUSY.value, "BUSY")
        self.assertEqual(ATCommandResponse.NO_ANSWER.value, "NO ANSWER")
    
    def test_multiple_commands_responses(self):
        """Test multiple commands with different responses."""
        # Test OK
        result = self.pei.test_connection()
        self.assertTrue(result)
        self.assertEqual(self.pei.get_last_response_type(), "OK")
        
        # Test ERROR
        success, _ = self.pei._send_command("AT+INVALID")
        self.assertFalse(success)
        self.assertEqual(self.pei.get_last_response_type(), "ERROR")
        
        # Test OK again
        result = self.pei.test_connection()
        self.assertTrue(result)
        self.assertEqual(self.pei.get_last_response_type(), "OK")
    
    def test_valid_response_terminators(self):
        """Test that all valid response terminators are defined."""
        expected_terminators = [
            "OK\r\n",
            "ERROR\r\n",
            "NO CARRIER\r\n",
            "NO DIALTONE\r\n",
            "BUSY\r\n",
            "NO ANSWER\r\n"
        ]
        self.assertEqual(self.pei.VALID_RESPONSE_TERMINATORS, expected_terminators)


class TestBusyCallScenario(unittest.TestCase):
    """Test busy call scenarios with multiple radios."""
    
    def setUp(self):
        """Set up test fixtures with 3 radios."""
        self.simulators = []
        self.connections = []
        self.peis = []
        
        # Create 3 simulated radios
        for i in range(3):
            simulator = TetraRadioSimulator(
                radio_id=f"radio_{i+1}",
                host="127.0.0.1",
                port=15020 + i,
                issi=f"100{i+1}"
            )
            simulator.start()
            self.simulators.append(simulator)
        
        time.sleep(0.5)
        
        # Create connections and PEI instances
        for i in range(3):
            connection = RadioConnection(f"radio_{i+1}", "127.0.0.1", 15020 + i)
            connection.connect()
            self.connections.append(connection)
            self.peis.append(TetraPEI(connection))
    
    def tearDown(self):
        """Clean up test fixtures."""
        for connection in self.connections:
            if connection.is_connected():
                connection.disconnect()
        for simulator in self.simulators:
            simulator.stop()
        time.sleep(0.5)
    
    def test_busy_call_scenario(self):
        """Test complete busy call scenario."""
        radio1_pei = self.peis[0]
        radio2_pei = self.peis[1]
        radio3_pei = self.peis[2]
        radio3_sim = self.simulators[2]
        
        # Put radio 3 in a call first (simulating it's already busy)
        radio3_sim.set_busy_state("9999")
        
        # Now try to make another call on radio 3 - should get BUSY
        result = radio3_pei.make_individual_call("1001")
        self.assertFalse(result)
        self.assertEqual(radio3_pei.get_last_response_type(), "BUSY")
        
        # Clear busy state
        radio3_sim.clear_busy_state()
        
        # Now should be able to make the call
        result = radio3_pei.make_individual_call("1001")
        self.assertTrue(result)
        self.assertEqual(radio3_pei.get_last_response_type(), "OK")
    
    def test_third_radio_gets_busy_when_calling_occupied_radio(self):
        """Test that a radio gets BUSY when it's already in a call."""
        radio2_pei = self.peis[1]
        radio2_sim = self.simulators[1]
        
        # Put radio 2 in busy state (already in a call)
        radio2_sim.set_busy_state("1001")
        
        # Radio 2 tries to make another call while already busy - should get BUSY
        result = radio2_pei.make_individual_call("1003")
        self.assertFalse(result)
        self.assertEqual(radio2_pei.get_last_response_type(), "BUSY")
        
        # Clear busy state
        radio2_sim.clear_busy_state()
        
        # Now should be able to call
        result = radio2_pei.make_individual_call("1003")
        self.assertTrue(result)
        self.assertEqual(radio2_pei.get_last_response_type(), "OK")


if __name__ == '__main__':
    unittest.main()
