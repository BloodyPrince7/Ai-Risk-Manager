from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# ============================================================
# Database configuration
# ============================================================

DATABASE_URL = "sqlite:///./risk_manager.db"


# ============================================================
# Database engine
# ============================================================

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False
    }
)


# ============================================================
# Session factory
# ============================================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ============================================================
# Base class for database models
# ============================================================

Base = declarative_base()


# ============================================================
# Database dependency
# ============================================================

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()