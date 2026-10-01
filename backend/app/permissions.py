from fastapi import Depends, HTTPException

from app.auth import current_user


def require_roles(*allowed_roles):
    def check(user=Depends(current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(403, "Permissions insuffisantes")
        return user

    return check
