from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from .deps import get_current_user
from ..database.model import User

router = APIRouter(prefix="/users", tags=["Users"])

@router.get(
    "/me",
    status_code=status.HTTP_200_OK
)
async def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    return current_user
