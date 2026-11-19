import pyodbc
from datetime import datetime

# --- IMPORTANT DEPENDENCY CHECK ---
# This file requires the 'pyodbc' library to connect to MsSQL.
# If you run into "ModuleNotFoundError: No module named 'pyodbc'", 
# install it using: pip install pyodbc
# ----------------------------------

# --- Configuration for MsSQL Connection ---
# Credentials are read from environment variables so they never live in the code.
# DRIVER: check your system for the ODBC driver name (e.g. 'ODBC Driver 17 for SQL Server').
import os

DB_CONFIG = {
    'driver': os.environ.get('MSSQL_DRIVER', '{ODBC Driver 17 for SQL Server}'),
    'server': os.environ.get('MSSQL_SERVER', 'localhost'),
    'database': os.environ.get('MSSQL_DATABASE', 'Aquaponics'),
    'username': os.environ.get('MSSQL_USERNAME', ''),
    'password': os.environ.get('MSSQL_PASSWORD', ''),
}

# Connection string setup
CONN_STR = (
    f'DRIVER={DB_CONFIG["driver"]};'
    f'SERVER={DB_CONFIG["server"]};'
    f'DATABASE={DB_CONFIG["database"]};'
    f'UID={DB_CONFIG["username"]};'
    f'PWD={DB_CONFIG["password"]};'
)

# SQL command to ensure the table exists (runs once)
CREATE_TABLE_SQL = """
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='PlantMetrics' AND xtype='U')
BEGIN
    CREATE TABLE PlantMetrics (
        ID INT PRIMARY KEY IDENTITY(1,1),
        Timestamp DATETIME NOT NULL,
        GroupName NVARCHAR(50) NOT NULL,
        PlantName NVARCHAR(50),
        Height_cm FLOAT,
        Width_cm FLOAT,
        Area_cm2 FLOAT,
        Confidence FLOAT
    )
END
"""

def initialize_db():
    """Initializes the database connection and creates the table if it doesn't exist."""
    print("Attempting database initialization...")
    try:
        with pyodbc.connect(CONN_STR) as conn:
            with conn.cursor() as cursor:
                cursor.execute(CREATE_TABLE_SQL)
            conn.commit()
        print("Database connection successful and table 'PlantMetrics' ensured.")
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        if sqlstate == '08001': # Client unable to establish connection
            print("\nFATAL ERROR: Database connection failed.")
            print("Please ensure your 'server', 'username', and 'password' in DB_CONFIG are correct.")
        elif sqlstate == '28000': # Invalid authorization specification
            print("\nFATAL ERROR: Authentication failed.")
            print("Please check 'username' and 'password' in DB_CONFIG.")
        else:
            print(f"Database Initialization Error (SQLSTATE: {sqlstate}): {ex}")
        # Re-raise the exception to stop the application from running without a database
        raise
    except Exception as e:
        print(f"Database Initialization Error: {e}")
        raise # Re-raise to stop app if essential service fails

def save_detection_data(group_name: str, plant_data: list):
    """
    Saves detection data for a group to the MsSQL database.
    plant_data is expected to be a list of dictionaries, e.g., 
    [{'name': 'Lettuce', 'height_cm': 7.4, 'width_cm': 6.2, 'confidence': 0.95}, ...]
    
    Returns the number of records inserted, or 0 on failure.
    """
    if not plant_data:
        print(f"No valid data to save for {group_name}.")
        return 0

    insert_sql = """
    INSERT INTO PlantMetrics (Timestamp, GroupName, PlantName, Height_cm, Width_cm, Area_cm2, Confidence)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    
    current_time = datetime.now()
    records_inserted = 0
    
    try:
        with pyodbc.connect(CONN_STR) as conn:
            with conn.cursor() as cursor:
                for plant in plant_data:
                    # Sanitize input: ensure all fields exist, providing defaults if missing
                    cursor.execute(
                        insert_sql, 
                        current_time, 
                        group_name, 
                        plant.get('name', 'Unknown'),
                        plant.get('height_cm'),
                        plant.get('width_cm'),
                        plant.get('area_cm2'),
                        plant.get('confidence')
                    )
                    records_inserted += 1
            conn.commit()
        print(f"Successfully inserted {records_inserted} records for {group_name}.")
        return records_inserted
    except Exception as e:
        print(f"MsSQL Save Error for {group_name}: {e}")
        return 0

if __name__ == '__main__':
    # This block is for testing the database connection and table creation
    try:
        initialize_db()
        
        # Example test data
        test_data = [
            {'name': 'lettuce', 'height_cm': 7.4, 'width_cm': 6.2, 'area_cm2': 35.1, 'confidence': 0.98},
            {'name': 'lettuce', 'height_cm': 6.8, 'width_cm': 6.0, 'area_cm2': 31.4, 'confidence': 0.95},
        ]
        save_detection_data("Experimental Group (Test)", test_data)
        print("Test data insertion successful.")

    except Exception as e:
        print(f"\nExiting due to database error.")