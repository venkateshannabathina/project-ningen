#!/bin/bash
# Ningen AI Boardroom — start both Flask API and Streamlit
cd "$(dirname "$0")"

# Activate venv if present
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

# Kill any existing instances
pkill -f "api_server" 2>/dev/null
pkill -f "streamlit run app.py" 2>/dev/null
sleep 1

echo "Starting Ningen API server on :5001 ..."
python3 -c "from api_server import start_server; start_server(5001)" &
FLASK_PID=$!

sleep 2
echo "Starting Streamlit on :8501 ..."
streamlit run app.py

# Cleanup on exit
kill $FLASK_PID 2>/dev/null
