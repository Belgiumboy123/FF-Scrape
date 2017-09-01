from enum import Enum
from random import randint

Weeks = 13

class M(Enum):
	brecht = 0
	nick = 1
	phil = 2
	kevin = 3
	andy = 4
	jack = 5
	micah = 6
	mel = 7
	bot = 8
	drew = 9

class D(Enum):
	east = 0
	west = 1

divisions = {D.east: [M.brecht, M.nick, M.phil, M.kevin, M.andy],
	D.west: [M.jack, M.micah, M.mel, M.bot, M.drew]}

schedules = dict([(m, [''] * Weeks) for m in M])

def InSameDivision(team1, team2):
	return team1 in divisions[D.east] and team2 in divisions[D.east] or \
		team1 in divisions[D.west] and team2 in divisions[D.west]

def GetNumberOfExistingMatchups(team1, team2):
	return schedules[team1].count(team2)
		
def HasOpponent(team, week):
	return schedules[team][week] != ''
		
def IsValidNewMatchup(team1, team2, week):
	
	if HasOpponent(team1, week) or HasOpponent(team2, week):
		return False

	if InSameDivision(team1, team2):
		return GetNumberOfExistingMatchups(team1, team2) < 2
	else:
		return GetNumberOfExistingMatchups(team1, team2) < 1
		
def GetRandomOpponent(team1):
	opp = team1
	while opp == team1:
		opp = M(randint(0, 9))
	return opp
		
def main():
	
	for week in range(0,1):
		for m in M:
			if HasOpponent(m, week):
				continue
	
			foundOpp = False
			while not foundOpp:
				newOpp = GetRandomOpponent(m)
				if IsValidNewMatchup(m, newOpp, week):
					schedules[m][week] = newOpp
					schedules[newOpp][week] = m
					foundOpp = True
	
	# Double check that each team plays it's own division members twice, and the other once
	for m1 in M:
		for m2 in M:
			pass
	
	for week in range(0, 1):
		print("Week 1")
		printedMembers = []
		for m in M:
			if m not in printedMembers:
				opp = schedules[m][week]
				print("\t" + m.name + "\t  vs\t" +  opp.name) 
				printedMembers.append(m)
				printedMembers.append(opp)
		print("\n\n")
		
	
main()