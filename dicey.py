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
import json
import logging
import os
import re
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

prefix = "$"


cRoll = prefix + "croll"
simpleRoll = prefix + "roll"
trosRoll = prefix + "tros"
disconnect = prefix + "disconnect"
doc = prefix + "help"
simpleHelp = prefix + "simplerollhelp"
cRollHelp = prefix + "cocrollhelp"
trosRollHelp = prefix + "trosrollhelp"

fail = "Couldn't parse input. Use "+prefix+"help to get more information."

goodRobot = ["Thanks! :smile:", "I appreciate it!", "Always happy to help! :wink:", ":robot::heart_exclamation:"]
badRobot = [":cry:", ":robot::broken_heart:", "I'm sorry... I'll try to do better."]*5+["Look, *you* try keeping track of all this math."]
greetings = ["Hi!", "Hello!", "Happy to be here!"]
greetRobot = ["hi", "hello", "meet", "here"]

mood = prefix + "mood"
genericSearches = ["dungeon", "adventure", "rpg", "dungeons and dragons", "d&d", "background", "fantasy", "video game"]
moodChoices = ["creepy", "epic", "battle", "crypt", "enchanted", "village", "woods", "winter", "city", "desert"]

name = prefix + "name"
nameType = prefix + "nametypes"
nameFile = "nameList.csv"
nameFail = "Sorry, you sent a specifier that's not used. Use "+prefix+"nametypes to see what's available."
fileFail = "No name file (" + nameFile + ") found."

save = prefix + "save"
useSaved = prefix + "saved"
rollsFile = "customRolls.json"
delete = prefix + "delete"
getCommandsList = prefix + "commands"
saveHelp = prefix + "savehelp"
saveDoc = """
```
Dicey can save up to 1000 custom commands to be accessed later.
In your command name, use only ASCII characters and do not use spaces.
Uses the file """ + rollsFile + """ in the same directory as Dicey's code.
Commands are specific to the computer Dicey is running on!

"""+prefix+"""save [name] [command] saves a simple roll command under "name" and sends an example roll. This will NOT overwrite an existing command. Make sure you put a space between [name] and [command].
"""+prefix+"""saved [name] accesses the saved command "name"
"""+prefix+"""delete [name] deletes command "name"
"""+prefix+"""commands sends a list of all available custom commands. This may be long!
```
"""

turn = prefix + "turn"

helpDoc = """
```
"""+prefix+"""roll [[iterations]x][[number]d[die type]][+[bonus]][other keys][,[new roll]]
Use """+prefix+"""SimpleRollHelp for info and examples.

"""+prefix+"""croll [[number=1][b OR p]]...[[score][threshold]]
Use """+prefix+"""CoCRollHelp for info and examples.

"""+prefix+"""tros [[iterations]x][[pool]/[target number]] OR simple roll[, [new roll]]
Use """+prefix+"""trosRollHelp for info and examples.

"""+prefix+"""mood [search terms]
Sends a random youtube video found by searching rpg-background-music type keywords.
No argument returns a generic video chosen from a list of words (like "battle," "village," etc.)
Or add your own search terms

"""+prefix+"""name [origin] [label]
Sends name chosen from a file in the same directory as Dicey's code, called """ + nameFile + """
Origin and label are optional specifiers. 
Use """+prefix+"""nametypes for more info.

"""+prefix+"""turn [level] [charisma bonus]
Rolls a 3.5E D&D turning check.

"""+prefix+"""save [name] [command]
Saves a simple roll command under a custom name, saved in Dicey's code directory under """ + rollsFile + """
Acceess with """+prefix+"""saved, delete with """+prefix+"""delete, see options with """+prefix+"""commands
See """+prefix+"""saveHelp for more info

"""+prefix+"""disconnect
As on tin

"""+prefix+"""help
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

	if searchString == "":
		search = " ".join([choice(moodChoices) for i in range(randint(1, 2))])
	else:
		#search = "\"" + searchString + "\""
		search = searchString.strip()

	#search += " " + choice(genericSearches)
	search += " music"
	search = quote(search)

	print("Searching youtube for " + search)

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

Request names with """+prefix+"""name [origin] [label]. Both inputs are optional.
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

def saveCommand(commandString):
	"""
	Save a custom roll command
	"""

	if not os.path.exists(rollsFile):
		open(rollsFile, 'x').close()

	result = ""
	index = commandString.find(" ")
	if index == -1:
		send = "I need you to put a space between your command name and the roll so I can tell the difference."
	else:
		name = commandString[:index]
		if not str.isascii(name):
			send = "Please only use ASCII characters in your command name :pleading_face:"
		elif len(name) > 50:
			send = "That's more than 50 characters long. Try a shorter commands name."
		else:

			roll = Roll(commandString[index:].lower().strip())
			result = roll.format()

			# If result was a string, something failed; send string.
			if isinstance(result, str):
				send = "Your roll command failed :cry: :\n" + result

			else:

				splitDesc = re.split(r":|\n", result.desc)

				descriptionList = []
				for n in range(0, len(splitDesc), 2):
					description = splitDesc[n]
					if "keep" in splitDesc[n+1]:
						description += " keep " + str(splitDesc[n+1].count(",") + 1)
					if "drop" in splitDesc[n+1]:
						description += " drop " + str(splitDesc[n+1].count(",") + 1)

					descriptionList.append(description)

				cleanDesc = ", ".join(descriptionList)

				cleanDesc = cleanDesc.replace("\u2265", ">=")
				cleanDesc = cleanDesc.replace("\u2264", "<=")

				printDesc = cleanDesc
				if len(cleanDesc) > 50:
					printDesc = cleanDesc[:50] + "..."

				with open(rollsFile, 'r') as jsonFile:
					dictString = jsonFile.read()

				if len(dictString) == 0:
					commandsDict = {}
				else:
					try:
						with open(rollsFile, 'r') as jsonFile:
							commandsDict = json.load(jsonFile)
					except:
						send = "There was an error in the format of " + rollsFile
						result = ""
						return send, result

				if name in commandsDict.keys():
					send = "Command name already in use as " + commandsDict[name] + ". Delete it first to use this name."
					result = ""
				elif len(commandsDict) > 1000:
					send = "I already have 1000 commands saved, to conserve space I won't save any more."
				else:
					commandsDict[name] = cleanDesc

					with open(rollsFile, 'w') as jsonFile:
						json.dump(commandsDict, jsonFile)

					send = "Saving command name '" + name + "' as " + printDesc + ". Here's an example:\n"

	return send, result


def deleteCommand(commandString):

	if not os.path.exists(rollsFile):
		open(rollsFile, 'x').close()

	with open(rollsFile, 'r') as jsonFile:
		dictString = jsonFile.read()

	if len(dictString) == 0:
		commandsDict = {}
	else:
		try:
			with open(rollsFile, 'r') as jsonFile:
				commandsDict = json.load(jsonFile)
		except:
			send = "There was an error in the format of " + rollsFile
			return send

		if commandString not in commandsDict.keys():
			result = "Command not found. Nothing deleted."
		else:
			command = commandsDict[commandString]
			commandsDict.pop(commandString)

			if len(command) > 50:
				command = command[:50] + "..."

			result = "Deleted command '" + commandString + "' " + command

			with open(rollsFile, 'w') as jsonFile:
				json.dump(commandsDict, jsonFile)			

	return result


def getCommand(commandString):


	if not os.path.exists(rollsFile):
		open(rollsFile, 'x').close()

	with open(rollsFile, 'r') as jsonFile:
		dictString = jsonFile.read()

	if len(dictString) == 0:
		commandsDict = {}
	else:
		try:
			with open(rollsFile, 'r') as jsonFile:
				commandsDict = json.load(jsonFile)
		except:
			result = "There was an error in the format of " + rollsFile
			return result

		if commandString not in commandsDict.keys():
			result = "Command not found."
		else:
			command = commandsDict[commandString]

			roll = Roll(command)
			result = roll.format()

	return result

def getCommands():

	if not os.path.exists(rollsFile):
		open(rollsFile, 'x').close()

	with open(rollsFile, 'r') as jsonFile:
		dictString = jsonFile.read()

	if len(dictString) == 0:
		commandsDict = {}
	else:
		try:
			with open(rollsFile, 'r') as jsonFile:
				commandsDict = json.load(jsonFile)
		except:
			result = "There was an error in the format of " + rollsFile
			return result

		commands = []
		for key in sorted(commandsDict):
			command = key + ": " + commandsDict[key]
			if len(command) > 100:
				command = command[:100] + "..."

			commands.append(command)

		result = "\n".join(commands)

	return result

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
	await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=prefix+"roll, "+prefix+"help"))

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

	# Handle a roll command
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

	elif parse.startswith(useSaved):

		result = getCommand(message.content[len(useSaved):].strip())

		# If result was a string, something failed; send string.
		if isinstance(result, str):
			await message.channel.send(result)

		else:
			em = discord.Embed(title = result.title,
								description = author,
								colour = result.colour)
			em.set_footer(text = result.desc)

			await message.channel.send(embed=em)

	elif parse.startswith(saveHelp):
		await message.channel.send(saveDoc)

	elif parse.startswith(save):
		send, result = saveCommand(message.content[len(save):].strip())
		if not (isinstance(result, str)):
			em = discord.Embed(title = result.title,
								description = author,
								colour = result.colour)
			em.set_footer(text = result.desc)
			await message.channel.send(send, embed=em)
		else:
			await message.channel.send(send)

	elif parse.startswith(delete):
		result = deleteCommand(message.content[len(delete):].strip())
		await message.channel.send(result)

	elif parse.startswith(getCommandsList):
		result = getCommands()

		if len(result) < 1000:
			await message.channel.send(result)
		else:
			commands = result.split("\n")

			sendList = []
			for n in (0, len(commands), 20):
				sendList.append("\n".join(commands[n:n+20]))

			for message in sendList:
				await message.channel.send(message)

	# Handle a tros command
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

	# Handle a croll command
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
