from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app.core.database import get_db, templates
from app.core.security import create_access_token
from app.features.auth import service, schemas
from app.features.auth.models import User, RefreshToken
from app.config import settings

router = APIRouter()
# We'll use this single router for both API and Pages for better consistency

# --- API ROUTES ---

from app.core.email import send_resend_email

@router.post("/api/v1/auth/register", response_model=schemas.UserOut)
async def register(request: Request, user_in: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    # Abuse prevention: Check if IP has already registered
    ip = request.client.host
    existing_ip_stmt = select(User).where(User.registration_ip == ip)
    existing_ip_res = await db.execute(existing_ip_stmt)
    if existing_ip_res.scalar_one_or_none():
         # Instead of blocking, we could just give them 0 credits, 
         # but the user asked to "prevent", so we'll block.
         raise HTTPException(status_code=400, detail="Account limit reached for this connection")

    user = await service.get_user_by_email(db, user_in.email)
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = await service.create_user(db, user_in)
    new_user.registration_ip = ip
    
    from app.features.auth.trial_service import setup_new_user_trial
    await setup_new_user_trial(new_user)
    
    await db.commit()
    
    code = await service.generate_otp_code(db, new_user.id, "email_verification")
    
    await send_resend_email(
        to_email=new_user.email,
        subject="Verify your List Intel account",
        template_name="auth_code.html",
        context={
            "title": "Welcome to List Intel",
            "subtext": "Thanks for signing up! Please use the secure code below to verify your email.",
            "code": code
        }
    )
    return new_user

@router.post("/api/v1/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"success": True}

from app.core.dependencies import get_current_user
@router.post("/api/v1/auth/logout_all")
async def logout_all(response: Response, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Delete all refresh tokens for this user
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await db.commit()
    response.delete_cookie(key="access_token")
    return {"success": True}

@router.post("/api/v1/auth/verify-email")
async def verify_email(response: Response, data: schemas.EmailVerificationIn, db: AsyncSession = Depends(get_db)):
    user = await service.get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    is_valid = await service.verify_otp_code(db, user.id, data.code, "email_verification")
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        
    user.email_verified = True
    await db.commit()
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": str(user.id)}, expires_delta=access_token_expires)
    
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True, 
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return {"success": True, "access_token": access_token}

@router.post("/api/v1/auth/resend-verification")
async def resend_verification(data: schemas.ResendVerificationIn, db: AsyncSession = Depends(get_db)):
    user = await service.get_user_by_email(db, data.email)
    if not user:
        return {"success": True}
    if user.email_verified:
        return {"success": True, "message": "Already verified"}
        
    code = await service.generate_otp_code(db, user.id, "email_verification")
    await send_resend_email(
        to_email=user.email,
        subject="Your requested verification code",
        template_name="auth_code.html",
        context={
            "title": "Email Verification",
            "subtext": "Here is the new secure code you requested.",
            "code": code
        }
    )
    return {"success": True}

@router.post("/api/v1/auth/forgot-password")
async def forgot_password(data: schemas.ForgotPasswordIn, db: AsyncSession = Depends(get_db)):
    user = await service.get_user_by_email(db, data.email)
    if user:
        code = await service.generate_otp_code(db, user.id, "password_reset")
        await send_resend_email(
            to_email=user.email,
            subject="List Intel Password Reset Request",
            template_name="auth_code.html",
            context={
                "title": "Reset Your Password",
                "subtext": "We received a request to change your password. Use the secure code below to verify your identity.",
                "code": code
            }
        )
    return {"success": True}

@router.post("/api/v1/auth/reset-password")
async def reset_password(data: schemas.ResetPasswordOTPIn, db: AsyncSession = Depends(get_db)):
    user = await service.get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid code")
        
    is_valid = await service.verify_otp_code(db, user.id, data.code, "password_reset")
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
        
    from app.core.security import get_password_hash
    user.password_hash = get_password_hash(data.new_password)
    await db.commit()
    return {"success": True}

@router.post("/api/v1/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        token = token.split(" ")[1]
    
    if not token:
        raise HTTPException(status_code=401, detail="No token available for refresh")
        
    from app.core.security import decode_access_token, create_access_token
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError()
            
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        new_token = create_access_token(data={"sub": user_id}, expires_delta=access_token_expires)
        
        response.set_cookie(
            key="access_token", 
            value=f"Bearer {new_token}", 
            httponly=True, 
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="lax"
        )
        return {"success": True, "data": {"access_token": new_token}}
    except:
        raise HTTPException(status_code=401, detail="Invalid session token format")

@router.post("/api/v1/auth/login", response_model=schemas.Token)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user = await service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True, 
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("auth/signup.html", {"request": request})

@router.get("/verify-email", response_class=HTMLResponse)
async def verify_email_page(request: Request):
    return templates.TemplateResponse("auth/verify_email.html", {"request": request})

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("auth/forgot_password.html", {"request": request})

@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    return templates.TemplateResponse("auth/reset_password.html", {"request": request})
