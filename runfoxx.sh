#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "FoxxGent Setup Script"
echo "====================="

if [ ! -f ".env" ]; then
    echo "Creating .env from example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
    else
        cat > .env << 'EOF'
OPENROUTER_API_KEY=your_openrouter_api_key_here
TELEGRAM_BOT_KEY=your_telegram_bot_token_here
DB_PATH=foxxgent.db
EOF
    fi
    echo "Please edit .env with your API keys!"
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip >/dev/null 2>&1
pip install fastapi "uvicorn[standard]" python-telegram-bot sqlalchemy openai python-crontab psutil jinja2 python-dotenv requests beautifulsoup4 croniter google-api-python-client google-auth-httplib2 httpx aiohttp cryptography boto3 email-validator python-multipart >/dev/null 2>&1

echo "Initializing database..."
python3 -c "from database import init_db; init_db()" 2>/dev/null || true

echo ""
echo "FoxxGent is ready!"
echo "=================="
echo "Starting server on http://localhost:8000"
echo ""
echo "Then open http://localhost:8000 in your browser"
echo ""
echo "To restart after editing .env, run:"
echo "  bash runfoxx.sh"
echo ""

exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
