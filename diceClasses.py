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

cRoll = "/croll"
simpleRoll = "/roll"
disconnect = "/disconnect"
doc = "/help"
simpleHelp = "/simplerollhelp"
cRollHelp = "/cocrollhelp"

fail = "Couldn't parse input. Use /help to get more information."

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
	def __init__(self, message=None):
		self.dice = 1
		self.type = 20
		self.bonus = 0
		self.drop = 0
		self.__keepFlag__ = False
		self.success = None
		self.__lessThanFlag__ = False
		self.explode = None
		self.explodeType = "stack"
		self.message = message
		self.result = []

		self.rollsLimit = 50
		self.digitLimit = 10000

		self.__commands__ = r"(drop|keep|exp|explode|>=|=>|<=|=<|[\+!><=d ])"
		self.__mult__ = "Command appears more than once."
		self.__incompatible__ = "Incompatible commands used."
		self.__overRolls__ = "Sorry... I'd rather not print that many rolls."
		self.__overDigits__ = "Hey! Stop trying to break me with big numbers :("
		self.__badExplode__ = "I tried to explode the dice like you asked, but there were too many of them.\nWhatever you were doing, you probably won."

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
		Creates a DiceResult object given an xdy+z - style roll.
		That roll is contained in a Roll() class
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

		CombinedResult = sum(result) + self.bonus

		# Explode
		if self.explode is not None:
			if not self.__explodeFlag__:
				if CombinedResult >= self.explode:
					ret = self.resolve(depth + 1)

					if type(ret) is str:
						return ret
					else:
						retList.extend(ret)

			else:
				if CombinedResult <= self.explode:
					ret = self.resolve(depth + 1)

					if type(ret) is str:
						return ret
					else:
						retList.extend(ret)

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

		# Construct description string
		prelude = ""
		if depth > 0:
			prelude += "Explosion:  "

		prelude += str(self.dice) + "d" + str(self.type)
		if self.bonus != 0:
			prelude += " + " + str(self.bonus)

		if self.success is not None:
			if not self.__lessThanFlag__:
				prelude += ' \u2265 ' 
			else:
				prelude += ' \u2264 '
			prelude += str(self.success)

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

		prelude += ':  '
		resultDesc = ' + '.join([str(i) for i in result])

		if self.bonus == 0:
			bonusDesc = ''
		else:
			resultDesc = '(' + resultDesc
			bonusDesc = ') + ' + str(self.bonus)
			if self.explode is not None and len(retList) > 0:
				bonusDesc += '*' + str(len(retList) + 1)
		desc = resultDesc + bonusDesc

		if '+' in desc:
			desc = prelude + desc + ' = ' + str(CombinedResult)
		else:
			desc = prelude + str(CombinedResult)

		if len(dropList) > 0:
			desc += '  (dropped ' + ', '.join([str(i) for i in dropList]) + ')'

		# Construct DiceResult object to return info
		ret = DiceResult()
		ret.total = CombinedResult
		ret.rollList = result
		ret.dropList = dropList

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
		else:
			ret.title = str(CombinedResult)
		
		ret.desc = desc.replace("+-", "-").replace("+ -", "- ")
		
		retList.append(ret)
		if depth == 0:
			retList.reverse()

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
		# if True:
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
					commands = [item for item in commands if item != " "]
					commands = [item for item in commands if item != ""]
					commands = [item for item in commands if item != "+"]

					temp = []
					for n in range(len(commands)):
						if commands[n] is "-":
							commands[n] = commands[n] + commands[n+1]
							temp.append(n+1)
					commands = [commands[n] for n in range(len(commands)) if n not in temp]


					print(commands)
					# Now search through commands to apply each one.
					# xdy+z syntax
					if "d" in commands:
						index = commands.index("d")
						# Reset values to default - surveys indicate that 
						# this is expected behaviour
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

					# Or interpret a single number as the bonus
					else:
						try:
							self.bonus = int(commands[0])
						except:
							pass

					if "drop" in commands:
						index = commands.index("drop")

						if index + 1 < len(commands):
							if "drop" in commands[index+1:]:
								self.result = self.__mult__
								return self.result

						try:
							self.drop = int(commands[index+1])
							if index + 2 < len(commands):
								if commands[index+2] == "d":
									self.drop = 1
						except:
							self.drop = 1

					if "keep" in commands:
						index = commands.index("keep")

						if "drop" in commands:
							self.result = self.__incompatible__
							return self.result

						if index + 1 < len(commands):
							if "keep" in commands[index+1:]:
								self.result = self.__mult__
								return self.result

						self.__keepFlag__ = True
						try:
							self.drop = int(commands[index+1])
							if index + 2 < len(commands):
								if commands[index+2] == "d":
									self.drop = 1
						except:
							self.drop = 1

					# Three different explode commands
					# Explosion 1
					if "!" in commands:
						index = commands.index("!")

						# Check for compound exploding dice
						if index+1 != len(commands):
							if index + 1 < len(commands):				
								if commands[index+1] == "!":
									self.explodeType = "add"
									index += 1
								else:
									self.explodeType = "stack"

								if index + 1 < len(commands):
									if "!" in commands[index+1:]:
										self.result = self.__mult__
										return self.result

						# Actually set explosion number
						try:
							self.explode = int(commands[index+1])
						except:
							self.explode = self.dice * self.type + self.bonus

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
					
					# Explosion 2
					if "exp" in commands or "explode" in commands:
						try:
							index = commands.index("exp")
						except:
							index = commands.index("explode")

						if "!" in commands[index+1:] or "exp" in commands[index+1:] or "explode" in commands[index+1:]:
							self.result = self.__mult__
							return self.result

						# Compound exploding dice not possible here
						# Set explosion number
						try:
							self.explode = int(commands[index+1])
						except:
							self.explode = self.dice * self.type + self.bonus

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
						if ">" in commands[i] or "<" in commands[i]:
							if i > 0 and commands[i-1] in ["drop", "keep", "!"]:
									continue
							elif setSuccess:
								self.result = self.__mult__
								return self.result

							setSuccess = True
							self.success = int(commands[i+1])
							if ">" in commands[i]:
								if "=" not in commands[i]:
									self.success += 1
							if "<" in commands[i]:
								self.__lessThanFlag__ = True
								if "=" not in commands[i]:
									self.success -= 1

					# Check for bad numbers
					if any([abs(i[1]) > self.digitLimit for i in self.params().items() if type(i[1]) is int]):
						self.result = self.__overDigits__
						return self.result
					if self.dice > self.rollsLimit:
						self.result = __overRolls__
						return self.result
					if self.explode is not None:
						if self.dice * self.type + self.bonus - self.explode == 1:
							self.result = self.__badExplode__
							return self.result

					# Return roll
					res = self.resolve()
					if type(res) is str:
						self.result = res
						return self.result

					self.result.extend(res)


			return self.result

		except:
			return ValueError