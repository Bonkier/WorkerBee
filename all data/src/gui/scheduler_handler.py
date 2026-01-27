import os
import json
import logging
from datetime import datetime
import src.gui.process_handler as process_handler

logger = logging.getLogger("gui_launcher")

class SchedulerHandler:
    def __init__(self, base_path, shared_vars, start_callbacks):
        self.base_path = base_path
        self.shared_vars = shared_vars
        self.start_callbacks = start_callbacks
        self.last_scheduled_execution = {}

    def check_scheduler(self):
        """Check schedule.json and start tasks if needed"""
        try:
            schedule_path = os.path.join(self.base_path, "config", "schedule.json")
            if not os.path.exists(schedule_path):
                return

            try:
                with open(schedule_path, 'r') as f:
                    schedule_data = json.load(f)
            except json.JSONDecodeError:
                return
                
            if not schedule_data.get("enabled", False):
                return
                
            # Don't start if something is already running
            if process_handler.is_any_process_running():
                return
                
            now = datetime.now()
            current_day = now.weekday() # 0=Monday, 6=Sunday
            current_time_str = now.strftime("%H:%M")
            
            tasks = schedule_data.get("tasks", [])
            
            for i, task in enumerate(tasks):
                if not task.get("enabled", True):
                    continue
                    
                # Check days
                days = task.get("days", "all")
                if days != "all":
                    if isinstance(days, list) and current_day not in days:
                        continue
                    elif isinstance(days, int) and current_day != days:
                        continue
                
                # Check time
                if task.get("time", "") != current_time_str:
                    continue
                    
                # Check if already executed for this time slot
                exec_key = f"{i}_{now.strftime('%Y-%m-%d_%H:%M')}"
                if exec_key in self.last_scheduled_execution:
                    continue
                    
                # Execute Task
                task_type = task.get("type", "mirror")
                logger.info(f"Scheduler: Starting task {task_type} at {current_time_str}")
                
                self._execute_task(task_type, task)
                
                # Mark executed
                self.last_scheduled_execution[exec_key] = True
                if len(self.last_scheduled_execution) > 50:
                    self.last_scheduled_execution.clear()
                    self.last_scheduled_execution[exec_key] = True
                return
                
        except Exception as e:
            logger.error(f"Scheduler error: {e}")

    def _execute_task(self, task_type, task):
        if task_type == "Mirror Dungeon" or task_type == "mirror":
            if "hard_mode" in task: self.shared_vars.hard_mode.value = bool(task["hard_mode"])
            self.start_callbacks['start_mirror'](runs=task.get("runs", 1))

        elif task_type == "Exp" or task_type == "exp":
            if "runs" in task: self.shared_vars.exp_runs.value = int(task["runs"])
            if "stage" in task and task["stage"] != "latest": self.shared_vars.exp_stage.value = int(task["stage"])
            self.start_callbacks['start_exp']()
            
        elif task_type == "Threads" or task_type == "thread":
            if "runs" in task: self.shared_vars.threads_runs.value = int(task["runs"])
            if "difficulty" in task: self.shared_vars.threads_difficulty.value = int(task["difficulty"])
            self.start_callbacks['start_threads']()
        
        elif task_type == "Chain Automation":
                self.start_callbacks['start_chain']()