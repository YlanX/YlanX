import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from email.message import EmailMessage

from monitor import (
    analyze_acronis,
    analyze_hqbird,
    extract_text_from_email,
    filter_lines_by_keywords,
    Priority,
    summarize,
)


def test_hqbird_priorities():
    log = """
    Backup verified successfully
    incremental backup fail on node
    Database corrompido detected
    """
    findings = analyze_hqbird(log)
    assert any(f.priority == Priority.CRITICAL for f in findings)
    assert any(f.priority == Priority.WARNING for f in findings)
    assert any(f.priority == Priority.OK for f in findings)


def test_acronis_backup_status():
    log = """
    Backup completed successfully
    Backup failed due to timeout
    Lack of space on target
    """
    findings = analyze_acronis(log)
    assert len(findings) == 3
    assert findings[0].priority == Priority.OK
    assert findings[1].priority == Priority.WARNING
    assert findings[2].priority == Priority.CRITICAL


def test_summary_format():
    log = "Backup completed successfully"
    findings = analyze_acronis(log)
    summary = summarize(findings)
    assert "CRITICAL: 0" in summary
    assert "WARNING: 0" in summary
    assert "OK: 1" in summary


def test_filter_lines_by_keywords():
    log = "Backup completed\nDatabase corrompido\nIncremental OK"
    filtered = filter_lines_by_keywords(log, ["corrompido", "incremental"])
    assert "Backup completed" not in filtered
    assert "Database corrompido" in filtered
    assert "Incremental OK" in filtered


def test_extract_text_from_email():
    message = EmailMessage()
    message.set_content("Backup verified successfully")
    assert extract_text_from_email(message) == "Backup verified successfully\n"
