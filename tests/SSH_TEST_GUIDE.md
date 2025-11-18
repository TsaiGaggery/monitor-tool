# Remote Linux SSH - Quick Test Guide

## Prerequisites Checklist

### Local System
- [x] paramiko installed: `pip install paramiko>=3.0.0`
- [x] Code compiled without errors

### Remote System
Ensure you can SSH into it:
```bash
ssh username@remote-host
```

## Test Steps

### 1. Basic Connection Test

```bash
cd ~/monitor-tool
python3 tests/test_ssh_connection.py
```

Enter:
- Remote host (e.g., `192.168.1.100`)
- Username
- Port (default: 22)
- Use SSH key? (y/n)

Expected output:
```
📡 Connecting to username@host:22...
✅ Connected to host
✅ Sudo available without password (NOPASSWD)
   OR
✅ Sudo works with SSH password
   OR
⚠️  Sudo requires different password

✅ Connection successful!
   Data source: Remote Linux (username@host:22)

📊 Testing data collection (3 samples, 2 seconds apart)...

--- Sample 1 ---
CPU:
  Cores: 8
  Usage: 15.3%
  Frequency: 2400 MHz
  Temperature: 45.2°C

Memory:
  Total: 16.0 GB
  Used: 8.5 GB (53.1%)
  Available: 7.5 GB
  
... (continues for 3 samples)
```

### 2. GUI Test

```bash
./monitor-tool --ssh --host 192.168.1.100 --user username
```

Or with SSH key:
```bash
./monitor-tool --ssh --host 192.168.1.100 --user username --key ~/.ssh/id_rsa
```

Expected:
- Password prompt (if not using key)
- Sudo check messages
- GUI window opens showing remote system stats

### 3. CLI Test

```bash
./monitor-tool-cli --ssh --host 192.168.1.100 --user username
```

Expected:
- Interactive curses dashboard
- Real-time updates every second
- Press 'q' to quit

### 4. CLI with Export

```bash
./monitor-tool-cli --ssh --host 192.168.1.100 --user username -e html -o remote_test.html
```

Expected:
- Runs for a while (press 'q' to stop)
- Exports HTML report to `reports/YYYY-MM-DD/remote_test.html`
- Report shows correct duration and data

## Common Issues & Solutions

### Issue: "Connection refused"
```bash
# Check if SSH is running on remote
ssh username@remote-host

# Check firewall
sudo ufw status
```

### Issue: "Permission denied"
```bash
# Verify SSH key
ssh -v username@remote-host

# Copy key again
ssh-copy-id username@remote-host
```

### Issue: "Sudo password incorrect"
```bash
# Test sudo on remote
ssh username@remote-host "sudo -n true"

# If fails, set up NOPASSWD (on remote):
sudo visudo -f /etc/sudoers.d/monitor-tool
# Add: username ALL=(ALL) NOPASSWD: ALL
```

### Issue: "Temperature shows 0°C"
```bash
# Need sudo for temperature
ssh username@remote-host "sudo cat /sys/class/thermal/thermal_zone0/temp"

# If fails, add to sudoers:
username ALL=(ALL) NOPASSWD: /bin/cat /sys/class/thermal/*/temp
```

### Issue: "GPU not detected"
```bash
# Test NVIDIA
ssh username@remote-host "nvidia-smi"

# Test Intel
ssh username@remote-host "sudo intel_gpu_top -l"
```

## Validation Checklist

After testing, verify:
- [ ] SSH connection works (password or key)
- [ ] Sudo detection works correctly
- [ ] CPU usage updates in real-time (changes between samples)
- [ ] Memory stats are accurate
- [ ] GPU detected (if present)
- [ ] Network speed updates (non-zero when active)
- [ ] Disk I/O updates (non-zero when active)
- [ ] Temperature readings work (if sudo available)
- [ ] Export generates correct HTML report
- [ ] Duration in report is accurate

## Test Scenarios

### Scenario 1: NOPASSWD Sudo (Ideal)
```bash
# On remote: sudo visudo -f /etc/sudoers.d/monitor-tool
username ALL=(ALL) NOPASSWD: ALL

# Test
./monitor-tool-cli --ssh --host remote --user username
```
Expected: No sudo password prompt, all features work

### Scenario 2: Password Sudo
```bash
# On remote: No NOPASSWD configured

# Test
./monitor-tool-cli --ssh --host remote --user username
```
Expected: Uses SSH password for sudo, all features work

### Scenario 3: No Sudo Access
```bash
# On remote: User not in sudoers

# Test
./monitor-tool-cli --ssh --host remote --user username
```
Expected: Basic monitoring works, temperature/GPU may fail

### Scenario 4: SSH Key with NOPASSWD
```bash
# Best practice scenario
./monitor-tool-cli --ssh --host remote --user username --key ~/.ssh/id_rsa
```
Expected: Completely password-less, all features work

## Next Steps

After successful testing:
1. Test on different remote systems (Ubuntu, CentOS, etc.)
2. Test with different network conditions
3. Test GUI stability with longer runs
4. Verify export formats (HTML, CSV, JSON)
5. Check memory usage on both local and remote
