# 🤖 PlacePilot: Your Location Companion

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Fused](https://img.shields.io/badge/Fused-udf-d1e550)](https://www.fused.io/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-✓-blue.svg)](https://core.telegram.org/bots/api)

PlacePilot is an intelligent Telegram bot that transforms how users interact with location data through natural language conversations. Built using agentic AI architecture, our bot serves as a comprehensive location assistant that can search, recommend, and help users contribute to the Foursquare database—all through simple chat interactions.

## 🏗️ Architecture

PlacePilot uses a modern, production-ready architecture:

- **Agentic AI System**: Supervisor agent coordinates specialized agents for different tasks
- **Async-First**: Built with FastAPI and async/await patterns for high performance
- **Microservices Ready**: Clean separation between agents, services, and integrations
- **Production-Grade**: Structured logging, health checks, error handling, and monitoring

### 🌟 Core Components

```
src/
├── agents/          # Agentic AI system
├── core/           # Configuration, database, logging
├── integrations/   # External API clients
├── models/         # Data models and schemas
├── services/       # Business logic
├── utils/          # Utility functions
└── webapp/         # Web interface
```

## 🚀 Features

### 🔍 Interactive Location Discovery
- **Visual Map Integration**: Explore Foursquare's 100M+ POIs through interactive maps
- **Natural Language Search**: "Show me coffee shops near Times Square"
- **Real-time Data**: Access to Foursquare's comprehensive database

### 🧠 Smart Place Recommendations  
- **Conversational Queries**: "I'm craving pizza in downtown, what are my options?"
- **Rich Responses**: Photos, ratings, contact details, operating hours
- **Context-Aware**: AI understands preferences and location context

### 📝 Crowd-Sourced Data Enhancement
- **Community Contributions**: Add new places through simple chat
- **AI-Assisted Entry**: Natural language processing eliminates complex forms
- **Quality Assurance**: Built-in validation ensures data accuracy

## 🛠️ Setup & Installation

### Prerequisites

```
- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- OpenAI API Key
- Foursquare API Key  
- Telegram Bot Token
```

### 🚀 Environment Setup

1. **Clone and setup**:
```bash
git clone <repository-url>
cd FSQ_Placemaker_Bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Environment variables**:
```bash
cp env.example .env
# Edit .env with your API keys and database settings
```

3. **Database setup**:
```bash
# Start PostgreSQL and Redis
sudo systemctl start postgresql redis

# Create database
createdb placemaker_db
```

4. **Run the application**:
```bash
python main.py
```

## 📋 Configuration

Key environment variables:

```bash
# API Keys (Required)
OPENAI_API_KEY=your-openai-api-key-here
FOURSQUARE_API_KEY=your-foursquare-api-key-here  
TELEGRAM_BOT_TOKEN=your-telegram-bot-token-here

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/placemaker_db

# Server
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development
```

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src tests/

# Type checking
mypy src/

# Code formatting
black src/
flake8 src/
```

## 🏗️ Development

### Adding a New Agent

1. Create agent class:
```python
from src.agents.base_agent import BaseAgent
from src.models.pydantic_models import AgentType

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(AgentType.MY_AGENT, "MyAgent")
    
    async def can_handle(self, request):
        # Logic to determine if agent can handle request
        return True
    
    async def process_request(self, request):
        # Process the request
        return self.create_response("Response text")
```

2. Register agent:
```python
from src.agents import agent_registry
agent_registry.register_agent(MyAgent())
```

### Database Migrations

```bash
# Generate migration
alembic revision --autogenerate -m "Description"

# Apply migrations  
alembic upgrade head
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build image
docker build -t placemaker .

# Run with docker-compose
docker-compose up -d
```

### Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Configure proper `SECRET_KEY`
- [ ] Set up SSL certificates
- [ ] Configure logging aggregation
- [ ] Set up monitoring and alerting
- [ ] Configure backup strategy

## 🏛️ Project Structure

```
PlacePilot/
├── src/
│   ├── agents/           # AI agent system
│   │   ├── base_agent.py
│   │   ├── supervisor_agent.py
│   │   ├── search_agent.py
│   │   ├── recommendation_agent.py
│   │   └── data_management_agent.py
│   ├── core/             # Core infrastructure
│   │   ├── config.py     # Configuration management
│   │   ├── database.py   # Database setup
│   │   ├── logging.py    # Structured logging
│   │   └── exceptions.py # Custom exceptions
│   ├── integrations/     # External APIs
│   │   ├── openai_client.py
│   │   ├── foursquare_client.py
│   │   └── telegram_client.py
│   ├── models/           # Data models
│   │   ├── pydantic_models.py  # API schemas
│   │   └── database_models.py  # SQLAlchemy models
│   ├── services/         # Business logic
│   ├── utils/           # Utilities
│   └── webapp/          # Web interface
├── tests/               # Test suite
├── docs/                # Documentation
├── migrations/          # Database migrations
├── main.py              # Application entry point
└── requirements.txt     # Dependencies
```

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Commit your changes (`git commit -m 'Add some amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

### 🔄 Development Guidelines

- Follow PEP 8 style guidelines
- Write comprehensive tests
- Update documentation
- Use type hints
- Follow the existing architecture patterns

## 📊 Monitoring & Observability

PlacePilot includes built-in monitoring:

- **Health Checks**: Database, Redis, external APIs
- **Structured Logging**: JSON logs with context
- **Metrics**: Performance and usage metrics
- **Error Tracking**: Comprehensive error handling

## 📈 Roadmap

- [x] **Phase 1**: Core agent framework ✅ 
- [ ] **Phase 2**: Specialized agents implementation
- [ ] **Phase 3**: Advanced AI features
- [ ] **Phase 4**: Production deployment
- [ ] **Phase 5**: Analytics and insights
- [ ] **Phase 6**: Multi-language support

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support, please open an issue or contact the development team.

---

**Built with ❤️ for the Foursquare community** 