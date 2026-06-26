# Real-Time Fraud Detection Guard 🛡️
[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=black)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4+-3178c6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-336791?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-6+-dc382d?logo=redis&logoColor=white)](https://redis.io)
[![Azure](https://img.shields.io/badge/Azure-Cloud-0078d4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com)
[![Azure Deployment](https://img.shields.io/badge/Deployed%20on-Azure-0078d4.svg)](https://azure.microsoft.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Production-ready fraud detection system** processing transactions in real-time using ML models, business rules, and risk scoring to prevent fraudulent activities.

📊 **[Live Demo](https://drive.google.com/file/d/1yqJosEKuqZR0V5XdPcfb33kXkEQjuKAw/view?usp=sharing)** | 📋 **[Documentation](https://drive.google.com/file/d/1diOrjA_uckAZ3tuCbOqRDrFS0ELhfEpU/view?usp=sharing)** | 🔗 **[API](https://delightful-grass-0e3b7ed00.7.azurestaticapps.net)**

## 📁 Repository Structure

```
fraud-detection-guard/
├── 🎨 frontend/          # React 18 + TypeScript + Tailwind CSS
├── ⚡ backend/           # FastAPI + Python 3.11 + Async SQLAlchemy
├── 🤖 ml/               # Machine Learning Pipeline (XGBoost + ONNX)
├── 🔧 .github/          # CI/CD Workflows (Azure Deployment)
└── 📄 README.md         # Project Overview
```

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FRAUD DETECTION GUARD                      │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┐    ┌─────────────────────────────────────────────┐
│   Frontend UI    │    │              Azure Cloud                    │
│                  │    │                                             │
│  React 18 + TS   │◄──►│  ┌─────────────────┐  ┌─────────────────┐  │
│  Tailwind CSS    │    │  │  Static Web     │  │   App Service   │  │
│  Vite Build      │    │  │     Apps        │  │   (FastAPI)     │  │
└──────────────────┘    │  └─────────────────┘  └─────────────────┘  │
                        │           │                     │            │
┌──────────────────┐    │           ▼                     ▼            │
│ External APIs    │    │  ┌─────────────────┐  ┌─────────────────┐  │
│                  │    │  │  PostgreSQL     │  │  Redis Cache    │  │
│ 📧 SMTP (Gmail)  │◄──►│  │   Database      │  │   + Streams     │  │
│ 📱 Twilio (SMS)  │    │  └─────────────────┘  └─────────────────┘  │
└──────────────────┘    │                                             │
                        └─────────────────────────────────────────────┘
┌──────────────────┐
│   ML Pipeline    │    ┌─────────────────────────────────────────────┐
│                  │    │            GitHub Actions CI/CD             │
│ XGBoost + ONNX   │    │                                             │
│ Feature Eng.     │    │  Code Push ──► Tests ──► Build ──► Deploy  │
│ Model Training   │    │              ├─Backend ──► Azure App Service│
└──────────────────┘    │              └─Frontend ──► Static Web Apps │
                        └─────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        CORE PROCESSING FLOW                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Transaction ──► Feature ──► Rule ──► ML ──► Decision              │
│   Ingestion      Extract     Engine    Model   (Approve/           │
│                                              Verify/Block)         │
│                                    │                               │
│                                    ▼                               │
│  Email Notifications: 📧 samhillux@gmail.com (SMTP)               │
│  ├─ Transaction blocked alerts                                     │
│  ├─ Verification codes (OTP)                                       │
│  └─ User notifications                                             │
│                                                                     │
│  SMS Notifications: 📱 Twilio API                                  │
│  ├─ OTP verification codes                                         │
│  └─ Fraud alerts                                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Architecture Highlights
- **Frontend**: React 18 + TypeScript deployed on Azure Static Web Apps
- **Backend**: FastAPI + Python 3.11 on Azure App Service with auto-scaling
- **Database**: Azure Database for PostgreSQL (managed service)
- **Cache**: Azure Cache for Redis for real-time event streams
- **ML**: ONNX runtime with XGBoost models for fraud scoring
- **Email**: SMTP integration with Gmail (samhillux@gmail.com)
- **SMS**: Twilio API for OTP and alerts
- **Deployment**: GitHub Actions → Azure (automated CI/CD)
- **Monitoring**: Azure Application Insights for observability

## 🚀 Key Features

- **⚡ Real-time Processing** - Sub-second transaction decisions with Azure auto-scaling
- **🤖 ML-Powered Scoring** - ONNX runtime with XGBoost ensemble models
- **📏 Business Rules Engine** - Configurable rules with dynamic score adjustments
- **🔍 Multi-tier Decisions** - Approve, verify, or block with confidence scoring
- **📊 Live Dashboard** - Real-time monitoring with fraud metrics and alerts
- **🔐 Verification Workflow** - SMS (Twilio) + Email (SMTP) OTP with audit trails
- **📧 Email Notifications** - Automated alerts for blocked transactions and verifications
- **📈 Performance Analytics** - Model accuracy tracking and system metrics
- **🌐 Enterprise Ready** - GitHub Actions CI/CD with Azure deployment

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | React 18 + TypeScript + Tailwind CSS | Modern responsive UI |
| **Backend** | FastAPI + Python 3.11 + Async/Await | High-performance API |
| **Database** | PostgreSQL + SQLAlchemy 2.0 | Transactional data storage |
| **Cache** | Redis + Streams | Real-time event processing |
| **ML Runtime** | ONNX + XGBoost + Scikit-learn | Fraud model inference |
| **Email Service** | SMTP + Gmail (samhillux@gmail.com) | Verification & notifications |
| **SMS Service** | Twilio API | OTP delivery & alerts |
| **Deployment** | GitHub Actions + Azure | Automated CI/CD pipeline |
| **Hosting** | Azure App Service + Static Web Apps | Cloud-native scaling |

## 🌐 Deployment & Services

**Production Environment: Microsoft Azure + External APIs**

- **Frontend**: Azure Static Web Apps (Global CDN + Auto-deployment)
- **Backend API**: Azure App Service (Auto-scaling + Health monitoring)
- **Database**: Azure Database for PostgreSQL (Managed service)
- **Cache**: Azure Cache for Redis (High availability + Persistence)
- **Email**: SMTP via Gmail (samhillux@gmail.com for all notifications)
- **SMS**: Twilio API (OTP verification + fraud alerts)
- **CI/CD**: GitHub Actions workflows (Automated testing + deployment)
- **Monitoring**: Azure Application Insights + Log Analytics

## � Quick Start

### Prerequisites
- Python 3.11+, Node.js 20+
- PostgreSQL 13+, Redis 6+
- Azure CLI (for deployment)

### Local Development

```bash
# 1. Clone repository
git clone https://github.com/your-org/fraud-detection-guard.git
cd fraud-detection-guard

# 2. Backend setup
cd backend
pip install poetry
poetry install --with dev
cp .env.example .env  # Configure your database/redis URLs
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload

# 3. Frontend setup (new terminal)
cd frontend
npm install
cp .env.example .env  # Set VITE_API_BASE_URL
npm run dev

# 4. Access application
# Frontend: http://localhost:5173
# API Docs: http://localhost:8000/docs
```

### Production Deployment (Azure)

The system is deployed using Azure services:

1. **Azure Static Web Apps** - Frontend hosting with global CDN
2. **Azure App Service** - Backend API with auto-scaling
3. **Azure Database for PostgreSQL** - Managed database service
4. **Azure Cache for Redis** - In-memory data store

View deployment workflows in `.github/workflows/`

## 📧 Notification Services

### Email Integration (SMTP + Gmail)
- **Service**: Gmail SMTP server
- **Account**: samhillux@gmail.com (dedicated service account)
- **Use Cases**:
  - 🔐 Email verification (OTP codes)
  - 🚫 Blocked transaction alerts
  - ⚠️ Fraud detection notifications
  - 📋 System status updates

### SMS Integration (Twilio API)
- **Service**: Twilio Programmable SMS
- **Use Cases**:
  - 📱 SMS verification (OTP codes)
  - 🚨 Real-time fraud alerts
  - 🔒 Two-factor authentication
  - 📞 Critical security notifications

### Notification Flow
```
Transaction Event ──► Decision Engine ──► Notification Router
                                               │
                        ┌─────────────────────┼─────────────────────┐
                        ▼                     ▼                     ▼
                   📧 Email Queue        📱 SMS Queue        🔔 System Alerts
                  (Gmail SMTP)        (Twilio API)      (Internal Logging)
```

## � API Overview

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/transactions/ingest` | POST | Process new transaction |
| `/api/v1/decisions/{id}` | GET | Get fraud decision |
| `/api/v1/rules` | GET/POST | Manage fraud rules |
| `/api/v1/verification/initiate` | POST | Start verification flow |
| `/api/v1/dashboard/metrics` | GET | Real-time analytics |

### Example Transaction Processing

```json
POST /api/v1/transactions/ingest
{
  "transaction_id": "txn_123456",
  "user_id": "user_789",
  "amount": 249.99,
  "currency": "USD",
  "merchant": "Example Store",
  "timestamp": "2024-01-15T14:30:00Z"
}

Response:
{
  "decision": "verify",
  "score": 75,
  "reasons": ["high_velocity", "new_device"],
  "verification_required": true
}
```

## 🧪 Testing & Quality

```bash
# Backend testing
cd backend
poetry run pytest --cov=app --cov-report=html
poetry run ruff check . && poetry run black .

# Frontend testing  
cd frontend
npm test && npm run lint && npm run typecheck
```

## 📈 Performance Targets

- **Transaction Throughput**: Designed for high-volume processing
- **Decision Latency**: Sub-second response times
- **Model Accuracy**: Continuously monitored and optimized
- **System Uptime**: Azure-backed reliability and auto-scaling

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


---
**⚡ Built for Fraud Prevention | Deployed on Azure Cloud**