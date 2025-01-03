import aiohttp
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import logging
from logging.handlers import RotatingFileHandler
import signal
import os
import json
import sys

# Windows에서 UTF-8 사용
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

# 기본 설정
TOKEN = '7236325983:AAG8lgDrMrpgajLtaE0IvWuS4QGMmloMqwM'
ADMIN_ID = "1388163548"  # 여기에 관리자(당신)의 채팅 ID를 입력
USERS_FILE = 'users.json'
BASE_URL = "https://api.hyperliquid.xyz/info"

# 설정 파일 경로
LOG_DIR = 'logs'
SCHEDULE_FILE = 'schedules.json'  # 예약 메시지 저장

# 기본 설정 생성
DEFAULT_CONFIG = {
    "coins": ["BTC", "ETH", "SOL"]
}

def ensure_directories():
    """필요한 디렉토리 생성"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

def load_users():
    """사용자 목록 로드"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"사용자 데이터 로드 중 오류: {str(e)}")
    return {}

def save_users(users):
    """사용자 목록 저장"""
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"사용자 데이터 저장 중 오류: {str(e)}")

def is_admin(user_id):
    """관리자 여부 확인"""
    return str(user_id) == ADMIN_ID

def register_user(user_id, username=None):
    """신규 사용자 등록 또는 기존 사용자 정보 반환"""
    users = load_users()
    user_id = str(user_id)
    
    if user_id not in users:
        users[user_id] = {
            "coins": DEFAULT_CONFIG["coins"].copy(),
            "username": username,
            "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_users(users)
        logger.info(f"새 사용자 등록됨: {user_id}")
    
    return users[user_id]

def get_user_coins(user_id):
    """사용자의 코인 목록 조회"""
    users = load_users()
    user_id = str(user_id)
    if user_id in users:
        return users[user_id]["coins"]
    return register_user(user_id)["coins"]

def update_user_coins(user_id, coins):
    """사용자의 코인 목록 업데이트"""
    users = load_users()
    user_id = str(user_id)
    if user_id in users:
        users[user_id]["coins"] = coins
        save_users(users)

def load_schedules():
    """예약된 메시지 로드"""
    try:
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"예약 데이터 로드 중 오류: {str(e)}")
    return []

def save_schedules(schedules):
    """예약된 메시지 저장"""
    try:
        with open(SCHEDULE_FILE, 'w', encoding='utf-8') as f:
            json.dump(schedules, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"예약 데이터 저장 중 오류: {str(e)}")

def setup_logging():
    """로깅 설정"""
    ensure_directories()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 이전 핸들러 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 콘솔 핸들러 (UTF-8 인코딩 설정)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 (UTF-8 인코딩으로 파일 생성)
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'funding_bot.log'),
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

# 전역 로거 설정
logger = setup_logging()

# 이모지 매핑
EMOJI_MAP = {
    'BTC': '₿',
    'ETH': '⟠',
    'SOL': '◎',
}

class APIHelper:
    @staticmethod
    async def get_coin_data(session, coin):
        """특정 코인의 데이터 조회"""
        try:
            payload = {"type": "metaAndAssetCtxs"}
            async with session.post(BASE_URL, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    market_data = data[1]
                    universe = data[0]['universe']
                    
                    for i, asset in enumerate(universe):
                        if asset['name'] == coin:
                            funding_rate = float(market_data[i]['funding']) * 100
                            price = float(market_data[i]['markPx'])
                            return {
                                'funding_rate': funding_rate,
                                'price': price,
                                'exists': True,
                                'error': None
                            }
                    
                    return {
                        'funding_rate': 0,
                        'price': 0,
                        'exists': False,
                        'error': None
                    }
                else:
                    return {
                        'funding_rate': 0,
                        'price': 0,
                        'exists': False,
                        'error': 'API 응답 오류'
                    }
        except Exception as e:
            logger.error(f"API 호출 중 오류: {str(e)}")
            return {
                'funding_rate': 0,
                'price': 0,
                'exists': False,
                'error': str(e)
            }

    @staticmethod
    async def verify_coin(session, coin):
        """코인 존재 여부 확인"""
        try:
            payload = {"type": "metaAndAssetCtxs"}
            async with session.post(BASE_URL, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    universe = data[0]['universe']
                    return any(asset['name'] == coin for asset in universe)
                return False
        except Exception as e:
            logger.error(f"코인 확인 중 오류: {str(e)}")
            return False

def get_emoji(coin):
    """코인별 이모지 반환"""
    return EMOJI_MAP.get(coin, '🪙')

# 테스트용 코드
if __name__ == "__main__":
    print("기본 설정이 완료되었습니다.")
    print(f"현재 기본 설정 코인: {DEFAULT_CONFIG['coins']}")
    print("로그 디렉토리:", LOG_DIR)
    print("사용자 데이터 파일:", USERS_FILE)
    print("예약 메시지 파일:", SCHEDULE_FILE)
    logger.info("테스트 로그 메시지")