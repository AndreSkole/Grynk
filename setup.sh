#!/bin/bash

# Grynk Setup Script for Linux/macOS

echo "=================================================="
echo "  Grynk Installer — Powerful. Fast. Alive."
echo "=================================================="

# Check for Python
if ! command -v python3 &> /dev/null
then
    echo "✖ Error: Python 3 is not installed."
    exit 1
fi

# Install dependencies
echo "[setup] Installing dependencies..."
python3 -m pip install colorama requests beautifulsoup4 openai

# Make the wrapper script
echo "[setup] Creating global grynk command..."
INSTALL_DIR="/usr/local/bin"
GRYNK_PATH="$(pwd)/grynk.py"

# Use sudo if needed for /usr/local/bin
if [ -w "$INSTALL_DIR" ]; then
    printf "#!/bin/bash\npython3 \"$GRYNK_PATH\" \"\$@\"" > "$INSTALL_DIR/grynk"
    chmod +x "$INSTALL_DIR/grynk"
else
    echo "⚠ Permissions denied for $INSTALL_DIR. Running with sudo..."
    printf "#!/bin/bash\npython3 \"$GRYNK_PATH\" \"\$@\"" | sudo tee "$INSTALL_DIR/grynk" > /dev/null
    sudo chmod +x "$INSTALL_DIR/grynk"
fi

echo "=================================================="
echo "  ✔ Grynk installed successfully!"
echo "  Try running: grynk help"
echo "=================================================="
