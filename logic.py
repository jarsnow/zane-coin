import discord
from dotenv import load_dotenv
import os
import sqlite3
import time
import datetime
import random

class MyClient(discord.Client):

    async def on_ready(self):
        # isolation
        self.connection = sqlite3.connect("user_info_database.db", isolation_level=None)
        # auto commit things to the database
        self.cursor = self.connection.cursor()
        # setup database if it does not exist
        setup_command =    "CREATE TABLE IF NOT EXISTS Users (\
                            UID INT PRIMARY KEY,\
                            CoinCount INT(255),\
                            TimeLastCoinsAwarded TEXT(512),\
                            TimeLastCoinsDeducted TEXT(512));"
        self.cursor.execute(setup_command)
        print(f'Now running as {self.user}...')

    async def on_message(self, message):
        author = message.author
        content = message.content
        channel = message.channel

        # check if the message is for the bot
        if not await self.is_message_for_bot(content, channel):
            return

        await self.add_user_to_database_if_not_in_users(author.id)
        
        # remove prefix
        command = content[len(prefix) + 1:] # len('zc ') = len(prefix) + len of the space = 3
        
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
        
        # zane coin bot doesn't like getting pinged
        if f"<@{this_bot_uid}" in message_string:
            return "don't ping me"

        commands = {
            "balance" : self.get_user_coins_response,
            "+1" : self.user_awards_user_with_coin,
            "-1" : self.user_deducts_user_coin,
            "rank" : self.get_leaderboard_response,
            "status" : self.get_status_response,
            "coinflip" : self.coinflip,
            "bless" : self.debug
        }

        # get the command by the first string of the message
        user_command = message_string.split(" ")[0]
        
        # command cannot be found
        if user_command not in list(commands.keys()):
            return "what?"
        
        # formatting
        command_to_run = commands[user_command]
        command_out = await command_to_run(message_string, user_message)
        # end early if there's no message
        if command_out is None:
            return
        uid = user_message.author.id
        name = await self.get_username_from_uid(uid, user_message)
        out = f"**{name}:\n**" + command_out
        return out

    async def add_user_to_database_if_not_in_users(self, user_uid):
        # get epoch time in seconds
            epoch_time = int(time.time())
            # store a new user into the database
            # make a new list of the last times they gave a coin
            # initialize to all zeroes so the user can give x amount away at the start
            zeroes = [0] * coin_max
            coin_add_cd_list_as_string = await self.convert_int_list_to_string_list(zeroes)
            coin_deduct_cd_list_as_string = await self.convert_int_list_to_string_list([0])

            self.cursor.execute(f"INSERT OR IGNORE INTO Users (UID, CoinCount, TimeLastCoinsAwarded, TimeLastCoinsDeducted)\
                VALUES ({user_uid}, 0, '{coin_add_cd_list_as_string}', '{coin_deduct_cd_list_as_string}');")

    async def get_user_coins_response(self, message_string, user_message):
        user_uid = user_message.author.id
            
        # get coin count from tables
        coins = await self.get_coin_count_from_uid(user_uid)

        # special case if coins is zero
        if coins == 0:
            return f'you have no coins... get your money up.'

        # print normal output for users with more than one coin
        # add flavor text to ending
        flavor_text = await self.get_flavor_text_from_coin_count(coins)
        return f'you have {coins} coin{"s" if coins != 0 else ""}. ' + flavor_text        
    
    async def get_uids_from_message_string(self, message_str):
        uids = []

        while ("<@") in message_str:
            # remove everything to the left of the <@, including the <@
            index = message_str.index("<@")
            message_str = message_str[index + 2:]
            # uids are length 18
            uid = 0
            try:
                uid = int(message_str[:18])
            except:
                break
            
            uids.append(uid)

        return uids
    async def convert_string_list_to_int_list(self, string_of_times):
        # assume it is in "[(int),(int),(int)]" format
        # return list of ints
        return [int(x) for x in string_of_times.strip("[]'").split(",")]

    async def convert_int_list_to_string_list(self, list_of_times):
        # assume list of ints
        # return string in "[(int),(int),(int)]" format

        # remove beginning and ending brackets
        return str(list_of_times)

    async def get_flavor_text_from_coin_count(self, coin_count):
        texts = {
                -1:'you are deep in zebt. how did this happen',
                0:'get your money up man.',
                1:'youi need to get a job, bum.',
                2:'you are still broke, and a bum.',
                3:'still pooooor!!!! lol',
                5:'it\'s better than nothing I guess.',
                7:'you are moving up in zociety.',
                10:'big money moves.',
                15:'you are rich rich, time to buy zounter ztrike cases',
                25:'you are a zane coin millionaire (zillionaire)'
                }

        # find the maximum value that the coin count rounds down to
        for val in list(texts.keys()):
            if coin_count <= val:
                return texts[val]
        
        # return the last one if they are over the last case value
        return list(texts.values())[-1]

    async def coinflip(self, message_string, user_message):
        uid = user_message.author.id

        coins = await self.get_coin_count_from_uid(uid)

        if coins <= 0:
            return f"you cannot gamble with {coins} coins LMAOO"

        args = []
        wager = 0
        user_choice = ""
        # check user input
        try:
            # remove the 'zc'
            args = message_string.split(" ")[1:]
            wager = int(args[0])
            user_choice = args[1]
        except Exception as e:
            return "stop gambling"
        
        # check user input again
        if not(user_choice == "heads" or user_choice == "tails"):
            return "pick heads or tails man"

        if wager <= 0:
            return "you can't wager less than or equal to zero coins..."

        if wager > coins:
            return "you do NOT have that many coins to wager..."

        bot_choice = "heads" if random.randint(0,1) == 0 else "tails"
        
        if bot_choice == user_choice:
            # add coins
            await self.change_user_coins_by_num(uid, wager)
            return f"I flipped a **{bot_choice}**, and you've WON {wager}... you're at {coins + wager} coins now..."
        else:
            await self.change_user_coins_by_num(uid, -1 * wager)
            return f"I flipped a **{bot_choice}**... you LOST {wager}... you're at {coins - wager} currently now.."

    async def get_coin_count_from_uid(self, UID):
        get_coin_query = f"SELECT CoinCount FROM Users WHERE UID = {UID}"
        self.cursor.execute(get_coin_query)
        return int(self.cursor.fetchone()[0])

    async def change_user_coins_by_num(self, uid, change):
        query_decrement_target_coins =    f"UPDATE Users\
                                            SET CoinCount = CoinCount + {change}\
                                            WHERE UID = {uid};"

        self.cursor.execute(query_decrement_target_coins)

    async def set_user_coins_by_num(self, uid, num):
        query_decrement_target_coins =    f"UPDATE Users\
                                            SET CoinCount = {num}\
                                            WHERE UID = {uid};"

        self.cursor.execute(query_decrement_target_coins)

    async def debug(self, message_string, user_message):
        uid = user_message.author.id
        if uid != mod_uid:
            return "nice try lol"
        

        # get uids
        uids = await self.get_uids_from_message_string(message_string)
        target_uid = uids[0]

        args = message_string.strip().split(" ")[1:] # skip the zc
        count = int(args[1])

        await self.set_user_coins_by_num(target_uid, count)

        name = await self.get_username_from_uid(target_uid, user_message)
        
        return f"**{name}** now has {count} coins... truly an act of zod"

    async def user_awards_user_with_coin(self, message_string, user_message):
        user_uid = user_message.author.id

        # check if the time of user's oldest awarded coin 
        query_get_coin_awarded_times = f"SELECT TimeLastCoinsAwarded FROM Users WHERE UID = {user_uid};"
        self.cursor.execute(query_get_coin_awarded_times)
        awarded_times = self.cursor.fetchone()[0]

        if(awarded_times is None):
            return 

        time_list = await self.convert_string_list_to_int_list(awarded_times)
        oldest_awarded = time_list[0]

        # get current epoch time
        curr_time = int(time.time())
        # check if the user is not able to award a coin
        if oldest_awarded + award_cooldown >= curr_time:
            time_remaining_int = oldest_awarded + award_cooldown - curr_time
            time_remaining_str = datetime.timedelta(seconds=time_remaining_int)
            return f'you must wait {time_remaining_str} until you can award another coin.'
        
        
        # get uids
        uids = await self.get_uids_from_message_string(message_string)
        target_uid = uids[0]

        # ensure the target user is in the database
        await self.add_user_to_database_if_not_in_users(target_uid)

        # check to make sure that a sure isn't giving a coin to themselves
        if user_uid == target_uid:
            return f"you CANNOT give a coin to yourself... greedy bastard..."
        

        # pop the first index off, then append the current time
        time_list.pop(0)
        time_list.append(curr_time)

        # replace the value in the sql database
        new_str_list_val = await self.convert_int_list_to_string_list(time_list)
        query_replace_awarded_times = f"UPDATE Users SET TimeLastCoinsAwarded = '{new_str_list_val}' WHERE UID = {user_uid};"
        self.cursor.execute(query_replace_awarded_times)
        
        target_name = await self.get_username_from_uid(target_uid, user_message)
        
        # random chance for +1 to be +10
        if random.random() < lucky_chance:
            await self.change_user_coins_by_num(target_uid, 10)
            await self.change_user_coins_by_num(user_uid, 2)
            return f"you have given... TEN COINS! TO **{target_name}** WOW!! SO LUCKY AND GENEROUS!\n\
            YOU GET TWO COINS FOR YOURSELF TOO! WOOHOO!"

        await self.change_user_coins_by_num(target_uid, 1)
        return f"you have given one coin to **{target_name}** how generous of you"

    async def user_deducts_user_coin(self, message_string, user_message):
        user_uid = user_message.author.id

        # check if the time of user's oldest awarded coin 
        query_get_coin_deducted_times = f"SELECT TimeLastCoinsDeducted FROM Users WHERE UID = {user_uid};"
        self.cursor.execute(query_get_coin_deducted_times)
        deducted_times = self.cursor.fetchone()[0]

        if(deducted_times is None):
            return 

        time_list = await self.convert_string_list_to_int_list(deducted_times)
        oldest_deducted = time_list[0]

        # get current epoch time
        curr_time = int(time.time())
        # check if the user is not able to award a coin
        if oldest_deducted + deducting_cooldown >= curr_time:
            time_remaining_int = oldest_deducted + deducting_cooldown - curr_time
            time_remaining_str = datetime.timedelta(seconds=time_remaining_int)
            return f'you must wait {time_remaining_str} until you can deduct another user\'s coins... why must your heart be so gray...'
        
                
        # get uids
        uids = await self.get_uids_from_message_string(message_string)
        target_uid = uids[0]

        # ensure the target user is in the database
        await self.add_user_to_database_if_not_in_users(target_uid)

        # check to make sure that a user isn't taking away a coin from themselves
        if user_uid == target_uid:
            return f"take a coin away from yourself? do you resent your state of being? are you okay?..."



        # pop the first index off, then append the current time
        time_list.pop(0)
        time_list.append(curr_time)

        # replace the value in the sql database
        new_str_list_val = await self.convert_int_list_to_string_list(time_list)
        query_replace_awarded_times = f"UPDATE Users SET TimeLastCoinsDeducted = '{new_str_list_val}' WHERE UID = {user_uid};"
        self.cursor.execute(query_replace_awarded_times)
        
        target_name = await self.get_username_from_uid(target_uid, user_message)
        # I guess this is unlucky
        if random.random() < lucky_chance:
            # take 5 away from the caller, give 3 to target
            await self.change_user_coins_by_num(user_uid, -5)
            await self.change_user_coins_by_num(target_uid, 3)
            return f"WOW you are so rude... you have been FINED **FIVE** of *YOUR* COINS!\n\
                    I will have mercy on **{target_name}** and give them three coins instead..."
        
        await self.change_user_coins_by_num(target_uid, -1)
        return f"you have taken away a coin from **{target_name}**... why must your heart be so evil..."
    
    async def get_leaderboard_response(self, message_string, user_message):
        user_uid = user_message.author.id

        highest_least_shown = 5

        query_get_uid_coins_descending = "SELECT UID, CoinCount\
                                            FROM Users \
                                            ORDER BY CoinCount DESC \
                                            LIMIT 5;"

        self.cursor.execute(query_get_uid_coins_descending)
        results = self.cursor.fetchall()

        # rare case that there's less than 6 people when called
        if len(results) < highest_least_shown:
            return "no"

        output = ""

        # format leaderboard as
        # 1. @jarsnow has 3 coins.
        # 2. @notjarsnow has 2 coins.
        # show top, bottom, and the calling user if they aren't in either of the three
        output += f"the top {highest_least_shown} players in zociety:\n"
        for i, result in enumerate(results[:highest_least_shown]):
            UID, CoinCount = result[0], result[1]
            target_name = ""
            try:
                target_name = await self.get_username_from_uid(UID, user_message)
            except Exception as e:
                target_name = "idk who this is"
            output += (f"{i + 1}. **{target_name}** has {CoinCount} coins. \n")
        
        output += "...\n"
        output += f"the bottom {highest_least_shown} brokest server members:\n"

        query_get_uid_coins_asc = "SELECT UID, CoinCount\
                                            FROM Users \
                                            ORDER BY CoinCount ASC\
                                            LIMIT 5;"

        self.cursor.execute(query_get_uid_coins_asc)
        results = self.cursor.fetchall()
        # bottom count
        for i, result in enumerate(results[-highest_least_shown:]):
            UID, CoinCount = result[0], result[1]
            target_name = ""
            try:
                target_name = await self.get_username_from_uid(UID, user_message)
            except Exception as e:
                target_name = "(probably some bot)"     
            output += (f"{i}. **{target_name}** has {CoinCount} coins. \n")

        return output
    
    async def get_status_response(self, message_string, user_message): 
        user_uid = user_message.author.id

        # get the timers for users 
        query_get_coin_awarded_times = f"SELECT TimeLastCoinsAwarded FROM Users WHERE UID = {user_uid};"
        self.cursor.execute(query_get_coin_awarded_times)
        awarded_times = self.cursor.fetchone()[0]

        if(awarded_times is None):
            return

        time_list = await self.convert_string_list_to_int_list(awarded_times)
        curr_time = int(time.time())
        HOUR_IN_SECONDS = 60 * 60
        
        # let the user view the cooldown for awarding a coin
        # format is
        #coin1 cooldown: 12:02:04 [############------------]
        #coin2 cooldown: READY
        result = ""
        for i, time_value in enumerate(time_list):
            result += f"Coin {i+ 1} Cooldown: "
            seconds_remaining = time_value + award_cooldown - curr_time 
            if (seconds_remaining <= 0):
                result += "READY"
            else:
                # add time remaining
                time_remaining_str = str(datetime.timedelta(seconds=seconds_remaining))
                result += time_remaining_str + " | "
                # add loading bar
                # add one tag for each hour increment 
                num_left = seconds_remaining // HOUR_IN_SECONDS + 1
                # cap to 24 hashtags
                num_left = 24 if num_left > 24 else num_left
                result += "["
                result += "=" * (24 - num_left)
                result += "-" * num_left
                result += "]"
            result += "\n"

        return result
    

    async def get_username_from_uid(self, UID, user_message):
        guild = user_message.guild
        member = await guild.fetch_member(UID)
        name = member.name
        return name

    async def is_message_for_bot(self, content, channel):
        # check if command is ran
        content = content.lower()
        return f"{prefix} " in content and content.index(f"{prefix} ") == 0 and channel.id == usable_channel_id
    
def setup():
    # load discord token from .env file
    load_dotenv()
    global discord_token
    discord_token = os.getenv('DISCORD_TOKEN')

    # load groq token from .env file
    global groq_token
    groq_token = os.getenv('GROQ_API_KEY')
    
    # used for quip
    global this_bot_uid
    this_bot_uid = int(os.getenv('BOT_UID'))
    
    global usable_channel_id
    usable_channel_id = int(os.getenv('CHANNEL_ID'))

    global mod_uid
    mod_uid = int(os.getenv('MOD_UID'))

    # set bot prefix
    global prefix
    prefix = 'zc'

    # set the maximum amount of coins you can hold onto
    global coin_max
    coin_max = 3

    # an award must be at least a day after the oldest one, up to three
    global award_cooldown
    SECONDS_IN_ONE_DAY = 86400
    award_cooldown = SECONDS_IN_ONE_DAY

    # 12 hr cooldown for deducting a coin
    global deducting_cooldown
    deducting_cooldown = SECONDS_IN_ONE_DAY / 2
    
    # set chance for +1 to be a +10 instead
    global lucky_chance
    lucky_chance = 0.05


def main():

    setup()

    # setup discord wrapper
    intents = discord.Intents.default()
    intents.message_content = True
    client = MyClient(intents=intents)

    
    client.run(discord_token)


if __name__ == "__main__":
    main()
