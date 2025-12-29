#!/bin/bash

# Event Storming Navigator - Development Server Startup Script

echo "🚀 Starting Event Storming Navigator..."
echo ""

# Check if Neo4j is running
echo "📊 Checking Neo4j connection..."
if ! nc -z localhost 7687 2>/dev/null; then
    echo "⚠️  Neo4j doesn't seem to be running on port 7687"
    echo "   Please start Neo4j before running this script"
    echo ""
fi

# Kill existing processes on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null

# Start Backend API
echo "🔧 Starting FastAPI backend on port 8000..."
cd "$(dirname "$0")"

# Find Python with uvicorn
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3 -m uvicorn"
elif [ -f "/Users/uengine/Library/Python/3.9/bin/uvicorn" ]; then
    PYTHON_CMD="/Users/uengine/Library/Python/3.9/bin/uvicorn"
else
    PYTHON_CMD="uvicorn"
fi

$PYTHON_CMD api.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# Wait for backend to start
sleep 2

# Start Frontend
echo "🎨 Starting Vue.js frontend on port 5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

echo ""
echo "✅ Development servers started!"
echo ""
echo "   📡 Backend API:  http://localhost:8000"
echo "   🌐 Frontend:     http://localhost:5173"
echo "   📚 API Docs:     http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers..."

# Handle shutdown
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "   Done!"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for both processes
wait

