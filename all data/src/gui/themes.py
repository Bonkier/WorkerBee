import os
import json
import logging

logger = logging.getLogger(__name__)

def load_available_themes(base_path):
    """Load all theme JSON files from the themes directory"""
    themes_dir = os.path.join(base_path, "themes")

    sleek_mono_path = os.path.join(themes_dir, "sleek_mono.json")
    default_dark_theme = sleek_mono_path if os.path.exists(sleek_mono_path) else "blue"
    
    themes = {
        "Dark": {"mode": "Dark", "theme": default_dark_theme},
        "Blue": {"mode": "Dark", "theme": "blue"},
        "Green": {"mode": "Dark", "theme": "green"},
        "Dark-Blue": {"mode": "Dark", "theme": "dark-blue"},
        "Light": {"mode": "Light", "theme": "blue"},
        "System": {"mode": "System", "theme": "blue"}
    }
    
    try:
        if os.path.exists(themes_dir):
            for filename in os.listdir(themes_dir):
                if filename.endswith('.json'):
                    theme_name = os.path.splitext(filename)[0]
                    theme_path = os.path.join(themes_dir, filename)

                    try:
                        with open(theme_path, 'r') as f:
                            theme_data = json.load(f)
                            if 'CTk' in theme_data:
                                themes[theme_name] = {"mode": "Dark", "theme": theme_path}
                    except (json.JSONDecodeError, KeyError):
                        continue
    except Exception as e:
        logger.error(f"Error loading themes: {e}")
    
    return themes