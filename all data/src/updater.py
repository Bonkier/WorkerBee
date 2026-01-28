import os
import sys
import json
import time
import urllib.request
import urllib.error
import zipfile
import shutil
import logging
import subprocess
import platform
import threading
import fnmatch
from datetime import datetime

logger = logging.getLogger("updater")

EXCLUDED_PATHS = [
    "backups/",    
    "temp/",      
    "logs/",
    "*.log",       
    "profiles/",   
    "*.exe",       
    "*.lnk",       
    "*.url",       
    "bootstrapper.py", 
    "setup.vbs",   
    "update.zip",  
    "staged_updater", 
    "pictures/CustomFuse/CustomEgoGifts/", 
    "config/stats.json", 
    "config/schedule.json"
]

CONFIG_MERGE_FILES = [
    "config/gui_config.json",
    "config/pack_priority.json",
    "config/delayed_pack_priority.json", 
    "config/pack_exceptions.json",
    "config/delayed_pack_exceptions.json",
    "config/squad_order.json",
    "config/delayed_squad_order.json",
    "config/status_selection.json",
    "config/fusion_exceptions.json",
    "config/grace_selection.json",
    "config/exp_team_selection.json",
    "config/threads_team_selection.json",
    "config/image_thresholds.json"
]

class Updater:
    
    def __init__(self, repo_owner, repo_name, current_version_file="version.json", 
                 backup_folder="backups", temp_folder="temp", api_url=None, pre_exit_callback=None):
        """Initialize updater with repository info and file paths"""
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.current_version_file = current_version_file
        self.backup_folder = backup_folder
        self.temp_folder = temp_folder
        self.exclusions = EXCLUDED_PATHS
        self.pre_exit_callback = pre_exit_callback

        if api_url is None:
            self.api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        else:
            self.api_url = api_url

        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            script_path = os.path.abspath(__file__)
            self.base_path = os.path.dirname(script_path)

        if os.path.basename(self.base_path) == "src":
            self.all_data_dir = os.path.dirname(self.base_path)
            self.parent_dir = os.path.dirname(self.all_data_dir)
        elif os.path.basename(self.base_path) == "all data":
            self.all_data_dir = self.base_path
            self.parent_dir = os.path.dirname(self.all_data_dir)
        else:
            self.parent_dir = self.base_path
            self.all_data_dir = os.path.join(self.parent_dir, "all data")

        self.version_file_path = os.path.join(self.all_data_dir, current_version_file)

        self.backup_path = os.path.join(self.parent_dir, backup_folder)

        self.temp_path = os.path.join(self.parent_dir, temp_folder)

        os.makedirs(self.backup_path, exist_ok=True)
        os.makedirs(self.temp_path, exist_ok=True)
    
    def _retry_file_operation(self, operation, operation_desc, max_retries=5, delay=0.5):
        """
        Retry a file operation with exponential backoff to handle file locks and permission issues
        """
        for attempt in range(max_retries):
            try:
                operation()
                if attempt > 0:
                    logger.info(f"Successfully {operation_desc} on attempt {attempt + 1}")
                return True
            except (OSError, IOError, PermissionError) as e:
                error_type = type(e).__name__
                if attempt == max_retries - 1:
                    logger.error(f"RETRY FAILED: Unable to {operation_desc} after {max_retries} attempts. Final error: {error_type}: {e}")
                    raise
                else:
                    wait_time = delay * (2 ** attempt) 
                    logger.warning(f"RETRY {attempt + 1}/{max_retries}: {error_type} while trying to {operation_desc}: {e}")
                    logger.info(f"Waiting {wait_time:.1f}s before retry...")
                    time.sleep(wait_time)
        return False
        
    def get_current_version(self):
        try:
            if os.path.exists(self.version_file_path):
                with open(self.version_file_path, 'r') as f:
                    version = f.read().strip()
                    return version if version else 'v0'
            return 'v0'  
        except Exception as e:
            logger.error(f"Error reading version file: {e}")
            return 'v0'
            
    def get_latest_version(self):
        ver_json_info = None
        release_info = None

        try:
            version_file_url = f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/main/all%20data/version.json?t={int(time.time())}"

            req = urllib.request.Request(version_file_url, headers={'User-Agent': 'WorkerBee-Updater'})
            with urllib.request.urlopen(req) as response:
                if response.getcode() == 200:
                    repo_version = response.read().decode().strip()
                    if repo_version:
                        try:
                            commits_url = f"{self.api_url}/commits/main"
                            req_commit = urllib.request.Request(commits_url, headers={'User-Agent': 'WorkerBee-Updater'})
                            with urllib.request.urlopen(req_commit) as response_commit:
                                commit_data = json.loads(response_commit.read().decode())
                                commit_hash = commit_data['sha']
                                download_url = f"{self.api_url}/zipball/{commit_hash}"
                        except Exception as e:
                            logger.warning(f"Failed to get commit hash, falling back to main zipball: {e}")
                            download_url = f"{self.api_url}/zipball/main"
                            
                        ver_json_info = (repo_version, download_url)
        except Exception as e:
            logger.warning(f"Could not read version.json from repository: {e}")

        try:
            release_url = f"{self.api_url}/releases/latest"

            req = urllib.request.Request(release_url, headers={'User-Agent': 'WorkerBee-Updater'})
            with urllib.request.urlopen(req) as response:
                if response.getcode() == 200:
                    release_data = json.loads(response.read().decode())
                    release_info = (release_data['tag_name'], release_data['zipball_url'])
        except Exception as e:
            pass

        if ver_json_info and release_info:
            v_json = self.parse_version(ver_json_info[0])
            v_rel = self.parse_version(release_info[0])
            
            if v_rel > v_json:
                return release_info
            else:
                return ver_json_info
        elif ver_json_info:
            return ver_json_info
        elif release_info:
            return release_info

        try:
            commits_url = f"{self.api_url}/commits/main"
            req = urllib.request.Request(commits_url, headers={'User-Agent': 'WorkerBee-Updater'})
            with urllib.request.urlopen(req) as response:
                commit_data = json.loads(response.read().decode())
                commit_hash = commit_data['sha']
                commit_date = commit_data['commit']['committer']['date'].split('T')[0].replace('-', '.')
                download_url = f"{self.api_url}/zipball/{commit_hash}"
                return f"commit-{commit_date}", download_url
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return None, None
    
    def parse_version(self, version_str):
        """Parse version string into a comparable tuple"""
        clean_ver = version_str.lower().strip()
        if clean_ver.startswith('v'):
            clean_ver = clean_ver[1:]

        if clean_ver.startswith('commit-'):
            return (0, 0, 0) 

        parts = clean_ver.split('.')
        parsed_parts = []
        
        for p in parts:
            num_str = ""
            for char in p:
                if char.isdigit():
                    num_str += char
                else:
                    break
            parsed_parts.append(int(num_str) if num_str else 0)
                
        return tuple(parsed_parts)

    def check_for_updates(self):
        current_version = self.get_current_version()
        latest_version, download_url = self.get_latest_version()
        
        if latest_version is None:
            logger.warning("Failed to retrieve latest version information")
            return False, None, None

        current_clean = current_version.strip() if current_version else ""
        latest_clean = latest_version.strip() if latest_version else ""

        logger.info(f"Checking for updates... Local: '{current_clean}', Remote: '{latest_clean}'")

        curr_tuple = self.parse_version(current_clean)
        lat_tuple = self.parse_version(latest_clean)
        logger.debug(f"Comparing versions: Local {curr_tuple} vs Remote {lat_tuple}")

        if lat_tuple > curr_tuple:
            logger.info(f"Update available: {current_clean} -> {latest_clean}")
            return True, latest_clean, download_url
        else:
            if lat_tuple < curr_tuple:
                logger.info(f"Local version ({current_clean}) is newer than remote ({latest_clean}). Skipping update.")
            else:
                logger.info(f"Versions match ({current_clean}), no update needed")
            return False, latest_clean, None

    def should_exclude(self, file_path, dest_file_path=None):
        normalized_path = file_path.replace("\\", "/")

        if normalized_path.startswith(f"{self.backup_folder}/") or normalized_path == self.backup_folder:
            return True
            
        if normalized_path.startswith(f"{self.temp_folder}/") or normalized_path == self.temp_folder:
            return True
        
        for pattern in self.exclusions:
            if normalized_path == pattern:
                return True

            if pattern.endswith("/") and normalized_path.startswith(pattern):
                return True

            if "*" in pattern and fnmatch.fnmatch(normalized_path, pattern):
                return True
        
        return False
    
    def download_update(self, download_url):
        try:
            for item in os.listdir(self.temp_path):
                item_path = os.path.join(self.temp_path, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            logger.info(f"Cleared temp directory {self.temp_path}")
        except Exception as e:
            logger.warning(f"Error clearing temp directory: {e}")
        
        try:
            os.makedirs(self.temp_path, exist_ok=True)

            zip_path = os.path.join(self.temp_path, 'update.zip')
            logger.info(f"Downloading update from {download_url}")

            req = urllib.request.Request(download_url, headers={'User-Agent': 'WorkerBee-Updater'})
            with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
                
            logger.info(f"Download completed: {zip_path}")
            return zip_path
        except Exception as e:
            logger.error(f"Error downloading update: {e}")
            return None
    
    def modify_backup_config(self, backup_dir):
        possible_config_paths = [
            os.path.join(backup_dir, "all data", "config", "gui_config.json"),
            os.path.join(backup_dir, "config", "gui_config.json"),
        ]

        config_path = None
        for path in possible_config_paths:
            if os.path.exists(path):
                config_path = path
                break

        if not config_path:
            for root, dirs, files in os.walk(backup_dir):
                if "gui_config.json" in files:
                    config_path = os.path.join(root, "gui_config.json")
                    break
        
        if not config_path or not os.path.exists(config_path):
            logger.warning(f"Could not find gui_config.json in backup directory {backup_dir}")
            return False
        
        try:
            logger.info(f"Modifying backup config at: {config_path}")

            config_data = {}
            with open(config_path, 'r') as f:
                config_data = json.load(f)

            if 'Settings' not in config_data:
                config_data['Settings'] = {}

            old_auto_update = config_data['Settings'].get('auto_update', 'Unknown')
            old_notifications = config_data['Settings'].get('update_notifications', 'Unknown')

            config_data['Settings']['auto_update'] = False
            config_data['Settings']['update_notifications'] = False

            config_data['Settings']['_backup_version'] = True

            with open(config_path, 'w') as configfile:
                json.dump(config_data, configfile, indent=2)
            
            logger.info(f"   - auto_update: {old_auto_update} -> False")
            logger.info(f"   - update_notifications: {old_notifications} -> False")
            logger.info(f"   - Location: {config_path}")
            logger.info("   - Original config remains unchanged!")
            
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Error modifying backup config: {e}")
            logger.info("Backup creation will continue, but update loop prevention failed")
            return False
    
    def backup_current_version(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_dir = os.path.join(self.backup_path, backup_name)
        
        logger.info(f"Creating backup at {backup_dir}")
        
        try:
            try:
                os.makedirs(self.backup_path, exist_ok=True)
                os.makedirs(backup_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create backup directory at {backup_dir}: {e}")
                return None

            source_dir = self.parent_dir
            logger.info(f"Backing up contents from {source_dir}")

            file_count = 0
            dir_count = 0

            for item in os.listdir(source_dir):
                item_path = os.path.join(source_dir, item)
                backup_item_path = os.path.join(backup_dir, item)

                if item == self.backup_folder or item == self.temp_folder or item == "extracted":
                    logger.info(f"Skipping {item} folder from backup")
                    continue
                
                try:
                    if os.path.isdir(item_path):
                        def ignore_func(src, names):
                            return [n for n in names if 
                                    n == self.backup_folder or 
                                    n == self.temp_folder or 
                                    n == "extracted" or
                                    n.endswith('.log')]
                                
                        shutil.copytree(item_path, backup_item_path, 
                                      ignore=ignore_func)
                        dir_count += 1
                        logger.info(f"Backed up directory: {item}")
                    else:
                        if item.endswith('.log'):
                            logger.info(f"Skipping log file: {item}")
                            continue
                            
                        shutil.copy2(item_path, backup_item_path)
                        file_count += 1
                        logger.info(f"Backed up file: {item}")
                except Exception as e:
                    logger.error(f"Failed to backup {item}: {e}")
            
            logger.info(f"Backup completed successfully: {file_count} files and {dir_count} directories")

            logger.info("Modifying backup config to prevent update loops...")
            self.modify_backup_config(backup_dir)
            
            return backup_dir
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None
    
    def apply_update(self, zip_path):
        if self._is_staged_update():
            return self._perform_staged_update()
            
        if not zip_path or not os.path.exists(zip_path):
            logger.error("Invalid zip file path")
            return False
            
        try:
            logger.info(f"Extracting update to {self.temp_path}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_path)

            repo_dir = None

            if "all data" in os.listdir(self.temp_path) and os.path.isdir(os.path.join(self.temp_path, "all data")):
                repo_dir = self.temp_path
            else:
                subdirs = [d for d in os.listdir(self.temp_path) if os.path.isdir(os.path.join(self.temp_path, d)) and d != "extracted"]
                for d in subdirs:
                    if "all data" in os.listdir(os.path.join(self.temp_path, d)):
                        repo_dir = os.path.join(self.temp_path, d)
                        break
            
            if not repo_dir:
                logger.error("Invalid update structure: 'all data' folder not found in update")
                return False
            
            logger.info(f"Found repository directory: {repo_dir}")

            new_version_path = os.path.join(repo_dir, "all data", "version.json")
            if os.path.exists(new_version_path):
                try:
                    with open(new_version_path, 'r') as f:
                        new_version = f.read().strip()
                    
                    current_version = self.get_current_version()

                    new_ver_tuple = self.parse_version(new_version)
                    curr_ver_tuple = self.parse_version(current_version)

                    if new_ver_tuple <= curr_ver_tuple:
                        logger.warning(f"Downloaded update version ({new_version}) is not newer than current version ({current_version}). Aborting update to prevent loop.")
                        return False
                except Exception as e:
                    logger.warning(f"Failed to verify version in update package: {e}")

            if platform.system() == "Windows":
                return self._run_batch_update(repo_dir)

            temp_config_backup = self.handle_config_merging(repo_dir)
            
            self._copy_directory_with_exclusions(repo_dir, self.parent_dir)

            self._handle_deleted_files(repo_dir)
            
            if temp_config_backup:
                self.merge_configs_from_temp(temp_config_backup)
            
            logger.info("Update applied successfully")
            return True
        except Exception as e:
            logger.error(f"Error applying update: {e}")
            return False
    
    def _copy_directory_with_exclusions(self, src_dir, dest_dir):
        os.makedirs(dest_dir, exist_ok=True)
        
        file_count = 0
        dir_count = 0

        for root, dirs, files in os.walk(src_dir):
            rel_path = os.path.relpath(root, src_dir)

            if rel_path != "." and self.should_exclude(rel_path.replace("\\", "/")):
                logger.info(f"Skipping excluded directory: {rel_path}")

                for excluded_dir in list(dirs):
                    if self.should_exclude(os.path.join(rel_path, excluded_dir).replace("\\", "/")):
                        dirs.remove(excluded_dir)
                continue

            for file in files:
                if rel_path == ".":
                    file_rel_path = file
                else:
                    file_rel_path = os.path.join(rel_path, file).replace("\\", "/")

                src_file = os.path.join(root, file)
                dest_file = os.path.join(dest_dir, rel_path, file)

                if self.should_exclude(file_rel_path, dest_file):
                    logger.info(f"Skipping excluded file: {file_rel_path}")
                    continue

                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                
                try:
                    if os.path.samefile(src_file, __file__) if os.path.exists(dest_file) else False:
                        logger.info(f"Skipping update to self: {file_rel_path}")
                        continue

                    if os.path.exists(dest_file):
                        self._retry_file_operation(lambda: os.remove(dest_file), f"remove {dest_file}")

                    self._retry_file_operation(lambda: shutil.copy2(src_file, dest_file), f"copy {src_file} to {dest_file}")
                    file_count += 1
                    logger.debug(f"Updated file: {file_rel_path}")
                except Exception as e:
                    logger.error(f"Failed to update file {file_rel_path}: {e}")
        
        logger.info(f"Update copied {file_count} files")
    
    def _handle_deleted_files(self, extracted_repo_dir):
        repo_files = set()
        for root, dirs, files in os.walk(extracted_repo_dir):
            dirs_to_remove = []
            for d in dirs:
                rel_path = os.path.relpath(os.path.join(root, d), extracted_repo_dir).replace("\\", "/")
                if self.should_exclude(rel_path):
                    dirs_to_remove.append(d)

            for d in dirs_to_remove:
                dirs.remove(d)
                
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, extracted_repo_dir)

                normalized_path = rel_path.replace("\\", "/")

                if not self.should_exclude(normalized_path):
                    repo_files.add(normalized_path)
        
        app_files = set()
        for root, dirs, files in os.walk(self.parent_dir):
            rel_root = os.path.relpath(root, self.parent_dir).replace("\\", "/")
            if self.should_exclude(rel_root):

                dirs[:] = []
                continue
                
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.parent_dir)

                normalized_path = rel_path.replace("\\", "/")

                if not self.should_exclude(normalized_path):
                    app_files.add(normalized_path)

        deleted_files = app_files - repo_files

        deleted_count = 0
        for file_path in deleted_files:
            if self.should_exclude(file_path):
                logger.info(f"Protected excluded file from deletion: {file_path}")
                continue
                
            full_path = os.path.join(self.parent_dir, file_path)
            try:
                if os.path.samefile(full_path, __file__) if os.path.exists(full_path) else False:
                    logger.info(f"Skipping deletion of self: {file_path}")
                    continue
                    
                os.remove(full_path)
                deleted_count += 1
                logger.info(f"Removed deleted file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to remove deleted file {file_path}: {e}")
        
        logger.info(f"Removed {deleted_count} deleted files")

        for root, dirs, files in os.walk(self.parent_dir, topdown=False):
            rel_path = os.path.relpath(root, self.parent_dir).replace("\\", "/")
            if self.should_exclude(rel_path):
                continue
                
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                rel_dir_path = os.path.relpath(dir_path, self.parent_dir).replace("\\", "/")

                if self.should_exclude(rel_dir_path):
                    continue

                try:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        logger.info(f"Removed empty directory: {rel_dir_path}")
                except OSError as e:
                    logger.debug(f"Could not remove directory {rel_dir_path}: {e}")
    
    def handle_config_merging(self, repo_dir):
        """
        Handle smart config merging:
        1. Backup user configs to temp
        2. Allow new configs to be installed 
        3. Merge user settings back into new configs
        4. Auto-cleanup temp configs
        """
        logger.info("Starting config merging process")

        temp_config_backup = os.path.join(self.temp_path, "config_backup")
        os.makedirs(temp_config_backup, exist_ok=True)
        
        try:
            config_dir = os.path.join(self.all_data_dir, "config")
            if os.path.exists(config_dir):
                for config_file in CONFIG_MERGE_FILES:
                    config_filename = os.path.basename(config_file)
                    user_config_path = os.path.join(config_dir, config_filename)
                    backup_config_path = os.path.join(temp_config_backup, config_filename)
                    
                    if os.path.exists(user_config_path):
                        shutil.copy2(user_config_path, backup_config_path)
                        logger.info(f"Backed up user config: {config_filename}")

            logger.info("User configs backed up to temp, allowing new configs to install")
            
            return temp_config_backup
            
        except Exception as e:
            logger.error(f"Error during config backup: {e}")
            return None
    
    def merge_configs_from_temp(self, temp_config_backup):
        """
        Merge user settings from temp backup into newly installed configs
        """
        logger.info("Merging user settings into new configs")
        
        try:
            config_dir = os.path.join(self.all_data_dir, "config")
            
            for config_file in CONFIG_MERGE_FILES:
                config_filename = os.path.basename(config_file)
                user_backup_path = os.path.join(temp_config_backup, config_filename)
                current_config_path = os.path.join(config_dir, config_filename)
                
                if os.path.exists(user_backup_path) and os.path.exists(current_config_path):
                    self._merge_single_config(user_backup_path, current_config_path)
                    logger.info(f"Merged config: {config_filename}")
                elif os.path.exists(user_backup_path):
                    shutil.copy2(user_backup_path, current_config_path)
                    logger.info(f"Restored user config (no new version): {config_filename}")

            shutil.rmtree(temp_config_backup, ignore_errors=True)
            logger.info("Config merging completed, temp files cleaned up")
            
        except Exception as e:
            logger.error(f"Error during config merging: {e}")
    
    def _merge_single_config(self, user_config_path, new_config_path):
        """
        Merge a single config file: user values take priority, new keys get added
        """
        try:
            with open(user_config_path, 'r') as f:
                user_config = json.load(f)
        except:
            logger.warning(f"Failed to load user config: {user_config_path}")
            return
        
        try:
            with open(new_config_path, 'r') as f:
                new_config = json.load(f)
        except:
            logger.warning(f"Failed to load new config: {new_config_path}")
            shutil.copy2(user_config_path, new_config_path)
            return

        merged_config = self._deep_merge_configs(new_config, user_config)

        with open(new_config_path, 'w') as f:
            json.dump(merged_config, f, indent=2)
        
        logger.debug(f"Successfully merged: {os.path.basename(new_config_path)}")
    
    def _deep_merge_configs(self, default_config, user_config):
        """
        Deep merge configs - user values override defaults, new keys from default are added
        """
        if isinstance(default_config, dict) and isinstance(user_config, dict):
            result = default_config.copy()
            for key, value in user_config.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._deep_merge_configs(result[key], value)
                else:
                    result[key] = value
            return result
        else:
            return user_config if user_config is not None else default_config

    def update_version_file(self, version):
        try:
            with open(self.version_file_path, 'w') as f:
                f.write(version)
                
            logger.info(f"Version file updated to {version}")
            return True
        except Exception as e:
            logger.error(f"Error updating version file: {e}")
            return False
    
    def clean_temp_files(self):
        if os.path.exists(self.temp_path):
            try:
                for item in os.listdir(self.temp_path):
                    item_path = os.path.join(self.temp_path, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                logger.info("Temporary files cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up temporary files: {e}")
    
    def restart_application(self):
        try:
            logger.info("Restarting application")

            os.makedirs(self.temp_path, exist_ok=True)

            if getattr(sys, 'frozen', False):
                cmd = [sys.executable]
            else:
                gui_launcher_path = os.path.join(self.all_data_dir, "gui_launcher.py")
                cmd = [sys.executable, gui_launcher_path]

            cmd.append("--updated")

            restart_script_path = os.path.join(self.temp_path, "restart.py")
            restart_log_path = os.path.join(self.temp_path, "restart.log")
            restart_log_path_esc = restart_log_path.replace('\\', '\\\\')
            
            with open(restart_script_path, "w") as f:
                f.write(f"""
import os
import sys
import time
import subprocess

# Redirect output to file to prevent hanging on closed console
try:
    sys.stdout = open('{restart_log_path_esc}', 'w')
    sys.stderr = sys.stdout
except:
    pass

# Wait a moment to ensure files are fully written
time.sleep(3)

# Launch the application
cmd = {repr(cmd)}
print(f"Launching application with command: {{cmd}}")

try:
    if sys.platform == 'win32':
        subprocess.Popen(cmd, creationflags=0x08000000, close_fds=True) # CREATE_NO_WINDOW
    else:
        subprocess.Popen(cmd, start_new_session=True, close_fds=True)
    print("Application launched successfully")
except Exception as e:
    print(f"Error launching application: {{e}}")
""")
            
            if platform.system() == "Windows":
                subprocess.Popen([sys.executable, restart_script_path], 
                              creationflags=0x08000000, close_fds=True)
            else:
                subprocess.Popen([sys.executable, restart_script_path], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL, 
                             stdin=subprocess.DEVNULL,
                             start_new_session=True)

            logger.info("Restart script launched")
            return True
            
        except Exception as e:
            logger.error(f"Error restarting application: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count=3):
        """Remove old backup folders, keeping only the most recent ones"""
        try:
            if not os.path.exists(self.backup_path):
                return

            backup_dirs = []
            for item in os.listdir(self.backup_path):
                item_path = os.path.join(self.backup_path, item)
                if os.path.isdir(item_path) and item.startswith("backup_"):
                    backup_dirs.append(item_path)

            backup_dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)

            for old_backup in backup_dirs[keep_count:]:
                try:
                    shutil.rmtree(old_backup)
                    logger.info(f"Removed old backup: {os.path.basename(old_backup)}")
                except Exception as e:
                    logger.warning(f"Failed to remove old backup {old_backup}: {e}")
            
            if len(backup_dirs) > keep_count:
                logger.info(f"Cleaned up {len(backup_dirs) - keep_count} old backups, kept {keep_count} most recent")
                
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
    
    def perform_update(self, create_backup=True, auto_restart=True, preserve_only_last_3=True):
        backup_path = None
        if create_backup:
            backup_path = self.backup_current_version()
            if not backup_path:
                return False, "Failed to create safety backup"
        else:
            logger.info("Skipping backup creation as requested")

        update_available, latest_version, download_url = self.check_for_updates()
        
        if not update_available or download_url is None:
            logger.info("No updates available or failed to get update information")
            if not create_backup and backup_path and os.path.exists(backup_path):
                try:
                    shutil.rmtree(backup_path)
                    logger.info("Cleaned up unnecessary backup")
                except:
                    pass
            return False, "No updates available"

        zip_path = self.download_update(download_url)
        if not zip_path:
            return False, "Failed to download update"

        if not self.apply_update(zip_path):
            return False, "Failed to apply update"

        self.update_version_file(latest_version)

        if not create_backup and backup_path and os.path.exists(backup_path):
            try:
                shutil.rmtree(backup_path)
                logger.info("Cleaned up unwanted backup after successful update")
            except:
                pass

        if create_backup and preserve_only_last_3:
            self.cleanup_old_backups(keep_count=3)

        self.clean_temp_files()
        
        if auto_restart:
            self.restart_application()
        
        return True, f"Successfully updated to {latest_version}"
    
    def check_and_update_async(self, callback=None, create_backup=False, auto_restart=True, preserve_only_last_3=True):
        def update_thread():
            result, message = self.perform_update(create_backup, auto_restart, preserve_only_last_3)
            if callback:
                callback(result, message)
        
        thread = threading.Thread(target=update_thread)
        thread.daemon = True
        thread.start()
        return thread

    def _run_batch_update(self, repo_dir):
        """Create and run a batch script to handle the update process safely"""
        try:
            batch_script_path = os.path.join(self.temp_path, "install_update.bat")
            vbs_script_path = os.path.join(self.temp_path, "silent_updater.vbs")
            current_pid = os.getpid()

            if getattr(sys, 'frozen', False):
                executable = sys.executable
                args = "--updated"
            else:
                executable = sys.executable
                if platform.system() == "Windows" and "python.exe" in executable.lower():
                    pythonw = executable.lower().replace("python.exe", "pythonw.exe")
                    if os.path.exists(pythonw):
                        executable = pythonw
                
                script_path = os.path.join(self.all_data_dir, "gui_launcher.py")
                args = f'"{script_path}" --updated'

            self.handle_config_merging(repo_dir)

            batch_content = f"""@echo off
echo Waiting for WorkerBee to close...
ping 127.0.0.1 -n 4 > NUL

echo Force closing PID {current_pid} and children...
taskkill /F /PID {current_pid} /T > NUL 2>&1

echo Updating files...
xcopy "{repo_dir}\\*" "{self.parent_dir}\\" /E /Y /I /Q > NUL

echo Restarting WorkerBee...
start "" "{executable}" {args}

echo Done.
exit
"""
            with open(batch_script_path, "w") as f:
                f.write(batch_content)

            with open(vbs_script_path, "w") as f:
                f.write('Set WshShell = CreateObject("WScript.Shell")\n')
                f.write(f'WshShell.Run chr(34) & "{batch_script_path}" & chr(34), 0, False\n')
                f.write('Set WshShell = Nothing\n')

            if self.pre_exit_callback:
                try:
                    self.pre_exit_callback()
                except Exception as e:
                    logger.error(f"Error in pre-exit callback: {e}")
            
            logger.info(f"Launching silent updater: {vbs_script_path}")

            subprocess.Popen(["wscript.exe", vbs_script_path], shell=False, close_fds=True)

            os._exit(0)
            
        except Exception as e:
            logger.error(f"Error running batch update: {e}")
            return False

    def _is_staged_update(self):
        return False


def check_for_updates(repo_owner, repo_name, callback=None):
    repo_owner = "Bonkier"
    repo_name = "WorkerBee"
        
    try:
        updater = Updater(repo_owner, repo_name)
        update_available, version, download_url = updater.check_for_updates()
        
        if update_available:
            message = f"Update available: {version}"
            logger.info(message)
            
            if callback:
                callback(True, message, True)
            return True
        else:
            message = "You have the latest version"
            if callback:
                callback(True, message, False)
            return False
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        if callback:
            callback(False, f"Error: {e}", False)
        return False

def auto_update(repo_owner, repo_name, create_backup=False, preserve_only_last_3=True, callback=None, pre_exit_callback=None):
    repo_owner = "Bonkier"
    repo_name = "WorkerBee"
        
    try:
        updater = Updater(repo_owner, repo_name, pre_exit_callback=pre_exit_callback)
        return updater.check_and_update_async(callback, create_backup, preserve_only_last_3=preserve_only_last_3)
    except Exception as e:
        logger.error(f"Error starting auto-update: {e}")
        if callback:
            callback(False, f"Error: {e}")
        return None

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%d/%m/%Y %H:%M:%S'
    )
    check_for_updates("Bonkier", "WorkerBee")