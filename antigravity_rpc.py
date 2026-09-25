#!/usr/bin/env python3
"""
Antigravity 2.0 - Discord Rich Presence Watcher
Monitors Antigravity 2.0 active workspace, tasks, and agent tool execution.
"""

import os
import sys
import time
import json
import sqlite3
import logging
import urllib.parse
import urllib.request
import signal
import psutil
from pypresence import Presence

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
LOG_PATH = os.path.join(SCRIPT_DIR, "rpc.log")

handlers = [logging.FileHandler(LOG_PATH, encoding="utf-8")]
if sys.stderr is not None:
    handlers.append(logging.StreamHandler(sys.stderr))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=handlers
)
logger = logging.getLogger("AntigravityRPC")

DEFAULT_CONFIG = {
    "client_id": "1440730997460172810",
    "poll_interval": 3,
    "language": "fr",
    "show_project": True,
    "show_tool_action": True,
    "process_names": ["Antigravity.exe", "Antigravity IDE.exe"],
    "assets": {
        "large_image": "antigravity_logo",
        "large_text": "Antigravity 2.0",
        "small_image_working": "robot",
        "small_text_working": "Agent actif",
        "small_image_idle": "robot",
        "small_text_idle": "Agent en attente"
    }
}

TOOL_TRANSLATIONS = {
    "fr": {
        "run_command": "Exécute une commande terminal",
        "view_file": "Inspecte un fichier",
        "replace_file_content": "Édite le code",
        "write_to_file": "Crée un fichier",
        "search_web": "Recherche sur le web",
        "read_url_content": "Consulte documentation web",
        "invoke_subagent": "Orchestre un sous-agent",
        "ask_question": "Attend confirmation utilisateur",
        "thinking": "Réflexion Gemini...",
        "idle": "En attente d'instruction",
        "working": "En cours de travail...",
        "project_prefix": "Projet: "
    },
    "en": {
        "run_command": "Running terminal command",
        "view_file": "Inspecting file",
        "replace_file_content": "Editing code",
        "write_to_file": "Creating file",
        "search_web": "Searching the web",
        "read_url_content": "Reading web doc",
        "invoke_subagent": "Orchestrating subagent",
        "ask_question": "Waiting for user input",
        "thinking": "Thinking...",
        "idle": "Idle / Waiting for input",
        "working": "Working...",
        "project_prefix": "Project: "
    }
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return {**DEFAULT_CONFIG, **cfg}
        except Exception as e:
            logger.warning(f"Error loading config.json, using defaults: {e}")
    return DEFAULT_CONFIG

def is_antigravity_running(process_names):
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"]
            if name and any(target.lower() in name.lower() for target in process_names):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def get_latest_conversation():
    db_path = os.path.abspath(os.path.expanduser("~/.gemini/antigravity/conversation_summaries.db"))
    if not os.path.exists(db_path):
        return None

    try:
        uri = f"file:{urllib.request.pathname2url(db_path)}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        cur = conn.cursor()
        cur.execute("""
            SELECT conversation_id, title, workspace_uris, not_fully_idle, status, last_modified_time
            FROM conversation_summaries
            ORDER BY not_fully_idle DESC, last_modified_time DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        conn.close()
        if not row:
            return None

        conv_id, title, workspace_uris, not_fully_idle, status, last_modified_time = row
        return {
            "conversation_id": conv_id,
            "title": title or "Antigravity Session",
            "workspace_uris": workspace_uris,
            "not_fully_idle": bool(not_fully_idle),
            "status": status,
            "last_modified_time": last_modified_time
        }
    except Exception as e:
        logger.debug(f"DB read error: {e}")
        return None

def extract_project_name(workspace_uris_json):
    if not workspace_uris_json:
        return "Workspace"
    try:
        uris = json.loads(workspace_uris_json)
        if uris and isinstance(uris, list):
            raw_uri = uris[0]
            unquoted = urllib.parse.unquote(raw_uri)
            clean_path = unquoted.replace("file:///", "").replace("file://", "")
            clean_path = os.path.normpath(clean_path)
            basename = os.path.basename(clean_path)
            if basename:
                return basename
    except Exception:
        pass
    return "Workspace"

def sanitize_discord_string(text, min_len=2, max_len=128):
    if not text:
        text = "Antigravity"
    text = text.strip()
    if len(text) < min_len:
        text = text.ljust(min_len)
    if len(text) > max_len:
        text = text[:max_len - 3] + "..."
    return text

def parse_transcript_action(conv_id, lang):
    tr = TOOL_TRANSLATIONS.get(lang, TOOL_TRANSLATIONS["en"])
    transcript_path = os.path.abspath(
        os.path.expanduser(f"~/.gemini/antigravity/brain/{conv_id}/.system_generated/logs/transcript.jsonl")
    )
    if not os.path.exists(transcript_path):
        return tr["working"]

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            seek_pos = max(0, size - 12000)
            f.seek(seek_pos)
            lines = f.readlines()
            if seek_pos > 0 and len(lines) > 1:
                lines = lines[1:]

            for raw_line in reversed(lines):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    step = json.loads(line)
                    tool_calls = step.get("tool_calls", [])
                    if tool_calls:
                        tc = tool_calls[0]
                        tool_name = tc.get("name", "")
                        args = tc.get("args", {})
                        action_desc = args.get("toolAction") or args.get("toolSummary")
                        if action_desc and isinstance(action_desc, str):
                            clean_action = action_desc.strip('"\'')
                            if clean_action:
                                return clean_action
                        return tr.get(tool_name, f"Tool: {tool_name}")

                    if step.get("type") == "PLANNER_RESPONSE" and step.get("thinking"):
                        return tr["thinking"]
                except Exception:
                    continue
    except Exception as e:
        logger.debug(f"Transcript read error: {e}")

    return tr["working"]

class AntigravityRPC:
    def __init__(self):
        self.config = load_config()
        self.client_id = self.config["client_id"]
        self.poll_interval = self.config.get("poll_interval", 3)
        self.lang = self.config.get("language", "fr")
        self.rpc = None
        self.connected = False
        self.session_start_time = None
        self.current_conv_id = None
        self.last_state = None
        self.last_details = None

    def connect(self):
        if self.connected:
            return True
        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.connected = True
            logger.info("Connected to Discord RPC.")
            return True
        except Exception as e:
            self.rpc = None
            self.connected = False
            logger.debug(f"Discord not available or connection failed: {e}")
            return False

    def disconnect(self):
        if self.connected and self.rpc:
            try:
                self.rpc.clear()
                self.rpc.close()
            except Exception:
                pass
            logger.info("Disconnected from Discord RPC.")
        self.connected = False
        self.rpc = None

    def update_presence(self):
        if not is_antigravity_running(self.config["process_names"]):
            if self.connected:
                logger.info("Antigravity process not detected. Clearing status.")
                self.disconnect()
            return

        if not self.connected:
            if not self.connect():
                return

        conv = get_latest_conversation()
        tr = TOOL_TRANSLATIONS.get(self.lang, TOOL_TRANSLATIONS["en"])
        assets = self.config.get("assets", {})

        if self.session_start_time is None:
            self.session_start_time = int(time.time())

        if not conv:
            details = sanitize_discord_string("Antigravity 2.0")
            state = sanitize_discord_string(tr["idle"])
            small_key = assets.get("small_image_idle", "robot")
            small_text = assets.get("small_text_idle", "Idle")
        else:
            conv_id = conv["conversation_id"]
            self.current_conv_id = conv_id

            proj_name = extract_project_name(conv["workspace_uris"])
            if self.config.get("show_project", True):
                details = sanitize_discord_string(f"{tr['project_prefix']}{proj_name}")
            else:
                details = sanitize_discord_string(conv["title"])

            is_working = conv["not_fully_idle"]
            if is_working:
                action = parse_transcript_action(conv_id, self.lang)
                state = sanitize_discord_string(action)
                small_key = assets.get("small_image_working", "robot")
                small_text = assets.get("small_text_working", "Agent actif")
            else:
                state = sanitize_discord_string(tr["idle"])
                small_key = assets.get("small_image_idle", "robot")
                small_text = assets.get("small_text_idle", "En attente")

        # Avoid spamming Discord if nothing changed
        if state == self.last_state and details == self.last_details:
            return

        try:
            payload = {
                "details": details,
                "state": state,
                "large_text": assets.get("large_text", "Antigravity 2.0")
            }
            if assets.get("large_image"):
                payload["large_image"] = assets["large_image"]
            if small_key:
                payload["small_image"] = small_key
                payload["small_text"] = small_text
            if self.session_start_time:
                payload["start"] = self.session_start_time

            self.rpc.update(**payload)
            self.last_state = state
            self.last_details = details
            logger.info(f"Updated RPC: [{details}] | [{state}]")
        except Exception as e:
            logger.warning(f"Error updating presence: {e}")
            self.disconnect()

    def run(self):
        logger.info(f"Antigravity Discord RPC Watcher started (Interval: {self.poll_interval}s).")
        while True:
            try:
                self.update_presence()
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                logger.info("Stopping watcher...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(self.poll_interval)
        self.disconnect()

if __name__ == "__main__":
    app = AntigravityRPC()
    def sig_handler(sig, frame):
        logger.info("Shutdown signal received.")
        app.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)
    app.run()
