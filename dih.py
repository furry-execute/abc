# file: validate_tokens.py
import csv
import requests
import time
import logging
from datetime import datetime

# Configuration
AUTH_FILE = "auth_tokens.csv"
VALID_TOKENS_FILE = "valid_tokens.csv"
TRUECALLER_API_URL = "https://asia-south1-truecaller-web.cloudfunctions.net/webapi/noneu/search/v2"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_token_validity(token):
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
        logger.error(f"Error checking token: {e}")
        return False

def validate_all_tokens():
    """Validate all Truecaller tokens"""
    tokens = []
    
    # Load tokens from auth file
    try:
        with open(AUTH_FILE, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'access_token' in row:
                    tokens.append(row['access_token'])
    except Exception as e:
        logger.error(f"Error loading tokens: {e}")
        return []
    
    logger.info(f"Found {len(tokens)} tokens to validate")
    
    valid_tokens = []
    invalid_tokens = []
    
    for i, token in enumerate(tokens, 1):
        logger.info(f"Checking token {i}/{len(tokens)}...")
        
        if check_token_validity(token):
            valid_tokens.append(token)
            logger.info(f"✓ Token {i} is valid")
        else:
            invalid_tokens.append(token)
            logger.info(f"✗ Token {i} is invalid")
        
        # Delay to avoid rate limiting
        time.sleep(1)
    
    # Save valid tokens
    try:
        with open(VALID_TOKENS_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['token', 'validated_at'])
            for token in valid_tokens:
                writer.writerow([token, datetime.now().isoformat()])
        
        logger.info(f"Saved {len(valid_tokens)} valid tokens to {VALID_TOKENS_FILE}")
        
    except Exception as e:
        logger.error(f"Error saving valid tokens: {e}")
    
    return valid_tokens

if __name__ == "__main__":
    logger.info("Starting token validation...")
    valid_tokens = validate_all_tokens()
    logger.info(f"Validation complete! Valid tokens: {len(valid_tokens)}")
