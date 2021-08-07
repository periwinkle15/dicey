#!/usr/bin/env python3
"""
Dicey die rolling discord bot.
Thanks to the bot Dorian for the basic structure.
"""

"""
Imports
"""

import asyncio
import csv
import discord
import logging
import urllib.request
from numpy import floor
from random import choice
from random import randint
from urllib.parse import quote

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
trosRoll = "/tros"
disconnect = "/disconnect"
doc = "/help"
simpleHelp = "/simplerollhelp"
cRollHelp = "/cocrollhelp"
trosRollHelp = "/trosrollhelp"

fail = "Couldn't parse input. Use /help to get more information."

goodRobot = ["Thanks! :smile:", "I appreciate it!", "Always happy to help! :wink:", ":robot::heart_exclamation:"]
badRobot = [":cry:", ":robot::broken_heart:", "I'm sorry... I'll try to do better."]*5+["Look, *you* try keeping track of all this math."]
greetings = ["Hi!", "Hello!", "Happy to be here!"]
greetRobot = ["hi", "hello", "meet", "here"]

mood = "/mood"
music = "music"
genericSearches = ["dungeon", "adventure", "rpg", "dungeons and dragons", "d&d", "background", "fantasy", "video game"]
moodChoices = ["creepy", "epic", "battle", "crypt", "enchanted", "village", "woods", "winter", "city", "desert"]

name = "/name"
nameType = "/nametypes"
nameFile = "nameList.csv"
nameFail = "Sorry, you sent a specifier that's not used. Use /nametypes to see what's available."
fileFail = "No name file (" + nameFile + ") found."

turn = "/turn"

helpDoc = """
```
/roll [[iterations]x][[number]d[die type]][+[bonus]][other keys][,[new roll]]
Use /SimpleRollHelp for info and examples.

/croll [[number=1][b OR p]]...[[score][threshold]]
Use /CoCRollHelp for info and examples.

/tros [[iterations]x][[pool]/[target number]] OR simple roll[, [new roll]]
Use /trosRollHelp for info and examples.

/mood [search terms]
Sends a random youtube video found by searching rpg-background-music type keywords.
No argument returns a generic video chosen from a list of words (like "battle," "village," etc.)
Or add your own search terms

/name [origin] [label]
Sends name chosen from a file in the same directory as Dicey's code, called """ + nameFile + """
Origin and label are optional specifiers. 
Use /nametypes for more info.

/turn [level] [charisma bonus]
Rolls a 3.5E D&D turning check.

/disconnect
As on tin

/help
You already found me!
```
"""

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

def getMood(searchString):

	search = " ".join([choice(genericSearches) for i in range(randint(1, 2))])

	if searchString == "":
		search += " " + " ".join([choice(moodChoices) for i in range(randint(1, 2))])
	elif searchString != "":
		search += quote(searchString)

	search += " " + music
	search = search.replace(" ", "+")

	page = urllib.request.urlopen('https://www.youtube.com/results?search_query=' + search)
	html = str(page.read())

	results = []
	for i in range(len(html)-9):
	    if html[i:i+9] == "/watch?v=":
	    	results.append(html[i:i+20])

	return "https://www.youtube.com" + choice(results[:max([5, len(results)])])


def getName(nameString):

	names = []
	origins = []
	labels = []

	try:
		with open(nameFile) as csvfile:
			reader = csv.reader(csvfile)
			for line in reader:
				names.append(line[0])
				origins.append(line[1])
				labels.append(line[2])
	except IOError:
		return fileFail

	origin = ""
	label = ""

	if " " in nameString:
		origin = nameString.split(" ")[0]
		label = nameString.split(" ")[-1]
		if origin not in origins:
			return nameFail
		if label not in labels and label != "name":
			return nameFail
	elif nameString in origins:
		origin = nameString
	elif nameString in labels or nameString == "name":
		label = nameString
	elif nameString == "":
		label = "name"
	elif nameString != "":
		return nameFail

	if label == "":
		label = "name"

	originNames = names.copy()
	labelNames = names.copy()
	if origin != "":
		originNames = [names[i] for i in range(len(names)) if origins[i] == origin]
	if label != "name":
		labelNames = [names[i] for i in range(len(names)) if labels[i] == label]
	else:
		labelNames = [names[i] for i in range(len(names)) if labels[i] == "male" or labels[i] == "female"]

	nameList = [item for item in originNames if item in labelNames]

	if len(nameList) == 0:
		return "Sorry, no names that match your request."

	return choice(nameList)

def getNameTypes():

	origins = []
	labels = []
	try:
		with open(nameFile) as csvfile:
			reader = csv.reader(csvfile)
			for line in reader:
				origins.append(line[1])
				labels.append(line[2])
	except IOError:
		return fileFail

	origins = list(set(origins))
	labels = list(set(labels))

	origins.sort()
	labels.sort()

	returnString = """
	```
Available name types:
Origins: """ + ", ".join(origins) + """
Labels: """ + ", ".join(labels) + """, name

Request names with /name [origin] [label]. Both inputs are optional.
The 'name' label will search over both male and female names. If no label is given, 'name' is used as the default.
```"""

	return returnString

def getTurn(turnString):

	parse = turnString.strip().split(" ")

	level = int(parse[0])
	charisma = int(parse[1])

	maxHD = level + floor((randint(1, 20) + charisma - 10)/3)
	if maxHD < level - 4:
		maxHD = level - 4
	elif maxHD > level + 4:
		maxHD = level + 4

	damage = randint(1, 6) + randint (1, 6) + level + charisma

	damage = int(damage)
	maxHD = int(maxHD)

	footer = "You can turn " + str(damage) + " HD of undead.\n"
	footer += "The highest HD undead you can turn is " + str(maxHD) + " HD.\n"
	footer += "You can destroy undead of " + str(int(floor(level/2.0))) + " HD or lower."

	title = str(damage) + " HD damage, " + str(maxHD) + " HD max"

	return title, footer

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
	await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/roll, /help"))

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

	# Handle help requests
	if parse == doc:
		await message.channel.send(helpDoc)

	elif parse == simpleHelp:
		await message.channel.send(simpleRollDoc)

	elif parse == cRollHelp:
		await message.channel.send(cRollDoc)

	elif parse == trosRollHelp:
		await message.channel.send(trosRollDoc)

	# Handle a /roll command
	elif parse.startswith(simpleRoll):

		roll = Roll(parse[len(simpleRoll):])
		result = roll.format()

		# If result was a string, something failed; send string.
		if isinstance(result, str):
			await message.channel.send(result)

		else:
			em = discord.Embed(title = result.title,
								description = author,
								colour = result.colour)
			em.set_footer(text = result.desc)

			await message.channel.send(embed=em)

	# Handle a /tros command
	elif parse.startswith(trosRoll):

		roll = RoS(parse[len(trosRoll):])
		result = roll.format()

		# If result was a string, something failed; send string.
		if isinstance(result, str):
			await message.channel.send(result)

		else:
			em = discord.Embed(title = result.title,
								description = author,
								colour = result.colour)
			em.set_footer(text = result.desc)

			await message.channel.send(embed=em)

	# Handle a /croll command
	elif parse.startswith(cRoll):
		roll = CoC(parse[len(cRoll):])
		result = roll.format()

		# If result was a string, something failed; send string.
		if isinstance(result, str):
			await message.channel.send(result)

		else:
			em = discord.Embed(title = result.title,
								description = author,
								colour = result.colour)
			em.set_footer(text = result.desc)

			await message.channel.send(embed=em)

	elif message.content.startswith(mood):
		await message.channel.send(getMood(message.content[len(mood):]))

	elif parse.startswith(nameType):
		await message.channel.send(getNameTypes())

	elif parse.startswith(turn):
		title, footer = getTurn(parse[len(turn):])
		em = discord.Embed(title = title,
							description = author,
							colour = 0x2e71cc)
		em.set_footer(text = footer)

		await message.channel.send(embed=em)

	elif parse.startswith(name):
		await message.channel.send(getName(message.content[len(name):].strip().lower()))

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

"""
Finally...
we run the bot
"""

client.run(token)
