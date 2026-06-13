import pytest
from src.coordinator.main_coordinator import MainCoordinator, CoordinatorState

def test_coordinator_initialization():
    """测试协调器初始化"""
    coordinator = MainCoordinator()
    assert coordinator.state.current_stage == "idle"
    assert len(coordinator.state.completed_stages) == 0

def test_coordinator_state():
    """测试协调器状态"""
    state = CoordinatorState()
    assert state.current_stage == "idle"
    assert state.completed_stages == []
    assert state.results == {}
