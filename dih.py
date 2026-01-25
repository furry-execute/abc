import csv
import json
import logging
import asyncio
import os
import re
import random
import pyodbc
import requests
from datetime import datetime, date, timedelta
from pathlib import Path
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    Message, CallbackQuery, FSInputFile, InputMediaPhoto
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
import time
import pytz
from typing import Dict, List, Optional

# Increase CSV field size limit
csv.field_size_limit(1000000000)

# Bot Configuration
BOT_TOKEN = "8425134191:AAEnlnx222sHKNkGYCj5prQDgfjODQ1aOM0"
REQUIRED_CHANNEL = "@db_kurdistan"
ADMIN_USER_ID = 6290314134

# Truecaller Configuration
TRUECALLER_SEND_OTP = "https://asia-south1-truecaller-web.cloudfunctions.net/webapi/noneu/auth/truecaller/v1/send-otp"
TRUECALLER_VERIFY_OTP = "https://asia-south1-truecaller-web.cloudfunctions.net/webapi/noneu/auth/truecaller/v1/verify-otp"
TRUECALLER_API_URL = "https://asia-south1-truecaller-web.cloudfunctions.net/webapi/noneu/search/v2"
AUTH_FILE = "auth_tokens.csv"

# Initialize bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path("C:/Users/hp/Desktop/all-bot-in-one")
DATABASES = {
    "iraq-facebook": {
        "path": BASE_DIR / "iraq-facebook",
        "files": ["clean_1.csv", "clean_2.csv", "clean_3.csv", "clean_4.csv", "clean_5.csv", "clean_6.csv"],
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
        "files": ["all.json"],
        "type": "json",
        "name": "Loan Korektel"
    },
    "qi-card": {
        "path": BASE_DIR / "qi-card",
        "files": ["Qi_Card.json"],
        "type": "json",
        "name": "Qi Card"
    },
    "zain": {
        "path": BASE_DIR / "zain",
        "files": ["Zain.json"],
        "type": "json",
        "name": "Zain"
    },
    "kurdistan-lawyers": {
        "path": BASE_DIR / "kurdistan-lawyers",
        "files": ["lawyers.csv"],
        "type": "csv",
        "name": "Kurdistan Lawyers"
    },
    "asiacell": {
        "path": BASE_DIR / "asiacell",
        "files": ["Asiacell-2023.accdb"],
        "type": "access",
        "name": "Asiacell Database"
    }
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
            "age": "🎂 لێگەریان ب تەمەن",
            "date_of_birth": "📅 لێگەریان ب بەروارێ ژدایکبوونێ",
            "passport": "🪪 لێگەریان ب ناسنامە (پاسپۆرت)",
            "vaccine_date": "💉 لێگەریان ب بەروارێ ڤاکسینێ",
            "facebook_id": "🆔 لێگەریان ب ID یێ فەیسبوکی",
            "facebook_username": "👤 لێگەریان ب ناڤێ هەژمارا فەیسبوکی",
            "full_search": "🔎 لێگەریان ل هەمیان",
            "truecaller": "📱 لێگەریان ب Truecaller"
        },
        "instructions": {
            "name": "✅ لێگەریان ب ناڤ هاتە دەستنیشانکرن.\nهیڤییە ناڤی بنڤیسە (کوردی، ئینگلیزی، عەرەبی)\n\n💡 نمونە: 'Haider' یان 'هایدار احمد'",
            "phone": "✅ لێگەریان ب ژمارێ هاتە دەستنیشانکرن.\nهیڤییە ژمارا موبایکی بنڤیسە\n\n🔍 نمونە: 7708356605 یان +9647708356605",
            "age": "✅ لێگەریان ب تەمەن هاتە دەستنیشانکرن.\nهیڤییە ژمارا تەمەنێ بنڤیسە\n\n🎂 نمونە: 25 یان 30",
            "date_of_birth": "✅ لێگەریان ب بەروارێ ژدایکبوونێ هاتە دەستنیشانکرن.\nهیڤییە بەروارێ بنڤیسە\n\n📅 نمونە: '1990-05-15' یان '1990/05/15'",
            "passport": "✅ لێگەریان ب ژمارا کارتا نیشتیمانی هاتە دەستنیشانکرن.\nهیڤییە ژمارا ناسنامێ بنڤیسە\n\n🪪 نمونە: '1234567'",
            "vaccine_date": "✅ لێگەریان ب بەروارێ ڤاکسینێ هاتە دەستنیشانکرن.\nهیڤییە بەروارێ ڤاکسینێ بنڤیسە\n\n💉 نمونە: '2021-11-08'",
            "facebook_id": "✅ لێگەریان ب ئایدیێ فەیسبوکی هاتە هەلبژارتن.\nهیڤییە ژمارا ئایدیێ فەیسبوکی بنڤیسە\n\n💡 نمونە: '100010778795609'",
            "facebook_username": "✅ لێگەریان ب ناڤێ هەژمارا فەیسبوکی هاتە هەلبژارتن.\nهیڤییە ناڤێ هەژمارێ بنڤیسە\n\n💡 نمونە: 'haider.qies.3'",
            "full": "✅ لێگەریان ل هەمیا هاتە دەستنیشانکرن.\nهیڤییە ئیك ژڤان بنڤیسی (ناڤ، ژمارا موبایلی، بەروار، ژمارا ناسنامە)",
            "truecaller": "✅ لێگەریان ب Truecaller هاتە دەستنیشانکرن.\nهیڤییە ژمارا موبایلێ بنڤیسە\n\n📱 نمونە: 7701234567 یان +9647701234567"
        },
        "searching": "🔍 لێگەریان ل هەمی داتابەیسا...",
        "no_results": "❌ هیچ زانیارییەک نەهاتە دیتن دناڤ داتابیسێن مەدا.",
        "found": "✅ لیگەریان ب دوماهیک هات! زانیاریێن {total} کەسا هاتنە دیتن.\n\n📊 زانیاریێن ژ داتابەیسا هاتینە دیتن:",
        "back": "⏪ زڤرین",
        "prev_page": "◀ پەڕەی پێشڤە",
        "next_page": "پەڕەی دواڤە ▶",
        "bot_info": "ℹ️ زانیاریێن بوتی",
        "join_channel": "🔴 دڤێت تو جوینی کەناڵی ببی تاکو بوتی بکار بینی.",
        "processing": "⏳ لێگەریانەکا تەیا دیتر یا د کاریدا، هیڤیە براوەستە...",
        "select_database": "📋 داتابەیسی بهەلبژێرە دا داتایا ببینی:",
        "truecaller_login": "📱 Truecaller Login\n\n📥 هیڤییە تو دەسپێکێ بچیتە بارنامەی TrueCaller و Login بکەی، لسەر ئێکێ ژ سیستەمێن Iphone یان Android.\n\n📞 پشتێ هەنگە ئەو ژمارەیەتا login بکرێ بۆما فراوانە (وەک: 07501231234 یان +9647501231234).",
        "truecaller_otp": "📨 ئەو کودێ فراوانە یێ ب OTP بۆتە هاتە، لسەر TrueCaller.",
        "truecaller_success": "✅ ب سەرکەفتەیانا تو بەژدار بووی، هیڤییە وێ هاژمارە فراوانەیا تە دەوەت زانیاریێت وێ ببینە...",
        "truecaller_not_logged": "🔒 تو هەژمارێ Truecaller نەکردووە.\nهیڤییە کلیک بکە لسەر 'Truecaller' بو بەژداربینین.",
        "logout": "🚪 ب سەرکەفتەیانا تو چوویە جدارڤە، بۆ دووبارە login بوونە /start کلیک بکە"
    },
    "ku": {
        "start": "🤖 بۆتی گەڕان لە هەموو داتابەیسەکان\n\n📌 تکایە زمانەکەت هەڵبژێرە:",
        "welcome": "بەخێربێیت! تکایە جۆری گەڕانەکەت هەڵبژێرە:",
        "search_types": {
            "name": "🔍 گەڕان بە ناو",
            "phone": "📞 گەڕان بە ژمارەی تەلەفۆن",
            "age": "🎂 گەڕان بە تەمەن",
            "date_of_birth": "📅 گەڕان بە بەرواری لەدایک بوون",
            "passport": "🪪 گەڕان بە ناسنامە (پاسپۆرت)",
            "vaccine_date": "💉 گەڕان بە بەرواری ڤاکسین",
            "facebook_id": "🆔 گەڕان بە ژمارەی فەیسبووک",
            "facebook_username": "👤 گەڕان بە ناوی بەکارهێنەری فەیسبووک",
            "full_search": "🔎 گەڕان بە هەموو زانیاریەکان",
            "truecaller": "📱 گەڕان بە Truecaller"
        },
        "instructions": {
            "name": "✅ گەڕان بە ناو هەڵبژێردرا.\nتکایە ناوەکە بنووسە\n\n💡 نموونە: 'Haider' یان 'علی احمد'",
            "phone": "✅ گەڕان بە ژمارەی تەلەفۆن هەڵبژێردرا.\nتکایە ژمارەی تەلەفۆنەکە بنووسە\n\n🔍 نموونە: 7708356605 یان +9647708356605",
            "age": "✅ گەڕان بە تەمەن هەڵبژێردرا.\nتکایە ژمارەی تەمەن بنووسە\n\n🎂 نموونە: 25 یان 30",
            "date_of_birth": "✅ گەڕان بە بەرواری لەدایک بوون هەڵبژێردرا.\nتکایە بەروارەکە بنووسە\n\n📅 نموونە: '1990-05-15' یان '1990/05/15'",
            "passport": "✅ گەڕان بە ژمارەی ناسنامە هەڵبژێردرا.\nتکایە ژمارەی ناسنامە بنووسە\n\n🪪 نموونە: '1234567'",
            "vaccine_date": "✅ گەڕان بە بەرواری ڤاکسین هەڵبژێردرا.\nتکایە بەرواری ڤاکسین بنووسە\n\n💉 نموونە: '2021-11-08'",
            "facebook_id": "✅ گەڕان بە ژمارەی فەیسبووک هەڵبژێردرا.\nتکایە ژمارەی فەیسبووک بنووسە\n\n💡 نموونە: '100010778795609'",
            "facebook_username": "✅ گەڕان بە ناوی بەکارهێنەری فەیسبووک هەڵبژێردرا.\nتکایە ناوی بەکارهێنەر بنووسە\n\n💡 نموونە: 'haider.qies.3'",
            "full": "✅ گەڕان بە هەموو زانیاریەکان هەڵبژێردرا.\nتکایە هەر زانیاریەک بنووسە (ناو، ژمارە، بەروار، یان ID)",
            "truecaller": "✅ گەڕان بە Truecaller هەڵبژێردرا.\nتکایە ژمارەی تەلەفۆن بنووسە\n\n📱 نموونە: 7701234567 یان +9647701234567"
        },
        "searching": "🔍 گەڕان لە هەموو داتابەیسەکاندا...",
        "no_results": "❌ هیچ زانیاریەک نەدۆزرایەوە لە هیچ داتابیسێکدا.",
        "found": "✅ گەڕان تەواو بوو! {total} کەس دۆزرایەوە.\n\n📊 ئەنجامەکان بەپێی داتابەیس:",
        "back": "⏪ گەڕانەوە",
        "prev_page": "◀ پەڕەی پێشوو",
        "next_page": "پەڕەی دوواتر ▶",
        "bot_info": "ℹ️ زانیاری بۆت",
        "join_channel": "🔴 دڤێت تو بەژداری کەناڵی ببی تاکو بشێی بوتی بکاربینی.",
        "processing": "⏳ گەڕانێکی تر لە کارە، تکایە چاوەروان بە...",
        "select_database": "📋 داتابەیسێک هەڵبژێرە بۆ بینینی ئەنجامەکان:",
        "truecaller_login": "📱 Truecaller Login\n\n📥 تکایە تو دەستپێک بچیتە بەرنامەی TrueCaller و Login بکەی، لسەر ئێکێ ژ سیستەمێن Iphone یان Android.\n\n📞 پشتێ هەنگە ئەو ژمارەیەتا login بکرێ بۆما فراوانە (وەک: 07501231234 یان +9647501231234).",
        "truecaller_otp": "📨 ئەو کودێ فراوانە یێ ب OTP بۆتە هاتە، لسەر TrueCaller.",
        "truecaller_success": "✅ ب سەرکەفتەیانا تو بەژدار بووی، هیڤییە وێ هاژمارە فراوانەیا تە دەوەت زانیاریێت وێ ببینە...",
        "truecaller_not_logged": "🔒 تو هەژمارێ Truecaller نەکردووە.\nتکایە کلیک بکە لسەر 'Truecaller' بۆ بەژداربینین.",
        "logout": "🚪 ب سەرکەفتەیانا تو چوویە جدارڤە، بۆ دووبارە login بوونە /start کلیک بکە"
    }
}

# Global variables
user_states = {}
search_results = {}
user_languages = {}
active_searches = set()
registered_users = set()
truecaller_login_states = {}
truecaller_tokens = {}
active_truecaller_tokens = []  # List of active tokens
token_last_used = {}  # Track when tokens were last used

# Pagination settings
ITEMS_PER_PAGE = 20

# Logging functions
def log_user_activity(user_id, username, action):
    """Log user activity to CSV"""
    try:
        file_exists = os.path.isfile("user_logs.csv")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open("user_logs.csv", "a", encoding="utf-8", newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "user_id", "username", "action"])
            
            writer.writerow([timestamp, user_id, username or "No Username", action])
    except Exception as e:
        logging.error(f"Error logging user activity: {e}")

def log_search(user_id, username, search_type, search_term, results_count):
    """Log search activity to CSV"""
    try:
        file_exists = os.path.isfile("search_logs.csv")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open("search_logs.csv", "a", encoding="utf-8", newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "user_id", "username", "search_type", "search_term", "results_count"])
            
            writer.writerow([timestamp, user_id, username or "No Username", search_type, search_term, results_count])
    except Exception as e:
        logging.error(f"Error logging search: {e}")

def load_registered_users():
    """Load registered users from file"""
    global registered_users
    try:
        if os.path.exists("registered_users.csv"):
            with open("registered_users.csv", "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        registered_users.add(int(row[0]))
    except Exception as e:
        logging.error(f"Error loading registered users: {e}")

def save_registered_user(user_id, username):
    """Save user ID to registered users file if not already exists"""
    global registered_users
    if user_id not in registered_users:
        registered_users.add(user_id)
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("registered_users.csv", "a", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerow([user_id, username or "No Username", timestamp])
        except Exception as e:
            logging.error(f"Error saving registered user: {e}")

def load_truecaller_tokens():
    """Load Truecaller tokens from file and check validity"""
    global truecaller_tokens, active_truecaller_tokens
    try:
        if os.path.exists(AUTH_FILE):
            with open(AUTH_FILE, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    user_id = int(row['user_id'])
                    token = row['access_token']
                    truecaller_tokens[user_id] = token
                    
                    # Check token validity
                    if is_token_valid(token):
                        active_truecaller_tokens.append(token)
                        token_last_used[token] = 0  # Initialize last used time
                    else:
                        logger.info(f"Token for user {user_id} is expired")
    except Exception as e:
        logging.error(f"Error loading Truecaller tokens: {e}")

def is_token_valid(token):
    """Check if a Truecaller token is still valid"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "*/*",
            "Authorization": f"Bearer {token}",
            "Referer": "https://www.truecaller.com/",
            "Origin": "https://www.truecaller.com"
        }
        
        # Test with a common Iraqi number
        params = {
            "q": "7701234567",
            "countryCode": "iq",
            "type": "44"
        }
        
        response = requests.get(TRUECALLER_API_URL, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            return False
        else:
            # Try one more time with different number
            params["q"] = "7501234567"
            response2 = requests.get(TRUECALLER_API_URL, headers=headers, params=params, timeout=10)
            return response2.status_code == 200
            
    except Exception as e:
        logger.error(f"Error checking token validity: {e}")
        return False

def get_random_valid_token():
    """Get a random valid Truecaller token"""
    global active_truecaller_tokens
    
    if not active_truecaller_tokens:
        # Try to reload tokens
        load_truecaller_tokens()
        if not active_truecaller_tokens:
            return None
    
    # Sort tokens by last used time to distribute load
    sorted_tokens = sorted(active_truecaller_tokens, key=lambda t: token_last_used.get(t, 0))
    
    # Get the least recently used token
    token = sorted_tokens[0]
    token_last_used[token] = time.time()
    
    # Re-check token validity
    if not is_token_valid(token):
        active_truecaller_tokens.remove(token)
        return get_random_valid_token()
    
    return token

def save_truecaller_token(user_id, token):
    """Save Truecaller token to file"""
    global truecaller_tokens, active_truecaller_tokens
    
    truecaller_tokens[user_id] = token
    
    # Add to active tokens if valid
    if is_token_valid(token):
        if token not in active_truecaller_tokens:
            active_truecaller_tokens.append(token)
            token_last_used[token] = time.time()
    
    # Remove existing entry if exists
    rows = []
    fieldnames = ['user_id', 'access_token', 'login_time']
    
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row['user_id'] != str(user_id):
                    rows.append(row)
    
    # Add new token
    rows.append({
        'user_id': str(user_id),
        'access_token': token,
        'login_time': datetime.now().isoformat()
    })
    
    # Write back to file
    with open(AUTH_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def delete_truecaller_token(user_id):
    """Delete Truecaller token"""
    global truecaller_tokens, active_truecaller_tokens
    
    if user_id in truecaller_tokens:
        token = truecaller_tokens[user_id]
        if token in active_truecaller_tokens:
            active_truecaller_tokens.remove(token)
        del truecaller_tokens[user_id]
    
    # Remove from file
    if os.path.exists(AUTH_FILE):
        rows = []
        with open(AUTH_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row['user_id'] != str(user_id):
                    rows.append(row)
        
        with open(AUTH_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

# Helper functions
def normalize_phone(phone):
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
    
    # For Asiacell numbers, they're already 10 digits starting with 77
    # Don't add leading 0 if it's already 10 digits
    if phone_clean and len(phone_clean) == 10 and phone_clean.startswith('77'):
        return phone_clean
    
    if phone_clean and not phone_clean.startswith('0'):
        phone_clean = '0' + phone_clean
    
    return phone_clean

def calculate_age(birth_date_str):
    """Calculate age from birth date string"""
    try:
        # Try different date formats
        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y', '%m-%d-%Y', '%m/%d/%Y'):
            try:
                birth_date = datetime.strptime(birth_date_str, fmt).date()
                today = date.today()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                return age
            except ValueError:
                continue
    except:
        pass
    return None

def hide_sensitive_info(text, char_count=4):
    """Hide sensitive information like IDs and passwords"""
    if not text or len(text) < char_count:
        return text
    
    if len(text) <= 8:
        return f"{text[:2]}{'*' * (len(text)-4)}{text[-2:]}"
    else:
        return f"{text[:4]}{'*' * (len(text)-8)}{text[-4:]}"

def get_text(user_id, key, **kwargs):
    """Get text in user's language"""
    lang = user_languages.get(user_id, "ku")
    text = TEXTS.get(lang, TEXTS["ku"]).get(key, "")
    if kwargs:
        text = text.format(**kwargs)
    return text

# Truecaller functions
def clean_lookup_number(text):
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

def download_truecaller_image(image_url, token):
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
            # Save image temporarily
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(response.content)
            temp_file.close()
            return temp_file.name
        
    except Exception as e:
        logger.error(f"Error downloading Truecaller image: {e}")
    
    return None

def format_truecaller_result(data):
    """Format Truecaller API response"""
    if not data:
        return "❌ Hech zanyare nahatna detn bo ve jimare."
    
    result = []
    
    # Basic Information
    name = data.get('name', 'Unknown')
    if name == "تم تعريفه كمتطفل":
        name = "Ev Jimara Spam Krya, To nashey bbene."
    
    result.append(f"  • ID: {data.get('id', 'Unknown')}")
    result.append(f"  • Nav: {name}")
    result.append(f"  • Nvesena Kire: {data.get('jobTitle', 'Unknown')}")
    result.append(f"  • Nave Companyan: {data.get('companyName', 'Unknown')}")
    result.append(f"  • Pila: {data.get('score', 'Unknown')}")
    result.append(f"  • Jimara Kasya yan balava: {data.get('access', 'Unknown')}")
    result.append(f"  • Hajmara Bawarye ya: {'Bale' if data.get('enhanced') else 'Naxer'}")        
    
    # Phone Details
    phones = data.get('phones', [])
    if phones:
        result.append("\n📞 Jimara:")
        for phone in phones:
            result.append(f"  • Jimara mobile: {phone.get('e164Format', 'Unknown')}")
            result.append(f"  • Jore jimare: {phone.get('numberType', 'Unknown')}")
            result.append(f"  • Jimara Rastaqena: {phone.get('nationalFormat', 'Unknown')}")
            result.append(f"  • Dialoge code: {phone.get('dialingCode', 'Unknown')}")
            result.append(f"  • Companya jimare: {phone.get('carrier', 'Unknown')}")
            result.append(f"  • Jor: {phone.get('type', 'Unknown')}")
    
    # Addresses
    addresses = data.get('addresses', [])
    if addresses:
        result.append("\n🏠 Nav o nishanen Jhe:")
        for address in addresses:
            result.append(f"  • Jih: {address.get('address', 'Unknown')}")
            result.append(f"  • Kolan: {address.get('street', 'Unknown')}")
            result.append(f"  • Zipcode: {address.get('zipCode', 'Unknown')}")
            result.append(f"  • Bajer: {address.get('city', 'Unknown')}")
            result.append(f"  • Dame Davare: {address.get('timeZone', 'Unknown')}")
    
    # Internet Addresses
    internet = data.get('internetAddresses', [])
    if internet:
        result.append("\n🌐 Nav o nishanen Internete:")
        for addr in internet:
            service = addr.get('service', 'Unknown')
            if service == 'email':
                result.append(f"  • Email: {addr.get('id', 'Unknown')}")
            elif service == 'link':
                result.append(f"  • Link: {addr.get('id', 'Unknown')}")
    
    # Search Warnings
    srchwarn = data.get('searchWarnings', [])
    if srchwarn:
        result.append("\n⚠️ Hshyarbon li ligariane:")
        for warning in srchwarn:
            rule_name = warning.get('ruleName', 'Unknown')
            result.append(f"  • {rule_name}")
    
    # Badges
    badges = data.get('badges', [])
    if badges:
        result.append("\n🏅 Nishan:")
        for badge in badges:
            result.append(f"  • {badge.capitalize()}")
    
    # Tags
    tags = data.get('tags', [])
    if tags:
        result.append("\n🏷️ Tags:")
        for tag in tags:
            result.append(f"  • {tag}")
    
    return "\n".join(result)

# Database search functions
async def search_iraq_facebook(search_term, search_type):
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
                    
                    elif search_type == "facebook_id":
                        if search_term in user_id:
                            matched = True
                    
                    elif search_type == "facebook_username":
                        if facebook_url and search_term.lower() in facebook_url.lower():
                            matched = True
                    
                    elif search_type == "full":
                        search_lower = search_term.lower()
                        if (search_lower in first_name.lower() or 
                            search_lower in last_name.lower() or
                            search_lower in user_id.lower() or
                            search_lower in phone.lower() or
                            (facebook_url and search_lower in facebook_url.lower())):
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
                            "location": row[9] if len(row) > 9 else "",
                            "email": row[13] if len(row) > 13 else ""
                        })
                        
                        if len(results) >= 10000:
                            return results
            
        except Exception as e:
            logging.error(f"Error reading {file_path}: {e}")
    
    return results

async def search_kurdistan_health(search_term, search_type):
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
                
                elif search_type == "date_of_birth":
                    if search_term in birth_date:
                        matched = True
                
                elif search_type == "age":
                    age = calculate_age(birth_date)
                    if age and str(age) == search_term:
                        matched = True
                
                elif search_type == "passport" or search_type == "national_id":
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
                        search_lower in national_id.lower() or
                        search_lower in vaccine_date.lower()):
                        matched = True
                
                if matched:
                    results.append({
                        "database": "kurdistan-health",
                        "id": row.get('id', ''),
                        "name": name,
                        "phone": phone,
                        "birth_date": birth_date,
                        "age": calculate_age(birth_date),
                        "gender": row.get('gender', ''),
                        "province": row.get('province', ''),
                        "vaccine_1_type": row.get('vaccine_1_type', ''),
                        "vaccine_1_date": row.get('vaccine_1_date', ''),
                        "identity_card_number": national_id
                    })
                    
                    if len(results) >= 10000:
                        break
        
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
    
    return results

async def search_aman(search_term, search_type):
    """Search in Aman CSV with correct column mapping"""
    results = []
    db_info = DATABASES["aman"]
    file_path = db_info["path"] / "aman.csv"
    
    if not file_path.exists():
        return results
    
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            # Read the first line to get headers
            first_line = f.readline().strip()
            # Check if file is empty
            if not first_line:
                return results
            
            # Parse headers
            headers = first_line.split(',')
            
            # Go back to start
            f.seek(0)
            reader = csv.DictReader(f)
            
            for row in reader:
                matched = False
                
                # Extract key fields with fallbacks
                full_name = row.get('الاسم_الرباعي', '') or row.get('اسم_مالك_العجلة', '') or row.get('اسم_السائق_الرباعي', '')
                phone = row.get('رقم_الهاتف', '')
                national_id = row.get('الهوية', '') or row.get('رقم_الهوية', '')
                birth_date = row.get('تاريخ_الميلاد', '')
                
                if search_type == "name":
                    if search_term.lower() in full_name.lower():
                        matched = True
                
                elif search_type == "phone":
                    normalized_search = normalize_phone(search_term)
                    normalized_db = normalize_phone(phone)
                    if normalized_search and normalized_db and normalized_search in normalized_db:
                        matched = True
                
                elif search_type == "date_of_birth":
                    if search_term in birth_date:
                        matched = True
                
                elif search_type == "age":
                    age = calculate_age(birth_date)
                    if age and str(age) == search_term:
                        matched = True
                
                elif search_type == "passport" or search_type == "national_id":
                    if search_term in national_id:
                        matched = True
                
                elif search_type == "full":
                    search_lower = search_term.lower()
                    if (search_lower in full_name.lower() or 
                        search_lower in phone.lower() or
                        search_lower in national_id.lower() or
                        search_lower in birth_date.lower()):
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
                        "identity": row.get('الهوية', ''),
                        "identity_number": national_id,
                        "birth_date": birth_date,
                        "age": calculate_age(birth_date),
                        "car_model": row.get('الموديل', ''),
                        "car_color": row.get('لون_العجلة', ''),
                        "car_number": row.get('رقم_اللوحات', ''),
                        "address": row.get('العنوان', ''),
                        "province": row.get('المحافظة', ''),
                        "workplace": row.get('جهة_العمل', row.get('المهنة', '')),
                        "mother_name": row.get('اسم_الام', ''),
                        "entry_point": row.get('اسم_المنفذ', ''),
                        "car_owner": row.get('اسم_مالك_العجلة', ''),
                        "nearest_point": row.get('اقرب_نقطة_دالة', ''),
                        "bundle": row.get('الباقة', ''),
                        "email": row.get('البريد_الالكتروني', ''),
                        "country": row.get('البلد', ''),
                        "specialization": row.get('التخصص', ''),
                        "classification": row.get('التصنيف', ''),
                        "entity": row.get('الجهة', ''),
                        "marital_status": row.get('الحالة_الاجتماعية', ''),
                        "description": row.get('الصفة', ''),
                        "social_security": row.get('الضمان_الاجتماعي', ''),
                        "family": row.get('العائلة', ''),
                        "data_entry_user": row.get('المستخدم_الذي_ادخل_البيانات', ''),
                        "notes": row.get('الملاحظات', ''),
                        "profession": row.get('المهنة', ''),
                        "union": row.get('النقابة', ''),
                        "expiry_date": row.get('تاريخ_الانتهاء', ''),
                        "join_date": row.get('تاريخ_الانظمام', ''),
                        "birth_date": row.get('تاريخ_الميلاد', ''),
                        "route_activation_date": row.get('تاريخ_نفاذ_خط_السیر', ''),
                        "receipt_status": row.get('حالة_الاستلام', ''),
                        "id_payment_status": row.get('حالة_الدفع_الهوية', ''),
                        "certificate_status": row.get('حالة_الشهادة', ''),
                        "id_status": row.get('حالة_الهوية', ''),
                        "route": row.get('خط_السیر', ''),
                        "file_number": row.get('رقم_الاظبارة', ''),
                        "insurance_number": row.get('رقم_التامين', ''),
                        "annual_number": row.get('رقم_السنوية', ''),
                        "receipt_number": row.get('رقم_الوصل', ''),
                        "work_years": row.get('سنوات_العمل', ''),
                        "work_address": row.get('عنوان_العمل', ''),
                        "car_cost": row.get('كلفة_العجلة', ''),
                        "password": row.get('كلمة_المرور', ''),
                        "referral_code": row.get('کود_الاحالة', ''),
                        "special_referral_code": row.get('کود_الاحالة_الخاص_به', ''),
                        "car_type": row.get('نوع_العجلة', ''),
                        "driver_name": row.get('اسم_السائق_الرباعي', ''),
                        "image_count": image_count,
                        "raw_data": row
                    })
                    
                    if len(results) >= 10000:
                        break
        
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
    
    return results

async def search_json_database(db_name, search_term, search_type):
    """Search in JSON databases"""
    results = []
    db_info = DATABASES[db_name]
    file_path = db_info["path"] / db_info["files"][0]
    
    if not file_path.exists():
        return results
    
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
                    
                    if search_type == "name":
                        if search_term.lower() in full_name.lower():
                            matched = True
                    elif search_type == "phone":
                        normalized_search = normalize_phone(search_term)
                        normalized_db = normalize_phone(phone)
                        if normalized_search and normalized_db and normalized_search in normalized_db:
                            matched = True
                    elif search_type == "date_of_birth":
                        if search_term in birth_date:
                            matched = True
                    elif search_type == "age":
                        age = calculate_age(birth_date)
                        if age and str(age) == search_term:
                            matched = True
                    elif search_type == "passport" or search_type == "national_id":
                        if search_term in national_id:
                            matched = True
                    elif search_type == "full":
                        search_lower = search_term.lower()
                        if (search_lower in full_name.lower() or 
                            search_lower in phone.lower() or
                            search_lower in national_id.lower() or
                            search_lower in birth_date.lower()):
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
                    
                    if len(results) >= 10000:
                        break
        
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
    
    return results

async def search_lawyers(search_term, search_type):
    """Search in lawyers database"""
    results = []
    db_info = DATABASES["kurdistan-lawyers"]
    file_path = db_info["path"] / "lawyers.csv"
    
    if not file_path.exists():
        return results
    
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
                                image_path = possible_path
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
                        "image_path": str(image_path) if image_path else None
                    })
                    
                    if len(results) >= 30:
                        break
        
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
    
    return results

async def search_asiacell(search_term, search_type):
    """Search in Asiacell Access database"""
    results = []
    db_info = DATABASES["asiacell"]
    file_path = db_info["path"] / "Asiacell-2023.accdb"
    
    if not file_path.exists():
        return results
    
    try:
        # Connect to Access database
        conn_str = (
            r"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};"
            r"DBQ={};".format(str(file_path))
        )
        
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Clean the search term for Asiacell
        search_clean = normalize_phone(search_term)
        # For Asiacell, remove leading 0 if present and it's 11 digits
        if search_clean and len(search_clean) == 11 and search_clean.startswith('0'):
            search_clean = search_clean[1:]  # Remove leading 0
        
        # Search in MAIN_DATA table
        if search_type == "name":
            query = "SELECT NAME, PHONE, BIRTH, CARD_ID, PRO FROM MAIN_DATA WHERE NAME LIKE ?"
            cursor.execute(query, f'%{search_term}%')
        elif search_type == "phone":
            if search_clean:
                # Try different formats
                query = "SELECT NAME, PHONE, BIRTH, CARD_ID, PRO FROM MAIN_DATA WHERE PHONE LIKE ?"
                cursor.execute(query, f'%{search_clean}%')
            else:
                return results
        elif search_type == "date_of_birth":
            query = "SELECT NAME, PHONE, BIRTH, CARD_ID, PRO FROM MAIN_DATA WHERE BIRTH LIKE ?"
            cursor.execute(query, f'%{search_term}%')
        elif search_type == "age":
            # This is complex for Access, skip for now or implement approximate age search
            return results
        elif search_type == "passport" or search_type == "national_id":
            query = "SELECT NAME, PHONE, BIRTH, CARD_ID, PRO FROM MAIN_DATA WHERE CARD_ID LIKE ?"
            cursor.execute(query, f'%{search_term}%')
        elif search_type == "full":
            # Search in multiple fields
            if search_clean:
                query = "SELECT NAME, PHONE, BIRTH, CARD_ID, PRO FROM MAIN_DATA WHERE NAME LIKE ? OR PHONE LIKE ? OR CARD_ID LIKE ? OR BIRTH LIKE ?"
                cursor.execute(query, f'%{search_term}%', f'%{search_clean}%', f'%{search_term}%', f'%{search_term}%')
            else:
                query = "SELECT NAME, PHONE, BIRTH, CARD_ID, PRO FROM MAIN_DATA WHERE NAME LIKE ? OR CARD_ID LIKE ? OR BIRTH LIKE ?"
                cursor.execute(query, f'%{search_term}%', f'%{search_term}%', f'%{search_term}%')
        else:
            # For other search types, don't search Asiacell
            cursor.close()
            conn.close()
            return results
        
        rows = cursor.fetchall()
        
        for row in rows:
            results.append({
                "database": "asiacell",
                "name": row[0] if row[0] else "",
                "phone": row[1] if row[1] else "",
                "birth_date": row[2] if row[2] else "",
                "card_id": row[3] if row[3] else "",
                "province": row[4] if row[4] else "",
                "age": calculate_age(row[2]) if row[2] else None
            })
            
            if len(results) >= 10000:
                break
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logging.error(f"Error searching Asiacell database: {e}")
        import traceback
        logging.error(traceback.format_exc())
    
    return results

async def search_truecaller(search_term, user_id=None):
    """Search using Truecaller API with random token selection"""
    
    # Get a random valid token
    token = get_random_valid_token()
    if not token:
        return []
    
    try:
        # Clean phone number
        phone_number = clean_lookup_number(search_term)
        if not phone_number:
            return []
        
        # Prepare API request
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "*/*",
            "Authorization": f"Bearer {token}",
            "Referer": "https://www.truecaller.com/",
            "Origin": "https://www.truecaller.com"
        }

        params = {
            "q": phone_number,
            "countryCode": "iq",
            "type": "44"
        }

        # Make request
        response = requests.get(TRUECALLER_API_URL, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Download image if available
            image_path = None
            image_url = data.get('image')
            if image_url:
                image_path = download_truecaller_image(image_url, token)
            
            return [{
                "database": "truecaller",
                "data": data,
                "image_path": image_path
            }]
        elif response.status_code == 401:
            # Token expired, remove it
            if token in active_truecaller_tokens:
                active_truecaller_tokens.remove(token)
            return []
    
    except Exception as e:
        logging.error(f"Error searching Truecaller: {e}")
    
    return []

async def search_all_databases(search_term, search_type, user_id, message=None):
    """Search across all databases"""
    all_results = {}
    total_found = 0
    
    # Mark user as searching
    active_searches.add(user_id)
    
    databases_to_search = [
        ("iraq-facebook", search_iraq_facebook),
        ("kurdistan-health", search_kurdistan_health),
        ("aman", search_aman),
        ("loan-korektel", lambda term, stype: search_json_database("loan-korektel", term, stype)),
        ("qi-card", lambda term, stype: search_json_database("qi-card", term, stype)),
        ("zain", lambda term, stype: search_json_database("zain", term, stype)),
        ("kurdistan-lawyers", search_lawyers),
        ("asiacell", search_asiacell)
    ]
    
    for db_name, search_func in databases_to_search:
        if user_id not in active_searches:
            break
            
        try:
            # Update progress message
            if message:
                try:
                    await message.edit_text(f"🔍 لێگەریان د {DATABASES[db_name]['name']}...")
                except:
                    pass
            
            # Perform search
            results = await search_func(search_term, search_type)
            if results:
                all_results[db_name] = results
                total_found += len(results)
                
                if message and len(results) > 0:
                    try:
                        await message.edit_text(
                            f"✅ {len(results)} هاتە دیتن د {DATABASES[db_name]['name']}.\n"
                            f"📊 گشتی تا ئێستا: {total_found}"
                        )
                    except:
                        pass
            
            # Small delay to prevent rate limiting
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logging.error(f"Error searching {db_name}: {e}")
    
    # Clear active search
    if user_id in active_searches:
        active_searches.remove(user_id)
    
    return all_results

# Formatting functions
def format_lawyer_result(lawyer_data, lang):
    """Format lawyer result"""
    if lang == "ku":
        result_text = (
            "⚖️ زانیاری پارێزەر:\n\n"
            f"🆔 ژمارەی پارێزەر:\n{lawyer_data.get('id', 'N/A')}\n\n"
            f"👤 ناو:\n{lawyer_data.get('name', 'N/A')}\n\n"
            f"🏛️ جۆری پارێزەر:\n{lawyer_data.get('lawyer_type', 'N/A')}\n\n"
            f"⚧ ڕەگەز:\n{lawyer_data.get('gender', 'N/A')}\n\n"
            f"📞 ژمارەی مۆبایل:\n{lawyer_data.get('phone', 'N/A')}\n\n"
            f"📍 ناونیشان:\n{lawyer_data.get('address', 'N/A')}\n\n"
            f"📧 ئیمەیڵ:\n{lawyer_data.get('email', 'N/A')}\n\n"
            f"🏢 لق:\n{lawyer_data.get('branch', 'N/A')}\n\n"
            f"📅 بەرواری ئەندام بوون:\n{lawyer_data.get('join_date', 'N/A')}\n"
        )
    else:
        result_text = (
            "⚖️ زانیاریێن پارێزەری:\n\n"
            f"🆔 ئایدیێ پارێزەری:\n{lawyer_data.get('id', 'N/A')}\n\n"
            f"👤 ناڤ:\n{lawyer_data.get('name', 'N/A')}\n\n"
            f"🏛️ جورێ پارێزەری:\n{lawyer_data.get('lawyer_type', 'N/A')}\n\n"
            f"⚧ رەگەز:\n{lawyer_data.get('gender', 'N/A')}\n\n"
            f"📞 ژمارا موبایلێ:\n{lawyer_data.get('phone', 'N/A')}\n\n"
            f"📍 جهـ:\n{lawyer_data.get('address', 'N/A')}\n\n"
            f"📧 ئیمێڵ:\n{lawyer_data.get('email', 'N/A')}\n\n"
            f"🏢 ڵق:\n{lawyer_data.get('branch', 'N/A')}\n\n"
            f"📅 بەروارا بەژداربینێ:\n{lawyer_data.get('join_date', 'N/A')}\n"
        )
    
    return result_text, lawyer_data.get("image_path")

def format_facebook_result(facebook_data, lang):
    """Format Facebook data result"""
    if lang == "ku":
        result_text = (
            "📱 زانیاری فەیسبووک:\n\n"
            f"🆔 ژمارەی بەکارهێنەر:\n{hide_sensitive_info(facebook_data.get('user_id', 'N/A'))}\n\n"
            f"👤 ناو:\n{facebook_data.get('first_name', '')} {facebook_data.get('last_name', '')}\n\n"
            f"📞 ژمارەی تەلەفۆن:\n{facebook_data.get('phone', 'N/A')}\n\n"
            f"⚧ ڕەگەز:\n{facebook_data.get('gender', 'N/A')}\n\n"
            f"🔗 لینکی فەیسبووک:\n{facebook_data.get('facebook_url', 'N/A')}\n\n"
            f"📍 شوێن:\n{facebook_data.get('location', 'N/A')}\n\n"
            f"📧 ئیمەیڵ:\n{hide_sensitive_info(facebook_data.get('email', 'N/A'))}\n"
        )
    else:
        result_text = (
            "📱 زانیاریێن فەیسبوکی:\n\n"
            f"🆔 ئایدیێ هەژمارێ:\n{hide_sensitive_info(facebook_data.get('user_id', 'N/A'))}\n\n"
            f"👤 ناڤ:\n{facebook_data.get('first_name', '')} {facebook_data.get('last_name', '')}\n\n"
            f"📞 ژمارا موبایلێ:\n{facebook_data.get('phone', 'N/A')}\n\n"
            f"⚧ رەگەز:\n{facebook_data.get('gender', 'N/A')}\n\n"
            f"🔗 لینکێ فەیسبوکی:\n{facebook_data.get('facebook_url', 'N/A')}\n\n"
            f"📍 جهـ یان بایو:\n{facebook_data.get('location', 'N/A')}\n\n"
            f"📧 ئیمێڵ:\n{hide_sensitive_info(facebook_data.get('email', 'N/A'))}\n"
        )
    
    return result_text

def format_health_result(health_data, lang):
    """Format health data result"""
    if lang == "ku":
        result_text = (
            "🏥 زانیاری تەندروستی:\n\n"
            f"🆔 ژمارە:\n{health_data.get('id', 'N/A')}\n\n"
            f"👤 ناو:\n{health_data.get('name', 'N/A')}\n\n"
            f"📞 ژمارەی تەلەفۆن:\n{health_data.get('phone', 'N/A')}\n\n"
            f"📅 بەرواری لەدایک بوون:\n{health_data.get('birth_date', 'N/A')}\n\n"
            f"🎂 تەمەن:\n{health_data.get('age', 'N/A')}\n\n"
            f"⚧ ڕەگەز:\n{health_data.get('gender', 'N/A')}\n\n"
            f"🏙️ پارێزگا:\n{health_data.get('province', 'N/A')}\n\n"
            f"🪪 ژمارەی ناسنامە:\n{hide_sensitive_info(health_data.get('identity_card_number', 'N/A'))}\n\n"
            f"💉 جۆری ڤاکسینی یەکەم:\n{health_data.get('vaccine_1_type', 'N/A')}\n\n"
            f"📅 بەرواری ڤاکسینی یەکەم:\n{health_data.get('vaccine_1_date', 'N/A')}\n"
        )
    else:
        result_text = (
            "🏥 زانیاریێن تەندروستی:\n\n"
            f"🆔 ئایدی:\n{health_data.get('id', 'N/A')}\n\n"
            f"👤 ناڤ:\n{health_data.get('name', 'N/A')}\n\n"
            f"📞 ژمارا موبایلێ:\n{health_data.get('phone', 'N/A')}\n\n"
            f"📅 بەروارا ژدایکبوونێ:\n{health_data.get('birth_date', 'N/A')}\n\n"
            f"🎂 تەمەن:\n{health_data.get('age', 'N/A')}\n\n"
            f"⚧ رەگەز:\n{health_data.get('gender', 'N/A')}\n\n"
            f"🏙️ پارێزگەهـ:\n{health_data.get('province', 'N/A')}\n\n"
            f"🪪 ژمارا ناسنامێ:\n{hide_sensitive_info(health_data.get('identity_card_number', 'N/A'))}\n\n"
            f"💉 خورێ ئێکەم ڤاکسێنێ:\n{health_data.get('vaccine_1_type', 'N/A')}\n\n"
            f"📅 بەروارا ئێکەم ڤاکسینێ:\n{health_data.get('vaccine_1_date', 'N/A')}\n"
        )
    
    return result_text

def format_aman_result(aman_data, lang):
    """Format Aman data result with all fields"""
    if lang == "ku":
        result_text = (
            "🚗 زانیاری ئامان:\n\n"
            f"👤 ناوی تەواو:\n{aman_data.get('full_name', 'N/A')}\n\n"
            f"📞 ژمارەی تەلەفۆن:\n{aman_data.get('phone', 'N/A')}\n\n"
            f"📅 بەرواری لەدایک بوون:\n{aman_data.get('birth_date', 'N/A')}\n\n"
            f"🎂 تەمەن:\n{aman_data.get('age', 'N/A')}\n\n"
            f"👩 ناوی دایک:\n{aman_data.get('mother_name', 'N/A')}\n\n"
            f"🪪 ژمارەی ناسنامە:\n{hide_sensitive_info(aman_data.get('identity_number', 'N/A'))}\n\n"
            f"🚗 مۆدێلی ئوتومبێل:\n{aman_data.get('car_model', 'N/A')}\n\n"
            f"🎨 ڕەنگی ئوتومبێل:\n{aman_data.get('car_color', 'N/A')}\n\n"
            f"🚗 ژمارەی ئوتومبێل:\n{aman_data.get('car_number', 'N/A')}\n\n"
            f"🏠 ناونیشان:\n{aman_data.get('address', 'N/A')}\n\n"
            f"🏙️ پارێزگا:\n{aman_data.get('province', 'N/A')}\n"
        )
    else:
        result_text = (
            "🚗 زانیاریێن ئەمان:\n\n"
            f"👤 ناڤ:\n{aman_data.get('full_name', 'N/A')}\n\n"
            f"📞 ژمارا موبایلێ:\n{aman_data.get('phone', 'N/A')}\n\n"
            f"📅 بەروارا ژدایکبوونێ:\n{aman_data.get('birth_date', 'N/A')}\n\n"
            f"🎂 تەمەن:\n{aman_data.get('age', 'N/A')}\n\n"
            f"👩 ناڤێ دەیکێ:\n{aman_data.get('mother_name', 'N/A')}\n\n"
            f"🪪 ژمارا ناسنامی:\n{hide_sensitive_info(aman_data.get('identity_number', 'N/A'))}\n\n"
            f"🚙 جورێ ئوتومبیلێ:\n{aman_data.get('car_model', 'N/A')}\n\n"
            f"🎨 رەنگێ ترومبێلێ:\n{aman_data.get('car_color', 'N/A')}\n\n"
            f"🚗 ژمارا ترومبێلێ:\n{aman_data.get('car_number', 'N/A')}\n\n"
            f"🏠 جهـ:\n{aman_data.get('address', 'N/A')}\n\n"
            f"🏙️ پارێزگەهـ:\n{aman_data.get('province', 'N/A')}\n"
        )
    
    # Add image count if available
    image_count = aman_data.get('image_count', 0)
    if image_count > 0:
        if lang == "ku":
            result_text += f"\n\n📸 ئەم کەسە {image_count} وێنەی هەیە لە داتابەیسماندا."
        else:
            result_text += f"\n\n📸 مە {image_count} وێنەیێن ڤی کەسی هەنە"
    
    return result_text

def format_json_result(json_data, db_name, lang):
    """Format JSON database results"""
    data = json_data.get("data", {})
    
    if db_name == "loan-korektel":
        if lang == "ku":
            result_text = (
                "💰 زانیاری وام (کۆرەکتێل):\n\n"
                f"📞 ژمارەی تەلەفۆن:\n{data.get('MSISDN', 'N/A')}\n\n"
                f"🏦 کۆدی خزمەتگوزاری:\n{data.get('SC', 'N/A')}\n\n"
                f"👤 ناوی ئاژانسی:\n{data.get('AgentName', 'N/A')}\n\n"
                f"📅 بەروار:\n{data.get('Date', 'N/A')}\n\n"
                f"🕒 کات:\n{data.get('Time', 'N/A')}\n"
            )
        else:
            result_text = (
                "💰 زانیاریێن بکارهیةەرێن سەنتەرێ کورەکی:\n\n"
                f"📞 ژمارا موبایلێ:\n{data.get('MSISDN', 'N/A')}\n\n"
                f"🏦 کودێ خزمەتگوزاریێ:\n{data.get('SC', 'N/A')}\n\n"
                f"👤 ناڤێ ئاژانسی:\n{data.get('AgentName', 'N/A')}\n\n"
                f"📅 بەروار:\n{data.get('Date', 'N/A')}\n\n"
                f"🕒 دەم:\n{data.get('Time', 'N/A')}\n"
            )
    elif db_name == "qi-card":
        age = calculate_age(data.get('DOB', ''))
        if lang == "ku":
            result_text = (
                "💳 زانیاری کارتی قی:\n\n"
                f"👤 ناوی تەواو:\n{data.get('Full_Name', 'N/A')}\n\n"
                f"📞 ژمارەی تەلەفۆن:\n{data.get('Phone_Number', 'N/A')}\n\n"
                f"📅 بەرواری لەدایک بوون:\n{data.get('DOB', 'N/A')}\n\n"
                f"🎂 تەمەن:\n{age if age else 'N/A'}\n\n"
                f"📍 شوێنی لەدایک بوون:\n{data.get('Place_of_Birth', 'N/A')}\n\n"
                f"🏠 ناونیشان:\n{data.get('Address', 'N/A')}\n\n"
                f"🆔 ژمارەی ناسنامە:\n{hide_sensitive_info(data.get('Nationality_ID', 'N/A'))}\n\n"
                f"🍎 ژمارەی خۆراک:\n{data.get('Food_ID', 'N/A')}\n\n"
                f"👩 ناوی دایک:\n{data.get('Mothers_Name', 'N/A')}\n"
            )
        else:
            result_text = (
                "💳 زانیاریێن کارتا کی:\n\n"
                f"👤 ناڤ:\n{data.get('Full_Name', 'N/A')}\n\n"
                f"📞 ژمارا موبایلێ:\n{data.get('Phone_Number', 'N/A')}\n\n"
                f"📅 بەروارا ژدایکبینێ:\n{data.get('DOB', 'N/A')}\n\n"
                f"🎂 تەمەن:\n{age if age else 'N/A'}\n\n"
                f"📍 جهێ ژدایکبینێ:\n{data.get('Place_of_Birth', 'N/A')}\n\n"
                f"🏠 جهـ:\n{data.get('Address', 'N/A')}\n\n"
                f"🆔 ژمارا کارتا نیشتیمانی:\n{hide_sensitive_info(data.get('Nationality_ID', 'N/A'))}\n\n"
                f"🍎 ژمارا خارنێ:\n{data.get('Food_ID', 'N/A')}\n\n"
                f"👩 ناڤێ دەیکێ:\n{data.get('Mothers_Name', 'N/A')}\n"
            )
    elif db_name == "zain":
        if lang == "ku":
            result_text = (
                "📶 زانیاری زاین:\n\n"
                f"👤 ناوی تەواو:\n{data.get('Full_Name', 'N/A')}\n\n"
                f"📞 ژمارەی تەلەفۆن:\n{data.get('Phone_Number', 'N/A')}\n\n"
                f"🏙️ پارێزگا:\n{data.get('Gov', 'N/A')}\n"
            )
        else:
            result_text = (
                "📶 زانیاریێن زێن:\n\n"
                f"👤 ناڤ:\n{data.get('Full_Name', 'N/A')}\n\n"
                f"📞 ژمارa موبایلێ:\n{data.get('Phone_Number', 'N/A')}\n\n"
                f"🏙️ جهـ:\n{data.get('Gov', 'N/A')}\n"
            )
    
    return result_text

def format_asiacell_result(asiacell_data, lang):
    """Format Asiacell database result"""
    # Clean phone number - remove .0 if present
    phone = asiacell_data.get('phone', 'N/A')
    if phone != 'N/A' and isinstance(phone, str):
        # Remove trailing .0
        if phone.endswith('.0'):
            phone = phone[:-2]
    
    if lang == "ku":
        result_text = (
            "📱 زانیاری ئاسیاسێل:\n\n"
            f"👤 ناو:\n{asiacell_data.get('name', 'N/A')}\n\n"
            f"📞 ژمارەی تەلەفۆن:\n{phone}\n\n"
            f"📅 بەرواری لەدایک بوون:\n{asiacell_data.get('birth_date', 'N/A')}\n\n"
            f"🎂 تەمەن:\n{asiacell_data.get('age', 'N/A')}\n\n"
            f"🪪 ژمارەی کارتی ناسنامە:\n{hide_sensitive_info(asiacell_data.get('card_id', 'N/A'))}\n\n"
            f"🏙️ پارێزگا:\n{asiacell_data.get('province', 'N/A')}\n"
        )
    else:
        result_text = (
            "📱 زانیاریێن ئاسیا سێل:\n\n"
            f"👤 ناڤ:\n{asiacell_data.get('name', 'N/A')}\n\n"
            f"📞 ژمارا موبایلێ:\n{phone}\n\n"
            f"📅 بەروارا ژدایکبوونێ:\n{asiacell_data.get('birth_date', 'N/A')}\n\n"
            f"🎂 تەمەن:\n{asiacell_data.get('age', 'N/A')}\n\n"
            f"🪪 ژمارا کارتا نیشتیمانی:\n{hide_sensitive_info(asiacell_data.get('card_id', 'N/A'))}\n\n"
            f"🏙️ پارێزگەهـ:\n{asiacell_data.get('province', 'N/A')}\n"
        )
    
    return result_text

def format_truecaller_display(data, lang):
    """Format Truecaller data for display"""
    if not data:
        return "❌ هیچ زانیارییەک نەدۆزرایەوە لە Truecaller."
    
    truecaller_data = data.get("data", {})
    result_text = format_truecaller_result(truecaller_data)
    
    # Add disclaimer
    if lang == "ku":
        disclaimer = "\n\n══════\n"
        disclaimer += "🔴 هەر کارێک بێ ئەخلاق بکەیت ئەم نەبەرپرسیارین.\n"
        disclaimer += "📢 کەناڵ: @db_kurdistan\n"
        disclaimer += "══════"
    else:
        disclaimer = "\n\n══════\n"
        disclaimer += "🔴 بەرپرس نینن ژ هەر بێ ئەخلاقیەکا تو بکی.\n"
        disclaimer += "📢 کەناڵ: @db_kurdistan\n"
        disclaimer += "══════"
    
    result_text += disclaimer
    
    return result_text, data.get("image_path")

# Channel membership check
async def check_user_membership(user_id):
    """Check if user is member of required channel"""
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        logging.error(f"Error checking membership: {e}")
    return False

async def create_channel_join_button():
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
    username = message.from_user.username
    
    # Log user activity
    save_registered_user(user_id, username)
    log_user_activity(user_id, username, "start")
    
    # Clear any existing state
    user_states[user_id] = {}
    
    # Language selection keyboard
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="کوردی (بادینی)", callback_data="lang_en_UK"),
                InlineKeyboardButton(text="کوردی (سورانی)", callback_data="lang_ku")
            ]
        ]
    )
    
    await message.reply("🤖 All-in-One Search Bot\n\n📌 Please choose your language:", reply_markup=keyboard)

@router.message(Command("logout"))
async def logout_command(message: Message):
    """Handle /logout command for Truecaller"""
    user_id = message.from_user.id
    
    # Clear Truecaller login state
    if user_id in truecaller_login_states:
        del truecaller_login_states[user_id]
    
    # Remove token
    delete_truecaller_token(user_id)
    
    await message.reply(get_text(user_id, "logout"))

@router.callback_query(F.data.startswith("lang_"))
async def language_callback(callback: CallbackQuery):
    """Handle language selection"""
    user_id = callback.from_user.id
    lang = callback.data.replace("lang_", "")
    
    # Set user language
    user_languages[user_id] = lang
    
    # Check channel membership
    if not await check_user_membership(user_id):
        keyboard = await create_channel_join_button()
        await callback.message.edit_text(
            get_text(user_id, "join_channel"),
            reply_markup=keyboard
        )
        await callback.answer()
        return
    
    # Show search type selection
    texts = TEXTS.get(lang, TEXTS["ku"])
    
    # Check if user has Truecaller token
    has_truecaller = user_id in truecaller_tokens
    
    keyboard_buttons = [
        [
            InlineKeyboardButton(text=texts["search_types"]["name"], callback_data="search_name"),
            InlineKeyboardButton(text=texts["search_types"]["phone"], callback_data="search_phone")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["age"], callback_data="search_age"),
            InlineKeyboardButton(text=texts["search_types"]["date_of_birth"], callback_data="search_date_of_birth")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["passport"], callback_data="search_passport"),
            InlineKeyboardButton(text=texts["search_types"]["vaccine_date"], callback_data="search_vaccine_date")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["facebook_id"], callback_data="search_facebook_id"),
            InlineKeyboardButton(text=texts["search_types"]["facebook_username"], callback_data="search_facebook_username")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["full_search"], callback_data="search_full")
        ]
    ]
    
    # Add Truecaller button with login status
    truecaller_text = texts["search_types"]["truecaller"]
    if has_truecaller or active_truecaller_tokens:
        truecaller_text += " ✅"
    else:
        truecaller_text += " 🔒"
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=truecaller_text, callback_data="search_truecaller")
    ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=texts["bot_info"], callback_data="bot_info")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(texts["welcome"], reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "bot_info")
async def bot_info_callback(callback: CallbackQuery):
    """Show bot information"""
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ku")
    
    if lang == "ku":
        info_text = (
            "🤖 زانیاری بۆت:\n\n"
            "• ناو: گەڕانکاری هەموو داتابەیسەکان\n"
            "• دروستکراو: کوردو\n"
            "• کار: گەڕان لە هەموو داتابەیسەکاندا بۆ دۆزینەوەی کەس\n"
            "• جۆرەکانی گەڕان: ناو، ژمارەی تەلەفۆن، تەمەن، بەرواری لەدایک بوون، ناسنامە، بەرواری ڤاکسین\n\n"
            "📢 کەناڵ: @db_kurdistan\n"
            "✅ Truecaller: چالاکە"
        )
    else:
        info_text = (
            "🤖 زانیاریێن بوتی:\n\n"
            "• ناڤ: لێگەریان ل هەمی داتابیسا\n"
            "• دروستکرن ژلایێ: کوردو\n"
            "• کار: لێگەریان ل هەمی داتابیسا بو دیتنا کەسێ مەبەست پێ\n"
            "• جورێن لێگەریانێ : ناڤ، ژمارا موبایلێ، تەمەن، بەروارا ژدایکبوونێ، ناسنامە، بەروارا ڤاکسینێ\n\n"
            "📢 کەناڵ: @db_kurdistan\n"
            "✅ Truecaller: چالاکە"
        )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="back_to_search")
        ]]
    )
    
    await callback.message.edit_text(info_text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "back_to_search")
async def back_to_search_callback(callback: CallbackQuery):
    """Return to search menu"""
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ku")
    texts = TEXTS.get(lang, TEXTS["ku"])
    
    # Check if user has Truecaller token or active tokens exist
    has_truecaller = (user_id in truecaller_tokens) or active_truecaller_tokens
    
    keyboard_buttons = [
        [
            InlineKeyboardButton(text=texts["search_types"]["name"], callback_data="search_name"),
            InlineKeyboardButton(text=texts["search_types"]["phone"], callback_data="search_phone")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["age"], callback_data="search_age"),
            InlineKeyboardButton(text=texts["search_types"]["date_of_birth"], callback_data="search_date_of_birth")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["passport"], callback_data="search_passport"),
            InlineKeyboardButton(text=texts["search_types"]["vaccine_date"], callback_data="search_vaccine_date")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["facebook_id"], callback_data="search_facebook_id"),
            InlineKeyboardButton(text=texts["search_types"]["facebook_username"], callback_data="search_facebook_username")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["full_search"], callback_data="search_full")
        ]
    ]
    
    # Add Truecaller button with login status
    truecaller_text = texts["search_types"]["truecaller"]
    if has_truecaller:
        truecaller_text += " ✅"
    else:
        truecaller_text += " 🔒"
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=truecaller_text, callback_data="search_truecaller")
    ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=texts["bot_info"], callback_data="bot_info")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(texts["welcome"], reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("search_"))
async def search_type_callback(callback: CallbackQuery):
    """Handle search type selection"""
    user_id = callback.from_user.id
    search_type = callback.data.replace("search_", "")
    
    # Check if it's Truecaller and no active tokens available
    if search_type == "truecaller" and not active_truecaller_tokens and user_id not in truecaller_tokens:
        # Show Truecaller login instructions
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📲 Truecaller (Android)", url="https://play.google.com/store/apps/details?id=com.truecaller"),
                    InlineKeyboardButton(text="📱 Truecaller (iOS)", url="https://apps.apple.com/app/truecaller/id448142450")
                ],
                [
                    InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="back_to_search")
                ]
            ]
        )
        
        await callback.message.edit_text(get_text(user_id, "truecaller_login"), reply_markup=keyboard)
        await callback.answer()
        return
    
    # Store search type
    user_states[user_id] = {"search_type": search_type}
    
    # Get instructions based on search type
    instructions_key = search_type if search_type != "full" else "full"
    if instructions_key in get_text(user_id, "instructions"):
        instructions = get_text(user_id, "instructions")[instructions_key]
    else:
        instructions = get_text(user_id, "instructions")["full"]
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="back_to_search")
        ]]
    )
    
    await callback.message.edit_text(instructions, reply_markup=keyboard)
    await callback.answer()

@router.message()
async def handle_search_query(message: Message):
    """Handle search queries"""
    user_id = message.from_user.id
    username = message.from_user.username
    search_term = message.text.strip()
    
    # Log user activity
    log_user_activity(user_id, username, "search_query")
    
    # Check if user has active search
    if user_id in active_searches:
        await message.reply(get_text(user_id, "processing"))
        return
    
    # Check channel membership first
    if not await check_user_membership(user_id):
        keyboard = await create_channel_join_button()
        await message.reply(get_text(user_id, "join_channel"), reply_markup=keyboard)
        return
    
    # Check if user is in Truecaller login flow
    if user_id in truecaller_login_states:
        state = truecaller_login_states[user_id]
        
        if 'sessionId' in state and len(search_term) == 6:
            # This is OTP code
            await handle_truecaller_otp(message, search_term, user_id)
            return
        elif 'sessionId' not in state:
            # This is phone number for login
            await handle_truecaller_login_phone(message, search_term, user_id)
            return
    
    # Get search type from user state
    user_state = user_states.get(user_id, {})
    search_type = user_state.get("search_type")
    
    if not search_type:
        # If no search type selected, ask to use /start
        await message.reply("⚠️ Please use /start to select search type first")
        return
    
    # Special handling for Truecaller
    if search_type == "truecaller":
        await handle_truecaller_search(message, search_term, user_id)
        return
    
    # Start search for other databases
    search_msg = await message.reply(get_text(user_id, "searching"))
    
    # Perform search
    all_results = await search_all_databases(search_term, search_type, user_id, search_msg)
    
    # Store results
    search_results[user_id] = {
        "results": all_results,
        "search_term": search_term,
        "search_type": search_type
    }
    
    # Count total results
    total_results = sum(len(results) for results in all_results.values())
    
    # Log the search
    log_search(user_id, username, search_type, search_term, total_results)
    
    if total_results == 0:
        await search_msg.edit_text(get_text(user_id, "no_results"))
        return
    
    # Show summary of found results
    summary_text = get_text(user_id, "found", total=total_results)
    
    for db_name, results in all_results.items():
        if results:
            summary_text += f"\n• {DATABASES[db_name]['name']}: {len(results)} کەس"
    
    # Create database selection keyboard with pagination for databases with many results
    keyboard_buttons = []
    for db_name, results in all_results.items():
        if results:
            db_display_name = DATABASES[db_name]['name']
            count = len(results)
            
            if count <= ITEMS_PER_PAGE:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{db_display_name} ({count})", 
                        callback_data=f"view_db_{db_name}_0"
                    )
                ])
            else:
                # Show with page indication
                total_pages = (count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{db_display_name} ({count}) - پەڕەی 1", 
                        callback_data=f"view_db_{db_name}_0"
                    )
                ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="back_to_search")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await search_msg.edit_text(summary_text, reply_markup=keyboard)

async def handle_truecaller_login_phone(message: Message, phone_text: str, user_id: int):
    """Handle Truecaller login phone number"""
    # Normalize phone number
    def normalize_number(text):
        if ' ' in text:
            return None
        number = text.strip().replace('+', '')
        if number.startswith('0'):
            number = '964' + number[1:]
        elif number.startswith('964'):
            pass
        elif number.startswith('7') and len(number) == 10:
            number = '964' + number
        else:
            return None
        return number if number[3:].isdigit() else None
    
    phone = normalize_number(phone_text)
    if not phone:
        await message.reply("❌ Jimara xalata hevya wake vana freka:\n07502326670 yan +9647502326670")
        return
    
    # Send OTP request
    data = {"phone": int(phone), "countryCode": "iq"}
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.truecaller.com",
        "Referer": "https://www.truecaller.com"
    }
    
    try:
        response = requests.post(TRUECALLER_SEND_OTP, json=data, headers=headers, timeout=30)
        if response.status_code == 200 and 'sessionId' in response.json():
            truecaller_login_states[user_id] = {
                'sessionId': response.json()['sessionId'],
                'phone': phone
            }
            await message.reply(get_text(user_id, "truecaller_otp"))
        elif response.status_code == 429:
            await message.reply("❌ Galak daxaze hatna krn, hevya dobara hawlbda.")
        else:
            await message.reply("❌ Nashen OTP frekayn, hevya to pshtrast be to l app daxlkrbet peshtr.")
    except Exception as e:
        logging.error(f"Truecaller OTP request failed: {e}")
        await message.reply("❌ Areshayak ya hay dgal server, hevya dobara bhnera.")

async def handle_truecaller_otp(message: Message, otp_code: str, user_id: int):
    """Handle Truecaller OTP verification"""
    state = truecaller_login_states[user_id]
    data = {
        "sessionId": state['sessionId'],
        "verificationCode": otp_code,
        "phone": int(state['phone']),
        "countryCode": "iq"
    }
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.truecaller.com",
        "Referer": "https://www.truecaller.com"
    }
    
    try:
        response = requests.post(TRUECALLER_VERIFY_OTP, json=data, headers=headers, timeout=30)
        if response.status_code == 200 and 'accessToken' in response.json():
            token = response.json()['accessToken']
            save_truecaller_token(user_id, token)
            
            # Clear login state
            del truecaller_login_states[user_id]
            
            await message.reply(get_text(user_id, "truecaller_success"))
            
            # Return to search menu
            await back_to_search_after_login(message, user_id)
        else:
            await message.reply("❌ xalata OTP, hevya dobara freka, yan /start dobara bka.")
    except Exception as e:
        logging.error(f"Truecaller OTP verification failed: {e}")
        await message.reply("❌ Areshayak ya hay dgal server, hevya dobara hawl bda")

async def back_to_search_after_login(message: Message, user_id: int):
    """Return to search menu after successful login"""
    lang = user_languages.get(user_id, "ku")
    texts = TEXTS.get(lang, TEXTS["ku"])
    
    # Check if user has Truecaller token or active tokens exist
    has_truecaller = (user_id in truecaller_tokens) or active_truecaller_tokens
    
    keyboard_buttons = [
        [
            InlineKeyboardButton(text=texts["search_types"]["name"], callback_data="search_name"),
            InlineKeyboardButton(text=texts["search_types"]["phone"], callback_data="search_phone")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["age"], callback_data="search_age"),
            InlineKeyboardButton(text=texts["search_types"]["date_of_birth"], callback_data="search_date_of_birth")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["passport"], callback_data="search_passport"),
            InlineKeyboardButton(text=texts["search_types"]["vaccine_date"], callback_data="search_vaccine_date")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["facebook_id"], callback_data="search_facebook_id"),
            InlineKeyboardButton(text=texts["search_types"]["facebook_username"], callback_data="search_facebook_username")
        ],
        [
            InlineKeyboardButton(text=texts["search_types"]["full_search"], callback_data="search_full")
        ]
    ]
    
    # Add Truecaller button with login status
    truecaller_text = texts["search_types"]["truecaller"]
    if has_truecaller:
        truecaller_text += " ✅"
    else:
        truecaller_text += " 🔒"
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=truecaller_text, callback_data="search_truecaller")
    ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=texts["bot_info"], callback_data="bot_info")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(texts["welcome"], reply_markup=keyboard)

async def handle_truecaller_search(message: Message, search_term: str, user_id: int):
    """Handle Truecaller search"""
    # Mark user as searching
    active_searches.add(user_id)
    
    search_msg = await message.reply("⏳ Truecaller لێگەریان...")
    
    try:
        # Search using Truecaller
        results = await search_truecaller(search_term)
        
        # Clear active search
        if user_id in active_searches:
            active_searches.remove(user_id)
        
        if not results:
            await search_msg.edit_text("❌ هیچ زانیارییەک نەهاتە دیتن د Truecaller.")
            return
        
        # Get Truecaller data
        truecaller_data = results[0]
        image_path = truecaller_data.get("image_path")
        
        # Format result
        result_text = format_truecaller_display(truecaller_data, user_languages.get(user_id, "ku"))
        
        if isinstance(result_text, tuple):
            result_text, _ = result_text
        
        # Add phone number for links
        phone_number = clean_lookup_number(search_term)
        if phone_number:
            intl_number = "+964" + phone_number
            links = (
                f"\n\n🔸 Telegram: https://t.me/{intl_number}\n"
                f"🔸 WhatsApp: https://wa.me/{intl_number}"
            )
            result_text += links
        
        # Send result with image if available
        if image_path and os.path.exists(image_path):
            try:
                photo = FSInputFile(image_path)
                # Truncate text if too long for caption
                caption = result_text[:1000] + "..." if len(result_text) > 1000 else result_text
                
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    caption=caption
                )
                
                # Send remaining text if truncated
                if len(result_text) > 1000:
                    remaining = result_text[1000:]
                    chunks = [remaining[i:i+4000] for i in range(0, len(remaining), 4000)]
                    for chunk in chunks:
                        await message.answer(chunk)
                
                await search_msg.delete()
                
                # Clean up temp file
                try:
                    os.unlink(image_path)
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"Error sending photo: {e}")
                # Fall back to text only
                await search_msg.edit_text(result_text)
        else:
            await search_msg.edit_text(result_text)
            
    except Exception as e:
        logging.error(f"Truecaller search failed: {e}")
        await search_msg.edit_text("❌ خەلەتیەک ژ Truecaller.")
        
        # Clear active search
        if user_id in active_searches:
            active_searches.remove(user_id)

@router.callback_query(F.data.startswith("view_db_"))
async def view_database_results(callback: CallbackQuery):
    """View results from a specific database with pagination"""
    user_id = callback.from_user.id
    
    # Parse callback data
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Error in data")
        return
    
    db_name = parts[2]
    page = int(parts[3])
    
    # Get user's search results
    user_results = search_results.get(user_id, {})
    all_db_results = user_results.get("results", {})
    results = all_db_results.get(db_name, [])
    
    if not results:
        await callback.answer("❌ No results")
        return
    
    # Calculate pagination
    total_pages = (len(results) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(results))
    
    # Create result list
    result_text = f"📋 {DATABASES[db_name]['name']} (پەڕەی {page + 1}/{total_pages}):\n\n"
    
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
            age = result.get('age', '')
            age_text = f" - 🎂{age}" if age else ""
            result_text += f"{item_num}. {name}{age_text}\n"
        
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
                phone = data.get('Phone_Number', 'N/A')
                result_text += f"{item_num}. {name[:30]}... - 📞{phone}\n"
            elif db_name == "zain":
                name = data.get('Full_Name', 'N/A')
                phone = data.get('Phone_Number', 'N/A')
                result_text += f"{item_num}. {name[:30]}... - 📞{phone}\n"
        
        elif db_name == "kurdistan-lawyers":
            name = result.get('name', 'N/A')
            phone = result.get('phone', 'N/A')
            result_text += f"{item_num}. {name} - 📞{phone}\n"
        
        elif db_name == "asiacell":
            name = result.get('name', 'N/A')
            phone = result.get('phone', 'N/A')
            result_text += f"{item_num}. {name} - 📞{phone}\n"
    
    result_text += f"\n📊 کۆی گشتی: {len(results)} کەس"
    
    # Create pagination keyboard
    keyboard_buttons = []
    
    # Add result selection buttons - only for current page
    for i, result in enumerate(results[start_idx:end_idx], start=1):
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"👁️ بینینا کەسێ {start_idx + i}", 
                callback_data=f"view_item_{db_name}_{start_idx + i - 1}"
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
        await callback.message.edit_text(result_text, reply_markup=keyboard)
    except Exception as e:
        # If message is too long, send as new message
        if "message is too long" in str(e):
            await callback.message.delete()
            await callback.message.answer(result_text[:4000], reply_markup=keyboard)
    
    await callback.answer()

@router.callback_query(F.data == "back_to_results")
async def back_to_results(callback: CallbackQuery):
    """Go back to database selection"""
    user_id = callback.from_user.id
    
    # Get user's search results
    user_results = search_results.get(user_id, {})
    all_db_results = user_results.get("results", {})
    search_term = user_results.get("search_term", "")
    search_type = user_results.get("search_type", "")
    
    # Count total results
    total_results = sum(len(results) for results in all_db_results.values())
    
    if total_results == 0:
        await callback.answer("❌ هیچ ئەنژامەک نەهاتە دیتن")
        return
    
    # Show summary
    summary_text = get_text(user_id, "found", total=total_results)
    
    for db_name, results in all_db_results.items():
        if results:
            summary_text += f"\n• {DATABASES[db_name]['name']}: {len(results)} کەس"
    
    # Create database selection keyboard
    keyboard_buttons = []
    for db_name, results in all_db_results.items():
        if results:
            db_display_name = DATABASES[db_name]['name']
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{db_display_name} ({len(results)})", 
                    callback_data=f"view_db_{db_name}_0"
                )
            ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="back_to_search")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(summary_text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("view_item_"))
async def view_item_details(callback: CallbackQuery):
    """View detailed information about a specific item"""
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, "ku")
    
    # Parse callback data
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ خەلەتیەک ژ داتایا")
        return
    
    db_name = parts[2]
    index = int(parts[3])
    
    # Get user's search results
    user_results = search_results.get(user_id, {})
    all_db_results = user_results.get("results", {})
    results = all_db_results.get(db_name, [])
    
    if index >= len(results):
        await callback.answer("❌ ئەڤ پارچە نەهاتە دیتن")
        return
    
    item = results[index]
    
    # Format result based on database type
    if db_name == "iraq-facebook":
        result_text = format_facebook_result(item, lang)
    
    elif db_name == "kurdistan-health":
        result_text = format_health_result(item, lang)
    
    elif db_name == "aman":
        result_text = format_aman_result(item, lang)
    
    elif db_name in ["loan-korektel", "qi-card", "zain"]:
        result_text = format_json_result(item, db_name, lang)
    
    elif db_name == "kurdistan-lawyers":
        result_text, image_path = format_lawyer_result(item, lang)
        
        # Send message with image if available
        if image_path and os.path.exists(image_path):
            try:
                # Send photo with caption (truncated if too long)
                photo = FSInputFile(image_path)
                caption = result_text[:1000] if len(result_text) > 1000 else result_text
                await bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=photo,
                    caption=caption
                )
                
                # Send the rest of the text if it was truncated
                if len(result_text) > 1000:
                    remaining_text = result_text[1000:]
                    chunks = [remaining_text[i:i+4000] for i in range(0, len(remaining_text), 4000)]
                    for chunk in chunks:
                        await callback.message.answer(chunk)
                
                # Add back button
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(text=get_text(user_id, "back"), callback_data=f"view_db_{db_name}_0")
                    ]]
                )
                await callback.message.answer("⬆️ وێنە هاوار کرا ⬆️", reply_markup=keyboard)
                await callback.answer()
                return
            except Exception as e:
                logging.error(f"Error sending photo: {e}")
                result_text += f"\n❌ نەتوانرا وێنە بنێرێ: {str(e)}"
        else:
            if lang == "ku":
                result_text += "\n📷 وێنە بەردەست نییە"
            else:
                result_text += "\n📷 وێنە بەردەست نینە"
    
    elif db_name == "asiacell":
        result_text = format_asiacell_result(item, lang)
    
    else:
        if lang == "ku":
            result_text = "❌ فۆرماتێکی نەناسراو"
        else:
            result_text = "❌ فورماتەک نەزانراو"
    
    # Add disclaimer
    if lang == "ku":
        disclaimer = "\n\n══════\n"
        disclaimer += "🔴 هەر کارێک بێ ئەخلاق بکەیت ئەم نەبەرپرسیارین.\n"
        disclaimer += "📢 کەناڵ: @db_kurdistan\n"
        disclaimer += "══════"
    else:
        disclaimer = "\n\n══════\n"
        disclaimer += "🔴 بەرپرس نینن ژ هەر بێ ئەخلاقیەکا تو بکی.\n"
        disclaimer += "📢 کەناڵ: @db_kurdistan\n"
        disclaimer += "══════"
    
    result_text += disclaimer
    
    # Split long messages
    if len(result_text) > 4000:
        # Send in chunks
        chunks = [result_text[i:i+4000] for i in range(0, len(result_text), 4000)]
        
        # Send all chunks except last one
        for chunk in chunks[:-1]:
            await callback.message.answer(chunk)
        
        # Last chunk with back button
        last_chunk = chunks[-1]
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text=get_text(user_id, "back"), callback_data=f"view_db_{db_name}_0")
            ]]
        )
        await callback.message.answer(last_chunk, reply_markup=keyboard)
    else:
        # Send single message with back button
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text=get_text(user_id, "back"), callback_data=f"view_db_{db_name}_0")
            ]]
        )
        await callback.message.edit_text(result_text, reply_markup=keyboard)
    
    await callback.answer()

@router.callback_query(F.data == "noop")
async def no_operation(callback: CallbackQuery):
    """Handle no-operation callback"""
    await callback.answer()

async def periodic_token_check():
    """Periodically check and update token validity"""
    while True:
        try:
            logger.info("Checking Truecaller token validity...")
            load_truecaller_tokens()  # Reload and check tokens
            logger.info(f"Active tokens: {len(active_truecaller_tokens)}")
        except Exception as e:
            logger.error(f"Error in periodic token check: {e}")
        
        # Check every 30 minutes
        await asyncio.sleep(1800)

async def main():
    """Main function to start the bot"""
    # Load registered users
    load_registered_users()
    
    # Load and check Truecaller tokens
    load_truecaller_tokens()
    logger.info(f"Loaded {len(active_truecaller_tokens)} active Truecaller tokens")
    
    # Start periodic token check
    asyncio.create_task(periodic_token_check())
    
    logging.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
