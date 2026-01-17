from typing import Optional
try:
    from app.database import SessionLocal, Project, ProjectTable, User
except Exception as exc:
    try:
        from backend.app.database import SessionLocal, Project, ProjectTable, User
    except Exception:
        print("Failed to import app.database in databasemanager.py:", exc)
        raise exc


class DatabaseManager:
    def __init__(self):
        self.session = SessionLocal()
        self.projects = ProjectRepository(self.session)
        self.users = UserRepository(self.session)
        self.project_tables = ProjectTableRepository(self.session)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        try:
            if exc_type:
                self.session.rollback()
            else:
                try:
                    self.session.commit()
                except Exception:
                    self.session.rollback()
                    raise
        finally:
            self.session.close()


class BaseRepository:
    def __init__(self, session):
        self.session = session


class UserRepository(BaseRepository):
    def create(self, email: str, hashed_password: str) -> User:
        user = User(email=email, hashed_password=hashed_password)
        self.session.add(user)
        self.session.flush()
        return user

    def get_by_email(self, email: str) -> Optional[User]:
        return self.session.query(User).filter_by(email=email).first()


class ProjectRepository(BaseRepository):
    def get_all_for_user(self, user_id: int):
        return self.session.query(Project).filter_by(user_id=user_id).all()

    def get_schema_name(self, project_id: int) -> Optional[str]:
        proj = self.session.get(Project, project_id)
        return proj.schema_name if proj else None

    def rename_project(self, project_id: int, new_name: str) -> bool:
        proj = self.session.get(Project, project_id)
        if proj:
            proj.display_name = new_name
            self.session.flush()
            return True
        return False

    def create(self, user_id: int, display_name: str, schema_name: str, project_type: str = "raw_data", description: str = None) -> Project:
        # default project_type to raw_data so DB non-null constraint is satisfied
        proj = Project(user_id=user_id, display_name=display_name, schema_name=schema_name, project_type=project_type, description=description)
        self.session.add(proj)
        self.session.flush()
        return proj


class ProjectTableRepository(BaseRepository):
    def add_table_metadata(self, project_id, table_name: str, row_count: int):
        pt = ProjectTable(project_id=project_id, table_name=table_name, row_count=row_count)
        self.session.add(pt)
        self.session.flush()
        return pt
