
from pytz import utc
import os
import csv
import requests
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, ApplicationBuilder

# Configuration
BOT_TOKEN = "8104952238:AAED6UvpqWUkgHb3pJfzXCpTyswZNLoQtPQ"
REQUIRED_CHANNEL = "@db_kurdistan"
TRUECALLER_SEND_OTP = "https://asia-south1-truecaller-web.cloudfunctions.net/webapi/noneu/auth/truecaller/v1/send-otp"
TRUECALLER_VERIFY_OTP = "https://asia-south1-truecaller-web.cloudfunctions.net/webapi/noneu/auth/truecaller/v1/verify-otp"
TRUECALLER_API_URL = "https://asia-south1-truecaller-web.cloudfunctions.net/webapi/noneu/search/v2"
AUTH_FILE = "auth_tokens.csv"
HISTORY_FILE = "lookup_history.csv"

# Initialize application
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store login states in memory
login_states = {}

class TruecallerBot:
    def __init__(self):
        self.setup_files()
        
    def setup_files(self):
        # Create auth file if doesn't exist
        if not os.path.exists(AUTH_FILE):
            with open(AUTH_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['user_id', 'access_token', 'login_time'])
        
        # Create history file if doesn't exist
        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'chat_id', 'user_id', 'username', 
                    'phone_number', 'result_name', 'result_carrier'
                ])
    
    def get_user_token(self, user_id):
        """Retrieve user's token from CSV file"""
        if not os.path.exists(AUTH_FILE):
            return None
            
        with open(AUTH_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['user_id'] == str(user_id):
                    return row['access_token']
        return None
    
    def save_user_token(self, user_id, token):
        """Save user's token to CSV file"""
        # Remove existing entry if exists
        rows = []
        if os.path.exists(AUTH_FILE):
            with open(AUTH_FILE, 'r', newline='') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    if row['user_id'] != str(user_id):
                        rows.append(row)
        
        # Add new token
        rows.append({
            'user_id': user_id,
            'access_token': token,
            'login_time': datetime.now().isoformat()
        })
        
        # Write back to file
        with open(AUTH_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    
    def delete_user_token(self, user_id):
        """Remove user's token from CSV file"""
        if not os.path.exists(AUTH_FILE):
            return
            
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

    def log_history(self, update, phone_number, result):
        """Log lookup history to CSV"""
        with open(HISTORY_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                update.effective_chat.id,
                update.effective_user.id,
                update.effective_user.username or "",
                phone_number,
                result.get('name', ''),
                result.get('carrier', '')
            ])

    async def create_channel_join_button(self):
        """Create inline button for channel join"""
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="📢 کلیک بکە و بەژداربە", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")]]
        )

    async def check_user_membership(self, user_id, context):
        """Check if user is member of required channel"""
        try:
            member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
            return member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            logger.error(f"Error checking membership: {str(e)}")
            return False

    def normalize_number(self, text):
        """Normalize phone number for lookup"""
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

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        
        # Check channel membership
        if not await self.check_user_membership(user_id, context):
            keyboard = await self.create_channel_join_button()
            await update.message.reply_text(
                "🔴 دڤێت تو بەژداری کەناڵی ببی تاکو بشێی بوتی بکاربینی.",
                reply_markup=keyboard
            )
            return
        
        # Check if user already logged in
        token = self.get_user_token(user_id)
        if token:
            welcome_msg = (
                "🌟 Bxer hate, to bare noka ye choy d jorva!\n\n"
                "Agar ta dvet accounte xwa ldaf ma jebbe, hevya ve commande click bka /logout\n"
                "📱 Jmara mobile freka bw legaryane, wak:\n"
                "07504567444 yan +9647504567444\n\n"
                "⏳ Hevya galak jmara na freka chonke de band be.."
            )
            await update.message.reply_text(welcome_msg)
            return
        
        # New user flow
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📲 Truecaller (Android)", url="https://play.google.com/store/apps/details?id=com.truecaller")],
            [InlineKeyboardButton("📱 Truecaller (iOS)", url="https://apps.apple.com/app/truecaller/id448142450")]
        ])
        await update.message.reply_text(
            "📥 Hevya to daspeke bche barname TrueCaller o Login kay, lsar ek j systemen Iphone yan Android. \n\n"
            "📞 Pshte hnge aw jmara ta login kre boma freka (Wak: 07501231234 yan +9647501231234).", 
            reply_markup=keyboard
        )
        login_states[user_id] = {'start_time': datetime.now().isoformat()}

    async def logout_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /logout command"""
        user_id = update.effective_user.id
        
        # Clear login state
        if user_id in login_states:
            del login_states[user_id]
        
        # Remove token from file
        self.delete_user_token(user_id)
        
        await update.message.reply_text("🚪 B sarkaftyana to choy jdarva, bo dobara login bone /start click bka")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all incoming messages"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        # Check channel membership first
        if not await self.check_user_membership(user_id, context):
            keyboard = await self.create_channel_join_button()
            await update.message.reply_text(
                "🔴 دڤێت تو بەژداری کەناڵی ببی تاکو بشێی بوتی بکاربینی.",
                reply_markup=keyboard
            )
            return
        
        # Check if user has active token
        user_token = self.get_user_token(user_id)
        
        # Handle OTP code input
        if user_id in login_states and 'sessionId' in login_states[user_id] and len(text) == 6:
            await self.handle_otp(update, text, user_id)
            return
        
        # Handle phone number input for login
        if user_id in login_states and 'sessionId' not in login_states[user_id]:
            await self.handle_login_phone(update, text, user_id)
            return
        
        # Handle phone number lookup
        if user_token:
            await self.handle_phone_lookup(update, text, user_token)
            return
        
        # If no active session, prompt to start
        await update.message.reply_text("🛑 Hevya daspeke /start click bka bw bajdar bene.")

    async def handle_otp(self, update, otp_code, user_id):
        """Verify OTP and complete login"""
        state = login_states[user_id]
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
            response = requests.post(TRUECALLER_VERIFY_OTP, json=data, headers=headers)
            if response.status_code == 200 and 'accessToken' in response.json():
                token = response.json()['accessToken']
                self.save_user_token(user_id, token)
                state['accessToken'] = token
                state['login_time'] = datetime.now().isoformat()
                await update.message.reply_text("✅ B sarkaftyana to bajdar boy, hevya we hajmare freka ya ta dvet zanyaryet we bbene...")
            else:
                await update.message.reply_text("❌ xalata OTP, hevya dobara freka, yan /start dobara bka.")
        except Exception as e:
            logger.error(f"OTP verification failed: {str(e)}")
            await update.message.reply_text("❌ Areshayak ya hay dgal server, hevya dobara hawl bda")

    async def handle_login_phone(self, update, phone_text, user_id):
        """Send OTP to user's phone"""
        phone = self.normalize_number(phone_text)
        if not phone:
            await update.message.reply_text("❌ Jimara xalata hevya wake vana freka:\n07502326670 yan +9647502326670")
            return
        
        data = {"phone": int(phone), "countryCode": "iq"}
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://www.truecaller.com",
            "Referer": "https://www.truecaller.com"
        }
        
        try:
            response = requests.post(TRUECALLER_SEND_OTP, json=data, headers=headers)
            if response.status_code == 200 and 'sessionId' in response.json():
                login_states[user_id]['sessionId'] = response.json()['sessionId']
                login_states[user_id]['phone'] = phone
                await update.message.reply_text("📨 Awe Code freka ye b OTP bota hate, lsar TrueCaller.")
            elif response.status_code == 429:
                await update.message.reply_text("❌ Galak daxaze hatna krn, hevya dobara hawlbda.")
            else:
                await update.message.reply_text("❌ Nashen OTP frekayn, hevya to pshtrast be to l app daxlkrbet peshtr.")
        except Exception as e:
            logger.error(f"OTP request failed: {str(e)}")
            await update.message.reply_text("❌ Areshayak ya hay dgal server, hevya dobara bhnera.")

    def clean_lookup_number(self, text):
        """Clean and validate phone number for lookup"""
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

    async def handle_phone_lookup(self, update, phone_text, access_token):
        """Perform Truecaller lookup"""
        phone_number = self.clean_lookup_number(phone_text)
        if not phone_number:
            await update.message.reply_text(
                "❌ Jimara xalata, hevya wak avan nmona freka:\n"
                "07504039444\n+9647504039444\n9647504039444\n"
                ""
            )
            return
        
        # Send waiting message
        wait_msg = await update.message.reply_text("⏳ خوە پچەکێ بگرە...")
        
        try:
            # Perform lookup
            result = self.lookup_number(phone_number, access_token)
            # Download image if available
            image_data = None
            image_url = result.get('image')
            if image_url:
                image_data = self.download_image(image_url, access_token)
    
    # Try alternative URL patterns if first fails
                if not image_data:
        # Try different URL formats
                    for pattern in ['/myview/', '/profile/']:
                        if pattern in image_url:
                            new_url = image_url.replace(pattern, '/')
                            image_data = self.download_image(new_url, access_token)
                            if image_data:
                                break
            
            # Log history
            self.log_history(update, phone_number, result)
            
            # Format result
            formatted_result = self.format_result(result)
            
            # Generate WhatsApp/Telegram links
            intl_number = "+964" + phone_number
            links = (
                f"\n\n🔸 Telegram: https://t.me/{intl_number}\n"
                f"🔸 WhatsApp: https://wa.me/{intl_number}\n\n"
                f"کورد ساتانیزم بەرپرس نینە ژ هەر بێ ئەخلاقیەکا تو بکەی....!"
            )
            
            # Send result
            await wait_msg.delete()
            
            if image_data:
                await update.message.reply_photo(
                    photo=image_data,
                    caption=formatted_result + links
                )
            else:
                await update.message.reply_text(formatted_result + links)
                
        except Exception as e:
            logger.error(f"Lookup failed: {str(e)}")
            await update.message.reply_text(
                "❌ Xalatyak chebe, hevya dobara frekava.\n"
                "Nmona: 075041231234 yan +9647501231234"
            )

    def download_image(self, image_url, access_token):
        """Download image using full browser simulation"""
        try:
            # Create a persistent session
            session = requests.Session()
        
        # Set headers to simulate a real browser
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
                "Accept": "image/webp,*/*",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Referer": "https://www.truecaller.com/",
                "Origin": "https://www.truecaller.com",
                    "Sec-Fetch-Dest": "image",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "cross-site",
                "Authorization": f"Bearer {access_token}"
            })
        
        # Add cookies that Truecaller might expect
            session.cookies.set("tc_session", "valid-session", domain=".truecallerstatic.com")
            session.cookies.set("country", "iq", domain=".truecaller.com")
        
        # Download image
            response = session.get(image_url, timeout=10)
            response.raise_for_status()
        
        # Verify image content
            if response.headers.get('Content-Type', '').startswith('image/'):
                return response.content
            
            logger.error(f"Non-image response: {response.headers.get('Content-Type')}")
            return None
        
        except Exception as e:
            logger.error(f"Image download failed: {str(e)}")
            return None

    def lookup_number(self, phone_number, access_token):
        """Call Truecaller API for number lookup"""
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "*/*",
            "Authorization": f"Bearer {access_token}",
            "Referer": "https://www.truecaller.com/",
            "Origin": "https://www.truecaller.com"
        }

        params = {
            "q": phone_number,
            "countryCode": "iq",
            "type": "44"
        }

        try:
                response = requests.get(TRUECALLER_API_URL, headers=headers, params=params)
        
                if response.status_code == 401:
                    raise Exception("Token expired")
        
                response.raise_for_status()
                return response.json()
        except Exception as e:
                logger.error(f"Lookup failed: {str(e)}")
                return {}

    def format_result(self, data):
        """Format Truecaller API response"""
        if not data:
            return "❌ Hech zanyare nahatna detn bo ve jimare."
        
        result = []
        ltr = "\u200E"
        
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
                result.append(f"  • Bajer: {address.get('city'
