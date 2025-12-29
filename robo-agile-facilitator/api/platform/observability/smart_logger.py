import shutil
import time
import json
import os
import threading
from datetime import datetime
from typing import Optional

class SmartLogger:
    LEVEL_PRIORITY = {
        "DEBUG": 0,
        "INFO": 1,
        "WARNING": 2,
        "ERROR": 3,
        "CRITICAL": 4
    }
    _instance = None


    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def log(cls, level, message, category=None, params=None, max_inline_chars=100):
        cls.instance()._log(level, message, category, params, max_inline_chars)


    def __init__(self, 
                 main_log_path=None, 
                 detail_log_dir=None,
                 blacklisted_log_path=None,
                 blacklisted_detail_log_dir=None,
                 min_level=None,
                 include_all_min_level=None,
                 console_output=None,
                 file_output=None,
                 remove_log_on_create=None): 
        self.main_log_path = self._get_env_variable(
            main_log_path, "MAIN_LOG_PATH", "logs/app_flow.jsonl"
        )
        self.detail_log_dir = self._get_env_variable(
            detail_log_dir, "DETAIL_LOG_DIR", "logs/details"
        )
        self.blacklisted_log_path = self._get_env_variable(
            blacklisted_log_path, "BLACKLISTED_LOG_PATH", "logs/app_flow_blacklisted.jsonl"
        )
        self.blacklisted_detail_log_dir = self._get_env_variable(
            blacklisted_detail_log_dir, "BLACKLISTED_DETAIL_LOG_DIR", "logs/details_blacklisted"
        )
        self.min_level = self._get_env_variable(
            min_level, "MIN_LEVEL", "ERROR"
        )
        self.include_all_min_level = self._get_env_variable(
            include_all_min_level, "INCLUDE_ALL_MIN_LEVEL", "ERROR"
        )
        self.console_output = self._get_env_variable(
            str(console_output) if console_output is not None else None, "CONSOLE_OUTPUT", "True"
        ) == "True"
        self.file_output = self._get_env_variable(
            str(file_output) if file_output is not None else None, "FILE_OUTPUT", "False"
        ) == "True"
        self.remove_log_on_create = self._get_env_variable(
            str(remove_log_on_create) if remove_log_on_create is not None else None, "REMOVE_LOG_ON_CREATE", "False"
        ) == "True"

        self._lock = threading.Lock()
        self._last_timestamp = None
        self._timestamp_counter = 0
        self.blacklist_categories = self._load_blacklist_categories()

        if self.file_output:
            dir_paths = [
                os.path.dirname(self.main_log_path), self.detail_log_dir, 
                os.path.dirname(self.blacklisted_log_path), self.blacklisted_detail_log_dir
            ]
            for dir_path in dir_paths:
                if self.remove_log_on_create and os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            for dir_path in dir_paths:
                os.makedirs(dir_path, exist_ok=True)
    
    def _get_env_variable(self, direct_value: Optional[str], env_key: str, default: str) -> str:
        if direct_value is not None:
            return direct_value
        return os.environ.get(f"SMART_LOGGER_{env_key}", default)

    def _load_blacklist_categories(self):
        """
        환경변수에서 블랙리스트 카테고리 목록을 로드
        SMART_LOGGER_BLACKLIST_CATEGORIES 환경변수에서 ","로 구분된 카테고리 목록을 파싱
        """
        blacklist_env = os.environ.get("SMART_LOGGER_BLACKLIST_CATEGORIES", "")
        if not blacklist_env:
            return set()
        
        categories = [cat.strip() for cat in blacklist_env.split(",") if cat.strip()]
        return set(categories)

    def _is_blacklisted(self, category):
        """
        주어진 카테고리가 블랙리스트에 포함되어 있는지 확인
        """
        if category is None:
            return False
        return category in self.blacklist_categories

    def _generate_unique_trace_id(self):
        """
        고유한 trace_id를 생성
        동일한 타임스탬프가 연속으로 사용될 경우를 대비해서 _1, _2, _3 ... 접미사를 추가
        """
        current_timestamp = str(int(time.time()))
        
        if self._last_timestamp == current_timestamp:
            self._timestamp_counter += 1
            trace_id = f"{current_timestamp}_{self._timestamp_counter}"
        else:
            self._last_timestamp = current_timestamp
            self._timestamp_counter = 1
            trace_id = f"{current_timestamp}_1"
        
        return trace_id

    def _save_detail_payload(self, trace_id, payload, is_blacklisted=False):
        """
        큰 데이터(파라미터)를 별도 JSON 파일로 저장
        블랙리스트 카테고리인 경우 별도 디렉토리에 저장
        """
        filename = f"{trace_id}.json"
        target_dir = self.blacklisted_detail_log_dir if is_blacklisted else self.detail_log_dir
        filepath = os.path.join(target_dir, filename)
        
        try:
            if self.file_output:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
            return filename
        except Exception as e:
            return f"Error saving detail: {str(e)}"

    def _should_log(self, level):
        """
        주어진 로그 레벨이 최소 레벨 이상인지 확인
        """
        level_priority = self.LEVEL_PRIORITY.get(level.upper(), 1)
        min_priority = self.LEVEL_PRIORITY.get(self.min_level.upper(), 0)
        return level_priority >= min_priority

    def _should_include_all(self, level):
        """
        주어진 로그 레벨이 모든 파라미터를 강제로 포함시킬 최소 레벨 이상인지 확인
        """
        level_priority = self.LEVEL_PRIORITY.get(level.upper(), 1)
        min_priority = self.LEVEL_PRIORITY.get(self.include_all_min_level.upper(), 3)
        return level_priority >= min_priority

    def _log(self, level, message, category=None, params=None, max_inline_chars=100):
        """
        Args:
            level (str): INFO, ERROR, DEBUG etc.
            message (str): 로그 메시지
            category (str): 로그 카테고리 (예: "auth", "payment", "network" 등)
            params (dict): 상세 파라미터
            max_inline_chars (int): 메인 로그에 포함할 최대 글자 수. 이보다 길면 분리 저장.
        """
        if not self._should_log(level):
            return

        timestamp = datetime.now().isoformat()
        is_blacklisted = self._is_blacklisted(category)

        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }

        if category:
            log_entry["category"] = category

        if params:
            params_str = str(params)
            if len(params_str) <= max_inline_chars or self._should_include_all(level):
                log_entry["params_summary"] = params
            
            else:
                trace_id = self._generate_unique_trace_id()
                detail_filename = self._save_detail_payload(trace_id, params, is_blacklisted)
                
                if detail_filename.startswith("Error"):
                    log_entry["detail_save_error"] = detail_filename
                else:
                    log_entry["has_detail_file"] = True
                    log_entry["detail_ref"] = detail_filename
                
                if isinstance(params, dict):
                    log_entry["params_summary"] = {"keys": list(params.keys())}
                elif isinstance(params, (list, tuple)):
                    log_entry["params_summary"] = {"type": type(params).__name__, "length": len(params)}
                else:
                    log_entry["params_summary"] = {"type": type(params).__name__}

        target_log_path = self.blacklisted_log_path if is_blacklisted else self.main_log_path
        if self.file_output:
            with self._lock:
                with open(target_log_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        if self.console_output:
            category_str = f"[{category}]" if category else ""
            if self._should_include_all(level):
                print(f"[{level}]{category_str} {message} {params}")
            else :
                print(f"[{level}]{category_str} {message}")
