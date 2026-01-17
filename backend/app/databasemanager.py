from typing import Optional
try:
    from app.database import SessionLocal, Project, ProjectTable, User, FileTable, File
except Exception as exc:
    try:
        from backend.app.database import SessionLocal, Project, ProjectTable, User, FileTable, File
    except Exception:
        print("Failed to import app.database in databasemanager.py:", exc)
        raise exc


class DatabaseManager:
    def __init__(self):
        self.session = SessionLocal()
        self.projects = ProjectRepository(self.session)
        self.users = UserRepository(self.session)
        self.project_tables = ProjectTableRepository(self.session)
        # Provide a `file_tables` alias for clarity in newer code that
        # prefers file-based naming (routes now expect `dm.file_tables`).
        self.file_tables = self.project_tables

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
        # `schema_name` column may be removed from `projects`; return None
        # Keep method for compatibility but avoid attribute access errors.
        try:
            return getattr(proj, 'schema_name', None) if proj else None
        except Exception:
            return None

    def rename_project(self, project_id: int, new_name: str) -> bool:
        proj = self.session.get(Project, project_id)
        if proj:
            proj.projectname = new_name
            self.session.flush()
            return True
        return False

    def create(self, user_id: int, projectname: str, description: str = None) -> Project:
        # Create a Project record without `project_type` or `schema_name` fields.
        proj = Project(user_id=user_id, projectname=projectname, description=description)
        self.session.add(proj)
        self.session.flush()
        return proj


class ProjectTableRepository(BaseRepository):
    def add_table_metadata(self, project_id=None, file_id=None, table_name: str = None, row_count: int = 0):
        """Add metadata for either a Project (project_id) or a File (file_id).

        One of `project_id` or `file_id` must be provided. Returns the created metadata object.
        """
        if project_id is not None:
            # Projects are no longer tracked via ProjectTable rows in the DB schema.
            # For compatibility, do nothing when asked to add project-level metadata.
            return None
        if file_id is not None:
            # Use FileTable for file-backed metadata
            ft = FileTable(file_id=file_id, tablename=table_name, row_count=row_count)
            self.session.add(ft)
            self.session.flush()
            return ft
        raise ValueError("Either project_id or file_id must be provided")
