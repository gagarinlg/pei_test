"""
Test Helper Classes

Provides helper classes and utilities to make creating complex test cases easier.
These helpers reduce boilerplate and make test intent clearer.
"""

import logging
import time
from typing import Dict, List, Optional, Callable
from contextlib import contextmanager

from .tetra_pei import TetraPEI


logger = logging.getLogger(__name__)


class CallSession:
    """
    Helper class to manage call lifecycle.
    
    Simplifies call setup, maintenance, and teardown with automatic cleanup.
    
    Example:
        with CallSession(radio1, "2001") as call:
            call.wait(2)  # Call active for 2 seconds
        # Call automatically ended
    """
    
    def __init__(self, radio: TetraPEI, target: str, call_type: str = "individual", 
                 emergency: bool = False):
        """
        Initialize call session.
        
        Args:
            radio: Radio to initiate call from
            target: Target ISSI or GSSI
            call_type: "individual" or "group"
            emergency: If True, make emergency call
        """
        self.radio = radio
        self.target = target
        self.call_type = call_type
        self.emergency = emergency
        self.established = False
    
    def __enter__(self):
        """Establish call on context entry."""
        if self.call_type == "individual":
            self.established = self.radio.make_individual_call(self.target, emergency=self.emergency)
        else:
            self.established = self.radio.make_group_call(self.target, emergency=self.emergency)
        
        if not self.established:
            raise RuntimeError(f"Failed to establish {self.call_type} call to {self.target}")
        
        logger.info(f"Call established: {self.radio.radio_id} -> {self.target} ({self.call_type})")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End call on context exit."""
        if self.established:
            self.radio.end_call()
            logger.info(f"Call ended: {self.radio.radio_id} -> {self.target}")
        return False
    
    def wait(self, seconds: float):
        """Wait for specified seconds while call is active."""
        time.sleep(seconds)


class PTTSession:
    """
    Helper class to manage PTT operations.
    
    Simplifies PTT press/release with automatic release on exit.
    
    Example:
        with PTTSession(radio1):
            time.sleep(2)  # PTT pressed for 2 seconds
        # PTT automatically released
    """
    
    def __init__(self, radio: TetraPEI, press_duration: Optional[float] = None):
        """
        Initialize PTT session.
        
        Args:
            radio: Radio to control PTT
            press_duration: If provided, auto-release after this many seconds
        """
        self.radio = radio
        self.press_duration = press_duration
        self.pressed = False
    
    def __enter__(self):
        """Press PTT on context entry."""
        self.pressed = self.radio.press_ptt()
        if not self.pressed:
            raise RuntimeError(f"Failed to press PTT on {self.radio.radio_id}")
        
        logger.info(f"PTT pressed: {self.radio.radio_id}")
        
        if self.press_duration:
            time.sleep(self.press_duration)
            self.__exit__(None, None, None)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release PTT on context exit."""
        if self.pressed:
            self.radio.release_ptt()
            logger.info(f"PTT released: {self.radio.radio_id}")
            self.pressed = False
        return False


class RadioGroup:
    """
    Helper class to manage a group of radios.
    
    Simplifies operations on multiple radios at once.
    
    Example:
        group = RadioGroup([radio1, radio2, radio3])
        group.join_group("9001")
        with group.make_call("9001"):
            # Group call active
            pass
        group.leave_group("9001")
    """
    
    def __init__(self, radios: List[TetraPEI], names: Optional[List[str]] = None):
        """
        Initialize radio group.
        
        Args:
            radios: List of radio instances
            names: Optional list of friendly names for radios
        """
        self.radios = radios
        self.names = names or [r.radio_id for r in radios]
    
    def join_group(self, group_id: str) -> bool:
        """
        Join all radios to a group.
        
        Returns:
            True if all radios joined successfully
        """
        results = []
        for radio, name in zip(self.radios, self.names):
            result = radio.join_group(group_id)
            results.append(result)
            if result:
                logger.info(f"{name} joined group {group_id}")
            else:
                logger.error(f"{name} failed to join group {group_id}")
        
        return all(results)
    
    def leave_group(self, group_id: str) -> bool:
        """
        Remove all radios from a group.
        
        Returns:
            True if all radios left successfully
        """
        results = []
        for radio, name in zip(self.radios, self.names):
            result = radio.leave_group(group_id)
            results.append(result)
            if result:
                logger.info(f"{name} left group {group_id}")
        
        return all(results)
    
    @contextmanager
    def make_call(self, group_id: str, caller_index: int = 0):
        """
        Make a group call from one of the radios.
        
        Args:
            group_id: Group to call
            caller_index: Index of radio to initiate call (default: 0)
        
        Yields:
            The calling radio
        """
        caller = self.radios[caller_index]
        caller_name = self.names[caller_index]
        
        if not caller.make_group_call(group_id):
            raise RuntimeError(f"Failed to establish group call from {caller_name}")
        
        logger.info(f"Group call established: {caller_name} -> {group_id}")
        
        try:
            yield caller
        finally:
            caller.end_call()
            logger.info(f"Group call ended: {caller_name} -> {group_id}")
    
    def get(self, index: int) -> TetraPEI:
        """Get radio at index."""
        return self.radios[index]
    
    def __len__(self):
        return len(self.radios)
    
    def __getitem__(self, index):
        return self.radios[index]


class TestScenarioBuilder:
    """
    Fluent API builder for creating test scenarios.
    
    Makes complex test scenarios more readable and maintainable.
    
    Example:
        scenario = TestScenarioBuilder(radios)
        scenario.setup_groups({
            "9001": [0, 1],  # radios 0 and 1 in group 9001
            "9002": [2, 3]   # radios 2 and 3 in group 9002
        }).parallel_calls([
            ("9001", 0),  # call from radio 0 to group 9001
            ("9002", 2)   # call from radio 2 to group 9002
        ]).with_ptt([
            (0, 2),  # radio 0 presses PTT for 2 seconds
            (2, 2)   # radio 2 presses PTT for 2 seconds
        ]).execute()
    """
    
    def __init__(self, radios: Dict[str, TetraPEI]):
        """
        Initialize scenario builder.
        
        Args:
            radios: Dictionary of radio_id to TetraPEI instance
        """
        self.radios = radios
        self.radio_list = list(radios.values())
        self.radio_ids = list(radios.keys())
        self.groups_setup = {}
        self.calls = []
        self.ptt_actions = []
        self.cleanup_actions = []
    
    def setup_groups(self, groups: Dict[str, List[int]]) -> 'TestScenarioBuilder':
        """
        Setup group memberships.
        
        Args:
            groups: Dict mapping group_id to list of radio indices
        
        Returns:
            Self for chaining
        """
        self.groups_setup = groups
        
        for group_id, radio_indices in groups.items():
            for idx in radio_indices:
                self.radio_list[idx].join_group(group_id)
                logger.info(f"{self.radio_ids[idx]} joined group {group_id}")
        
        return self
    
    def parallel_calls(self, calls: List[tuple]) -> 'TestScenarioBuilder':
        """
        Establish parallel calls.
        
        Args:
            calls: List of tuples (target, radio_index, call_type)
                  where call_type is "group" or "individual"
        
        Returns:
            Self for chaining
        """
        self.calls = calls
        
        for target, radio_idx, *call_type_tuple in calls:
            call_type = call_type_tuple[0] if call_type_tuple else "group"
            radio = self.radio_list[radio_idx]
            
            if call_type == "individual":
                success = radio.make_individual_call(target)
            else:
                success = radio.make_group_call(target)
            
            if not success:
                raise RuntimeError(f"Failed to establish call from {self.radio_ids[radio_idx]}")
            
            logger.info(f"Call established: {self.radio_ids[radio_idx]} -> {target} ({call_type})")
        
        time.sleep(1)  # Allow calls to establish
        return self
    
    def with_ptt(self, ptt_actions: List[tuple], parallel: bool = False) -> 'TestScenarioBuilder':
        """
        Execute PTT actions.
        
        Args:
            ptt_actions: List of tuples (radio_index, duration_seconds)
            parallel: If True, press PTT on all radios before releasing any
        
        Returns:
            Self for chaining
        """
        self.ptt_actions = ptt_actions
        
        if parallel:
            # Press all PTTs first
            for radio_idx, _ in ptt_actions:
                radio = self.radio_list[radio_idx]
                if not radio.press_ptt():
                    raise RuntimeError(f"Failed to press PTT on {self.radio_ids[radio_idx]}")
                logger.info(f"PTT pressed: {self.radio_ids[radio_idx]}")
            
            # Wait for max duration
            max_duration = max(duration for _, duration in ptt_actions)
            time.sleep(max_duration)
            
            # Release all PTTs
            for radio_idx, _ in ptt_actions:
                radio = self.radio_list[radio_idx]
                radio.release_ptt()
                logger.info(f"PTT released: {self.radio_ids[radio_idx]}")
        else:
            # Sequential PTT operations
            for radio_idx, duration in ptt_actions:
                radio = self.radio_list[radio_idx]
                if not radio.press_ptt():
                    raise RuntimeError(f"Failed to press PTT on {self.radio_ids[radio_idx]}")
                logger.info(f"PTT pressed: {self.radio_ids[radio_idx]}")
                
                time.sleep(duration)
                
                radio.release_ptt()
                logger.info(f"PTT released: {self.radio_ids[radio_idx]}")
        
        return self
    
    def wait(self, seconds: float) -> 'TestScenarioBuilder':
        """
        Wait for specified seconds.
        
        Args:
            seconds: Duration to wait
        
        Returns:
            Self for chaining
        """
        time.sleep(seconds)
        return self
    
    def cleanup(self):
        """
        Cleanup all resources (end calls, leave groups).
        """
        # End all calls
        for _, radio_idx, *_ in self.calls:
            radio = self.radio_list[radio_idx]
            radio.end_call()
            logger.info(f"Call ended on {self.radio_ids[radio_idx]}")
        
        # Leave all groups
        for group_id, radio_indices in self.groups_setup.items():
            for idx in radio_indices:
                self.radio_list[idx].leave_group(group_id)
                logger.info(f"{self.radio_ids[idx]} left group {group_id}")
    
    def execute(self):
        """
        Execute the scenario (placeholder for future enhancements).
        """
        # Currently just a marker method
        # Could add validation, timing, etc.
        pass
