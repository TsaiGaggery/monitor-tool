# Enabling Intel GPU Usage Monitoring

By default, Intel GPU usage shows 0% because the sysfs interface only provides frequency information, not actual utilization.

To get **real Intel GPU usage percentage**, you need to enable `intel_gpu_top` integration.

## Prerequisites

1. Install `intel-gpu-tools`:
   ```bash
   sudo apt install intel-gpu-tools
   ```

2. Configure passwordless sudo for `intel_gpu_top`:
   ```bash
   cd ~/monitor-tool
   ./update_sudoers.sh
   ```

3. Restart monitor-tool:
   ```bash
   ./monitor-tool
   ```

## How it works

- **Without intel_gpu_top**: GPU usage shows 0%, only frequency is displayed
- **With intel_gpu_top**: Real GPU utilization from Render/3D, Video, Compute engines

## Verification

Test if `intel_gpu_top` works:
```bash
sudo -n intel_gpu_top -J -s 500 -o -
```

If this works without asking for password, GPU usage monitoring is enabled!

## Manual Configuration

If you prefer to configure sudoers manually:

```bash
sudo visudo -f /etc/sudoers.d/monitor-tool
```

Add this line (replace `your_username`):
```
your_username ALL=(ALL) NOPASSWD: /usr/bin/intel_gpu_top
```

## Troubleshooting

### `intel_gpu_top` crashes
- Some Intel GPUs are not supported by older versions
- Try updating: `sudo apt upgrade intel-gpu-tools`
- Or accept that GPU usage will show 0%

### Permission denied
- Run `./update_sudoers.sh` again
- Check: `sudo -n intel_gpu_top -J -s 500 -o -` should work without password

### GPU usage still 0%
- Make sure there's actual GPU workload (run `glmark2` or video playback)
- Check if `intel_gpu_top` is actually running: `ps aux | grep intel_gpu_top`
