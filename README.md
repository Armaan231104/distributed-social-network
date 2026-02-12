CMPUT404-project-socialdistribution\
[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/bRZK9dqv)
===================================

See the web page for a [description of the project.](https://uofa-cmput404.github.io/general/project.html)

Make a distributed social network!

## Team Members
| Name | CCID |
| --- | --- |
| Kaitlin Fong | krfong | 
| Sean Carson | swcarson |
| Nikhil Joshi | njoshi4 |
| Aaron Mramba | mramba |
| Watkin Tang | watkin1 |
| Armaan Khan | aikhan |

## License

This project is licensed under the MIT License . See the [LICENSE.md](LICENSE) file for details.

## Copyright

2026 CMPUT404 Social Distribution Project - Team Crimson

## 🌐 Project Overview

This project implements a distributed social networking platform that:

- Supports authors, entries (posts), comments, likes, and follow requests  
- Uses an **inbox push model** for federation  
- Identifies all API objects using **Fully Qualified IDs (FQIDs)**  
- Supports entry visibility levels:
  - PUBLIC
  - UNLISTED
  - FRIENDS
  - DELETED  
- Provides a RESTful API for both local and remote node communication  
- Can be deployed to Heroku with PostgreSQL  

The system is designed so that multiple nodes (servers) can communicate with each other to exchange content.

---

## 🛠 Tech Stack

- Python 3.11+
- Django
- PostgreSQL (Production / Heroku)
- SQLite (Local development)
- WhiteNoise (Static file serving)
- Gunicorn (Production WSGI server)

---

## 🚀 Local Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/uofa-cmput404/w26-socialdistribution-project-crimson.git
cd w26-socialdistribution-project-crimson
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` file in the project root

Create a file named `.env` in the root directory (same level as `manage.py`) and add:

```
DEBUG=True
SECRET_KEY=dev-only-change-me
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=sqlite:///db.sqlite3
```

### 5. Apply migrations

```bash
python manage.py migrate
```

### 6. Run the development server

```bash
python manage.py runserver
```

Open in browser:

```
http://127.0.0.1:8000
```

---

## 🗄 Database Configuration

Database configuration is controlled using the `DATABASE_URL` environment variable.

- Local development uses SQLite.
- Production deployment uses PostgreSQL on Heroku.

---

## 📡 API Structure

API endpoints follow this prefix structure:

```
http://<service>/api/
```

Examples:

```
GET  /api/authors/
GET  /api/authors/{AUTHOR_SERIAL}/
POST /api/authors/{AUTHOR_SERIAL}/entries/
```

All remote node-to-node communication uses HTTP Basic Authentication.

Full API documentation will be provided in later project parts.

---

## 🔐 Authentication

- Local authentication: Django session or token-based authentication (implementation in progress)
- Remote node authentication: HTTP Basic Auth

---

## ☁ Deployment

Each team member must deploy their own node to Heroku using:

- One Django web dyno
- One PostgreSQL add-on
- A single Django application serving:
  - Frontend
  - Static content
  - Backend API

Deployment instructions will be added in future project parts.

---

## 📄 License

This project uses an OSI-approved open-source license.  
See the `LICENSE` file for details.

Portions of this project are derived from W3C ActivityPub documentation under W3C license.

---

## 📌 Notes

- Virtual environments (`.venv/`) are not tracked by Git.
- The `.env` file is not committed to version control.
- All API objects are identified using fully qualified URLs (FQIDs).
- Federation functionality will be implemented in later project parts.
