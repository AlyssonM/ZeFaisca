import json
import re
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, CallbackContext, ConversationHandler
)

from crewai import Crew, Process
from agents.agents import Agents
from tasks.tasks import InstructorTasks, AssistantTasks
from tools.tools import TelegramTools
from langchain.tools import Tool
from langchain_community.tools import DuckDuckGoSearchRun
from gemini.GeminiFactory import GeminiFactory
import logging
logging.basicConfig(filename='./example.log', encoding='utf-8', level=logging.INFO)


user_sessions = {}

LOBBY, QUIZ_CATEGORY, QUIZ_LEVEL, CONVERSATION, QUIZ_QUESTION = range(5)


def escape_markdown_v2(text):
    # escape_chars = r'{}+-.!><=#'
    # escaped_text = ''.join([f'\\{char}' if char in escape_chars else char for char in text])

    # # Usando uma expressão regular para adicionar um escape a '(' quando não é precedido por ']'
    # escaped_text = re.sub(r'(?<!\])\(', r'\\(', escaped_text)

    
    # return escaped_text
    escape_chars = r'{}+-.!><=#'
    # Primeiro escapamos todos os caracteres especiais, exceto os parênteses
    escaped_text = ''.join([f'\\{char}' if char in escape_chars else char for char in text])

    # Escapamos '*' quando não fazem parte de '**'
    # Usando expressão regular para encontrar '*' que não estão duplicados
    escaped_text = re.sub(r'(?<!\*)\*(?!\*)', r'\\*', escaped_text)
    
    # Escapamos parênteses fora dos links
    new_text = ''
    cursor = 0
    for match in re.finditer(r'\[.*?\]\(.*?\)', escaped_text):
        # Adiciona o texto antes do link, escapando os parênteses
        new_text += re.sub(r'([()])', r'\\\1', escaped_text[cursor:match.start()])
        # Adiciona o link sem modificar
        new_text += match.group(0)
        cursor = match.end()
    
    # Adiciona o restante do texto após o último link, escapando os parênteses
    new_text += re.sub(r'([()])', r'\\\1', escaped_text[cursor:])

    return new_text

search = DuckDuckGoSearchRun()
search_tool = Tool(
    name="search\_tool",
    description="A search tool used to query DuckDuckGo for search results when trying to find information from the internet.",
    func=search.run
    )

def setup_handlers(app):
    agents = []
    Instructor_agent = []
    Assistant_agent = []
    tasks = []
    assist = []
    
    # Definir comando para iniciar a conversação
    async def start_bot(update: Update, context: CallbackContext) -> None:
        user_id = str(update.effective_user.id)
        await update.message.reply_text("Please, send your Gemini Api Key with the command /set\_api followed by your Google AI Studio key, ex\.: /set\_api AIgaStcxU\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.xH1S1d6rAc8F2", parse_mode="MarkdownV2")
        
    async def set_api(update: Update, context: CallbackContext) -> int:
        user_id = str(str(update.effective_user.id))
        api_key = update.message.text.split(maxsplit=1)[1]
  
        try:
            user_sessions[user_id] = GeminiFactory(api_key)
            response = await user_sessions[user_id].send_message("""You are an electrical engineer specialized in residential electrical 
                                           projects, and in-depth knowledge of Brazilian standards NBR5410. 
                                           You will be an assistant and tutor for students on the technical course 
                                           in Electrotechnics at Ifes Guarapari. You must answer students' questions 
                                           and guide them to solve problems. AVOID give the correct answer immediately, 
                                           give tips, use questions so that the student is able to understand and solve the problem 
                                           by themselves, ONLY give the final answer only if the student claims not to be able to solve it, 
                                           after trying at least once.
                                           If the student send audio, please avoid adding timestamps to 
                                            the student's voice recordings. You will receive the audio and should 
                                            continue the dialogue naturally, as you would in a typical conversation 
                                            session. Please respond without hesitation to what the student requests.
                                           The response MUST BE compatible with MarkdownV2 formatting, adhering to the following syntax guidelines:
                                            - - item from a list `- item`
                                            - *Bold*: `*text*`
                                            - _Italic_: `_text_`
                                            - __Underline__: `__text__`
                                            - ~Strikethrough~: `~text~`
                                            - ||Spoiler||: `||text||`
                                            - Inline URL: `[link text](http://www.example.com/)`
                                            - Inline mention of a user: `[username](tg://user?id=123456789)`
                                            - Emoji via URL: `![emoji](tg://emoji?id=5368324170671202286)`
                                            - Inline fixed-width code: `` `code` ``
                                            - Pre-formatted fixed-width code block in Python:
                                                ```python
                                                python code
                                                ```
                        
                                            Please note:
                                            - Any ASCII character (codes 1-126) can be escaped with a preceding '\' to be treated as a literal character.
                                            - Inside pre and code entities, all '`' and '\' must be escaped with '\'.
                                            - Within the URL or emoji part (…), all ')' and '\' must be escaped.
                                            - In TEXT (not Inline URLs), characters '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!' MUST BE escaped with '\'.
                                            - For combined underline and italic, use italic underline or separate them with an empty bold ** to avoid formatting conflicts.
                                            - A valid emoji should be provided as an alternative in custom emoji definitions for better compatibility.
                                            - Custom emoji usage may be limited to bots with specific permissions.
                                            Whenever possible, provide references to technical standards or relevant literature.
                                            DO NOT ADD ANY COMMENTS OR ANYTHING ELSE, JUST EXACTLY THE FORMAT ABOVE. Response MUST BE always in PT-BR""")
            response_text = "API key configured successfully. Let's start!"
            # Configure o Crew AI
            nonlocal agents, Instructor_agent, Assistant_agent, tasks, assist
            agents = Agents(tools=[], api_key=api_key)
            Instructor_agent = agents.instructor_agent()
            Assistant_agent = agents.assistant_agent()
            tasks = InstructorTasks(agent=Instructor_agent)
            assist = AssistantTasks(agent=Assistant_agent)
        except Exception as e:
            response_text = f"Failed to configure API key: {str(e)}"
            print(f"Error during API configuration: {e}")

        await update.message.reply_text(response_text)
        #await update.message.delete()
        return LOBBY
    
    async def fallback(update: Update, context: CallbackContext):
        await update.message.reply_text("Workflow error. Try again....")
        return ConversationHandler.END  # ou QUIZ_CATEGORY para reiniciar o quiz
    
    # Handler para mensagens de texto que não correspondem a nenhum comando conhecido
    async def handle_unexpected_message(update: Update, context: CallbackContext):
        await update.message.reply_text("Sorry, I didn't understand that. Try a command or use /help for assistance.")

    # Handler para comandos não reconhecidos
    async def handle_unknown_command(update: Update, context: CallbackContext):
        if 'CONVERSATION' in context.user_data.get('active_state', ''):
            await update.message.reply_text(
            "You are currently in a conversation. Do you want to end it and start the quiz? Send /end_conversation to end and /startquiz to start a quiz.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("End Conversation", callback_data='cancel')],
                [InlineKeyboardButton("Continue Conversation", callback_data='continue_conversation')]
            ])
        )
        return None  # Retornar None mantém o estado atual ativo
      
        await update.message.reply_text("Unknown command. Use /help if you need assistance.")

    async def cancel(update: Update, context: CallbackContext) -> int:
        user_id = str(update.effective_user.id)
        if user_id not in user_sessions:
            await update.message.reply_text("Please, send your Gemini Api Key with the command `/set_api` followed by your Google AI Studio key, ex\.: `/set_api AIgaStcxU\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.xH1S1d6rAc8F2`", parse_mode="MarkdownV2")
            return
        session = user_sessions[user_id]
        session.status = False
        await context.bot.send_message(chat_id=user_id, text="End of conversation.")
        context.user_data['in_conversation'] = False
        return LOBBY
     
    async def handle_photo(update: Update, context: CallbackContext) -> None:
        user_id = str(update.effective_user.id)
        if user_id not in user_sessions:
            await update.message.reply_text("Please, send your Gemini Api Key with the command `/set_api` followed by your Google AI Studio key, ex\.: `/set_api AIgaStcxU\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.xH1S1d6rAc8F2`", parse_mode="MarkdownV2")
            return
        session = user_sessions[user_id]
        photo_file = await update.message.photo[-1].get_file()
        photo_path = f'./temp_{user_id}.jpg'
        await photo_file.download_to_drive(custom_path=photo_path)
        text = update.message.caption if update.message.caption else "" 
        response = await session.send_message(text, "image/jpg", photo_path)
        response_text = response['candidates'][0]['content']['parts'][0]['text']
  
        # json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        # if json_match:
        #     json_str = json_match.group(0)
        # else:
        #     raise ValueError("No valid JSON found in the response text")
        # response_json = json.loads(json_str)
        # output = response_json['output']
        try:
            await update.message.reply_text(escape_markdown_v2(response_text), parse_mode='MarkdownV2')
        except Exception as e:
            try:
                await update.message.reply_text(response_text)
            except Exception as inst:
                print(inst)

        os.remove(photo_path)

    async def handle_conversation(update: Update, context: CallbackContext) -> int:
        user_id = str(update.effective_user.id)
        if user_id not in user_sessions:
            await update.message.reply_text("Please, configure your API key with the command /set\_api followed by your Google AI Studio key, ex\.: /set\_api AIgaStcxU\.\.\.\.\.\.\.\.\.\.\.\.\.\.\.xH1S1d6rAc8F2", parse_mode="MarkdownV2")
            return
        session = user_sessions[user_id]
        if update.message.voice:
            # Processamento de mensagens de voz
            voice_file = await update.message.voice.get_file()
            voice_path = f"./voice_{user_id}.ogg"
            await voice_file.download_to_drive(custom_path=voice_path)
            response = await session.send_message('', "audio/ogg", voice_path)
            response_text = response['candidates'][0]['content']['parts'][0]['text']
            os.remove(voice_path)
     
            if session.status:
                await update.message.reply_text(escape_markdown_v2(response_text), parse_mode='MarkdownV2')
           
        else:
            # Processamento de mensagens de texto
            text = update.message.text
            response = await session.send_message(text)
            #print(session.history)
            response_text = response['candidates'][0]['content']['parts'][0]['text']
            # json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            # if json_match:
            #     json_str = json_match.group(0)
            # else:
            #     raise ValueError("No valid JSON found in the response text")
            
            # response_json = json.loads(json_str)
            #print(response_text)
            #print(escape_markdown_v2(response_text))
            await update.message.reply_text(escape_markdown_v2(response_text), parse_mode='MarkdownV2')
            
        return LOBBY

    async def send_quiz_question(update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        user_id = str(update.effective_user.id)
        session = user_sessions[user_id]
        if not isinstance(session, GeminiFactory):
            await query.message.reply_text("Session not properly configured.")
            return ConversationHandler.END
        
        nonlocal agents, Instructor_agent, Assistant_agent, tasks, assist
        Instructor_task1 = tasks.quiz(
                tools=[TelegramTools().quiz, search_tool], 
                user_id=user_id, 
                context=session.quizzes, 
                level="Intermediate",
                category="Projetos Eletricos Residenciais (NBR5410:2004)",
                callback=[])
        crew = Crew(
            agents=[Instructor_agent],
            tasks=[Instructor_task1],
            verbose=True
        )
        result = crew.kickoff()
        try:
            result_json =  re.sub(r'\}\s*[^}]*$', '}', Instructor_task1.output.raw)
            result_dict = json.loads(result_json) 
            session.quizzes.append(result_dict)
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(session.quizzes[-1]['alt1'], callback_data="alt1_correct" if session.quizzes[-1]['answer'] == "alt1" else "alt1")],
                [InlineKeyboardButton(session.quizzes[-1]['alt2'], callback_data="alt2_correct" if session.quizzes[-1]['answer'] == "alt2" else "alt2")],
                [InlineKeyboardButton(session.quizzes[-1]['alt3'], callback_data="alt3_correct" if session.quizzes[-1]['answer'] == "alt3" else "alt3")],
                [InlineKeyboardButton(session.quizzes[-1]['alt4'], callback_data="alt4_correct" if session.quizzes[-1]['answer'] == "alt4" else "alt4")]
            ])
            await update.message.reply_text(f"❓ {escape_markdown_v2(session.quizzes[-1]['question'])}", reply_markup=markup)
        except Exception as inst:
                    print(inst)
                    return ConversationHandler.END
        
        return QUIZ_QUESTION

    async def quiz_answer(update: Update, context: CallbackContext) -> int:
        user_id = str(update.effective_user.id)
        if user_id not in user_sessions:
            await context.bot.send_message(user_id, "Please, configure your API key with the command /set_api.")
            return ConversationHandler.END
        session = user_sessions[user_id]
        query = update.callback_query
        await query.answer()
        user_response = query.data  # This would be the user's selected answer
        user_answer = query.data.split('_')[0]
        if session.quizzes and 'user_alt' not in session.quizzes[-1]:
            session.quizzes[-1].setdefault('user_alt', user_answer)
            if "_correct" in query.data:
                await query.message.reply_text("Correct answer!")
                feedback_msg = "Good Work!"
            else:
                await query.message.reply_text("Incorrect answer. Try again!")
                Instructor_task2 = tasks.dar_feedback(
                tools=[], 
                user_id=user_id, 
                context=session.quizzes[-1], 
                callback=[])
                crew = Crew(
                    agents=[Instructor_agent],
                    tasks=[Instructor_task2],
                    verbose=False
                )
                result = crew.kickoff()
                feedback_msg = Instructor_task2.output.raw
                
        await query.message.reply_text(feedback_msg, parse_mode='markdown')   
        
        # Decide what to do next after an answer is given
        return LOBBY  # Optionally, continue the quiz or end the conversation

   
    app.add_handler(ConversationHandler(
        entry_points=[
            CommandHandler("start", start_bot),
            CommandHandler("set_api", set_api)
        ],
        states={
            LOBBY: [ 
                MessageHandler(filters.VOICE | filters.TEXT & ~filters.COMMAND, handle_conversation),
                CommandHandler("quiz", send_quiz_question),
                MessageHandler(filters.PHOTO, handle_photo)
            ],
            QUIZ_QUESTION: [
                CallbackQueryHandler(quiz_answer),
                CommandHandler('cancel', cancel)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.COMMAND, handle_unknown_command),
            MessageHandler(filters.TEXT, handle_unexpected_message)
        ],
        per_message=False
    ))
    