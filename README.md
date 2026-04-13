# Distributed Social Networking Platform

A distributed social media system that enables multiple nodes (servers) to exchange posts, comments, likes, and follow requests using a RESTful API and an inbox-based communication model.

## Key Features
- Node-to-node communication using HTTP
- REST APIs for authors, posts, comments, likes, and follow requests
- Inbox-based event propagation system (push model)
- Multiple visibility levels: public, unlisted, friends-only
- Globally unique identifiers (FQIDs) for cross-node consistency

## My Contributions
- Implemented REST API endpoints for authors, posts, comments, and follow requests, including validation and response handling
- Contributed to inbox-based communication between nodes for posts, likes, and comments
- Worked on data modeling and visibility logic (public, unlisted, friends-only)

## Tech Stack
- Python, Django
- REST APIs, HTTP, JSON
- SQLite (development), PostgreSQL (deployment)
- Gunicorn, WhiteNoise

## Architecture Overview
The system follows a distributed architecture where each node:
- Stores local data (authors, posts, etc.)
- Sends events (posts, likes, comments) to other nodes via inbox endpoints
- Receives and processes events from remote nodes

## Why This Project Matters
This project demonstrates:
- Backend API design
- Distributed system communication
- Data consistency across multiple nodes
- Real-world social platform architecture concepts
