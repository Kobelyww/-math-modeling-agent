from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime


class CoordinatorStatus(Enum):
    """协调器状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class Checkpoint:
    """检查点"""
    stage: str
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CoordinatorState:
    """协调器状态"""
    current_stage: str = "idle"
    completed_stages: List[str] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    checkpoints: List[Checkpoint] = field(default_factory=list)
    status: CoordinatorStatus = CoordinatorStatus.IDLE
    
    def advance_stage(self) -> None:
        """推进到下一阶段"""
        self.completed_stages.append(self.current_stage)
        stage_order = [
            "document_parsing",
            "content_understanding",
            "knowledge_extraction",
            "outline_generation",
            "question_generation",
            "quality_evaluation",
            "completed"
        ]
        current_index = stage_order.index(self.current_stage) if self.current_stage in stage_order else -1
        if current_index < len(stage_order) - 1:
            self.current_stage = stage_order[current_index + 1]
    
    def save_checkpoint(self) -> Checkpoint:
        """保存检查点"""
        checkpoint = Checkpoint(
            stage=self.current_stage,
            timestamp=datetime.now(),
            data={
                "completed_stages": self.completed_stages.copy(),
                "results": self.results.copy(),
            }
        )
        self.checkpoints.append(checkpoint)
        return checkpoint


class MainCoordinator:
    """主协调器"""
    
    def __init__(self):
        self.state = CoordinatorState()
        self.sub_coordinators: Dict[str, Any] = {}
    
    def register_sub_coordinator(self, name: str, coordinator: Any) -> None:
        """注册子协调器"""
        self.sub_coordinators[name] = coordinator
    
    async def invoke(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """执行协调流程"""
        self.state.status = CoordinatorStatus.RUNNING
        self.state.current_stage = "document_parsing"
        
        try:
            result = {
                "status": "success",
                "message": "协调流程执行完成",
                "data": {}
            }
            
            self.state.status = CoordinatorStatus.COMPLETED
            self.state.advance_stage()
            
            return result
        except Exception as e:
            self.state.status = CoordinatorStatus.FAILED
            self.state.errors.append({
                "stage": self.state.current_stage,
                "error": str(e),
                "timestamp": datetime.now()
            })
            raise
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "current_stage": self.state.current_stage,
            "completed_stages": self.state.completed_stages,
            "status": self.state.status.value,
            "errors": len(self.state.errors)
        }
