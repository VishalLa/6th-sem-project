from fastapi import (
    HTTPException, 
    status
)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select 
from ..database.model import User
from ..schema.user import UserCreate


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db 

    async def create_new_user_(self, payload: UserCreate) -> User:
        query = select(User).where(User.email_id == payload.email_id)

        result = await self.db.execute(query) 
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email id: {payload.email_id} already exist"
            )
        
        data_dict = payload.model_dump(exclude={"password"})


        new_user = User(
            **data_dict
        )
        new_user.set_password(password=payload.password)

        self.db.add(new_user)
        try:
            await self.db.commit()
            await self.db.refresh(new_user)
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
        

    async def get_user(self, email_id: str) -> User | None:
        query = select(User).where(User.email_id == email_id)

        result = await self.db.execute(query)
        user = result.scalar_one_or_none() 
        return user
    
    async def get_user_by_id(self, user_id: str) -> User | None:
        query = select(User).where(User.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
