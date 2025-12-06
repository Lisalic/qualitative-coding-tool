# Qualitative Coding Tool

A full-stack web application for qualitative data analysis and coding, built with React (Vite) frontend and FastAPI backend.

## Project Structure

```
qualitative-coding/
├── backend/           # Python FastAPI backend
│   ├── app/
│   │   ├── api/      # API routes
│   │   ├── models/   # Database models
│   │   └── schemas/  # Pydantic schemas
│   ├── requirements.txt
│   └── .env.example
└── frontend/         # React + Vite frontend
    ├── src/
    │   ├── components/
    │   ├── pages/
    │   └── main.jsx
    ├── package.json
    └── vite.config.js
```

## Backend Setup

1. Navigate to the backend directory:

   ```bash
   cd backend
   ```

2. Create a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file:

   ```bash
   cp .env.example .env
   ```

5. Run the development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

The API will be available at `http://localhost:8000`
API documentation: `http://localhost:8000/docs`

## Frontend Setup

1. Navigate to the frontend directory:

   ```bash
   cd frontend
   ```

2. Install dependencies:

   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   npm run dev
   ```

The frontend will be available at `http://localhost:5173`

## Features

- Document management (create, read, update, delete)
- Qualitative coding interface
- Text selection and annotation
- Code organization and categorization
- RESTful API backend
- Modern React frontend with routing

## Tech Stack

### Backend

- FastAPI - Modern web framework for Python
- SQLAlchemy - SQL toolkit and ORM
- Pydantic - Data validation
- SQLite - Database (easily swappable)

### Frontend

- React 18 - UI library
- Vite - Build tool and dev server
- React Router - Client-side routing
- Axios - HTTP client

## Development

- Backend runs on port 8000
- Frontend runs on port 5173
- Frontend proxies API requests to backend
- CORS is configured for local development

## API Endpoints

- `GET /api/documents/` - List all documents
- `POST /api/documents/` - Create a new document
- `GET /api/documents/{id}` - Get a specific document
- `PUT /api/documents/{id}` - Update a document
- `DELETE /api/documents/{id}` - Delete a document
- `GET /api/codes/` - List all codes
- `POST /api/codes/` - Create a new code
- `DELETE /api/codes/{id}` - Delete a code
