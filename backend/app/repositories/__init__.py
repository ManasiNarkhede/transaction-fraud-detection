"""Data-access layer for transaction ingestion and fraud-score persistence.

Isolates all SQLAlchemy writes for the ingestion flow so services and routers
stay free of ORM/session details.
"""
