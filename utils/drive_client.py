import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly'
]
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), '../env_vars/credneciales.json')

def get_drive_service():
    """
    Authenticates with Google Drive using service account credentials
    and returns a Google Drive service object.
    """
    try:
        credentials = Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=credentials)
        return service
    except Exception as e:
        print(f"Error getting Drive service: {e}")
        return None

def verify_drive_connection():
    """
    Verifies the Google Drive connection by trying to list a small number of files.
    """
    service = get_drive_service()
    if not service:
        return False, "Failed to get Drive service."

    try:
        # Call the Drive v3 API to list files
        results = service.files().list(
            pageSize=10, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])

        if not items:
            return True, "Successfully connected to Google Drive, but no files found."
        else:
            file_names = [item['name'] for item in items]
            return True, f"Successfully connected to Google Drive. Found files: {', '.join(file_names[:3])}..."
    except HttpError as error:
        print(f"An HTTP error occurred: {error}")
        return False, f"An HTTP error occurred: {error}"
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False, f"An unexpected error occurred: {e}"

def get_sheets_service():
    """
    Authenticates with Google Sheets using service account credentials
    and returns a Google Sheets service object.
    """
    try:
        credentials = Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        print(f"Error getting Sheets service: {e}")
        return None

def read_spreadsheet(spreadsheet_id, range_name):
    """
    Reads data from a Google Sheet.
    """
    service = get_sheets_service()
    if not service:
        return None, "Failed to get Sheets service."

    try:
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                    range=range_name).execute()
        values = result.get('values', [])
        return values, "Successfully read spreadsheet."
    except HttpError as error:
        print(f"An HTTP error occurred: {error}")
        return None, f"An HTTP error occurred: {error}"
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None, f"An unexpected error occurred: {e}"

if __name__ == '__main__':
    # The ID of the spreadsheet to read.
    SPREADSHEET_ID = '1JVTklK1ZL5NDLVe8VxC1Lzi85b-wwGqBlT-fZwbozQQ'
    # The A1 notation of the range to retrieve.
    RANGE_NAME = 'Hoja 1!A1:E10'

    print(f"Attempting to read spreadsheet: {SPREADSHEET_ID}")
    values, message = read_spreadsheet(SPREADSHEET_ID, RANGE_NAME)

    if values is not None:
        print(f"Status: {message}")
        if not values:
            print("No data found.")
        else:
            print("First 10 rows of data:")
            for row in values:
                print(row)
    else:
        print(f"Status: {message}")
