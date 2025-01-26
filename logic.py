import discord
from dotenv import load_dotenv
import os
import sqlite3
import time
import datetime
import random
import yfinance as yf


class MyClient(discord.Client):

    async def on_ready(self):
        # isolation
        self.connection = sqlite3.connect("user_info.db", isolation_level=None)
        # auto commit things to the database
        self.cursor = self.connection.cursor()
        # setup database if it does not exist
        setup_command =    "CREATE TABLE IF NOT EXISTS Users (\
                            UID INT PRIMARY KEY,\
                            CoinCount INT(255),\
                            TimeLastCoinsAwarded TEXT(512),\
                            TimeLastCoinsDeducted TEXT(512));"

        # setup shares table
        setup_shares =  "CREATE TABLE IF NOT EXISTS Shares (\
                         UID INT,\
                         StockTicker TEXT(8),\
                         ShareCount TEXT(256));"

        self.cursor.execute(setup_command)
        self.cursor.execute(setup_shares)
        print(f'Now running as {self.user}...')

    async def on_message(self, message):
        author = message.author
        content = message.content
        channel = message.channel

        # remove prefix
        # len('zc ') = len(prefix) + len of the space = 3
        command = content[len(prefix) + 1:]

        # check if the message is for the bot
        if not await self.is_message_for_bot(content, channel):
            return

        message_in_right_channel = await self.is_message_in_allowed_channel(content, channel)

        # check for using +1, -1 outside of bot commands channel
        # use emoji reactions instead of text response
        if not await self.is_message_in_allowed_channel(content, channel):
            # add the correct emojis to the message
            emojis = tuple()

            # if it's outside of a bot commands channel, then only certain actions are allowed
            lower = content.lower()

            # zane coin bot doesn't like getting pinged
            if f"<@{this_bot_uid}" in content:
                return

            # -100 for unknown code
            return_code = -100
            if '+1' in lower:
                # try doing +1 command
                return_code = await self.user_awards_user_with_coin(lower, message, quick_response=True)
            elif '-1' in lower:
                return_code = await self.user_deducts_user_coin(lower, message, quick_response=True)
            # all possible return codes
            match (return_code):
                case -5:
                    emojis = ('zfacepalm', '❌')
                case -1:
                    emojis = ('zwhimper', '✅')
                case 0:
                    emojis = ('zunshaven', '⏳')
                case 1:
                    emojis = ('zshades', '✅')
                case 5:
                    emojis = ('zbomb', '❗')
                case 10:
                    emojis = ('zomg', '🔟')
                case _:
                    emojis = ('zquestion', '❓')

            # add emojis in order to message
            await self.add_emoji_to_message_from_name(message, emojis)

            # return, done adding emojis
            return

        # message is in appropriate channel, formulate a proper text response

        await self.add_user_to_database_if_not_in_users(author.id)

        # get response from command
        bot_response = await self.get_response(command, message)

        await self.send_message(bot_response, message)

    async def send_message(self, bot_response, message):
        # don't send anything if the bot has nothing to say
        if not bot_response:
            return

        await message.channel.send(bot_response)

    async def get_response(self, message_string, user_message):
        message_string == message_string.lower()
        # zane coin bot doesn't like getting pinged
        if f"<@{this_bot_uid}" in message_string:
            return "don't ping me"

        commands = {
            "balance": self.get_user_coins_response,
            "+1": self.user_awards_user_with_coin,
            "-1": self.user_deducts_user_coin,
            "rank": self.get_leaderboard_response,
            "status": self.get_status_response,
            "coinflip": self.coinflip,
            "bless": self.debug,
            "gift": self.user_gifts_user_coins,
            "reset_cd": self.debug_cooldown,
            "check_price": self.user_checks_price_of_share_count,
            "buy_shares": self.user_buys_shares,
            "sell_shares": self.user_sells_shares,
            "check_shares": self.user_check_shares,
            "beg": self.user_begs,
            "help": self.user_asks_help
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

    # example usage
    # (zc) help
    # (zc) help beg
    async def user_asks_help(self, message_string, user_message):
        parameters = message_string.split(' ')
        all_commands = """\
here's a list of all the usable commands
parameters in brackets -> [] are required
paremters in parenthesis -> () are optional
bolded -> can be used outside of #bot-commands

help     displays this message
**+1 [user]     gives a user a zane coin (if you have one off cooldown)**
**-1 [user]     removes a user's zane coin (if you have it off cooldown)**
gift [user] [amount]     give a user coins from your own balance, how kind

status     displays your cooldowns for +1/-1
balance     displays your liquid amount of zane coins on hand
rank     displays the server-wide ranking of user balance (shares not included)

coinflip [wager] [heads/tails]     gamble your coins away, double your coins on win, lose all on loss
beg     get yourself out of zebt.
check_price [ticker] (amount)     returns the price for a given amount of a company's shares, one if unspecified.
buy_shares [ticker] [amount]     purchase shares in a company, the amount can also be fractional.
sell_shares [ticker] [all/amount]     sell your held shares in a company, use 'all' to sell all your shares for that company.
check_shares     displays information about your owned shares

bless [user] [amount]     this command ain't for you
reset_cd [user]     also not for you lol
"""
        return all_commands

    async def get_user_total_share_worth(self, uid):
        # remove all shares that have zero share count
        delete_zeroes_query = """DELETE FROM Shares WHERE\
                                 ShareCount = '0.0';"""

        self.cursor.execute(delete_zeroes_query)

        # get all shares that the user owns
        get_shares = f"""SELECT StockTicker, ShareCount
                        FROM Shares
                        WHERE UID = {uid}"""

        # get owned shares by user
        self.cursor.execute(get_shares)
        owned_shares = self.cursor.fetchall()

        total_share_value = 0
        # add each share to output message
        for share in owned_shares:
            ticker_name, share_count = share[0], round(float(share[1]), 2)
            share_price = await self.get_share_price_from_name_amount(ticker_name, share_count)
            share_price = int(share_price)

            total_share_value += share_price

        return total_share_value

    # example usage:
    # (zc) beg
    # sometimes gives a coin to a user if they have <= 0 coins
    async def user_begs(self, message_string, user_message):
        uid = user_message.author.id

        # get user balance
        user_coins = await self.get_coin_count_from_uid(uid)

        total_share_value = await self.get_user_total_share_worth(uid)

        if user_coins <= 0 and total_share_value > 10:
            return 'are you some bezos wannabe? I know you aren\'t actually poor. \
sell some of those stocks if you really need some coin, man'

        if user_coins > 0:

            # message for <= 20 coins
            if user_coins <= 20:
                no_beg = """\
You’ve been in this place long enough, \
and I know deep down, you’re ready to move on. \
Begging for coins no longer defines you, \
and I can see that you’ve outgrown it. \
There is a fire inside you, a strength that longs for something greater, \
something beyond these moments of asking for scraps. \
You’ve carried yourself with dignity, even when times were hard, \
and that dignity is worth more than any coin someone might offer. \
It’s time for you to realize that you’ve earned the right to stand tall, \
to seek the life you truly deserve. \
You are capable of so much more than this, \
and it breaks my heart to watch you settle for less than you’re worth. \
Don’t let these moments define who you are; \
let them fuel your drive to rise up, to break free from this cycle.\n\n\
You are ready to step into a future that honors all that you’ve always been.\
"""
                return no_beg

            no_beg = """\
You don't need to beg for coins. \
It breaks my heart to see you in that position because I know you’re far above that. \
You’ve worked hard, built something meaningful, \
and have a dignity that should never be tarnished by begging. \
The wealth you possess is not just material, \
but a treasure of character, strength, and resilience. \
You deserve so much more than to stoop to such a level, \
especially when your worth is so much higher. \
It pains me to watch someone of your caliber diminish themselves like this. \
Please, you have everything you need within you, \
and asking for scraps is not the reflection of who you truly are.\n\n\
Stand tall, for you’ve already been blessed with more than most can ever dream of.\
"""
            return no_beg

        # random outcomes
        match random.randint(0, 4):
            case 0:
                # give 1 coin
                await self.change_user_coins_by_num(uid, 1)
                # new balance
                new_bal = await self.get_coin_count_from_uid(uid)
                return f'a passerby takes pity on you, and decides to give you a coin...\n\
you now have {new_bal} coins'
            case 1:
                # give 1 coin
                await self.change_user_coins_by_num(uid, 1)
                # new balance
                new_bal = await self.get_coin_count_from_uid(uid)
                return f'as you walk around the streets of san fransisco, you find a dirty coin on the ground...\n\
you now have {new_bal} coins'
            case 2:
                # give no coins
                return 'you should really get a job man.'
            case 3:
                return 'maybe try selling cans or something instead of begging.'
            case _:
                # take away 1 coin
                await self.change_user_coins_by_num(uid, -1)
                # new balance
                new_bal = await self.get_coin_count_from_uid(uid)
                return f'a rival beggar spots your setup and steals a nonexistent\
                coin from your stash, pushing you further into zebt...\n\
you now have {new_bal} coins'

    # example usage:
    # (zc) check_shares
    async def user_check_shares(self, message_string, user_message):
        uid = user_message.author.id

        # remove all shares that have zero share count
        delete_zeroes_query = """DELETE FROM Shares WHERE\
                                 ShareCount = '0.0';"""

        self.cursor.execute(delete_zeroes_query)

        # get all shares that the user owns
        get_shares = f"""SELECT StockTicker, ShareCount
                        FROM Shares
                        WHERE UID = {uid}"""

        # get owned shares by user
        self.cursor.execute(get_shares)
        owned_shares = self.cursor.fetchall()

        if len(owned_shares) == 0:
            return 'you have no shares in anything.'

        out = "current price summary:\n"
        total_share_value = 0
        # add each share to output message
        for share in owned_shares:
            ticker_name, share_count = share[0], round(float(share[1]), 2)
            share_price = await self.get_share_price_from_name_amount(ticker_name, share_count)
            share_price = int(share_price)

            out += f'{share_count} shares in {ticker_name}: \t\t {share_price} zc\n'
            total_share_value += share_price

        # display total share value
        out += f'\ntotal share value: {total_share_value} zc'

        return out


    # example usage:
    # (zc) buy_shares AAPL 1.35
    async def user_buys_shares(self, message_string, user_message):
        user_uid = user_message.author.id
        # get parameters
        parameters = message_string.split(' ')[1:]
        ticker_name, share_count = parameters[0], float(parameters[1])

        # you can't buy negative stock amount
        if share_count < 0:
            return 'do not try and game the system man.'

        # you can't buy zero stock
        if share_count == 0:
            return 'now you are just being silly man'

        # round share count to 2 decimals
        share_count = round(share_count, 2)

        # get price of requested shares
        price = 999999
        try:
            price = await self.get_share_price_from_name_amount(ticker_name, share_count)
        except Exception as e:
            # something went wrong, probably incorrect ticker name
            print(e)
            return 'what recheck your message and try again bro'

        # check balance of the user
        coins = await self.get_coin_count_from_uid(user_uid)

        # can't buy if you don't have the cash
        # round, then add 1 to avoid 0 cost shares
        price = int(price) + 1
        if coins < price:
            return f'mane you are broke broke, you need {price} coins, \
but you only have {coins} coins'

        # subtract price from user
        user_uid = user_message.author.id
        await self.change_user_coins_by_num(user_uid, -price)

        # get owned shares from database
        find_owned_count_query = f"SELECT ShareCount\
                                   FROM Shares\
                                   WHERE UID = {user_uid} AND\
                                   StockTicker = '{ticker_name}'"

        # execute query
        self.cursor.execute(find_owned_count_query)
        # get share count result
        owned_res = self.cursor.fetchall()
        if len(owned_res) == 0:
            # if there's no query, then add a new share
            # for that user into the db
            # add share to database
            add_query = f"INSERT INTO Shares\
                          VALUES (\
                          {user_uid},\
                          '{ticker_name}',\
                          {share_count});"

            # execute query
            self.cursor.execute(add_query)

            # the user's new count is the same as what they just bought
            # because they had none to start with
            new_count = share_count
        else:
            # update the count to current amount + new amount
            owned_count = round(float(owned_res[0][0]), 2)
            new_count = share_count + owned_count

            # update user's share value
            update_query = f"UPDATE Shares\
                             SET ShareCount = {new_count}\
                             WHERE UID = {user_uid} AND\
                             StockTicker = '{ticker_name}';"

            # add user share into db
            self.cursor.execute(update_query)

        # get user's balance after purchase
        new_balance = await self.get_coin_count_from_uid(user_uid)

        return f'you have sucessfully bought {share_count} shares \
of {ticker_name}, you now have {new_count} shares and {new_balance} coins.\n\
may luck be in your favor.'

    # example usage
    # (zc) sell all
    async def user_sells_shares(self, message_string, user_message):
        user_uid = user_message.author.id

        # get parameters
        parameters = message_string.split(' ')[1:]
        ticker_name = parameters[0]

        # check to make sure the user has that amount of stocks
        stock_amount_query = f"SELECT ShareCount FROM SHARES\
                              WHERE UID = {user_uid} AND\
                              StockTicker = '{ticker_name}';"

        self.cursor.execute(stock_amount_query)
        owned_shares = float(self.cursor.fetchall()[0][0])

        # special case, share_count == all
        if parameters[1].lower() == 'all':
            # set share_count to the amount of owned shares
            share_count = owned_shares
        else:
            share_count = float(parameters[1])

        # you can't sell negative stock amount
        if share_count < 0:
            return f'you do NOT have that many shares of {ticker_name}. don\'t play with me...'

        if share_count == 0:
            return 'now you are just being silly man'

        # round share count to 2 decimals
        share_count = round(share_count, 2)

        # get price of requested shares
        price = -9999999
        try:
            price = await self.get_share_price_from_name_amount(ticker_name, share_count)

            # price rounding
            price = int(price)
        except Exception:
            # something went wrong, probably incorrect ticker name
            return 'what :zquestion: recheck your message and try again bro :zunshaven: :zunshaven:'

        # add the price back to the user's balance
        await self.change_user_coins_by_num(user_uid, price)

        # remove stock from user
        new_count = owned_shares - share_count
        # update user's share value
        update_query = f"UPDATE Shares\
                         SET ShareCount = {new_count}\
                         WHERE UID = {user_uid} AND\
                         StockTicker = '{ticker_name}';"

        self.cursor.execute(update_query)

        # get user's balance after selling stock
        new_balance = await self.get_coin_count_from_uid(user_uid)

        return f'you have sucessfully (or maybe unsucessfully) \
sold {share_count} shares of {ticker_name}, gaining you {price} zane coins \n\
you now have {new_count} shares and {new_balance} coins.'

    # example usage
    # (zc) check_price AAPL 1
    async def user_checks_price_of_share_count(self, message_string, user_message):
        # get parameters
        parameters = message_string.split(' ')[1:]

        # if there's only one parameter, assume it's a testcase like
        # (zc) check_price AAPL
        # then set share_count to 1
        if len(parameters) == 1:
            ticker_name = parameters[0]
            share_count = 1
        else:
            ticker_name, share_count = parameters[0], float(parameters[1])

        # round share count to 2 decimals
        share_count = round(share_count, 2)

        share_price = -1
        try:
            share_price = await self.get_share_price_from_name_amount(ticker_name, share_count)
        except Exception as e:
            print(e)
            return 'something went wrong, check the ticker name and try again :zunshaven:'

        # round share_price
        rounded_price = int(share_price) + 1

        output_str = f'the price for {share_count} shares of {ticker_name} is {rounded_price} zane coins\n\
{round(share_price,6)} before rounding...'

        return output_str

    async def get_share_price_from_name_amount(self, ticker_name, amount):
        ticker_price = -1
        ticker_price = await self.get_ticker_price(ticker_name)
        if ticker_price is None:
            raise Exception

        share_price = ticker_price * amount

        return round(share_price, 2)

    # returns a float or a None if the ticker is invalid
    async def get_ticker_price(self, ticker_name):
        # get price from yfinace api
        price = yf.Ticker(ticker_name).fast_info.last_price

        # price returns some error message if it's an invalid ticker
        # so check for that here
        if type(price) is not float:
            return None

        # return price as a float value
        return price

    async def debug_cooldown(self, message_string, user_message):
        # make sure it is from a moderator uid
        user_uid = user_message.author.id
        if user_uid != mod_uid:
            return "I'm dead :sob: :sob:"

        # reset cooldowns for first uid in message
        uids = await self.get_uids_from_message_string(message_string)
        target_uid = uids[0]
        await self.reset_user_cooldowns(target_uid)

        # return
        username = await self.get_username_from_uid(target_uid, user_message)
        return_message = f'cooldowns reset for {username}'
        return return_message

    async def reset_user_cooldowns(self, user_uid):
        # copied from adding new user command
        zeroes = [0] * coin_max
        coin_add_cd_list_as_string = await self.convert_int_list_to_string_list(zeroes)
        coin_deduct_cd_list_as_string = await self.convert_int_list_to_string_list([0])
        reset_query = f"\
            UPDATE Users\
            SET TimeLastCoinsAwarded = '{coin_add_cd_list_as_string}',\
            TimeLastCoinsDeducted = '{coin_deduct_cd_list_as_string}'\
            WHERE UID = {user_uid}\
            "

        self.cursor.execute(reset_query)

    async def add_user_to_database_if_not_in_users(self, user_uid):
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
            return 'you have no coins... get your money up.'

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
            except Exception:
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
            print(e)
            return "check the command format again"

        # check user input again
        if not (user_choice == "heads" or user_choice == "tails"):
            return "pick heads or tails man"

        if wager <= 0:
            return "you can't wager less than or equal to zero coins..."

        if wager > coins:
            return "you do NOT have that many coins to wager..."

        bot_choice = "heads" if random.randint(0, 1) == 0 else "tails"

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

    # when quick response is true, it will return -5, 0, 1, 10
    # for command failing due to greed (-5)
    # award on cooldown (0)
    # award went through normally (1)
    # award got lucky and did +10, (10)
    async def user_awards_user_with_coin(self, message_string, user_message, quick_response=False):
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
            # return code 0 for no coins awarded
            if quick_response:
                return 0
            return f'you must wait {time_remaining_str} until you can award another coin.'
        # get uids
        uids = await self.get_uids_from_message_string(message_string)
        target_uid = uids[0]

        # ensure the target user is in the database
        await self.add_user_to_database_if_not_in_users(target_uid)

        # check to make sure that a sure isn't giving a coin to themselves
        if user_uid == target_uid:
            # return code -5 for greed
            if quick_response:
                return -5
            return "you CANNOT give a coin to yourself... greedy bastard..."

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
            # return code 10 for 10 awarded
            if quick_response:
                return 10
            return f"you have given... TEN COINS! TO **{target_name}** WOW!! SO LUCKY AND GENEROUS!\n\
            YOU GET TWO COINS FOR YOURSELF TOO! WOOHOO!"

        await self.change_user_coins_by_num(target_uid, 1)

        # return code 1 for 1 coin awarded
        if quick_response:
            return 1
        return f"you have given one coin to **{target_name}** how generous of you"

    # example usage:
    # (zc) gift @jarsnow 10
    async def user_gifts_user_coins(self, message_string, user_message):
        user_uid = user_message.author.id
        uids = await self.get_uids_from_message_string(message_string)
        target_uid = uids[0]

        # make sure user is in database
        await self.add_user_to_database_if_not_in_users(target_uid)

        # check to make sure that a sure isn't giving a coin to themselves
        if user_uid == target_uid:
            return "you CANNOT give a coin to yourself... greedy bastard..."

        # get gift amount
        amount = 0

        try:
            amount = int(message_string.split(' ')[2])
        except Exception as e:
            print(e)
            pass

        # edge cases for odd gifting numbers
        if amount == 0:
            return "mane what's the point of this"

        if amount < 0:
            return "your attempt at betrayal makes me sick..."

        # check to see that the user has enough to give
        giver_balance = await self.get_coin_count_from_uid(user_uid)
        if giver_balance < amount:
            return 'you are TOO POOR to give this many coins away... lol.'

        # exchange coins
        await self.change_user_coins_by_num(user_uid, -amount)
        await self.change_user_coins_by_num(target_uid, amount)

        target_nickname = await self.get_username_from_uid(target_uid, user_message)

        return f"you have given **{target_nickname}** \
{amount} coin{'s' if amount > 1 else ''}, how generous of you"

    # for quick response, can return -1, 0, 5
    # -1 for normal case
    # 0 for failed case (cooldown most likely)
    # 5 for rare chance case
    async def user_deducts_user_coin(self, message_string, user_message, quick_response=False):
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
            # quick response (case 0)
            if quick_response:
                return 0

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

            # quick_response (case 5)
            if quick_response:
                return 5

            return f"WOW you are so rude... you have been FINED **FIVE** of *YOUR* COINS!\n\
                    I will have mercy on **{target_name}** and give them three coins instead..."

        await self.change_user_coins_by_num(target_uid, -1)

        # quick_response (case -1)
        if quick_response:
            return -1

        return f"you have taken away a coin from **{target_name}**... why must your heart be so evil..."

    async def get_leaderboard_response(self, message_string, user_message):
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
            except Exception:
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
            except Exception:
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

    # adds an emoji to the given user message given an emoji name (no colons included)
    async def add_emoji_to_message_from_name(self, user_message, emoji_names):
        # find emoji from where the bot is located
        emojis = user_message.guild.emojis

        # cast tuple to a set
        emojis_to_add = list(emoji_names)

        for emoji_name in emojis_to_add:
            if len(emoji_name) == 1:
                # add it to server message, it's a normal emoji
                await user_message.add_reaction(emoji_name)
            else:
                # search through guild emojis to find the right one
                for server_emoji in emojis:
                    if server_emoji.name == emoji_name:
                        await user_message.add_reaction(server_emoji)
                        break

    async def get_username_from_uid(self, UID, user_message):
        guild = user_message.guild
        member = await guild.fetch_member(UID)
        name = member.name
        return name

    async def is_message_for_bot(self, content, channel):
        # check if command is ran
        content = content.lower()
        return f"{prefix} " in content and content.index(f"{prefix} ") == 0

    async def is_message_in_allowed_channel(self, content, channel):
        # check if the message is in the channel specified by .env file
        return channel.id == usable_channel_id


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

    global client
    client = MyClient(intents=intents)
    client.run(discord_token)


if __name__ == "__main__":
    main()
