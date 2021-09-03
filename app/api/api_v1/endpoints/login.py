from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.core import security
from app.core.config import get_settings
from app.core.security import get_password_hash
from app.utils.auth import generate_password_reset_token, verify_password_reset_token
from app.utils.email import send_reset_password_email

settings = get_settings()  # Import App settings

router = APIRouter()


@router.post("/login/access-token", response_model=schemas.Token)
def login_access_token(
    db: Session = Depends(deps.get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """login_access_token: OAuth2 compatible token login, get an access token for future requests

    Parameters
    ----------
    db : Session
         The database session, by default Depends(deps.get_db)
    form_data : OAuth2PasswordRequestForm, optional
        Object to hold the data from a form coming from the user, by default Depends()

    Returns
    -------
    Any
       Returns an Access Bearer token.

    Raises
    ------
    HTTPException
        Raised when the user has entered an incorrect email/password.
    HTTPException
        Raised when an inactive User tries to authenticate.
    """
    user = crud.user.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not crud.user.is_active(user):
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }


@router.post("/login/test-token", response_model=schemas.User)
def test_token(current_user: models.User = Depends(deps.get_current_user)) -> Any:
    """test_token to test access token.

    Parameters
    ----------
    current_user : models.User, optional
        Instance of the User who is currently logged in, by default Depends(deps.get_current_user)

    Returns
    -------
    Any
        [description]
    """
    return current_user


@router.post("/password-recovery/{email}", response_model=schemas.Msg)
def recover_password(email: str, db: Session = Depends(deps.get_db)) -> Any:
    """recover_password: Password Recovery

    Parameters
    ----------
    email : str
        email of the User.
    db : Session
        The database session, by default Depends(deps.get_db)

    Returns
    -------
    Any
        Message confirmation for password Recovery.

    Raises
    ------
    HTTPException
        Raised when email fetching from database fails.
    """
    user = crud.user.get_by_email(db, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    send_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )
    return {"msg": "Password recovery email sent"}


@router.post("/reset-password/", response_model=schemas.Msg)
def reset_password(
    token: str = Body(...),
    new_password: str = Body(...),
    db: Session = Depends(deps.get_db),
) -> Any:
    """reset_password: Reset password

    Parameters
    ----------
    token : str
        User token generated before, by default Body(...)
    new_password : str
        New user entered password, by default Body(...)
    db : Session
        The database session, by default Depends(deps.get_db)

    Returns
    -------
    Any
        Message confirmation for password reset.

    Raises
    ------
    HTTPException
        Raised when an invalid token is provided.
    HTTPException
        Raised when the user is not found in the system.
    HTTPException
        Raised when the user is inactive.
    """
    email = verify_password_reset_token(token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = crud.user.get_by_email(db, email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    elif not crud.user.is_active(user):
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = get_password_hash(new_password)
    user.hashed_password = hashed_password
    db.add(user)
    db.commit()
    return {"msg": "Password updated successfully"}
