"""
Configuration management for subscription manager
Handles paths and settings across different environments
"""

import os
from pathlib import Path

def get_data_directory():
    """Get the data directory for storing database and config files"""
    # Check environment variable first (for Docker/CI)
    if env_dir := os.getenv('SUBSCRIPTIONS_DATA_DIR'):
        return Path(env_dir)
    
    # Use XDG spec on Linux/Mac
    if xdg_data := os.getenv('XDG_DATA_HOME'):
        return Path(xdg_data) / 'subscriptions'
    
    # Default to home directory
    return Path.home() / '.subscriptions'

def get_database_path():
    """Get the database file path"""
    data_dir = get_data_directory()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / 'subscriptions.db'

def get_config_path():
    """Get the MCP config file path"""
    data_dir = get_data_directory()
    return data_dir / 'config.json'

# For backward compatibility with current setup
if __name__ == "__main__":
    print(f"Data directory: {get_data_directory()}")
    print(f"Database path: {get_database_path()}")