import discord
from dotenv import load_dotenv
import os

class MyClient(discord.Client):

    async def on_ready(self):
        print(f'Now running as {self.user}...')

    async def on_message(self, message):
        author = message.author
        content = message.content
        channel = message.channel

        # check if the message is for the bot
        if not await self.is_message_for_bot(content):
            return
        
        # remove prefix
        command = content[3:]

        # get response from command
        bot_response = await self.get_response(command, message)

        await self.send_message(bot_response, message)

    async def send_message(self, bot_response, message):
        # don't send anything if the bot has nothing to say
        if not bot_response:
            return
        
        await message.channel.send(bot_response)

    async def get_response(self, message_string, user_message):
        message_string = message_string.lower()
        
        if 'hi' in message_string or 'hello' in message_string:
            return 'hello'
        elif 'bye' in message_string:
            return 'bye'
        elif 'gn' in message_string or 'good night' in message_string:
            return 'sweet dreams my love'
        elif 'i love you' in message_string:
            return 'i love you too'
        else:
            return ""
        
    async def is_message_for_bot(self, content):
        # check if command is ran
        return f"{prefix} " in content and content.index(f"{prefix} ") == 0

def main():

    # set bot prefix
    global prefix
    prefix = 'zc'

    # setup discord wrapper
    intents = discord.Intents.default()
    intents.message_content = True
    client = MyClient(intents=intents)

    # load discord token from .env file
    load_dotenv()
    token = os.getenv('DISCORD_TOKEN')
    client.run(token)


if __name__ == "__main__":
    main()