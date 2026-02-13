import os
import re
import io
import json
import time
import uuid
import zipfile
import hashlib
import asyncio
import logging
import tempfile
import subprocess
import threading
from datetime import datetime, timedelta, time as dt_time
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# --- CONFIGURATION ---
BOT_TOKEN = "8251499938:AAGZ5Vf5obSaaw2PXgRx80wZmXHm0NpBBqU"
ADMIN_ID = 6290314134
BOT_USERNAME = "@FEMBOYSecULPbot"
PREMIUM_CONTACT = "@kurdfemboys"

# Channels to follow
CHANNELS = [
    "@FEMBOYSec",
    "@db_kurdistan", 
    "@JNCBC1"
]

# Paths
DB_PATH = "main.txt"
DATA_DIR = "bot_data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
BANS_FILE = os.path.join(DATA_DIR, "bans.json")
SPAM_FILE = os.path.join(DATA_DIR, "spam.json")
INVITES_FILE = os.path.join(DATA_DIR, "invites.json")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")
SCRIPTS_DIR = os.path.join(DATA_DIR, "scripts")
GROUPS_FILE = os.path.join(DATA_DIR, "groups.json")
REFERRALS_FILE = os.path.join(DATA_DIR, "referrals.json")

# Premium pricing
PREMIUM_PRICES = {
    "3days": 25,
    "1week": 50,
    "1month": 150,
    "1year": 1000
}

# Limits
SEARCH_LIMIT_NORMAL = 5
SEARCH_LIMIT_PREMIUM = 50
PREMIUM_VISIBILITY = 100
NORMAL_VISIBILITY = 70
ZIP_THRESHOLD = 20 * 1024 * 1024
SPLIT_THRESHOLD = 35 * 1024 * 1024
RATE_LIMIT_SECONDS = 5
MAX_SEARCH_TERM_LENGTH = 100
MAX_CONCURRENT_SEARCHES = 10

# Create directories
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SCRIPTS_DIR, exist_ok=True)

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- DATA STRUCTURES ---
class UserData:
    def __init__(self, user_id: int):
        self.user_id = str(user_id)
        self.status = "normal"  # normal, premium, banned
        self.premium_expiry = None  # ISO format date if premium
        self.searches_today = 0
        self.last_reset = datetime.now().isoformat()
        self.total_searches = 0
        self.weekly_searches = 0
        self.monthly_searches = 0
        self.join_date = datetime.now().isoformat()
        self.last_search = 0
        self.warnings = 0
        self.notes = []
        self.referred_by = None
        self.referrals = []  # List of user IDs they referred
        self.bonus_searches = 0  # Extra searches from referrals
        
    def to_dict(self):
        return {
            "user_id": self.user_id,
            "status": self.status,
            "premium_expiry": self.premium_expiry,
            "searches_today": self.searches_today,
            "last_reset": self.last_reset,
            "total_searches": self.total_searches,
            "weekly_searches": self.weekly_searches,
            "monthly_searches": self.monthly_searches,
            "join_date": self.join_date,
            "last_search": self.last_search,
            "warnings": self.warnings,
            "notes": self.notes,
            "referred_by": self.referred_by,
            "referrals": self.referrals,
            "bonus_searches": self.bonus_searches
        }
    
    @classmethod
    def from_dict(cls, data):
        user = cls(int(data["user_id"]))
        user.status = data["status"]
        user.premium_expiry = data.get("premium_expiry")
        user.searches_today = data["searches_today"]
        user.last_reset = data.get("last_reset", datetime.now().isoformat())
        user.total_searches = data["total_searches"]
        user.weekly_searches = data.get("weekly_searches", 0)
        user.monthly_searches = data.get("monthly_searches", 0)
        user.join_date = data["join_date"]
        user.last_search = data.get("last_search", 0)
        user.warnings = data.get("warnings", 0)
        user.notes = data.get("notes", [])
        user.referred_by = data.get("referred_by")
        user.referrals = data.get("referrals", [])
        user.bonus_searches = data.get("bonus_searches", 0)
        return user
    
    def get_daily_limit(self):
        if self.status == "premium":
            return SEARCH_LIMIT_PREMIUM
        return SEARCH_LIMIT_NORMAL + self.bonus_searches
    
    def check_premium_expiry(self):
        if self.status == "premium" and self.premium_expiry:
            expiry = datetime.fromisoformat(self.premium_expiry)
            if datetime.now() > expiry:
                self.status = "normal"
                self.premium_expiry = None
                self.notes.append(f"Premium expired at {datetime.now().isoformat()}")
                return True
        return False

class BotDatabase:
    def __init__(self):
        self.users: Dict[str, UserData] = {}
        self.banned_users: set = set()
        self.spam_list: Dict[str, int] = defaultdict(int)
        self.invites: Dict[str, Dict] = {}
        self.groups: Dict[str, Dict] = {}
        self.referral_stats: Dict = defaultdict(lambda: {"invites_sent": 0, "converted": 0})
        self.stats: Dict = {
            "total_searches": 0,
            "total_users": 0,
            "premium_users": 0,
            "banned_users": 0,
            "daily_searches": [],
            "weekly_searches": [],
            "monthly_searches": [],
            "search_history": []
        }
        self.active_searches: Dict[str, asyncio.Task] = {}
        self.load_all()
        self.check_premium_expirations()
    
    def load_all(self):
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                data = json.load(f)
                for uid, user_data in data.items():
                    user = UserData.from_dict(user_data)
                    self.users[uid] = user
                    if user.status == "banned":
                        self.banned_users.add(uid)
        
        if os.path.exists(BANS_FILE):
            with open(BANS_FILE, 'r') as f:
                self.banned_users = set(json.load(f))
        
        if os.path.exists(SPAM_FILE):
            with open(SPAM_FILE, 'r') as f:
                self.spam_list = defaultdict(int, json.load(f))
        
        if os.path.exists(INVITES_FILE):
            with open(INVITES_FILE, 'r') as f:
                self.invites = json.load(f)
        
        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r') as f:
                self.groups = json.load(f)
        
        if os.path.exists(REFERRALS_FILE):
            with open(REFERRALS_FILE, 'r') as f:
                self.referral_stats = defaultdict(lambda: {"invites_sent": 0, "converted": 0}, json.load(f))
        
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                self.stats.update(json.load(f))
    
    def save_all(self):
        users_dict = {uid: user.to_dict() for uid, user in self.users.items()}
        with open(USERS_FILE, 'w') as f:
            json.dump(users_dict, f, indent=2)
        
        with open(BANS_FILE, 'w') as f:
            json.dump(list(self.banned_users), f)
        
        with open(SPAM_FILE, 'w') as f:
            json.dump(dict(self.spam_list), f)
        
        with open(INVITES_FILE, 'w') as f:
            json.dump(self.invites, f)
        
        with open(GROUPS_FILE, 'w') as f:
            json.dump(self.groups, f)
        
        with open(REFERRALS_FILE, 'w') as f:
            json.dump(dict(self.referral_stats), f)
        
        with open(STATS_FILE, 'w') as f:
            json.dump(self.stats, f, indent=2)
    
    def check_premium_expirations(self):
        for user in self.users.values():
            if user.check_premium_expiry():
                self.save_all()
    
    def get_user(self, user_id: int) -> UserData:
        uid = str(user_id)
        if uid not in self.users:
            self.users[uid] = UserData(user_id)
            self.stats["total_users"] = len(self.users)
            self.save_all()
        return self.users[uid]
    
    def reset_daily_searches(self):
        today = datetime.now().date().isoformat()
        reset_count = 0
        for user in self.users.values():
            last_reset_date = user.last_reset.split('T')[0] if 'T' in user.last_reset else user.last_reset
            if last_reset_date != today:
                old_searches = user.searches_today
                user.searches_today = 0
                user.last_reset = datetime.now().isoformat()
                if old_searches > 0:
                    reset_count += 1
        self.save_all()
        return reset_count
    
    def can_search(self, user_id: int) -> Tuple[bool, str]:
        uid = str(user_id)
        user = self.get_user(user_id)
        
        if uid in self.banned_users or user.status == "banned":
            return False, f"you are banned potato >.< contact admin if this is a mistake"
        
        if self.spam_list[uid] >= 3:
            return False, f"you've been flagged for spam :( contact admin"
        
        current_time = time.time()
        if current_time - user.last_search < RATE_LIMIT_SECONDS:
            wait_time = int(RATE_LIMIT_SECONDS - (current_time - user.last_search))
            return False, f"please wait {wait_time} seconds between searches :3"
        
        daily_limit = user.get_daily_limit()
        if user.searches_today >= daily_limit:
            reset_time = datetime.fromisoformat(user.last_reset) + timedelta(days=1)
            time_left = reset_time - datetime.now()
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            return False, f"daily limit reached potato~ reset in {hours}h {minutes}m"
        
        return True, "OK"
    
    def record_search(self, user_id: int, search_term: str, results_count: int):
        uid = str(user_id)
        user = self.get_user(user_id)
        
        user.searches_today += 1
        user.total_searches += 1
        user.weekly_searches += 1
        user.monthly_searches += 1
        user.last_search = time.time()
        
        self.stats["total_searches"] += 1
        
        today = datetime.now().date().isoformat()
        week = datetime.now().strftime('%Y-W%W')
        month = datetime.now().strftime('%Y-%m')
        
        self.stats["daily_searches"].append({"date": today, "count": 1})
        self.stats["weekly_searches"].append({"week": week, "count": 1})
        self.stats["monthly_searches"].append({"month": month, "count": 1})
        
        self.stats["search_history"].append({
            "user_id": uid,
            "term": search_term[:50],
            "results": results_count,
            "timestamp": datetime.now().isoformat()
        })
        
        if len(self.stats["search_history"]) > 1000:
            self.stats["search_history"] = self.stats["search_history"][-1000:]
        
        if len(self.stats["daily_searches"]) > 30:
            self.stats["daily_searches"] = self.stats["daily_searches"][-30:]
        if len(self.stats["weekly_searches"]) > 12:
            self.stats["weekly_searches"] = self.stats["weekly_searches"][-12:]
        if len(self.stats["monthly_searches"]) > 12:
            self.stats["monthly_searches"] = self.stats["monthly_searches"][-12:]
        
        self.save_all()
    
    def ban_user(self, user_id: int, reason: str = ""):
        uid = str(user_id)
        self.banned_users.add(uid)
        user = self.get_user(user_id)
        user.status = "banned"
        user.notes.append(f"banned: {reason} at {datetime.now().isoformat()}")
        self.stats["banned_users"] = len(self.banned_users)
        self.save_all()
    
    def unban_user(self, user_id: int):
        uid = str(user_id)
        self.banned_users.discard(uid)
        user = self.get_user(user_id)
        user.status = "normal"
        user.notes.append(f"unbanned at {datetime.now().isoformat()}")
        self.save_all()
    
    def add_to_spam_list(self, user_id: int):
        uid = str(user_id)
        self.spam_list[uid] += 1
        if self.spam_list[uid] >= 3:
            self.ban_user(user_id, "spam detected")
        self.save_all()
    
    def generate_invite(self, created_by: int, uses: int = 1) -> str:
        code = f"FEMBOY-{uuid.uuid4().hex[:8].upper()}"
        self.invites[code] = {
            "created_by": str(created_by),
            "created_at": datetime.now().isoformat(),
            "uses_left": uses,
            "used_by": []
        }
        self.save_all()
        return code
    
    def redeem_invite(self, code: str, user_id: int) -> bool:
        if code not in self.invites:
            return False
        
        invite = self.invites[code]
        if invite["uses_left"] <= 0:
            return False
        
        user = self.get_user(user_id)
        user.status = "premium"
        user.premium_expiry = (datetime.now() + timedelta(days=30)).isoformat()  # Default 30 days
        user.notes.append(f"upgraded via invite {code} at {datetime.now().isoformat()}")
        
        # Give referral bonus to inviter
        inviter_id = invite["created_by"]
        if inviter_id and inviter_id != str(user_id):
            inviter = self.get_user(int(inviter_id))
            inviter.bonus_searches += 1
            inviter.referrals.append(str(user_id))
            user.referred_by = inviter_id
            self.referral_stats[inviter_id]["converted"] += 1
        
        invite["uses_left"] -= 1
        invite["used_by"].append(str(user_id))
        
        if invite["uses_left"] <= 0:
            del self.invites[code]
        
        self.stats["premium_users"] = sum(1 for u in self.users.values() if u.status == "premium")
        self.save_all()
        return True
    
    def add_premium_time(self, user_id: int, days: int):
        user = self.get_user(user_id)
        if user.status != "premium":
            user.status = "premium"
            user.premium_expiry = (datetime.now() + timedelta(days=days)).isoformat()
        else:
            current = datetime.fromisoformat(user.premium_expiry)
            user.premium_expiry = (current + timedelta(days=days)).isoformat()
        user.notes.append(f"premium extended by {days} days at {datetime.now().isoformat()}")
        self.stats["premium_users"] = sum(1 for u in self.users.values() if u.status == "premium")
        self.save_all()
    
    def add_group(self, chat_id: int, title: str, added_by: int):
        cid = str(chat_id)
        self.groups[cid] = {
            "title": title,
            "added_by": str(added_by),
            "added_at": datetime.now().isoformat()
        }
        self.save_all()
    
    def remove_group(self, chat_id: int):
        cid = str(chat_id)
        if cid in self.groups:
            del self.groups[cid]
            self.save_all()
    
    def generate_referral_link(self, user_id: int) -> str:
        code = f"REF-{uuid.uuid4().hex[:8].upper()}"
        self.invites[code] = {
            "created_by": str(user_id),
            "created_at": datetime.now().isoformat(),
            "uses_left": 1,
            "used_by": [],
            "type": "referral"
        }
        self.referral_stats[str(user_id)]["invites_sent"] += 1
        self.save_all()
        return code

# Initialize database
db = BotDatabase()

# --- GROUP CHAT HANDLER ---
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            chat = update.effective_chat
            user = update.effective_user
            db.add_group(chat.id, chat.title or "unnamed group", user.id)
            logger.warning(f"bot added to group: {chat.title} by user {user.id}")
            try:
                await context.bot.leave_chat(chat.id)
                logger.info(f"left group {chat.id}")
            except Exception as e:
                logger.error(f"failed to leave group {chat.id}: {e}")
            db.ban_user(user.id, "attempted to add bot to group")
            logger.warning(f"banned user {user.id} for adding bot to group")
            break

async def handle_left_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.left_chat_member:
        return
    
    if update.message.left_chat_member.id == context.bot.id:
        chat = update.effective_chat
        db.remove_group(chat.id)

# --- SEARCH ENGINE ---
class SearchManager:
    def __init__(self):
        self.active_scripts = {}
        self.script_lock = asyncio.Lock()
        self.search_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)
    
    def create_search_script(self, user_id: int, search_term: str, limit: int) -> str:
        script_id = f"search_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        script_path = os.path.join(SCRIPTS_DIR, f"{script_id}.sh")
        
        safe_term = search_term.replace('"', '\\"').replace("'", "'\\''")
        
        script_content = f"""#!/bin/bash
export LC_ALL=C
grep -i -a -h -m {limit} -F "{safe_term}" "{DB_PATH}" 2>/dev/null || true
"""
        
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        os.chmod(script_path, 0o755)
        return script_path, script_id
    
    async def execute_search(self, user_id: int, search_term: str, limit: int, update_msg) -> List[str]:
        async with self.search_semaphore:
            script_path = None
            try:
                script_path, script_id = self.create_search_script(user_id, search_term, limit)
                self.active_scripts[script_id] = {
                    "user_id": user_id,
                    "path": script_path,
                    "start_time": time.time()
                }
                
                lines = []
                last_update = time.time()
                
                proc = await asyncio.create_subprocess_exec(
                    script_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    
                    clean_line = line.decode('utf-8', errors='ignore').strip()
                    if clean_line:
                        lines.append(clean_line)
                    
                    current_time = time.time()
                    if current_time - last_update > 1.5:
                        try:
                            await update_msg.edit_text(
                                f"searching potato~ :3\n\nlines found: {len(lines)}\ntime: {int(current_time - last_update)}s"
                            )
                            last_update = current_time
                        except:
                            pass
                
                await proc.wait()
                return lines
                
            except Exception as e:
                logger.error(f"search error for user {user_id}: {e}")
                return []
            finally:
                if script_path and os.path.exists(script_path):
                    try:
                        os.remove(script_path)
                    except:
                        pass
                
                for sid, data in list(self.active_scripts.items()):
                    if data["user_id"] == user_id:
                        del self.active_scripts[sid]

search_manager = SearchManager()

# --- FILE HANDLING ---
def prepare_files(content: str, base_filename: str) -> List[Tuple[bytes, str]]:
    data_bytes = content.encode('utf-8')
    final_files = []
    
    if len(data_bytes) > ZIP_THRESHOLD:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.writestr(base_filename, data_bytes)
        payload = zip_buffer.getvalue()
        ext_filename = base_filename.replace('.txt', '.zip')
    else:
        payload = data_bytes
        ext_filename = base_filename
    
    if len(payload) > SPLIT_THRESHOLD:
        total_parts = (len(payload) + SPLIT_THRESHOLD - 1) // SPLIT_THRESHOLD
        for i in range(total_parts):
            start = i * SPLIT_THRESHOLD
            end = min((i + 1) * SPLIT_THRESHOLD, len(payload))
            chunk = payload[start:end]
            part_name = f"part_{i+1}_of_{total_parts}_{ext_filename}"
            final_files.append((chunk, part_name))
    else:
        final_files.append((payload, ext_filename))
    
    return final_files

# --- MESSAGE HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    
    user = update.effective_user
    db.get_user(user.id)
    
    if str(user.id) in db.banned_users:
        await update.message.reply_text("you are banned potato >.<")
        return
    
    db.reset_daily_searches()
    user_data = db.get_user(user.id)
    
    channels_text = "\n".join([f"• {ch}" for ch in CHANNELS])
    
    welcome_text = (
        f"hewwo potato~ :3\n"
        f"welcome to {BOT_USERNAME}\n\n"
        f"your status: {user_data.status.upper()}\n"
        f"searches today: {user_data.searches_today}/{user_data.get_daily_limit()}\n\n"
        f"premium users get 100% results (normal users see 70%)\n\n"
        f"follow us so u dont lose us potato :D\n"
        f"{channels_text}\n\n"
        f"choose an option:"
    )
    
    keyboard = [
        [InlineKeyboardButton("search domain", callback_data="search_domain")],
        [InlineKeyboardButton("search email", callback_data="search_email")],
        [InlineKeyboardButton("search password", callback_data="search_password")],
        [InlineKeyboardButton("profile", callback_data="profile"),
         InlineKeyboardButton("premium", callback_data="premium")],
        [InlineKeyboardButton("referral", callback_data="referral"),
         InlineKeyboardButton("help", callback_data="help")]
    ]
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if str(user.id) in db.banned_users:
        await query.edit_message_text("you are banned >.<")
        return
    
    if query.data == "profile":
        daily_limit = user_data.get_daily_limit()
        expiry = ""
        if user_data.status == "premium" and user_data.premium_expiry:
            expiry_date = datetime.fromisoformat(user_data.premium_expiry)
            days_left = (expiry_date - datetime.now()).days
            expiry = f"\npremium expires: {days_left} days"
        
        channels_text = "\n".join([f"• {ch}" for ch in CHANNELS])
        
        profile_text = (
            f"your profile potato :3\n\n"
            f"id: {user.id}\n"
            f"status: {user_data.status.upper()}{expiry}\n"
            f"searches today: {user_data.searches_today}/{daily_limit}\n"
            f"total searches: {user_data.total_searches}\n"
            f"weekly searches: {user_data.weekly_searches}\n"
            f"monthly searches: {user_data.monthly_searches}\n"
            f"joined: {user_data.join_date[:10]}\n"
            f"warnings: {user_data.warnings}\n"
            f"bonus searches: {user_data.bonus_searches}\n"
            f"referrals: {len(user_data.referrals)}\n\n"
            f"follow us:\n{channels_text}"
        )
        await query.edit_message_text(profile_text)
        
    elif query.data == "premium":
        premium_text = (
            "premium benefits :D\n\n"
            "100% results (free users see 70%)\n"
            "50 searches per day (free users get 5)\n"
            "priority support\n"
            "exclusive data access\n\n"
            "prices:\n"
            f"3 days -> ${PREMIUM_PRICES['3days']}\n"
            f"1 week -> ${PREMIUM_PRICES['1week']}\n"
            f"1 month -> ${PREMIUM_PRICES['1month']}\n"
            f"1 year -> ${PREMIUM_PRICES['1year']}\n\n"
            f"contact {PREMIUM_CONTACT} to buy potato~ :3"
        )
        await query.edit_message_text(premium_text)
        
    elif query.data == "referral":
        code = db.generate_referral_link(user.id)
        referral_text = (
            "refer a friend potato! :D\n\n"
            "when your friend uses this link and becomes premium,\n"
            "you get 1 bonus search!\n\n"
            f"your referral code: {code}\n\n"
            f"share this with your friends :3"
        )
        await query.edit_message_text(referral_text)
        
    elif query.data == "help":
        channels_text = "\n".join([f"• {ch}" for ch in CHANNELS])
        help_text = (
            "help & info :3\n\n"
            "search types:\n"
            "domain: search by domain (example.com)\n"
            "email: search by email address\n"
            "password: search by password hash\n\n"
            "limits:\n"
            "free: 5 searches/day, 70% results\n"
            "premium: 50 searches/day, 100% results\n\n"
            "commands:\n"
            "/cancel - stop current search\n\n"
            f"follow us:\n{channels_text}"
        )
        await query.edit_message_text(help_text)
        
    elif query.data.startswith("search_"):
        search_type = query.data.replace("search_", "")
        context.user_data['search_mode'] = search_type
        await query.edit_message_text(
            f"enter {search_type} to search :3\n"
            f"(type /cancel to cancel)"
        )

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    
    if 'search_mode' not in context.user_data:
        return
    
    user = update.effective_user
    search_term = update.message.text.strip()
    
    if search_term.lower() == '/cancel':
        context.user_data.pop('search_mode', None)
        await update.message.reply_text("search cancelled potato~")
        return
    
    if str(user.id) in db.active_searches:
        await update.message.reply_text("u already have an active search :o please wait")
        return
    
    if len(search_term) > MAX_SEARCH_TERM_LENGTH:
        await update.message.reply_text(f"search term too long potato >.< max {MAX_SEARCH_TERM_LENGTH} chars")
        return
    
    if not re.match(r'^[a-zA-Z0-9@\.\-_]+$', search_term):
        await update.message.reply_text("invalid characters :( use letters, numbers, @ . - _")
        return
    
    can_search, message = db.can_search(user.id)
    if not can_search:
        await update.message.reply_text(message)
        return
    
    status_msg = await update.message.reply_text("searching potato~ :3\n\nlines found: 0")
    
    try:
        user_data = db.get_user(user.id)
        is_premium = user_data.status == "premium"
        result_limit = 10000000 if is_premium else 1000000
        
        lines = await search_manager.execute_search(
            user.id, 
            search_term, 
            result_limit,
            status_msg
        )
        
        if not lines:
            await status_msg.edit_text("no results found :(")
            return
        
        if not is_premium:
            visible_count = int(len(lines) * (NORMAL_VISIBILITY / 100))
            lines = lines[:visible_count]
            visibility_msg = f"showing {NORMAL_VISIBILITY}% of results (free user)"
        else:
            visibility_msg = "showing 100% of results (premium)"
        
        db.record_search(user.id, search_term, len(lines))
        
        channels_text = "\n".join([f"• {ch}" for ch in CHANNELS])
        
        header = (
            f"search results :D\n"
            f"bot: {BOT_USERNAME}\n"
            f"term: {search_term}\n"
            f"results: {len(lines)}\n"
            f"user: {user_data.status.upper()}\n"
            f"time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{visibility_msg}\n\n"
            f"we sell daily breaches!\n"
            f"join us:\n{channels_text}\n"
            f"{'='*50}\n\n"
        )
        
        content = header + "\n".join(lines)
        
        safe_term = re.sub(r'[^\w]', '_', search_term)[:30]
        filename = f"{BOT_USERNAME}_{context.user_data['search_mode']}_{safe_term}.txt"
        
        files_to_send = prepare_files(content, filename)
        
        for file_data, file_name in files_to_send:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=io.BytesIO(file_data),
                filename=file_name,
                caption=f"{search_term[:30]} | {len(lines)} results :3"
            )
        
        await status_msg.delete()
        
        if not is_premium and len(lines) > 100:
            await update.message.reply_text(
                f"want to see all {len(lines)} results? :o\n"
                f"get premium for 100% visibility!\n"
                f"contact {PREMIUM_CONTACT}"
            )
        
    except Exception as e:
        logger.error(f"search error for user {user.id}: {e}")
        await status_msg.edit_text("an error occurred potato :( try again later")
    finally:
        context.user_data.pop('search_mode', None)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    
    if 'search_mode' in context.user_data:
        context.user_data.pop('search_mode')
        await update.message.reply_text("search cancelled potato~ :3")
    else:
        await update.message.reply_text("no active search to cancel :3")

# --- ADMIN COMMANDS ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    db.check_premium_expirations()
    
    # Calculate stats
    active_today = sum(1 for u in db.users.values() if u.searches_today > 0)
    active_week = sum(1 for u in db.users.values() if u.weekly_searches > 0)
    active_month = sum(1 for u in db.users.values() if u.monthly_searches > 0)
    
    premium_users = sum(1 for u in db.users.values() if u.status == "premium")
    expiring_soon = sum(1 for u in db.users.values() 
                       if u.status == "premium" and u.premium_expiry 
                       and (datetime.fromisoformat(u.premium_expiry) - datetime.now()).days <= 7)
    
    stats_text = (
        f"admin stats potato~ :3\n\n"
        f"users: {len(db.users)}\n"
        f"premium: {premium_users}\n"
        f"banned: {len(db.banned_users)}\n"
        f"spam listed: {len(db.spam_list)}\n"
        f"groups tracked: {len(db.groups)}\n\n"
        f"searches:\n"
        f"total: {db.stats['total_searches']}\n"
        f"today: {sum(u.searches_today for u in db.users.values())}\n"
        f"week: {sum(u.weekly_searches for u in db.users.values())}\n"
        f"month: {sum(u.monthly_searches for u in db.users.values())}\n\n"
        f"active users:\n"
        f"today: {active_today}\n"
        f"week: {active_week}\n"
        f"month: {active_month}\n\n"
        f"premium expiring soon: {expiring_soon}\n"
        f"active scripts: {len(search_manager.active_scripts)}\n"
        f"active invites: {len(db.invites)}"
    )
    
    await update.message.reply_text(stats_text)

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    page = 1
    if context.args and context.args[0].isdigit():
        page = int(context.args[0])
    
    users_per_page = 20
    start = (page - 1) * users_per_page
    end = start + users_per_page
    
    all_users = list(db.users.values())
    total_pages = (len(all_users) + users_per_page - 1) // users_per_page
    
    users_text = f"users list (page {page}/{total_pages}) :3\n\n"
    
    for user in all_users[start:end]:
        status_icon = "👑" if user.status == "premium" else "👤" if user.status == "normal" else "🚫"
        users_text += f"{status_icon} {user.user_id}: {user.searches_today}/{user.get_daily_limit()} | total: {user.total_searches}\n"
    
    if page < total_pages:
        users_text += f"\nuse /users {page + 1} for next page"
    
    await update.message.reply_text(users_text)

async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("usage: /ban <user_id> [reason]")
        return
    
    target_id = context.args[0].replace('@', '')
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "no reason"
    
    try:
        db.ban_user(int(target_id), reason)
        await update.message.reply_text(f"banned user {target_id}\nreason: {reason}")
    except:
        await update.message.reply_text("invalid user id >.<")

async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("usage: /unban <user_id>")
        return
    
    target_id = context.args[0]
    
    try:
        db.unban_user(int(target_id))
        await update.message.reply_text(f"unbanned user {target_id}")
    except:
        await update.message.reply_text("invalid user id :(")

async def admin_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("usage: /limit <user_id> <new_limit>")
        return
    
    target_id = context.args[0]
    try:
        new_limit = int(context.args[1])
        user = db.get_user(int(target_id))
        user.bonus_searches = max(0, new_limit - SEARCH_LIMIT_NORMAL)
        db.save_all()
        await update.message.reply_text(f"set limit for {target_id} to {new_limit} searches/day")
    except:
        await update.message.reply_text("invalid input :(")

async def admin_unlimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("usage: /unlimit <user_id>")
        return
    
    target_id = context.args[0]
    try:
        user = db.get_user(int(target_id))
        user.bonus_searches = 0
        db.save_all()
        await update.message.reply_text(f"reset {target_id} to normal limit (5 searches/day)")
    except:
        await update.message.reply_text("invalid user id :(")

async def admin_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    today = datetime.now().date().isoformat()
    daily_data = [d for d in db.stats["daily_searches"] if d["date"] == today]
    total_today = sum(d["count"] for d in daily_data)
    
    active_users = [u for u in db.users.values() if u.searches_today > 0]
    top_users = sorted(active_users, key=lambda x: x.searches_today, reverse=True)[:10]
    
    text = f"daily stats ({today}) :3\n\n"
    text += f"total searches: {total_today}\n"
    text += f"active users: {len(active_users)}\n\n"
    text += "top users today:\n"
    
    for i, user in enumerate(top_users, 1):
        text += f"{i}. {user.user_id}: {user.searches_today} searches\n"
    
    await update.message.reply_text(text)

async def admin_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    week = datetime.now().strftime('%Y-W%W')
    weekly_data = [w for w in db.stats["weekly_searches"] if w["week"] == week]
    total_week = sum(w["count"] for w in weekly_data)
    
    active_users = [u for u in db.users.values() if u.weekly_searches > 0]
    top_users = sorted(active_users, key=lambda x: x.weekly_searches, reverse=True)[:10]
    
    text = f"weekly stats ({week}) :3\n\n"
    text += f"total searches: {total_week}\n"
    text += f"active users: {len(active_users)}\n\n"
    text += "top users this week:\n"
    
    for i, user in enumerate(top_users, 1):
        text += f"{i}. {user.user_id}: {user.weekly_searches} searches\n"
    
    await update.message.reply_text(text)

async def admin_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    month = datetime.now().strftime('%Y-%m')
    monthly_data = [m for m in db.stats["monthly_searches"] if m["month"] == month]
    total_month = sum(m["count"] for m in monthly_data)
    
    active_users = [u for u in db.users.values() if u.monthly_searches > 0]
    top_users = sorted(active_users, key=lambda x: x.monthly_searches, reverse=True)[:10]
    
    text = f"monthly stats ({month}) :3\n\n"
    text += f"total searches: {total_month}\n"
    text += f"active users: {len(active_users)}\n\n"
    text += "top users this month:\n"
    
    for i, user in enumerate(top_users, 1):
        text += f"{i}. {user.user_id}: {user.monthly_searches} searches\n"
    
    await update.message.reply_text(text)

async def admin_lifetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    top_users = sorted(db.users.values(), key=lambda x: x.total_searches, reverse=True)[:20]
    
    text = "lifetime stats :3\n\n"
    text += f"total searches: {db.stats['total_searches']}\n"
    text += f"total users: {len(db.users)}\n"
    text += f"premium users: {sum(1 for u in db.users.values() if u.status == 'premium')}\n\n"
    text += "top users all time:\n"
    
    for i, user in enumerate(top_users[:10], 1):
        text += f"{i}. {user.user_id}: {user.total_searches} searches\n"
    
    await update.message.reply_text(text)

async def admin_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    uses = int(context.args[0]) if context.args else 1
    code = db.generate_invite(update.effective_user.id, uses)
    
    await update.message.reply_text(
        f"invite code generated:\n{code}\n\nuses: {uses}"
    )

async def admin_give_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("usage: /givepremium <user_id> <days>")
        return
    
    target_id = context.args[0]
    try:
        days = int(context.args[1])
        db.add_premium_time(int(target_id), days)
        await update.message.reply_text(f"gave {days} days premium to {target_id}")
    except:
        await update.message.reply_text("invalid input :(")

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("usage: /broadcast <message>")
        return
    
    message = ' '.join(context.args)
    sent = 0
    
    for user_id in db.users.keys():
        try:
            await context.bot.send_message(
                int(user_id),
                f"broadcast from admin :3\n\n{message}"
            )
            sent += 1
            await asyncio.sleep(0.05)
        except:
            continue
    
    await update.message.reply_text(f"broadcast sent to {sent} users")

async def admin_spam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not db.spam_list:
        await update.message.reply_text("no spam list :3")
        return
    
    text = "spam list:\n\n"
    for uid, count in sorted(db.spam_list.items(), key=lambda x: x[1], reverse=True)[:20]:
        user = db.users.get(uid)
        if user:
            text += f"{uid}: {count} warnings ({user.status})\n"
    
    await update.message.reply_text(text)

async def admin_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not db.groups:
        await update.message.reply_text("no groups tracked")
        return
    
    text = "groups bot was added to:\n\n"
    for gid, gdata in list(db.groups.items())[:20]:
        text += f"group: {gdata['title']}\nid: {gid}\nadded by: {gdata['added_by']}\ntime: {gdata['added_at'][:19]}\n\n"
    
    if len(db.groups) > 20:
        text += f"\n... and {len(db.groups) - 20} more"
    
    await update.message.reply_text(text)

async def admin_reset_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    count = db.reset_daily_searches()
    await update.message.reply_text(f"reset daily searches for {count} users potato~ :3")

# --- DAILY RESET NOTIFICATION ---
async def daily_reset_notification(context: ContextTypes.DEFAULT_TYPE):
    """Send notification when daily searches reset"""
    count = db.reset_daily_searches()
    if count > 0:
        # Notify admin
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"daily reset complete :3\nreset {count} users' searches"
            )
        except:
            pass
        
        # Notify users who used all their searches
        for user_id, user in db.users.items():
            if user.searches_today == 0 and user.total_searches > 0:
                try:
                    await context.bot.send_message(
                        int(user_id),
                        f"your daily searches have been reset potato~ :3\n"
                        f"you have {user.get_daily_limit()} searches ready! :D"
                    )
                    await asyncio.sleep(0.05)
                except:
                    pass

# --- ERROR HANDLER ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"update {update} caused error {context.error}")
    
    try:
        if update and update.effective_message and update.effective_chat.type == "private":
            # Don't reply to users who blocked the bot
            if "Forbidden: bot was blocked by the user" not in str(context.error):
                await update.effective_message.reply_text(
                    "an error occurred potato :( try again later"
                )
    except:
        pass

# --- MAIN ---
def main():
    db.reset_daily_searches()
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Group handlers
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.COMMAND, 
        handle_group_message
    ))
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS, 
        handle_new_chat_members
    ))
    application.add_handler(MessageHandler(
        filters.StatusUpdate.LEFT_CHAT_MEMBER, 
        handle_left_chat_member
    ))
    
    # Private chat handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Admin commands
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("users", admin_users))
    application.add_handler(CommandHandler("ban", admin_ban))
    application.add_handler(CommandHandler("unban", admin_unban))
    application.add_handler(CommandHandler("limit", admin_limit))
    application.add_handler(CommandHandler("unlimit", admin_unlimit))
    application.add_handler(CommandHandler("daily", admin_daily))
    application.add_handler(CommandHandler("weekly", admin_weekly))
    application.add_handler(CommandHandler("monthly", admin_monthly))
    application.add_handler(CommandHandler("lifetime", admin_lifetime))
    application.add_handler(CommandHandler("invite", admin_invite))
    application.add_handler(CommandHandler("givepremium", admin_give_premium))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(CommandHandler("spam", admin_spam))
    application.add_handler(CommandHandler("groups", admin_groups))
    application.add_handler(CommandHandler("resetdaily", admin_reset_daily))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, 
        handle_search
    ))
    
    application.add_error_handler(error_handler)
    
    # Schedule daily reset at midnight (00:00)
    job_queue = application.job_queue
    if job_queue:
        # Run daily reset at midnight
        job_queue.run_daily(daily_reset_notification, time=dt_time(hour=0, minute=0, second=0))
        print("daily reset job scheduled for midnight :3")
    else:
        print("warning: job queue not available, daily reset won't run automatically")
    
    print(f"bot {BOT_USERNAME} is running... :3")
    print(f"admin id: {ADMIN_ID}")
    print(f"users: {len(db.users)}")
    print(f"premium: {sum(1 for u in db.users.values() if u.status == 'premium')}")
    
    application.run_polling()

if __name__ == "__main__":
    main()
