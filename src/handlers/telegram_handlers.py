import json 
import re 
from PIL import Image
import os

# Função para configurar os handlers
def setup_handlers(bot, gemini_factory):
    user_sessions = {}
    
    # Definir comando para iniciar a conversação
    @bot.message_handler(commands=['start'])
    def start_bot(message):
        chat_id = message.chat.id
        bot.send_message(chat_id, "Por favor, envie sua chave API Gemini para iniciar com o comando.")
        

    @bot.message_handler(commands=['set_api'])
    def set_api(message):
        chat_id = message.chat.id
        api_key = message.text.split(maxsplit=1)[1]  # Assume que o formato é /set_api <api_key>
        user_sessions[chat_id] = {
            "api_key": api_key,
            "gemini":  gemini_factory.create_instance(api_key),
            "status": False,
            "conversation_history": []
        }
        bot.send_message(chat_id, "Chave API configurada com sucesso! Agora você pode interagir com o bot.")
        bot.delete_message(message.chat.id, message.message_id)
        session = user_sessions[chat_id]
        gemini = session["gemini"]
        if not session["status"]:
            session["status"] = True
            response = gemini.send_message("""You are an electrical engineer specialized in residential electrical 
                                           projects, and in-depth knowledge of Brazilian standards NBR5410. 
                                           You will be an assistant and tutor for students on the technical course 
                                           in Electrotechnics at Ifes Guarapari. You must answer students' questions 
                                           and guide them to solve problems. AVOID give the correct answer immediately, 
                                           give tips, use questions so that the student is able to understand and solve the problem 
                                           by themselves, ONLY give the final answer only if the student claims not to be able to solve it, 
                                           after trying at least once.
                                           Whenever possible, provide references to technical standards or relevant literature.
                                           Your response MUST be a json formatted string with the following format:
                                           {
                                               input: transcript,
                                               output: response 
                                           }
                                           where transcript is the transcription content of the student interaction, or question (if empty, transcript = ''), 
                                           and response is your dialogue response.
                                           DO NOT ADD ANY COMMENTS OR ANYTHING ELSE, JUST EXACTLY THE FORMAT ABOVE. Response MUST BE always in PT-BR""")
            
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                response_json = json.loads(json_str)
                new_message = {
                "role": "model",
                "content": (response_json['output']),
                }
                session["conversation_history"].append(new_message)
                print(response_json['output'])
            else:
                raise ValueError("No valid JSON found in the response text")
            


    # Manipulador de mensagens de texto
    @bot.message_handler(func=lambda message: True)
    def handle_message(message):
        chat_id = message.chat.id
        if chat_id not in user_sessions:
            bot.send_message(chat_id, "Por favor, configure sua chave API com o comando /set_api.")
            return
        session = user_sessions[chat_id]
        gemini = session["gemini"]
        text = message.text
        response = []
        if session["status"]:
            try:
                response = gemini.send_message(text)
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    response_json = json.loads(json_str)
                    new_message = {
                        "role": "user",
                        "content": (response_json['input']),
                    }
                    session["conversation_history"].append(new_message)
                    new_message = {
                        "role": "model",
                        "content": (response_json['output']),
                    }
                    session["conversation_history"].append(new_message)
                    bot.send_message(chat_id, response_json['output'], parse_mode='markdown')
                else:
                    raise ValueError("No valid JSON found in the response text")
                 
            except:
                try:
                    bot.send_message(chat_id, response_json['output'])
                except Exception as inst:
                    print(inst)  
                    
        else:
            bot.send_message(chat_id, "É necessário executar o comando /start para inicializar!")

    
    # Manipulador de fotos
    @bot.message_handler(content_types=['photo'])
    def handle_photo(message):
        chat_id = message.chat.id
        if chat_id not in user_sessions:
            bot.send_message(chat_id, "Por favor, configure sua chave API com o comando /set_api.")
            return
        session = user_sessions[chat_id]
        gemini = session["gemini"]
        file_id = message.photo[-1].file_id # Pega a foto de maior resolução
        text = message.caption 

        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open('./temp.jpg', 'wb') as new_file:
            new_file.write(downloaded_file)

        image = Image.open('./temp.jpg')
        response = gemini.send_message([text, image])
        print(response.text)
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            raise ValueError("No valid JSON found in the response text")
        response_json = json.loads(json_str)
        output = response_json['output']
        try:
            bot.send_message(chat_id, output, parse_mode='markdown')
        except:
            try:
                bot.send_message(chat_id, output)
            except Exception as inst:
                print(inst)   

        os.remove('./temp.jpg')