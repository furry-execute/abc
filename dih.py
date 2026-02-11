#!/usr/bin/env python3
"""
ULTRA-FAST ULP Search Bot for @FEMBOYSecULPbot
Using Pyrogram for maximum performance and reliability
Enhanced with proper grep search, security fixes, and cute femboy personality
"""

import asyncio
import os
import re
import zipfile
import io
import csv
import logging
import hashlib
import time
import signal
import sys
import json
import random
import subprocess
import shlex
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Set, Any

from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, CallbackQuery,
    Message, InlineQuery, InputFile
)
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.errors import FloodWait
import aiofiles
import aiofiles.os

# ================= CONFIGURATION =================
BOT_TOKEN = "8251499938:AAGZ5Vf5obSaaw2PXgRx80wZmXHm0NpBBqU"
ADMIN_ID = 6290314134
BOT_USERNAME = "@FEMBOYSecULPbot"

# File paths
ULP_DIRECTORY = "."  # Directory containing ULP files
MAIN_DATABASE = "main.txt"  # Main consolidated database - HIDDEN FROM USERS
USERS_FILE = "users.json"
INVITES_FILE = "invites.json"
LOG_FILE = "bot.log"
SPAM_LOG_FILE = "spam_log.csv"
BAN_LOG_FILE = "ban_log.csv"
SEARCH_LOG_FILE = "search_log.csv"

# Limits
NORMAL_LINE_LIMIT = 1000000  # 1M lines for normal users
PREMIUM_LINE_LIMIT = 10000000  # 10M lines for premium users
FILE_PART_SIZE = 45 * 1024 * 1024  # 45MB per part (Telegram limit)
MAX_FILE_SIZE = 45 * 1024 * 1024  # 45MB Telegram limit

# Search settings
MAX_GREP_TIME = 30  # seconds
MAX_RESULTS_PREVIEW = 50  # Max results to show in preview

# Spam protection
SPAM_LIMIT = 8  # Max messages per minute
SPAM_WINDOW = 60  # 1 minute window
BAN_DURATIONS = [300, 1800, 3600, 86400]  # 5min, 30min, 1h, 1d
MAX_SEARCHES_PER_DAY = 50  # Daily search limit
SEARCH_COOLDOWN = 30  # seconds between searches for normal users

# Invite system
INVITE_BONUS_SEARCHES = 1  # Searches given for successful invite
INVITE_CODE_LENGTH = 8

# Allowed characters for search terms (prevents command injection)
ALLOWED_CHARS = re.compile(r'^[a-zA-Z0-9\s@._:/\\-]+$')
DOMAIN_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$')
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9._-]{3,50}$')
PASSWORD_PATTERN = re.compile(r'^[^\n\r\t\f\v]{1,100}$')
KEYWORD_PATTERN = re.compile(r'^[a-zA-Z0-9\s@._:/\\-]{2,100}$')

# ================= SETUP LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================= INITIALIZE BOT =================
app = Client(
    "ulp_search_bot",
    bot_token=BOT_TOKEN,
    workers=20,  # Increase worker count for better performance
    workdir="./sessions",
    sleep_threshold=10,
    max_concurrent_transmissions=5
)

# ================= CUTE FEMBOY PHRASES =================
CUTE_PHRASES = [
    "hold on potato, im digging through the data~",
    "searching like a good femboy, please wait :3",
    "scanning the database with love and care~",
    "looking for your stuff, be patient cutie :3",
    "sifting through billions of lines for you~",
    "working hard to find your results! :D",
    "be patient, good things take time~",
    "searching with maximum femboy power!",
    "hold tight, im on it cutie~",
    "almost there, just a bit more~"
]

PROGRESS_PHRASES = [
    "found some potatoes in the data patch!",
    "unearthing potatoes from the database~",
    "found {count} lines so far! good stuff :3",
    "ooh, i see something interesting~",
    "the potato harvest is going well! :D",
    "lots of data potatoes coming up~",
    "your results are growing like potatoes!",
    "look at all these cute data potatoes~"
]

COMPLETION_PHRASES = [
    "all done cutie! heres your data~ :3",
    "potato harvest complete! enjoy your results~",
    "found everything for you, sweetie!",
    "search finished successfully! :3",
    "your data is ready, cutie potato~",
    "all set! here are your results :D"
]

ERROR_PHRASES = [
    "oh no, something went wrong potato!",
    "oopsie, error occurred :<",
    "not working right now, try again cutie~",
    "uh oh, potato error! :("
]

# ================= DATA STRUCTURES =================
class UserData:
    def __init__(self):
        self.user_id = 0
        self.username = ""
        self.first_name = ""
        self.search_count = 0
        self.daily_searches = 0
        self.last_search_date = None
        self.last_search_time = datetime.min
        self.invited_count = 0
        self.invited_users = set()
        self.is_premium = False
        self.is_banned = False
        self.banned_until = None
        self.ban_reason = ""
        self.ban_count = 0
        self.total_results_found = 0
        self.invite_code = None
        self.received_invites = 0
        self.created_at = datetime.now()

# Global data stores
users_data = {}
active_searches = set()
startup_time = datetime.now()
database_line_count = 0
database_size_gb = 0

# ================= SECURITY FUNCTIONS =================
def sanitize_search_term(term: str, search_type: str) -> Tuple[bool, str]:
    """Sanitize and validate search term to prevent command injection"""
    if not term or len(term) > 100:
        return False, "term too long or empty"
    
    # Remove any null bytes and control characters
    term = ''.join(char for char in term if ord(char) >= 32 and ord(char) != 127)
    
    # Check allowed characters based on search type
    if search_type in ["domain", "email", "username", "keyword"]:
        if not ALLOWED_CHARS.match(term):
            return False, "contains invalid characters"
    
    if search_type == "domain":
        if not DOMAIN_PATTERN.match(term):
            return False, "invalid domain format"
    
    elif search_type == "email":
        if not EMAIL_PATTERN.match(term):
            return False, "invalid email format"
    
    elif search_type == "username":
        if not USERNAME_PATTERN.match(term):
            return False, "invalid username format"
    
    elif search_type == "password":
        if not PASSWORD_PATTERN.match(term):
            return False, "invalid password format"
    
    elif search_type == "keyword":
        if not KEYWORD_PATTERN.match(term):
            return False, "invalid keyword format"
    
    return True, term

def escape_grep_pattern(pattern: str) -> str:
    """Escape pattern for grep to prevent command injection"""
    # Escape special regex characters
    special_chars = r'\.^$*+?{}[]|()'
    for char in special_chars:
        pattern = pattern.replace(char, '\\' + char)
    return pattern

# ================= FILE MANAGEMENT =================
async def check_main_database():
    """Check if main database exists and is accessible"""
    global MAIN_DATABASE, database_line_count, database_size_gb
    
    if not os.path.exists(MAIN_DATABASE):
        logger.error(f"Main database {MAIN_DATABASE} not found!")
        txt_files = [f for f in os.listdir(ULP_DIRECTORY) 
                    if f.endswith('.txt') and os.path.getsize(f) > 1000000]
        if txt_files:
            MAIN_DATABASE = txt_files[0]
            logger.info(f"Using {MAIN_DATABASE} as main database")
        else:
            raise FileNotFoundError("No suitable database file found!")
    
    file_size = os.path.getsize(MAIN_DATABASE)
    database_size_gb = file_size / (1024 * 1024 * 1024)
    
    # Get line count efficiently
    try:
        result = subprocess.run(
            ['wc', '-l', MAIN_DATABASE], 
            capture_output=True, text=True, timeout=30, check=False
        )
        if result.returncode == 0:
            database_line_count = int(result.stdout.split()[0])
        else:
            database_line_count = 0
    except:
        database_line_count = 0
    
    logger.info(f"Main database: {MAIN_DATABASE} ({database_size_gb:.2f} GB, {database_line_count:,} lines)")
    return True

# ================= USER MANAGEMENT =================
async def load_user_data():
    """Load user data from JSON file"""
    global users_data
    try:
        if os.path.exists(USERS_FILE):
            async with aiofiles.open(USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.loads(await f.read())
                for user_id_str, user_dict in data.items():
                    user_id = int(user_id_str)
                    ud = UserData()
                    ud.user_id = user_id
                    ud.username = user_dict.get('username', '')
                    ud.first_name = user_dict.get('first_name', '')
                    ud.search_count = user_dict.get('search_count', 0)
                    ud.daily_searches = user_dict.get('daily_searches', 0)
                    ud.is_premium = user_dict.get('is_premium', False)
                    ud.is_banned = user_dict.get('is_banned', False)
                    ud.invited_count = user_dict.get('invited_count', 0)
                    ud.ban_count = user_dict.get('ban_count', 0)
                    ud.total_results_found = user_dict.get('total_results_found', 0)
                    ud.invite_code = user_dict.get('invite_code')
                    ud.received_invites = user_dict.get('received_invites', 0)
                    ud.invited_users = set(user_dict.get('invited_users', []))
                    
                    if user_dict.get('banned_until'):
                        ud.banned_until = datetime.fromisoformat(user_dict['banned_until'])
                    
                    if user_dict.get('last_search_date'):
                        ud.last_search_date = datetime.fromisoformat(user_dict['last_search_date']).date()
                    
                    if user_dict.get('last_search_time'):
                        ud.last_search_time = datetime.fromisoformat(user_dict['last_search_time'])
                    
                    if user_dict.get('created_at'):
                        ud.created_at = datetime.fromisoformat(user_dict['created_at'])
                    
                    users_data[user_id] = ud
            
            logger.info(f"Loaded {len(users_data)} users from {USERS_FILE}")
    except FileNotFoundError:
        logger.info("No existing user data file, starting fresh")
        users_data = {}
    except Exception as e:
        logger.error(f"Error loading user data: {e}")
        users_data = {}

async def save_user_data():
    """Save user data to JSON file"""
    try:
        data = {}
        for user_id, ud in users_data.items():
            user_dict = {
                'user_id': ud.user_id,
                'username': ud.username,
                'first_name': ud.first_name,
                'search_count': ud.search_count,
                'daily_searches': ud.daily_searches,
                'is_premium': ud.is_premium,
                'is_banned': ud.is_banned,
                'invited_count': ud.invited_count,
                'ban_count': ud.ban_count,
                'total_results_found': ud.total_results_found,
                'invite_code': ud.invite_code,
                'received_invites': ud.received_invites,
                'invited_users': list(ud.invited_users),
                'created_at': ud.created_at.isoformat()
            }
            
            if ud.banned_until:
                user_dict['banned_until'] = ud.banned_until.isoformat()
            
            if ud.last_search_date:
                user_dict['last_search_date'] = datetime.combine(
                    ud.last_search_date, datetime.min.time()
                ).isoformat()
            
            if ud.last_search_time and ud.last_search_time > datetime.min:
                user_dict['last_search_time'] = ud.last_search_time.isoformat()
            
            data[str(user_id)] = user_dict
        
        async with aiofiles.open(USERS_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2))
        
        logger.debug(f"Saved {len(users_data)} users to {USERS_FILE}")
    except Exception as e:
        logger.error(f"Error saving user data: {e}")

def get_or_create_user(user_id: int, message: Message = None) -> UserData:
    """Get existing user or create new one"""
    if user_id not in users_data:
        ud = UserData()
        ud.user_id = user_id
        
        if message and message.from_user:
            ud.username = message.from_user.username or ""
            ud.first_name = message.from_user.first_name or ""
        
        # Generate unique invite code
        import random
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=INVITE_CODE_LENGTH))
        ud.invite_code = code
        
        users_data[user_id] = ud
        asyncio.create_task(save_user_data())
    
    return users_data[user_id]

# ================= SPAM PROTECTION =================
async def check_spam(user: UserData) -> Tuple[bool, Optional[str]]:
    """Check if user is spamming, return (is_spam, reason)"""
    now = datetime.now()
    
    # Reset daily counter if new day
    if user.last_search_date != now.date():
        user.daily_searches = 0
        user.last_search_date = now.date()
        await save_user_data()
    
    # Check daily limit
    if user.daily_searches >= MAX_SEARCHES_PER_DAY and not user.is_premium:
        return True, f"daily limit reached ({MAX_SEARCHES_PER_DAY} searches) potato"
    
    # Check ban status
    if user.is_banned and user.banned_until:
        if now < user.banned_until:
            remaining = (user.banned_until - now).total_seconds()
            minutes = int(remaining // 60)
            return True, f"banned for {minutes} more minutes potato"
        else:
            user.is_banned = False
            user.banned_until = None
            await save_user_data()
    
    # Check cooldown for non-premium users
    if not user.is_premium and user.last_search_time > datetime.min:
        cooldown = SEARCH_COOLDOWN
        time_since_last = (now - user.last_search_time).total_seconds()
        if time_since_last < cooldown:
            wait_time = int(cooldown - time_since_last)
            return True, f"please wait {wait_time} seconds between searches potato :3"
    
    return False, None

async def log_ban(user_id: int, duration: int, reason: str, admin_id: int):
    """Log ban to CSV file"""
    try:
        file_exists = os.path.exists(BAN_LOG_FILE)
        async with aiofiles.open(BAN_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            if not file_exists:
                await f.write('user_id,timestamp,duration,reason,admin_id\n')
            await f.write(f'{user_id},{datetime.now().isoformat()},{duration},{reason},{admin_id}\n')
    except Exception as e:
        logger.error(f"Error logging ban: {e}")

# ================= ULTRA-FAST SEARCH =================
async def grep_search_safe(term: str, search_type: str, user: UserData) -> Tuple[List[str], int]:
    """
    Safe grep search using subprocess with proper escaping
    Returns (results, count)
    """
    # Sanitize and escape the search term
    escaped_term = escape_grep_pattern(term)
    
    # Determine result limit
    max_lines = PREMIUM_LINE_LIMIT if user.is_premium else NORMAL_LINE_LIMIT
    
    try:
        # Use grep with -a to treat binary as text, -i for case insensitive
        # -m to limit results, -h to hide filename
        cmd = [
            'grep', '-a', '-i', '-h', '-m', str(max_lines),
            '--', escaped_term, MAIN_DATABASE
        ]
        
        start_time = time.time()
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=1024 * 1024  # 1MB buffer
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), 
                timeout=MAX_GREP_TIME
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.warning(f"Search timeout for '{term}' after {MAX_GREP_TIME}s")
            return [], 0
        
        if proc.returncode in [0, 1]:  # 0=found, 1=not found
            lines = stdout.decode('utf-8', errors='ignore').splitlines()
            
            # Filter out lines that don't actually contain the term (grep sometimes returns similar)
            term_lower = term.lower()
            filtered_lines = [
                line for line in lines 
                if term_lower in line.lower()
            ]
            
            elapsed = time.time() - start_time
            logger.info(f"Search '{term}' found {len(filtered_lines)} lines in {elapsed:.2f}s")
            
            # For normal users, show only 60% of results
            if not user.is_premium and filtered_lines:
                keep_count = int(len(filtered_lines) * 0.6)
                keep_count = max(1, keep_count)
                filtered_lines = filtered_lines[:keep_count]
            
            return filtered_lines, len(filtered_lines)
        else:
            error = stderr.decode('utf-8', errors='ignore')
            logger.error(f"Grep error for '{term}': {error}")
            return [], 0
            
    except Exception as e:
        logger.error(f"Search error for '{term}': {e}")
        return [], 0

# ================= FILE CREATION =================
def sanitize_filename(text: str) -> str:
    """Sanitize filename to prevent path traversal"""
    # Remove any path separators and special chars
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    # Limit length
    if len(text) > 50:
        text = text[:50]
    return text

async def create_result_file(results: List[str], search_type: str, term: str, user: UserData) -> Tuple[io.BytesIO, str]:
    """Create result file with cute femboy header"""
    # Sanitize term for filename
    safe_term = sanitize_filename(term)
    if not safe_term:
        safe_term = "search_results"
    
    # Format header
    header = f"""ULP SEARCH RESULTS
by @FEMBOYSecULPbot

search performed with love by femboy bot potato~
search details:
  type: {search_type}
  term: {term}
  results: {len(results):,}
  user: {'premium :D' if user.is_premium else 'normal potato'}
  date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

thank you for using our service!
contact @kurdfemboys for premium potato

{'=' * 50}

"""
    
    content = '\n'.join(results)
    full_content = header + content
    
    # Create filename with required format
    filename = f"@FEMBOYSecULPbot_{search_type}_{safe_term}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    # Create bytes buffer
    buffer = io.BytesIO(full_content.encode('utf-8'))
    buffer.seek(0)
    buffer.name = filename
    
    return buffer, filename

async def split_large_file(content: str, base_name: str) -> List[Tuple[io.BytesIO, str]]:
    """Split large content into multiple zip files"""
    files = []
    content_bytes = content.encode('utf-8')
    total_size = len(content_bytes)
    
    if total_size <= MAX_FILE_SIZE:
        # Single file
        buffer = io.BytesIO(content_bytes)
        buffer.seek(0)
        buffer.name = base_name
        files.append((buffer, base_name))
    else:
        # Split into parts and zip each part
        num_parts = (total_size // MAX_FILE_SIZE) + 1
        for i in range(num_parts):
            start = i * MAX_FILE_SIZE
            end = min((i + 1) * MAX_FILE_SIZE, total_size)
            part_content = content_bytes[start:end]
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr(base_name, part_content.decode('utf-8', errors='ignore'))
            zip_buffer.seek(0)
            
            # Format zip filename
            zip_name = f"@FEMBOYSecULPbot_{base_name.replace('.txt', '')}_part{i+1}.zip"
            zip_buffer.name = zip_name
            files.append((zip_buffer, zip_name))
    
    return files

# ================= KEYBOARDS =================
def create_main_keyboard() -> ReplyKeyboardMarkup:
    """Create main menu keyboard"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("🔍 Search Domain"), KeyboardButton("👤 Search Username")],
            [KeyboardButton("🔑 Search Password"), KeyboardButton("📧 Search Email")],
            [KeyboardButton("📝 Search Keyword"), KeyboardButton("📊 My Stats")],
            [KeyboardButton("👥 Invite Friends"), KeyboardButton("⭐ Premium Info")],
            [KeyboardButton("❓ Help"), KeyboardButton("ℹ️ About")]
        ],
        resize_keyboard=True
    )
    return keyboard

def create_inline_premium_keyboard() -> InlineKeyboardMarkup:
    """Create inline keyboard for premium"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton("💎 Contact for Premium", url="https://t.me/kurdfemboys"),
                InlineKeyboardButton("📢 Join Channel", url="https://t.me/FEMBOYSec")
            ]
        ]
    )
    return keyboard

def create_inline_invite_keyboard(invite_code: str) -> InlineKeyboardMarkup:
    """Create invite keyboard with user's code"""
    invite_link = f"https://t.me/{BOT_USERNAME[1:]}?start={invite_code}"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton("📋 Copy Invite Code", callback_data=f"copy_{invite_code}"),
                InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={invite_link}")
            ]
        ]
    )
    return keyboard

# ================= LOGGING =================
async def log_search(user_id: int, search_type: str, term: str, results: int, is_premium: bool):
    """Log search to CSV"""
    try:
        file_exists = os.path.exists(SEARCH_LOG_FILE)
        async with aiofiles.open(SEARCH_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            if not file_exists:
                await f.write('user_id,timestamp,type,term,results,is_premium\n')
            # Escape term for CSV
            escaped_term = term.replace('"', '""')
            await f.write(f'{user_id},{datetime.now().isoformat()},{search_type},"{escaped_term}",{results},{is_premium}\n')
    except Exception as e:
        logger.error(f"Error logging search: {e}")

# ================= COMMAND HANDLERS =================
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Handle /start command with invite system"""
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message)
    
    # Check invite code
    if len(message.command) > 1:
        invite_code = message.command[1]
        if len(invite_code) == INVITE_CODE_LENGTH:
            # Find inviter
            inviter_id = None
            for uid, ud in users_data.items():
                if ud.invite_code == invite_code and uid != user_id:
                    inviter_id = uid
                    break
            
            if inviter_id:
                inviter = users_data[inviter_id]
                if user_id not in inviter.invited_users:
                    inviter.invited_users.add(user_id)
                    inviter.invited_count += 1
                    inviter.search_count -= INVITE_BONUS_SEARCHES
                    user.received_invites += 1
                    
                    await save_user_data()
                    
                    try:
                        await client.send_message(
                            inviter_id,
                            f"🎉 friend joined using your invite potato!\n"
                            f"you received {INVITE_BONUS_SEARCHES} bonus search!\n"
                            f"total invited: {inviter.invited_count} :3"
                        )
                    except:
                        pass
    
    # Reset daily searches if needed
    now = datetime.now()
    if user.last_search_date != now.date():
        user.daily_searches = 0
        user.last_search_date = now.date()
    
    welcome_text = f"""✨ **welcome to ULP Search Bot** ✨
{random.choice(CUTE_PHRASES)}

hello cutie~ im your friendly femboy search assistant!
i help you search through massive databases with love and care~

📊 **database info:**
  • file: `secured.db`
  • size: `{database_size_gb:.1f} GB`
  • lines: `{database_line_count:,}`

✨ **features:**
  • ultra-fast grep search (3-5 seconds!)
  • live progress updates
  • cute femboy interface potato :3
  • invite system for bonus searches
  • premium for full results

👤 **your status:**
  • searches today: `{user.daily_searches}/{MAX_SEARCHES_PER_DAY}`
  • premium: `{'yes! full results! :D' if user.is_premium else 'no (40% results hidden) potato'}`
  • invite code: `{user.invite_code}`

use buttons below to start searching~ :3
"""
    
    await message.reply_text(
        welcome_text,
        reply_markup=create_main_keyboard(),
        parse_mode=enums.ParseMode.MARKDOWN
    )

# Search command handlers
@app.on_message(filters.regex("^🔍 Search Domain$"))
async def search_domain_prompt(client: Client, message: Message):
    user = get_or_create_user(message.from_user.id, message)
    
    # Check spam first
    is_spam, reason = await check_spam(user)
    if is_spam:
        await message.reply_text(f"⛔ {reason}")
        return
    
    await message.reply_text(
        "🌐 **potato please enter the domain to search for:**\n"
        "example: `example.com` or `sub.example.com`\n\n"
        "allowed characters: letters, numbers, dots, hyphens"
    )

@app.on_message(filters.regex("^👤 Search Username$"))
async def search_username_prompt(client: Client, message: Message):
    user = get_or_create_user(message.from_user.id, message)
    
    is_spam, reason = await check_spam(user)
    if is_spam:
        await message.reply_text(f"⛔ {reason}")
        return
    
    await message.reply_text(
        "👤 **potato please enter the username to search for:**\n"
        "example: `john_doe` or `user123`\n\n"
        "allowed characters: letters, numbers, dots, underscores, hyphens"
    )

@app.on_message(filters.regex("^🔑 Search Password$"))
async def search_password_prompt(client: Client, message: Message):
    user = get_or_create_user(message.from_user.id, message)
    
    is_spam, reason = await check_spam(user)
    if is_spam:
        await message.reply_text(f"⛔ {reason}")
        return
    
    await message.reply_text(
        "🔑 **potato please enter the password to search for:**\n"
        "any characters are allowed except newlines\n\n"
        "example: `mypassword123!`"
    )

@app.on_message(filters.regex("^📧 Search Email$"))
async def search_email_prompt(client: Client, message: Message):
    user = get_or_create_user(message.from_user.id, message)
    
    is_spam, reason = await check_spam(user)
    if is_spam:
        await message.reply_text(f"⛔ {reason}")
        return
    
    await message.reply_text(
        "📧 **potato please enter the email to search for:**\n"
        "example: `user@example.com`\n\n"
        "allowed characters: letters, numbers, dots, @, underscores, hyphens"
    )

@app.on_message(filters.regex("^📝 Search Keyword$"))
async def search_keyword_prompt(client: Client, message: Message):
    user = get_or_create_user(message.from_user.id, message)
    
    is_spam, reason = await check_spam(user)
    if is_spam:
        await message.reply_text(f"⛔ {reason}")
        return
    
    await message.reply_text(
        "📝 **potato please enter the keyword to search for:**\n"
        "example: `netflix` or `facebook login`\n\n"
        "allowed characters: letters, numbers, spaces, @, ., :, /, -, _"
    )

# Process search queries
@app.on_message(filters.text & filters.private & ~filters.regex("^[/🔍👤🔑📧📝📊👥⭐❓ℹ️]"))
async def process_search(client: Client, message: Message):
    """Process search terms"""
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message)
    term = message.text.strip()
    
    # Check if we're waiting for a search term
    # We'll determine search type from previous message
    try:
        prev_msg = await client.get_messages(message.chat.id, message.id - 1)
        prompt_text = prev_msg.text if prev_msg else ""
    except:
        prompt_text = ""
    
    # Determine search type from prompt
    search_type = None
    if "domain" in prompt_text.lower():
        search_type = "domain"
    elif "username" in prompt_text.lower():
        search_type = "username"
    elif "password" in prompt_text.lower():
        search_type = "password"
    elif "email" in prompt_text.lower():
        search_type = "email"
    elif "keyword" in prompt_text.lower():
        search_type = "keyword"
    else:
        # Not a search, ignore
        return
    
    # Sanitize and validate term
    is_valid, validated_term = sanitize_search_term(term, search_type)
    if not is_valid:
        await message.reply_text(f"❌ invalid {search_type} format: {validated_term}\nplease try again potato~")
        return
    
    # Final spam check
    is_spam, spam_reason = await check_spam(user)
    if is_spam:
        await message.reply_text(f"⛔ {spam_reason}")
        return
    
    # Check if already searching
    if user_id in active_searches:
        await message.reply_text("⏳ you already have an active search potato! please wait~")
        return
    
    active_searches.add(user_id)
    
    try:
        # Send initial progress message
        progress_msg = await message.reply_text(
            f"{random.choice(CUTE_PHRASES)}\n\n"
            f"🔍 searching for: `{validated_term}`\n"
            f"📁 type: {search_type}\n"
            f"👤 user: {'⭐ premium' if user.is_premium else '🥔 normal'}\n\n"
            f"⏳ search status:\n"
            f"  • lines searched: `{database_line_count:,}`\n"
            f"  • lines found: `0`\n\n"
            f"live updating every second potato~",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        # Perform search
        results, result_count = await grep_search_safe(validated_term, search_type, user)
        
        # Update user stats
        user.search_count += 1
        user.daily_searches += 1
        user.last_search_time = datetime.now()
        user.last_search_date = datetime.now().date()
        user.total_results_found += result_count
        
        await save_user_data()
        await log_search(user_id, search_type, validated_term, result_count, user.is_premium)
        
        # Delete progress message
        await progress_msg.delete()
        
        # Handle results
        if results:
            completion_msg = await message.reply_text(
                f"{random.choice(COMPLETION_PHRASES)}\n\n"
                f"✅ **search complete!**\n"
                f"  • term: `{validated_term}`\n"
                f"  • type: {search_type}\n"
                f"  • results: `{result_count:,}` lines\n"
                f"  • status: `{'premium (100% shown) :D' if user.is_premium else 'normal (60% shown) potato'}`\n\n"
                f"📦 creating file potato...",
                parse_mode=enums.ParseMode.MARKDOWN
            )
            
            # Create and send file
            buffer, filename = await create_result_file(results, search_type, validated_term, user)
            
            await completion_msg.delete()
            
            file_size = buffer.getbuffer().nbytes
            if file_size > MAX_FILE_SIZE:
                await message.reply_text("📦 file is large, splitting into parts potato...")
                content = buffer.getvalue().decode('utf-8')
                files = await split_large_file(content, filename)
                
                for file_buffer, part_name in files:
                    file_buffer.seek(0)
                    await client.send_document(
                        chat_id=user_id,
                        document=InputFile(file_buffer, filename=part_name),
                        caption=f"🥔 part: `{part_name}` :3"
                    )
            else:
                buffer.seek(0)
                await client.send_document(
                    chat_id=user_id,
                    document=InputFile(buffer, filename=filename),
                    caption=f"🥔 search results for: `{validated_term}` :3"
                )
            
            # Premium upsell for non-premium users
            if not user.is_premium and result_count > 100:
                await message.reply_text(
                    f"💎 **want full results potato?**\n\n"
                    f"upgrade to premium for:\n"
                    f"  • 100% results (vs 60% now)\n"
                    f"  • up to 10M lines per search\n"
                    f"  • no daily limits\n"
                    f"  • no cooldowns\n\n"
                    f"contact @kurdfemboys for premium! :3",
                    reply_markup=create_inline_premium_keyboard()
                )
        else:
            await message.reply_text(
                f"❌ no results found for `{validated_term}` potato :<\n\n"
                f"try:\n"
                f"  • different search terms\n"
                f"  • shorter keywords\n"
                f"  • contact @kurdfemboys for help~"
            )
    
    except Exception as e:
        logger.error(f"Search error for user {user_id}: {e}")
        await message.reply_text(
            f"{random.choice(ERROR_PHRASES)}\n"
            f"error: `{str(e)[:100]}`\n"
            f"please try again or contact @kurdfemboys"
        )
    
    finally:
        active_searches.discard(user_id)

# Stats command
@app.on_message(filters.regex("^📊 My Stats$"))
async def user_stats(client: Client, message: Message):
    """Show user statistics"""
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message)
    
    stats_text = f"""📊 **your statistics potato :3**

👤 **user info:**
  • id: `{user_id}`
  • premium: `{'yes! full access! :D' if user.is_premium else 'no (upgrade for full) potato'}`
  • status: `{'banned' if user.is_banned else 'active'}`

🔍 **search stats:**
  • total searches: `{user.search_count:,}`
  • today's searches: `{user.daily_searches}/{MAX_SEARCHES_PER_DAY}`
  • total results found: `{user.total_results_found:,}`
  • last search: `{user.last_search_time.strftime('%Y-%m-%d %H:%M') if user.last_search_time > datetime.min else 'never'}`

👥 **invite system:**
  • your invite code: `{user.invite_code}`
  • friends invited: `{user.invited_count}`
  • received invites: `{user.received_invites}`
  • bonus searches: `{user.received_invites * INVITE_BONUS_SEARCHES}`

🤖 **bot info:**
  • database lines: `{database_line_count:,}`
  • normal limit: `{NORMAL_LINE_LIMIT:,}` lines
  • premium limit: `{PREMIUM_LINE_LIMIT:,}` lines
  • search timeout: `{MAX_GREP_TIME}s`

invite friends to get bonus searches! :3
"""
    
    await message.reply_text(stats_text, parse_mode=enums.ParseMode.MARKDOWN)

# Invite command
@app.on_message(filters.regex("^👥 Invite Friends$"))
async def invite_friends(client: Client, message: Message):
    """Show invite information"""
    user_id = message.from_user.id
    user = get_or_create_user(user_id, message)
    
    invite_link = f"https://t.me/{BOT_USERNAME[1:]}?start={user.invite_code}"
    
    invite_text = f"""👥 **invite friends & get rewards potato! :3**

✨ **how it works:**
  1. share your invite link/code with friends
  2. when they join using your code
  3. you get `{INVITE_BONUS_SEARCHES}` bonus search!
  4. they get a warm welcome from me~

📋 **your invite code:**
`{user.invite_code}`

🔗 **your invite link:**
`{invite_link}`

📊 **your invite stats:**
  • friends invited: `{user.invited_count}`
  • received invites: `{user.received_invites}`
  • bonus searches earned: `{user.received_invites * INVITE_BONUS_SEARCHES}`

share the love and get more searches potato! :3"""
    
    await message.reply_text(
        invite_text, 
        reply_markup=create_inline_invite_keyboard(user.invite_code),
        parse_mode=enums.ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

# Premium info
@app.on_message(filters.regex("^⭐ Premium Info$"))
async def premium_info(client: Client, message: Message):
    """Show premium information"""
    premium_text = f"""💎 **premium features potato :D**

✨ **why go premium?**
  • get **100% search results** (normal: 60%)
  • up to **{PREMIUM_LINE_LIMIT:,} lines** per search (normal: {NORMAL_LINE_LIMIT:,})
  • **no daily search limits**
  • **no cooldowns** between searches
  • priority processing
  • exclusive support

📊 **comparison:**
