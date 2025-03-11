import os
import json
import zipfile
import paramiko
from scp import SCPClient
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
# Load configuration from JSON file
CONFIG_FILE = "config.json"

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

# Extract values from config
SRC_HOST = config["source_server"]["host"]
SRC_PORT = config["source_server"].get("port", 22)  # Default to port 22 if not specified
SRC_USERNAME = config["source_server"]["username"]
SRC_PASSWORD = config["source_server"]["password"]

DEST_HOST = config["destination_server"]["host"]
DEST_PORT = config["destination_server"].get("port", 22)  # Default to port 22 if not specified
DEST_USERNAME = config["destination_server"]["username"]
DEST_PASSWORD = config["destination_server"]["password"]
DEST_REMOTE_DIR = config["destination_server"]["remote_directory"]

ZIP_FILE_PATH = config["paths"]["zip_file"]
EXTRACTED_CONFIG_PATH = config["paths"]["extracted_config"]
FIRMWARES_DIR = config["paths"]["firmwares_dir"]
DATA_DIR = config["paths"]["data_dir"]


# Ensure extraction folders exist
os.makedirs(EXTRACTED_CONFIG_PATH, exist_ok=True)
os.makedirs(FIRMWARES_DIR, exist_ok=True)

# Extract the ZIP file
with zipfile.ZipFile(ZIP_FILE_PATH, 'r') as zip_ref:
    zip_ref.extractall(EXTRACTED_CONFIG_PATH)

# Read fabric.cfg correctly (handling missing section headers)
config_path = os.path.join(EXTRACTED_CONFIG_PATH, "fabric.cfg")

firmware_paths = []
with open(config_path, "r") as f:
    for line in f:
        line = line.strip()
        if line.lower().startswith("set path"):
            print(line)
            #_, path = line.split("=", 1)  # Extract value after '='
            path = line.replace("set path ","")
            firmware_paths.append(path.strip().replace('"', ''))  # Remove extra quotes

if not firmware_paths:
    raise ValueError("No 'set path' entries found in fabric.cfg")


def create_ssh_client(host, port, username, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Ignore bad certificates
    ssh.connect(host, port=port, username=username, password=password)
    return ssh

# Function to download firmware files with progress tracking
def download_firmwares():
    ssh = create_ssh_client(SRC_HOST, SRC_PORT, SRC_USERNAME, SRC_PASSWORD)
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(SRC_HOST, SRC_PORT, SRC_USERNAME, SRC_PASSWORD)
    ssh.connect(SRC_HOST, port=SRC_PORT, username=SRC_USERNAME, password=SRC_PASSWORD)
    print("connected")
    #calculate_total_size(ssh)  # Get total size before downloading

    with SCPClient(ssh.get_transport()) as scp:
        for fabric_path in firmware_paths:
            firmware_name = os.path.basename(fabric_path)
            remote_meta_file = f"firmwares/{firmware_name}.meta"
            remote_firmware_folder = f"/firmwares/{firmware_name}"

            # Ensure directories exist locally
            #firmware_local_dir = os.path.join(FIRMWARES_DIR, firmware_name)
            
            firmware_local_dir = os.path.join(FIRMWARES_DIR)
            os.makedirs(firmware_local_dir, exist_ok=True)

            # Download the .meta file
            meta_file_path = os.path.join(FIRMWARES_DIR, f"{firmware_name}.meta")
            try:
                print(f"\nDownloading ... {remote_meta_file}")
                scp.get(remote_meta_file, local_path=meta_file_path)
                print(f"\nDownloaded: {remote_meta_file}")
            except Exception as e:
                print(f"\nError downloading {remote_meta_file}: {e}")

            # Download the firmware directory
            try:
                print(f"\nDownloading directory ... {remote_firmware_folder}")
                scp.get(remote_firmware_folder, local_path=firmware_local_dir, recursive=True)
                print(f"\nDownloaded directory: {remote_firmware_folder}")
            except Exception as e:
                print(f"\nError downloading {remote_firmware_folder}: {e}")

    ssh.close()

MAX_PARALLEL_UPLOADS = 5  # Number of parallel uploads

# Function to create an SFTP connection
def create_sftp_client():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(DEST_HOST, port=DEST_PORT, username=DEST_USERNAME, password=DEST_PASSWORD)
    return ssh, ssh.open_sftp()

# Function to check and create remote directories if they don’t exist
def ensure_remote_directory(sftp, remote_directory):
    try:
        sftp.stat(remote_directory)  # Check if directory exists
    except FileNotFoundError:
        print(f"Creating remote directory: {remote_directory}")
        sftp.mkdir(remote_directory)  # Create directory if it doesn't exist

# Function to upload a single file
def upload_file(local_file_path, remote_file_path):
    try:
        ssh, sftp = create_sftp_client()
        
        # Ensure the remote directory exists
        remote_subdir = os.path.dirname(remote_file_path)
        ensure_remote_directory(sftp, remote_subdir)

        # Upload the file
        print(f"Uploading ... {local_file_path} → {remote_file_path}")
        sftp.put(local_file_path, remote_file_path)
        print(f"Uploaded: {local_file_path} → {remote_file_path}")

        sftp.close()
        ssh.close()
        return f"Success: {local_file_path}"

    except Exception as e:
        return f"Error uploading {local_file_path}: {e}"

# Function to collect all files that need to be uploaded
def collect_files():
    files_to_upload = []

    # Ensure the base remote directory exists
    ssh, sftp = create_sftp_client()
    ensure_remote_directory(sftp, DEST_REMOTE_DIR)

    for firmware_name in os.listdir(FIRMWARES_DIR):
        firmware_local_path = os.path.join(FIRMWARES_DIR, firmware_name)
        remote_path = os.path.join(DEST_REMOTE_DIR, firmware_name)

        # If it's a .meta file, add it to the upload list
        if firmware_name.endswith(".meta") and os.path.isfile(firmware_local_path):
            files_to_upload.append((firmware_local_path, remote_path))

        # If it's a directory, add all files inside it
        elif os.path.isdir(firmware_local_path):
            print(f"\nUploading directory: {firmware_local_path} → {remote_path}")
            ensure_remote_directory(sftp, remote_path)

            for root, _, files in os.walk(firmware_local_path):
                for file in files:
                    local_file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(local_file_path, firmware_local_path)
                    remote_file_path = os.path.join(remote_path, relative_path)

                    files_to_upload.append((local_file_path, remote_file_path))

    sftp.close()
    ssh.close()
    return files_to_upload

# Function to run parallel uploads
def upload_firmwares():
    files_to_upload = collect_files()

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_UPLOADS) as executor:
        future_to_file = {executor.submit(upload_file, local, remote): (local, remote) for local, remote in files_to_upload}
        
        for future in as_completed(future_to_file):
            result = future.result()
            print(result)




# Step 4: Download firmware files with progress tracking
#download_firmwares()

# Step 5: Zip the downloaded firmware files
'''firmwares_zip_path = "firmwares.zip"
with zipfile.ZipFile(firmwares_zip_path, 'w', zipfile.ZIP_DEFLATED) as firmware_zip:
    for root, _, files in os.walk(FIRMWARES_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            firmware_zip.write(file_path, os.path.relpath(file_path, FIRMWARES_DIR))

# Step 6: Append the ZIP to the original ZIP file
with zipfile.ZipFile(ZIP_FILE_PATH, 'a') as existing_zip:
    existing_zip.write(firmwares_zip_path, "firmwares.zip")'''

# Step 7: Upload the firmwares to the new target server
upload_firmwares()

print("\nAll firmwares downloaded, zipped, and uploaded successfully.")

''' TODO : 
1. stop fabric
2. Export config
3. update JSON
4. run download script
5. run upload firmwares to remote
6. upload config to remote fabric studio
'''
