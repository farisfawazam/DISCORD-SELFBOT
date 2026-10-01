#!/bin/bash
# ==============================================================================
# DISCORD VOICE STAY - FAST SHORTCUT CONTROLLER (VPS Linux)
# ==============================================================================
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

ACTION="${1:-}"

case "$ACTION" in
    start)
        if pgrep -f "run.py --run" > /dev/null 2>&1; then
            echo "[!] Bot sudah berjalan di background."
            exit 0
        fi
        nohup python3 run.py --run > selfbot.log 2>&1 &
        sleep 1.5
        PID=$(pgrep -f "run.py --run" | head -n 1)
        if [ -n "$PID" ]; then
            echo "[OK] Bot berhasil dijalankan di background (PID: $PID)."
            echo "[*] Untuk pantau log: ./bot.sh log"
        else
            echo "[FAIL] Gagal menjalankan bot. Cek selfbot.log:"
            tail -n 10 selfbot.log
        fi
        ;;

    stop)
        if pgrep -f "run.py" > /dev/null 2>&1; then
            pkill -f "run.py"
            sleep 1
            echo "[OK] Bot berhasil dihentikan."
        else
            echo "[!] Tidak ada bot yang sedang berjalan."
        fi
        ;;

    restart)
        $0 stop
        sleep 1
        $0 start
        ;;

    status)
        PID=$(pgrep -f "run.py --run" | head -n 1)
        if [ -n "$PID" ]; then
            echo "[STATUS] AKTIF (PID: $PID)"
        else
            echo "[STATUS] MATI"
        fi
        ;;

    log|logs)
        if [ ! -f selfbot.log ]; then
            touch selfbot.log
        fi
        echo "[*] Menampilkan log realtime (Tekan Ctrl+C untuk keluar)..."
        tail -f -n 25 selfbot.log
        ;;

    menu|"")
        python3 run.py
        ;;

    *)
        echo "Gunakan: ./bot.sh [start|stop|restart|status|log|menu]"
        ;;
esac
