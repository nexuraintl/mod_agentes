import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.google_drive_service import GoogleDriveService


class TestSheetsIncidentFiltering(unittest.TestCase):
    """
    Test suite for filtering and formatting incident data from Google Sheets.
    Following BDD approach: Given-When-Then
    """
    
    def setUp(self):
        """Initialize service before each test"""
        self.drive_service = GoogleDriveService()
        self.test_spreadsheet_id = "1YNl-KmBHEMI8QRyoHdSKTl9B1Auu6nwQkzTWEcymAQ4"
        self.sheet_name = "2. Consolidado Incidentes"
    
    def test_read_specific_sheet_by_name(self):
        """
        GIVEN: A spreadsheet with multiple sheets
        WHEN: Reading a specific sheet by name
        THEN: Should return only data from that sheet
        """
        range_name = f"{self.sheet_name}!A1:Z10"
        result = self.drive_service.get_sheet_values(
            self.test_spreadsheet_id, 
            range_name
        )
        
        self.assertIsNotNone(result)
        self.assertNotEqual(result, "")
        self.assertNotEqual(result, "No data found.")
        print(f"✅ Successfully read from sheet: {self.sheet_name}")
    
    def test_read_l1_and_ac1_columns(self):
        """
        GIVEN: The incident sheet with L1 and AC1 columns
        WHEN: Reading only L1 and AC1 columns
        THEN: Should return data from those specific columns
        """
        # L1 is column 12 (L), AC1 is column 29 (AC)
        range_name = f"{self.sheet_name}!L:L"
        l1_data = self.drive_service.get_sheet_values(
            self.test_spreadsheet_id,
            range_name
        )
        
        range_name = f"{self.sheet_name}!AC:AC"
        ac1_data = self.drive_service.get_sheet_values(
            self.test_spreadsheet_id,
            range_name
        )
        
        self.assertIsNotNone(l1_data)
        self.assertIsNotNone(ac1_data)
        print(f"✅ L1 column preview: {l1_data[:100]}")
        print(f"✅ AC1 column preview: {ac1_data[:100]}")
    
    def test_filter_empty_rows(self):
        """
        GIVEN: Raw sheet data with some empty cells
        WHEN: Filtering rows where L1 or AC1 are empty
        THEN: Should return only rows with both fields populated
        """
        # This will be implemented after we create the filtering method
        if not hasattr(self.drive_service, 'filter_and_format_incidents'):
            self.skipTest("filter_and_format_incidents not yet implemented")
        
        incidents = self.drive_service.filter_and_format_incidents(
            self.test_spreadsheet_id,
            self.sheet_name
        )
        
        # All incidents should have both L1 and AC1
        for incident in incidents:
            self.assertIn("L1:", incident)
            self.assertIn("AC1:", incident)
            # Ensure no empty values
            self.assertNotIn("L1: \n", incident)
            self.assertNotIn("AC1: \n", incident)
    
    def test_format_incident_document(self):
        """
        GIVEN: A row with L1 and AC1 data
        WHEN: Formatting it as a document
        THEN: Should create a structured, readable document
        """
        if not hasattr(self.drive_service, 'filter_and_format_incidents'):
            self.skipTest("filter_and_format_incidents not yet implemented")
        
        incidents = self.drive_service.filter_and_format_incidents(
            self.test_spreadsheet_id,
            self.sheet_name
        )
        
        if len(incidents) > 0:
            first_incident = incidents[0]
            # Check structure
            self.assertIn("===", first_incident)
            self.assertIn("L1:", first_incident)
            self.assertIn("AC1:", first_incident)
            print(f"✅ Sample formatted incident:\n{first_incident[:300]}")


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
