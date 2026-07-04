#!/usr/bin/env bash
# 本文件由 clipboard_manager.py 自动生成,请勿手动修改
python3 - <<'PYEOF' || exec /home/machache/item/myItem/copy_pasted/run.sh
import socket
s = socket.socket(socket.AF_UNIX)
s.settimeout(1)
s.connect('/tmp/clipboard-manager-1000')
s.sendall(b"toggle")
PYEOF
