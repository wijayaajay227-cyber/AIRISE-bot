# =============================================================================
# telegram_bot.py - Bot Telegram untuk Crypto Analyzer (FIXED VERSION)
# =============================================================================

import asyncio
import logging
import os
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Setup logging dengan format yang lebih baik
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# KONFIGURASI
# =============================================================================

# Token dari BotFather - Gunakan environment variable
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Chat ID untuk notifikasi
ADMIN_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Database sederhana untuk subscriber (gunakan file JSON)
SUBSCRIBERS_FILE = os.path.join(os.path.dirname(__file__), "subscribers.json")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def load_subscribers() -> Dict[str, List[str]]:
    """Load subscribers from file"""
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_subscribers(subscribers: Dict[str, List[str]]) -> None:
    """Save subscribers to file"""
    try:
        with open(SUBSCRIBERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(subscribers, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Error saving subscribers: {e}")

def format_number(num: float) -> str:
    """Format number with commas"""
    if num is None:
        return "0.00"
    return f"{num:,.2f}"

def format_percentage(num: float) -> str:
    """Format percentage"""
    if num is None:
        return "0.00%"
    return f"{num:+.2f}%"

# =============================================================================
# HANDLERS
# =============================================================================

class BotHandlers:
    """All bot command handlers"""
    
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user = update.effective_user
        if not user:
            return
            
        first_name = user.first_name or "User"
        
        welcome_text = f"""
🤖 <b>Crypto Futures Analyzer Bot</b>

Halo <b>{first_name}</b>! 👋

Saya adalah bot analisis crypto yang membantu Anda:
📊 Menganalisis pair crypto
📈 Mendapatkan sinyal trading
📉 Melakukan backtesting
📱 Mendapatkan notifikasi real-time

<b>🚀 Commands:</b>
/analyze &lt;symbol&gt; &lt;tf&gt; - Analisis pair
/backtest &lt;symbol&gt; - Backtesting
/market - Market overview
/subscribe &lt;symbol&gt; - Subscribe sinyal
/unsubscribe - Berhenti subscribe
/settings - Pengaturan
/help - Bantuan

<b>📝 Contoh:</b>
/analyze BTC/USDT 1h
/backtest ETH/USDT

<b>⚡️ Quick Analysis:</b>
        """
        
        # Quick analysis buttons
        keyboard = [
            [
                InlineKeyboardButton("BTC/USDT", callback_data="analyze_BTC/USDT"),
                InlineKeyboardButton("ETH/USDT", callback_data="analyze_ETH/USDT"),
                InlineKeyboardButton("SOL/USDT", callback_data="analyze_SOL/USDT")
            ],
            [
                InlineKeyboardButton("📊 Market Overview", callback_data="market"),
                InlineKeyboardButton("📈 Top Gainers", callback_data="top_gainers")
            ],
            [
                InlineKeyboardButton("🔔 Subscribe Notifications", callback_data="subscribe_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        # Welcome message to admin
        if ADMIN_CHAT_ID and str(user.id) == ADMIN_CHAT_ID:
            await update.message.reply_text(
                "🔔 <b>Admin Mode Active</b>\n\n"
                "Anda adalah admin bot. Anda akan menerima semua notifikasi penting.",
                parse_mode='HTML'
            )
    
    @staticmethod
    async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        help_text = """
📚 <b>Panduan Lengkap Bot</b>

<b>🔍 /analyze [symbol] [timeframe]</b>
Analisis teknikal lengkap
Contoh: <code>/analyze BTC/USDT 1h</code>

<b>📈 /backtest [symbol]</b>
Jalankan backtesting
Contoh: <code>/backtest ETH/USDT</code>

<b>📊 /market</b>
Lihat overview market

<b>🏷️ /subscribe [symbol]</b>
Subscribe notifikasi sinyal
Contoh: <code>/subscribe BTC/USDT</code>

<b>🔕 /unsubscribe</b>
Berhenti dari notifikasi

<b>⚙️ /settings</b>
Pengaturan bot

<b>📊 Timeframe yang tersedia:</b>
1m, 5m, 15m, 1h, 4h, 1d, 1w

<b>🏦 Exchange yang didukung:</b>
• Binance Futures
• Bybit
• OKX

<b>📈 Indikator yang digunakan:</b>
• EMA (9, 21, 50, 200)
• RSI (7, 14)
• MACD
• Bollinger Bands
• Stochastic
• ADX
• Volume Analysis

<b>💡 Tips:</b>
• Gunakan timeframe 1h atau 4h untuk sinyal yang lebih akurat
• Selalu konfirmasi dengan analisis fundamental
• Gunakan manajemen risiko yang baik
        """
        await update.message.reply_text(help_text, parse_mode='HTML')
    
    @staticmethod
    async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /analyze command"""
        args = context.args
        
        if not args:
            # Tampilkan keyboard untuk memilih pair
            keyboard = [
                [
                    InlineKeyboardButton("BTC/USDT", callback_data="analyze_BTC/USDT"),
                    InlineKeyboardButton("ETH/USDT", callback_data="analyze_ETH/USDT")
                ],
                [
                    InlineKeyboardButton("SOL/USDT", callback_data="analyze_SOL/USDT"),
                    InlineKeyboardButton("BNB/USDT", callback_data="analyze_BNB/USDT")
                ],
                [
                    InlineKeyboardButton("XRP/USDT", callback_data="analyze_XRP/USDT"),
                    InlineKeyboardButton("DOGE/USDT", callback_data="analyze_DOGE/USDT")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "📊 <b>Pilih Pair untuk Analisis:</b>",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            return
        
        symbol = args[0].upper()
        timeframe = args[1].upper() if len(args) > 1 else "1H"
        
        # Validasi timeframe
        valid_timeframes = ["1M", "5M", "15M", "1H", "4H", "1D", "1W"]
        if timeframe not in valid_timeframes:
            await update.message.reply_text(
                f"❌ Timeframe '{timeframe}' tidak valid.\n"
                f"Pilih salah satu: {', '.join(valid_timeframes)}"
            )
            return
        
        # Kirim pesan loading
        msg = await update.message.reply_text(
            f"⏳ Menganalisis {symbol} pada timeframe {timeframe}...\n\n"
            "🔄 Mengambil data dari exchange..."
        )
        
        try:
            # Import fungsi dari main app
            from app import get_ohlcv, add_indicators, analyze_single_timeframe
            
            # Ambil data
            df = get_ohlcv("Binance Futures", symbol, timeframe, 300)
            df = add_indicators(df)
            
            # Analisis
            signal = analyze_single_timeframe(df)
            
            # Format hasil analisis
            result_text = f"""
📊 <b>Analisis {symbol}</b>
⏱️ Timeframe: {timeframe}
🕐 Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<b>🎯 Sinyal: {signal.direction}</b>
📊 Score: {signal.score}
🎯 Confidence: {signal.confidence}

<b>💰 Level Entry:</b>
• Entry: ${format_number(signal.entry)}
• SL: ${format_number(signal.sl)}
• TP1: ${format_number(signal.tp1)}
• TP2: ${format_number(signal.tp2)}

<b>📈 Indikator:</b>
• RSI: {signal.rsi_value:.1f} ({signal.rsi_status})
• MACD: {signal.macd_status}
• BB: {signal.bb_status}
• Stochastic: {signal.stoch_status}
• Trend Strength: {signal.trend_strength}

<b>📋 Alasan:</b>
"""
            for reason in signal.reasons[:5]:
                result_text += f"• {reason}\n"
            
            # Tambahan info
            risk = abs(signal.entry - signal.sl)
            rr1 = abs(signal.tp1 - signal.entry) / risk if risk and risk > 0 else 0
            rr2 = abs(signal.tp2 - signal.entry) / risk if risk and risk > 0 else 0
            result_text += f"\n<b>📊 Risk/Reward:</b>\n"
            result_text += f"• TP1: {rr1:.1f}R\n"
            result_text += f"• TP2: {rr2:.1f}R"
            
            # Keyboard buttons
            keyboard = [
                [
                    InlineKeyboardButton("📈 Detail", callback_data=f"detail_{symbol}"),
                    InlineKeyboardButton("📊 Chart", callback_data=f"chart_{symbol}_{timeframe}")
                ],
                [
                    InlineKeyboardButton("🔔 Subscribe", callback_data=f"subscribe_{symbol}"),
                    InlineKeyboardButton("🔄 Refresh", callback_data=f"analyze_{symbol}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Edit pesan dengan hasil
            await msg.edit_text(
                result_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
            # Kirim notifikasi jika sinyal kuat
            if signal.direction != "HOLD" and signal.confidence in ["Tinggi", "Sangat Tinggi"]:
                notification = f"""
🚨 <b>STRONG SIGNAL</b> 🚨

Symbol: {symbol}
Direction: {signal.direction}
Confidence: {signal.confidence}
Entry: ${format_number(signal.entry)}
SL: ${format_number(signal.sl)}
TP1: ${format_number(signal.tp1)}

⚠️ <i>Gunakan manajemen risiko!</i>
                """
                await update.message.reply_text(notification, parse_mode='HTML')
                
                # Kirim ke admin juga
                if ADMIN_CHAT_ID and str(update.effective_user.id) != ADMIN_CHAT_ID:
                    try:
                        await context.bot.send_message(
                            chat_id=ADMIN_CHAT_ID,
                            text=f"📊 Signal dari @{update.effective_user.username or 'User'}\n{notification}",
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.error(f"Error sending to admin: {e}")
            
        except ImportError as e:
            await msg.edit_text(
                f"❌ Error: Modul app tidak ditemukan.\n"
                "Pastikan app.py ada di folder yang sama.\n\n"
                f"Detail: {str(e)}"
            )
            logger.error(f"Import error in analyze: {e}")
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}\n\nCoba lagi nanti.")
            logger.error(f"Error in analyze: {str(e)}")
    
    @staticmethod
    async def backtest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /backtest command"""
        args = context.args
        symbol = args[0].upper() if args else "BTC/USDT"
        
        msg = await update.message.reply_text(
            f"⏳ Running backtest for {symbol}...\n"
            "📊 Mengambil data historis..."
        )
        
        try:
            from app import get_ohlcv, run_backtest
            
            # Ambil data
            df = get_ohlcv("Binance Futures", symbol, "1h", 500)
            
            # Jalankan backtest
            result = run_backtest(df)
            
            # Format hasil
            result_text = f"""
📊 <b>Backtest Results - {symbol}</b>
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<b>📈 Performance:</b>
• Total Trades: {result.total_trades}
• Win Rate: {result.win_rate:.1f}%
• Avg Profit: {result.avg_profit_pct:.2f}%
• Profit Factor: {result.profit_factor:.2f}
• Max Profit: {result.max_profit_pct:.2f}%
• Max Loss: {result.max_loss_pct:.2f}%

<b>💰 Capital Growth:</b>
• Initial: $10,000.00
• Final: ${format_number(result.equity_curve[-1] if result.equity_curve else 10000)}
• Return: {((result.equity_curve[-1]/10000)-1)*100 if result.equity_curve else 0:.1f}%

<b>📊 Trade Summary:</b>
• Winning: {result.winning_trades}
• Losing: {result.losing_trades}
            """
            
            await msg.edit_text(result_text, parse_mode='HTML')
            
            # Kirim equity curve sebagai chart (opsional)
            if result.equity_curve and len(result.equity_curve) > 1:
                try:
                    import matplotlib
                    matplotlib.use('Agg')
                    import matplotlib.pyplot as plt
                    import io
                    
                    plt.figure(figsize=(10, 6))
                    plt.plot(result.equity_curve)
                    plt.title(f"Equity Curve - {symbol}")
                    plt.xlabel("Trade Number")
                    plt.ylabel("Capital (USDT)")
                    plt.grid(True)
                    
                    # Simpan ke buffer
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
                    buf.seek(0)
                    plt.close()
                    
                    # Kirim gambar
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=buf,
                        caption=f"📈 Equity Curve - {symbol}"
                    )
                except ImportError:
                    logger.warning("matplotlib not installed, skipping chart")
                except Exception as e:
                    logger.error(f"Error generating chart: {e}")
            
        except ImportError as e:
            await msg.edit_text(
                f"❌ Error: Modul app tidak ditemukan.\n"
                f"Detail: {str(e)}"
            )
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")
            logger.error(f"Error in backtest: {str(e)}")
    
    @staticmethod
    async def market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /market command"""
        msg = await update.message.reply_text("⏳ Fetching market data...")
        
        try:
            from app import get_exchange
            from app import POPULAR_SYMBOLS
            
            exchange = get_exchange("Binance Futures")
            market_data = []
            
            for symbol in POPULAR_SYMBOLS[:10]:
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    change_24h = ticker.get('percentage', 0)
                    market_data.append({
                        'symbol': symbol,
                        'price': ticker.get('last', 0),
                        'change': change_24h,
                        'volume': ticker.get('quoteVolume', 0),
                        'high': ticker.get('high', 0),
                        'low': ticker.get('low', 0)
                    })
                except Exception as e:
                    logger.error(f"Error fetching {symbol}: {e}")
                    continue
            
            # Format market overview
            market_text = "📊 <b>Market Overview</b>\n"
            market_text += f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Sort by change
            market_data.sort(key=lambda x: x['change'] if x['change'] is not None else 0, reverse=True)
            
            for data in market_data[:10]:
                change = data['change'] if data['change'] is not None else 0
                emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                trend = "📈" if change > 2 else "📉" if change < -2 else "➡️"
                
                market_text += f"{emoji} <b>{data['symbol']}</b>\n"
                market_text += f"   Price: ${format_number(data['price'])}\n"
                market_text += f"   {trend} 24h: {format_percentage(change)}\n"
                market_text += f"   Volume: ${data['volume']/1e6:.1f}M\n\n"
            
            # Keyboard untuk refresh
            keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="market")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await msg.edit_text(market_text, parse_mode='HTML', reply_markup=reply_markup)
            
        except ImportError as e:
            await msg.edit_text(
                f"❌ Error: Modul app tidak ditemukan.\n"
                f"Detail: {str(e)}"
            )
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")
            logger.error(f"Error in market: {str(e)}")
    
    @staticmethod
    async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /subscribe command"""
        args = context.args
        user = update.effective_user
        if not user:
            return
            
        user_id = str(user.id)
        
        if not args:
            # Tampilkan keyboard untuk pilih pair
            keyboard = [
                [
                    InlineKeyboardButton("BTC/USDT", callback_data="subscribe_BTC/USDT"),
                    InlineKeyboardButton("ETH/USDT", callback_data="subscribe_ETH/USDT")
                ],
                [
                    InlineKeyboardButton("SOL/USDT", callback_data="subscribe_SOL/USDT"),
                    InlineKeyboardButton("BNB/USDT", callback_data="subscribe_BNB/USDT")
                ],
                [
                    InlineKeyboardButton("📊 All Signals", callback_data="subscribe_all"),
                    InlineKeyboardButton("🔕 Unsubscribe", callback_data="unsubscribe")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🔔 <b>Subscribe to Notifications</b>\n\n"
                "Pilih pair untuk menerima notifikasi sinyal:\n"
                "• Sinyal akan dikirim saat confidence Tinggi/Sangat Tinggi\n"
                "• Notifikasi mencakup entry, SL, dan TP\n\n"
                "📌 Pilih pair di bawah:",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            return
        
        symbol = args[0].upper()
        
        # Load subscribers
        subscribers = load_subscribers()
        if user_id not in subscribers:
            subscribers[user_id] = []
        
        if symbol not in subscribers[user_id]:
            subscribers[user_id].append(symbol)
            save_subscribers(subscribers)
            message = f"✅ Subscribed to {symbol} notifications!"
        else:
            message = f"ℹ️ Already subscribed to {symbol}"
        
        await update.message.reply_text(
            f"{message}\n\n"
            "🔔 Anda akan menerima notifikasi saat ada sinyal kuat.\n"
            f"📊 Pair: {', '.join(subscribers[user_id])}"
        )
    
    @staticmethod
    async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /unsubscribe command"""
        user = update.effective_user
        if not user:
            return
            
        user_id = str(user.id)
        
        subscribers = load_subscribers()
        if user_id in subscribers:
            subscribers[user_id] = []
            save_subscribers(subscribers)
            await update.message.reply_text(
                "🔕 You have been unsubscribed from all notifications.\n\n"
                "Untuk subscribe lagi, gunakan /subscribe"
            )
        else:
            await update.message.reply_text(
                "ℹ️ You are not subscribed to any notifications.\n\n"
                "Gunakan /subscribe untuk mulai subscribe."
            )
    
    @staticmethod
    async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /settings command"""
        user = update.effective_user
        if not user:
            return
            
        user_id = str(user.id)
        subscribers = load_subscribers()
        subs = subscribers.get(user_id, [])
        
        keyboard = [
            [
                InlineKeyboardButton("⚙️ Default Timeframe", callback_data="set_tf"),
                InlineKeyboardButton("📊 Default Exchange", callback_data="set_exchange")
            ],
            [
                InlineKeyboardButton("🎯 Risk Level", callback_data="set_risk"),
                InlineKeyboardButton("🔔 Notification Settings", callback_data="notif_settings")
            ],
            [
                InlineKeyboardButton("📋 My Subscriptions", callback_data="my_subs"),
                InlineKeyboardButton("🔕 Unsubscribe All", callback_data="unsubscribe_all")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚙️ <b>Settings</b>\n\n"
            f"📊 Your Subscriptions: {', '.join(subs) if subs else 'None'}\n"
            f"📈 Total Subscribed: {len(subs)} pair\n\n"
            "Pilih pengaturan yang ingin diubah:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    @staticmethod
    async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all callback queries"""
        query = update.callback_query
        if not query:
            return
            
        await query.answer()
        
        data = query.data
        user = update.effective_user
        if not user:
            return
            
        user_id = str(user.id)
        
        # Analisis cepat
        if data.startswith("analyze_"):
            symbol = data.replace("analyze_", "")
            # Jalankan analisis
            await query.message.reply_text(f"⏳ Analyzing {symbol}...")
            
            # Panggil fungsi analyze dengan symbol
            context.args = [symbol, "1h"]
            await BotHandlers.analyze(update, context)
            
            await query.message.delete()
        
        # Subscribe
        elif data.startswith("subscribe_"):
            if data == "subscribe_all" or data == "subscribe_menu":
                if data == "subscribe_all":
                    # Subscribe ke semua sinyal
                    subscribers = load_subscribers()
                    if user_id not in subscribers:
                        subscribers[user_id] = []
                    if "ALL" not in subscribers[user_id]:
                        subscribers[user_id].append("ALL")
                        save_subscribers(subscribers)
                        await query.edit_message_text(
                            "✅ Subscribed to ALL signals!\n\n"
                            "Anda akan menerima semua sinyal kuat dari semua pair."
                        )
                    else:
                        await query.edit_message_text("ℹ️ Already subscribed to ALL signals")
                else:
                    # Menu subscribe
                    keyboard = [
                        [
                            InlineKeyboardButton("BTC/USDT", callback_data="subscribe_BTC/USDT"),
                            InlineKeyboardButton("ETH/USDT", callback_data="subscribe_ETH/USDT")
                        ],
                        [
                            InlineKeyboardButton("SOL/USDT", callback_data="subscribe_SOL/USDT"),
                            InlineKeyboardButton("BNB/USDT", callback_data="subscribe_BNB/USDT")
                        ],
                        [
                            InlineKeyboardButton("📊 All Signals", callback_data="subscribe_all"),
                            InlineKeyboardButton("🔕 Unsubscribe", callback_data="unsubscribe")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(
                        "🔔 <b>Subscribe to Notifications</b>\n\n"
                        "Pilih pair untuk menerima notifikasi:",
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
            
            else:
                symbol = data.replace("subscribe_", "")
                subscribers = load_subscribers()
                if user_id not in subscribers:
                    subscribers[user_id] = []
                if symbol not in subscribers[user_id]:
                    subscribers[user_id].append(symbol)
                    save_subscribers(subscribers)
                    await query.edit_message_text(
                        f"✅ Subscribed to {symbol} notifications!\n\n"
                        "🔔 Anda akan menerima notifikasi saat ada sinyal kuat."
                    )
                else:
                    await query.edit_message_text(f"ℹ️ Already subscribed to {symbol}")
        
        # Unsubscribe
        elif data == "unsubscribe" or data == "unsubscribe_all":
            subscribers = load_subscribers()
            if user_id in subscribers:
                subscribers[user_id] = []
                save_subscribers(subscribers)
                await query.edit_message_text(
                    "🔕 Unsubscribed from all notifications!"
                )
            else:
                await query.edit_message_text("ℹ️ You are not subscribed to any notifications")
        
        # Market refresh
        elif data == "market":
            await BotHandlers.market(update, context)
            await query.message.delete()
        
        # Top gainers
        elif data == "top_gainers":
            await query.edit_message_text(
                "📈 <b>Top Gainers</b>\n\n"
                "Fitur ini akan segera hadir!\n"
                "Untuk sekarang, gunakan /market untuk melihat overview.",
                parse_mode='HTML'
            )
        
        # My subscriptions
        elif data == "my_subs":
            subscribers = load_subscribers()
            subs = subscribers.get(user_id, [])
            
            if subs:
                text = f"📋 <b>Your Subscriptions</b>\n\n"
                for s in subs:
                    text += f"• {s}\n"
                text += f"\nTotal: {len(subs)} pair"
            else:
                text = "📋 <b>Your Subscriptions</b>\n\n"
                text += "❌ Anda belum subscribe ke pair apapun.\n"
                text += "Gunakan /subscribe untuk mulai."
            
            await query.edit_message_text(text, parse_mode='HTML')
        
        # Detail
        elif data.startswith("detail_"):
            symbol = data.replace("detail_", "")
            await query.edit_message_text(
                f"📈 <b>Detail Analysis - {symbol}</b>\n\n"
                "Untuk analisis lengkap:\n"
                f"<code>/analyze {symbol} 1h</code>\n\n"
                "📊 Gunakan timeframe yang berbeda:\n"
                "<code>/analyze BTC/USDT 4h</code>\n"
                "<code>/analyze BTC/USDT 1d</code>\n\n"
                "💡 Tips: Gunakan 4h atau 1d untuk trend utama.",
                parse_mode='HTML'
            )
        
        # Chart
        elif data.startswith("chart_"):
            parts = data.split("_")
            symbol = parts[1] if len(parts) > 1 else "BTC/USDT"
            tf = parts[2] if len(parts) > 2 else "1h"
            
            await query.edit_message_text(
                f"📊 <b>Chart - {symbol} ({tf})</b>\n\n"
                "📈 Untuk melihat chart:\n"
                "1. Buka TradingView\n"
                f"2. Cari {symbol}\n"
                f"3. Set timeframe {tf}\n\n"
                "🔗 Link: https://www.tradingview.com/chart/\n\n"
                "💡 Atau gunakan aplikasi web untuk chart interaktif.",
                parse_mode='HTML'
            )
        
        # Settings
        elif data.startswith("set_"):
            setting = data.replace("set_", "")
            
            if setting == "tf":
                keyboard = [
                    [
                        InlineKeyboardButton("1m", callback_data="tf_1m"),
                        InlineKeyboardButton("5m", callback_data="tf_5m"),
                        InlineKeyboardButton("15m", callback_data="tf_15m")
                    ],
                    [
                        InlineKeyboardButton("1h", callback_data="tf_1h"),
                        InlineKeyboardButton("4h", callback_data="tf_4h"),
                        InlineKeyboardButton("1d", callback_data="tf_1d")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "⚙️ <b>Set Default Timeframe</b>\n\n"
                    "Pilih timeframe default untuk analisis:",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            
            elif setting == "risk":
                keyboard = [
                    [
                        InlineKeyboardButton("🟢 Low (1%)", callback_data="risk_1"),
                        InlineKeyboardButton("🟡 Medium (2%)", callback_data="risk_2")
                    ],
                    [
                        InlineKeyboardButton("🔴 High (3%)", callback_data="risk_3"),
                        InlineKeyboardButton("⚫ Custom", callback_data="risk_custom")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "🎯 <b>Set Risk Level</b>\n\n"
                    "Pilih risk per trade yang diinginkan:",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(
                    f"⚙️ <b>Settings - {setting}</b>\n\n"
                    "Fitur ini akan segera hadir!",
                    parse_mode='HTML'
                )
        
        # Timeframe selection
        elif data.startswith("tf_"):
            tf = data.replace("tf_", "")
            await query.edit_message_text(
                f"✅ Default timeframe set to: {tf.upper()}\n\n"
                "Sekarang Anda bisa menggunakan /analyze [symbol] tanpa timeframe.\n"
                f"Contoh: <code>/analyze BTC/USDT</code>\n\n"
                f"👉 Akan menggunakan timeframe {tf.upper()} secara default.",
                parse_mode='HTML'
            )
        
        # Risk selection
        elif data.startswith("risk_"):
            risk = data.replace("risk_", "")
            if risk == "custom":
                await query.edit_message_text(
                    "⚙️ <b>Custom Risk Level</b>\n\n"
                    "Silakan kirim angka risk yang diinginkan (1-5):\n"
                    "Contoh: <code>2.5</code> untuk 2.5%",
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text(
                    f"✅ Risk level set to: {risk}%\n\n"
                    "Risk ini akan digunakan untuk perhitungan position sizing.\n"
                    "Selalu sesuaikan dengan toleransi risiko Anda.",
                    parse_mode='HTML'
                )
        
        # Notification settings
        elif data == "notif_settings":
            keyboard = [
                [
                    InlineKeyboardButton("🔊 On", callback_data="notif_on"),
                    InlineKeyboardButton("🔇 Off", callback_data="notif_off")
                ],
                [
                    InlineKeyboardButton("📊 Signal Only", callback_data="notif_signal"),
                    InlineKeyboardButton("📈 All Updates", callback_data="notif_all")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🔔 <b>Notification Settings</b>\n\n"
                "Pilih preferensi notifikasi Anda:",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                f"ℹ️ Unknown command: {data}\n\n"
                "Gunakan /help untuk melihat daftar command.",
                parse_mode='HTML'
            )

# =============================================================================
# MAIN BOT
# =============================================================================

def main() -> None:
    """Start the bot"""
    # Cek token
    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not set!")
        print("Please set your bot token in environment variable:")
        print("  export TELEGRAM_BOT_TOKEN=your_token_here")
        print("\nOr create .env file with:")
        print("  TELEGRAM_BOT_TOKEN=your_token_here")
        print("  TELEGRAM_CHAT_ID=your_chat_id_here")
        return
    
    try:
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        handlers = BotHandlers()
        
        # Command handlers
        application.add_handler(CommandHandler("start", handlers.start))
        application.add_handler(CommandHandler("help", handlers.help))
        application.add_handler(CommandHandler("analyze", handlers.analyze))
        application.add_handler(CommandHandler("backtest", handlers.backtest))
        application.add_handler(CommandHandler("market", handlers.market))
        application.add_handler(CommandHandler("subscribe", handlers.subscribe))
        application.add_handler(CommandHandler("unsubscribe", handlers.unsubscribe))
        application.add_handler(CommandHandler("settings", handlers.settings))
        
        # Callback handler
        application.add_handler(CallbackQueryHandler(handlers.callback_handler))
        
        # Start bot
        print("🤖 Starting Telegram bot...")
        print(f"✅ Bot token: {BOT_TOKEN[:10]}...")
        print("✅ Bot is running!")
        print("📱 Find your bot at: https://t.me/your_bot_username")
        print("\nPress Ctrl+C to stop")
        
        # Run the bot
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"❌ Error starting bot: {str(e)}")
        logger.error(f"Error starting bot: {str(e)}")

if __name__ == "__main__":
    main()