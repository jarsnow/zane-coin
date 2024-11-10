import discord
from dotenv import load_dotenv
import os
import sqlite3
import time

class MyClient(discord.Client):

    async def on_ready(self):
        self.connection = sqlite3.connect("test_database.db")
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
        elif 'check coins' in message_string:

            user_uid = user_message.author.id
            
            # connect to table
            cursor = self.connection.cursor()
            # get coin count from tables
            cursor.execute("SELECT UID FROM USERS")
            rows = cursor.fetchall()
            for row in rows:
                # check if uid is equal to user UID
                if row[0] == user_uid:
                    # get coin count
                    cursor.execute(f"SELECT CoinCount from USERS WHERE UID = {user_uid}")
                    new_rows = cursor.fetchone()
                    coin_count = new_rows[0]
                    
                    return f'you have {coin_count} coins'
        
            # add user to db if they aren't in the table

            # get epoch time in seconds
            epoch_time = int(time.time())
            cursor.execute(f"INSERT INTO USERS (UID, CoinCount, TimeLastCoinAwarded) VALUES ({user_uid}, 0, {epoch_time})")
            self.connection.commit()
            print(f"added user to db {user_uid}")

            return f'you have no coins lol, welcome though'
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