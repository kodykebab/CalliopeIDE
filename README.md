
# Calliope IDE - AI-Powered Chat Application for Smart Contract Development

Calliope IDE is a modern, browser-based AI coding assistant specifically designed to simplify Soroban smart contract development. Unlike traditional IDEs that require complex setup and local installations, Calliope IDE runs entirely in your browser, providing an intuitive chat interface for writing, testing, and deploying Soroban contracts.


## Why Calliope IDE?

Developing Soroban smart contracts can be challenging due to:
- Complex development environment setup
- Steep learning curve for Rust and Soroban SDK
- Limited debugging capabilities
- Time-consuming contract testing and deployment

Calliope IDE addresses these challenges by providing:
- 🚀 **Zero Setup**: Run directly in your browser - no local installations needed
- 🤖 **AI-Powered Assistance**: Get real-time help with contract development
- 📝 **Smart Code Generation**: Generate boilerplate code and common patterns
- 🔍 **Instant Error Detection**: Get immediate feedback on your code
- 🧪 **Built-in Testing**: Test your contracts directly in the chat interface
- 🔄 **Version Control**: Track changes and collaborate seamlessly

## Features

- 💬 Real-time chat functionality with AI assistance
- 🤖 AI-powered code generation and suggestions
- 🌙 Dark/Light mode support for comfortable coding
- 📱 Responsive design for coding on any device
- 🔒 Secure authentication and code storage
- 🎨 Modern UI with HeroUI components
- ⚡ Fast performance with Next.js
- 🔍 Advanced code search and analysis
- 📊 Contract analytics and insights
- 🧪 Built-in contract testing environment
- 🔄 Git integration for version control
- 📦 One-click contract deployment

## Technical Architecture

### Frontend
- **Framework**: Next.js 14 (Pages Router)
- **UI Components**: HeroUI v2
- **Styling**: Tailwind CSS with Tailwind Variants
- **State Management**: React Context + Custom Hooks
- **Type Safety**: TypeScript
- **Animations**: Framer Motion
- **Theme Management**: next-themes

### Backend
- **Server**: Next.js API Routes
- **Database**: (To be implemented)
- **Authentication**: (To be implemented)
- **Real-time Communication**: WebSocket
- **AI Integration**: OpenAI API

### Infrastructure
- **Hosting**: Vercel (recommended)
- **CI/CD**: GitHub Actions
- **Monitoring**: (To be implemented)
- **Analytics**: (To be implemented)

## User Flow

1. **Authentication**
   - User lands on the homepage
   - Option to sign in or create account
   - Email verification process
   - Profile setup

2. **Chat Interface**
   - Main chat dashboard
   - Conversation list
   - Active chat window
   - AI assistant integration

3. **Message Interaction**
   - Text message composition
   - File sharing
   - AI suggestions
   - Message reactions
   - Thread replies

4. **Settings & Customization**
   - Theme preferences
   - Notification settings
   - Profile management
   - Privacy controls


## Getting Started

### Prerequisites

- **Node.js**: v18.x or later
- **Python**: 3.8 or later
- **npm** or **yarn**
- **Git**

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/aludyalu/chatterji.git
    cd chatterji
    ```

2.  **Install Frontend Dependencies**:
    ```bash
    npm install
    # or
    yarn install
    ```

3.  **Install Backend Dependencies**:
    ```bash
    pip install flask google-generativeai
    ```

4.  **Set up Environment Variables**:
    Create a `.env.local` file in the root directory (optional but recommended for Next.js) or export variables directly:
    ```bash
    export GEMINI_API_KEY="your_google_gemini_api_key"
    ```

### Running Locally

1.  **Start the Backend**:
    ```bash
    python3 server/start.py
    ```

2.  **Start the Frontend** (in a new terminal):
    ```bash
    npm run dev
    ```

3.  **Access the IDE**:
    Open [http://localhost:3000](http://localhost:3000) in your browser.

## 🐳 Docker Setup (Recommended)

The easiest way to run Calliope IDE is with Docker — no need to manually install Node.js, Python, or any dependencies.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)

### Quick Start

1. **Clone the repository**:
    ```bash
    git clone https://github.com/kentuckyfriedcode/CalliopeIDE.git
    cd CalliopeIDE
    ```

2. **Set up environment variables**:
    ```bash
    cp .env.docker .env
    ```
    Edit `.env` and add your `GEMINI_API_KEY` and update the secret keys.

3. **Build and start**:
    ```bash
    docker-compose up --build
    ```

4. **Access the application**:
    - Frontend: [http://localhost:3000](http://localhost:3000)
    - Backend API: [http://localhost:5000](http://localhost:5000)
    - Health Check: [http://localhost:5000/health](http://localhost:5000/health)

### Development Mode

For local development with hot-reload (code changes reflect instantly):

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### Useful Commands

| Command | Description |
|---------|-------------|
| `docker-compose up --build` | Build and start all services |
| `docker-compose up -d` | Start in background (detached) |
| `docker-compose down` | Stop all services |
| `docker-compose down -v` | Stop and remove volumes (resets database) |
| `docker-compose logs -f backend` | Follow backend logs |
| `docker-compose logs -f frontend` | Follow frontend logs |
| `docker-compose ps` | Show running containers |
| `docker-compose restart backend` | Restart only the backend |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FRONTEND_PORT` | `3000` | Port for the Next.js frontend |
| `BACKEND_PORT` | `5000` | Port for the Flask backend |
| `FLASK_ENV` | `production` | Flask environment (`production` or `development`) |
| `SECRET_KEY` | — | Flask secret key (⚠️ change in production!) |
| `JWT_SECRET_KEY` | — | JWT signing key (⚠️ change in production!) |
| `JWT_ACCESS_TOKEN_EXPIRES` | `3600` | Access token lifetime in seconds |
| `JWT_REFRESH_TOKEN_EXPIRES` | `2592000` | Refresh token lifetime in seconds |
| `RATE_LIMIT_ENABLED` | `true` | Enable/disable API rate limiting |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max API requests per minute |
| `GEMINI_API_KEY` | — | Google Gemini API key for AI features |

### Architecture

```
┌──────────────────────────────────────────────┐
│              Docker Compose                   │
│                                               │
│  ┌─────────────┐      ┌──────────────────┐   │
│  │  Frontend    │      │   Backend        │   │
│  │  (Next.js)  │─────▶│   (Flask)        │   │
│  │  Port 3000  │      │   Port 5000      │   │
│  └─────────────┘      │   + SQLite DB    │   │
│                        │   + AI Agent     │   │
│                        └──────────────────┘   │
│                              │                │
│                        [backend-data]         │
│                        (persistent volume)    │
└──────────────────────────────────────────────┘
```

### Troubleshooting

- **Port already in use**: Change `FRONTEND_PORT` or `BACKEND_PORT` in `.env`
- **Backend unhealthy**: Check logs with `docker-compose logs backend`
- **Database reset**: Run `docker-compose down -v` to wipe the SQLite volume
- **Build cache issues**: Run `docker-compose build --no-cache`

## Contributing

We welcome contributions from the open-source community!

Please read our [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

Check out [TODO.md](TODO.md) for a list of features and fixes that need attention.

## Deployment

### Frontend (Vercel)
The easiest way to deploy the Next.js frontend is to use the [Vercel Platform](https://vercel.com/new).
1. Push your code to a Git repository.
2. Import the project into Vercel.
3. Add necessary environment variables.

### Backend
The Python/Flask backend needs a persistent server environment (unlike Vercel's serverless functions which have timeouts).
- **Recommended**: Railway, Render, or a VPS (DigitalOcean/AWS).
- Ensure the backend URL is correctly configured in the frontend (you may need to update `pages/app/index.jsx` or use an environment variable for the API URL).

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

---

Built with ❤️ using [Next.js](https://nextjs.org) and [HeroUI](https://heroui.com).
