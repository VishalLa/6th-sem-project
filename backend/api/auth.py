from fastapi import (
    APIRouter, 
    Depends,
    status,
    HTTPException
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession


from database.session import get_db 
from schema.user import UserCreate, UserResponse 
from service.user_service import UserService
from core.security import create_access_token


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
    """
    Register a new user account.
    """
    service = UserService(db)
    user = await service.create_new_user_(payload=payload)
    
    return user



@router.post(
    "/login",
    status_code=status.HTTP_200_OK
)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password.
    Returns JWT access token.
    """
    service = UserService(db)
    user = await service.get_user(email_id=form_data.username)

    # Check if user exists
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Verify password
    if not user.check_password(password=form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Create JWT token
    token = create_access_token({"sub": user.user_id})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.user_id,
        "email": user.email_id
    }


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK
)
async def logout():
    """
    Logout endpoint (client-side token deletion).
    """
    return {
        "message": "Logout successful. Please delete your access token."
    }
