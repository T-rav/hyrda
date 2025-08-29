#!/usr/bin/env python3
"""
Database migration CLI tool

Usage:
    python migrate.py status      # Show migration status
    python migrate.py migrate     # Apply pending migrations
    python migrate.py rollback VERSION  # Rollback to specific version
"""

import asyncio
import sys
import os
from typing import Optional

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import Settings
from migrations.migration_manager import MigrationManager
from migrations.registry import register_migrations
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def show_status():
    """Show current migration status"""
    settings = Settings()
    
    if not settings.database.enabled:
        print("❌ Database is disabled in settings")
        return
        
    migration_manager = MigrationManager(settings.database.url)
    register_migrations(migration_manager)
    
    try:
        await migration_manager.initialize()
        status = await migration_manager.get_migration_status()
        
        print("\n📋 Migration Status:")
        print(f"   Total migrations: {status['total_migrations']}")
        print(f"   Applied: {status['applied_count']}")
        print(f"   Pending: {status['pending_count']}")
        
        if status['latest_applied']:
            print(f"   Latest applied: {status['latest_applied']}")
        
        if status['applied_migrations']:
            print("\n✅ Applied migrations:")
            for version in status['applied_migrations']:
                print(f"   - {version}")
        
        if status['pending_migrations']:
            print("\n⏳ Pending migrations:")
            for version in status['pending_migrations']:
                print(f"   - {version}")
        else:
            print("\n✨ All migrations are up to date!")
            
    except Exception as e:
        print(f"❌ Error checking migration status: {e}")
        sys.exit(1)
    finally:
        await migration_manager.close()

async def apply_migrations():
    """Apply all pending migrations"""
    settings = Settings()
    
    if not settings.database.enabled:
        print("❌ Database is disabled in settings")
        return
        
    migration_manager = MigrationManager(settings.database.url)
    register_migrations(migration_manager)
    
    try:
        await migration_manager.initialize()
        
        status = await migration_manager.get_migration_status()
        if status['pending_count'] == 0:
            print("✨ No pending migrations to apply")
            return
            
        print(f"🚀 Applying {status['pending_count']} pending migrations...")
        await migration_manager.apply_migrations()
        print("✅ All migrations applied successfully!")
        
    except Exception as e:
        print(f"❌ Error applying migrations: {e}")
        sys.exit(1)
    finally:
        await migration_manager.close()

async def rollback_migration(version: str):
    """Rollback to a specific migration version"""
    settings = Settings()
    
    if not settings.database.enabled:
        print("❌ Database is disabled in settings")
        return
        
    migration_manager = MigrationManager(settings.database.url)
    register_migrations(migration_manager)
    
    try:
        await migration_manager.initialize()
        print(f"⏪ Rolling back migration {version}...")
        await migration_manager.rollback_migration(version)
        print(f"✅ Migration {version} rolled back successfully!")
        
    except Exception as e:
        print(f"❌ Error rolling back migration: {e}")
        sys.exit(1)
    finally:
        await migration_manager.close()

def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migrate.py status                 # Show migration status")
        print("  python migrate.py migrate                # Apply pending migrations") 
        print("  python migrate.py rollback <version>     # Rollback specific migration")
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == "status":
        asyncio.run(show_status())
    elif command == "migrate":
        asyncio.run(apply_migrations())
    elif command == "rollback":
        if len(sys.argv) < 3:
            print("❌ Please specify migration version to rollback")
            sys.exit(1)
        version = sys.argv[2]
        asyncio.run(rollback_migration(version))
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()