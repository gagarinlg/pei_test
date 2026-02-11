"""
Unit tests for test helper classes.

Tests the helper utilities that make creating complex test cases easier.
"""

import unittest
import time
from tetra_pei_test.core.radio_connection import RadioConnection
from tetra_pei_test.core.tetra_pei import TetraPEI
from tetra_pei_test.core.test_helpers import CallSession, PTTSession, RadioGroup, TestScenarioBuilder
from tetra_pei_test.simulator.radio_simulator import TetraRadioSimulator


class TestCallSession(unittest.TestCase):
    """Test CallSession helper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15050,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15050)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_individual_call_session(self):
        """Test CallSession with individual call."""
        with CallSession(self.pei, "2001", "individual") as call:
            self.assertTrue(call.established)
            call.wait(0.5)
        # Call should be ended after context exit
    
    def test_group_call_session(self):
        """Test CallSession with group call."""
        with CallSession(self.pei, "9001", "group") as call:
            self.assertTrue(call.established)
            call.wait(0.5)
    
    def test_emergency_call_session(self):
        """Test CallSession with emergency flag."""
        with CallSession(self.pei, "2001", "individual", emergency=True) as call:
            self.assertTrue(call.established)


class TestPTTSession(unittest.TestCase):
    """Test PTTSession helper."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.simulator = TetraRadioSimulator(
            radio_id="test_radio",
            host="127.0.0.1",
            port=15051,
            issi="1001"
        )
        self.simulator.start()
        time.sleep(0.5)
        
        self.connection = RadioConnection("test_radio", "127.0.0.1", 15051)
        self.connection.connect()
        self.pei = TetraPEI(self.connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.connection.is_connected():
            self.connection.disconnect()
        self.simulator.stop()
        time.sleep(0.5)
    
    def test_ptt_session(self):
        """Test PTTSession basic usage."""
        with PTTSession(self.pei) as ptt:
            self.assertTrue(ptt.pressed)
            time.sleep(0.5)
        # PTT should be released after context exit
    
    def test_ptt_session_with_duration(self):
        """Test PTTSession with auto-release duration."""
        start = time.time()
        with PTTSession(self.pei, press_duration=0.5):
            pass  # Should auto-press and release
        elapsed = time.time() - start
        # Should have taken at least 0.5 seconds
        self.assertGreaterEqual(elapsed, 0.5)


class TestRadioGroup(unittest.TestCase):
    """Test RadioGroup helper."""
    
    def setUp(self):
        """Set up test fixtures with 3 radios."""
        self.simulators = []
        self.connections = []
        self.peis = []
        
        for i in range(3):
            simulator = TetraRadioSimulator(
                radio_id=f"radio_{i+1}",
                host="127.0.0.1",
                port=15052 + i,
                issi=f"100{i+1}"
            )
            simulator.start()
            self.simulators.append(simulator)
        
        time.sleep(0.5)
        
        for i in range(3):
            connection = RadioConnection(f"radio_{i+1}", "127.0.0.1", 15052 + i)
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
    
    def test_radio_group_creation(self):
        """Test RadioGroup creation."""
        group = RadioGroup(self.peis, ["Radio1", "Radio2", "Radio3"])
        self.assertEqual(len(group), 3)
        self.assertEqual(group.get(0), self.peis[0])
    
    def test_join_leave_group(self):
        """Test group join/leave operations."""
        group = RadioGroup(self.peis)
        
        # Join group
        result = group.join_group("9001")
        self.assertTrue(result)
        
        # Leave group
        result = group.leave_group("9001")
        self.assertTrue(result)
    
    def test_make_call_context_manager(self):
        """Test making calls using context manager."""
        group = RadioGroup(self.peis)
        group.join_group("9001")
        
        with group.make_call("9001", caller_index=0) as caller:
            self.assertEqual(caller, self.peis[0])
            time.sleep(0.5)
        
        group.leave_group("9001")


class TestScenarioBuilderHelper(unittest.TestCase):
    """Test TestScenarioBuilder helper."""
    
    def setUp(self):
        """Set up test fixtures with 4 radios."""
        self.simulators = []
        self.connections = []
        self.radios = {}
        
        for i in range(4):
            simulator = TetraRadioSimulator(
                radio_id=f"radio_{i+1}",
                host="127.0.0.1",
                port=15055 + i,
                issi=f"100{i+1}"
            )
            simulator.start()
            self.simulators.append(simulator)
        
        time.sleep(0.5)
        
        for i in range(4):
            radio_id = f"radio_{i+1}"
            connection = RadioConnection(radio_id, "127.0.0.1", 15055 + i)
            connection.connect()
            self.connections.append(connection)
            self.radios[radio_id] = TetraPEI(connection)
    
    def tearDown(self):
        """Clean up test fixtures."""
        for connection in self.connections:
            if connection.is_connected():
                connection.disconnect()
        for simulator in self.simulators:
            simulator.stop()
        time.sleep(0.5)
    
    def test_scenario_builder_creation(self):
        """Test ScenarioBuilder creation."""
        builder = TestScenarioBuilder(self.radios)
        self.assertEqual(len(builder.radio_list), 4)
    
    def test_setup_groups(self):
        """Test group setup."""
        builder = TestScenarioBuilder(self.radios)
        builder.setup_groups({
            "9001": [0, 1],
            "9002": [2, 3]
        })
        self.assertEqual(len(builder.groups_setup), 2)
    
    def test_parallel_calls(self):
        """Test parallel call establishment."""
        builder = TestScenarioBuilder(self.radios)
        builder.setup_groups({
            "9001": [0, 1],
            "9002": [2, 3]
        })
        
        builder.parallel_calls([
            ("9001", 0, "group"),
            ("9002", 2, "group")
        ])
        
        # Cleanup
        builder.cleanup()
    
    def test_sequential_ptt(self):
        """Test sequential PTT operations."""
        builder = TestScenarioBuilder(self.radios)
        builder.setup_groups({"9001": [0, 1]})
        builder.parallel_calls([("9001", 0, "group")])
        
        builder.with_ptt([
            (0, 0.5),
            (1, 0.5)
        ], parallel=False)
        
        builder.cleanup()
    
    def test_parallel_ptt(self):
        """Test parallel PTT operations."""
        builder = TestScenarioBuilder(self.radios)
        builder.setup_groups({
            "9001": [0, 1],
            "9002": [2, 3]
        })
        builder.parallel_calls([
            ("9001", 0, "group"),
            ("9002", 2, "group")
        ])
        
        builder.with_ptt([
            (0, 1),
            (2, 1)
        ], parallel=True)
        
        builder.cleanup()


if __name__ == '__main__':
    unittest.main()
