#from telebot import TeleBot
#from telebot import apihelper
from telegram.ext import Application
from telegram.ext import ApplicationBuilder
from telegram import Update
from telegram.error import TimedOut, NetworkError, RetryAfter
from os import environ
from dotenv import load_dotenv
from agents.crewai_telemetry import *
from handlers import telegram_handlers_v2
from tools.tools import TelegramTools

import time
import google.generativeai as genai
from gemini.GeminiFactory import GeminiFactory

load_dotenv()

# Desabilita a telemetria da Crew AI
disable_crewai_telemetry()


if __name__ == "__main__":
    application = (
        ApplicationBuilder()
        .token(environ.get("BOT_TOKEN"))
        .get_updates_read_timeout(15)
        .get_updates_write_timeout(15)
        .get_updates_connect_timeout(30)
        .build()
    )
    telegram_handlers_v2.setup_handlers(application)
    # Run the bot until the user presses Ctrl-C
    while True:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        # try:
        #     application.run_polling(allowed_updates=Update.ALL_TYPES)
        # except TimedOut:
        #     # Lidar com o timeout especificamente
        #     print("Timeout occurred, attempting to continue...")
        # except RetryAfter as e:
        #     # Lidar com limitações de taxa e Retry-After
        #     print(f"Rate limits hit, sleeping for {e.retry_after} seconds")
        #     time.sleep(e.retry_after)
        # except NetworkError:
        #     # Tratar erros de rede genéricos
        #     print("Network error occurred, attempting to restart polling...")
        #     time.sleep(5)
        # except Exception as e:
        #     # Capturar qualquer outra exceção
        #     print(f"Unexpected error: {e}. Restarting polling...")
        #     time.sleep(5)
            
    
