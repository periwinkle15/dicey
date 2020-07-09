#!/usr/bin/env python3
"""
Dicey die rolling discord bot.
Thanks to the bot Dorian for the basic structure.
"""

"""
Imports
"""
import discord
import re
import logging
import asyncio
from os import environ
from random import randint

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

/disconnect
As on tin

/help
You already found me!
```
"""

simpleRollDoc = """
```
/roll [[iterations]x][[number]d[die type]][+/-[bonus]][drop [number]][>[=]success boundary][![>[=] exploding dice][,[new roll]]
Defaults to rolling 1d20
Spaces don't matter.

In order (and order does matter; it's set by what order the operations make sense in):
[[iterations]x] has global scope; it applies to everything after it and cannot be repeated. It causes the same input to be used again; /roll 2x performs /roll twice.
[number] on its own is interpreted as a bonus to the default roll.
[xdy] rolls a y-sided die x times and adds together the results. If x is ommitted, it defaults to 1.
[+ or - bonus] adds or subtracts a fixed amount to the total.
[drop] drops the lowest N rolls from the total, where N defaults to 1 or can be set by appending an integer. It resets to 0 unless a roll is being exactly repeated.
[>[=]] sets a boundary above which rolls will be counted as a success, and reported as successes or failures instead of raw numbers. Use >None to reset it to nonexistence.
[!] causes World of Darkness style exploding dice (rolls above a certain value trigger a new roll). It applies to the total xdy+z, not to each individual dy. It defaults to the maximum number; set a boundary with [>[=]]. Reset to nonexistence with !None.
[,] allows you to enter a new roll. Instead of 1d20, defaults will be set by the previous roll.

Examples:
		/roll
		2
		1d20+0: 2

		/roll 2d10+2
		13, 22
		2d10+2: (5+6) + 2 = 13
		2d10+2: (1+8) + 2 = 11

		/roll 2x3d17+3,2 drop 2,d4
		32, 4, 4, 40, 14, 3
		3d17+3:  (17 + 7 + 5) + 3 = 32
		3d17+2:  (2) + 2 = 4 (dropped 1, 1)
		1d4+0:  4
		3d17+3:  (15 + 16 + 6) + 3 = 40
		3d17+2:  (12) + 2 = 14 (dropped 3, 8)
		1d4+0:  3
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
Setup functions and classes
"""

class DiceResult:
	def __init__(self):
		self.title=""
		self.desc=""
		self.colour=COL_NORM_SUCCESS

class Roll:
	def __init__(self):
		self.dice = 1
		self.type = 20
		self.bonus = 0
		self.drop = 0
		self.success = None
		self.explode = None

	def params(self):
		return {"Dice": self.dice, 
				"Type": self.type,
				"Bonus": self.bonus,
				"Drop": self.drop, 
				"Success": self.success,
				"Explode": self.explode}

def RollDie(minimum=1, maximum=20):
	result = randint(minimum,maximum)
	return result

"""
Call of Cthulhu - roller that does penalty dice, bonus dice, and thresholds.
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

"""
Simple d20-style dice rolling functions
lmao "simple"
"""

def ResolveSimpleDice(rollObject, depth=0):
	"""
	Creates a DiceResult object given an xdy+z - style roll.
	That roll is contained in a Roll() class
	"""

	if depth > rollsLimit:
		return "I tried to explode the dice like you asked, but there were too many of them.\nWhatever you were doing, you probably won."

	result = []
	retList = []

	# roll
	for die in range(rollObject.dice):
		if rollObject.type == 0:
			result.append(0)
		else:
			result.append(RollDie(1, rollObject.type))

	# drop lowest, if applicable
	dropList = []
	while len(dropList) < rollObject.drop:
		dropList.append(min(result))
		result.remove(min(result))

	CombinedResult = sum(result) + rollObject.bonus

	# Explode
	if rollObject.explode is not None:
		if CombinedResult >= rollObject.explode:
			ret = ResolveSimpleDice(rollObject, depth + 1)

			if type(ret) is str:
				return ret
			else:
				retList.extend(ret)

	# Check for success, if applicable
	success = ''
	if rollObject.success is not None:
		if CombinedResult >= rollObject.success:
			success = 'Success'
		else:
			success = 'Failure'

	# Construct description string
	prelude = ''
	if depth > 0:
		prelude += 'Explosion:  '

	prelude += str(rollObject.dice) + 'd' + str(rollObject.type) + ' + ' + str(rollObject.bonus) 

	if rollObject.success is not None:
		prelude += ' \u2265 ' + str(rollObject.success)

	if rollObject.explode is not None:
		prelude += ' ! \u2265 ' + str(rollObject.explode)

	prelude += ':  '
	resultDesc = ' + '.join([str(i) for i in result])

	if rollObject.bonus == 0:
		bonusDesc = ''
	else:
		resultDesc = '(' + resultDesc
		bonusDesc = ') + ' + str(rollObject.bonus)
	desc = resultDesc + bonusDesc

	if '+' in desc:
		desc = prelude + desc + ' = ' + str(CombinedResult)
	else:
		desc = prelude + str(CombinedResult)

	if len(dropList) > 0:
		desc += '   (dropped ' + ', '.join([str(i) for i in dropList]) + ')'

	# Construct DiceResult object to return info
	ret = DiceResult()

	if success == 'Success':
		desc += '  \u2265 ' + str(rollObject.success)
		ret.title = success
		ret.colour = COL_HARD_SUCCESS
	elif success == 'Failure':
		desc += '  < ' + str(rollObject.success)
		ret.title = success
		ret.colour = COL_NORM_FAILURE
	else:
		ret.title = str(CombinedResult)
	
	ret.desc = desc.replace("+-", "-").replace("+ -", "- ")
	
	retList.append(ret)

	if depth == 0:
		retList.reverse()

	return retList

def parseSimpleRoll(diceString):
	"""
	Does its level best to make sense of the raw input
	and turn it into a series of xdy+z rolls 
	"""

	# Clean up input
	# this isn't cleaning this is horrible
	# i'm really sorry
	diceString = diceString.replace(" ", "")
	diceString = diceString.replace("-","+-")
	diceString = diceString.replace("++", "+")

	# Split up different rolls
	rolls = diceString.split(",")

	# Look for the x multiplier
	try:
		multIndex = rolls[0].find("x")
		if multIndex != -1:
			iterations = int(rolls[0][:multIndex])
			rolls[0] = rolls[0][multIndex+1:]
		else:
			iterations = 1
	# Return help doc on failure
	except:
		return fail

	# Check for excessively large number of loops being required
	if len(rolls)*iterations > rollsLimit:
		return "Sorry... I'd rather not print that many rolls."

	# Loop through rolls
	result = []
	for n in range(iterations):
		# Defaults are reset each iteration to ensure the same result
		rollParams = Roll()

		# if True:
		try: 
			for roll in rolls:

				# Blank rolls go to default
				if len(roll) == 0:
					result.extend(ResolveSimpleDice(rollParams))

				else:

					# If the roll isn't the same, default success back to nonexistence
					rollParams.success = None

					# "Exploding dice"
					explodeIndex = roll.find('!')
					explodeString = ''
					if explodeIndex != -1:
						explodeString = roll[explodeIndex:]

						roll = roll[:explodeIndex]

					# If there's still stuff left...
					if len(roll) != 0:

						# Look for >
						successIndex = roll.find('>')
						if successIndex != -1:

							if roll[successIndex+1] == '=':
								rollParams.success = int(roll[successIndex+2:])
							elif "none" in roll[successIndex:]:
								rollParams.success = None
							else:
								rollParams.success = int(roll[successIndex+1:])+1

							roll = roll[:successIndex]


						# If there's still stuff left...
						if len(roll) != 0:

							# Look for Drop indicator
							dropIndex = roll.find('drop')
							if dropIndex == -1:
								rollParams.drop = 0
							elif dropIndex + len('drop') == len(roll):
								rollParams.drop = 1
							else:
								rollParams.drop = int(roll[dropIndex+len('drop'):])

							if dropIndex != -1:
								roll = roll[:dropIndex]

							# If there's still stuff left...
							if len(roll) != 0:

								dIndex=roll.find('d')
								bonusIndex=roll.find('+')

								if bonusIndex == -1:
									bonusIndex = len(roll)

								# If dice number isn't specified but type is, set to 1
								if dIndex == 0:
									rollParams.dice = 1
									rollParams.type = int(roll[dIndex+1:bonusIndex])
								# Both dice and type specified
								elif dIndex != -1:
									rollParams.dice = int(roll[:dIndex])
									rollParams.type = int(roll[dIndex+1:bonusIndex])

								# Determine modifier
								if bonusIndex != len(roll):
									rollParams.bonus = int(roll[bonusIndex+1:])
								# If roll was a single number, interpret it as the modifier
								elif 'd' not in roll:
									rollParams.bonus = int(roll)
								# If roll was not a single number, but no bonus was specified,
								# set bonus to 0
								else:
									rollParams.bonus = 0

					if explodeString == '!':
						rollParams.explode = rollParams.type
					elif '=' in explodeString:
						rollParams.explode = int(explodeString[3:])
					elif '>' in explodeString:
						rollParams.explode = int(explodeString[2:]) + 1
					elif 'none' in explodeString:
						rollParams.explode = None
					elif explodeString != "":
						return fail

					# Check for bad numbers
					if any([abs(i[1]) > digitLimit for i in rollParams.params().items() if i[1] is not None]):
						return "Hey, stop trying to break me with big numbers :("
					if rollParams.dice > rollsLimit:
						return "Sorry... I'd rather not print that many rolls."
					if rollParams.drop > rollParams.dice:
						return "You're dropping more dice than you're rolling."
					if rollParams.drop < 0:
						return "Can't drop negative number of dice."
					if rollParams.explode is not None:
						if rollParams.dice * rollParams.type + rollParams.bonus - rollParams.explode == 1:
							return "That would be an infini-explosion... that's mean :("

					# Return roll
					res = ResolveSimpleDice(rollParams)
					if type(res) is str:
						return res

					result.extend(res)

		# Return help doc on failure
		except:
			return fail

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

@client.event
async def on_message(message):
	"""
	Listens to incoming messages
	"""
	# Disregard the bot's own messages
	if message.author == client.user:
		return

	# Get basic info
	parse = message.content.lower().replace(" ", "")
	if isinstance(message.author.nick, str):
		author = message.author.nick
	else:
		author = message.author.name
	author += "'s roll"


	# Cute extras
	if "badrobot" in parse or "badbot" in parse:
		await message.channel.send(":cry:")

	elif "goodrobot" in parse or "goodbot" in parse:
		await message.channel.send("Thanks! :smile:")

	elif "dicey" in message.content.lower():
		# Don't want to interpret things like "dice yes" here
		await message.channel.send("Hi!")

	# Handle a /roll command
	elif parse.startswith(simpleRoll):
		result = parseSimpleRoll(parse[len(simpleRoll):])

		# If result was a string, something failed; send string.
		if isinstance(result, str):
			await message.channel.send(result)

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

token=environ['DICEY_TOKEN']
client.run(token)
