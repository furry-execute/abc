# file: fix_encodings.py
import csv
import chardet
import os
from pathlib import Path

def detect_encoding(file_path):
    """Detect file encoding"""
    with open(file_path, 'rb') as f:
        raw_data = f.read(10000)  # Read first 10KB
        result = chardet.detect(raw_data)
        return result['encoding'], result['confidence']

def convert_to_utf8(file_path, target_encoding='utf-8-sig'):
    """Convert CSV file to UTF-8 with BOM"""
    try:
        # Detect current encoding
        encoding, confidence = detect_encoding(file_path)
        print(f"File: {file_path}")
        print(f"  Detected encoding: {encoding} (confidence: {confidence:.2%})")
        
        if encoding and confidence > 0.7:
            # Read with detected encoding
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                content = f.read()
            
            # Write with target encoding
            with open(file_path, 'w', encoding=target_encoding, errors='ignore') as f:
                f.write(content)
            
            print(f"  Converted to: {target_encoding}")
            return True
        else:
            print(f"  Could not detect encoding reliably")
            return False
            
    except Exception as e:
        print(f"  Error converting: {e}")
        return False

def fix_csv_file(file_path):
    """Fix CSV file encoding and check structure"""
    try:
        # Try to open with different encodings
        encodings_to_try = ['utf-8-sig', 'utf-8', 'cp1256', 'iso-8859-1', 'windows-1256', 'cp1252']
        
        for encoding in encodings_to_try:
            try:
                print(f"Trying encoding: {encoding} for {file_path}")
                
                with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                    # Try to read as CSV
                    content = f.read()
                    
                    # Check if it looks like CSV
                    if ',' in content or ';' in content:
                        print(f"  ✓ Success with {encoding}")
                        
                        # Rewrite with utf-8-sig
                        with open(file_path, 'w', encoding='utf-8-sig') as f_out:
                            f_out.write(content)
                        
                        # Verify it can be read as CSV
                        with open(file_path, 'r', encoding='utf-8-sig') as f_check:
                            reader = csv.reader(f_check)
                            headers = next(reader)
                            print(f"  ✓ CSV headers: {len(headers)} columns")
                            for i, header in enumerate(headers[:5]):
                                print(f"    Column {i}: {header[:50]}")
                        
                        return True
                        
            except UnicodeDecodeError:
                continue
            except StopIteration:
                print(f"  Empty file or no headers")
                return False
            except Exception as e:
                print(f"  Error with {encoding}: {e}")
                continue
        
        print(f"  ✗ Could not read with any encoding")
        return False
        
    except Exception as e:
        print(f"  ✗ Error processing file: {e}")
        return False

def scan_and_fix_directory(directory_path):
    """Scan directory for CSV files and fix encoding issues"""
    dir_path = Path(directory_path)
    
    if not dir_path.exists():
        print(f"Directory does not exist: {directory_path}")
        return
    
    print(f"\nScanning directory: {directory_path}")
    print("=" * 80)
    
    csv_files = []
    
    # Find all CSV files
    for ext in ['.csv', '.CSV']:
        csv_files.extend(dir_path.rglob(f"*{ext}"))
    
    if not csv_files:
        print("No CSV files found")
        return
    
    print(f"Found {len(csv_files)} CSV files")
    
    success_count = 0
    fail_count = 0
    
    for csv_file in csv_files:
        print(f"\nProcessing: {csv_file.name}")
        print(f"Full path: {csv_file}")
        
        # Check file size
        size = csv_file.stat().st_size
        print(f"File size: {size:,} bytes ({size/1024:.1f} KB)")
        
        if size == 0:
            print("  ✗ Empty file, skipping")
            fail_count += 1
            continue
        
        # Fix the file
        if fix_csv_file(csv_file):
            success_count += 1
        else:
            fail_count += 1
        
        print("-" * 80)
    
    print(f"\nSummary:")
    print(f"  Successfully fixed: {success_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Total: {len(csv_files)}")

def check_file_encodings(directory_path):
    """Check encodings of all files in directory"""
    dir_path = Path(directory_path)
    
    if not dir_path.exists():
        print(f"Directory does not exist: {directory_path}")
        return
    
    print(f"\nChecking encodings in: {directory_path}")
    print("=" * 80)
    
    all_files = []
    
    # Find all files
    for ext in ['.csv', '.CSV', '.json', '.JSON']:
        all_files.extend(dir_path.rglob(f"*{ext}"))
    
    if not all_files:
        print("No files found")
        return
    
    print(f"Found {len(all_files)} files")
    
    for file_path in all_files:
        print(f"\nFile: {file_path.name}")
        print(f"Path: {file_path}")
        
        size = file_path.stat().st_size
        print(f"Size: {size:,} bytes")
        
        if size == 0:
            print("  ✗ Empty file")
            continue
        
        # Detect encoding
        encoding, confidence = detect_encoding(file_path)
        print(f"  Detected encoding: {encoding} (confidence: {confidence:.2%})")
        
        # Try to read with detected encoding
        if encoding and confidence > 0.7:
            try:
                with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                    if file_path.suffix.lower() == '.csv':
                        # Try as CSV
                        try:
                            reader = csv.reader(f)
                            headers = next(reader)
                            print(f"  ✓ CSV - {len(headers)} columns")
                            for i, header in enumerate(headers[:3]):
                                print(f"    Column {i}: {header[:30]}")
                        except:
                            # Maybe not CSV
                            content = f.read(200)
                            print(f"  Content preview: {content[:100]}...")
                    elif file_path.suffix.lower() == '.json':
                        # Try as JSON
                        import json
                        try:
                            data = json.load(f)
                            print(f"  ✓ JSON - {len(data)} records")
                        except:
                            content = f.read(200)
                            print(f"  Content preview: {content[:100]}...")
            except Exception as e:
                print(f"  ✗ Error reading: {e}")
        else:
            print(f"  ✗ Could not detect encoding reliably")

def backup_and_convert_all():
    """Backup and convert all database files"""
    databases = {
        "iraq-facebook": "/root/iraq/downloads/iraq-facebook",
        "kurdistan-health": "/root/iraq/downloads/kurdistan-health",
        "aman": "/root/iraq/downloads/aman",
        "kurdistan-lawyers": "/root/iraq/downloads/kurdistan-lawyers",
        "loan-korektel": "/root/iraq/downloads/loan-korektel",
        "qi-card": "/root/iraq/downloads/qi-card",
        "zain": "/root/iraq/downloads/zain",
    }
    
    for db_name, db_path in databases.items():
        print(f"\n{'='*80}")
        print(f"Processing: {db_name}")
        print(f"Path: {db_path}")
        print('='*80)
        
        if os.path.exists(db_path):
            scan_and_fix_directory(db_path)
        else:
            print(f"  ✗ Directory does not exist")

def create_test_files():
    """Create test files to verify encoding"""
    test_dir = Path("/root/iraq/downloads/test_encoding")
    test_dir.mkdir(exist_ok=True)
    
    # Test with Arabic text
    arabic_text = "الاسم,العمر,المدينة\nعلي,25,بغداد\nمحمد,30,اربيل\nسارة,28,السليمانية\n"
    
    # Test with Kurdish text
    kurdish_text = "ناو,تەمەن,شار\nحەسەن,25,هەولێر\nسەلاح,30,سلێمانی\nڕێزان,28,دهۆک\n"
    
    # Test with mixed text
    mixed_text = "Name,Age,City\nAli,25,Baghdad\nهاڤال,30,Erbil\nسارا,28,Sulaymaniyah\n"
    
    # Write with different encodings
    encodings = ['utf-8-sig', 'utf-8', 'cp1256', 'windows-1256']
    
    for i, (text, name) in enumerate([
        (arabic_text, "arabic"),
        (kurdish_text, "kurdish"),
        (mixed_text, "mixed")
    ]):
        for encoding in encodings:
            filename = test_dir / f"{name}_{encoding}.csv"
            try:
                with open(filename, 'w', encoding=encoding) as f:
                    f.write(text)
                print(f"Created: {filename} with {encoding}")
            except Exception as e:
                print(f"Error creating {filename}: {e}")
    
    print(f"\nTest files created in: {test_dir}")

if __name__ == "__main__":
    import sys
    
    print("CSV Encoding Fixer Script")
    print("=" * 80)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "scan":
            # Scan all databases
            backup_and_convert_all()
        
        elif command == "check":
            # Check encodings
            if len(sys.argv) > 2:
                directory = sys.argv[2]
                check_file_encodings(directory)
            else:
                backup_and_convert_all()
        
        elif command == "fix":
            # Fix specific directory
            if len(sys.argv) > 2:
                directory = sys.argv[2]
                scan_and_fix_directory(directory)
            else:
                print("Please provide directory path")
        
        elif command == "test":
            # Create test files
            create_test_files()
        
        elif command == "detect":
            # Detect encoding of specific file
            if len(sys.argv) > 2:
                file_path = sys.argv[2]
                encoding, confidence = detect_encoding(file_path)
                print(f"File: {file_path}")
                print(f"Encoding: {encoding}")
                print(f"Confidence: {confidence:.2%}")
            else:
                print("Please provide file path")
        
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  scan     - Scan and fix all database directories")
            print("  check    - Check encodings of files")
            print("  fix DIR  - Fix files in specific directory")
            print("  test     - Create test files")
            print("  detect FILE - Detect encoding of specific file")
    
    else:
        # Default: scan all databases
        backup_and_convert_all()
