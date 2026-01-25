# file: all_bot_linux.py
import csv
import json
import logging
import asyncio
import os
import re
import random
import string
import requests
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    Message, CallbackQuery, FSInputFile,
    InputMediaPhoto, PhotoSize
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import hashlib

# Increase CSV field size limit
csv.field_size_limit(1000000000)

# Bot Configuration
BOT_TOKEN = "8425134191:AAEnlnx222sHKNkGYCj5prQDgfjODQ1aOM0"  # Replace with your token
REQUIRED_CHANNEL = "@db_kurdistan"
ADMIN_USER_ID = 6290314134

# Truecaller Configuration
TRUECALLER_SEND_OTP = "https://asia-south1-truecaller-web.cloudfunctions.net/webapi/noneu/auth/truecaller/v1/send-otp"
TRUECALLER_VERIFY_OTP = "https://asia-south1-truecaller-web.cloudfunctions.net/webapi/noneu/auth/truecaller/v1/verify-otp"
TRUECALLER_API_URL = "https://asia-south1-truecaller-web.cloudfunctions.net/webapi/noneu/search/v2"
AUTH_FILE = "auth_tokens.csv"
VALID_TOKENS_FILE = "valid_tokens.csv"

# Initialize bot with memory storage
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base directories for Linux
BASE_DIR = Path("/root/iraq/downloads")
DATABASES = {
    "iraq-facebook": {
        "path": BASE_DIR / "iraq-facebook",
        "files": ["iraq-facebook.csv", "clean_1.csv", "clean_2.csv", "clean_3.csv", "clean_4.csv", "clean_5.csv", "clean_6.csv"],
        "type": "csv",
        "name": "Facebook Iraq"
    },
    "kurdistan-health": {
        "path": BASE_DIR / "kurdistan-health",
        "files": ["all.csv"],
        "type": "csv",
        "name": "Kurdistan Health"
    },
    "aman": {
        "path": BASE_DIR / "aman",
        "files": ["aman.csv"],
        "type": "csv",
        "name": "Aman Database"
    },
    "loan-korektel": {
        "path": BASE_DIR / "loan-korektel",
        "files": ["all.json", "loan-korektel.json"],
        "type": "json",
        "name": "Loan Korektel"
    },
    "qi-card": {
        "path": BASE_DIR / "qi-card",
        "files": ["Qi_Card.json", "qi-card.json"],
        "type": "json",
        "name": "Qi Card"
    },
    "zain": {
        "path": BASE_DIR / "zain",
        "files": ["zain.json", "Zain.json"],
        "type": "json",
        "name": "Zain"
    },
    "kurdistan-lawyers": {
        "path": BASE_DIR / "kurdistan-lawyers",
        "files": ["lawyers.csv", "kurdistan-lawyers.csv"],
        "type": "csv",
        "name": "Kurdistan Lawyers"
    },
}

# Language support
LANGUAGES = {
    "en_UK": "کوردی (بادینی)",
    "ku": "کوردی (سورانی)"
}

# Language texts
TEXTS = {
    "en_UK": {
        "start": "🤖 All-in-One Search Bot\n\n📌 Please choose your language:",
        "welcome": "بخێرهاتی! هیڤییە جورێ لێگەریانێ بهەلبژێرە:",
        "search_types": {
            "name": "🔍 لێگەریان ب ناڤی",
            "phone": "📞 لێگەریان ب ژمارا موبایلێ",
            "facebook_id": "🆔 لێگەریان ب ID یێ فەیسبوکی",
            "facebook_username": "👤 لێگەریان ب ناڤێ هەژمارا فەیسبوکی",
            "date": "📅 لێگەریان ب روژان",
            "age": "🎂 لێگەریان ب تەمەن",
            "national_id": "🪪 لێگەریان ب کارتا نیشتیمانی",
            "passport": "📘 لێگەریان ب پاسپۆرت",
            "vaccine_date": "💉 لێگەریان ب بەرواری ڤاکسین",
            "full_search": "🔎 لێگەریان ل هەمیان"
        },
        "instructions": {
            "name": "✅ لێگەریان ب ناڤ هاتە دەستنیشانکرن.\nهیڤییە ناڤی بنڤیسە\n💡 نمونە: 'Haider' یان 'هایدار احمد'",
            "phone": "✅ لێگەریان ب ژمارێ هاتە دەستنیشانکرن.\nهیڤییە ژمارا موبایکی ب ئنگلیزی بنڤیسە\n🔍 نمونە: 7708356605 یان +9647708356605",
            "date": "✅ لێگەریان ب روژ هاتە هەژمارتن.\nهیڤییە بەروار بنڤیسە (YYYY-MM-DD)\n💡 نمونە: '2021-11-08' یان '1990-05-15'",
            "age": "✅ لێگەریان ب تەمەن هاتە هەژمارتن.\nهیڤییە ژمارا تەمەنی بنڤیسە\n💡 نمونە: '25' یان '30'",
            "national_id": "✅ لێگەریان ب ژمارا کارتا نیشتیەمانی هاتە دەستنیشانکرن.\nهیڤییە ژمارا کارتا نیشتیمانی بنڤیسە\n💡 نمونە: '1234567'",
            "passport": "✅ لێگەریان ب پاسپۆرت هاتە دەستنیشانکرن.\nهیڤییە ژمارا پاسپۆرتی بنڤیسە",
            "vaccine_date": "✅ لێگەریان ب بەرواری ڤاکسین هاتە دەستنیشانکرن.\nهیڤییە بەروارا ڤاکسینێ بنڤیسە\n💡 نمونە: '2022-03-15'",
            "full": "✅ لێگەریان ل هەمیا هاتە دەستنیشانکرن.\nهیڤییە ئیك ژڤان بنڤیسی (ناڤ، ژمارا موبایلی، روژ، ئایدی)"
        },
        "searching": "🔍 لێگەریان ل هەمی داتابەیسا...",
        "no_results": "❌ هیچ زانیارییەک نەهاتە دیتن دناڤ داتابیسێن مەدا.",
        "found": "✅ لیگەریان ب دوماهیک هات! زانیاریێن {total} کەسا هاتنە دیتن.",
        "back": "⏪ زڤرین",
        "next_page": "پێشڤە ⏩",
        "prev_page": "⏪ پاشڤە",
        "view_details": "👁️ بینینا کەسێ",
        "select_database": "📋 داتابەیسی بهەلبژێرە:",
        "truecaller_search": "📱 لێگەریان ب Truecaller",
        "database_search": "🗄️ لێگەریان ل داتابیسا",
        "both_search": "🔍 هەردووکیان",
        "search_options": "⚙️ هەلبژارتنێن لێگەریانێ",
        "processing": "⏳ لێگەریانەکا تەیا دیتر یا د کاریدا...",
        "truecaller_result": "📱 Truecaller Result",
        "database_result": "🗄️ Database Result",
        "image_available": "📸 وێنە بەردەستە",
        "no_image": "📷 وێنە بەردەست نییە"
    },
    "ku": {
        "start": "🤖 بۆتی گەڕان لە هەموو داتابەیسەکان\n\n📌 تکایە زمانەکەت هەڵبژێرە:",
        "welcome": "بەخێربێیت! تکایە جۆری گەڕانەکەت هەڵبژێرە:",
        "search_types": {
            "name": "🔍 گەڕان بە ناو",
            "phone": "📞 گەڕان بە ژمارەی تەلەفۆن",
            "facebook_id": "🆔 گەڕان بە ژمارەی فەیسبووک",
            "facebook_username": "👤 گەڕان بە ناوی بەکارهێنەری فەیسبووک",
            "date": "📅 گەڕان بە بەروار",
            "age": "🎂 گەڕان بە تەمەن",
            "national_id": "🪪 گەڕان بە ژمارەی ناسنامە",
            "passport": "📘 گەڕان بە پاسپۆرت",
            "vaccine_date": "💉 گەڕان بە بەرواری ڤاکسین",
            "full_search": "🔎 گەڕان بە هەموو زانیاریەکان"
        },
        "instructions": {
            "name": "✅ گەڕان بە ناو هەڵبژێردرا.\nتکایە ناوەکە بنووسە\n💡 نموونە: 'Haider' یان 'علی احمد'",
            "phone": "✅ گەڕان بە ژمارەی تەلەفۆن هەڵبژێردرا.\nتکایە ژمارەی تەلەفۆنەکە بنووسە\n🔍 نموونە: 7708356605 یان +9647708356605",
            "date": "✅ گەڕان بە بەروار هەڵبژێردرا.\nتکایە بەروارەکە بنووسە (YYYY-MM-DD)\n💡 نموونە: '2021-11-08' یان '1990-05-15'",
            "age": "✅ گەڕان بە تەمەن هەڵبژێردرا.\nتکایە ژمارەی تەمەن بنووسە\n💡 نموونە: '25' یان '30'",
            "national_id": "✅ گەڕان بە ژمارەی ناسنامە هەڵبژێردرا.\nتکایە ژمارەی ناسنامە بنووسە\n💡 نموونە: '1234567'",
            "passport": "✅ گەڕان بە پاسپۆرت هەڵبژێردرا.\nتکایە ژمارەی پاسپۆرت بنووسە",
            "vaccine_date": "✅ گەڕان بە بەرواری ڤاکسین هەڵبژێردرا.\nتکایە بەرواری ڤاکسین بنووسە\n💡 نموونە: '2022-03-15'",
            "full": "✅ گەڕان بە هەموو زانیاریەکان هەڵبژێردرا.\nتکایە هەر زانیاریەک بنووسە (ناو، ژمارە، بەروار، یان ID)"
        },
        "searching": "🔍 گەڕان لە هەموو داتابەیسەکاندا...",
        "no_results": "❌ هیچ زانیاریەک نەدۆزرایەوە لە هیچ داتابیسێکدا.",
        "found": "✅ گەڕان تەواو بوو! {total} کەس دۆزرایەوە.",
        "back": "⏪ گەڕانەوە",
        "next_page": "پێشڤە ⏩",
        "prev_page": "⏪ پاشڤە",
        "view_details": "👁️ بینینی کەسێک",
        "select_database": "📋 داتابەیسێک هەڵبژێرە:",
        "truecaller_search": "📱 گەڕان بە Truecaller",
        "database_search": "🗄️ گەڕان لە داتابەیسەکان",
        "both_search": "🔍 هەردووکیان",
        "search_options": "⚙️ هەڵبژاردنەکانی گەڕان",
        "processing": "⏳ گەڕانێکی تر لە کارە...",
        "truecaller_result": "📱 ئەنجامی Truecaller",
        "database_result": "🗄️ ئەنجامی داتابەیس",
        "image_available": "📸 وێنە بەردەستە",
        "no_image": "📷 وێنە بەردەست نییە"
    }
}

# Global variables
user_states = {}
search_results = {}
user_languages = {}
active_searches = set()
registered_users = set()
truecaller_tokens = {}
valid_truecaller_tokens = []

# FSM States
class SearchStates(StatesGroup):
    waiting_for_query = State()
    waiting_for_age = State()
    waiting_for_date = State()
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_id = State()
    waiting_for_passport = State()
    waiting_for_vaccine_date = State()

# Data classes for better organization
@dataclass
class SearchResult:
    database: str
    data: Dict
    index: int = 0

@dataclass
class PaginatedResults:
    results: List[SearchResult]
    page_size: int = 20
    current_page: int = 0
    
    def get_page(self, page_num: int) -> List[SearchResult]:
        start_idx = page_num * self.page_size
        end_idx = start_idx + self.page_size
        return self.results[start_idx:end_idx]
    
    def total_pages(self) -> int:
        return (len(self.results) + self.page_size - 1) // self.page_size

# Helper functions
def normalize_phone(phone: str) -> str:
    """Normalize phone number to standard format"""
    if not phone:
        return ""
    
    phone_str = str(phone).strip()
    phone_clean = ''.join(c for c in phone_str if c.isdigit() or c == '+')
    
    if phone_clean.startswith('+964'):
        phone_clean = '0' + phone_clean[4:]
    elif phone_clean.startswith('964'):
        phone_clean = '0' + phone_clean[3:]
    
    phone_clean = ''.join(c for c in phone_clean if c.isdigit())
    
    if phone_clean and not phone_clean.startswith('0'):
        phone_clean = '0' + phone_clean
    
    return phone_clean

def hide_sensitive_info(text: str, char_count: int = 4) -> str:
    """Hide sensitive information like IDs and passwords"""
    if not text or len(text) < char_count:
        return text
    
    if len(text) <= 8:
        return f"{text[:2]}{'*' * (len(text)-4)}{text[-2:]}"
    else:
        return f"{text[:4]}{'*' * (len(text)-8)}{text[-4:]}"

def get_text(user_id: int, key: str, **kwargs) -> str:
    """Get text in user's language"""
    lang = user_languages.get(user_id, "ku")
    text = TEXTS.get(lang, TEXTS["ku"]).get(key, "")
    if kwargs:
        text = text.format(**kwargs)
    return text

def calculate_age(birth_date_str: str) -> int:
    """Calculate age from birth date string"""
    try:
        if not birth_date_str:
            return 0
        
        # Try different date formats
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']:
            try:
                birth_date = datetime.strptime(birth_date_str, fmt).date()
                today = date.today()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                return age
            except:
                continue
        return 0
    except:
        return 0

# Token management functions
def load_truecaller_tokens():
    """Load Truecaller tokens from file"""
    global truecaller_tokens, valid_truecaller_tokens
    
    truecaller_tokens = {}
    valid_truecaller_tokens = []
    
    try:
        if os.path.exists(AUTH_FILE):
            with open(AUTH_FILE, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    user_id = int(row['user_id'])
                    token = row['access_token']
                    truecaller_tokens[user_id] = token
                    valid_truecaller_tokens.append(token)
            logger.info(f"Loaded {len(truecaller_tokens)} tokens from {AUTH_FILE}")
    except Exception as e:
        logger.error(f"Error loading Truecaller tokens: {e}")

def check_token_validity(token: str) -> bool:
    """Check if a Truecaller token is still valid"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "*/*",
            "Authorization": f"Bearer {token}",
            "Referer": "https://www.truecaller.com/",
            "Origin": "https://www.truecaller.com"
        }
        
        # Test with a known Iraqi number
        test_number = "7701234567"
        params = {
            "q": test_number,
            "countryCode": "iq",
            "type": "44"
        }
        
        response = requests.get(TRUECALLER_API_URL, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            return False
        else:
            # If it's not 401, token might still work
            return response.status_code < 400
            
    except Exception as e:
        logger.error(f"Error checking token validity: {e}")
        return False

def validate_truecaller_tokens():
    """Validate all Truecaller tokens and save valid ones"""
    global valid_truecaller_tokens
    
    logger.info("Starting Truecaller token validation...")
    valid_tokens = []
    
    for user_id, token in truecaller_tokens.items():
        logger.info(f"Checking token for user {user_id}...")
        if check_token_validity(token):
            valid_tokens.append(token)
            logger.info(f"Token for user {user_id} is valid")
        else:
            logger.info(f"Token for user {user_id} is expired")
        
        # Small delay to avoid rate limiting
        time.sleep(1)
    
    # Save valid tokens to separate file
    try:
        with open(VALID_TOKENS_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['token', 'checked_at'])
            for token in valid_tokens:
                writer.writerow([token, datetime.now().isoformat()])
        
        valid_truecaller_tokens = valid_tokens
        logger.info(f"Saved {len(valid_tokens)} valid tokens to {VALID_TOKENS_FILE}")
        
    except Exception as e:
        logger.error(f"Error saving valid tokens: {e}")
    
    return valid_tokens

def get_random_valid_token() -> Optional[str]:
    """Get a random valid Truecaller token"""
    if not valid_truecaller_tokens:
        # Try to load valid tokens from file
        try:
            if os.path.exists(VALID_TOKENS_FILE):
                with open(VALID_TOKENS_FILE, 'r', newline='') as f:
                    reader = csv.DictReader(f)
                    valid_truecaller_tokens.extend([row['token'] for row in reader if 'token' in row])
        except Exception as e:
            logger.error(f"Error loading valid tokens: {e}")
    
    if valid_truecaller_tokens:
        return random.choice(valid_truecaller_tokens)
    return None

# Truecaller functions
def clean_lookup_number(text: str) -> Optional[str]:
    """Clean and validate phone number for Truecaller lookup"""
    phone_number = text.replace('+', '').replace(' ', '')
    
    # Handle Iraqi numbers
    if phone_number.startswith('964'):
        phone_number = '0' + phone_number[3:]
    
    # Validate format
    if not (phone_number.startswith('0') and 
            len(phone_number) == 11 and 
            phone_number[1:].isdigit()):
        return None
    
    return phone_number[1:]  # Remove leading '0' for API

async def search_truecaller(phone_number: str) -> Optional[Dict]:
    """Search using Truecaller API with random valid token"""
    token = get_random_valid_token()
    if not token:
        logger.error("No valid Truecaller tokens available")
        return None
    
    try:
        # Clean phone number
        clean_number = clean_lookup_number(phone_number)
        if not clean_number:
            return None
        
        # Prepare API request
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "*/*",
            "Authorization": f"Bearer {token}",
            "Referer": "https://www.truecaller.com/",
            "Origin": "https://www.truecaller.com"
        }

        params = {
            "q": clean_number,
            "countryCode": "iq",
            "type": "44"
        }

        # Make request
        response = requests.get(TRUECALLER_API_URL, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            # Token expired, remove from valid list
            if token in valid_truecaller_tokens:
                valid_truecaller_tokens.remove(token)
            logger.info(f"Token expired, removed from valid list. {len(valid_truecaller_tokens)} tokens remaining")
            return None
        else:
            logger.error(f"Truecaller API error: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error searching Truecaller: {e}")
        return None

def format_truecaller_result(data: Dict, lang: str = "ku") -> Tuple[str, Optional[str]]:
    """Format Truecaller API response"""
    if not data:
        return "❌ هیچ زانیارییەک نەهاتە دیتن", None
    
    result_lines = []
    
    # Basic Information
    name = data.get('name', 'Unknown')
    if name == "تم تعريفه كمتطفل":
        name = "ئەم ژمارەیە Spam کراوە"
    
    if lang == "ku":
        result_lines.append(f"📱 **ئەنجامی Truecaller:**")
        result_lines.append(f"• **ناو:** {name}")
        result_lines.append(f"• **ناوی کۆمپانیا:** {data.get('companyName', 'Unknown')}")
        result_lines.append(f"• **ناونیشانی کار:** {data.get('jobTitle', 'Unknown')}")
    else:
        result_lines.append(f"📱 **Truecaller Result:**")
        result_lines.append(f"• **Nav:** {name}")
        result_lines.append(f"• **Nave Companyan:** {data.get('companyName', 'Unknown')}")
        result_lines.append(f"• **Nvesena Kire:** {data.get('jobTitle', 'Unknown')}")
    
    # Phone Details
    phones = data.get('phones', [])
    if phones:
        result_lines.append("\n📞 **ژمارەکان:**")
        for phone in phones:
            result_lines.append(f"• **ژمارە:** {phone.get('e164Format', 'Unknown')}")
            result_lines.append(f"• **جۆر:** {phone.get('numberType', 'Unknown')}")
            result_lines.append(f"• **کۆمپانیا:** {phone.get('carrier', 'Unknown')}")
    
    # Addresses
    addresses = data.get('addresses', [])
    if addresses:
        result_lines.append("\n🏠 **ناونیشانەکان:**")
        for address in addresses:
            result_lines.append(f"• **شار:** {address.get('city', 'Unknown')}")
            result_lines.append(f"• **شارەوانی:** {address.get('street', 'Unknown')}")
    
    # Get image URL if available
    image_url = data.get('image')
    
    return "\n".join(result_lines), image_url

async def download_truecaller_image(image_url: str, token: str) -> Optional[bytes]:
    """Download image from Truecaller"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "image/webp,*/*",
            "Authorization": f"Bearer {token}",
            "Referer": "https://www.truecaller.com/",
            "Origin": "https://www.truecaller.com"
        }
        
        response = requests.get(image_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        if response.headers.get('Content-Type', '').startswith('image/'):
            return response.content
            
    except Exception as e:
        logger.error(f"Error downloading Truecaller image: {e}")
    
    return None

# Database search functions
async def search_iraq_facebook(search_term: str, search_type: str) -> List[Dict]:
    """Search in Iraq Facebook CSV files"""
    results = []
    db_info = DATABASES["iraq-facebook"]
    
    for file_name in db_info["files"]:
        file_path = db_info["path"] / file_name
        if not file_path.exists():
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    continue
                
                for row in reader:
                    if len(row) < 13:
                        continue
                    
                    user_id = row[0] if len(row) > 0 else ""
                    phone = row[1] if len(row) > 1 else ""
                    first_name = row[2] if len(row) > 2 else ""
                    last_name = row[3] if len(row) > 3 else ""
                    facebook_url = row[5] if len(row) > 5 else ""
                    birth_date = row[10] if len(row) > 10 else ""
                    
                    matched = False
                    
                    if search_type == "name":
                        search_lower = search_term.lower()
                        full_name = f"{first_name} {last_name}".lower()
                        if (search_lower in first_name.lower() or 
                            search_lower in last_name.lower() or
                            search_lower in full_name):
                            matched = True
                    
                    elif search_type == "phone":
                        normalized_search = normalize_phone(search_term)
                        normalized_db = normalize_phone(phone)
                        if normalized_search and normalized_db and normalized_search in normalized_db:
                            matched = True
                    
                    elif search_type == "date":
                        if search_term in birth_date:
                            matched = True
                    
                    elif search_type == "age":
                        age = calculate_age(birth_date)
                        if age and str(age) == search_term:
                            matched = True
                    
                    elif search_type == "full":
                        search_lower = search_term.lower()
                        if (search_lower in first_name.lower() or 
                            search_lower in last_name.lower() or
                            search_lower in user_id.lower() or
                            search_lower in phone.lower()):
                            matched = True
                    
                    if matched:
                        results.append({
                            "database": "iraq-facebook",
                            "user_id": user_id,
                            "phone": phone,
                            "first_name": first_name,
                            "last_name": last_name,
                            "facebook_url": facebook_url,
                            "gender": row[4] if len(row) > 4 else "",
                            "birth_date": birth_date,
                            "location": row[9] if len(row) > 9 else "",
                            "email": row[13] if len(row) > 13 else ""
                        })
                        
                        if len(results) >= 1000:
                            return results
            
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
    
    return results

async def search_kurdistan_health(search_term: str, search_type: str) -> List[Dict]:
    """Search in Kurdistan Health CSV"""
    results = []
    db_info = DATABASES["kurdistan-health"]
    file_path = db_info["path"] / "all.csv"
    
    if not file_path.exists():
        return results
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                matched = False
                
                name = row.get('name', '')
                phone = row.get('phone', '')
                birth_date = row.get('birth_date', '')
                national_id = row.get('identity_card_number', '')
                vaccine_date = row.get('vaccine_1_date', '') or row.get('vaccine_2_date', '') or row.get('vaccine_3_date', '')
                
                if search_type == "name":
                    if search_term.lower() in name.lower():
                        matched = True
                
                elif search_type == "phone":
                    normalized_search = normalize_phone(search_term)
                    normalized_db = normalize_phone(phone)
                    if normalized_search and normalized_db and normalized_search in normalized_db:
                        matched = True
                
                elif search_type == "date":
                    if search_term in birth_date:
                        matched = True
                
                elif search_type == "age":
                    age = calculate_age(birth_date)
                    if age and str(age) == search_term:
                        matched = True
                
                elif search_type == "national_id":
                    if search_term in national_id:
                        matched = True
                
                elif search_type == "vaccine_date":
                    if search_term in vaccine_date:
                        matched = True
                
                elif search_type == "full":
                    search_lower = search_term.lower()
                    if (search_lower in name.lower() or 
                        search_lower in phone.lower() or
                        search_lower in birth_date.lower() or
                        search_lower in national_id.lower()):
                        matched = True
                
                if matched:
                    results.append({
                        "database": "kurdistan-health",
                        "id": row.get('id', ''),
                        "name": name,
                        "phone": phone,
                        "birth_date": birth_date,
                        "gender": row.get('gender', ''),
                        "province": row.get('province', ''),
                        "vaccine_1_type": row.get('vaccine_1_type', ''),
                        "vaccine_1_date": row.get('vaccine_1_date', ''),
                        "identity_card_number": national_id
                    })
                    
                    if len(results) >= 1000:
                        break
        
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
    
    return results

async def search_aman(search_term: str, search_type: str) -> List[Dict]:
    """Search in Aman CSV"""
    results = []
    db_info = DATABASES["aman"]
    
    for file_name in db_info["files"]:
        file_path = db_info["path"] / file_name
        if not file_path.exists():
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    matched = False
                    
                    full_name = row.get('الاسم_الرباعي', '') or row.get('اسم_مالك_العجلة', '') or row.get('اسم_السائق_الرباعي', '')
                    phone = row.get('رقم_الهاتف', '')
                    national_id = row.get('الهوية', '') or row.get('رقم_الهوية', '')
                    birth_date = row.get('تاريخ_الميلاد', '')
                    passport = row.get('رقم_جواز_السفر', '') or row.get('جواز_السفر', '')
                    
                    if search_type == "name":
                        if search_term.lower() in full_name.lower():
                            matched = True
                    
                    elif search_type == "phone":
                        normalized_search = normalize_phone(search_term)
                        normalized_db = normalize_phone(phone)
                        if normalized_search and normalized_db and normalized_search in normalized_db:
                            matched = True
                    
                    elif search_type == "date":
                        if search_term in birth_date:
                            matched = True
                    
                    elif search_type == "age":
                        age = calculate_age(birth_date)
                        if age and str(age) == search_term:
                            matched = True
                    
                    elif search_type == "national_id":
                        if search_term in national_id:
                            matched = True
                    
                    elif search_type == "passport":
                        if search_term in passport:
                            matched = True
                    
                    elif search_type == "full":
                        search_lower = search_term.lower()
                        if (search_lower in full_name.lower() or 
                            search_lower in phone.lower() or
                            search_lower in national_id.lower()):
                            matched = True
                    
                    if matched:
                        # Count images
                        image_count = 0
                        for i in range(1, 42):
                            if row.get(f'image_{i}', '').strip():
                                image_count += 1
                        
                        results.append({
                            "database": "aman",
                            "full_name": full_name,
                            "phone": phone,
                            "identity_number": national_id,
                            "passport": passport,
                            "birth_date": birth_date,
                            "car_model": row.get('الموديل', ''),
                            "car_number": row.get('رقم_اللوحات', ''),
                            "address": row.get('العنوان', ''),
                            "province": row.get('المحافظة', ''),
                            "email": row.get('البريد_الالكتروني', ''),
                            "mother_name": row.get('اسم_الام', ''),
                            "image_count": image_count
                        })
                        
                        if len(results) >= 1000:
                            break
            
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
    
    return results

async def search_json_database(db_name: str, search_term: str, search_type: str) -> List[Dict]:
    """Search in JSON databases"""
    results = []
    db_info = DATABASES[db_name]
    
    for file_name in db_info["files"]:
        file_path = db_info["path"] / file_name
        if not file_path.exists():
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                for item in data:
                    matched = False
                    
                    if db_name == "loan-korektel":
                        msisdn = item.get("MSISDN", "")
                        if search_type == "phone" or search_type == "full":
                            normalized_search = normalize_phone(search_term)
                            normalized_db = normalize_phone(msisdn)
                            if normalized_search and normalized_db and normalized_search in normalized_db:
                                matched = True
                    
                    elif db_name == "qi-card":
                        full_name = item.get("Full_Name", "")
                        phone = item.get("Phone_Number", "") or item.get("Phone_NumberA", "") or item.get("Phone_NumberB", "")
                        national_id = item.get("Nationality_ID", "")
                        birth_date = item.get("DOB", "")
                        passport = item.get("Passport_Number", "")
                        
                        if search_type == "name":
                            if search_term.lower() in full_name.lower():
                                matched = True
                        elif search_type == "phone":
                            normalized_search = normalize_phone(search_term)
                            normalized_db = normalize_phone(phone)
                            if normalized_search and normalized_db and normalized_search in normalized_db:
                                matched = True
                        elif search_type == "date":
                            if search_term in birth_date:
                                matched = True
                        elif search_type == "age":
                            age = calculate_age(birth_date)
                            if age and str(age) == search_term:
                                matched = True
                        elif search_type == "national_id":
                            if search_term in national_id:
                                matched = True
                        elif search_type == "passport":
                            if search_term in passport:
                                matched = True
                        elif search_type == "full":
                            search_lower = search_term.lower()
                            if (search_lower in full_name.lower() or 
                                search_lower in phone.lower() or
                                search_lower in national_id.lower()):
                                matched = True
                    
                    elif db_name == "zain":
                        full_name = item.get("Full_Name", "")
                        phone = item.get("Phone_Number", "")
                        
                        if search_type == "name":
                            if search_term.lower() in full_name.lower():
                                matched = True
                        elif search_type == "phone":
                            normalized_search = normalize_phone(search_term)
                            normalized_db = normalize_phone(phone)
                            if normalized_search and normalized_db and normalized_search in normalized_db:
                                matched = True
                        elif search_type == "full":
                            search_lower = search_term.lower()
                            if search_lower in full_name.lower() or search_lower in phone.lower():
                                matched = True
                    
                    if matched:
                        results.append({
                            "database": db_name,
                            "data": item
                        })
                        
                        if len(results) >= 1000:
                            break
        
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
    
    return results

async def search_lawyers(search_term: str, search_type: str) -> List[Dict]:
    """Search in lawyers database"""
    results = []
    db_info = DATABASES["kurdistan-lawyers"]
    
    for file_name in db_info["files"]:
        file_path = db_info["path"] / file_name
        if not file_path.exists():
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    matched = False
                    
                    name = row.get('ناو', '') or row.get('پارێزەرە', '')
                    phone = row.get('ژمارەی مۆبایل', '')
                    
                    if search_type == "name":
                        if search_term.lower() in name.lower():
                            matched = True
                    elif search_type == "phone":
                        normalized_search = normalize_phone(search_term)
                        normalized_db = normalize_phone(phone)
                        if normalized_search and normalized_db and normalized_search in normalized_db:
                            matched = True
                    elif search_type == "full":
                        search_lower = search_term.lower()
                        if search_lower in name.lower() or search_lower in phone.lower():
                            matched = True
                    
                    if matched:
                        lawyer_id = row.get('ID', '')
                        image_path = None
                        images_dir = db_info["path"] / "images"
                        if images_dir.exists():
                            for ext in ['.jpg', '.jpeg', '.png', '.gif']:
                                possible_path = images_dir / f"{lawyer_id}{ext}"
                                if possible_path.exists():
                                    image_path = str(possible_path)
                                    break
                        
                        results.append({
                            "database": "kurdistan-lawyers",
                            "id": lawyer_id,
                            "name": name,
                            "lawyer_type": row.get('پارێزەرە', ''),
                            "gender": row.get('رەگەز', ''),
                            "phone": phone,
                            "address": row.get('ناونیشان', ''),
                            "email": row.get('ئیمەیڵ', ''),
                            "branch": row.get('لق', ''),
                            "join_date": row.get('بەرواری ئەندام بوون', ''),
                            "image_path": image_path
                        })
                        
                        if len(results) >= 30:
                            break
        
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
    
    return results

async def search_all_databases(search_term: str, search_type: str, user_id: int) -> Dict[str, List[Dict]]:
    """Search across all databases"""
    all_results = {}
    
    databases_to_search = [
        ("iraq-facebook", search_iraq_facebook),
        ("kurdistan-health", search_kurdistan_health),
        ("aman", search_aman),
        ("loan-korektel", lambda term, stype: search_json_database("loan-korektel", term, stype)),
        ("qi-card", lambda term, stype: search_json_database("qi-card", term, stype)),
        ("zain", lambda term, stype: search_json_database("zain", term, stype)),
        ("kurdistan-lawyers", search_lawyers),
    ]
    
    for db_name, search_func in databases_to_search:
        try:
            results = await search_func(search_term, search_type)
            if results:
                all_results[db_name] = results
        except Exception as e:
            logger.error(f"Error searching {db_name}: {e}")
    
    return all_results

# Formatting functions
def format_lawyer_result(lawyer_data: Dict, lang: str = "ku") -> Tuple[str, Optional[str]]:
    """Format lawyer result"""
    if lang == "ku":
        result_text = (
            "⚖️ **زانیاری پارێزەر:**\n\n"
            f"• **ژمارەی پارێزەر:** {lawyer_data.get('id', 'N/A')}\n"
            f"• **ناو:** {lawyer_data.get('name', 'N/A')}\n"
            f"• **جۆری پارێزەر:** {lawyer_data.get('lawyer_type', 'N/A')}\n"
            f"• **ڕەگەز:** {lawyer_data.get('gender', 'N/A')}\n"
            f"• **ژمارەی مۆبایل:** {lawyer_data.get('phone', 'N/A')}\n"
            f"• **ناونیشان:** {lawyer_data.get('address', 'N/A')}\n"
            f"• **ئیمەیڵ:** {lawyer_data.get('email', 'N/A')}\n"
            f"• **لق:** {lawyer_data.get('branch', 'N/A')}\n"
            f"• **بەرواری ئەندام بوون:** {lawyer_data.get('join_date', 'N/A')}\n"
        )
    else:
        result_text = (
            "⚖️ **زانیاریێن پارێزەری:**\n\n"
            f"• **ئایدیێ پارێزەری:** {lawyer_data.get('id', 'N/A')}\n"
            f"• **ناڤ:** {lawyer_data.get('name', 'N/A')}\n"
            f"• **جورێ پارێزەری:** {lawyer_data.get('lawyer_type', 'N/A')}\n"
            f"• **رەگەز:** {lawyer_data.get('gender', 'N/A')}\n"
            f"• **ژمارا موبایلێ:** {lawyer_data.get('phone', 'N/A')}\n"
            f"• **جهـ:** {lawyer_data.get('address', 'N/A')}\n"
            f"• **ئیمێڵ:** {lawyer_data.get('email', 'N/A')}\n"
            f"• **ڵق:** {lawyer_data.get('branch', 'N/A')}\n"
            f"• **بەروارا بەژداربینێ:** {lawyer_data.get('join_date', 'N/A')}\n"
        )
    
    return result_text, lawyer_data.get("image_path")

def format_facebook_result(facebook_data: Dict, lang: str = "ku") -> str:
    """Format Facebook data result"""
    name = f"{facebook_data.get('first_name', '')} {facebook_data.get('last_name', '')}".strip()
    
    if lang == "ku":
        result_text = (
            "📱 **زانیاری فەیسبووک:**\n\n"
            f"• **ژمارەی بەکارهێنەر:** {hide_sensitive_info(facebook_data.get('user_id', 'N/A'))}\n"
            f"• **ناو:** {name}\n"
            f"• **ژمارەی تەلەفۆن:** {facebook_data.get('phone', 'N/A')}\n"
            f"• **ڕەگەز:** {facebook_data.get('gender', 'N/A')}\n"
            f"• **بەرواری لەدایک بوون:** {facebook_data.get('birth_date', 'N/A')}\n"
            f"• **لینکی فەیسبووک:** {facebook_data.get('facebook_url', 'N/A')}\n"
            f"• **شوێن:** {facebook_data.get('location', 'N/A')}\n"
            f"• **ئیمەیڵ:** {hide_sensitive_info(facebook_data.get('email', 'N/A'))}\n"
        )
    else:
        result_text = (
            "📱 **زانیاریێن فەیسبوکی:**\n\n"
            f"• **ئایدیێ هەژمارێ:** {hide_sensitive_info(facebook_data.get('user_id', 'N/A'))}\n"
            f"• **ناڤ:** {name}\n"
            f"• **ژمارا موبایلێ:** {facebook_data.get('phone', 'N/A')}\n"
            f"• **رەگەز:** {facebook_data.get('gender', 'N/A')}\n"
            f"• **بەروارا ژدایکبوونێ:** {facebook_data.get('birth_date', 'N/A')}\n"
            f"• **لینکێ فەیسبوکی:** {facebook_data.get('facebook_url', 'N/A')}\n"
            f"• **جهـ:** {facebook_data.get('location', 'N/A')}\n"
            f"• **ئیمێڵ:** {hide_sensitive_info(facebook_data.get('email', 'N/A'))}\n"
        )
    
    return result_text

def format_health_result(health_data: Dict, lang: str = "ku") -> str:
    """Format health data result"""
    if lang == "ku":
        result_text = (
            "🏥 **زانیاری تەندروستی:**\n\n"
            f"• **ژمارە:** {health_data.get('id', 'N/A')}\n"
            f"• **ناو:** {health_data.get('name', 'N/A')}\n"
            f"• **ژمارەی تەلەفۆن:** {health_data.get('phone', 'N/A')}\n"
            f"• **بەرواری لەدایک بوون:** {health_data.get('birth_date', 'N/A')}\n"
            f"• **ڕەگەز:** {health_data.get('gender', 'N/A')}\n"
            f"• **پارێزگا:** {health_data.get('province', 'N/A')}\n"
            f"• **ژمارەی ناسنامە:** {hide_sensitive_info(health_data.get('identity_card_number', 'N/A'))}\n"
            f"• **جۆری ڤاکسینی یەکەم:** {health_data.get('vaccine_1_type', 'N/A')}\n"
            f"• **بەرواری ڤاکسینی یەکەم:** {health_data.get('vaccine_1_date', 'N/A')}\n"
        )
    else:
        result_text = (
            "🏥 **Health Information:**\n\n"
            f"• **ئایدی:** {health_data.get('id', 'N/A')}\n"
            f"• **ناڤ:** {health_data.get('name', 'N/A')}\n"
            f"• **ژمارا موبایلێ:** {health_data.get('phone', 'N/A')}\n"
            f"• **بەروارا ژدایکبوونێ:** {health_data.get('birth_date', 'N/A')}\n"
            f"• **رەگەز:** {health_data.get('gender', 'N/A')}\n"
            f"• **پارێزگەهـ:** {health_data.get('province', 'N/A')}\n"
            f"• **ژمارا ناسنامێ:** {hide_sensitive_info(health_data.get('identity_card_number', 'N/A'))}\n"
            f"• **خورێ ئێکەم ڤاکسێنێ:** {health_data.get('vaccine_1_type', 'N/A')}\n"
            f"• **بەروارا ئێکەم ڤاکسینێ:** {health_data.get('vaccine_1_date', 'N/A')}\n"
        )
    
    return result_text

def format_aman_result(aman_data: Dict, lang: str = "ku") -> str:
    """Format Aman data result"""
    if lang == "ku":
        result_text = (
            "🚗 **زانیاری ئامان:**\n\n"
            f"• **ناوی تەواو:** {aman_data.get('full_name', 'N/A')}\n"
            f"• **ژمارەی تەلەفۆن:** {aman_data.get('phone', 'N/A')}\n"
            f"• **ناوی دایک:** {aman_data.get('mother_name', 'N/A')}\n"
            f"• **ژمارەی ناسنامە:** {hide_sensitive_info(aman_data.get('identity_number', 'N/A'))}\n"
            f"• **ژمارەی پاسپۆرت:** {aman_data.get('passport', 'N/A')}\n"
            f"• **بەرواری لەدایک بوون:** {aman_data.get('birth_date', 'N/A')}\n"
            f"• **مۆدێلی ئوتومبێل:** {aman_data.get('car_model', 'N/A')}\n"
            f"• **ژمارەی ئوتومبێل:** {aman_data.get('car_number', 'N/A')}\n"
            f"• **ناونیشان:** {aman_data.get('address', 'N/A')}\n"
            f"• **پارێزگا:** {aman_data.get('province', 'N/A')}\n"
            f"• **ئیمەیڵ:** {aman_data.get('email', 'N/A')}\n"
        )
    else:
        result_text = (
            "🚗 **زانیاریێن ئەمان:**\n\n"
            f"• **ناڤ:** {aman_data.get('full_name', 'N/A')}\n"
            f"• **ژمارا موبایلێ:** {aman_data.get('phone', 'N/A')}\n"
            f"• **ناڤێ دەیکێ:** {aman_data.get('mother_name', 'N/A')}\n"
            f"• **ژمارا ناسنامی:** {hide_sensitive_info(aman_data.get('identity_number', 'N/A'))}\n"
            f"• **ژمارا پاسپۆرتی:** {aman_data.get('passport', 'N/A')}\n"
            f"• **بەروارا ژدایکبینێ:** {aman_data.get('birth_date', 'N/A')}\n"
            f"• **جورێ ترومبێلێ:** {aman_data.get('car_model', 'N/A')}\n"
            f"• **ژمارا ترومبێلێ:** {aman_data.get('car_number', 'N/A')}\n"
            f"• **جهـ:** {aman_data.get('address', 'N/A')}\n"
            f"• **پارێزگەهـ:** {aman_data.get('province', 'N/A')}\n"
            f"• **ئیمێڵ:** {aman_data.get('email', 'N/A')}\n"
        )
    
    # Add image count if available
    image_count = aman_data.get('image_count', 0)
    if image_count > 0:
        if lang == "ku":
            result_text += f"\n📸 **وێنەکان:** {image_count} وێنە بەردەستە"
        else:
            result_text += f"\n📸 **وێنە:** {image_count} وێنەیێن ڤی کەسی هەنە"
    
    return result_text

def format_json_result(json_data: Dict, db_name: str, lang: str = "ku") -> str:
    """Format JSON database results"""
    data = json_data.get("data", {})
    
    if db_name == "loan-korektel":
        if lang == "ku":
            result_text = (
                "💰 **زانیاری وام (کۆرەکتێل):**\n\n"
                f"• **ژمارەی تەلەفۆن:** {data.get('MSISDN', 'N/A')}\n"
                f"• **کۆدی خزمەتگوزاری:** {data.get('SC', 'N/A')}\n"
                f"• **ناوی ئاژانسی:** {data.get('AgentName', 'N/A')}\n"
                f"• **بەروار:** {data.get('Date', 'N/A')}\n"
                f"• **کات:** {data.get('Time', 'N/A')}\n"
            )
        else:
            result_text = (
                "💰 **زانیاریێن بکارهیةەرێن سەنتەرێ کورەکی:**\n\n"
                f"• **ژمارا موبایلێ:** {data.get('MSISDN', 'N/A')}\n"
                f"• **کودێ خزمەتگوزاریێ:** {data.get('SC', 'N/A')}\n"
                f"• **ناڤێ ئاژانسی:** {data.get('AgentName', 'N/A')}\n"
                f"• **بەروار:** {data.get('Date', 'N/A')}\n"
                f"• **دەم:** {data.get('Time', 'N/A')}\n"
            )
    elif db_name == "qi-card":
        if lang == "ku":
            result_text = (
                "💳 **زانیاری کارتی قی:**\n\n"
                f"• **ناوی تەواو:** {data.get('Full_Name', 'N/A')}\n"
                f"• **ژمارەی تەلەفۆن:** {data.get('Phone_Number', 'N/A')}\n"
                f"• **بەرواری لەدایک بوون:** {data.get('DOB', 'N/A')}\n"
                f"• **شوێنی لەدایک بوون:** {data.get('Place_of_Birth', 'N/A')}\n"
                f"• **ناونیشان:** {data.get('Address', 'N/A')}\n"
                f"• **ژمارەی ناسنامە:** {hide_sensitive_info(data.get('Nationality_ID', 'N/A'))}\n"
                f"• **ناوی دایک:** {data.get('Mothers_Name', 'N/A')}\n"
            )
        else:
            result_text = (
                "💳 **زانیاریێن کارتا کی:**\n\n"
                f"• **ناڤ:** {data.get('Full_Name', 'N/A')}\n"
                f"• **ژمارا موبایلێ:** {data.get('Phone_Number', 'N/A')}\n"
                f"• **بەروارا ژدایکبینێ:** {data.get('DOB', 'N/A')}\n"
                f"• **جهێ ژدایکبینێ:** {data.get('Place_of_Birth', 'N/A')}\n"
                f"• **جهـ:** {data.get('Address', 'N/A')}\n"
                f"• **ژمارا کارتا نیشتیمانی:** {hide_sensitive_info(data.get('Nationality_ID', 'N/A'))}\n"
                f"• **ناڤێ دەیکێ:** {data.get('Mothers_Name', 'N/A')}\n"
            )
    elif db_name == "zain":
        if lang == "ku":
            result_text = (
                "📶 **زانیاری زاین:**\n\n"
                f"• **ناوی تەواو:** {data.get('Full_Name', 'N/A')}\n"
                f"• **ژمارەی تەلەفۆن:** {data.get('Phone_Number', 'N/A')}\n"
                f"• **پارێزگا:** {data.get('Gov', 'N/A')}\n"
            )
        else:
            result_text = (
                "📶 **زانیاریێن زێن:**\n\n"
                f"• **ناڤ:** {data.get('Full_Name', 'N/A')}\n"
                f"• **ژمارا موبایلێ:** {data.get('Phone_Number', 'N/A')}\n"
                f"• **جهـ:** {data.get('Gov', 'N/A')}\n"
            )
    
    return result_text

# Channel membership check
async def check_user_membership(user_id: int) -> bool:
    """Check if user is member of required channel"""
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        logger.error(f"Error checking membership: {e}")
    return False

async def create_channel_join_button() -> InlineKeyboardMarkup:
    """Create join channel button"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="📢 کلیک بکە و بەشداربە", 
                url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}"
            )
        ]]
    )
    return keyboard

# Bot handlers
@router.message(Command("start"))
async def start_command(message: Message):
    """Handle /start command"""
    user_id = message.from_user.id
    
    # Check channel membership
    if not await check_user_membership(user_id):
        keyboard = await create_channel_join_button()
        await message.reply_text(
            "🔴 دڤێت تو بەژداری کەناڵی ببی تاکو بشێی بوتی بکاربینی.",
            reply_markup=keyboard
        )
        return
    
    # Language selection keyboard
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="کوردی (بادینی)", callback_data="lang_en_UK"),
                InlineKeyboardButton(text="کوردی (سورانی)", callback_data="lang_ku")
            ]
        ]
    )
    
    await message.reply_text(
        "🤖 All-in-One Search Bot\n\n📌 Please choose your language:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("lang_"))
async def language_callback(callback: CallbackQuery):
    """Handle language selection"""
    user_id = callback.from_user.id
    lang = callback.data.replace("lang_", "")
    
    # Set user language
    user_languages[user_id] = lang
    
    # Show search type selection
    texts = TEXTS.get(lang, TEXTS["ku"])
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts["search_types"]["name"], callback_data="search_name"),
                InlineKeyboardButton(text=texts["search_types"]["phone"], callback_data="search_phone")
            ],
            [
                InlineKeyboardButton(text=texts["search_types"]["date"], callback_data="search_date"),
                InlineKeyboardButton(text=texts["search_types"]["age"], callback_data="search_age")
            ],
            [
                InlineKeyboardButton(text=texts["search_types"]["national_id"], callback_data="search_national_id"),
                InlineKeyboardButton(text=texts["search_types"]["passport"], callback_data="search_passport")
            ],
            [
                InlineKeyboardButton(text=texts["search_types"]["vaccine_date"], callback_data="search_vaccine_date"),
                InlineKeyboardButton(text=texts["search_types"]["full_search"], callback_data="search_full")
            ],
            [
                InlineKeyboardButton(text=texts["search_options"], callback_data="search_options")
            ]
        ]
    )
    
    await callback.message.edit_text(texts["welcome"], reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "search_options")
async def search_options_callback(callback: CallbackQuery):
    """Show search options (Truecaller, Database, Both)"""
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ku")
    texts = TEXTS.get(lang, TEXTS["ku"])
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts["truecaller_search"], callback_data="search_truecaller_only"),
                InlineKeyboardButton(text=texts["database_search"], callback_data="search_database_only")
            ],
            [
                InlineKeyboardButton(text=texts["both_search"], callback_data="search_both"),
                InlineKeyboardButton(text=texts["back"], callback_data="back_to_search_types")
            ]
        ]
    )
    
    await callback.message.edit_text(texts["search_options"], reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "back_to_search_types")
async def back_to_search_types_callback(callback: CallbackQuery):
    """Return to search type selection"""
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ku")
    texts = TEXTS.get(lang, TEXTS["ku"])
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=texts["search_types"]["name"], callback_data="search_name"),
                InlineKeyboardButton(text=texts["search_types"]["phone"], callback_data="search_phone")
            ],
            [
                InlineKeyboardButton(text=texts["search_types"]["date"], callback_data="search_date"),
                InlineKeyboardButton(text=texts["search_types"]["age"], callback_data="search_age")
            ],
            [
                InlineKeyboardButton(text=texts["search_types"]["national_id"], callback_data="search_national_id"),
                InlineKeyboardButton(text=texts["search_types"]["passport"], callback_data="search_passport")
            ],
            [
                InlineKeyboardButton(text=texts["search_types"]["vaccine_date"], callback_data="search_vaccine_date"),
                InlineKeyboardButton(text=texts["search_types"]["full_search"], callback_data="search_full")
            ],
            [
                InlineKeyboardButton(text=texts["search_options"], callback_data="search_options")
            ]
        ]
    )
    
    await callback.message.edit_text(texts["welcome"], reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("search_"))
async def search_type_callback(callback: CallbackQuery, state: FSMContext):
    """Handle search type selection"""
    user_id = callback.from_user.id
    search_data = callback.data
    
    if search_data == "search_truecaller_only":
        await state.set_state(SearchStates.waiting_for_phone)
        await state.update_data(search_type="phone", search_mode="truecaller_only")
        instructions = "📱 **Truecaller Search**\n\nهیڤییە ژمارا موبایلێ بنڤیسە:\nنموونە: 07501231234 یان +9647501231234"
        
    elif search_data == "search_database_only":
        await state.set_state(SearchStates.waiting_for_query)
        await state.update_data(search_type="full", search_mode="database_only")
        instructions = "🗄️ **Database Search**\n\nهیڤییە هەر زانیاریەک بنڤیسە (ناڤ، ژمارە، بەروار، ئایدی):"
        
    elif search_data == "search_both":
        await state.set_state(SearchStates.waiting_for_phone)
        await state.update_data(search_type="phone", search_mode="both")
        instructions = "🔍 **Truecaller & Database Search**\n\nهیڤییە ژمارا موبایلێ بنڤیسە:\nنموونە: 07501231234 یان +9647501231234"
        
    else:
        search_type = search_data.replace("search_", "")
        
        # Set appropriate state based on search type
        if search_type == "name":
            await state.set_state(SearchStates.waiting_for_name)
        elif search_type == "phone":
            await state.set_state(SearchStates.waiting_for_phone)
        elif search_type == "date":
            await state.set_state(SearchStates.waiting_for_date)
        elif search_type == "age":
            await state.set_state(SearchStates.waiting_for_age)
        elif search_type == "national_id":
            await state.set_state(SearchStates.waiting_for_id)
        elif search_type == "passport":
            await state.set_state(SearchStates.waiting_for_passport)
        elif search_type == "vaccine_date":
            await state.set_state(SearchStates.waiting_for_date)
        elif search_type == "full":
            await state.set_state(SearchStates.waiting_for_query)
        
        await state.update_data(search_type=search_type, search_mode="database_only")
        
        # Get instructions
        instructions_key = search_type if search_type != "full" else "full"
        instructions = get_text(user_id, "instructions")[instructions_key]
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="back_to_search_types")
        ]]
    )
    
    await callback.message.edit_text(instructions, reply_markup=keyboard)
    await callback.answer()

@router.message(SearchStates.waiting_for_name)
@router.message(SearchStates.waiting_for_phone)
@router.message(SearchStates.waiting_for_date)
@router.message(SearchStates.waiting_for_age)
@router.message(SearchStates.waiting_for_id)
@router.message(SearchStates.waiting_for_passport)
@router.message(SearchStates.waiting_for_query)
async def handle_search_query(message: Message, state: FSMContext):
    """Handle search queries"""
    user_id = message.from_user.id
    search_term = message.text.strip()
    
    # Get search data from state
    data = await state.get_data()
    search_type = data.get("search_type", "full")
    search_mode = data.get("search_mode", "database_only")
    
    # Clear state
    await state.clear()
    
    # Check channel membership
    if not await check_user_membership(user_id):
        keyboard = await create_channel_join_button()
        await message.reply_text(
            "🔴 دڤێت تو بەژداری کەناڵی ببی تاکو بشێی بوتی بکاربینی.",
            reply_markup=keyboard
        )
        return
    
    # Check if user has active search
    if user_id in active_searches:
        await message.reply_text(get_text(user_id, "processing"))
        return
    
    # Mark user as searching
    active_searches.add(user_id)
    
    # Send searching message
    search_msg = await message.reply_text(get_text(user_id, "searching"))
    
    try:
        all_results = {}
        truecaller_result = None
        truecaller_image = None
        
        # Perform Truecaller search if needed
        if search_mode in ["truecaller_only", "both"] and search_type == "phone":
            truecaller_result = await search_truecaller(search_term)
            if truecaller_result:
                truecaller_text, image_url = format_truecaller_result(truecaller_result, user_languages.get(user_id, "ku"))
                if image_url:
                    token = get_random_valid_token()
                    if token:
                        truecaller_image = await download_truecaller_image(image_url, token)
        
        # Perform database search if needed
        if search_mode in ["database_only", "both"]:
            all_results = await search_all_databases(search_term, search_type, user_id)
        
        # Clear active search
        if user_id in active_searches:
            active_searches.remove(user_id)
        
        # Count total results
        total_results = sum(len(results) for results in all_results.values())
        
        # Store results for pagination
        search_results[user_id] = {
            "all_results": all_results,
            "truecaller_result": truecaller_result,
            "truecaller_image": truecaller_image,
            "search_term": search_term,
            "search_type": search_type,
            "search_mode": search_mode,
            "current_page": 0
        }
        
        # Prepare response
        response_parts = []
        
        # Add Truecaller result if available
        if truecaller_result:
            truecaller_text, _ = format_truecaller_result(truecaller_result, user_languages.get(user_id, "ku"))
            response_parts.append(f"📱 **Truecaller Result:**\n{truecaller_text}")
        
        # Add database results summary
        if total_results > 0:
            summary = get_text(user_id, "found", total=total_results)
            
            # Add database breakdown
            for db_name, results in all_results.items():
                if results:
                    summary += f"\n• {DATABASES[db_name]['name']}: {len(results)}"
            
            response_parts.append(summary)
        elif search_mode == "database_only" or (search_mode == "both" and not truecaller_result):
            await search_msg.edit_text(get_text(user_id, "no_results"))
            return
        
        # Send image if available
        if truecaller_image:
            try:
                await message.answer_photo(
                    photo=truecaller_image,
                    caption="\n\n".join(response_parts)[:1024],
                    parse_mode=ParseMode.MARKDOWN
                )
                await search_msg.delete()
            except Exception as e:
                logger.error(f"Error sending photo: {e}")
                await search_msg.edit_text("\n\n".join(response_parts), parse_mode=ParseMode.MARKDOWN)
        else:
            await search_msg.edit_text("\n\n".join(response_parts), parse_mode=ParseMode.MARKDOWN)
        
        # Show database selection if there are results
        if total_results > 0:
            await show_database_selection(user_id, search_msg.chat.id)
            
    except Exception as e:
        logger.error(f"Error during search: {e}")
        if user_id in active_searches:
            active_searches.remove(user_id)
        await search_msg.edit_text(f"❌ خەلەتیەک: {str(e)}")

async def show_database_selection(user_id: int, chat_id: int):
    """Show database selection keyboard"""
    user_data = search_results.get(user_id, {})
    all_results = user_data.get("all_results", {})
    
    if not all_results:
        return
    
    keyboard_buttons = []
    for db_name, results in all_results.items():
        if results:
            db_display_name = DATABASES[db_name]['name']
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{db_display_name} ({len(results)})", 
                    callback_data=f"view_db_{db_name}_0"
                )
            ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="back_to_search_types")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await bot.send_message(
        chat_id=chat_id,
        text=get_text(user_id, "select_database"),
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("view_db_"))
async def view_database_results(callback: CallbackQuery):
    """View results from a specific database"""
    user_id = callback.from_user.id
    
    # Parse callback data
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Error in data")
        return
    
    db_name = parts[2]
    page = int(parts[3])
    
    # Get user's search results
    user_data = search_results.get(user_id, {})
    all_db_results = user_data.get("all_results", {})
    results = all_db_results.get(db_name, [])
    
    if not results:
        await callback.answer("❌ No results")
        return
    
    # Update current page
    search_results[user_id]["current_page"] = page
    
    # Calculate pagination
    items_per_page = 20
    total_pages = (len(results) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(results))
    
    # Create result list
    lang = user_languages.get(user_id, "ku")
    result_text = f"📋 **{DATABASES[db_name]['name']}** (Page {page + 1}/{total_pages}):\n\n"
    
    for i, result in enumerate(results[start_idx:end_idx], start=1):
        item_num = start_idx + i
        
        # Extract basic info based on database type
        if db_name == "iraq-facebook":
            name = f"{result.get('first_name', '')} {result.get('last_name', '')}".strip()
            phone = result.get('phone', 'N/A')
            result_text += f"{item_num}. {name} - 📞{phone}\n"
        
        elif db_name == "kurdistan-health":
            name = result.get('name', 'N/A')
            birth_date = result.get('birth_date', 'N/A')
            result_text += f"{item_num}. {name} - 📅{birth_date[:10] if birth_date else 'N/A'}\n"
        
        elif db_name == "aman":
            name = result.get('full_name', 'N/A')
            phone = result.get('phone', 'N/A')
            result_text += f"{item_num}. {name} - 📞{phone}\n"
        
        elif db_name in ["loan-korektel", "qi-card", "zain"]:
            data = result.get("data", {})
            if db_name == "loan-korektel":
                msisdn = data.get('MSISDN', 'N/A')
                result_text += f"{item_num}. 📞{msisdn}\n"
            elif db_name == "qi-card":
                name = data.get('Full_Name', 'N/A')
                result_text += f"{item_num}. {name[:30]}\n"
            elif db_name == "zain":
                name = data.get('Full_Name', 'N/A')
                result_text += f"{item_num}. {name[:30]}\n"
        
        elif db_name == "kurdistan-lawyers":
            name = result.get('name', 'N/A')
            phone = result.get('phone', 'N/A')
            result_text += f"{item_num}. {name} - 📞{phone}\n"
    
    # Create pagination keyboard
    keyboard_buttons = []
    
    # Add result selection buttons
    for i, result in enumerate(results[start_idx:end_idx], start=1):
        item_idx = start_idx + i - 1
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{get_text(user_id, 'view_details')} {item_idx + 1}", 
                callback_data=f"view_item_{db_name}_{item_idx}"
            )
        ])
    
    # Add pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text=get_text(user_id, "prev_page"), callback_data=f"view_db_{db_name}_{page - 1}")
        )
    
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )
    
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text=get_text(user_id, "next_page"), callback_data=f"view_db_{db_name}_{page + 1}")
        )
    
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    
    # Add back button
    keyboard_buttons.append([
        InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="back_to_results")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    try:
        await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error editing message: {e}")
    
    await callback.answer()

@router.callback_query(F.data == "back_to_results")
async def back_to_results_callback(callback: CallbackQuery):
    """Go back to database selection"""
    user_id = callback.from_user.id
    await show_database_selection(user_id, callback.message.chat.id)
    await callback.answer()

@router.callback_query(F.data == "noop")
async def no_operation(callback: CallbackQuery):
    """Handle no-operation callback"""
    await callback.answer()

@router.callback_query(F.data.startswith("view_item_"))
async def view_item_details(callback: CallbackQuery):
    """View detailed information about a specific item"""
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ku")
    
    # Parse callback data
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Error in data")
        return
    
    db_name = parts[2]
    index = int(parts[3])
    
    # Get user's search results
    user_data = search_results.get(user_id, {})
    all_db_results = user_data.get("all_results", {})
    results = all_db_results.get(db_name, [])
    
    if index >= len(results):
        await callback.answer("❌ ئەڤ پارچە نەهاتە دیتن")
        return
    
    item = results[index]
    
    # Format result based on database type
    if db_name == "iraq-facebook":
        result_text = format_facebook_result(item, lang)
        image_path = None
    
    elif db_name == "kurdistan-health":
        result_text = format_health_result(item, lang)
        image_path = None
    
    elif db_name == "aman":
        result_text = format_aman_result(item, lang)
        image_path = None
    
    elif db_name in ["loan-korektel", "qi-card", "zain"]:
        result_text = format_json_result(item, db_name, lang)
        image_path = None
    
    elif db_name == "kurdistan-lawyers":
        result_text, image_path = format_lawyer_result(item, lang)
    
    else:
        result_text = "❌ فورماتەک نەزانراو"
        image_path = None
    
    # Add disclaimer
    disclaimer = "\n\n══════\n"
    disclaimer += "🔴 هەر کارێک بێ ئەخلاق بکەیت ئەم نەبەرپرسیارین.\n"
    disclaimer += "📢 کەناڵ: @db_kurdistan\n"
    disclaimer += "══════"
    
    result_text += disclaimer
    
    # Send message with image if available
    if image_path and os.path.exists(image_path):
        try:
            with open(image_path, 'rb') as photo:
                await callback.message.answer_photo(
                    photo=photo,
                    caption=result_text[:1024],
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
            await callback.message.reply_text(essage.answer(result_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await callback.message.reply_text(result_text, parse_mode=ParseMode.MARKDOWN)
    
    await callback.answer()

# Command to validate Truecaller tokens
@router.message(Command("validate_tokens"))
async def validate_tokens_command(message: Message):
    """Validate Truecaller tokens (admin only)"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await message.reply_text("❌ تەنیا ئەدمین دەتوانێت ئەم فرمانە بەکاربهێنێت.")
        return
    
    await message.reply_text("🔄 دەستپێکردنی پشکنینی تۆکنەکانی Truecaller...")
    
    valid_tokens = validate_truecaller_tokens()
    
    await message.reply_text(
        f"✅ پشکنین تەواو بوو!\n"
        f"تۆکنە باشەکان: {len(valid_tokens)}\n"
        f"کۆی گشتی تۆکنەکان: {len(truecaller_tokens)}"
    )

# Command to check bot status
@router.message(Command("status"))
async def status_command(message: Message):
    """Check bot status"""
    user_id = message.from_user.id
    
    status_text = (
        f"🤖 **بۆتێ گەڕان لە هەموو داتابەیسەکان**\n\n"
        f"• **کەناڵ:** {REQUIRED_CHANNEL}\n"
        f"• **زمان:** {user_languages.get(user_id, 'ku')}\n"
        f"• **تۆکنەکانی Truecaller:** {len(truecaller_tokens)}\n"
        f"• **تۆکنە باشەکان:** {len(valid_truecaller_tokens)}\n"
        f"• **گەڕانە چالاکەکان:** {len(active_searches)}\n"
        f"• **بەکارهێنەرە تۆمارکراوەکان:** {len(registered_users)}\n\n"
        f"📢 @db_kurdistan"
    )
    
    await message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

# Command to reload tokens
@router.message(Command("reload_tokens"))
async def reload_tokens_command(message: Message):
    """Reload Truecaller tokens"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_USER_ID:
        await message.reply_text("❌ تەنیا ئەدمین دەتوانێت ئەم فرمانە بەکاربهێنێت.")
        return
    
    load_truecaller_tokens()
    await message.reply_text(f"✅ تۆکنەکان بارکرانەوە!\nکۆی گشتی: {len(truecaller_tokens)}")

async def main():
    """Main function to start the bot"""
    # Load Truecaller tokens
    load_truecaller_tokens()
    
    # Validate tokens on startup
    logger.info(f"Loaded {len(truecaller_tokens)} Truecaller tokens")
    
    if truecaller_tokens:
        logger.info("Validating Truecaller tokens...")
        validate_truecaller_tokens()
    
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
