# Fabric Images Downloader & Uploader

## Overview

This Python script automates the process of downloading firmware images from a source server, extracting them, and uploading them to a destination server. It reads the configuration from a JSON file and utilizes SSH and SCP for secure file transfers.

## Features

- Reads firmware paths from `fabric.cfg` within an extracted zip archive.
- Uses SCP and SFTP for secure file transfers.
- Downloads firmware files from a source server.
- Uploads firmware files to a remote destination server.
- Supports multi-threaded uploads for efficiency.
- Handles directory creation and ensures smooth file transfers.

## Dependencies

Ensure you have the following Python modules installed:

```bash
pip install paramiko scp
```

## Configuration

The script reads configurations from `config.json`. The configuration file must include the following structure:

```json
{
  "source_server": {
    "host": "fabricstudio.example.url/",
    "url": "https://fabricstudio.example.url/",
    "port": 22,
    "username": "admin",
    "password": "password"
  },
  "destination_server": {
    "host": "fabricstudio.example-dest.url/",
    "username": "admin",
    "password": "password",
    "remote_directory": "firmwares"
  },
  "paths": {
    "zip_file": "eSOC FCSS Security Operations 7.4 Analyst.zip",
    "extracted_config": "data/config_extract",
    "firmwares_dir": "data/firmwares",
    "data_dir": "data"
  }
}
```

## How to Use

### Running the Script

To execute the script, simply run:

```bash
python3 downloadFabicImages.py
```

### Steps Performed:

1. Extracts `fabric.cfg` from the provided zip file.
2. Parses `fabric.cfg` for firmware paths.
3. Connects to the source server via SSH and downloads firmware files.
4. Uploads firmware files to the destination server.
5. Logs success/failure messages for each file transfer.

## Expected Output

A typical execution logs:

```
Downloading ... firmwares/eSOC-DC_FML.meta
Downloaded: firmwares/eSOC-DC_FML.meta
Downloading directory ... /firmwares/eSOC-DC_FML
Downloaded directory: /firmwares/eSOC-DC_FML
...
Uploading directory: data/firmwares/eSOC-DC_FML → firmwares/eSOC-DC_FML
Success: data/firmwares/eSOC-DC_FML/.split
...
All firmwares downloaded, zipped, and uploaded successfully.
```

## Saving Output to a File

To save the script output to a file, use:

```bash
python3 downloadFabicImages.py > output.log 2>&1
```

This will capture both standard output and errors in `output.log`.

## Uploading to FabricStudio

Finally import the fabric file .zip into FabricStudio

## Error Handling

- If a required configuration key is missing, the script will raise a `KeyError`.
- If the firmware path is not found in `fabric.cfg`, the script raises a `ValueError`.
- If a file transfer fails due to permission errors, it logs the failure and continues with other transfers.

## Use Case Example

A security analyst working with `eSOC FCSS Security Operations 7.4` needs to migrate firmware images across servers. This script automates:

1. Extracting the firmware paths from `fabric.cfg`.
2. Downloading the firmware from `fabricstudio.example.url/`.
3. Uploading it securely to `fabricstudio.example-dest.url/firmwares/`.

## Troubleshooting

- **Permission Denied Errors:** Ensure that the user has the correct SSH/SFTP permissions.
- **Connection Refused:** Verify server credentials and network connectivity.
- **Missing Configurations:** Ensure `config.json` follows the expected format.

## Future Enhancements

- Implement retry mechanisms for failed transfers.
- Support additional authentication methods (e.g., SSH keys).
- Add logging to a file instead of only console output.


