import logging
import json
import time
import os
import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import threading
from pathlib import Path
import hashlib

from telegram import Update, Chat, ChatMember, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Message, MessageEntity, InputMediaPhoto, InputMediaVideo, InputMediaDocument, User
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode, ChatType

# ===== CUTE CONFIGURATION =====
BOT_TOKEN = "8549469336:AAFUQTjqfBfESBkTgOsRbS_v1-P0VyL6ZTo"
OWNER_ID = 6290314134  # Your potato id
BOT_USERNAME = "@FemboysHelpBot"  # Added bot username
OWNER_CHANNEL = "@db_kurdistan"  # Your channel

# SINGLE archive group for files only
ARCHIVE_GROUP_ID = -5282634578  # Your main archive group

# File for storing data
DATA_DIR = "femboy_data"
DB_FILE = os.path.join(DATA_DIR, "bot_potato.db")

# ===== LOGGING SETUP =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== CUTE UTILITIES =====
def cute_header(text: str) -> str:
    """Add cute header to messages."""
    lines = ["ฅ^•ﻌ•^ฅ " * 1]
    lines.append(f"{text}")
    lines.append("ฅ^•ﻌ•^ฅ " * 1)
    return "\n".join(lines)

def potato_mention(user: User) -> str:
    """Create cute mention for users."""
    if user.username:
        return f"@{user.username} (little potato)"
    return f"{user.first_name} (cute bean)"

def femboy_style(text: str) -> str:
    """Add femboy-style formatting to text."""
    # Replace common phrases with cute versions
    replacements = {
        "hello": "hewwo",
        "hi": "haii",
        "sorry": "sowwy",
        "thank you": "thankies",
        "thanks": "tankies",
        "please": "pwease",
        "good": "gud",
        "very": "vewy",
        "really": "weawy",
        "love": "wuv",
        "cute": "cyoot",
        "admin": "big potato",
        "user": "smol bean",
        "group": "snuggle pile",
        "welcome": "welcome to the snuggle pile",
        "rules": "snuggle rules"
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
        text = text.replace(old.capitalize(), new.capitalize())
    
    return text

# ===== DATABASE SETUP =====
class Database:
    def __init__(self):
        self.setup_directories()
        self.init_database()
        self.cleanup_deleted_accounts()
    
    def setup_directories(self):
        """Create necessary directories for data storage."""
        os.makedirs(DATA_DIR, exist_ok=True)
        logger.info(f"Data directory created: {DATA_DIR}")
    
    def init_database(self):
        """Initialize SQLite database with all tables."""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Users table with update tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            is_bot INTEGER DEFAULT 0,
            language_code TEXT,
            current_name_hash TEXT,
            current_username_hash TEXT,
            is_deleted INTEGER DEFAULT 0,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # User name history
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_name_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        # Groups table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            type TEXT,
            username TEXT,
            invite_link TEXT,
            description TEXT,
            member_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Group admins
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            level INTEGER DEFAULT 1,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            removed_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (chat_id) REFERENCES groups (chat_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        # Muted users
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS muted_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            muted_by INTEGER,
            reason TEXT,
            muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            muted_until TIMESTAMP,
            unmuted_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (chat_id) REFERENCES groups (chat_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        # Banned users
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS banned_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            banned_by INTEGER,
            reason TEXT,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            unbanned_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (chat_id) REFERENCES groups (chat_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        # Reports
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            reporter_id INTEGER,
            reported_id INTEGER,
            reason TEXT,
            message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            handled INTEGER DEFAULT 0,
            handled_by INTEGER,
            handled_at TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES groups (chat_id),
            FOREIGN KEY (reporter_id) REFERENCES users (user_id),
            FOREIGN KEY (reported_id) REFERENCES users (user_id)
        )
        ''')
        
        # Welcome messages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS welcome_messages (
            chat_id INTEGER PRIMARY KEY,
            message TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES groups (chat_id)
        )
        ''')
        
        # Group rules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_rules (
            chat_id INTEGER PRIMARY KEY,
            rules TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES groups (chat_id)
        )
        ''')
        
        # Archived files (ONLY files - no messages)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS archived_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_message_id INTEGER,
            original_chat_id INTEGER,
            user_id INTEGER,
            file_type TEXT CHECK(file_type IN ('document', 'photo', 'video', 'audio', 'voice', 'animation')),
            file_id TEXT,
            file_unique_id TEXT,
            file_name TEXT,
            file_size INTEGER,
            caption TEXT,
            archive_message_id INTEGER,
            archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized with cute tables! 🥔")
    
    def cleanup_deleted_accounts(self):
        """Mark deleted accounts in the database."""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Mark users who have 'Deleted Account' or similar as deleted
        cursor.execute('''
        UPDATE users SET is_deleted = 1 
        WHERE first_name IN ('Deleted Account', 'Deleted', 'Account deleted') 
        OR username IS NULL AND last_seen < date('now', '-30 days')
        ''')
        
        deleted_count = cursor.rowcount
        if deleted_count > 0:
            logger.info(f"Marked {deleted_count} deleted accounts")
        
        conn.commit()
        conn.close()
    
    def save_user(self, user: User):
        """Save or update user information."""
        if user.first_name in ['Deleted Account', 'Deleted', 'Account deleted']:
            return  # Skip deleted accounts
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Calculate hashes for comparison
        name_hash = hashlib.md5(f"{user.first_name}{user.last_name}".encode()).hexdigest()
        username_hash = hashlib.md5(str(user.username).encode()).hexdigest()
        
        # Check if user exists
        cursor.execute("SELECT current_name_hash, current_username_hash FROM users WHERE user_id = ?", (user.id,))
        result = cursor.fetchone()
        
        current_time = datetime.now().isoformat()
        
        if result:
            old_name_hash, old_username_hash = result
            
            # Check if name changed
            if old_name_hash != name_hash or old_username_hash != username_hash:
                # Save to history
                cursor.execute('''
                INSERT INTO user_name_history (user_id, first_name, last_name, username)
                SELECT user_id, first_name, last_name, username FROM users WHERE user_id = ?
                ''', (user.id,))
                
                # Update current info
                cursor.execute('''
                UPDATE users SET 
                    first_name = ?, 
                    last_name = ?, 
                    username = ?,
                    current_name_hash = ?,
                    current_username_hash = ?,
                    is_deleted = 0,
                    last_seen = ?,
                    last_updated = ?
                WHERE user_id = ?
                ''', (user.first_name, user.last_name, user.username, name_hash, username_hash, current_time, current_time, user.id))
            else:
                # Just update last seen
                cursor.execute("UPDATE users SET last_seen = ?, is_deleted = 0 WHERE user_id = ?", (current_time, user.id))
        else:
            # New user
            cursor.execute('''
            INSERT INTO users 
            (user_id, first_name, last_name, username, is_bot, language_code, current_name_hash, current_username_hash, first_seen, last_seen, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user.id, user.first_name, user.last_name, user.username, int(user.is_bot), user.language_code, name_hash, username_hash, current_time, current_time, current_time))
        
        conn.commit()
        conn.close()
    
    def save_group(self, chat: Chat):
        """Save or update group information."""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        
        cursor.execute('''
        INSERT OR REPLACE INTO groups 
        (chat_id, title, type, username, invite_link, description, member_count, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            chat.id, 
            chat.title, 
            chat.type, 
            chat.username,
            getattr(chat, 'invite_link', None),
            getattr(chat, 'description', None),
            getattr(chat, 'member_count', None),
            current_time
        ))
        
        conn.commit()
        conn.close()
    
    def get_user_info(self, user_id: int) -> Dict:
        """Get user information from database."""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT first_name, last_name, username, is_deleted FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return {
                'first_name': result[0],
                'last_name': result[1],
                'username': result[2],
                'is_deleted': bool(result[3])
            }
        return {'first_name': 'Unknown', 'last_name': '', 'username': None, 'is_deleted': True}
    
    def is_admin(self, chat_id: int, user_id: int) -> bool:
        """Check if user is admin in the chat."""
        if user_id == OWNER_ID:
            return True
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT COUNT(*) FROM group_admins 
        WHERE chat_id = ? AND user_id = ? AND is_active = 1
        ''', (chat_id, user_id))
        
        result = cursor.fetchone()[0] > 0
        conn.close()
        
        return result
    
    def add_admin(self, chat_id: int, user_id: int, added_by: int = None):
        """Add user as admin."""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Deactivate any existing admin entry
        cursor.execute('''
        UPDATE group_admins SET is_active = 0, removed_at = ?
        WHERE chat_id = ? AND user_id = ? AND is_active = 1
        ''', (datetime.now().isoformat(), chat_id, user_id))
        
        # Add new admin entry
        cursor.execute('''
        INSERT INTO group_admins (chat_id, user_id, added_by, added_at, is_active)
        VALUES (?, ?, ?, ?, 1)
        ''', (chat_id, user_id, added_by, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def remove_admin(self, chat_id: int, user_id: int, removed_by: int = None):
        """Remove user from admin."""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE group_admins SET is_active = 0, removed_at = ?
        WHERE chat_id = ? AND user_id = ? AND is_active = 1
        ''', (datetime.now().isoformat(), chat_id, user_id))
        
        conn.commit()
        conn.close()
    
    def save_archived_file(self, original_message_id: int, original_chat_id: int, user_id: int, 
                          file_type: str, file_id: str, file_unique_id: str, file_name: str, 
                          file_size: int, caption: str, archive_message_id: int):
        """Save archived file information."""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO archived_files 
        (original_message_id, original_chat_id, user_id, file_type, file_id, 
         file_unique_id, file_name, file_size, caption, archive_message_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (original_message_id, original_chat_id, user_id, file_type, file_id, 
              file_unique_id, file_name, file_size, caption, archive_message_id))
        
        conn.commit()
        conn.close()

# Initialize database
db = Database()

# ===== FILE FORWARDING SYSTEM (OPTIMIZED) =====
media_groups_cache = {}
last_forward_time = 0
FORWARD_DELAY = 1.0  # Delay between forwards to avoid rate limits

async def forward_file_to_archive(message: Message, context: ContextTypes.DEFAULT_TYPE):
    """Forward files ONE BY ONE to archive with cute descriptions."""
    if not ARCHIVE_GROUP_ID:
        return
    
    global last_forward_time
    
    chat = message.chat
    user = message.from_user
    
    # Skip deleted accounts
    if user.first_name in ['Deleted Account', 'Deleted', 'Account deleted']:
        return
    
    # Save user info to database
    db.save_user(user)
    
    # Rate limiting
    current_time = time.time()
    if current_time - last_forward_time < FORWARD_DELAY:
        await asyncio.sleep(FORWARD_DELAY - (current_time - last_forward_time))
    
    # Create cute header with user info
    user_info = db.get_user_info(user.id)
    if user_info['is_deleted']:
        return  # Skip deleted accounts
    
    username_display = f"@{user_info['username']}" if user_info['username'] else "no username"
    header = f"ฅ^•ﻌ•^ฅ From: {user_info['first_name']} ({username_display})\n"
    header += f"𓃠 Chat: {chat.title if chat.title else 'Unknown'}\n"
    header += f"🥔 IDs: User:{user.id} | Chat:{chat.id}\n\n"
    
    try:
        archive_message = None
        
        # Handle ONLY files (no messages)
        if message.document:
            # For documents/files
            document = message.document
            file_caption = f"{header}{message.caption if message.caption else '📄 A document for the snuggle pile!'}"
            
            archive_message = await context.bot.send_document(
                chat_id=ARCHIVE_GROUP_ID,
                document=document.file_id,
                caption=file_caption[:1024],  # Telegram caption limit
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Save to database
            db.save_archived_file(
                original_message_id=message.message_id,
                original_chat_id=chat.id,
                user_id=user.id,
                file_type="document",
                file_id=document.file_id,
                file_unique_id=document.file_unique_id,
                file_name=document.file_name,
                file_size=document.file_size,
                caption=message.caption,
                archive_message_id=archive_message.message_id
            )
            
        elif message.photo:
            # For photos
            photo = message.photo[-1]  # Get highest resolution
            photo_caption = f"{header}{message.caption if message.caption else '📸 A picture for the snuggle pile!'}"
            
            archive_message = await context.bot.send_photo(
                chat_id=ARCHIVE_GROUP_ID,
                photo=photo.file_id,
                caption=photo_caption[:1024],
                parse_mode=ParseMode.MARKDOWN
            )
            
            db.save_archived_file(
                original_message_id=message.message_id,
                original_chat_id=chat.id,
                user_id=user.id,
                file_type="photo",
                file_id=photo.file_id,
                file_unique_id=photo.file_unique_id,
                file_name="",
                file_size=photo.file_size,
                caption=message.caption,
                archive_message_id=archive_message.message_id
            )
            
        elif message.video:
            # For videos
            video = message.video
            video_caption = f"{header}{message.caption if message.caption else '🎥 A video for the snuggle pile!'}"
            
            archive_message = await context.bot.send_video(
                chat_id=ARCHIVE_GROUP_ID,
                video=video.file_id,
                caption=video_caption[:1024],
                parse_mode=ParseMode.MARKDOWN
            )
            
            db.save_archived_file(
                original_message_id=message.message_id,
                original_chat_id=chat.id,
                user_id=user.id,
                file_type="video",
                file_id=video.file_id,
                file_unique_id=video.file_unique_id,
                file_name=video.file_name,
                file_size=video.file_size,
                caption=message.caption,
                archive_message_id=archive_message.message_id
            )
            
        elif message.audio:
            # For audio files
            audio = message.audio
            audio_caption = f"{header}{message.caption if message.caption else '🎵 A sound for the snuggle pile!'}"
            
            archive_message = await context.bot.send_audio(
                chat_id=ARCHIVE_GROUP_ID,
                audio=audio.file_id,
                caption=audio_caption[:1024],
                parse_mode=ParseMode.MARKDOWN
            )
            
            db.save_archived_file(
                original_message_id=message.message_id,
                original_chat_id=chat.id,
                user_id=user.id,
                file_type="audio",
                file_id=audio.file_id,
                file_unique_id=audio.file_unique_id,
                file_name=audio.file_name,
                file_size=audio.file_size,
                caption=message.caption,
                archive_message_id=archive_message.message_id
            )
            
        elif message.voice:
            # For voice messages
            voice = message.voice
            voice_caption = f"{header}{message.caption if message.caption else '🗣️ A voice message for the snuggle pile!'}"
            
            archive_message = await context.bot.send_voice(
                chat_id=ARCHIVE_GROUP_ID,
                voice=voice.file_id,
                caption=voice_caption[:1024],
                parse_mode=ParseMode.MARKDOWN
            )
            
            db.save_archived_file(
                original_message_id=message.message_id,
                original_chat_id=chat.id,
                user_id=user.id,
                file_type="voice",
                file_id=voice.file_id,
                file_unique_id=voice.file_unique_id,
                file_name="",
                file_size=voice.file_size,
                caption=message.caption,
                archive_message_id=archive_message.message_id
            )
            
        elif message.animation:  # GIFs
            animation = message.animation
            gif_caption = f"{header}{message.caption if message.caption else '🔄 A wiggly GIF for the snuggle pile!'}"
            
            archive_message = await context.bot.send_animation(
                chat_id=ARCHIVE_GROUP_ID,
                animation=animation.file_id,
                caption=gif_caption[:1024],
                parse_mode=ParseMode.MARKDOWN
            )
            
            db.save_archived_file(
                original_message_id=message.message_id,
                original_chat_id=chat.id,
                user_id=user.id,
                file_type="animation",
                file_id=animation.file_id,
                file_unique_id=animation.file_unique_id,
                file_name="",
                file_size=animation.file_size,
                caption=message.caption,
                archive_message_id=archive_message.message_id
            )
        
        # Update last forward time
        last_forward_time = time.time()
        
        return archive_message
        
    except Exception as e:
        logger.error(f"Error forwarding file to archive: {e}")
        return None

# ===== HELPER FUNCTIONS =====
async def is_user_admin(chat: Chat, user_id: int) -> bool:
    """Check if user is admin in the chat."""
    if user_id == OWNER_ID:
        return True
    
    try:
        member = await chat.get_member(user_id)
        return member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except:
        return False

async def is_bot_admin(chat: Chat, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if bot is admin in the chat."""
    try:
        bot_member = await chat.get_member(context.bot.id)
        return bot_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except:
        return False

def parse_time(time_str: str) -> Optional[float]:
    """Parse time string like 1h, 30m, 2d into timestamp."""
    if not time_str:
        return None
    
    multipliers = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        'w': 604800
    }
    
    unit = time_str[-1].lower()
    if unit not in multipliers:
        return None
    
    try:
        value = int(time_str[:-1])
        return time.time() + (value * multipliers[unit])
    except:
        return None

def donate_message() -> str:
    """Create cute donate message."""
    message = cute_header("Support Our Snuggle Pile")
    message += "\n\n"
    message += "𓃠 If you enjoy this cozy bot and want to support our femboy community...\n\n"
    message += "🥔 **Donate to help us grow:**\n"
    message += f"• Telegram: @kurdfemboys\n"
    message += "• Any help is appreciated, big or smol!\n\n"
    message += "💖 Your support helps keep this bot running and makes our snuggle pile even cozier!\n"
    message += "Thankies for being part of our community! ฅ^•ﻌ•^ฅ"
    
    return femboy_style(message)

# ===== CUTE COMMAND HANDLERS =====
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    
    if update.effective_chat.type == "private":
        welcome = cute_header("Welcome to Femboy Help Bot!")
        welcome += f"\n\nHaii {user.first_name}! 🥔\n\n"
        welcome += "I'm your friendly neighborhood femboy helper bot!\n\n"
        welcome += "𓃠 **What I do:**\n"
        welcome += "• Keep your snuggle pile safe and cozy\n"
        welcome += "• Archive important files (one by one!)\n"
        welcome += "• Track user name changes\n"
        welcome += "• Automatically ignore deleted accounts\n"
        welcome += "• Work in many groups without getting tired\n\n"
        welcome += "🥔 **In groups, I can help with:**\n"
        welcome += "/help - See all commands\n"
        welcome += "/rules - Show snuggle rules\n"
        welcome += "/report - Report a naughty bean\n"
        welcome += "/donate - Support our community\n\n"
        welcome += "👑 **For big potatoes (admins):**\n"
        welcome += "/welcome - Set welcome message\n"
        welcome += "/ban - Ban a bean\n"
        welcome += "/mute - Quiet a noisy bean\n"
        welcome += "/kick - Gently remove a bean\n"
        welcome += "and many more!\n\n"
        welcome += f"Add me to your group and make me a big potato (admin)!\n\n"
        welcome += f"Check out my channel: {OWNER_CHANNEL}"
        
        await update.message.reply_text(femboy_style(welcome))
    else:
        # In group, show simple welcome
        await update.message.reply_text(
            femboy_style(f"Haii {user.first_name}! Use /help to see what I can do in this snuggle pile! ฅ^•ﻌ•^ฅ")
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type == "private":
        await start_command(update, context)
        return
    
    if not db.is_admin(chat.id, user.id):
        # Regular users see basic help
        help_text = cute_header("How Can I Help?")
        help_text += "\n\n"
        help_text += "𓃠 **For all beans:**\n"
        help_text += "/report [reason] - Report a naughty bean (reply to message)\n"
        help_text += "/rules - See our snuggle rules\n"
        help_text += "/donate - Support our cozy community\n"
        help_text += "/help - Show this message\n\n"
        help_text += "🥔 **Note:** Only big potatoes (admins) can use admin commands!\n"
        help_text += "Be a gud bean and follow the rules! ฅ^•ﻌ•^ฅ"
        
        await update.message.reply_text(femboy_style(help_text))
        return
    
    # Admin help
    help_text = cute_header("Big Potato Commands")
    help_text += "\n\n"
    help_text += "👤 **Bean Management:**\n"
    help_text += "/ban [reason] - Ban a naughty bean (reply)\n"
    help_text += "/unban [id] - Unban a sorry bean\n"
    help_text += "/mute [time] [reason] - Quiet bean (1h, 30m, 2d)\n"
    help_text += "/unmute - Let bean speak again (reply)\n"
    help_text += "/kick [reason] - Gently remove bean (reply)\n"
    help_text += "/warn [reason] - Warn a naughty bean (reply)\n"
    help_text += "/unwarn - Remove warning from bean (reply/id)\n"
    help_text += "/warnings - Check bean's warnings (reply/id)\n"
    help_text += "/clearwarns - Clear all warnings (reply/id)\n\n"
    
    help_text += "📋 **Snuggle Pile Management:**\n"
    help_text += "/welcome [text] - Set welcome hug\n"
    help_text += "/setrules [text] - Set snuggle rules\n"
    help_text += "/rules - Show rules\n"
    help_text += "/pin - Pin important message (reply)\n"
    help_text += "/unpin - Unpin message\n"
    help_text += "/clean [number] - Clean up messages\n"
    help_text += "/ro - Quiet mode for beans\n"
    help_text += "/unro - Party mode for beans\n\n"
    
    help_text += "👑 **Big Potato Management:**\n"
    help_text += "/promote - Make bean a big potato (reply)\n"
    help_text += "/demote - Bean becomes smol again (owner only)\n\n"
    
    help_text += "⚙️ **Bot Stuff:**\n"
    help_text += "/reload - Refresh bot in this pile\n"
    help_text += "/stats - See pile statistics\n\n"
    
    help_text += "• Works in many groups happily!"
    
    await update.message.reply_text(femboy_style(help_text))

async def donate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /donate command."""
    await update.message.reply_text(donate_message(), parse_mode=ParseMode.MARKDOWN)

async def welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /welcome command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can set welcome hugs! ฅ^•ﻌ•^ฅ"))
        return
    
    if not context.args:
        # Get current welcome message
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT message FROM welcome_messages WHERE chat_id = ?", (chat.id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            await update.message.reply_text(f"Current welcome hug:\n\n{result[0]}")
        else:
            await update.message.reply_text("No welcome hug set. Use /welcome [message] to give beans a warm welcome!")
        return
    
    welcome_text = ' '.join(context.args)
    
    # Save to database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO welcome_messages (chat_id, message, updated_at)
    VALUES (?, ?, ?)
    ''', (chat.id, welcome_text, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(femboy_style("Yay! Welcome hug updated! New beans will feel extra cozy! ฅ^•ﻌ•^ฅ"))

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ban command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can banish beans! ฅ^•ﻌ•^ฅ"))
        return
    
    # Check if trying to ban an admin
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        if db.is_admin(chat.id, target_user.id) and user.id != OWNER_ID:
            await update.message.reply_text(femboy_style("You cannot banish other big potatoes! Only the supreme potato can do that!"))
            return
    
    if not await is_bot_admin(chat, context):
        await update.message.reply_text(femboy_style("I need to be a big potato too! Make me admin first! ฅ^•ﻌ•^ฅ"))
        return
    
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text(femboy_style("Usage: /ban [reason] OR reply to a naughty bean's message"))
        return
    
    try:
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            reason = ' '.join(context.args) if context.args else "Being a naughty bean"
        else:
            await update.message.reply_text(femboy_style("Pwease reply to the bean's message to banish them"))
            return
        
        # Skip deleted accounts
        if target_user.first_name in ['Deleted Account', 'Deleted', 'Account deleted']:
            await update.message.reply_text(femboy_style("This bean has already vanished from existence! 👻"))
            return
        
        # Save user info
        db.save_user(target_user)
        
        # Ban the user
        await chat.ban_member(target_user.id)
        
        # Save to database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO banned_users (chat_id, user_id, banned_by, reason, banned_at, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        ''', (chat.id, target_user.id, user.id, reason, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            femboy_style(f"✨ Bean {target_user.first_name} has been banished from the snuggle pile.\n"
                        f"Reason: {reason}\n"
                        f"Be a gud bean, everyone! ฅ^•ﻌ•^ฅ")
        )
        
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        await update.message.reply_text(femboy_style("Failed to banish bean. Make sure I have big potato powers!"))

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unban command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can forgive beans! ฅ^•ﻌ•^ฅ"))
        return
    
    if not context.args:
        await update.message.reply_text(femboy_style("Usage: /unban [bean_id]"))
        return
    
    try:
        target_user_id = int(context.args[0])
        await chat.unban_member(target_user_id)
        
        # Update database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE banned_users SET is_active = 0, unbanned_at = ?
        WHERE chat_id = ? AND user_id = ? AND is_active = 1
        ''', (datetime.now().isoformat(), chat.id, target_user_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(femboy_style("Bean has been forgiven and can return to the snuggle pile! ฅ^•ﻌ•^ฅ"))
    except Exception as e:
        await update.message.reply_text(femboy_style("Failed to forgive bean. Maybe they were already forgiven?"))

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mute command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can quiet noisy beans! ฅ^•ﻌ•^ฅ"))
        return
    
    # Check if trying to mute an admin
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        if db.is_admin(chat.id, target_user.id) and user.id != OWNER_ID:
            await update.message.reply_text(femboy_style("You cannot quiet other big potatoes! Only the supreme potato can do that!"))
            return
    
    if not await is_bot_admin(chat, context):
        await update.message.reply_text(femboy_style("I need to be a big potato too! Make me admin first! ฅ^•ﻌ•^ฅ"))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(femboy_style("Pwease reply to a bean's message to quiet them"))
        return
    
    target_user = update.message.reply_to_message.from_user
    time_str = context.args[0] if context.args else None
    
    # Skip deleted accounts
    if target_user.first_name in ['Deleted Account', 'Deleted', 'Account deleted']:
        await update.message.reply_text(femboy_style("This bean has already vanished from existence! 👻"))
        return
    
    mute_until = parse_time(time_str) if time_str else None
    reason = ' '.join(context.args[1:]) if time_str and len(context.args) > 1 else ' '.join(context.args) if not time_str else "Too noisy"
    
    # Apply restrictions - FIXED VERSION
    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_manage_topics=False
    )
    
    try:
        # Save user info
        db.save_user(target_user)
        
        if mute_until:
            until_date = datetime.fromtimestamp(mute_until)
            await chat.restrict_member(target_user.id, permissions, until_date=until_date)
            time_display = time_str
        else:
            await chat.restrict_member(target_user.id, permissions)
            time_display = "forever and ever"
        
        # Save to database
        mute_until_iso = datetime.fromtimestamp(mute_until).isoformat() if mute_until else None
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO muted_users (chat_id, user_id, muted_by, reason, muted_at, muted_until, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        ''', (chat.id, target_user.id, user.id, reason, datetime.now().isoformat(), mute_until_iso))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            femboy_style(f"🔇 Bean {target_user.first_name} has been quieted for {time_display}.\n"
                        f"Reason: {reason if reason else 'Being too wiggly'}\n"
                        f"Shhhh... ฅ^•ﻌ•^ฅ")
        )
    except Exception as e:
        logger.error(f"Error muting user: {e}")
        await update.message.reply_text(femboy_style("Failed to quiet bean. Make sure I have big potato powers!"))

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unmute command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can let beans speak again! ฅ^•ﻌ•^ฅ"))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(femboy_style("Pwease reply to a bean's message to let them speak again"))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    # Restore normal permissions - FIXED VERSION
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False,
        can_manage_topics=False
    )
    
    try:
        await chat.restrict_member(target_user.id, permissions)
        
        # Update database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE muted_users SET is_active = 0, unmuted_at = ?
        WHERE chat_id = ? AND user_id = ? AND is_active = 1
        ''', (datetime.now().isoformat(), chat.id, target_user.id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(femboy_style(f"🔊 Bean {target_user.first_name} can speak again! Yay! ฅ^•ﻌ•^ฅ"))
    except Exception as e:
        logger.error(f"Error unmuting user: {e}")
        await update.message.reply_text(femboy_style("Failed to let bean speak. Maybe they were already speaking?"))
        
async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /kick command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can gently remove beans! ฅ^•ﻌ•^ฅ"))
        return
    
    # Check if trying to kick an admin
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        if db.is_admin(chat.id, target_user.id) and user.id != OWNER_ID:
            await update.message.reply_text(femboy_style("You cannot remove other big potatoes! Only the supreme potato can do that!"))
            return
    
    if not await is_bot_admin(chat, context):
        await update.message.reply_text(femboy_style("I need to be a big potato too! Make me admin first! ฅ^•ﻌ•^ฅ"))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(femboy_style("Pwease reply to a bean's message to gently remove them"))
        return
    
    target_user = update.message.reply_to_message.from_user
    reason = ' '.join(context.args) if context.args else "Need some alone time"
    
    # Skip deleted accounts
    if target_user.first_name in ['Deleted Account', 'Deleted', 'Account deleted']:
        await update.message.reply_text(femboy_style("This bean has already vanished from existence! 👻"))
        return
    
    try:
        # Save user info
        db.save_user(target_user)
        
        await chat.ban_member(target_user.id)
        await chat.unban_member(target_user.id)  # Unban immediately to allow rejoining
        
        await update.message.reply_text(
            femboy_style(f"👢 Bean {target_user.first_name} has been gently removed from the snuggle pile.\n"
                        f"Reason: {reason}\n"
                        f"They can come back if they behave! ฅ^•ﻌ•^ฅ")
        )
    except Exception as e:
        logger.error(f"Error kicking user: {e}")
        await update.message.reply_text(femboy_style("Failed to remove bean. Make sure I have big potato powers!"))

async def promote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /promote command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can make other big potatoes! ฅ^•ﻌ•^ฅ"))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(femboy_style("Pwease reply to a bean's message to promote them"))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    # Skip deleted accounts
    if target_user.first_name in ['Deleted Account', 'Deleted', 'Account deleted']:
        await update.message.reply_text(femboy_style("This bean has already vanished from existence! 👻"))
        return
    
    # Check if user is already admin
    if db.is_admin(chat.id, target_user.id):
        await update.message.reply_text(femboy_style("This bean is already a big potato!"))
        return
    
    # Save user info
    db.save_user(target_user)
    
    # Add to database
    db.add_admin(chat.id, target_user.id, user.id)
    
    await update.message.reply_text(femboy_style(f"👑 Bean {target_user.first_name} has been promoted to big potato! Treat them with respect! ฅ^•ﻌ•^ฅ"))

async def demote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /demote command."""
    chat = update.effective_chat
    user = update.effective_user
    
    # Only owner can demote admins
    if user.id != OWNER_ID:
        await update.message.reply_text(femboy_style("Only the supreme potato can demote other big potatoes! ฅ^•ﻌ•^ฅ"))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(femboy_style("Pwease reply to a potato's message to demote them"))
        return
    
    target_user = update.message.reply_to_message.from_user
    
    # Check if user is admin
    if not db.is_admin(chat.id, target_user.id):
        await update.message.reply_text(femboy_style("This bean is not a big potato!"))
        return
    
    # Don't allow demoting owner
    if target_user.id == OWNER_ID:
        await update.message.reply_text(femboy_style("Cannot demote the supreme potato! That's me! 🥔"))
        return
    
    # Remove from database
    db.remove_admin(chat.id, target_user.id, user.id)
    
    await update.message.reply_text(femboy_style(f"🔻 Potato {target_user.first_name} has been demoted to regular bean. Be nice to them! ฅ^•ﻌ•^ฅ"))

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /report command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type == "private":
        await update.message.reply_text(femboy_style("This command can only be used in snuggle piles!"))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(femboy_style("Pwease reply to the message you want to report"))
        return
    
    reported_user = update.message.reply_to_message.from_user
    reason = ' '.join(context.args) if context.args else "Being a naughty bean"
    
    # Skip deleted accounts
    if reported_user.first_name in ['Deleted Account', 'Deleted', 'Account deleted']:
        await update.message.reply_text(femboy_style("This bean has already vanished from existence! 👻"))
        return
    
    # Save users info
    db.save_user(user)
    db.save_user(reported_user)
    
    # Save to database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO reports (chat_id, reporter_id, reported_id, reason, message_id, created_at, handled)
    VALUES (?, ?, ?, ?, ?, ?, 0)
    ''', (chat.id, user.id, reported_user.id, reason, update.message.reply_to_message.message_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        femboy_style(f"✅ Your report has been sent to the big potatoes!\n"
                    f"Thankies for helping keep our snuggle pile safe and cozy! ฅ^•ﻌ•^ฅ")
    )

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rules command."""
    chat = update.effective_chat
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT rules FROM group_rules WHERE chat_id = ?", (chat.id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        rules_text = cute_header("Snuggle Pile Rules")
        rules_text += "\n\n"
        rules_text += result[0]
        rules_text += "\n\nBe a gud bean and follow the rules! ฅ^•ﻌ•^ฅ"
        await update.message.reply_text(femboy_style(rules_text))
    else:
        default_rules = cute_header("Default Snuggle Rules")
        default_rules += "\n\n"
        default_rules += "1. Be kind and respectful to all beans\n"
        default_rules += "2. No harassment or bullying\n"
        default_rules += "3. No NSFW content\n"
        default_rules += "4. No spam or self-promotion\n"
        default_rules += "5. Listen to the big potatoes (admins)\n"
        default_rules += "6. Have fun and be yourself!\n\n"
        default_rules += "Big potatoes can set custom rules with /setrules"
        
        await update.message.reply_text(femboy_style(default_rules))

async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setrules command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can set snuggle rules! ฅ^•ﻌ•^ฅ"))
        return
    
    if not context.args:
        await update.message.reply_text(femboy_style("Usage: /setrules [rules text]\nExample: /setrules 1. Be nice 2. No spam"))
        return
    
    rules_text = ' '.join(context.args)
    
    # Save to database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO group_rules (chat_id, rules, updated_at)
    VALUES (?, ?, ?)
    ''', (chat.id, rules_text, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(femboy_style("Yay! Snuggle rules have been updated! ฅ^•ﻌ•^ฅ"))

async def reload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reload command."""
    global db
    
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can reload the bot! ฅ^•ﻌ•^ฅ"))
        return
    
    # Reinitialize database connection
    db = Database()
    
    await update.message.reply_text(femboy_style("🔄 Bot has been refreshed for this snuggle pile! Feeling recharged! ฅ^•ﻌ•^ฅ"))

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can see snuggle statistics! ฅ^•ﻌ•^ฅ"))
        return
    
    try:
        member_count = await chat.get_member_count()
        
        # Get stats from database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Admin count
        cursor.execute("SELECT COUNT(*) FROM group_admins WHERE chat_id = ? AND is_active = 1", (chat.id,))
        admin_count = cursor.fetchone()[0]
        
        # Muted count
        cursor.execute("SELECT COUNT(*) FROM muted_users WHERE chat_id = ? AND is_active = 1", (chat.id,))
        muted_count = cursor.fetchone()[0]
        
        # Banned count
        cursor.execute("SELECT COUNT(*) FROM banned_users WHERE chat_id = ? AND is_active = 1", (chat.id,))
        banned_count = cursor.fetchone()[0]
        
        # Reports count
        cursor.execute("SELECT COUNT(*) FROM reports WHERE chat_id = ? AND handled = 0", (chat.id,))
        reports_count = cursor.fetchone()[0]
        
        conn.close()
        
        stats_text = cute_header("Snuggle Pile Statistics")
        stats_text += "\n\n"
        stats_text += f"👥 Total Beans: {member_count}\n"
        stats_text += f"👑 Big Potatoes: {admin_count}\n"
        stats_text += f"🔇 Quiet Beans: {muted_count}\n"
        stats_text += f"🚫 Banished Beans: {banned_count}\n"
        stats_text += f"📝 Reports to check: {reports_count}\n\n"
        stats_text += "Keep the snuggle pile cozy! ฅ^•ﻌ•^ฅ"
        
        await update.message.reply_text(femboy_style(stats_text))
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await update.message.reply_text(femboy_style("Failed to get statistics. Sowwy!"))

async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /pin command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can pin important messages! ฅ^•ﻌ•^ฅ"))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(femboy_style("Pwease reply to a message to pin it"))
        return
    
    try:
        await update.message.reply_to_message.pin()
        await update.message.reply_text(femboy_style("📌 Message pinned! All beans will see this important notice! ฅ^•ﻌ•^ฅ"))
    except Exception as e:
        await update.message.reply_text(femboy_style("Failed to pin message. Make sure I have big potato powers!"))

async def unpin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unpin command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can unpin messages! ฅ^•ﻌ•^ฅ"))
        return
    
    try:
        await chat.unpin_all_messages()
        await update.message.reply_text(femboy_style("📌 All messages unpinned! The board is clean! ฅ^•ﻌ•^ฅ"))
    except Exception as e:
        await update.message.reply_text(femboy_style("Failed to unpin messages. Sowwy!"))

async def clean_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clean command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can clean up! ฅ^•ﻌ•^ฅ"))
        return
    
    if not await is_bot_admin(chat, context):
        await update.message.reply_text(femboy_style("I need to be a big potato too! Make me admin first! ฅ^•ﻌ•^ฅ"))
        return
    
    try:
        if context.args and context.args[0].isdigit():
            count = int(context.args[0])
            count = min(count, 100)  # Limit to 100 messages at once
            
            # Delete command message
            await update.message.delete()
            
            # Delete previous messages
            message_id = update.message.message_id
            deleted = 0
            for i in range(1, count + 1):
                try:
                    await context.bot.delete_message(chat.id, message_id - i)
                    deleted += 1
                    await asyncio.sleep(0.1)  # Small delay to avoid rate limits
                except:
                    pass
            
            if deleted > 0:
                # Send confirmation (it will auto-delete)
                msg = await context.bot.send_message(
                    chat.id,
                    femboy_style(f"✨ Cleaned up {deleted} messages! Snuggle pile is tidy! ฅ^•ﻌ•^ฅ")
                )
                # Auto-delete confirmation after 3 seconds
                await asyncio.sleep(3)
                await msg.delete()
        else:
            if update.message.reply_to_message:
                await update.message.reply_to_message.delete()
                await update.message.delete()
            else:
                await update.message.reply_text(femboy_style("Usage: /clean [number] OR reply to a message"))
    except Exception as e:
        logger.error(f"Error cleaning messages: {e}")

async def ro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ro (read-only) command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can quiet the snuggle pile! ฅ^•ﻌ•^ฅ"))
        return
    
    if not await is_bot_admin(chat, context):
        await update.message.reply_text(femboy_style("I need to be a big potato too! Make me admin first! ฅ^•ﻌ•^ฅ"))
        return
    
    # Set read-only permissions for all members
    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_manage_topics=False
    )
    
    try:
        await chat.set_permissions(permissions)
        await update.message.reply_text(femboy_style("🔒 Quiet time! Only big potatoes can speak now. Shhh... ฅ^•ﻌ•^ฅ"))
    except Exception as e:
        logger.error(f"Error setting RO mode: {e}")
        await update.message.reply_text(femboy_style("Failed to quiet the snuggle pile. Sowwy!"))

async def unro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unro command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can start the party again! ฅ^•ﻌ•^ฅ"))
        return
    
    if not await is_bot_admin(chat, context):
        await update.message.reply_text(femboy_style("I need to be a big potato too! Make me admin first! ฅ^•ﻌ•^ฅ"))
        return
    
    # Set normal permissions
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False,
        can_manage_topics=False
    )
    
    try:
        await chat.set_permissions(permissions)
        await update.message.reply_text(femboy_style("🔓 Party time! Beans can speak again! Yay! ฅ^•ﻌ•^ฅ"))
    except Exception as e:
        logger.error(f"Error disabling RO mode: {e}")
        await update.message.reply_text(femboy_style("Failed to start the party. Sowwy!"))
        
# ===== WARNING SYSTEM =====
async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /warn command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can warn beans! ฅ^•ﻌ•^ฅ"))
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text(femboy_style("Pwease reply to a bean's message to warn them"))
        return
    
    target_user = update.message.reply_to_message.from_user
    reason = ' '.join(context.args) if context.args else "Breaking snuggle rules"
    
    # Skip deleted accounts
    if target_user.first_name in ['Deleted Account', 'Deleted', 'Account deleted']:
        await update.message.reply_text(femboy_style("This bean has already vanished from existence! 👻"))
        return
    
    # Save user info
    db.save_user(target_user)
    
    # Get current warning count
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create warnings table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        user_id INTEGER,
        warned_by INTEGER,
        reason TEXT,
        warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (chat_id) REFERENCES groups (chat_id),
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # Count active warnings
    cursor.execute('''
    SELECT COUNT(*) FROM warnings 
    WHERE chat_id = ? AND user_id = ? AND is_active = 1
    ''', (chat.id, target_user.id))
    
    warning_count = cursor.fetchone()[0]
    
    # Add new warning
    cursor.execute('''
    INSERT INTO warnings (chat_id, user_id, warned_by, reason, warned_at, is_active)
    VALUES (?, ?, ?, ?, ?, 1)
    ''', (chat.id, target_user.id, user.id, reason, datetime.now().isoformat()))
    
    warning_count += 1
    conn.commit()
    
    # Check if user should be kicked (3 warnings)
    if warning_count >= 3:
        try:
            await chat.ban_member(target_user.id)
            await chat.unban_member(target_user.id)  # Kick instead of ban
            
            # Deactivate all warnings
            cursor.execute('''
            UPDATE warnings SET is_active = 0 
            WHERE chat_id = ? AND user_id = ? AND is_active = 1
            ''', (chat.id, target_user.id))
            
            conn.commit()
            conn.close()
            
            await update.message.reply_text(
                femboy_style(f"👢 Bean {target_user.first_name} has been kicked for reaching 3 warnings!\n"
                            f"Final warning reason: {reason}\n"
                            f"They can come back if they promise to behave! ฅ^•ﻌ•^ฅ")
            )
            return
        except Exception as e:
            logger.error(f"Error kicking user after warnings: {e}")
            conn.close()
            await update.message.reply_text(femboy_style("Failed to kick bean after 3 warnings. Sowwy!"))
            return
    
    conn.close()
    
    # Show warning count
    warnings_left = 3 - warning_count
    warning_message = f"⚠️ Bean {target_user.first_name} has been warned!\n"
    warning_message += f"Reason: {reason}\n"
    warning_message += f"Warning {warning_count}/3"
    
    if warnings_left > 0:
        warning_message += f" ({warnings_left} more {'warning' if warnings_left == 1 else 'warnings'} and they'll be kicked)"
    
    warning_message += "\nBe a gud bean! ฅ^•ﻌ•^ฅ"
    
    await update.message.reply_text(femboy_style(warning_message))

async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unwarn command."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can forgive warnings! ฅ^•ﻌ•^ฅ"))
        return
    
    if not context.args:
        await update.message.reply_text(femboy_style("Usage: /unwarn [bean_id] OR reply to a bean's message"))
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create warnings table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        user_id INTEGER,
        warned_by INTEGER,
        reason TEXT,
        warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (chat_id) REFERENCES groups (chat_id),
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    try:
        target_user_id = None
        
        if update.message.reply_to_message:
            # If replying to a message, get that user
            target_user = update.message.reply_to_message.from_user
            target_user_id = target_user.id
        else:
            # Otherwise use the provided user ID
            target_user_id = int(context.args[0])
        
        # Get user info for display
        cursor.execute("SELECT first_name FROM users WHERE user_id = ?", (target_user_id,))
        user_info = cursor.fetchone()
        
        if not user_info:
            conn.close()
            await update.message.reply_text(femboy_style("Bean not found in the potato database!"))
            return
        
        # Remove latest warning
        cursor.execute('''
        UPDATE warnings SET is_active = 0 
        WHERE id = (
            SELECT id FROM warnings 
            WHERE chat_id = ? AND user_id = ? AND is_active = 1 
            ORDER BY warned_at DESC LIMIT 1
        )
        ''', (chat.id, target_user_id))
        
        rows_affected = cursor.rowcount
        
        if rows_affected > 0:
            # Count remaining warnings
            cursor.execute('''
            SELECT COUNT(*) FROM warnings 
            WHERE chat_id = ? AND user_id = ? AND is_active = 1
            ''', (chat.id, target_user_id))
            
            remaining_warnings = cursor.fetchone()[0]
            
            conn.commit()
            conn.close()
            
            await update.message.reply_text(
                femboy_style(f"✨ One warning removed from {user_info[0]}!\n"
                            f"Remaining warnings: {remaining_warnings}/3\n"
                            f"Keep being a gud bean! ฅ^•ﻌ•^ฅ")
            )
        else:
            conn.close()
            await update.message.reply_text(femboy_style("This bean has no active warnings! They're being a gud bean! ฅ^•ﻌ•^ฅ"))
            
    except Exception as e:
        conn.close()
        logger.error(f"Error removing warning: {e}")
        await update.message.reply_text(femboy_style("Failed to remove warning. Sowwy!"))

async def warnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /warnings command."""
    chat = update.effective_chat
    user = update.effective_user
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create warnings table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        user_id INTEGER,
        warned_by INTEGER,
        reason TEXT,
        warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (chat_id) REFERENCES groups (chat_id),
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    try:
        target_user_id = None
        target_user_name = None
        
        if update.message.reply_to_message:
            # If replying to a message, get that user
            target_user = update.message.reply_to_message.from_user
            target_user_id = target_user.id
            target_user_name = target_user.first_name
        elif context.args:
            # Otherwise use the provided user ID
            target_user_id = int(context.args[0])
            cursor.execute("SELECT first_name FROM users WHERE user_id = ?", (target_user_id,))
            user_info = cursor.fetchone()
            if user_info:
                target_user_name = user_info[0]
        else:
            # No user specified, show current user's warnings
            target_user_id = user.id
            target_user_name = user.first_name
        
        if not target_user_name:
            target_user_name = f"User {target_user_id}"
        
        # Get active warnings
        cursor.execute('''
        SELECT reason, warned_at FROM warnings 
        WHERE chat_id = ? AND user_id = ? AND is_active = 1
        ORDER BY warned_at DESC
        ''', (chat.id, target_user_id))
        
        warnings = cursor.fetchall()
        warning_count = len(warnings)
        
        if warning_count == 0:
            conn.close()
            await update.message.reply_text(
                femboy_style(f"✨ Bean {target_user_name} has no warnings!\n"
                            f"They're being a perfect little bean! ฅ^•ﻌ•^ฅ")
            )
            return
        
        # Build warning list
        warnings_text = cute_header(f"Warnings for {target_user_name}")
        warnings_text += f"\n\n⚠️ Total warnings: {warning_count}/3\n\n"
        
        for i, (reason, warned_at) in enumerate(warnings, 1):
            warned_time = datetime.fromisoformat(warned_at).strftime('%Y-%m-%d %H:%M')
            warnings_text += f"{i}. {reason}\n   📅 {warned_time}\n\n"
        
        warnings_left = 3 - warning_count
        if warnings_left > 0:
            warnings_text += f"❌ {warnings_left} more {'warning' if warnings_left == 1 else 'warnings'} = kick\n"
        else:
            warnings_text += "🚨 This bean should be kicked! Use /kick\n"
        
        warnings_text += "\nBe careful little bean! ฅ^•ﻌ•^ฅ"
        
        conn.close()
        await update.message.reply_text(femboy_style(warnings_text))
        
    except Exception as e:
        conn.close()
        logger.error(f"Error getting warnings: {e}")
        await update.message.reply_text(femboy_style("Failed to get warnings. Sowwy!"))

async def clearwarns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clearwarns command (clear all warnings for a user)."""
    chat = update.effective_chat
    user = update.effective_user
    
    if not db.is_admin(chat.id, user.id):
        await update.message.reply_text(femboy_style("Only big potatoes can clear all warnings! ฅ^•ﻌ•^ฅ"))
        return
    
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text(femboy_style("Usage: /clearwarns [bean_id] OR reply to a bean's message"))
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create warnings table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        user_id INTEGER,
        warned_by INTEGER,
        reason TEXT,
        warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (chat_id) REFERENCES groups (chat_id),
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    try:
        target_user_id = None
        
        if update.message.reply_to_message:
            # If replying to a message, get that user
            target_user = update.message.reply_to_message.from_user
            target_user_id = target_user.id
            target_user_name = target_user.first_name
        else:
            # Otherwise use the provided user ID
            target_user_id = int(context.args[0])
            cursor.execute("SELECT first_name FROM users WHERE user_id = ?", (target_user_id,))
            user_info = cursor.fetchone()
            target_user_name = user_info[0] if user_info else f"User {target_user_id}"
        
        # Clear all warnings
        cursor.execute('''
        UPDATE warnings SET is_active = 0 
        WHERE chat_id = ? AND user_id = ? AND is_active = 1
        ''', (chat.id, target_user_id))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        if rows_affected > 0:
            await update.message.reply_text(
                femboy_style(f"✨ All {rows_affected} warnings cleared for {target_user_name}!\n"
                            f"Fresh start! Be a gud bean! ฅ^•ﻌ•^ฅ")
            )
        else:
            await update.message.reply_text(femboy_style("This bean has no active warnings to clear! ฅ^•ﻌ•^ฅ"))
            
    except Exception as e:
        conn.close()
        logger.error(f"Error clearing warnings: {e}")
        await update.message.reply_text(femboy_style("Failed to clear warnings. Sowwy!"))
        
# ===== OWNER COMMANDS =====
async def owner_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ownerstats command (owner only)."""
    user = update.effective_user
    
    if user.id != OWNER_ID:
        await update.message.reply_text(femboy_style("Only the supreme potato can see these stats! 🥔"))
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get total users
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_deleted = 0")
    total_users = cursor.fetchone()[0]
    
    # Get deleted accounts
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_deleted = 1")
    deleted_users = cursor.fetchone()[0]
    
    # Get total groups
    cursor.execute("SELECT COUNT(*) FROM groups")
    total_groups = cursor.fetchone()[0]
    
    # Get total archived files
    cursor.execute("SELECT COUNT(*) FROM archived_files")
    total_files = cursor.fetchone()[0]
    
    # Get database size
    db_size = os.path.getsize(DB_FILE) / (1024 * 1024)  # MB
    
    conn.close()
    
    stats = cute_header("Supreme Potato Statistics")
    stats += "\n\n"
    stats += f"👥 Active Beans: {total_users}\n"
    stats += f"👻 Vanished Beans: {deleted_users}\n"
    stats += f"🏠 Snuggle Piles: {total_groups}\n"
    stats += f"📁 Archived Files: {total_files}\n"
    stats += f"💾 Database Size: {db_size:.2f} MB\n"
    stats += f"📊 Data Directory: {DATA_DIR}\n\n"
    stats += f"🥔 Bot: {BOT_USERNAME}\n"
    stats += f"📢 Channel: {OWNER_CHANNEL}\n"
    stats += f"💖 Donate: @kurdfemboys\n\n"
    stats += "Thankies for helping our community grow! ฅ^•ﻌ•^ฅ"
    
    await update.message.reply_text(femboy_style(stats))

async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /userinfo command (owner only)."""
    user = update.effective_user
    
    if user.id != OWNER_ID:
        await update.message.reply_text(femboy_style("Only the supreme potato can see bean info! 🥔"))
        return
    
    if not context.args:
        await update.message.reply_text(femboy_style("Usage: /userinfo [bean_id]"))
        return
    
    try:
        target_user_id = int(context.args[0])
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute("SELECT first_name, last_name, username, first_seen, last_seen, is_deleted FROM users WHERE user_id = ?", (target_user_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            await update.message.reply_text(femboy_style("Bean not found in the potato database!"))
            return
        
        # Get name history
        cursor.execute('''
        SELECT first_name, last_name, username, changed_at 
        FROM user_name_history 
        WHERE user_id = ? 
        ORDER BY changed_at DESC 
        LIMIT 5
        ''', (target_user_id,))
        name_history = cursor.fetchall()
        
        conn.close()
        
        info_text = cute_header("Bean Information")
        info_text += "\n\n"
        info_text += f"🆔 Bean ID: `{target_user_id}`\n"
        info_text += f"👤 Current Name: {user_data[0]} {user_data[1] or ''}\n"
        info_text += f"📱 Username: @{user_data[2] if user_data[2] else 'no username'}\n"
        info_text += f"📅 First Seen: {user_data[3]}\n"
        info_text += f"🕒 Last Seen: {user_data[4]}\n"
        info_text += f"👻 Status: {'Vanished' if user_data[5] else 'Active'}\n\n"
        
        if name_history:
            info_text += f"📜 **Recent Name History:**\n"
            for hist in name_history:
                name = f"{hist[0]} {hist[1] or ''}".strip()
                username = f"@{hist[2]}" if hist[2] else "no username"
                info_text += f"• {name} ({username}) - {hist[3]}\n"
        
        await update.message.reply_text(femboy_style(info_text))
        
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        await update.message.reply_text(femboy_style(f"Error getting bean info: {str(e)}"))

# ===== MESSAGE HANDLERS =====
async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members joining."""
    chat = update.effective_chat
    
    for member in update.message.new_chat_members:
        # Check if the new member is the bot itself
        if member.id == context.bot.id:
            # Bot was added to a group
            db.save_group(chat)
            
            welcome_msg = cute_header("Thanks for adding me to your snuggle pile!")
            welcome_msg += "\n\n"
            welcome_msg += f"Haii! I'm {BOT_USERNAME}, your friendly femboy helper bot!\n\n"
            welcome_msg += "🥔 **Pwease make me a big potato (admin) with:**\n"
            welcome_msg += "• Delete messages power\n"
            welcome_msg += "• Ban beans power\n"
            welcome_msg += "• Invite beans power\n"
            welcome_msg += "• Pin messages power\n"
            welcome_msg += "• Manage chat power\n\n"
            welcome_msg += "Use /help to see all the cozy things I can do!\n"
            welcome_msg += f"Check out my channel: {OWNER_CHANNEL}\n\n"
            welcome_msg += "Let's make this snuggle pile extra cozy! ฅ^•ﻌ•^ฅ"
            
            await update.message.reply_text(femboy_style(welcome_msg))
            return
        
        # Skip deleted accounts
        if member.first_name in ['Deleted Account', 'Deleted', 'Account deleted']:
            continue
        
        # Save user info for new members
        db.save_user(member)
        
        # Check for welcome message
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT message FROM welcome_messages WHERE chat_id = ?", (chat.id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            welcome_message = result[0]
            # Replace placeholders
            welcome_text = welcome_message.replace("{name}", member.first_name)
            welcome_text = welcome_text.replace("{username}", f"@{member.username}" if member.username else member.first_name)
            welcome_text = welcome_text.replace("{chat}", chat.title)
            
            await update.message.reply_text(femboy_style(welcome_text))
        else:
            # Default welcome
            default_welcome = f"✨ Welcome {member.first_name} to our snuggle pile! ฅ^•ﻌ•^ฅ\n"
            default_welcome += "Be a gud bean and read /rules !"
            await update.message.reply_text(femboy_style(default_welcome))

async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle members leaving."""
    chat = update.effective_chat
    member = update.message.left_chat_member
    
    if member and member.id != context.bot.id:
        # Update last seen for leaving members
        db.save_user(member)
        
        # Cute goodbye
        goodbye = f"👋 Bean {member.first_name} has left the snuggle pile...\n"
        goodbye += "We'll miss you! Come back soon! ฅ^•ﻌ•^ฅ"
        await update.message.reply_text(femboy_style(goodbye))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all messages - optimized for file archiving only."""
    chat = update.effective_chat
    user = update.effective_user
    message = update.message
    
    if not message or not user:
        return
    
    # Skip if message is from bot itself
    if user.id == context.bot.id:
        return
    
    # Skip deleted accounts
    if user.first_name in ['Deleted Account', 'Deleted', 'Account deleted']:
        return
    
    # Save user info (tracks name/username changes)
    db.save_user(user)
    
    # Check if user is banned (from database)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT COUNT(*) FROM banned_users 
    WHERE chat_id = ? AND user_id = ? AND is_active = 1
    ''', (chat.id, user.id))
    is_banned = cursor.fetchone()[0] > 0
    
    # Check if user is muted
    cursor.execute('''
    SELECT COUNT(*) FROM muted_users 
    WHERE chat_id = ? AND user_id = ? AND is_active = 1
    ''', (chat.id, user.id))
    is_muted = cursor.fetchone()[0] > 0
    conn.close()
    
    if is_banned or is_muted:
        try:
            await message.delete()
        except:
            pass
        return
    
    # FORWARD FILES ONLY (no messages) to archive
    # Check for files only (documents, photos, videos, audio, voice, animation)
    has_file = any([
        message.document, message.photo, message.video, 
        message.audio, message.voice, message.animation
    ])
    
    if has_file and ARCHIVE_GROUP_ID and chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        try:
            # Forward files ONE BY ONE with delay to avoid rate limits
            await forward_file_to_archive(message, context)
        except Exception as e:
            logger.error(f"Error in file handling: {e}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("handle_report_"):
        user_id = int(data.split("_")[2])
        
        # Update report as handled
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE reports SET handled = 1, handled_by = ?, handled_at = ?
        WHERE reported_id = ? AND handled = 0
        ''', (query.from_user.id, datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()
        
        await query.edit_message_text(femboy_style("✅ Report handled. Thankies for keeping our snuggle pile safe! ฅ^•ﻌ•^ฅ"))
    
    elif data.startswith("dismiss_report_"):
        user_id = int(data.split("_")[2])
        
        # Update report as handled
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE reports SET handled = 1, handled_by = ?, handled_at = ?
        WHERE reported_id = ? AND handled = 0
        ''', (query.from_user.id, datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()
        
        await query.edit_message_text(femboy_style("❌ Report dismissed. Maybe it was a misunderstanding! ฅ^•ﻌ•^ฅ"))

# ===== ERROR HANDLER =====
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the bot."""
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Try to notify owner about critical errors
    try:
        if OWNER_ID:
            error_msg = f"⚠️ Potato Bot Error:\n\n{context.error}\n\n"
            if update and update.effective_message:
                error_msg += f"Chat: {update.effective_chat.title if update.effective_chat.title else update.effective_chat.id}\n"
                error_msg += f"Bean: {update.effective_user.first_name if update.effective_user else 'Unknown'}"
            
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=femboy_style(error_msg[:4000])
            )
    except:
        pass

# ===== MAIN FUNCTION =====
def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("donate", donate_command))
    application.add_handler(CommandHandler("welcome", welcome_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("unmute", unmute_command))
    application.add_handler(CommandHandler("kick", kick_command))
    application.add_handler(CommandHandler("promote", promote_command))
    application.add_handler(CommandHandler("demote", demote_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("setrules", setrules_command))
    application.add_handler(CommandHandler("reload", reload_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("pin", pin_command))
    application.add_handler(CommandHandler("unpin", unpin_command))
    application.add_handler(CommandHandler("clean", clean_command))
    application.add_handler(CommandHandler("ro", ro_command))
    application.add_handler(CommandHandler("unro", unro_command))
    application.add_handler(CommandHandler("warn", warn_command))
    application.add_handler(CommandHandler("unwarn", unwarn_command))
    application.add_handler(CommandHandler("warnings", warnings_command))
    application.add_handler(CommandHandler("clearwarns", clearwarns_command))
    
    # Owner commands
    application.add_handler(CommandHandler("ownerstats", owner_stats))
    application.add_handler(CommandHandler("userinfo", user_info_command))
    
    # Message handlers - OPTIMIZED ORDER:
    # 1. Status update handlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members), group=1)
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_member), group=1)
    
    # 2. General message handler (for file archiving only) - LOWEST PRIORITY
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message), group=2)
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start the bot with optimized settings
    print("="*60)
    print("ฅ^•ﻌ•^ฅ FEMBOY HELP BOT - EXTRA CUTE VERSION")
    print("="*60)
    print(f"🥔 Supreme Potato ID: {OWNER_ID}")
    print(f"🤖 Bot Username: {BOT_USERNAME}")
    print(f"📢 Channel: {OWNER_CHANNEL}")
    print(f"💖 Donate: @kurdfemboys")
    print(f"📁 Archive Group: {ARCHIVE_GROUP_ID}")
    print(f"💾 Database: {DB_FILE}")
    print(f"📊 Data Directory: {DATA_DIR}")
    print("="*60)
    print("✨ OPTIMIZED CUTE FEATURES:")
    print("• Archives FILES ONLY (no messages)")
    print("• Forwards ONE BY ONE (no rate limits)")
    print("• Ignores deleted accounts automatically")
    print("• Single archive group (efficient)")
    print("• SQLite database with bean history")
    print("• Cute femboy-style text")
    print("• Potato-themed everything!")
    print("• Works in many snuggle piles happily")
    print("="*60)
    print("🚀 Bot is starting... Press Ctrl+C to stop.")
    print("Let's make some snuggle piles cozy! ฅ^•ﻌ•^ฅ")
    
    # Run the bot with optimized settings
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False
    )

if __name__ == '__main__':
    main()
