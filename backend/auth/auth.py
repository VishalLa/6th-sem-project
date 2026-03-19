from fastapi import (
    APIRouter, 
    Depends,
    status,
    HTTPException
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.session import get_db
from ..schema.user import UserCreate, UserResponse
from ..service.user_service import UserService
from ..core.security import create_access_token


router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post(
    "/register", 
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
async def register_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    service = UserService(db)
    return await service.create_new_user_(payload=payload)


@router.post(
    "/login",
    status_code=status.HTTP_200_OK
)
async def login_user(
    # payload: UserLogin,
    from_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    service = UserService(db)
    user = await service.get_user(email_id=from_data.username)

    # check email
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # check password
    if not user.check_password(password=from_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # create token 
    token = create_access_token(
        {"sub": user.user_id}
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@router.post(
    "/logout",
    status_code=status.HTTP_200_OK
)
async def logout():
    return {"message": "Logout successful"}

