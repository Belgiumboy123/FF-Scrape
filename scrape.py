from itertools import chain
from bs4 import BeautifulSoup
import csv
from time import sleep
import sys
import os
import getopt

class Results:
	def __init__(self):

		# owner -> [wins, losses, totalpoints]
		self.standings = {}

		# Standings if every owner set best starting lineup
		self.standingsOptimal = {}
		
		# Player -> [owner who drafted player, draft cost]
		self.playerDraftMap = {}
		
		# Every wrong decision
		# list of wrong decisions [owner, week, starter nane, bench name, points lost]
		self.wrongDecisionsAll = []
		
		# Every unique wrong decision that would have resulted in optimal lineup
		# list of wrong decisions [owner, week, starter nane, bench name, points lost]
		self.wrongDecisionsOptimal = []

		# Every individual player game data
		# See comment at LoadStatsForTeam
		self.playerData = []

	def outputRows(self, filename, rows):
		with open(filename, "w") as f:
	 		w = csv.writer(f)
	 		w.writerows(rows)

	def outputStandings(self, filename, standings):
	 	standingsList = []
	 	for index,owner in enumerate(standings):
	 		standing = []
	 		standing.append(owner)
	 		for val in standings[owner]:
	 			standing.append(val)
	 		standingsList.append(standing)

	 	with open(filename, "w") as f:
	 		w = csv.writer(f)
	 		w.writerows(standingsList)

	def Output(self):
	 	self.outputRows("wrongDecisionsAll.csv", self.wrongDecisionsAll)
	 	self.outputRows("wrongDecisionsOptimal.csv", self.wrongDecisionsOptimal)
	 	self.outputRows("playerData.csv", self.playerData)
	 	self.outputStandings("standings.csv", self.standings)
	 	self.outputStandings("standingsOptimal.csv", self.standingsOptimal)


PosInSlotMap = 	{ 
					'QB' : ['QB'],
					'RB' : ['RB'],
					'WR' : ['WR'],
					'TE' : ['TE'],
					'DEF': ['Defense'],
					'FLEX' : ['RB', 'WR'],
					'EX-FLEX' : ['RB', 'WR', 'TE']
				}


def DoesPosFitInSlot(pos, slot):
	return pos in PosInSlotMap[slot]

'''
Fantasy Team Name
Player Name
Player Team
Player Position
Amount
'''
def LoadDraft():
	rows = []

	html = open("draft/draft.html", "r").read()
	soup = BeautifulSoup(html, 'html.parser')

	# player -> [draft owner, auction value]
	playerDraftMap = {}
	
	for team in soup.find_all('tr', class_='tableHead'):
		
		for player in team.find_next_siblings('tr'):

			rowData = []
			
			#Need to grab the owner name because
			#We have one too many 'Butt Stuffs' in our league
			title = team.a['title']
			idxStart = title.index('(')
			idxEnd = title.index(')')
			owner = title[idxStart+1:idxEnd]
			rowData.append(owner)

			data = player.find_all('td')
			playerName = data[1].a.text.strip()
			rowData.append(playerName)
			playerData = data[1].text.strip()
			if 'D/ST' in playerData:
				rowData.append("") # defensive team name.
				rowData.append("Defense")
			else:
				playerDetails = playerData.split(',')[1].strip().split()
				rowData.append(playerDetails[0])
				rowData.append(playerDetails[1])

			amount = data[2].text.strip()[1:]
			rowData.append(amount)

			playerDraftMap[str(playerName)] = [str(owner), str(amount)]
			rows.append(rowData)

	with open("draft.csv", "w") as f:
		writer = csv.writer(f)
		writer.writerows(rows)

	return playerDraftMap


#
# Calculate the optimal lineup
#
# Output
# 	list of optimal starters
# 	list of wrong decisions (bench players that should have been started)
#
def RunOptimalLinupAlgo(startingScoreRowData, benchScoreRowData, wrongDecisions):
	
	startingPlayers = startingScoreRowData[:]
	
	playersToInsert = benchScoreRowData[:]
	startersRemovedFromLineup = []

	# Attempts to set the optimal lineup
	# by placing bench players into lineup where they
	# get biggest points gain.
	# The removed starter is then placed back into the queue
	# to see if there is another spot for him
	while len(playersToInsert) > 0:

		player = playersToInsert.pop(0)

		if player[9] <= 0:
			continue

		newSlot = [-1,0]

		for index,starter in enumerate(startingPlayers):
			if not DoesPosFitInSlot(player[7], starter[4]):
				continue

			# Find the biggest point gain for our new player
			pointDiff = player[9] - starter[9]
			if pointDiff > newSlot[1]:
				newSlot[0] = index
				newSlot[1] = pointDiff

		if newSlot[0] > -1:

			# Try to reinsert the now benched player back
			# into starting lineup. Maybe there is still hope
			playerToRemove = startingPlayers[newSlot[0]]
			playersToInsert.append(playerToRemove)

			if not playerToRemove[12]:
				startersRemovedFromLineup.append(startingPlayers[newSlot[0]])

			# set player's slot and place into the starting lineup!
			player[4] = playerToRemove[4]
			startingPlayers[newSlot[0]] = player
			
	# get list of actual swaps and add to wrong decisions list
	# There should be one swap (bench player) per removed starter
	# it doesn't really matter which one
	replacedPlayers = []
	for removedStarter in startersRemovedFromLineup:
		for starter in startingPlayers:
			if starter[12] and DoesPosFitInSlot(removedStarter[7], starter[4]) and starter not in replacedPlayers:
				wrongDecision = []
				wrongDecision.append(starter[1])
				wrongDecision.append(starter[0])
				wrongDecision.append(removedStarter[5])
				wrongDecision.append(starter[5])
				wrongDecision.append(starter[9] - removedStarter[9])
				wrongDecisions.append(wrongDecision)
				replacedPlayers.append(starter)
				break

	return startingPlayers

#
# Return list of players row data from the given playerTable
#
# ScoreRowData
# 0   Week
# 1   Owner name
# 2   TeamName
# 3   Fantasy Opp
# 4   Slot
# 5	  Player Name
# 6   Team
# 7   Pos
# 8   player - Opp
# 9   Pts
# 10  Draft Owner
# 11  Draft Amount
# 12  is original bench
def LoadStatsForTeam(playerTable, index, week, owners, teamNames, playerDraftMap):

	scoreRowData = []

	playerRows = playerTable.find_all('tr', class_='pncPlayerRow')
		
	for row in playerRows:
		rowData = []
		rowData.append(week)
		rowData.append(owners[index])
		rowData.append(teamNames[index])
		rowData.append(teamNames[(index+1)%2])

		isDefense = False
		isBench = False
		slot = row.find('td', class_='playerSlot').text.strip()
		if slot == 'RB/WR':
			slot = 'FLEX'
		elif slot == 'D/ST':
			slot = 'DEF'
			isDefense = True
		elif slot == 'FLEX':
			slot = 'EX-FLEX'
		elif slot == 'Bench':
			isBench = True


		rowData.append(slot)

		playerInfo = row.find('td', class_='playertablePlayerName')

		# Some terrible human forgot to start anyone at all
		if playerInfo is None:
			rowData.append("")
			rowData.append("")
			rowData.append("")
			rowData.append("")
			rowData.append(0.0)
			rowData.append("")
			rowData.append("")
			rowData.append(False)
			scoreRowData.append(rowData)
			continue

		playerName = playerInfo.a.text.strip()
		rowData.append(playerName)

		if isDefense:
			rowData.append("")  #TODO get team name and convert to 3 letter shorthand
			rowData.append("Defense")
		else:
			playerInfoString = playerInfo.text.strip()
			if isBench and playerInfoString.find(",") == -1:
				# Defenses on the bench have no commas
				rowData.append("")
				rowData.append("Defense")
			else:
				details = playerInfoString.split(",")[1].strip().split()
				rowData.append(details[0])
				rowData.append(details[1])

		rowData.append(row.find('td', class_='').text)

		playerPoints = row.find('td', class_='playertableStat').text
		try:
			rowData.append(float(playerPoints))
		except ValueError:
			rowData.append(0.0)

		draftInfo = ["", ""]

		try:
			draftInfo = playerDraftMap[playerName]
		except KeyError:
			pass

		rowData.append(draftInfo[0])
		rowData.append(draftInfo[1])
		rowData.append(isBench)

		scoreRowData.append(rowData)

	return scoreRowData


def UpdateStandings(owners, standings, totalWeekPoints):
	for index,owner in enumerate(owners):
		ownerStandings = []
		try:
			ownerStandings = standings[owner]
		except KeyError:
			standings[owner] = [0,0,0]
			ownerStandings = standings[owner]

		ownerStandings[2] += totalWeekPoints[index]

		oppOwnerIndex = (index+1) % 2

		if( totalWeekPoints[index] > totalWeekPoints[oppOwnerIndex]):
			ownerStandings[0] += 1
		else:
			ownerStandings[1] += 1


def LoadStatsForPage(htmlFile, results):

	html = open(htmlFile, "r").read()
	soup = BeautifulSoup(html, 'html.parser')
  
  	# get week
  	week = soup.find('div', class_='games-pageheader').em.text[5:].strip()

  	# get both players starting lineup tables
	players = soup.find_all('table', class_='playerTableTable tableBody')

	# get both players bench tables
	benches = soup.find_all('table', class_='playerTableTable tableBody hideableGroup')

	# Team names (these are annoyingly not unique across weeks if people changed theirs)
	teamNames = []
	for player in players:
		teamName = player.find('tr', class_='playerTableBgRowHead').td.text[:-9].strip().upper()
		teamNames.append(teamName)

	# Actual un-changing/unique owner names
	owners = []
	ownerNames = soup.find_all('div', class_='teamInfoOwnerData')
	for owner in ownerNames:
		x = owner.encode('utf-8')
		idx =  len('<div class="teamInfoOwnerData">')
		idx2 = x.index("</div>")
		owner = x[idx:idx2]
		owners.append(owner)

	# total week points for each owner in same order as owner names
	# totalWeekPoints[0]  total week points for starting lineups
	# totalWeekPoints[1]  total week pints for optimal lineups
	totalWeekPoints = [[0,0],[0,0]]

	for index,playerTable in enumerate(players):

		startingScoreRowData = LoadStatsForTeam(playerTable, index, week, owners, teamNames, results.playerDraftMap)
		benchScoreRowData = LoadStatsForTeam(benches[index], index, week, owners, teamNames, results.playerDraftMap)

		# Add all starting and bench players to player data
		for row in startingScoreRowData:
			results.playerData.append(row)

		for row in benchScoreRowData:
			results.playerData.append(benchScoreRowData)

		# Get the optimal staring lineup
		optimalScoringPlayers = RunOptimalLinupAlgo(startingScoreRowData, benchScoreRowData, results.wrongDecisionsOptimal) 

		# Calculate total week points for both starting lineup
		# and the optimal starting lineup
		for player in startingScoreRowData:
			totalWeekPoints[0][index] += player[9]

		for player in optimalScoringPlayers:
			totalWeekPoints[1][index] += player[9]

	# update both standings maps from totalWeekPoints
	UpdateStandings(owners, results.standings, totalWeekPoints[0])
	UpdateStandings(owners, results.standingsOptimal, totalWeekPoints[1])

'''
Load stats for every single page found in directory
'''
def LoadStats(results, useTestDir):

	dirname = 'boxscores'
	if useTestDir:
		dirname = 'test'

	for item in os.listdir(dirname):
		print(item)
		LoadStatsForPage(dirname+'/'+item, results)

def main(argv):
	try:
		opts, args = getopt.getopt(argv,"td")
	except getopt.GetoptError:
		print("scrape.py -t [use test dir] -d [parse draft]")
		sys.exit(2)

	loadDraft = False
	useTestDir = False

	for opt, arg in opts:
		if opt == '-t':
			useTestDir = True
		elif opt == '-d':
			loadDraft = True

	results = Results()

	if loadDraft:
		results.playerDraftMap = LoadDraft()

	# Get all data and store in results
	LoadStats(results, useTestDir)

	# Write all of the results out to csv files
	results.Output()	
                             
if __name__ == '__main__':
    main(sys.argv[1:])
