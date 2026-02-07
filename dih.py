import asyncio
import os
import json
import time
import random
import logging
import signal
import sys
from datetime import datetime
import sqlite3
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.types import MessageMediaDocument

# ================================
# CONFIGURATION
# ================================
API_ID = 33762356
API_HASH = "2adcdcf539051eec6795ac7476ad45e7"
PHONE = "+9647515362746"

# Use a unique session file for this script
SESSION_FILE = "download_only.session"
ULP_CHANNEL_ID = -1003331150619
DOWNLOAD_DIR = "ulp_raw_downloads"
STATE_FILE = "download_state.json"

# Message ID range
START_MESSAGE_ID = 4
END_MESSAGE_ID = 781

# Download settings
MAX_CONCURRENT_DOWNLOADS = 3
DOWNLOAD_DELAY = 1
MAX_RETRIES = 5
BATCH_SIZE = 50

# ================================
# LOGGING SETUP (nohup compatible)
# ================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Also log to file for nohup
file_handler = logging.FileHandler('downloader.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# ================================
# SESSION LOCK MANAGER
# ================================
def cleanup_old_session_locks():
    """Clean up old session locks before starting"""
    session_files = [
        SESSION_FILE,
        SESSION_FILE + '-journal',
        SESSION_FILE + '-wal',
        SESSION_FILE + '-shm'
    ]
    
    for session_file in session_files:
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                logger.info(f"Cleaned up old session file: {session_file}")
            except Exception as e:
                logger.warning(f"Could not clean up {session_file}: {e}")

def wait_for_session_unlock(timeout=30):
    """Wait if session file is locked by another process"""
    import time as ttime
    
    start_time = ttime.time()
    session_path = Path(SESSION_FILE)
    
    while ttime.time() - start_time < timeout:
        try:
            # Try to open the SQLite database exclusively
            conn = sqlite3.connect(SESSION_FILE, timeout=1.0)
            conn.close()
            logger.info("Session file is unlocked, proceeding...")
            return True
        except sqlite3.OperationalError as e:
            if "locked" in str(e) or "database is locked" in str(e):
                logger.warning(f"Session file is locked, waiting... ({int(ttime.time() - start_time)}s)")
                ttime.sleep(2)
            else:
                # Different error, might not exist yet
                return True
    
    logger.error("Session file still locked after timeout")
    return False

# ================================
# SIMPLE STATE MANAGER
# ================================
class SimpleState:
    def __init__(self):
        self.state_file = STATE_FILE
        self.state = self.load_state()
    
    def load_state(self):
        default_state = {
            "last_downloaded_id": START_MESSAGE_ID - 1,
            "downloaded_ids": [],
            "failed_ids": [],
            "start_time": time.time(),
            "last_run": None
        }
        
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    
                    # Validate state
                    if not isinstance(state.get("downloaded_ids"), list):
                        state["downloaded_ids"] = []
                    if not isinstance(state.get("failed_ids"), list):
                        state["failed_ids"] = []
                    
                    # Ensure last_downloaded_id is within range
                    last_id = state.get("last_downloaded_id", START_MESSAGE_ID - 1)
                    if last_id < START_MESSAGE_ID - 1:
                        last_id = START_MESSAGE_ID - 1
                    
                    state["last_downloaded_id"] = last_id
                    state["start_time"] = state.get("start_time", time.time())
                    return state
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
                return default_state
        
        return default_state
    
    def save_state(self):
        try:
            self.state["last_run"] = datetime.now().isoformat()
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return False
    
    def add_downloaded(self, message_id):
        if message_id not in self.state["downloaded_ids"]:
            self.state["downloaded_ids"].append(message_id)
            # Keep sorted
            self.state["downloaded_ids"].sort()
        
        # Remove from failed if it was there
        if message_id in self.state["failed_ids"]:
            self.state["failed_ids"].remove(message_id)
        
        # Update last downloaded
        if message_id > self.state["last_downloaded_id"]:
            self.state["last_downloaded_id"] = message_id
        
        self.save_state()
    
    def add_failed(self, message_id):
        if message_id not in self.state["failed_ids"]:
            self.state["failed_ids"].append(message_id)
            self.state["failed_ids"].sort()
        self.save_state()
    
    def is_downloaded(self, message_id):
        return message_id in self.state["downloaded_ids"]
    
    def get_next_batch(self, batch_size=BATCH_SIZE):
        """Get next batch of IDs to download"""
        start_id = max(self.state["last_downloaded_id"] + 1, START_MESSAGE_ID)
        batch_end = min(start_id + batch_size - 1, END_MESSAGE_ID)
        
        # Generate IDs in range that haven't been downloaded
        batch_ids = []
        for msg_id in range(start_id, batch_end + 1):
            if not self.is_downloaded(msg_id):
                batch_ids.append(msg_id)
        
        return batch_ids

# ================================
# ROBUST DOWNLOADER
# ================================
class RobustDownloader:
    def __init__(self, client, state):
        self.client = client
        self.state = state
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        self.is_running = True
        self.connection_retries = 0
        self.max_connection_retries = 5
        
        # Create download directory
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        
        # Set up signal handling
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        logger.info(f"\nReceived signal {sig}, shutting down gracefully...")
        self.is_running = False
    
    def get_file_path(self, message_id):
        return os.path.join(DOWNLOAD_DIR, f"{message_id}.txt")
    
    async def verify_connection(self):
        """Verify Telegram connection is alive"""
        try:
            me = await self.client.get_me()
            logger.info(f"Connected as: {me.first_name} (ID: {me.id})")
            return True
        except Exception as e:
            logger.error(f"Connection verification failed: {e}")
            return False
    
    async def download_single_file(self, message_id):
        """Download a single file by message ID"""
        file_path = self.get_file_path(message_id)
        
        # Skip if already successfully downloaded
        if os.path.exists(file_path) and os.path.getsize(file_path) > 100:  # At least 100 bytes
            if not self.state.is_downloaded(message_id):
                self.state.add_downloaded(message_id)
                logger.info(f"✓ Already exists: {message_id}.txt")
            return True
        
        # Clean up corrupted/empty files
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"🗑️  Deleted bad file: {message_id}.txt")
            except Exception as e:
                logger.warning(f"Could not delete {file_path}: {e}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            if not self.is_running:
                return False
            
            try:
                # Get the message
                messages = await self.client.get_messages(
                    ULP_CHANNEL_ID,
                    ids=[message_id]
                )
                
                if not messages or not messages[0] or not messages[0].media:
                    logger.error(f"❌ No media found for message {message_id}")
                    self.state.add_failed(message_id)
                    return False
                
                message = messages[0]
                
                async with self.semaphore:
                    logger.info(f"⬇️  Downloading {message_id}.txt (attempt {attempt}/{MAX_RETRIES})...")
                    
                    start_time = time.time()
                    
                    # Download with timeout
                    download_task = self.client.download_media(
                        message.media,
                        file_path
                    )
                    
                    # Add timeout to prevent hanging
                    try:
                        await asyncio.wait_for(download_task, timeout=300)  # 5 minute timeout
                    except asyncio.TimeoutError:
                        logger.warning(f"⏰ Download timeout for {message_id}.txt")
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                            except:
                                pass
                        continue
                    
                    download_time = time.time() - start_time
                    
                    # Verify download
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                        file_size = os.path.getsize(file_path) / (1024 * 1024)
                        logger.info(f"✅ Downloaded {message_id}.txt: {file_size:.1f}MB in {download_time:.2f}s")
                        self.state.add_downloaded(message_id)
                        return True
                    else:
                        logger.warning(f"⚠️  Empty file downloaded for {message_id}.txt")
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                            except:
                                pass
                
            except FloodWaitError as e:
                wait_time = e.seconds + random.randint(5, 10)
                logger.warning(f"⏳ Flood wait: {e.seconds}s, waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
                
            except Exception as e:
                error_msg = str(e)
                if "database is locked" in error_msg:
                    logger.error(f"🔒 Session locked, cannot continue")
                    self.is_running = False
                    return False
                
                logger.error(f"❌ Error downloading {message_id}.txt: {error_msg}")
                await asyncio.sleep(random.uniform(2, 5))
                continue
            
            # Small delay between retries
            if attempt < MAX_RETRIES:
                await asyncio.sleep(random.uniform(1, 3))
        
        # All retries failed
        logger.error(f"❌ Failed to download {message_id}.txt after {MAX_RETRIES} attempts")
        self.state.add_failed(message_id)
        return False
    
    async def download_batch(self, message_ids):
        """Download a batch of messages"""
        if not message_ids:
            return 0
        
        logger.info(f"📦 Downloading batch: IDs {message_ids[0]}-{message_ids[-1]}")
        
        tasks = []
        for msg_id in message_ids:
            if self.is_running:
                task = asyncio.create_task(self.download_single_file(msg_id))
                tasks.append(task)
                # Small delay between starting tasks
                await asyncio.sleep(0.2)
        
        # Wait for all tasks with timeout
        if tasks:
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=3600  # 1 hour timeout for batch
                )
                
                successful = 0
                for i, result in enumerate(results):
                    msg_id = message_ids[i]
                    if isinstance(result, Exception):
                        logger.error(f"Task failed for {msg_id}: {result}")
                        self.state.add_failed(msg_id)
                    elif result is True:
                        successful += 1
                
                return successful
                
            except asyncio.TimeoutError:
                logger.error("Batch download timeout")
                return 0
        
        return 0
    
    async def run_downloads(self):
        """Main download loop"""
        logger.info(f"Starting download from message {START_MESSAGE_ID} to {END_MESSAGE_ID}")
        
        total_to_download = END_MESSAGE_ID - START_MESSAGE_ID + 1
        logger.info(f"Total files to check: {total_to_download}")
        
        # Get initial progress
        downloaded = len(self.state.state["downloaded_ids"])
        failed = len(self.state.state["failed_ids"])
        
        logger.info(f"Already downloaded: {downloaded}")
        logger.info(f"Previously failed: {failed}")
        
        while self.is_running:
            # Get next batch
            batch_ids = self.state.get_next_batch(BATCH_SIZE)
            
            if not batch_ids:
                logger.info("✅ All files downloaded!")
                break
            
            # Download batch
            successful = await self.download_batch(batch_ids)
            
            # Show progress
            downloaded = len(self.state.state["downloaded_ids"])
            failed = len(self.state.state["failed_ids"])
            total_processed = downloaded + failed
            
            logger.info(f"Progress: {total_processed}/{total_to_download} files")
            logger.info(f"  ✓ Downloaded: {downloaded}")
            logger.info(f"  ✗ Failed: {failed}")
            
            # Delay between batches
            if self.is_running and len(batch_ids) == BATCH_SIZE:
                delay = random.uniform(3, 7)
                logger.info(f"⏸️  Pausing for {delay:.1f}s...")
                await asyncio.sleep(delay)
            
            # Save state every batch
            self.state.save_state()
        
        # Final summary
        if self.is_running:
            self.show_final_summary()
    
    def show_final_summary(self):
        """Show final download summary"""
        downloaded = len(self.state.state["downloaded_ids"])
        failed = len(self.state.state["failed_ids"])
        elapsed = time.time() - self.state.state["start_time"]
        
        print("\n" + "="*60)
        print("DOWNLOAD COMPLETE!")
        print("="*60)
        print(f"Downloaded: {downloaded} files")
        print(f"Failed: {failed} files")
        print(f"Success rate: {downloaded/(downloaded+failed)*100:.1f}%")
        print(f"Total time: {elapsed/60:.1f} minutes")
        print(f"Average speed: {downloaded/max(elapsed/60, 0.1):.1f} files/minute")
        print(f"Files saved in: {os.path.abspath(DOWNLOAD_DIR)}/")
        
        if failed > 0:
            print(f"\nFailed IDs: {sorted(self.state.state['failed_ids'])}")
            print("You can retry failed downloads by running the script again.")
        
        print("="*60)

# ================================
# MAIN APPLICATION
# ================================
async def main():
    # Clean up old session locks before starting
    cleanup_old_session_locks()
    
    print("\n" + "="*60)
    print("ROBUST TELEGRAM FILE DOWNLOADER")
    print("="*60)
    print(f"Channel: {ULP_CHANNEL_ID}")
    print(f"Download range: {START_MESSAGE_ID} to {END_MESSAGE_ID}")
    print(f"Total files: {END_MESSAGE_ID - START_MESSAGE_ID + 1}")
    print(f"Save as: {DOWNLOAD_DIR}/[ID].txt")
    print(f"Session file: {SESSION_FILE}")
    print("="*60)
    print("Starting in 5 seconds...")
    print("Press Ctrl+C to stop gracefully\n")
    
    await asyncio.sleep(5)
    
    # Check if session file is locked
    if not wait_for_session_unlock():
        logger.error("Cannot proceed, session file is locked by another process.")
        print("\n⚠️  Another download process might be running.")
        print("   Check with: ps aux | grep downloader.py")
        print("   Or wait a few minutes and try again.")
        return
    
    # Initialize state first
    state = SimpleState()
    
    # Initialize client with proper error handling
    client = None
    try:
        client = TelegramClient(
            SESSION_FILE,
            API_ID,
            API_HASH,
            connection_retries=3,
            retry_delay=5,
            timeout=30,
            request_retries=3,
            auto_reconnect=True,
            flood_sleep_threshold=60
        )
        
        # Connect with explicit error handling
        logger.info("Connecting to Telegram...")
        await client.start(phone=PHONE)
        
        # Force new login if needed
        if not await client.is_user_authorized():
            logger.info("Not authorized, sending code...")
            await client.send_code_request(PHONE)
            code = input("Enter the code you received: ")
            await client.sign_in(PHONE, code)
        
        logger.info("✅ Successfully connected to Telegram")
        
        # Initialize downloader
        downloader = RobustDownloader(client, state)
        
        # Verify connection
        if not await downloader.verify_connection():
            logger.error("Connection verification failed")
            return
        
        # Start downloads
        await downloader.run_downloads()
        
    except SessionPasswordNeededError:
        logger.error("Two-factor authentication required!")
        password = input("Enter your 2FA password: ")
        await client.sign_in(password=password)
        
    except KeyboardInterrupt:
        print("\n🛑 Download interrupted by user")
        if state:
            state.save_state()
            print("Progress saved. Run again to resume.")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean disconnect
        if client:
            try:
                # Save session state
                client.session.save()
                # Disconnect
                await client.disconnect()
                logger.info("Disconnected from Telegram")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
        
        print("\nScript finished.")

# ================================
# ENTRY POINT WITH NOHUP SUPPORT
# ================================
if __name__ == "__main__":
    # Set proper working directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Handle nohup output
    if not sys.stdout.isatty():
        print("Running in background (nohup mode)...")
        print(f"Logs will be saved to: {os.path.abspath('downloader.log')}")
        print(f"Check progress with: tail -f 
