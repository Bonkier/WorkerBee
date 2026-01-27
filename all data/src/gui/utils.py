import json
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def load_json_data(path, default=None):
    """Load JSON data from file safely"""
    if default is None: default = {}
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r') as f:
            return json.load(f) or default
    except Exception as e:
        logger.error(f"Failed to load JSON {path}: {e}")
        return default

def save_json_data(path, data):
    """Save data to JSON file safely"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save JSON {path}: {e}")

def ensure_schedule_file(base_path):
    """Create default schedule.json if it doesn't exist"""
    schedule_path = os.path.join(base_path, "config", "schedule.json")
    if not os.path.exists(schedule_path):
        default_schedule = {
            "enabled": False,
            "tasks": [
                {
                    "type": "mirror",
                    "time": "08:00",
                    "days": "all",
                    "enabled": True,
                    "hard_mode": False
                },
                {
                    "type": "exp",
                    "time": "09:00",
                    "days": [0, 2, 4],
                    "enabled": True,
                    "runs": 3,
                    "stage": 6
                }
            ]
        }
        try:
            os.makedirs(os.path.dirname(schedule_path), exist_ok=True)
            save_json_data(schedule_path, default_schedule)
            logger.info("Created default schedule.json")
        except Exception as e:
            logger.error(f"Failed to create default schedule: {e}")

def format_log_line_with_time_ago(line):
    """Format log line with time ago context"""
    try:
        # Expected format: "25/01/2026 22:22:04 | ..."
        parts = line.split(' | ', 1)
        if len(parts) > 1:
            timestamp_str = parts[0]
            log_time = datetime.strptime(timestamp_str, '%d/%m/%Y %H:%M:%S')
            now = datetime.now()
            diff = now - log_time
            seconds = diff.total_seconds()
            
            if seconds < 60:
                time_ago = "Just now"
            elif seconds < 3600:
                time_ago = f"{int(seconds // 60)}m ago"
            elif seconds < 86400:
                time_ago = f"{int(seconds // 3600)}h ago"
            else:
                time_ago = f"{int(seconds // 86400)}d ago"
                
            return f"{timestamp_str} ({time_ago}) | {parts[1]}"
    except Exception:
        pass
    return line