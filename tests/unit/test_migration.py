import pytest
import sqlite3
import importlib.util
import sys
from pathlib import Path

# Load the migration script module dynamically because of the dots in filename
project_root = Path(__file__).parent.parent.parent
script_path = project_root / "scripts" / "migrate_v1.0_to_v1.1.py"

spec = importlib.util.spec_from_file_location(
    "migrate_script", 
    str(script_path)
)
migrate_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate_script)
DatabaseMigrator = migrate_script.DatabaseMigrator

class TestMigration:
    @pytest.fixture
    def db_path(self, tmp_path):
        path = tmp_path / "test_monitor.db"
        # Create a v1.0 database (just monitoring_data table)
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_data (
                session_id TEXT PRIMARY KEY,
                timestamp DATETIME,
                duration REAL
            )
        ''')
        conn.commit()
        conn.close()
        return str(path)

    def test_migration_creates_tables(self, db_path):
        migrator = DatabaseMigrator(db_path)
        migrator.connect()
        migrator.migrate_to_v1_1()
        
        # Verify tables exist
        cursor = migrator.cursor
        tables = ['process_data', 'log_entries', 'process_log_correlation', 'report_insights', 'schema_version']
        for table in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            assert cursor.fetchone() is not None, f"Table {table} should exist"
            
        # Verify version
        cursor.execute("SELECT version FROM schema_version")
        assert cursor.fetchone()[0] == '1.1'
        
        migrator.close()

    def test_idempotency(self, db_path):
        migrator = DatabaseMigrator(db_path)
        migrator.connect()
        migrator.migrate_to_v1_1()
        
        # Run again
        migrator.migrate_to_v1_1()
        
        # Should still be 1.1 and no errors
        cursor = migrator.cursor
        cursor.execute("SELECT count(*) FROM schema_version")
        assert cursor.fetchone()[0] == 1  # Should only have one entry
        
        migrator.close()

    def test_verify_migration(self, db_path):
        migrator = DatabaseMigrator(db_path)
        migrator.connect()
        migrator.migrate_to_v1_1()
        
        assert migrator.verify_migration() is True
        migrator.close()
