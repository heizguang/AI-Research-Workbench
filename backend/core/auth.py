"""
用户认证模块
实现JWT认证和用户管理
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

# 配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24小时

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token
security = HTTPBearer()


class UserCreate(BaseModel):
    """用户创建请求"""
    username: str
    password: str
    email: Optional[str] = None
    nickname: Optional[str] = None


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class UserResponse(BaseModel):
    """用户响应"""
    id: str
    username: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    created_at: str
    is_active: bool = True


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class UserDatabase:
    """用户数据库（简化版本，使用文件存储）"""

    def __init__(self, db_path: str = "./data/users.json"):
        self.db_path = db_path
        self.users = self._load_users()

    def _load_users(self) -> Dict[str, Any]:
        """加载用户数据"""
        import json
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_users(self):
        """保存用户数据"""
        import json
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """获取用户"""
        return self.users.get(username)

    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建用户"""
        username = user_data["username"]
        if username in self.users:
            raise ValueError("用户名已存在")

        self.users[username] = user_data
        self._save_users()
        return user_data

    def update_user(self, username: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新用户"""
        if username not in self.users:
            return None

        self.users[username].update(data)
        self._save_users()
        return self.users[username]

    def delete_user(self, username: str) -> bool:
        """删除用户"""
        if username not in self.users:
            return False

        del self.users[username]
        self._save_users()
        return True


# 全局用户数据库实例
user_db = UserDatabase()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """解码令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="无效的认证令牌"
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> UserResponse:
    """获取当前用户"""
    token = credentials.credentials
    payload = decode_token(token)

    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=401,
            detail="无效的认证令牌"
        )

    user = user_db.get_user(username)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="用户不存在"
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=403,
            detail="用户已被禁用"
        )

    return UserResponse(
        id=user.get("id", username),
        username=user["username"],
        email=user.get("email"),
        nickname=user.get("nickname"),
        created_at=user.get("created_at", datetime.now().isoformat()),
        is_active=user.get("is_active", True)
    )


def register_user(user_data: UserCreate) -> TokenResponse:
    """注册用户"""
    # 检查用户名是否已存在
    if user_db.get_user(user_data.username):
        raise HTTPException(
            status_code=400,
            detail="用户名已存在"
        )

    # 创建用户
    import uuid
    user = {
        "id": str(uuid.uuid4()),
        "username": user_data.username,
        "password": get_password_hash(user_data.password),
        "email": user_data.email,
        "nickname": user_data.nickname or user_data.username,
        "created_at": datetime.now().isoformat(),
        "is_active": True
    }

    user_db.create_user(user)

    # 创建令牌
    access_token = create_access_token({"sub": user["username"]})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user["id"],
            username=user["username"],
            email=user.get("email"),
            nickname=user.get("nickname"),
            created_at=user["created_at"],
            is_active=True
        )
    )


def login_user(login_data: UserLogin) -> TokenResponse:
    """用户登录"""
    user = user_db.get_user(login_data.username)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误"
        )

    if not verify_password(login_data.password, user["password"]):
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误"
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=403,
            detail="用户已被禁用"
        )

    # 创建令牌
    access_token = create_access_token({"sub": user["username"]})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user.get("id", login_data.username),
            username=user["username"],
            email=user.get("email"),
            nickname=user.get("nickname"),
            created_at=user.get("created_at", datetime.now().isoformat()),
            is_active=True
        )
    )


def get_user_by_token(token: str) -> Optional[UserResponse]:
    """通过令牌获取用户"""
    try:
        payload = decode_token(token)
        username = payload.get("sub")

        if username:
            user = user_db.get_user(username)
            if user:
                return UserResponse(
                    id=user.get("id", username),
                    username=user["username"],
                    email=user.get("email"),
                    nickname=user.get("nickname"),
                    created_at=user.get("created_at", datetime.now().isoformat()),
                    is_active=user.get("is_active", True)
                )
    except:
        pass

    return None
