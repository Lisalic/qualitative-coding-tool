from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from backend.app.database import (
        AsyncSessionLocal,
        Project,
        User,
        FileTable,
    )
except Exception as exc:
    try:
        from app.database import (
            AsyncSessionLocal,
            Project,
            User,
            FileTable,
        )
    except Exception:
        print("Failed to import database models in databasemanager.py:", exc)
        raise exc


class AsyncDatabaseManager:
    def __init__(self):
        self.session: Optional[AsyncSession] = None
        self.projects: Optional["AsyncProjectRepository"] = None
        self.users: Optional["AsyncUserRepository"] = None
        self.project_tables: Optional["AsyncProjectTableRepository"] = None
        self.file_tables: Optional["AsyncProjectTableRepository"] = None

    async def __aenter__(self):
        self.session = AsyncSessionLocal()
        self.projects = AsyncProjectRepository(self.session)
        self.users = AsyncUserRepository(self.session)
        self.project_tables = AsyncProjectTableRepository(self.session)
        self.file_tables = self.project_tables
        return self

    async def __aexit__(self, exc_type, exc_value, tb):
        try:
            if exc_type:
                await self.session.rollback()
            else:
                try:
                    await self.session.commit()
                except Exception:
                    await self.session.rollback()
                    raise
        finally:
            await self.session.close()


class AsyncUserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, email: str, hashed_password: str) -> User:
        user = User(email=email, password=hashed_password)
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_email(self, email: str) -> Optional[User]:
        r = await self.session.execute(select(User).where(User.email == email))
        return r.scalar_one_or_none()


class AsyncProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_for_user(self, user_id) -> List[Project]:
        r = await self.session.execute(select(Project).where(Project.user_id == user_id))
        return list(r.scalars().all())


    async def rename_project(self, project_id, new_name: str) -> bool:
        proj = await self.session.get(Project, project_id)
        if proj:
            proj.projectname = new_name
            await self.session.flush()
            return True
        return False

    async def create(self, user_id, projectname: str, description: str = None) -> Project:
        proj = Project(user_id=user_id, projectname=projectname, description=description)
        self.session.add(proj)
        await self.session.flush()
        return proj


class AsyncProjectTableRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_table_metadata(self, project_id=None, file_id=None, table_name: str = None, row_count: int = 0):
        if project_id is not None:
            return None
        if file_id is not None:
            ft = FileTable(file_id=file_id, tablename=table_name, row_count=row_count)
            self.session.add(ft)
            await self.session.flush()
            return ft
        raise ValueError("Either project_id or file_id must be provided")
