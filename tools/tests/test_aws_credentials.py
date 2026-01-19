"""
Tests for the AWS Credentials/Key Management module.
"""

import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aws.credentials import (
    save_private_key,
    load_private_key,
    list_saved_keys,
    delete_private_key,
    save_certificate,
    generate_ssh_config_entry,
)


def test_save_and_load_private_key():
    """Test saving and loading a private key."""
    print("Testing save and load private key...")
    
    test_key = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACBKtestkeytestkeytestkeytestkeytestAAAA
-----END OPENSSH PRIVATE KEY-----"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Monkey-patch the directories for testing
        import aws.credentials as creds_module
        original_pockitect_dir = creds_module.DEFAULT_POCKITECT_DIR
        original_ssh_dir = creds_module.DEFAULT_SSH_DIR
        
        creds_module.DEFAULT_POCKITECT_DIR = Path(tmpdir) / '.pockitect'
        creds_module.DEFAULT_SSH_DIR = Path(tmpdir) / '.ssh'
        
        try:
            # Save key
            result = save_private_key("test-key", test_key, save_to_ssh=True)
            
            assert 'pockitect_path' in result
            assert 'ssh_path' in result
            assert Path(result['pockitect_path']).exists()
            assert Path(result['ssh_path']).exists()
            
            # Check permissions
            pockitect_path = Path(result['pockitect_path'])
            assert (pockitect_path.stat().st_mode & 0o777) == 0o600
            
            # Load key
            loaded = load_private_key("test-key")
            assert loaded == test_key
            
        finally:
            creds_module.DEFAULT_POCKITECT_DIR = original_pockitect_dir
            creds_module.DEFAULT_SSH_DIR = original_ssh_dir
    
    print("  ✓ Save and load private key test passed")


def test_list_saved_keys():
    """Test listing saved keys."""
    print("Testing list saved keys...")
    
    test_key = "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        import aws.credentials as creds_module
        original_pockitect_dir = creds_module.DEFAULT_POCKITECT_DIR
        
        creds_module.DEFAULT_POCKITECT_DIR = Path(tmpdir) / '.pockitect'
        
        try:
            # Initially empty
            keys = list_saved_keys()
            assert len(keys) == 0
            
            # Save some keys
            save_private_key("key-alpha", test_key, save_to_ssh=False)
            save_private_key("key-beta", test_key, save_to_ssh=False)
            
            # List keys
            keys = list_saved_keys()
            assert len(keys) == 2
            
            key_names = [k['name'] for k in keys]
            assert 'key-alpha' in key_names
            assert 'key-beta' in key_names
            
        finally:
            creds_module.DEFAULT_POCKITECT_DIR = original_pockitect_dir
    
    print("  ✓ List saved keys test passed")


def test_delete_private_key():
    """Test deleting a private key."""
    print("Testing delete private key...")
    
    test_key = "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        import aws.credentials as creds_module
        original_pockitect_dir = creds_module.DEFAULT_POCKITECT_DIR
        original_ssh_dir = creds_module.DEFAULT_SSH_DIR
        
        creds_module.DEFAULT_POCKITECT_DIR = Path(tmpdir) / '.pockitect'
        creds_module.DEFAULT_SSH_DIR = Path(tmpdir) / '.ssh'
        
        try:
            # Save key
            save_private_key("to-delete", test_key, save_to_ssh=True)
            
            # Verify it exists
            assert load_private_key("to-delete") is not None
            
            # Delete it
            result = delete_private_key("to-delete")
            assert result is True
            
            # Verify it's gone
            assert load_private_key("to-delete") is None
            
            # Deleting again should return False
            result = delete_private_key("to-delete")
            assert result is False
            
        finally:
            creds_module.DEFAULT_POCKITECT_DIR = original_pockitect_dir
            creds_module.DEFAULT_SSH_DIR = original_ssh_dir
    
    print("  ✓ Delete private key test passed")


def test_save_certificate():
    """Test saving certificates."""
    print("Testing save certificate...")
    
    test_cert = """-----BEGIN CERTIFICATE-----
MIICpDCCAYwCCQDU+pQ4P7gB8DANBgkqhkiG9w0BAQsFADAUMRIwEAYDVQQDDAls
b2NhbGhvc3QwHhcNMjQwMTAxMDAwMDAwWhcNMjUwMTAxMDAwMDAwWjAUMRIwEAYD
-----END CERTIFICATE-----"""
    
    test_key = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7o5...
-----END PRIVATE KEY-----"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        import aws.credentials as creds_module
        original_pockitect_dir = creds_module.DEFAULT_POCKITECT_DIR
        
        creds_module.DEFAULT_POCKITECT_DIR = Path(tmpdir) / '.pockitect'
        
        try:
            result = save_certificate(
                project_name="my-project",
                cert_pem=test_cert,
                key_pem=test_key
            )
            
            assert 'cert_path' in result
            assert 'key_path' in result
            assert Path(result['cert_path']).exists()
            assert Path(result['key_path']).exists()
            
            # Verify content
            assert Path(result['cert_path']).read_text() == test_cert
            assert Path(result['key_path']).read_text() == test_key
            
            # Check permissions
            assert (Path(result['key_path']).stat().st_mode & 0o777) == 0o600
            
        finally:
            creds_module.DEFAULT_POCKITECT_DIR = original_pockitect_dir
    
    print("  ✓ Save certificate test passed")


def test_generate_ssh_config_entry():
    """Test SSH config entry generation."""
    print("Testing SSH config entry generation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        import aws.credentials as creds_module
        original_ssh_dir = creds_module.DEFAULT_SSH_DIR
        
        creds_module.DEFAULT_SSH_DIR = Path(tmpdir) / '.ssh'
        (Path(tmpdir) / '.ssh').mkdir()
        
        try:
            entry = generate_ssh_config_entry(
                key_name="my-key",
                host_alias="my-server",
                hostname="54.123.45.67",
                user="ubuntu"
            )
            
            assert "Host my-server" in entry
            assert "HostName 54.123.45.67" in entry
            assert "User ubuntu" in entry
            assert "my-key.pem" in entry
            
        finally:
            creds_module.DEFAULT_SSH_DIR = original_ssh_dir
    
    print("  ✓ SSH config entry generation test passed")


def test_key_name_sanitization():
    """Test that key names are properly sanitized."""
    print("Testing key name sanitization...")
    
    test_key = "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        import aws.credentials as creds_module
        original_pockitect_dir = creds_module.DEFAULT_POCKITECT_DIR
        
        creds_module.DEFAULT_POCKITECT_DIR = Path(tmpdir) / '.pockitect'
        
        try:
            # Key name with special characters
            result = save_private_key("my@key!with#special$chars", test_key, save_to_ssh=False)
            
            # Should be sanitized (only alphanumeric, dash, underscore kept)
            assert Path(result['pockitect_path']).exists()
            assert "mykeywithspecialchars" in result['pockitect_path']
            
        finally:
            creds_module.DEFAULT_POCKITECT_DIR = original_pockitect_dir
    
    print("  ✓ Key name sanitization test passed")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("AWS Credentials/Key Management Tests")
    print("="*60 + "\n")
    
    test_save_and_load_private_key()
    test_list_saved_keys()
    test_delete_private_key()
    test_save_certificate()
    test_generate_ssh_config_entry()
    test_key_name_sanitization()
    
    print("\n" + "="*60)
    print("All credentials tests passed! ✓")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
