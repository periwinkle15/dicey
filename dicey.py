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
/roll [[iterations]x][[number]d[die type]][+[bonus]][drop [number]][,[new roll]]
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
/roll [[iterations]x][[number]d[die type]][+[bonus]][drop [number]][,[new roll]]
Defaults to rolling 1d20
Spaces don't matter.

x has a global scope; it applies to everything after it and cannot be repeated. It causes exactly the same roll to happen again. It must be proceeded by a number.
, has a narrow scope; it creates a new roll, whose default values are set by the previous roll. No input repeats the same roll; a single digit resets the modifier; an xdy sets all values new, including setting the modifier to 0.
The "drop" keywords drops the lowest N rolls, where N defaults to 1 or can be set by appending an integer. It resets to 0 unless a roll is being exactly repeated.
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
"""

def ResolveSimpleDice(Dice, DieType, Bonus, Drop):
	"""
	Creates a DiceResult object given an xdy+z - style roll.
	"""

	result = []

	# roll
	for die in range(Dice):
		if DieType == 0:
			result.append(0)
		else:
			result.append(RollDie(1, DieType))

	# drop lowest, if applicable
	dropList = []
	while len(dropList) < Drop:
		dropList.append(min(result))
		result.remove(min(result))

	CombinedResult = sum(result)+Bonus

	prelude = str(Dice) + 'd' + str(DieType) + '+' + str(Bonus) + ':  '
	resultDesc = ' + '.join([str(i) for i in result])

	if Bonus == 0:
		bonusDesc = ''
	else:
		resultDesc = '(' + resultDesc
		bonusDesc = ') + ' + str(Bonus)
	desc = resultDesc + bonusDesc

	if '+' in desc:
		desc = prelude + desc + ' = ' + str(CombinedResult)
	else:
		desc = prelude + str(CombinedResult)

	if len(dropList) > 0:
		desc += '   (dropped ' + ', '.join([str(i) for i in dropList]) + ')'

	ret = DiceResult()
	ret.title = str(CombinedResult)
	ret.colour = COL_NORM_SUCCESS
	ret.desc = desc.replace("+-", "-").replace("+ -", "- ")
	
	return ret

def parseSimpleRoll(diceString):
	"""
	Does its level best to make sense of the raw input
	and turn it into a series of xdy+z rolls 
	"""

	# Clean up input
	# this isn't cleaning this is horrible
	# i'm really sorry
	diceString = diceString.replace(" ", "").replace("-","+-").replace("++", "+")
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
		defaultDice = 1
		defaultType = 20
		defaultBonus = 0
		defaultDrop = 0

		try: 
			for roll in rolls:

				# Blank rolls go to default
				if len(roll) == 0:
					result.append(ResolveSimpleDice(defaultDice, defaultType, defaultBonus, defaultDrop))
				else:
					# Look for Drop indicator
					dropIndex = roll.find('drop')
					if dropIndex == -1:
						Drop = 0
					elif dropIndex + len('drop') == len(roll):
						Drop = 1
					else:
						Drop = int(roll[dropIndex+len('drop'):])

					if dropIndex != -1:
						roll = roll[:dropIndex]

					if len(roll) == 0:
						Dice = defaultDice
						DieType = defaultType
						Bonus = defaultBonus

					else:

						dIndex=roll.find('d')
						bonusIndex=roll.find('+')

						if bonusIndex == -1:
							bonusIndex = len(roll)

						# If there's no dice given
						if dIndex == -1:
							Dice = defaultDice
							DieType = defaultType
						# If dice number isn't specified but type is, set to 1
						elif dIndex == 0:
							Dice = 1
							DieType = int(roll[dIndex+1:bonusIndex])
						# Both dice and type specified
						else:
							Dice = int(roll[:dIndex])
							DieType = int(roll[dIndex+1:bonusIndex])

						# Determine modifier
						if bonusIndex != len(roll):
							Bonus=int(roll[bonusIndex+1:])
						# If roll was a single number, interpret it as the modifier
						elif 'd' not in roll:
							Bonus = int(roll)
						# If roll was not a single number, but no bonus was specified,
						# set bonus to 0
						else:
							Bonus = 0

					# Reset defaults
					defaultDice = Dice
					defaultType = DieType
					defaultBonus = Bonus
					defaultDrop = Drop

					# Check for excessively large numbers
					if any([DieType>digitLimit, Bonus>digitLimit]):
						return "Hey, stop trying to break me with big numbers :("
					if Dice>rollsLimit:
						return "Sorry... I'd rather not print that many rolls."
					if Drop > Dice:
						return "You're dropping more dice than you're rolling."

					# Return roll
					result.append(ResolveSimpleDice(Dice, DieType, Bonus, Drop))

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
			em = discord.Embed(title=str(", ".join([roll.title for roll in result])),
								colour=COL_NORM_SUCCESS)
			em.set_footer(text=str("\n".join([roll.desc for roll in result])))
			em.description = author

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

# token="NjkzNTczODcxNzcyNjMxMTQx.XvNeBA.mojy46tQSUaLGSqDPrDxm4xNqDs" #Dorian
token="NzI1NDYyMDY1MTQ5NTA5Njc5.XvPFtg.UFU6xmE2Wa6RfXVMKNp3Z7E4lS8" #Dicey
#token=environ['DORIAN_TOKEN']
client.run(token)
