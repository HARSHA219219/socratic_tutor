# ADR 0001: Student Identity via Name and Roll Number

## Status
Accepted / Implemented

## Context
The application is designed for classroom environments where 30–40 students interact with an AI tutor. Requiring account registration, email verification, or passwords creates friction and onboarding overhead during class sessions.

## Decision
Student identity is strictly determined by a combination of full name and unique roll number (`roll_no`):
* No passwords or credentials are required for students.
* When a student enters their name and roll number, the backend queries the database:
  * If the roll number is unrecorded, a new `Student` record is created.
  * If the roll number exists with the matching name, the existing record is returned, allowing the student to resume prior sessions.
  * If the roll number exists but with a different name, the request is rejected with HTTP 400.

## Consequences
* Rapid onboarding for students with zero credential management friction.
* Sessions and conversation history are persistently mapped to the student entity.
* Not suitable for public untrusted environments where impersonation is a concern, but ideal for supervised academic cohorts.
