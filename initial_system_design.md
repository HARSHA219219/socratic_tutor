# Socratic Tutor — Prototype System Specification

## 1. Project Objective

Build a web-based Socratic Tutor prototype where students interact with a single LLM configured with the provided Socratic Tutor Master System Prompt.

The system must support approximately 30–40 concurrent students, persist all tutoring interactions, allow students to view and resume their previous conversations, and provide a credential-protected admin interface for the professor to review the collected logs.

The prototype should use a production-oriented architecture from the beginning so that the system can later be scaled without rewriting the frontend or backend.

---

# 2. Core Requirements

### Student

* Student enters:

  * Name
  * Roll number
* No student authentication/login.
* Name + unique roll number are treated as the student's identity.
* Student can start a tutoring session immediately.
* Student can view their previous tutoring sessions.
* Student can open an older session and resume the discussion.
* Student can create a new tutoring session at any time.
* Student interacts with the Socratic Tutor through a chat interface.
* The system uses a single LLM.
* Conversation history for a session is persisted and can be restored when the student reopens that session.
* All messages must remain permanently stored in the database for both student history and professor review.

### Professor

* Professor has a separate admin interface.
* Admin access must be credential protected.
* Professor can view:

  * Student name
  * Roll number
  * Sessions
  * Student prompts/messages
  * Model responses
  * Timestamps
* Professor should be able to open a session and see the complete chronological conversation.

### Concurrency

* Approximately 30–40 students should be able to use the system concurrently.
* Backend must use asynchronous/non-blocking operations where appropriate.
* Database connections should use connection pooling.
* LLM requests must not block unrelated users.
* Each student's sessions and conversation history must remain logically isolated.

---

# 3. Technology Stack

## Frontend

* React
* TypeScript
* Tailwind CSS

## Backend

* Python
* FastAPI
* Pydantic
* SQLAlchemy 2.0

## Database

* PostgreSQL

## AI

* Single LLM accessed through its API.
* Do not implement a multi-agent architecture.
* Keep the LLM integration modular so the underlying model/provider can be changed later.

## Deployment

* Docker
* Git/GitHub
* Production deployment should be container-friendly.

---

# 4. High-Level Architecture

```text
                         STUDENTS
                            |
                            v
                  +-------------------+
                  |   React Frontend  |
                  |                   |
                  |   Student Chat    |
                  |   Chat History    |
                  |   Admin Dashboard |
                  +---------+---------+
                            |
                         REST API
                            |
                            v
                  +-------------------+
                  |      FastAPI      |
                  |                   |
                  | Session Manager   |
                  | Chat API          |
                  | LLM Service       |
                  | Admin Auth        |
                  | Logging           |
                  +----+---------+----+
                       |         |
                       |         |
                       v         v
                +---------+   +-----------+
                | Single  |   | PostgreSQL|
                |   LLM   |   |           |
                +---------+   | Students  |
                              | Sessions  |
                              | Messages  |
                              +-----------+
```

The React frontend communicates only with FastAPI.

The LLM is accessed only from the backend.

The database is accessed only from the backend.

Students must never directly access the database or admin APIs.

Student identity is based on the name + unique roll number supplied by the student. There is no student authentication.

---

# 5. Student Identity and Session Model

Each student is represented by a unique roll number.

Example:

```text
Student
Name: Rahul
Roll No: 23110042
```

The backend should find the existing student record using the roll number or create a new student record if it does not exist.

Each student can have multiple tutoring sessions.

```text
Student A
    |
    +-- Session A123
    |      |
    |      +-- User message
    |      +-- Assistant response
    |      +-- User message
    |      +-- Assistant response
    |
    +-- Session B456
           |
           +-- User message
           +-- Assistant response
```

A student should be able to:

* View previous sessions.
* Open any previous session.
* Read the complete conversation.
* Continue the conversation.
* Start a new session.

The session history is persistent and remains available after browser refresh or returning to the application.

There is no requirement for students to authenticate. The system trusts that students enter their own name and unique roll number.

---

# 6. Database Schema

Keep the initial database simple and normalized.

## students

```text
id
name
roll_no
created_at
```

`roll_no` should be unique.

## sessions

```text
id
student_id
started_at
ended_at
```

Each session belongs to exactly one student.

## messages

```text
id
session_id
role
content
timestamp
```

The `role` field should distinguish at minimum:

```text
user
assistant
```

Every student prompt and every model response must be stored.

The database must preserve sessions after they are completed so that students and professors can access the historical conversations.

---

# 7. Student Flow

```text
Student opens application
        |
        v
Enter Name + Roll Number
        |
        v
Find/Create Student
        |
        v
Load Previous Sessions
        |
        +------------------------+
        |                        |
        v                        v
   Open Old Chat             New Chat
        |                        |
        v                        v
Load Messages              Create Session
        |                        |
        +------------+-----------+
                     |
                     v
                Chat Interface
                     |
                     v
             Student sends message
                     |
                     v
              FastAPI receives
                     |
                     v
             Load session context
                     |
                     v
              Construct LLM request
                     |
                     +-- System Prompt
                     +-- Conversation History
                     +-- New Student Message
                     |
                     v
                  Single LLM
                     |
                     v
                Tutor response
                     |
              +------+------+
              |             |
              v             v
          Save to DB   Return to React
              |             |
              +-------------+
```

---

# 8. Chat History and Resume

The React interface should provide a chat-history area/sidebar showing the student's previous sessions.

Example:

```text
+------------------+--------------------------------+
| Your Chats       | Current Conversation           |
|                  |                                |
| + New Chat       | Student:                       |
|                  | Why does inflation happen?     |
| Inflation        |                                |
| Newton's Laws    | Tutor:                         |
| Opportunity Cost | What do you think causes it?  |
|                  |                                |
|                  | [Type message...]              |
+------------------+--------------------------------+
```

When the student selects an older session:

1. React requests the session messages from FastAPI.
2. FastAPI verifies that the requested session belongs to the identified student context.
3. Backend returns the conversation.
4. React displays the conversation.
5. When the student sends a new message, the backend uses the existing conversation as context for the LLM.
6. The new student message and tutor response are persisted in the same session.

When the student selects "New Chat":

1. Create a new session.
2. Start with empty conversation context.
3. Keep the new session associated with the same student.

---

# 9. LLM Integration

The application uses one LLM.

Do not create:

* Multiple agents
* Planner agent
* Critic agent
* Evaluator agent
* Separate pedagogical agent
* Agent-to-agent communication

The provided Socratic Tutor Master System Prompt defines the tutoring behavior.

The backend should provide the LLM with:

1. System prompt
2. Current session conversation history
3. Current student message

The LLM generates the tutor response.

The LLM integration should be implemented behind a service/interface so that changing the model or provider later does not require rewriting the rest of the application.

Conceptually:

```text
FastAPI
   |
   v
LLM Service
   |
   v
LLM Provider
```

---

# 10. Socratic Tutor Behavior

The provided Socratic Tutor Master System Prompt is the primary behavioral specification.

The tutor should:

* Ask before telling when productive questioning can help.
* Diagnose the learner's current understanding.
* Avoid unnecessary question spam.
* Normally ask one major question at a time.
* Adapt the difficulty of questioning to the learner.
* Use progressive hints when the learner is stuck.
* Preserve partially correct reasoning and help the learner refine it.
* Identify misconceptions through the dialogue.
* Encourage evidence and justification.
* Examine assumptions.
* Consider alternative explanations.
* Use counterexamples when appropriate.
* Encourage transfer to novel situations.
* Use metacognitive reflection at meaningful points.
* Provide direct explanations when questioning is no longer productive or when explicitly requested.
* Avoid unnecessary praise.
* Avoid humiliating or dismissing the learner.
* Avoid pretending uncertain claims are certain.
* Avoid revealing hidden chain-of-thought.
* Keep normal tutoring responses concise.

The application should not attempt to replace the pedagogical logic with a complicated agent architecture. The single LLM should follow the provided system prompt.

---

# 11. API Design

Initial API structure:

## Student APIs

### POST /api/students

Create or retrieve a student using name and roll number.

Request:

```json
{
  "name": "Student Name",
  "roll_no": "123456"
}
```

Response should identify the student.

---

### POST /api/sessions

Create a new tutoring session for a student.

Request:

```json
{
  "student_id": "uuid"
}
```

Response should include a unique `session_id`.

---

### GET /api/sessions

Retrieve previous sessions for a student.

The response should provide enough information for the frontend to display the student's chat history.

---

### GET /api/sessions/{session_id}/messages

Retrieve the complete message history for a session.

---

### POST /api/chat

Send a student message and receive the tutor response.

Request:

```json
{
  "session_id": "uuid",
  "message": "Student's question"
}
```

Response:

```json
{
  "session_id": "uuid",
  "response": "Tutor response"
}
```

The backend must store both the user message and assistant response.

---

## Admin APIs

### POST /api/admin/login

Authenticate the professor/admin.

### GET /api/admin/students

Return student records available to the professor.

### GET /api/admin/sessions

Return tutoring sessions.

### GET /api/admin/sessions/{session_id}/messages

Return the complete chronological conversation for a session.

All admin APIs must require successful authentication.

---

# 12. Admin Dashboard

The professor dashboard should initially provide:

## Student List

Columns:

```text
Name
Roll Number
Number of Sessions
Last Activity
```

## Session List

Columns:

```text
Student
Roll Number
Session ID
Start Time
End Time
```

## Conversation View

Display:

```text
Student: [Name]
Roll Number: [Roll Number]
Session: [Session ID]

--------------------------------

Student:
[message]

Tutor:
[response]

Student:
[message]

Tutor:
[response]
```

Messages should appear chronologically.

---

# 13. Authentication

Students do not require authentication.

Student identity is based on the name and unique roll number entered by the student. The prototype intentionally trusts students to provide their own correct identity.

Professor/admin access must require credentials.

For the prototype:

* Admin credentials may be stored as environment variables/secrets.
* Never hard-code credentials in source code.
* Passwords should not be stored as plaintext in the database.
* Admin endpoints must reject unauthenticated requests.

The authentication implementation should be simple but structured so that it can later be replaced with a proper authentication/identity provider without redesigning the entire application.

---

# 14. Concurrency Requirements

Target:

```text
30–40 concurrent students
```

FastAPI should use asynchronous request handling.

LLM calls should use an asynchronous client where supported.

PostgreSQL should use connection pooling.

Do not use a global Python variable for conversation history.

Bad:

```python
conversation_history = []
```

Instead, all persistent conversation data must be associated with a unique `session_id`.

Multiple students must never receive another student's conversation history.

The backend should safely handle simultaneous requests from different sessions.

---

# 15. Frontend Structure

Suggested React structure:

```text
frontend/
    src/
        components/
            ChatMessage
            ChatInput
            LoadingIndicator
            StudentForm
            ChatSidebar
            SessionList
            SessionHeader
            AdminTable
            ConversationViewer

        pages/
            StudentPage
            AdminLoginPage
            AdminDashboardPage

        services/
            api.ts

        types/
            api.ts

        App.tsx
```

The frontend should remain simple and focused on the prototype requirements.

---

# 16. Backend Structure

Suggested FastAPI structure:

```text
backend/
    app/
        main.py

        api/
            student.py
            sessions.py
            chat.py
            admin.py

        models/
            student.py
            session.py
            message.py

        schemas/
            student.py
            session.py
            message.py
            admin.py

        services/
            llm_service.py
            student_service.py
            session_service.py
            logging_service.py
            auth_service.py

        db/
            database.py

        core/
            config.py
            security.py
```

Keep business logic out of route handlers where practical.

---

# 17. Environment Variables

Sensitive configuration must be provided through environment variables/secrets.

Example:

```text
DATABASE_URL=
LLM_API_KEY=
LLM_MODEL=
ADMIN_USERNAME=
ADMIN_PASSWORD_HASH=
```

Do not commit `.env` files or API keys to GitHub.

Provide a `.env.example` file containing variable names but no secrets.

---

# 18. Error Handling

The application should gracefully handle:

* LLM API failure
* LLM timeout
* Database failure
* Invalid session ID
* Session belonging to a different student
* Empty student message
* Invalid student information
* Invalid admin credentials
* Expired/invalid admin session
* Network failures

The frontend should show a user-friendly error rather than exposing backend stack traces.

---

# 19. Logging

Persist every tutoring interaction.

At minimum record:

```text
Student Name
Roll Number
Session ID
Student Prompt
Model Response
Timestamp
```

Do not store unnecessary personal information.

Application/server logs should be separate from tutoring interaction logs.

---

# 20. Non-Goals for Prototype

Do NOT implement unless specifically requested later:

* Multi-agent architecture
* RAG
* Vector database
* Fine-tuning
* Student login/authentication
* Complex learner profiles
* Knowledge graph
* Separate evaluator LLM
* Separate critic LLM
* Recommendation engine
* Mobile application
* Advanced analytics
* Payment system
* Complex role-based access control
* External identity provider for students

Persistent student chat history and session resumption ARE required.

---

# 21. Production Migration Principle

The prototype should already use:

```text
React
    +
FastAPI
    +
PostgreSQL
    +
Docker
```

so that production scaling primarily involves infrastructure improvements rather than rewriting the application.

Future production upgrades may include:

* Proper student identity/authentication provider
* Redis for caching/session coordination if required
* Background job processing if required
* Horizontal FastAPI scaling
* Load balancer
* Nginx/reverse proxy
* Monitoring
* Error tracking
* Rate limiting
* Stronger authorization
* HTTPS
* Database backups
* Observability

These are NOT required for the initial prototype.

---

# 22. Development Priority

### Phase 1 — Backend Foundation

1. FastAPI project setup
2. PostgreSQL connection
3. SQLAlchemy models
4. Database migrations
5. Student/session/message schema
6. Student creation/retrieval API
7. Session creation API
8. Session history API

### Phase 2 — LLM Integration

1. LLM service abstraction
2. System prompt integration
3. Conversation context handling
4. `/api/chat`
5. Persist prompts and responses
6. Error handling

### Phase 3 — Student Frontend

1. React + TypeScript setup
2. Student information form
3. Chat history/sidebar
4. New chat functionality
5. Chat interface
6. Open/resume previous chat
7. API integration
8. Loading/error states

### Phase 4 — Admin

1. Admin login
2. Protected admin routes
3. Student list
4. Session list
5. Conversation viewer

### Phase 5 — Testing & Concurrency

1. Test multiple simultaneous sessions
2. Test session isolation
3. Test reopening previous conversations
4. Test resuming conversations with correct context
5. Test database writes under concurrent requests
6. Test LLM API failures/timeouts
7. Test admin authorization
8. Test student identity/session behavior

### Phase 6 — Deployment

1. Dockerize frontend/backend
2. Configure environment secrets
3. Deploy
4. Test with approximately 30–40 concurrent users
5. Verify database logging
6. Verify persistent chat history
7. Verify admin access

---

# 23. Definition of Done

The prototype is complete when:

* A student can enter name and roll number without logging in.
* The system identifies the student using the unique roll number.
* A student can start a new tutoring conversation.
* A student can see their previous conversations.
* A student can open any previous conversation.
* A student can continue an old conversation.
* The resumed conversation provides the appropriate previous context to the LLM.
* A student can create multiple independent sessions.
* The single LLM responds according to the provided Socratic Tutor system prompt.
* Multiple students can use the application concurrently.
* Each student's sessions and conversations are isolated.
* Every student prompt is stored.
* Every model response is stored.
* Name, roll number, session ID, and timestamps are stored.
* Professor can securely log into the admin interface.
* Professor can view students.
* Professor can view sessions.
* Professor can view complete conversation logs.
* Students cannot access admin functionality.
* API keys and admin credentials are not exposed in source code.
* The system can be containerized and deployed.
* The architecture can be scaled toward production without replacing React or FastAPI.
