"""
Deployment script for NutriRec → Hostkey VPS
Uploads project files via SFTP and configures the server.
"""

import os
import sys
import time
import paramiko
from pathlib import Path

# ── Server credentials ──
HOST     = "185.70.184.133"
PORT     = 22
USER     = "root"
PASSWORD = "iVY-D%R-0n"

# ── Paths ──
LOCAL_DIR  = Path(r"d:\uni\food-recommender")
REMOTE_DIR = "/opt/nutrirec"

# ── Files/dirs to skip ──
SKIP = {".git", "__pycache__", "chroma_db", "deploy.py",
        "_fix2.py", "_fix_indent.py", "_patch_nav.py",
        "_patch_tone_and_names.py", "_redesign.py", "theory"}


def ssh_run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 120) -> tuple[str, str]:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out.strip())
    if err.strip():
        print("[stderr]", err.strip())
    return out, err


def upload_dir(sftp: paramiko.SFTPClient, local: Path, remote: str):
    """Recursively upload a local directory to remote."""
    try:
        sftp.mkdir(remote)
    except OSError:
        pass  # already exists

    for item in local.iterdir():
        if item.name in SKIP:
            continue
        rpath = f"{remote}/{item.name}"
        if item.is_dir():
            upload_dir(sftp, item, rpath)
        else:
            print(f"  ↑ {item.relative_to(LOCAL_DIR)}")
            sftp.put(str(item), rpath)


def main():
    print("=" * 55)
    print("  NutriRec — Deployment to Hostkey VPS")
    print("=" * 55)

    # ── 1. Connect ──
    print(f"\n[1/6] Connecting to {HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    print("      Connected ✓")

    # ── 2. Upload files ──
    print(f"\n[2/6] Uploading project files to {REMOTE_DIR}...")
    sftp = ssh.open_sftp()
    upload_dir(sftp, LOCAL_DIR, REMOTE_DIR)
    sftp.close()
    print("      Upload complete ✓")

    # ── 3. System packages ──
    print("\n[3/6] Installing system packages...")
    ssh_run(ssh, "apt-get update -qq", timeout=120)
    ssh_run(ssh, "apt-get install -y python3-pip python3-venv python3-dev build-essential -qq", timeout=180)

    # ── 4. Python virtual environment ──
    print("\n[4/6] Creating virtual environment and installing dependencies...")
    cmds = [
        f"python3 -m venv {REMOTE_DIR}/venv",
        f"{REMOTE_DIR}/venv/bin/pip install --upgrade pip -q",
        # Install CPU-only torch first (saves ~1.5GB vs full torch)
        f"{REMOTE_DIR}/venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu -q",
        # Rest of requirements
        f"{REMOTE_DIR}/venv/bin/pip install streamlit pandas numpy chromadb sentence-transformers transformers gigachat plotly -q",
    ]
    for cmd in cmds:
        ssh_run(ssh, cmd, timeout=600)

    # ── 5. Systemd service ──
    print("\n[5/6] Creating systemd service...")
    service = f"""[Unit]
Description=NutriRec Streamlit App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={REMOTE_DIR}
Environment="HOME=/root"
ExecStart={REMOTE_DIR}/venv/bin/streamlit run {REMOTE_DIR}/app.py \\
    --server.port 8501 \\
    --server.address 0.0.0.0 \\
    --server.headless true \\
    --browser.gatherUsageStats false
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    # Write service file via echo
    service_escaped = service.replace('"', '\\"').replace('\n', '\\n')
    ssh_run(ssh, f"cat > /etc/systemd/system/nutrirec.service << 'SVCEOF'\n{service}\nSVCEOF")
    ssh_run(ssh, "systemctl daemon-reload")
    ssh_run(ssh, "systemctl enable nutrirec")
    ssh_run(ssh, "systemctl start nutrirec")
    time.sleep(3)
    ssh_run(ssh, "systemctl status nutrirec --no-pager")

    # ── 6. Open firewall port ──
    print("\n[6/6] Opening firewall port 8501...")
    ssh_run(ssh, "ufw allow 8501/tcp 2>/dev/null || true")

    ssh.close()

    print("\n" + "=" * 55)
    print("  DEPLOYMENT COMPLETE!")
    print(f"  App URL: http://{HOST}:8501")
    print("=" * 55)


if __name__ == "__main__":
    main()
