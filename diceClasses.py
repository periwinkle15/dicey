#!/usr/bin/env python3
"""
Dicey die rolling classes
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
from dicey_token import token

"""
Global variables
"""

fail = "Couldn't parse input. Use /help to get more information."

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

trosRollDoc = """
```
/tros [[iterations]x][[pool]/[target number]] OR simple roll[, [new roll]]
Spaces don't matter. 

Shortcuts for rolling The Riddle of Steel, based on their notation pool (number of dice rolled) / target number (success boundary). No modifiers or default values available.

If the x/y notation is not used, the roll is resolved as if it were a simple roll. Simple roll iteration commands can be used.

Examples:
		/tros 4/7
		1 Success(es)
		Tyelcamo's roll
		1d10 ≥ 7 !! ≥ 10:  5  < 7
		1d10 ≥ 7 !! ≥ 10:  9  ≥ 7
		1d10 ≥ 7 !! ≥ 10:  4  < 7
		1d10 ≥ 7 !! ≥ 10:  2  < 7

		/tros 2x3/6, 1d6
		2 Success(es), 3, 1 Success(es), 1
		Tyelcamo's roll
		1d10 ≥ 6 !! ≥ 10:  4  < 6
		1d10 ≥ 6 !! ≥ 10:  8  ≥ 6
		1d10 ≥ 6 !! ≥ 10:  5  < 6
		1d6:  3
		1d10 ≥ 6 !! ≥ 10:  2  < 6
		1d10 ≥ 6 !! ≥ 10:  5  < 6
		1d10 ≥ 6 !! ≥ 10:  10 + 5 = 15  ≥ 6
		Explosion:  1d10 !! ≥ 10:  5
		1d6:  1

```
"""

"""
Setup functions and classes
"""

class DiceResult:
	def __init__(self):
		self.title = ""
		self.desc = ""
		self.rollList = []
		self.dropList = []
		self.total = 0

		self.COL_CRIT_SUCCESS = 0xFFFFFF
		self.COL_EXTR_SUCCESS = 0xf1c40f
		self.COL_HARD_SUCCESS = 0x2ecc71
		self.COL_NORM_SUCCESS = 0x2e71cc
		self.COL_NORM_FAILURE = 0xe74c3c
		self.COL_CRIT_FAILURE = 0x992d22

		self.colour = self.COL_NORM_SUCCESS

class Roll:

	# Basic attributes
	dice = 1
	bonus = 0
	drop = 0
	__keepFlag__ = False
	__lessThanFlag__ = False
	result = []

	rollsLimit = 50
	digitLimit = 10000

	__commands__ = r"(drop|keep|>=|=>|<=|=<|/|[\+!><=d ])"
	__fail__ = "Couldn't parse input. Use /help to get more information."
	__mult__ = "Command appears more than once."
	__incompatible__ = "Incompatible commands used."
	__overRolls__ = "Sorry... I'd rather not print that many rolls."
	__overDigits__ = "Hey! Stop trying to break me with big numbers :("
	__badExplode__ = "I tried to explode the dice like you asked, but there were too many of them.\nWhatever you were doing, you probably won."

	def __init__(self, message=None):
		# Default setup for a D&D-style roller which can be
		# modified to perform nearly any roll

		self.type = 20
		self.success = None
		self.explode = None
		self.explodeType = "stack"

		self.message = message

		if self.message is not None:
			self.parse()

	def params(self):
		return {"Dice": self.dice, 
				"Type": self.type,
				"Bonus": self.bonus,
				"Drop": self.drop, 
				"Success": self.success,
				"Explode": self.explode,
				"Message": self.message}

	def getRollsLimit(self):
		return self.rollsLimit

	def getDigitLimit(self):
		return self.digitLimit

	def setRollsLimit(self, n):
		self.rollsLimit = n

	def setDigitLimit(self, n):
		self.digitLimit = n

	def getResult(self):
		return self.result

	def rollDie(self, minimum=1, maximum=20):
		return randint(minimum,maximum)

	def __reset__(self):
		self.dice = 1
		self.type = 20
		self.bonus = 0
		self.drop = 0
		self.__keepFlag__ = False
		self.success = None
		self.__lessThanFlag__ = False
		self.explode = None
		self.__explodeFlag__ = False
		self.explodeType = "stack"		

	def resolve(self, depth=0):
		"""
		Creates a DiceResult object given an xdy+z - style roll
		contained in a Roll() class
		"""

		if depth > self.rollsLimit:
			return self.__badExplode__

		result = []
		retList = []

		# roll
		for die in range(self.dice):
			if self.type == 0:
				result.append(0)
			else:
				result.append(self.rollDie(1, self.type))

		# drop lowest or keep lowest, if applicable
		dropList = []
		if not self.__keepFlag__:
			while len(dropList) < self.drop:
				dropList.append(min(result))
				result.remove(min(result))
		else:
			while len(result) > self.drop:
				dropList.append(max(result))
				result.remove(max(result))

		# Add up
		CombinedResult = sum(result) + self.bonus

		# Explode
		if self.explode is not None:
			# Stacking explosions
			if not self.__explodeFlag__:
				if CombinedResult >= self.explode:
					ret = self.resolve(depth + 1)

					if type(ret) is str:
						return ret
					else:
						retList.extend(ret)

			# Adding explosions
			else:
				if CombinedResult <= self.explode:
					ret = self.resolve(depth + 1)

					if type(ret) is str:
						return ret
					else:
						retList.extend(ret)

		# Notate adding explosions correctly.
		if depth == 0 and self.explodeType == "add":
			for ret in retList[::-1]:
				CombinedResult += ret.total
				result.extend(ret.rollList)
				result.extend(ret.dropList)

		# Check for success, if applicable
		success = ""
		if self.success is not None:
			if not self.__lessThanFlag__:
				if CombinedResult >= self.success:
					success = "Success"
				else:
					success = "Failure"
			else:
				if CombinedResult <= self.success:
					success = "Success"
				else:
					success = "Failure"

		# Begin constructing description string
		prelude = ""
		if depth > 0:
			prelude += "Explosion:  "

		# Basic roll
		prelude += str(self.dice) + "d" + str(self.type)
		if self.bonus != 0:
			prelude += " + " + str(self.bonus)

		# Success indicator
		if self.success is not None:
			if depth == 0 or self.explodeType == "stack":
				if not self.__lessThanFlag__:
					prelude += ' \u2265 ' 
				else:
					prelude += ' \u2264 '
				prelude += str(self.success)

		# Explosion indicator
		if self.explode is not None:
			if self.explodeType == "stack":
				prelude += " ! "
			elif self.explodeType == "add":
				prelude += " !! "

			if not self.__explodeFlag__:
				prelude += "\u2265 "
			else:
				prelude += "\u2264 "
			prelude += str(self.explode)

		# Show rolls made
		prelude += ':  '
		resultDesc = ' + '.join([str(i) for i in result])

		# Show bonus dice
		if self.bonus == 0:
			bonusDesc = ''
		else:
			resultDesc = '(' + resultDesc
			bonusDesc = ') + ' + str(self.bonus)

			# Show added bonus dice properly
			if self.explode is not None and len(retList) > 0 and depth == 0:
				bonusDesc += '*' + str(len(retList) + 1)
		desc = resultDesc + bonusDesc

		# Show total if applicable
		if '+' in desc:
			desc = prelude + desc + ' = ' + str(CombinedResult)
		else:
			desc = prelude + str(CombinedResult)

		# Show dropped dice if applicable
		if len(dropList) > 0:
			desc += '  (dropped ' + ', '.join([str(i) for i in dropList]) + ')'

		# Construct DiceResult object to return info
		ret = DiceResult()
		ret.total = CombinedResult
		ret.rollList = result
		ret.dropList = dropList

		# Set success indicators (if not an added explosion die)
		ret.title = str(CombinedResult)
		if not (depth > 0 and self.explodeType == "add"):
			if success == 'Success':
				if not self.__lessThanFlag__:
					desc += '  \u2265 '
				else:
					desc += '  \u2264 '
				desc += str(self.success
					)
				ret.title = success
				ret.colour = ret.COL_HARD_SUCCESS

			elif success == 'Failure':
				desc += '  < ' + str(self.success)
				ret.title = success
				ret.colour = ret.COL_NORM_FAILURE
				
		# Clean up the description
		ret.desc = desc.replace("+-", "-").replace("+ -", "- ")
		
		# Make sure exploded dice appear in the right order
		retList.append(ret)
		if depth == 0:
			retList.reverse()

			# Show added exploded dice properly
			if self.explodeType == "add":
				for ret in retList[1:]:
					retList[0].desc += "\n" + ret.desc
				retList = [retList[0]]

		return retList

	def parse(self, message=None):
		"""
		Does its level best to make sense of the raw input
		and turn it into a series of xdy+z rolls 
		"""

		if message is None:
			message = self.message

		# The whole thing is in a try and will return ValueError on failure
		try:

			# Clean up input
			# Removes spaces, changes minus signs to deal with negative integers
			message = message.replace("-","+-")
			message = message.replace("++", "+")

			# Look for the x multiplier
			multIndex = message.find("x")
			if multIndex != -1:
				iterations = int(message[:multIndex])
				message = message[multIndex+1:]
			else:
				iterations = 1

			# Split up different rolls
			rolls = message.split(",")

			# Check for excessively large number of loops being required
			if len(rolls)*iterations > self.rollsLimit:
				return self.__overRolls__

			# Loop through rolls
			self.result = []
			for n in range(iterations):

				# Defaults are reset each iteration to ensure the same result
				self.__reset__()

				for roll in rolls:

					# Regular expression matches all possible commands
					# Note that order does matter to avoid collision
					# between "drop" and "d"

					commands = re.split(self.__commands__, roll)

					# Clean up the result a bit.
					commands = [item for item in commands if item != " "]
					commands = [item for item in commands if item != ""]
					commands = [item for item in commands if item != "+"]

					for n in range(len(commands)):
						if commands[n] is "-":
							commands[n] = commands[n] + commands[n+1]

					commands = [item for item in commands if item != "-"]

					# Now search through commands to apply each one.
					# xdy+z syntax
					if "d" in commands:
						index = commands.index("d")

						# If a new roll type is set, reset values to
						# default - surveys indicate that this is expected
						# behaviour
						self.__reset__()

						if index != 0:
							try:
								self.dice = int(commands[index-1])
							except:
								pass

						self.type = int(commands[index+1])
						try:
							self.bonus = int(commands[index+2])
						except:
							pass

					# If no d, interpret a single number as the bonus
					else:
						try:
							self.bonus = int(commands[0])
						except:
							pass

					# On to more complicated problems - drop and keep
					if "drop" in commands:
						index = commands.index("drop")

						# Check for duplicates
						if index + 1 < len(commands):
							if "drop" in commands[index+1:]:
								self.result = self.__mult__
								return self.result

						# Check for non-default (1) drop value
						try:
							self.drop = int(commands[index+1])
							if index + 2 < len(commands):
								# Undo that if drop was in front
								# of a "d" command
								if commands[index+2] == "d":
									self.drop = 1
						except:
							self.drop = 1

					# Redo for the "keep" command
					if "keep" in commands:
						index = commands.index("keep")

						# Check for duplicates
						if "drop" in commands:
							self.result = self.__incompatible__
							return self.result

						# Check for duplicates
						if index + 1 < len(commands):
							if "keep" in commands[index+1:]:
								self.result = self.__mult__
								return self.result

						# Set keep andd check for non-default
						self.__keepFlag__ = True
						try:
							self.drop = int(commands[index+1])
							if index + 2 < len(commands):
								# Undo that if keep was in front
								# of  "d" command
								if commands[index+2] == "d":
									self.drop = 1
						except:
							self.drop = 1

					# Explosion
					if "!" in commands:
						index = commands.index("!")

						# Check for compound exploding dice
						if index + 1 < len(commands):				
							if commands[index+1] == "!":
								self.explodeType = "add"
								index += 1
							else:
								self.explodeType = "stack"

							# Check for duplicates
							if index + 1 < len(commands):
								if "!" in commands[index+1:]:
									self.result = self.__mult__
									return self.result

						# Actually set explosion number
						try:
							self.explode = int(commands[index+1])
						except:
							self.explode = self.dice * self.type + self.bonus

							# Look for comparison symbols
							if index+1 != len(commands):
								if ">" in commands[index+1]:
									self.explode = int(commands[index+2])
									if "=" not in commands[index+1]:
										self.explode += 1

								elif "<" in commands[index+1]:
									self.explode = int(commands[index+2])
									self.__explodeFlag__ = True
									if "=" not in commands[index+1]:
										self.explode -= 1

					# Set success threshhold
					# A bit different from the others to handle notation
					# overlap with exploding dice
					setSuccess = False
					for i in range(len(commands)):
						# Check for a comparison symbol
						if ">" in commands[i] or "<" in commands[i]:
							# Check that it's not found a !
							if i > 0:
								if commands[i-1] == "!":
									continue

							# Check for duplicates
							elif setSuccess:
								self.result = self.__mult__
								return self.result

							# Set success limit
							setSuccess = True
							self.success = int(commands[i+1])
							# Check comparison symbol
							if ">" in commands[i]:
								if "=" not in commands[i]:
									self.success += 1
							if "<" in commands[i]:
								self.__lessThanFlag__ = True
								if "=" not in commands[i]:
									self.success -= 1

					# Check for bad numbers
					# Might add more to these later.
					# Too many digits
					if any([abs(i[1]) > self.digitLimit for i in self.params().items() if type(i[1]) is int]):
						self.result = self.__overDigits__
						return self.result
					# Too many rolls
					if self.dice > self.rollsLimit:
						self.result = __overRolls__
						return self.result
					# Infini-explode
					if self.explode is not None:
						if self.dice * self.type + self.bonus - self.explode == 1:
							self.result = self.__badExplode__
							return self.result

					# Return roll
					res = self.resolve()
					if type(res) is str:
						self.result = res
						return self.result
					else:
						self.result.extend(res)

			return self.result

		except:
			return ValueError

	def format(self):
		# D&D-style formatting

		# If result was a string, something failed; send string.
		if isinstance(self.result, str):
			return self.result
		elif ValueError in self.result:
			return self.__fail__

		# Else the function returns a list of DiceResult objects
		# Concatenate them into a text box
		else:
			sendResult = DiceResult()

			# Count successes; if there's a number result between strings
			# of successes or failures, interrupt the count with the number
			titles = [roll.title for roll in self.result]
			sendResult.title = ""

			successes = []
			for title in titles:
				# Build up success reports until interrupted
				if title == "Success" or title == "Failure":
					successes.append(title)
				else:

					# Report and reset successes
					if successes != []:
						# Add comma if necessary
						if sendResult.title !=  "":
							if sendResult.title[-1] != " ":
								sendResult.title += ", "

						sendResult.title += str(successes.count("Success")) + " Success(es)"
						successes = []

					# Check comma again
					if sendResult.title !=  "":
						if sendResult.title[-1] != " ":
							sendResult.title += ", "

					# Report number result
					sendResult.title += title

			# Check for success reports left over
			if successes != []:
				# Add comma if necessary
				if sendResult.title !=  "":
					if sendResult.title[-1] != " ":
						sendResult.title += ", "

				sendResult.title += str(successes.count("Success")) + " Success(es)"

			# Set colour
			if "Success" in titles or "Failure" in titles:

				if titles.count("Success") == titles.count("Success") + titles.count("Failure"):
					sendResult.colour = sendResult.COL_HARD_SUCCESS
				elif "Success" not in titles:
					sendResult.colour = sendResult.COL_NORM_FAILURE
				else:
					sendResult.colour = sendResult.COL_NORM_SUCCESS

			sendResult.desc = str("\n".join([roll.desc for roll in self.result]))

			if len(sendResult.title) > 256:
				return self.__overRolls__
			if len(sendResult.desc) >= 2048:
				sendResult.desc = "description too long; surpressed"

			return sendResult

class RoS(Roll):

	def __init__(self, message=None):
		# Default setup for a The Riddle of Steel-style roller which can be
		# can only take a few commands

		self.type = 10
		self.success = None
		self.explode = self.type
		self.explodeType = "add"

		self.message = message

		if self.message is not None:
			self.parse()

	def __reset__(self):
		self.dice = 1
		self.type = 10
		self.bonus = 0
		self.drop = 0
		self.__keepFlag__ = False
		self.success = None
		self.__lessThanFlag__ = False
		self.explode = self.type
		self.__explodeFlag__ = False
		self.explodeType = "add"

	def parse(self, message=None):
		"""
		Does its level best to make sense of the raw input
		and turn it into a series of xdy+z rolls 
		"""

		if message is None:
			message = self.message

		# The whole thing is in a try and will return ValueError on failure
		try:

			# Clean up input
			# Removes spaces, changes minus signs to deal with negative integers
			message = message.replace("-","+-")
			message = message.replace("++", "+")

			# Look for the x multiplier
			multIndex = message.find("x")
			if multIndex != -1:
				iterations = int(message[:multIndex])
				message = message[multIndex+1:]
			else:
				iterations = 1

			# Split up different rolls
			rolls = message.split(",")

			# Check for excessively large number of loops being required
			if len(rolls)*iterations > self.rollsLimit:
				return self.__overRolls__

			# Loop through rolls
			self.result = []
			for n in range(iterations):

				# Defaults are reset each iteration to ensure the same result
				self.__reset__()

				for roll in rolls:

					# Pass xdy style rolls back to the parent class
					if "/" not in roll:
						res = Roll(roll).result
						if res is ValueError:
							return ValueError
						elif isinstance(res, str):
							return res
						else:
							self.result.extend(res)

					else:

						# Regular expression matches all possible commands
						# Note that order does matter to avoid collision
						# between "drop" and "d"

						commands = re.split(self.__commands__, roll)

						# Clean up the result a bit.
						commands = [item for item in commands if item != " "]
						commands = [item for item in commands if item != ""]
						commands = [item for item in commands if item != "+"]

						for n in range(len(commands)):
							if commands[n] is "-":
								commands[n] = commands[n] + commands[n+1]

						commands = [item for item in commands if item != "-"]

						# The Riddle of Steel notates rolls with syntax
						# Pool / Target Number

						# Set success
						index = commands.index("/")
						self.success = int(commands[index+1])

						# Roll targets
						for i in range(int(commands[index-1])):
							res = self.resolve()
							if type(res) is str:
								self.result = res
								return self.result
							else:
								self.result.extend(res)

			return self.result

		except:
			return ValueError

