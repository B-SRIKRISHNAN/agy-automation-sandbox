"""Helper base class for unittest-compatible isolated in-memory tests."""

import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agy_automation.api.common.database import Base, get_db
from agy_automation.api.main import app


class InMemoryDatabaseTestCase(unittest.TestCase):
    """Base test case for isolating database operations in memory."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self):
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        app.dependency_overrides.clear()
