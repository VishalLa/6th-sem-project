from fastapi import (
    APIRouter,
    Depends,
    status
)

from auth.deps import get_current_user
from database.model import User


router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    status_code=status.HTTP_200_OK
)
async def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user profile information.
    """
    return {
        "user_id": current_user.user_id,
        "email": current_user.email_id,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "phone_no": current_user.phone_no,
        "organization": current_user.organization,
        "created_at": current_user.created_at.isoformat()
    }
