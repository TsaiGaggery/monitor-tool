#!/usr/bin/env python3
"""
Migration script to upgrade database schema from v1.0 to v1.1.
Adds tables for process monitoring, log collection, and AI insights.
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

class DatabaseMigrator:
    """Handle database schema migrations."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Connect to database."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def get_current_version(self) -> str:
        """Get current schema version."""
        try:
            self.cursor.execute(
                'SELECT version FROM schema_version '
                'ORDER BY applied_at DESC LIMIT 1'
            )
            result = self.cursor.fetchone()
            return result[0] if result else '1.0'
        except sqlite3.OperationalError:
            # Table doesn't exist, assume v1.0
            return '1.0'
    
    def migrate_to_v1_1(self):
        """Apply v1.1 migrations."""
        print("Starting migration to v1.1...")
        
        # Create version tracking table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version TEXT PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        ''')
        
        # Check if already migrated
        current_version = self.get_current_version()
        if current_version >= '1.1':
            print(f"Database already at version {current_version}")
            return
        
        # Create process_data table
        print("Creating process_data table...")
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS process_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                session_id TEXT NOT NULL,
                pid INTEGER NOT NULL,
                name TEXT NOT NULL,
                cpu_percent REAL NOT NULL,
                memory_rss INTEGER NOT NULL,
                memory_vms INTEGER,
                cmdline TEXT,
                status TEXT,
                num_threads INTEGER,
                create_time REAL,
                FOREIGN KEY (session_id) 
                    REFERENCES monitoring_data(session_id)
                    ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for process_data
        print("Creating indexes for process_data...")
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_process_timestamp '
            'ON process_data(timestamp)'
        )
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_process_session '
            'ON process_data(session_id)'
        )
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_process_cpu '
            'ON process_data(cpu_percent DESC)'
        )
        
        # Create log_entries table
        print("Creating log_entries table...")
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                source_file TEXT NOT NULL,
                severity TEXT,
                facility TEXT,
                message TEXT NOT NULL,
                raw_line TEXT,
                process_context TEXT,
                FOREIGN KEY (session_id) 
                    REFERENCES monitoring_data(session_id)
                    ON DELETE CASCADE
            )
        ''')
        
        # Create indexes for log_entries
        print("Creating indexes for log_entries...")
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_log_timestamp '
            'ON log_entries(timestamp)'
        )
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_log_session '
            'ON log_entries(session_id)'
        )
        self.cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_log_severity '
            'ON log_entries(severity)'
        )
        
        # Create process_log_correlation table
        print("Creating process_log_correlation table...")
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS process_log_correlation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                process_id INTEGER NOT NULL,
                log_entry_id INTEGER NOT NULL,
                correlation_type TEXT,
                confidence REAL,
                FOREIGN KEY (process_id) 
                    REFERENCES process_data(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (log_entry_id) 
                    REFERENCES log_entries(id)
                    ON DELETE CASCADE
            )
        ''')
        
        # Create report_insights table
        print("Creating report_insights table...")
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS report_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                provider TEXT,
                insights TEXT,
                prompt_used TEXT,
                FOREIGN KEY (session_id) 
                    REFERENCES monitoring_data(session_id)
                    ON DELETE CASCADE
            )
        ''')
        
        # Record migration
        print("Recording migration...")
        self.cursor.execute('''
            INSERT INTO schema_version (version, description)
            VALUES (?, ?)
        ''', ('1.1', 'Added process monitoring, log collection, and AI insights'))
        
        # Commit all changes
        self.conn.commit()
        
        print("Migration to v1.1 completed successfully!")
    
    def verify_migration(self):
        """Verify migration was successful."""
        print("\nVerifying migration...")
        
        tables = [
            'process_data',
            'log_entries',
            'process_log_correlation',
            'report_insights'
        ]
        
        for table in tables:
            self.cursor.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            )
            if self.cursor.fetchone():
                print(f"✓ Table {table} exists")
            else:
                print(f"✗ Table {table} missing!")
                return False
        
        print("\nMigration verification passed!")
        return True

def main():
    """Main migration entry point."""
    if len(sys.argv) < 2:
        db_path = Path.home() / '.monitor-tool' / 'monitor_data.db'
    else:
        db_path = Path(sys.argv[1])
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    print(f"Migrating database: {db_path}")
    
    migrator = DatabaseMigrator(str(db_path))
    try:
        migrator.connect()
        migrator.migrate_to_v1_1()
        if not migrator.verify_migration():
            sys.exit(1)
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        migrator.close()

if __name__ == '__main__':
    main()
