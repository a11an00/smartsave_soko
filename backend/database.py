from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
# This creates a connection to the MySQL database using SQLAlchemy, allowing for ORM operations and session management
# Replace with your actual MySQL credentials
DATABASE_URL = "mysql+pymysql://root:@localhost:3306/smartsave_soko"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()