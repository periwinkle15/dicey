#!/usr/bin/env python3
"""
Dicey die rolling discord bot.
Thanks to the bot Dorian for the basic structure.
"""

"""
Imports
"""

import asyncio
import discord
import logging
from urllib import parse
from urllib import request
from random import choice
from random import randint
import re
import youtube_dl

from diceClasses import *
from dicey_token import token

"""
Global variables
"""

logging.basicConfig(level=logging.INFO)

client = discord.Client()
discord.opus.load_opus

cRoll = "/croll"
simpleRoll = "/roll"
disconnect = "/disconnect"
doc = "/help"
simpleHelp = "/simplerollhelp"
cRollHelp = "/cocrollhelp"

fail = "Couldn't parse input. Use /help to get more information."

helpDoc = """
```
/roll [[iterations]x][[number]d[die type]][+[bonus]][other keys][,[new roll]]
Use /SimpleRollHelp for info and examples.

/croll [[number=1][b OR p]]...[[score][threshold]]
Use /CoCRollHelp for info and examples.

/mood [random OR [search terms]]
Sends a random youtube video found by searching rpg-background-music type keywords.
No argument returns a generic video
random returns a search with a an additional "mood" specifier chosen from a list of words like "battle," "creepy," etc.
Or add your own search terms

/disconnect
As on tin

/help
You already found me!
```
"""

simpleRollDoc = """
```
/roll [[iterations]x][[number]d[die type]][+/-[bonus]][other options][,[new roll]]
Defaults to rolling 1d20

[[iterations]x] has global scope; it applies to everything after it and cannot be repeated. It causes the same input to be used again; /roll 2x performs /roll twice.
[number] on its own is interpreted as a bonus to the default roll.
[xdy] rolls a y-sided die x times and adds together the results. If x is ommitted, it defaults to 1.
[+ or - bonus] adds or subtracts a fixed amount to the total.
[drop] drops the lowest N rolls from the total, where N defaults to 1 or can be set by appending an integer. It resets to 0 unless a roll is being repeated.
[keep] keeps the lowest N rolls, dropping the higher from the total, where N defaults to 1 or can be set by appending an integer. It resets to 0 unless a roll is being repeated.
[>/<[=]] sets a boundary above or below which rolls will be counted as a success, and reported as successes or failures instead of raw numbers.
[!] causes World of Darkness style exploding dice (rolls above a certain value trigger a new roll). It applies to the total xdy+z, not to each individual dy. It defaults to the maximum number; set a boundary with [>[=]] or [<[=]].
[!!] causes Shadowrun or Riddle of Steel style exploding dice, in which a new roll is added to the previous value.
[,] allows you to enter a new roll. Instead of 1d20, defaults will be set by the previous roll. If a new die type is entered, "fancy" attributes like drop go back to default.

Examples:
		/roll
		2
		1d20: 2

		/roll 2d10+2
		13, 22
		2d10+2: (5+6) + 2 = 13
		2d10+2: (1+8) + 2 = 11

		/roll 2x3d17+3,2 drop 2,d4
		32, 4, 4, 40, 14, 3
		3d17+3:  (17 + 7 + 5) + 3 = 32
		3d17+2:  (2) + 2 = 4 (dropped 1, 1)
		1d4:  4
		3d17+3:  (15 + 16 + 6) + 3 = 40
		3d17+2:  (12) + 2 = 14 (dropped 3, 8)
		1d4:  3
```
"""

cRollDoc = """
```
/croll [[number=1][die type]]...[[score][threshold]]
Spaces don't matter. 

Die Types:
		b: Bonus dice (can't be chained with Penalty)
		p: Penalty dice (can't be chained with Bonus)
		t: Threshold to determine success/fail. Score is required if a threshold is set.

Examples:
		/croll
		36

		/croll 60t
		Hard Success: 24

		/croll b
		70/30 + 5 = 35

		/croll 2p70t
		Failure: 0/50/70 + 4 = 74
```
"""
mood = "/mood"
music = "music"
genericSearches = ["dungeon", "adventure", "rpg", "dungeons and dragons", "d&d", "background", "fantasy", "video game"]
moodChoices = ["creepy", "epic", "battle", "crypt", "enchanted", "village", "woods", "winter", "city", "desert"]

goodRobot = ["Thanks! :smile:", "I appreciate it!", "Always happy to help! :wink:", ":robot::heart_exclamation:"]
badRobot = [":cry:", ":robot::broken_heart:", "I'm sorry... I'll try to do better."]*5+["Look, *you* try keeping track of all this math."]
greetings = ["Hi!", "Hello!", "Happy to be here!"]
greetRobot = ["hi", "hello", "meet", "here"]

rollsLimit = 50
digitLimit = 10000

FirstConnect=True

COL_CRIT_SUCCESS=0xFFFFFF
COL_EXTR_SUCCESS=0xf1c40f
COL_HARD_SUCCESS=0x2ecc71
COL_NORM_SUCCESS=0x2e71cc
COL_NORM_FAILURE=0xe74c3c
COL_CRIT_FAILURE=0x992d22

"""
Miscellaneous fun functions
"""

def ResolveCDice(BonusDie, PenaltyDie, Threshold):
	"""
	Resolves a CoC-style d% roll with bonus and penalty dice
	and a success threshold.
	"""
	TenResultPool = []
	TenResultPool.append(RollDie(0, 9))

	TenResult = min(TenResultPool)
	OneResult = RollDie(0, 9)

	if BonusDie > 0 and PenaltyDie > 0:
		return "Can't chain bonus and penalty dice."

	# Add bonus dice
	for i in range(BonusDie):
		TenResultPool.append(RollDie(0, 9))
		TenResult = min(TenResultPool)

		# Deal with the 00 0 = 100 case
		if OneResult == 0 and TenResult == 0 and TenResultPool.count(0)!=len(TenResultPool):
			TenResult = min([i for i in TenResultPool if i>0])

	# OR add penalty dice
	for i in range(PenaltyDie):
		TenResultPool.append(RollDie(0, 9))
		TenResult = max(TenResultPool)

		# Deal with the 00 0 = 100 case
		if 0 in TenResultPool and OneResult == 0:
			TenResult = 0

	# Find final result
	CombinedResult = (TenResult*10) + OneResult
	if CombinedResult == 0:
		CombinedResult = 100

	desc = str(TenResult*10)
	if len(TenResultPool) > 1:
		desc += '(' + '/'.join([str(i*10) for i in TenResultPool]) + ')'
	desc +=  ' + ' + str(OneResult) + ' = ' + str(CombinedResult)

	# Set box color based on the given threshhold.
	if Threshold:
		ret = DiceResult()
		ret.desc = desc
		
		if CombinedResult == 1:
			ret.title = "Critical Success!"
			ret.colour = COL_CRIT_SUCCESS
		elif CombinedResult == 100:
			ret.title = "Critical Failure!"
			ret.colour = COL_CRIT_FAILURE
		elif CombinedResult <= Threshold/5:
			ret.title = "Extreme Success!"
			ret.colour = COL_EXTR_SUCCESS
		elif CombinedResult <= Threshold/2:
			ret.title = "Hard Success!"
			ret.colour = COL_HARD_SUCCESS
		elif CombinedResult <= Threshold:
			ret.title = "Success"
			ret.colour = COL_NORM_SUCCESS
		else:
			ret.title = "Failure"
			ret.desc = ret.desc + "\npush the rolllllllll"
			ret.colour = COL_NORM_FAILURE

		return ret
	else:
		ret = DiceResult()
		ret.title = str(CombinedResult)
		ret.desc = desc

		return ret

def parseCRoll(diceString):
	"""
	Attempts to parse raw input into a number of bonus or penalty dice, and a threshold
	"""

	# Searches for the die syntaxes.
	dice=[x for x in re.split('(\d*?[bpt])',diceString) if x]

	if len(dice) > 1 and 'b' in diceString and 'p' in diceString:
		return "Can't chain bonus and penalty dice"
		
	BonusDie=0
	PenaltyDie=0
	Threshold=False

	# Categorizes die types. Uses some fancy regular expression stuff
	# from the original Dorian bot.
	for die in dice:

		default_num = False
		s = re.search('(\d*?)([bpt])', die)
		
		if not s:
			default_num = True
			die = "1"+die
		s = re.search('(\d*?)([bpt])', die)
		
		if not s:
			return fail

		g = s.groups()
		
		if len(g) != 2:
			return fail
		
		try:
			num = int(g[0])
		except:
			default_num = True
			num = 1

		dieCode=g[1]
		
		if len(dieCode) > 1:
			return fail

		# Set die numbers
		if dieCode == 'b':
			BonusDie = num

		if dieCode == 'p':
			PenaltyDie = num

		if	dieCode == 't':
			if default_num:
				return "Threshold requires a value!"
			else:
				Threshold = num

	# Check for invalid numbers
	if any([BonusDie>rollsLimit, PenaltyDie>rollsLimit]):
		return "Sorry... I'd rather not print that many rolls."
	elif Threshold < 0 or Threshold > 100:
		return "Invalid threshold - must be between 0 and 100."
				
	return ResolveCDice(BonusDie, PenaltyDie, Threshold)

def getMood(searchString):

	search = " ".join([choice(genericSearches) for i in range(randint(1, 3))])

	if "random" in searchString:
		search += " " + " ".join([choice(moodChoices) for i in range(randint(1, 2))])
	elif searchString != "":
		search += " " + searchString

	search += " " + music

	ydl_opts = {'format': 'bestaudio', 'noplaylist': True, 'no_warnings': True, "include ads": False, 
				"skip_downloads": True, "simulate": True, "age_limit": 13,}

	with youtube_dl.YoutubeDL(ydl_opts) as ydl:

		video = ydl.extract_info(f'ytsearch:{search}', download=False)['entries'][0]
		print(len(ydl.extract_info(f'ytsearch:{search}', download=False)['entries']))

	return f"Search result : {video['webpage_url']}"

"""
Functions that handle Discord events.
"""

@client.event
async def on_ready():
	"""
	Tells me the bot connected
	"""
	global FirstConnect
	print("Dicey connected")
	if FirstConnect:
		FirstConnect = False

@client.event
async def on_message(message):
	"""
	Listens to incoming messages
	"""
	# Disregard the bot's own messages
	if message.author == client.user:
		return

	# Get basic info
	parse = message.content.lower()
	if isinstance(message.author.nick, str):
		author = message.author.nick
	else:
		author = message.author.name
	author += "'s roll"

	# Handle a /roll command
	if parse.startswith(simpleRoll):

		roll = Roll(parse[len(simpleRoll):])
		result = roll.result

		# If result was a string, something failed; send string.
		if isinstance(result, str):
			await message.channel.send(result)
		elif result is ValueError:
			await message.channel.send(fail)

		# Else the function returns a list of DiceResult objects
		# Concatenate them into a text box
		else:
			# If all the titles are success/failure, do a count-successes thing instead
			titles = [roll.title for roll in result]
			successes = titles.count('Success')

			if all([i == 'Success' or i == 'Failure' for i in titles]):
				em = discord.Embed(title = str(successes) + ' Success(es)')
				if successes == 0:
					em.color = COL_NORM_FAILURE
				elif successes == len(titles):
					em.color = COL_HARD_SUCCESS
				else:
					em.color = COL_NORM_SUCCESS

			# Or count the successes, then display the base numbers
			elif 'Success' in titles or 'Failure' in titles:
				title = str(successes) + ' Success(es), '
				title += ", ".join([i for i in titles if i != 'Success' and i != 'Failure' ])

				em = discord.Embed(title = title)

				if successes == 0:
					em.color = COL_NORM_FAILURE
				else:
					em.color = COL_NORM_SUCCESS

			# Or just return the numbers
			else:
				em = discord.Embed(title=", ".join([i for i in titles]))
				if len(titles) == 1:
					em.color = result[0].colour
				else:
					em.color = COL_NORM_SUCCESS

			em.set_footer(text = str("\n".join([roll.desc for roll in result])))
			em.description = author

			if len(em.title) > 256:
				await message.channel.send("Too many results, couldn't send message.")
			else:
				if len(em.footer) >= 2048:
					em.set_footer(text = "description too long; surpressed")

				await message.channel.send(embed=em)

	# Handle a /croll command
	elif parse.startswith(cRoll):
		result = parseCRoll(parse[len(cRoll):])

		# If result was a string, something failed; send string.
		if isinstance(result, str):
			await message.channel.send(result)

		# Else the function returns DiceResult object
		# Concatenate them into a text box
		else:
			em = discord.Embed(title=result.title, colour=result.colour)
			em.set_footer(text=result.desc)
			em.description = author

			await message.channel.send(embed=em)	

	elif message.content.startswith(mood):
		await message.channel.send(getMood(message.content[len(mood):]))

	# Cute extras
	elif "badrobot" in parse.replace(" ", "") or "badbot" in parse.replace(" ", "") and "not" not in parse:
		await message.channel.send(choice(badRobot))

	elif "goodrobot" in parse.replace(" ", "") or "goodbot" in parse.replace(" ", "") and "not" not in parse:
		await message.channel.send(choice(goodRobot))

	elif "dicey" in parse and any([item in parse for item in greetRobot]):
		# Don't want to interpret things like "dice yes" here
		await message.channel.send(choice(greetings))

	# Handle disconnect
	elif message.content == disconnect:
		await message.channel.send("Dicey is disconnecting!")
		# TBD: find better disconnect method
		raise KeyboardInterrupt

	# Handle help requests
	elif parse == doc:
		await message.channel.send(helpDoc)

	elif parse == simpleHelp:
		await message.channel.send(simpleRollDoc)

	elif parse == cRollHelp:
		await message.channel.send(cRollDoc)

"""
Finally...
we run the bot
"""

client.run(token)
