from enum import Enum
from random import sample

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
		
	
def main():
		
	week = 0
	while week < Weeks:
		print("Generating opponents " + str(week))
		
		success = True
		
		try:
			for m in M:
				if HasOpponent(m, week):
					continue
		
				foundOpp = False
				newOpponnents = set(M)
				newOpponnents.discard(m)				
				while not foundOpp:

					newOpp = sample(newOpponnents, 1)[0]
					newOpponnents.discard(newOpp)
					if IsValidNewMatchup(m, newOpp, week):
						schedules[m][week] = newOpp
						schedules[newOpp][week] = m
						foundOpp = True
		except:
			success = False
		
		
		if not success:
			for m in M:
				schedules[m][week] = ''
				schedules[m][week-1] = ''
				schedules[m][week-2] = ''
			week = week - 2
			print("trying again")
		else:
			week = week + 1
	
	print("\nDouble checking opponents are correct\n")
	noFailures = True
	# Double check that each team plays it's own division members twice,
	# and the other division just once
	for m1 in M:
		for m2 in M:
			if m1 == m2:
				if schedules[m1].count(m2) != 0:
					noFailures = False
			elif InSameDivision(m1, m2):
				if schedules[m1].count(m2) != 2:
					noFailures = False
			else:
				if schedules[m1].count(m2) != 1:
					noFailures = False
	
	if noFailures:
		f = open("schedules.txt", "w")
		for week in range(0, Weeks):
			f.write("Week " + str(week+1) + "\n")
			printedMembers = []
			for m in M:
				if m not in printedMembers:
					opp = schedules[m][week]
					f.write("\t" + m.name + "\t  vs\t" +  opp.name + "\n")
					printedMembers.append(m)
					printedMembers.append(opp)
			f.write("\n\n")
		print("Success schedule written to file")
	else:
		print("Failures have been found")
		print(schedules)
	
main()