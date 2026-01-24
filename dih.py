import asyncio
import os
import re
import aiofiles
import zipfile
import io
import csv
import logging
import hashlib
import time
import concurrent.futures
from datetime import datetime, timedelta
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Set, Any
import subprocess

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Configuration
BOT_TOKEN = "8251499938:AAGZ5Vf5obSaaw2PXgRx80wZmXHm0NpBBqU"
ADMIN_ID = 6290314134
BOT_USERNAME = "@FEMBOYSecULPbot"

# File paths
ULP_DIRECTORY = "."  # Directory containing ULP files
USERS_FILE = "users.csv"
INVITES_FILE = "invites.csv"
LOG_FILE = "bot.log"
CACHE_FILE = "search_cache.json"
SPAM_LOG_FILE = "spam_log.csv"

# Limits
NORMAL_LINE_LIMIT = 1000000  # 1M lines for normal users
PREMIUM_LINE_LIMIT = 10000000  # 10M lines for premium users
FILE_PART_SIZE = 30 * 1024 * 1024  # 30MB per part
NORMAL_SEARCHES = 2  # Only 2 searches for normal users
NORMAL_KEYWORDS = 1  # Only 1 keyword for normal users
SEARCH_COOLDOWN = 300  # 5 minutes for keyword search
USER_COOLDOWN = 180  # 3 minutes between searches
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB Telegram limit

# Multi-processing
MAX_WORKERS = 8  # Number of parallel grep processes
BATCH_SIZE = 5  # Number of files per grep process
CHUNK_SIZE = 50000  # Lines to process per batch

# Spam protection
SPAM_LIMIT = 5  # Max messages per minute
SPAM_WINDOW = 60  # 1 minute window
BAN_DURATIONS = [300, 1800, 3600, 86400]  # 5min, 30min, 1h, 1d

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# User states
class UserStates(StatesGroup):
    waiting_for_domain = State()
    waiting_for_username = State()
    waiting_for_password = State()
    waiting_for_email = State()
    waiting_for_keyword = State()

# User data structure
class UserData:
    def __init__(self):
        self.search_count = 0
        self.keyword_count = 0
        self.last_search = datetime.min
        self.last_keyword = datetime.min
        self.invited_count = 0
        self.invited_users = set()
        self.is_premium = False
        self.is_banned = False
        self.is_limited = False
        self.limit_until = None
        self.spam_count = 0
        self.spam_reset_time = datetime.now()
        self.ban_count = 0
        self.search_times = deque(maxlen=10)

# Global dictionaries
users = {}
user_data = defaultdict(UserData)
search_cache = {}
ulp_files_cache = []  # Cache list of ULP files

# Load ULP files list
def load_ulp_files():
    global ulp_files_cache
    try:
        # Find all .txt files in directory
        ulp_files = [f for f in os.listdir(ULP_DIRECTORY) if f.endswith('.txt')]
        ulp_files.sort()  # Sort for consistent batching
        ulp_files_cache = ulp_files
        logger.info(f"Found {len(ulp_files)} ULP files")
        return ulp_files
    except Exception as e:
        logger.error(f"Error loading ULP files: {e}")
        return []

# Load user data from file
def load_user_data():
    global users, user_data
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    user_id = int(row['user_id'])
                    users[user_id] = {
                        'username': row.get('username', ''),
                        'date': row['date'],
                        'invited_by': int(row['invited_by']) if row['invited_by'] else None
                    }
                    ud = UserData()
                    ud.search_count = int(row.get('search_count', 0))
                    ud.keyword_count = int(row.get('keyword_count', 0))
                    ud.invited_count = int(row.get('invited_count', 0))
                    ud.is_premium = row.get('is_premium', '').lower() == 'true'
                    ud.is_banned = row.get('is_banned', '').lower() == 'true'
                    ud.is_limited = row.get('is_limited', '').lower() == 'true'
                    ud.ban_count = int(row.get('ban_count', 0))
                    if row.get('limit_until'):
                        ud.limit_until = datetime.fromisoformat(row['limit_until'])
                    user_data[user_id] = ud
        logger.info("User data loaded successfully")
    except Exception as e:
        logger.error(f"Error loading user data: {e}")

# Save user data
def save_user_data():
    try:
        with open(USERS_FILE, 'w', newline='') as f:
            fieldnames = ['user_id', 'username', 'date', 'invited_by', 'search_count', 
                         'keyword_count', 'invited_count', 'is_premium', 'is_banned', 
                         'is_limited', 'limit_until', 'ban_count']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for user_id, data in users.items():
                ud = user_data[user_id]
                writer.writerow({
                    'user_id': user_id,
                    'username': data.get('username', ''),
                    'date': data.get('date', datetime.now().isoformat()),
                    'invited_by': data.get('invited_by', ''),
                    'search_count': ud.search_count,
                    'keyword_count': ud.keyword_count,
                    'invited_count': ud.invited_count,
                    'is_premium': ud.is_premium,
                    'is_banned': ud.is_banned,
                    'is_limited': ud.is_limited,
                    'limit_until': ud.limit_until.isoformat() if ud.limit_until else '',
                    'ban_count': ud.ban_count
                })
        logger.info("User data saved")
    except Exception as e:
        logger.error(f"Error saving user data: {e}")

# Spam protection
def check_spam(user_id: int) -> Tuple[bool, Optional[int]]:
    now = datetime.now()
    if user_id not in user_data:
        return False, None
    
    user = user_data[user_id]
    
    if (now - user.spam_reset_time).total_seconds() > SPAM_WINDOW:
        user.spam_count = 0
        user.spam_reset_time = now
    
    user.spam_count += 1
    user.search_times.append(now)
    
    if len(user.search_times) >= SPAM_LIMIT:
        time_diff = (user.search_times[-1] - user.search_times[0]).total_seconds()
        if time_diff < SPAM_WINDOW:
            user.ban_count += 1
            ban_index = min(user.ban_count - 1, len(BAN_DURATIONS) - 1)
            ban_duration = BAN_DURATIONS[ban_index]
            user.is_banned = True
            user.limit_until = now + timedelta(seconds=ban_duration)
            save_user_data()
            
            with open(SPAM_LOG_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([user_id, now.isoformat(), user.ban_count, ban_duration])
            
            return True, ban_duration
    
    return False, None

# Track new users
async def track_new_user(user_id: int, username: str, invited_by: int = None):
    if user_id not in users:
        users[user_id] = {
            'username': username,
            'date': datetime.now().isoformat(),
            'invited_by': invited_by
        }
        user_data[user_id] = UserData()
        
        new_user_count = len([u for u in users.values() if u.get('date', '') > (datetime.now() - timedelta(days=1)).isoformat()])
        if new_user_count % 10 == 0:
            await send_users_csv_to_admin()
        
        save_user_data()

# Send CSV to admin
async def send_users_csv_to_admin():
    try:
        csv_data = io.StringIO()
        fieldnames = ['user_id', 'date', 'username']
        writer = csv.DictWriter(csv_data, fieldnames=fieldnames)
        writer.writeheader()
        
        for user_id, data in users.items():
            writer.writerow({
                'user_id': user_id,
                'date': data.get('date', ''),
                'username': data.get('username', '')
            })
        
        csv_bytes = csv_data.getvalue().encode()
        await bot.send_document(
            ADMIN_ID,
            types.InputFile(io.BytesIO(csv_bytes), filename=f"users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        )
    except Exception as e:
        logger.error(f"Error sending CSV to admin: {e}")

# Validation functions
def validate_domain(domain: str) -> bool:
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, domain)) and all(c.isalnum() or c in '.-:/' for c in domain)

def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_username(username: str) -> bool:
    return all(c.isalnum() or c in '._-' for c in username) and 3 <= len(username) <= 50

def validate_password(password: str) -> bool:
    return all(c.isprintable() and c not in '\n\r\t' for c in password) and 1 <= len(password) <= 100

def validate_keyword(keyword: str) -> bool:
    return all(c.isprintable() and c not in '\n\r\t\\\'\"' for c in keyword) and 2 <= len(keyword) <= 100

# Smart pattern extraction
def extract_smart_pattern(term: str, search_type: str) -> List[Tuple[str, str]]:
    patterns = []
    
    if search_type == "domain":
        parts = term.split('.')
        if len(parts) >= 2:
            if len(parts[-1]) >= 2 and len(parts[-2]) >= 2:
                pattern = f"{parts[-2][:4]}\\.{parts[-1]}"
                patterns.append((pattern, "strategy1"))
            
            if len(parts) >= 3:
                pattern = "\\.".join([p[:3] for p in parts[-3:]])
                patterns.append((pattern, "strategy2"))
            else:
                pattern = "\\.".join([p[:4] for p in parts[-2:]])
                patterns.append((pattern, "strategy2"))
            
            patterns.append((parts[0][:4], "strategy3"))
            patterns.append((term[:6], "strategy4"))
    
    elif search_type == "email":
        username, domain = term.split('@')
        patterns.append((username[:5], "strategy1"))
        domain_patterns = extract_smart_pattern(domain, "domain")
        for pat, strategy in domain_patterns:
            patterns.append((pat, f"domain_{strategy}"))
    
    elif search_type in ["username", "password"]:
        patterns.append((term[:3], "strategy1"))
        patterns.append((term[:4], "strategy2"))
        patterns.append((term[:5], "strategy3"))
        patterns.append((term[:6], "strategy4"))
    
    else:
        patterns.append((term[:3], "strategy1"))
        patterns.append((term[:4], "strategy2"))
        patterns.append((term[:5], "strategy3"))
    
    return patterns if patterns else [(term[:6], "default")]

# Get exact regex for search type
def get_exact_regex(term: str, search_type: str) -> re.Pattern:
    if search_type == "domain":
        escaped = re.escape(term)
        return re.compile(f'(https?://)?{escaped}(/|:| |\n|$)', re.IGNORECASE)
    elif search_type == "email":
        escaped = re.escape(term)
        return re.compile(f'[^a-zA-Z0-9]{escaped}[^a-zA-Z0-9]', re.IGNORECASE)
    elif search_type == "username":
        escaped = re.escape(term)
        return re.compile(f'[:/]({escaped})[:/]', re.IGNORECASE)
    elif search_type == "password":
        escaped = re.escape(term)
        return re.compile(f':[^:]*:({escaped})$', re.IGNORECASE)
    else:
        escaped = re.escape(term)
        return re.compile(escaped, re.IGNORECASE)

# Multi-threaded grep search
async def parallel_grep_search(pattern: str, files: List[str], progress_callback=None) -> List[str]:
    """Search pattern in multiple files in parallel"""
    results = []
    
    # Split files into batches
    file_batches = [files[i:i + BATCH_SIZE] for i in range(0, len(files), BATCH_SIZE)]
    
    async def search_batch(batch_files: List[str]) -> List[str]:
        batch_results = []
        try:
            # Create grep command for multiple files
            files_str = " ".join(batch_files)
            cmd = f"grep -r -i '{pattern}' {files_str} 2>/dev/null | head -n {CHUNK_SIZE}"
            
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if stdout:
                lines = stdout.decode('utf-8', errors='ignore').split('\n')
                batch_results.extend([clean_result_line(line) for line in lines if line.strip()])
            
            if progress_callback:
                progress_callback(len(batch_results))
                
        except Exception as e:
            logger.error(f"Batch search error: {e}")
        
        return batch_results
    
    # Run all batches in parallel
    tasks = [search_batch(batch) for batch in file_batches]
    all_batches = await asyncio.gather(*tasks)
    
    # Combine results
    for batch in all_batches:
        results.extend(batch)
    
    return results

# Ultra-fast parallel search
async def ultra_parallel_search(term: str, search_type: str, user_id: int, progress_msg: types.Message = None) -> Optional[List[str]]:
    """Perform ultra-fast parallel search with multiple strategies"""
    if user_id not in user_data:
        return None
    
    user = user_data[user_id]
    line_limit = PREMIUM_LINE_LIMIT if user.is_premium else NORMAL_LINE_LIMIT
    
    # Get ULP files
    ulp_files = ulp_files_cache if ulp_files_cache else load_ulp_files()
    if not ulp_files:
        return None
    
    # Get multiple search patterns
    patterns = extract_smart_pattern(term, search_type)
    exact_regex = get_exact_regex(term, search_type)
    
    results = []
    total_lines_found = 0
    seen = set()
    
    # Progress callback
    def update_progress(batch_count: int):
        nonlocal total_lines_found
        total_lines_found += batch_count
        if progress_msg and batch_count > 0:
            try:
                asyncio.create_task(
                    progress_msg.edit_text(
                        f"please wait potato, im checking it :3\n"
                        f"lines found till now {total_lines_found}\n"
                        f"Processing..."
                    )
                )
            except:
                pass
    
    # Process each pattern strategy
    for pattern_idx, (pattern, strategy) in enumerate(patterns):
        if len(results) >= line_limit:
            break
        
        if progress_msg:
            try:
                await progress_msg.edit_text(
                    f"please wait potato, im checking it :3\n"
                    f"lines found till now {total_lines_found}\n"
                    f"Strategy {pattern_idx + 1}/{len(patterns)}: {strategy}"
                )
            except:
                pass
        
        # Search with current pattern
        pattern_results = await parallel_grep_search(pattern, ulp_files, update_progress)
        
        # Filter with exact regex
        for line in pattern_results:
            if len(results) >= line_limit:
                break
            
            if line and line not in seen and exact_regex.search(line):
                seen.add(line)
                results.append(line)
    
    return results if results else None

# Two-phase search for better accuracy
async def two_phase_parallel_search(term: str, search_type: str, user_id: int, progress_msg: types.Message = None) -> Optional[List[str]]:
    """Two-phase search: Phase 1 quick filter, Phase 2 exact match"""
    if user_id not in user_data:
        return None
    
    user = user_data[user_id]
    line_limit = PREMIUM_LINE_LIMIT if user.is_premium else NORMAL_LINE_LIMIT
    
    ulp_files = ulp_files_cache if ulp_files_cache else load_ulp_files()
    if not ulp_files:
        return None
    
    results = []
    seen = set()
    
    # PHASE 1: Quick search with simple pattern
    if progress_msg:
        await progress_msg.edit_text(
            f"please wait potato, im checking it :3\n"
            f"Phase 1: Quick filtering...\n"
            f"lines found till now 0"
        )
    
    # Get initial pattern (first 4 chars)
    initial_pattern = term[:4]
    phase1_results = await parallel_grep_search(initial_pattern, ulp_files)
    
    # PHASE 2: Exact matching with regex
    if progress_msg:
        await progress_msg.edit_text(
            f"please wait potato, im checking it :3\n"
            f"Phase 2: Exact matching...\n"
            f"lines found till now 0"
        )
    
    exact_regex = get_exact_regex(term, search_type)
    
    # Process in chunks to avoid memory issues
    for i in range(0, len(phase1_results), 10000):
        chunk = phase1_results[i:i + 10000]
        
        for line in chunk:
            if len(results) >= line_limit:
                break
            
            if line and line not in seen and exact_regex.search(line):
                seen.add(line)
                results.append(line)
        
        # Update progress
        if progress_msg and i % 10000 == 0:
            try:
                await progress_msg.edit_text(
                    f"please wait potato, im checking it :3\n"
                    f"Phase 2: Exact matching...\n"
                    f"lines found till now {len(results)}"
                )
            except:
                pass
    
    return results if results else None

# Hybrid search - combines both methods
async def hybrid_parallel_search(term: str, search_type: str, user_id: int, progress_msg: types.Message = None) -> Optional[List[str]]:
    """Hybrid search using multiple parallel strategies"""
    if user_id not in user_data:
        return None
    
    user = user_data[user_id]
    line_limit = PREMIUM_LINE_LIMIT if user.is_premium else NORMAL_LINE_LIMIT
    
    ulp_files = ulp_files_cache if ulp_files_cache else load_ulp_files()
    if not ulp_files:
        return None
    
    results = []
    seen = set()
    
    # Multiple search tasks in parallel
    tasks = []
    
    # Task 1: Two-phase search
    tasks.append(two_phase_parallel_search(term, search_type, user_id, progress_msg))
    
    # Task 2: Pattern-based search
    tasks.append(ultra_parallel_search(term, search_type, user_id, progress_msg))
    
    # Task 3: Direct grep with term (for shorter terms)
    if len(term) <= 20:
        tasks.append(parallel_grep_search(term, ulp_files))
    
    # Run all tasks in parallel
    all_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Combine and deduplicate results
    for task_result in all_results:
        if isinstance(task_result, Exception):
            logger.error(f"Search task error: {task_result}")
            continue
        
        if task_result:
            for line in task_result:
                if len(results) >= line_limit:
                    break
                
                if line and line not in seen:
                    seen.add(line)
                    results.append(line)
    
    return results if results else None

def clean_result_line(line: str) -> str:
    """Clean result line - remove file paths and format nicely"""
    if not line:
        return ""
    
    # Remove file path prefix (like ./ulp-6.txt:)
    if ':' in line:
        parts = line.split(':', 1)
        if len(parts) > 1:
            # Check if first part looks like a file path
            if parts[0].endswith('.txt') or '/' in parts[0] or '\\' in parts[0]:
                line = parts[1].strip()
    
    # Clean up any remaining file indicators
    line = re.sub(r'^[./\\].*?\.txt:', '', line)
    
    return line.strip()

# Create split files
async def create_split_files(content: str, base_filename: str) -> List[Tuple[io.BytesIO, str]]:
    files = []
    
    content_bytes = content.encode('utf-8')
    total_size = len(content_bytes)
    
    if total_size <= FILE_PART_SIZE:
        buffer = io.BytesIO(content_bytes)
        buffer.seek(0)
        files.append((buffer, f"{base_filename}.txt"))
    else:
        num_parts = (total_size // FILE_PART_SIZE) + 1
        
        for i in range(num_parts):
            start = i * FILE_PART_SIZE
            end = min((i + 1) * FILE_PART_SIZE, total_size)
            part_bytes = content_bytes[start:end]
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr(f"{base_filename}_part{i+1}.txt", part_bytes.decode('utf-8', errors='ignore'))
            zip_buffer.seek(0)
            
            files.append((zip_buffer, f"{base_filename}_part{i+1}.zip"))
    
    return files

# Create result file
async def create_result_file(content: str, search_type: str, term: str) -> Tuple[str, List[Tuple[io.BytesIO, str]]]:
    header = f"""ULP BOT BY t.me/kurdfemboys

join FEMBOYSec channel, to see our free databases and insale ones, here you can find us:
@FEMBOYSec
@JNCBC1
@db_kurdistan


FEMBOYSec - Team

Search type: {search_type}
Search term: {term}
Results found: {len(content.splitlines())}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Search method: Parallel multi-file processing

"""
    
    full_content = header + content
    
    safe_term = re.sub(r'[^\w\-_]', '_', term)[:50]
    base_filename = f"@kurdfemboys_{search_type}_{safe_term}"
    
    files = await create_split_files(full_content, base_filename)
    
    return full_content, files

# Create main keyboard
def create_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    keyboard.add(
        KeyboardButton("🔍 Domain"),
        KeyboardButton("👤 Username")
    ).add(
        KeyboardButton("🔑 Password"),
        KeyboardButton("📧 Email")
    ).add(
        KeyboardButton("📝 Keyword"),
        KeyboardButton("ℹ️ Info")
    ).add(
        KeyboardButton("❓ Help"),
        KeyboardButton("💰 Premium")
    )
    return keyboard

# Start command handler
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Check spam
    is_spam, ban_duration = check_spam(user_id)
    if is_spam:
        await message.answer(
            f"You have been banned for {ban_duration // 60} minutes due to spam.\n"
            f"Please wait until the ban is lifted."
        )
        
        asyncio.create_task(schedule_unban(user_id, ban_duration))
        return
    
    # Check if user is banned
    if user_id in user_data and user_data[user_id].is_banned:
        ban_until = user_data[user_id].limit_until
        if ban_until and datetime.now() < ban_until:
            remaining = (ban_until - datetime.now()).total_seconds()
            await message.answer(
                f"You are banned for {int(remaining // 60)} more minutes.\n"
                f"Please wait until the ban is lifted."
            )
            return
        else:
            user_data[user_id].is_banned = False
            user_data[user_id].limit_until = None
            save_user_data()
    
    # Check for invite code
    invite_code = message.get_args()
    if invite_code and invite_code.isdigit():
        inviter_id = int(invite_code)
        if inviter_id != user_id and inviter_id in user_data:
            user_data[inviter_id].search_count = max(0, user_data[inviter_id].search_count - 1)
            user_data[inviter_id].invited_count += 1
            user_data[inviter_id].invited_users.add(user_id)
            save_user_data()
            
            try:
                await bot.send_message(
                    inviter_id, 
                    f"User {message.from_user.username or user_id} joined using your invite!\n"
                    f"You got 1 more search :D"
                )
            except:
                pass
    
    # Track new user
    await track_new_user(user_id, message.from_user.username, 
                        int(invite_code) if invite_code and invite_code.isdigit() else None)
    
    welcome_text = f"""Welcome to ULP Search Bot {BOT_USERNAME}!

⚠️ IMPORTANT: Searches take 3-10 minutes or more!
Be patient, the database is huge (560GB+).

Now with PARALLEL PROCESSING:
• Multiple files searched simultaneously
• Faster results with multi-threading
• Smart pattern matching

You have:
• {NORMAL_SEARCHES} searches total
• {NORMAL_KEYWORDS} keyword search
• Up to {NORMAL_LINE_LIMIT:,} lines per result

Premium users get:
• Unlimited searches
• Up to {PREMIUM_LINE_LIMIT:,} lines
• Priority processing

Use buttons below to search :3
"""
    
    await message.answer(welcome_text, reply_markup=create_main_keyboard())

# Schedule unban
async def schedule_unban(user_id: int, ban_duration: int):
    await asyncio.sleep(ban_duration)
    
    if user_id in user_data:
        user_data[user_id].is_banned = False
        user_data[user_id].limit_until = None
        save_user_data()
        
        try:
            await bot.send_message(
                user_id,
                "Your ban has been lifted! You can now use the bot again.\n"
                "Please avoid spamming to prevent future bans."
            )
        except:
            pass

# Common search handler
async def handle_search(message: types.Message, state: State, search_type: str, validate_func, process_func):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        await track_new_user(user_id, message.from_user.username)
    
    user = user_data[user_id]
    
    if user.is_banned:
        if user.limit_until:
            remaining = (user.limit_until - datetime.now()).total_seconds()
            if remaining > 0:
                await message.answer(f"You are banned for {int(remaining // 60)} more minutes.")
                return
            else:
                user.is_banned = False
                user.limit_until = None
                save_user_data()
    
    if user.is_limited and user.limit_until and datetime.now() < user.limit_until:
        remaining = (user.limit_until - datetime.now()).total_seconds()
        await message.answer(f"You are limited for {int(remaining // 60)} more minutes.")
        return
    
    if not user.is_premium and user.search_count >= NORMAL_SEARCHES:
        await message.answer(
            f"You've used all {NORMAL_SEARCHES} searches.\n"
            f"Invite friends to get more searches!"
        )
        return
    
    time_since_last = (datetime.now() - user.last_search).total_seconds()
    if time_since_last < USER_COOLDOWN:
        wait_time = int(USER_COOLDOWN - time_since_last)
        await message.answer(f"Please wait {wait_time} seconds before searching again :]")
        return
    
    if search_type == "keyword":
        if not user.is_premium and user.keyword_count >= NORMAL_KEYWORDS:
            await message.answer(
                f"You've used your {NORMAL_KEYWORDS} keyword search.\n"
                f"Normal users get only {NORMAL_KEYWORDS} keyword search."
            )
            return
        
        time_since_keyword = (datetime.now() - user.last_keyword).total_seconds()
        if time_since_keyword < SEARCH_COOLDOWN:
            wait_time = int(SEARCH_COOLDOWN - time_since_keyword)
            await message.answer(f"Keyword search cooldown: {wait_time} seconds left.")
            return
    
    await state.set()
    await message.answer(f"Please enter the {search_type} to search for:")

# Process search results
async def process_search_results(user_id: int, term: str, search_type: str, message: types.Message, state: FSMContext):
    user = user_data[user_id]
    
    wait_msg = await message.answer(f"please wait potato, im checking it :3\nlines found till now 0")
    
    try:
        # Use hybrid parallel search for best performance
        results = await hybrid_parallel_search(term, search_type, user_id, wait_msg)
        
        user.search_count += 1
        user.last_search = datetime.now()
        if search_type == "keyword":
            user.keyword_count += 1
            user.last_keyword = datetime.now()
        save_user_data()
        
        await wait_msg.delete()
        
        if results:
            content = '\n'.join(results)
            full_content, files = await create_result_file(content, search_type, term)
            
            result_count = len(results)
            await message.answer(
                f"Successfully found {result_count:,} lines.\n"
                f"Search completed using parallel processing!\n"
                f"contact @kurdfemboys if you faced any issues, or if you want to buy premium version.\n\n"
                f"Sending {len(files)} file(s)..."
            )
            
            for file_buffer, filename in files:
                try:
                    await bot.send_document(
                        chat_id=user_id,
                        document=types.InputFile(file_buffer, filename=filename),
                        caption=f"{search_type}: {term} | Parallel search"
                    )
                except Exception as e:
                    logger.error(f"Error sending file: {e}")
                    await message.answer(f"Error sending file: {filename}")
        
        else:
            await message.answer("No results found :/\nTry different search terms.")
    
    except Exception as e:
        logger.error(f"Search error: {e}")
        await message.answer("Error during search. Please try again later.")
    
    finally:
        await state.finish()

# Domain search
@dp.message_handler(lambda message: message.text == "🔍 Domain")
async def cmd_domain(message: types.Message):
    await handle_search(message, UserStates.waiting_for_domain, "domain", validate_domain, process_search_results)

@dp.message_handler(state=UserStates.waiting_for_domain)
async def process_domain(message: types.Message, state: FSMContext):
    term = message.text.strip()
    
    if not validate_domain(term):
        await message.answer("Invalid domain. Use format: example.com")
        return
    
    await message.answer(f"Searching domain: {term}\nThis may take 3-10 minutes...\nUsing parallel processing for speed!")
    await process_search_results(message.from_user.id, term, "domain", message, state)

# Username search
@dp.message_handler(lambda message: message.text == "👤 Username")
async def cmd_username(message: types.Message):
    await handle_search(message, UserStates.waiting_for_username, "username", validate_username, process_search_results)

@dp.message_handler(state=UserStates.waiting_for_username)
async def process_username(message: types.Message, state: FSMContext):
    term = message.text.strip()
    
    if not validate_username(term):
        await message.answer("Invalid username. Use letters, numbers, dots, underscores, hyphens only.")
        return
    
    await message.answer(f"Searching username: {term}\nThis may take 3-10 minutes...\nUsing parallel processing for speed!")
    await process_search_results(message.from_user.id, term, "username", message, state)

# Password search
@dp.message_handler(lambda message: message.text == "🔑 Password")
async def cmd_password(message: types.Message):
    await handle_search(message, UserStates.waiting_for_password, "password", validate_password, process_search_results)

@dp.message_handler(state=UserStates.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    term = message.text.strip()
    
    if not validate_password(term):
        await message.answer("Invalid password format.")
        return
    
    await message.answer(f"Searching password: {term}\nThis may take 3-10 minutes...\nUsing parallel processing for speed!")
    await process_search_results(message.from_user.id, term, "password", message, state)

# Email search
@dp.message_handler(lambda message: message.text == "📧 Email")
async def cmd_email(message: types.Message):
    await handle_search(message, UserStates.waiting_for_email, "email", validate_email, process_search_results)

@dp.message_handler(state=UserStates.waiting_for_email)
async def process_email(message: types.Message, state: FSMContext):
    term = message.text.strip()
    
    if not validate_email(term):
        await message.answer("Invalid email. Use format: user@example.com")
        return
    
    await message.answer(f"Searching email: {term}\nThis may take 3-10 minutes...\nUsing parallel processing for speed!")
    await process_search_results(message.from_user.id, term, "email", message, state)

# Keyword search
@dp.message_handler(lambda message: message.text == "📝 Keyword")
async def cmd_keyword(message: types.Message):
    await handle_search(message, UserStates.waiting_for_keyword, "keyword", validate_keyword, process_search_results)

@dp.message_handler(state=UserStates.waiting_for_keyword)
async def process_keyword(message: types.Message, state: FSMContext):
    term = message.text.strip()
    
    if not validate_keyword(term):
        await message.answer("Invalid keyword.")
        return
    
    await message.answer(f"Searching keyword: {term}\nThis may take 5-15 minutes...\nUsing parallel processing for speed!")
    await process_search_results(message.from_user.id, term, "keyword", message, state)

# Info command
@dp.message_handler(lambda message: message.text == "ℹ️ Info")
async def cmd_info(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        await track_new_user(user_id, message.from_user.username)
    
    user = user_data[user_id]
    searches_left = max(0, NORMAL_SEARCHES - user.search_count) if not user.is_premium else "Unlimited"
    keywords_left = max(0, NORMAL_KEYWORDS - user.keyword_count) if not user.is_premium else "Unlimited"
    
    info_text = f"""Your Info:

User ID: {user_id}
Searches used: {user.search_count}/{NORMAL_SEARCHES if not user.is_premium else '∞'}
Searches left: {searches_left}
Keyword searches left: {keywords_left}
Friends invited: {user.invited_count}
Premium: {'Yes :D' if user.is_premium else 'No'}
Status: {'Banned' if user.is_banned else 'Limited' if user.is_limited else 'Active'}
Ban count: {user.ban_count}

Bot: {BOT_USERNAME}
Database: 560GB+ (~60B lines)
Search method: Parallel multi-file processing
Search time: 3-10+ minutes
"""
    
    await message.answer(info_text)

# Help command
@dp.message_handler(lambda message: message.text == "❓ Help")
async def cmd_help(message: types.Message):
    help_text = f"""Help - {BOT_USERNAME}

⚠️ IMPORTANT:
• Searches take 3-10 minutes or more!
• Database is 560GB+ with ~60 billion lines
• Be patient and don't spam

NEW: Parallel Processing!
• Multiple files searched simultaneously
• Faster results with multi-threading
• Smart pattern matching algorithms

Limits (Normal users):
• {NORMAL_SEARCHES} total searches
• {NORMAL_KEYWORDS} keyword search
• {NORMAL_LINE_LIMIT:,} lines per result
• {USER_COOLDOWN//60} min cooldown between searches
• {SEARCH_COOLDOWN//60} min cooldown for keywords

Premium users get:
• Unlimited searches
• {PREMIUM_LINE_LIMIT:,} lines per result
• No cooldowns
• Priority processing

How to search:
1. Choose search type
2. Enter search term
3. Wait 3-10+ minutes
4. Receive results as file(s)

Search types:
• Domain - Search domains (example.com)
• Username - Search usernames
• Password - Search passwords
• Email - Search emails
• Keyword - Search any text

Invite friends to get more searches!

Contact @kurdfemboys for premium or issues.
"""
    
    await message.answer(help_text)

# Premium info button
@dp.message_handler(lambda message: message.text == "💰 Premium")
async def cmd_premium_button(message: types.Message):
    premium_text = f"""Premium Features - {BOT_USERNAME}

Get premium for:
• Unlimited searches (vs {NORMAL_SEARCHES})
• {PREMIUM_LINE_LIMIT:,} lines per result (vs {NORMAL_LINE_LIMIT:,})
• No {USER_COOLDOWN//60} minute cooldowns
• Priority parallel processing
• Faster results with multi-threading

Perfect for:
• Researchers
• Security professionals
• Data analysts
• Anyone needing extensive searches

Price: Contact @kurdfemboys

With 560GB+ database, premium ensures:
• Complete results
• No waiting
• Maximum lines
• Priority queue
• Advanced parallel algorithms

Get premium today! :D
"""
    
    await message.answer(premium_text)

# Admin commands
@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Access denied :[")
        return
    
    admin_text = f"""Admin Commands:

/ban <user_id> <minutes> - Ban user
/unban <user_id> - Unban user
/limit <user_id> <minutes> - Limit user
/unlimit <user_id> - Remove limit
/premium <user_id> - Give premium
/unpremium <user_id> - Remove premium
/stats - Show statistics
/users - Get users CSV
/searchstats - Search statistics
/reset <user_id> - Reset user
/spammers - Show spammers
/clean - Clean old data
/updatefiles - Update ULP files cache
"""
    
    await message.answer(admin_text)

@dp.message_handler(commands=['updatefiles'])
async def cmd_updatefiles(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    files = load_ulp_files()
    await message.answer(f"Updated ULP files cache: {len(files)} files found")

@dp.message_handler(commands=['premium'])
async def cmd_premium_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        args = message.get_args().split()
        if len(args) != 1:
            await message.answer("Usage: /premium <user_id>")
            return
        
        user_id = int(args[0])
        if user_id in user_data:
            user_data[user_id].is_premium = True
            save_user_data()
            
            await message.answer(f"Gave premium to user {user_id}")
            
            try:
                await bot.send_message(user_id, "You have been granted premium status! :D")
            except:
                pass
        else:
            await message.answer("User not found")
    except:
        await message.answer("Usage: /premium <user_id>")

@dp.message_handler(commands=['unpremium'])
async def cmd_unpremium_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        args = message.get_args().split()
        if len(args) != 1:
            await message.answer("Usage: /unpremium <user_id>")
            return
        
        user_id = int(args[0])
        if user_id in user_data:
            user_data[user_id].is_premium = False
            save_user_data()
            
            await message.answer(f"Removed premium from user {user_id}")
            
            try:
                await bot.send_message(user_id, "Your premium status has been removed.")
            except:
                pass
        else:
            await message.answer("User not found")
    except:
        await message.answer("Usage: /unpremium <user_id>")

@dp.message_handler(commands=['ban'])
async def cmd_ban(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        args = message.get_args().split()
        if len(args) != 2:
            await message.answer("Usage: /ban <user_id> <minutes>")
            return
        
        user_id = int(args[0])
        minutes = int(args[1])
        
        if user_id in user_data:
            user_data[user_id].is_banned = True
            user_data[user_id].limit_until = datetime.now() + timedelta(minutes=minutes)
            save_user_data()
            
            await message.answer(f"Banned user {user_id} for {minutes} minutes")
            
            try:
                await bot.send_message(
                    user_id,
                    f"You have been banned for {minutes} minutes.\n"
                    f"Reason: Admin decision"
                )
            except:
                pass
        else:
            await message.answer("User not found")
    except:
        await message.answer("Usage: /ban <user_id> <minutes>")

@dp.message_handler(commands=['unban'])
async def cmd_unban(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        args = message.get_args().split()
        if len(args) != 1:
            await message.answer("Usage: /unban <user_id>")
            return
        
        user_id = int(args[0])
        if user_id in user_data:
            user_data[user_id].is_banned = False
            user_data[user_id].limit_until = None
            save_user_data()
            
            await message.answer(f"Unbanned user {user_id}")
            
            try:
                await bot.send_message(user_id, "Your ban has been lifted by admin.")
            except:
                pass
        else:
            await message.answer("User not found")
    except:
        await message.answer("Usage: /unban <user_id>")

@dp.message_handler(commands=['users'])
async def cmd_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await send_users_csv_to_admin()
    await message.answer("Users CSV sent to admin")

@dp.message_handler(commands=['stats'])
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    total_users = len(users)
    premium_users = sum(1 for u in user_data.values() if u.is_premium)
    banned_users = sum(1 for u in user_data.values() if u.is_banned)
    active_users = total_users - banned_users
    ulp_files_count = len(ulp_files_cache) if ulp_files_cache else 0
    
    total_searches = sum(u.search_count for u in user_data.values())
    total_keywords = sum(u.keyword_count for u in user_data.values())
    
    stats_text = f"""Bot Statistics:

Total users: {total_users}
Active users: {active_users}
Premium users: {premium_users}
Banned users: {banned_users}

ULP files: {ulp_files_count}
Parallel workers: {MAX_WORKERS}
Batch size: {BATCH_SIZE} files

Total searches: {total_searches}
Total keywords: {total_keywords}

Memory usage: {len(users)} users loaded
Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    await message.answer(stats_text)

# Handle other text
@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def handle_other_messages(message: types.Message):
    current_state = await dp.current_state(user=message.from_user.id).get_state()
    if current_state:
        return
    
    await message.answer("Please use the buttons below:", reply_markup=create_main_keyboard())

# Initialize bot
async def on_startup(dp):
    load_user_data()
    load_ulp_files()  # Load ULP files on startup
    logger.info(f"Bot {BOT_USERNAME} started with parallel processing")
    
    try:
        await bot.send_message(ADMIN_ID, f"Bot {BOT_USERNAME} started successfully!\nParallel processing enabled with {MAX_WORKERS} workers.")
    except:
        pass

# Cleanup
async def on_shutdown(dp):
    save_user_data()
    logger.info("Bot shutting down")

# Run bot
if __name__ == '__main__':
    # Create necessary files
    for file in [USERS_FILE, SPAM_LOG_FILE]:
        if not os.path.exists(file):
            Path(file).touch()
    
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True)
