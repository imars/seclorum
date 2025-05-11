# tests/test_filesystem_manager.py
import os
import subprocess
import pytest
import shutil
from pathlib import Path
from seclorum.core.filesystem import FileSystemManager
from tempfile import TemporaryDirectory

@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def git_repo(temp_dir):
    """Create a temporary Git repository."""
    subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True, capture_output=True, text=True)
    yield temp_dir

def test_initialization_non_git(temp_dir):
    """Test initialization in a non-Git directory."""
    fsm = FileSystemManager.get_instance(repo_path=temp_dir, require_git=False)
    assert fsm.repo_path == os.path.abspath(temp_dir)
    assert not fsm.is_git_repo
    assert "Initialized FileSystemManager" in fsm.get_logs()[-1]["message"]

def test_initialization_git(git_repo):
    """Test initialization in a Git repository."""
    fsm = FileSystemManager.get_instance(repo_path=git_repo, require_git=True)
    assert fsm.repo_path == os.path.abspath(git_repo)
    assert fsm.is_git_repo
    assert "Initialized FileSystemManager" in fsm.get_logs()[-1]["message"]

def test_require_git_failure(temp_dir):
    """Test initialization failure when Git is required but absent."""
    with pytest.raises(ValueError, match="is not a Git repository"):
        FileSystemManager.get_instance(repo_path=temp_dir, require_git=True)

def test_singleton_pattern(temp_dir):
    """Test that the singleton pattern returns the same instance."""
    fsm1 = FileSystemManager.get_instance(repo_path=temp_dir)
    fsm2 = FileSystemManager.get_instance(repo_path=temp_dir)
    assert fsm1 is fsm2
    with pytest.raises(ValueError, match="Use get_instance"):
        FileSystemManager(repo_path=temp_dir)

def test_save_file_non_git(temp_dir):
    """Test saving a file in a non-Git directory."""
    fsm = FileSystemManager.get_instance(repo_path=temp_dir)
    content = "Hello, World!"
    filename = "test.txt"
    assert fsm.save_file(filename, content)
    with open(os.path.join(temp_dir, filename), "r") as f:
        assert f.read() == content
    assert f"Saved and staged file: {filename}" in [log["message"] for log in fsm.get_logs()]

def test_save_file_git(git_repo):
    """Test saving a file in a Git repository and staging it."""
    fsm = FileSystemManager.get_instance(repo_path=git_repo)
    content = "Hello, Git!"
    filename = "test.txt"
    assert fsm.save_file(filename, content)
    assert filename in fsm.get_staged_files()
    with open(os.path.join(git_repo, filename), "r") as f:
        assert f.read() == content
    assert f"Saved and staged file: {filename}" in [log["message"] for log in fsm.get_logs()]

def test_commit_changes_git(git_repo):
    """Test committing staged changes in a Git repository."""
    fsm = FileSystemManager.get_instance(repo_path=git_repo)
    content = "Commit me!"
    filename = "commit.txt"
    assert fsm.save_file(filename, content)
    assert fsm.commit_changes("Test commit")
    assert not fsm.get_staged_files()  # Staged files cleared
    result = subprocess.run(["git", "log", "-1", "--pretty=%B"], cwd=git_repo, capture_output=True, text=True)
    assert "Test commit" in result.stdout
    assert "Committed changes: Test commit" in [log["message"] for log in fsm.get_logs()]

def test_commit_no_changes(git_repo):
    """Test committing when no changes are staged."""
    fsm = FileSystemManager.get_instance(repo_path=git_repo)
    assert fsm.commit_changes("No changes commit")
    assert "No files staged for commit: No changes commit" in [log["message"] for log in fsm.get_logs()]

def test_file_cache(git_repo):
    """Test file caching and retrieval."""
    fsm = FileSystemManager.get_instance(repo_path=git_repo)
    content = "Cached content"
    filename = "cache.txt"
    assert fsm.save_file(filename, content)
    assert fsm.get_file(filename) == content
    assert "Retrieved file from cache" not in [log["message"] for log in fsm.get_logs()]
    assert fsm.get_file(filename) == content  # Should hit cache
    assert "Retrieved file from cache: cache.txt" in [log["message"] for log in fsm.get_logs()]
    fsm.clear_cache()
    assert fsm.get_file(filename) == content  # Should read from disk
    assert "Read file: cache.txt" in [log["message"] for log in fsm.get_logs()]

def test_invalid_filename(git_repo):
    """Test saving a file with an invalid filename."""
    fsm = FileSystemManager.get_instance(repo_path=git_repo)
    fsm.clear_cache()  # Clear caches before test
    content = "Invalid path"
    print(f"Testing invalid filename: ../outside.txt, repo_path: {git_repo}")
    assert not fsm.save_file("../outside.txt", content)  # Expect failure
    logs = [log["message"] for log in fsm.get_logs()]
    assert "Filename ../outside.txt rejected due to parent directory references" in logs
    assert "Failed to save file ../outside.txt: Filename ../outside.txt attempts to access outside repository" in logs
    print(f"Testing invalid filename: test<file.txt, repo_path: {git_repo}")
    assert not fsm.save_file("test<file.txt", content)  # Expect failure
    logs = [log["message"] for log in fsm.get_logs()]  # Refresh logs
    print("Logs after test<file.txt:", logs)
    assert "Failed to save file test<file.txt: Filename test<file.txt contains invalid characters" in logs

def test_file_not_found(git_repo):
    """Test retrieving a non-existent file."""
    fsm = FileSystemManager.get_instance(repo_path=git_repo)
    with pytest.raises(FileNotFoundError):
        fsm.get_file("nonexistent.txt")
    assert "File not found: nonexistent.txt" in [log["message"] for log in fsm.get_logs()]

def test_commit_failure_retry(git_repo, monkeypatch):
    """Test commit retry logic on failure."""
    fsm = FileSystemManager.get_instance(repo_path=git_repo)
    filename = "retry.txt"
    assert fsm.save_file(filename, "Retry content")

    # Simulate a transient failure for git commit
    call_count = 0
    original_run = subprocess.run
    def mock_run(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2 and args[0][0] == "git" and args[0][1] == "commit":
            raise subprocess.CalledProcessError(1, args[0], stderr="Simulated git error")
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)
    assert fsm.commit_changes("Retry commit")
    assert call_count >= 3  # Should retry twice before succeeding
    print("Logs:", [log["message"] for log in fsm.get_logs()])
    assert any("Attempt 1/3 failed to commit changes: Simulated git error" in log["message"] for log in fsm.get_logs())
    assert "Committed changes: Retry commit" in [log["message"] for log in fsm.get_logs()]
