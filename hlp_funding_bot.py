from base_config import *

class FundingBot:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running = False
        self.application = None
        
    async def start(self):
        """봇 초기화 및 시작"""
        self.application = Application.builder().token(TOKEN).build()
        
        # 기본 커맨드 핸들러 등록
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("add", self.add_coin))
        self.application.add_handler(CommandHandler("remove", self.remove_coin))
        self.application.add_handler(CommandHandler("list", self.list_coins))
        self.application.add_handler(CommandHandler("check", self.check_now))
        
        # 관리자 커맨드 핸들러 등록
        self.application.add_handler(CommandHandler("userlist", self.admin_list_users))
        self.application.add_handler(CommandHandler("send", self.admin_send))
        self.application.add_handler(CommandHandler("markdown", self.admin_markdown))
        self.application.add_handler(CommandHandler("schedule", self.admin_schedule))
        
        # 미디어 핸들러
        self.application.add_handler(MessageHandler(
            filters.Document.ALL | filters.PHOTO,
            self.handle_admin_media
        ))
        
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("봇이 시작되었습니다.")

    async def help_command(self, update, context):
        """도움말 표시"""
        help_text = (
            "🤖 펀딩비 모니터링 봇 사용법\n\n"
            "사용 가능한 명령어:\n"
            "/help - 이 도움말 메시지 표시\n"
            "/add [코인심볼] - 새로운 코인 추가 (예: /add BTC)\n"
            "/remove [코인심볼] - 코인 제거 (예: /remove BTC)\n"
            "/list - 현재 모니터링 중인 코인 목록 표시\n"
            "/check - 즉시 펀딩비 확인\n"
        )
        
        if is_admin(update.message.chat_id):
            help_text += (
                "\n관리자 명령어:\n"
                "/userlist - 전체 사용자 목록 확인\n"
                "/send [USER_ID] [메시지] - 특정 사용자에게 메시지 전송\n"
                "/markdown [USER_ID] [메시지] - 서식 있는 메시지 전송\n"
                "/schedule [날짜] [시간] [USER_ID] [메시지] - 예약 전송\n"
                "이미지/파일 전송 - 미디어에 캡션으로 /send [USER_ID] 입력"
            )
        
        await update.message.reply_text(help_text)

    async def start_command(self, update, context):
        """시작 메시지 및 사용자 등록"""
        user_id = update.message.chat_id
        username = update.message.from_user.username
        user_data = register_user(user_id, username)
        
        welcome_text = (
            "👋 안녕하세요! 펀딩비 모니터링 봇입니다.\n\n"
            "이 봇은 설정된 코인들의 펀딩비를 주기적으로 확인하여 알려드립니다.\n"
            f"기본 설정된 코인: {', '.join(user_data['coins'])}\n\n"
            "사용 가능한 명령어를 보려면 /help를 입력해주세요."
        )
        await update.message.reply_text(welcome_text)

    async def admin_list_users(self, update, context):
        """관리자용: 사용자 목록 보기"""
        if not is_admin(update.message.chat_id):
            return
            
        users = load_users()
        if not users:
            await update.message.reply_text("아직 등록된 사용자가 없습니다.")
            return
            
        message = "👥 현재 사용자 목록:\n\n"
        for uid, data in users.items():
            status = "👑" if str(uid) == ADMIN_ID else "👤"
            username = f" (@{data['username']})" if data.get('username') else ""
            coins = ", ".join(data['coins'])
            joined = data.get('joined_at', '알 수 없음')
            
            message += (
                f"{status} ID: `{uid}`{username}\n"
                f"코인 목록: {coins}\n"
                f"가입일: {joined}\n\n"
            )
        
        await update.message.reply_text(message, parse_mode='Markdown')

    async def admin_send(self, update, context):
        """관리자용: 특정 사용자에게 메시지 전송"""
        if not is_admin(update.message.chat_id):
            return
            
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "사용법: /send USER_ID 메시지\n"
                "예시: /send 123456789 안녕하세요!"
            )
            return
            
        target_id = context.args[0]
        message = ' '.join(context.args[1:])
        
        try:
            await self.application.bot.send_message(
                chat_id=target_id,
                text=f"📩 관리자 메시지:\n\n{message}"
            )
            await update.message.reply_text(f"✅ {target_id}님에게 메시지 전송 완료")
        except Exception as e:
            await update.message.reply_text(f"❌ 전송 실패: {str(e)}")

    async def admin_markdown(self, update, context):
        """관리자용: 마크다운/HTML 형식 메시지 전송"""
        if not is_admin(update.message.chat_id):
            return
            
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "사용법: /markdown USER_ID 메시지\n"
                "지원 형식:\n"
                "- *굵게* 또는 <b>굵게</b>\n"
                "- _기울임_ 또는 <i>기울임</i>\n"
                "- `코드` 또는 <code>코드</code>\n"
                "- [링크제목](url)"
            )
            return
            
        target_id = context.args[0]
        message = ' '.join(context.args[1:])
        
        try:
            await self.application.bot.send_message(
                chat_id=target_id,
                text=f"📩 관리자 메시지:\n\n{message}",
                parse_mode='Markdown'
            )
            await update.message.reply_text("✅ 메시지 전송 완료")
        except Exception as e:
            await update.message.reply_text(f"❌ 형식 오류: {str(e)}")
    async def handle_admin_media(self, update, context):
        """관리자의 미디어 파일 전송 처리"""
        if not is_admin(update.message.chat_id):
            return
            
        if not update.message.caption or not update.message.caption.startswith('/send'):
            return
            
        # /send USER_ID [caption] 형식 파싱
        args = update.message.caption.split()
        if len(args) < 2:
            await update.message.reply_text("❌ 사용자 ID를 지정해주세요")
            return
            
        target_id = args[1]
        caption = " ".join(args[2:]) if len(args) > 2 else None
        
        try:
            if update.message.photo:
                # 이미지 전송
                file_id = update.message.photo[-1].file_id
                await self.application.bot.send_photo(
                    chat_id=target_id,
                    photo=file_id,
                    caption=caption
                )
            elif update.message.document:
                # 파일 전송
                await self.application.bot.send_document(
                    chat_id=target_id,
                    document=update.message.document.file_id,
                    caption=caption
                )
            await update.message.reply_text(f"✅ 미디어 전송 완료 ({target_id})")
        except Exception as e:
            await update.message.reply_text(f"❌ 전송 실패: {str(e)}")

    async def admin_schedule(self, update, context):
        """관리자용: 메시지 예약 전송"""
        if not is_admin(update.message.chat_id):
            return
            
        if len(context.args) < 4:
            await update.message.reply_text(
                "사용법: /schedule YYYY-MM-DD HH:MM USER_ID 메시지\n"
                "예시: /schedule 2024-11-01 14:30 123456789 안녕하세요"
            )
            return
            
        try:
            schedule_time = datetime.strptime(f"{context.args[0]} {context.args[1]}", "%Y-%m-%d %H:%M")
            target_id = context.args[2]
            message = ' '.join(context.args[3:])
            
            if schedule_time < datetime.now():
                await update.message.reply_text("❌ 과거 시간으로는 예약할 수 없습니다.")
                return
            
            # 예약 작업 추가
            self.scheduler.add_job(
                self.send_scheduled_message,
                'date',
                run_date=schedule_time,
                args=[target_id, message]
            )
            
            # 예약 정보 저장
            schedules = load_schedules()
            schedules.append({
                "target_id": target_id,
                "message": message,
                "schedule_time": schedule_time.strftime("%Y-%m-%d %H:%M"),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            save_schedules(schedules)
            
            await update.message.reply_text(
                f"✅ 예약 완료\n"
                f"📅 전송 시각: {schedule_time}\n"
                f"👤 대상: {target_id}\n"
                f"📝 메시지: {message}"
            )
        except ValueError:
            await update.message.reply_text("❌ 날짜/시간 형식이 잘못되었습니다.")
        except Exception as e:
            await update.message.reply_text(f"❌ 예약 실패: {str(e)}")

    async def send_scheduled_message(self, target_id, message):
        """예약 메시지 전송"""
        try:
            await self.application.bot.send_message(
                chat_id=target_id,
                text=f"📩 예약 메시지:\n\n{message}"
            )
            logger.info(f"예약 메시지 전송 완료 (대상: {target_id})")
        except Exception as e:
            logger.error(f"예약 메시지 전송 실패: {str(e)}")

    async def add_coin(self, update, context):
        """코인 추가 커맨드 핸들러"""
        user_id = update.message.chat_id
        coins = get_user_coins(user_id)
        
        if not context.args:
            await update.message.reply_text(
                "⚠️ 사용법: /add COIN_SYMBOL\n"
                "예시: /add BTC\n\n"
                "코인 심볼을 입력해주세요."
            )
            return
            
        coin = context.args[0].upper()
        
        if coin in coins:
            await update.message.reply_text(
                f"ℹ️ {coin}은(는) 이미 모니터링 중입니다.\n"
                f"현재 모니터링 중인 코인 목록을 보려면 /list를 입력하세요."
            )
            return

        # 코인 존재 여부 확인
        async with aiohttp.ClientSession() as session:
            if not await APIHelper.verify_coin(session, coin):
                await update.message.reply_text(
                    f"❌ {coin}은(는) 지원하지 않는 코인입니다.\n"
                    "올바른 코인 심볼을 입력해주세요."
                )
                return
            
        coins.append(coin)
        update_user_coins(user_id, coins)
        await update.message.reply_text(
            f"✅ {coin}이(가) 모니터링 목록에 추가되었습니다.\n"
            f"현재 모니터링 중인 코인: {', '.join(sorted(coins))}"
        )
        logger.info(f"코인 추가됨: {coin} (사용자: {user_id})")

    async def remove_coin(self, update, context):
        """코인 제거 커맨드 핸들러"""
        user_id = update.message.chat_id
        coins = get_user_coins(user_id)
        
        if not context.args:
            await update.message.reply_text(
                "⚠️ 사용법: /remove COIN_SYMBOL\n"
                "예시: /remove BTC\n\n"
                "제거할 코인 심볼을 입력해주세요."
            )
            return
            
        coin = context.args[0].upper()
        if coin not in coins:
            await update.message.reply_text(
                f"❌ {coin}은(는) 모니터링 목록에 없습니다.\n"
                f"현재 모니터링 중인 코인 목록을 보려면 /list를 입력하세요."
            )
            return
            
        coins.remove(coin)
        update_user_coins(user_id, coins)
        await update.message.reply_text(
            f"✅ {coin}이(가) 모니터링 목록에서 제거되었습니다.\n"
            f"현재 모니터링 중인 코인: {', '.join(sorted(coins))}"
        )
        logger.info(f"코인 제거됨: {coin} (사용자: {user_id})")

    async def list_coins(self, update, context):
        """모니터링 중인 코인 목록 표시"""
        user_id = update.message.chat_id
        coins = get_user_coins(user_id)
            
        if not coins:
            await update.message.reply_text(
                "ℹ️ 현재 모니터링 중인 코인이 없습니다.\n"
                "코인을 추가하려면 /add COIN_SYMBOL 명령어를 사용하세요."
            )
            return
            
        coins = "\n".join([f"- {coin}" for coin in sorted(coins)])
        await update.message.reply_text(
            f"📋 현재 모니터링 중인 코인 목록:\n{coins}\n\n"
            "코인을 추가하려면 /add COIN_SYMBOL\n"
            "코인을 제거하려면 /remove COIN_SYMBOL\n"
            "명령어를 사용하세요."
        )

    async def check_now(self, update, context):
        """즉시 펀딩비 확인"""
        user_id = update.message.chat_id
        coins = get_user_coins(user_id)
        
        if not coins:
            await update.message.reply_text(
                "ℹ️ 현재 모니터링 중인 코인이 없습니다.\n"
                "먼저 /add 명령어로 코인을 추가해주세요."
            )
            return
            
        await update.message.reply_text("🔍 펀딩비를 확인하고 있습니다...")
        await self.send_funding_rate(user_id)

    async def get_funding_rates(self, user_id):
        """설정된 코인들의 펀딩비 조회"""
        try:
            coins = get_user_coins(user_id)
            async with aiohttp.ClientSession() as session:
                results = []
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                results.append(f"🕒 {current_time}")
                
                for coin in sorted(coins):
                    data = await APIHelper.get_coin_data(session, coin)
                    
                    if data['error']:
                        results.append(f"\n❌ {coin} 데이터 조회 중 오류가 발생했습니다")
                        continue
                        
                    if not data['exists']:
                        results.append(f"\n❌ {coin} 데이터를 찾을 수 없습니다")
                        continue
                        
                    funding_rate = data['funding_rate']
                    apr = funding_rate * 24 * 365
                    price = data['price']
                    
                    # 가격 표시 형식을 코인별로 다르게 설정
                    if coin in ['BTC']:
                        price_format = f"${price:,.2f}"
                    else:
                        price_format = f"${price:,.3f}"
                    
                    results.append(
                        f"\n{get_emoji(coin)} {coin}\n"
                        f"가격: {price_format}\n"
                        f"현재 펀딩비: {funding_rate:+.6f}%\n"
                        f"예상 APR: {apr:+.2f}%"
                    )
                
                return "".join(results)
                
        except Exception as e:
            logger.error(f"펀딩비 조회 중 오류: {str(e)}")
            return "❌ 데이터 조회 중 오류가 발생했습니다."

    async def send_funding_rate(self, user_id=None):
        """펀딩비 메시지 전송"""
        if not self._running and user_id is None:
            return
            
        try:
            users = load_users()
            if user_id is not None:
                # 특정 사용자에게만 전송
                message = await self.get_funding_rates(user_id)
                await self.application.bot.send_message(chat_id=user_id, text=message)
                logger.info(f"메시지 전송 완료 (사용자: {user_id}):\n{message}")
            else:
                # 모든 사용자에게 전송
                for uid in users.keys():
                    message = await self.get_funding_rates(uid)
                    await self.application.bot.send_message(chat_id=uid, text=message)
                    logger.info(f"메시지 전송 완료 (사용자: {uid}):\n{message}")
        except Exception as e:
            error_msg = f"메시지 전송 중 오류: {str(e)}"
            logger.error(error_msg)

    def signal_handler(self, signum, frame):
        """시그널 핸들러"""
        logger.info("종료 신호를 받았습니다.")
        self._running = False

    async def run(self):
        """봇 실행"""
        try:
            # 시그널 핸들러 설정
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            # 봇 초기화
            self._running = True
            await self.start()
            
            # 스케줄러 설정 및 시작
            self.scheduler = AsyncIOScheduler()  # 여기서 다시 초기화
            self.scheduler.add_job(
                self.send_funding_rate,
                'cron',
                minute=59,
                misfire_grace_time=None
            )
            self.scheduler.start()
            
            logger.info("봇이 시작되었습니다.")
            
            # 봇 실행 유지
            while self._running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"봇 실행 중 오류 발생: {str(e)}")
        finally:
            # 종료 처리
            if self.scheduler:
                self.scheduler.shutdown()
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
            logger.info("봇이 정상적으로 종료되었습니다.")

async def main():
    """메인 함수"""
    bot = FundingBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())