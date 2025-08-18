#!/bin/bash
# Setup script for PlacePilot local development

echo "🚀 Setting up PlacePilot local development environment..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed. Please install it first:"
    echo "   Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib"
    echo "   macOS: brew install postgresql"
    echo "   Or use Docker: docker run --name postgres-placemaker -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres"
    exit 1
fi

# Check if PostgreSQL service is running
if ! pg_isready &> /dev/null; then
    echo "❌ PostgreSQL service is not running. Please start it:"
    echo "   Ubuntu/Debian: sudo systemctl start postgresql"
    echo "   macOS: brew services start postgresql"
    exit 1
fi

echo "✅ PostgreSQL is installed and running"

# Setup database
echo "📊 Setting up database..."
sudo -u postgres psql -f scripts/setup_db.sql

if [ $? -eq 0 ]; then
    echo "✅ Database setup completed"
else
    echo "❌ Database setup failed. Trying alternative method..."
    # Alternative method for different PostgreSQL setups
    psql -U postgres -f scripts/setup_db.sql
fi

# Copy environment file
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp env.example .env
    echo "✅ .env file created. Please update it with your API keys."
else
    echo "ℹ️  .env file already exists"
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

echo "🎉 Setup completed!"
echo ""
echo "Next steps:"
echo "1. Update .env with your API keys (OPENAI_API_KEY, FOURSQUARE_API_KEY, TELEGRAM_BOT_TOKEN)"
echo "2. Run: python main.py --demo"
echo "" 