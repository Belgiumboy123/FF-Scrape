from bs4 import BeautifulSoup
from decimal import Decimal
from itertools import chain
import csv
import getopt
import os
import sys

# Base class used to hold generic data
# The csv writer works on arrays so this class
# Wraps an array giving user ability to set named attributes
# on am instance.
class RowData:

	# values and attrs arrays must be of same length
	# each index maps to the other in same array
	# default values are set in derived class constructor
	def __init__(self):
		self.values = []
		self.attrs =  []

	# Order in which fields get written to file
	def __getitem__(self, i):
		return self.values[i]

	# if 'attrs' field doesn't exist yet, set attr as normal
	# otherwise this will crash if 'attr' isn't in self.attrs list
	def __setattr__(self, attr, value):
		if "attrs" not in self.__dict__:
			self.__dict__[attr] = value
		else:
			attrIndex = self.__dict__["attrs"].index(attr)
			self.__dict__["values"][attrIndex] = value	

	def __getattr__(self, attr):
		if attr in self.__dict__:
			return self.__dict__[attr]
		else:
			attrIndex = self.__dict__["attrs"].index(attr)
			return self.__dict__["values"][attrIndex]

	def __len__(self):
		return len(self.values)

	def __eq__(self, other):
		return self.values == other.values

	def __str__(self):
		return str(self.__dict__)

# One wrong lineup decision made by an owner
# removedStarter and benchPlayer are both PlayerBoxScore instances
class WrongDecision(RowData):
	def __init__(self, replacedStarter, benchPlayer):
		self.values = ["", 0, "", "", 0]
		self.attrs =  ["owner", "week", "replacedStarter", "benchPlayer", "pointsLost"]

		self.owner = replacedStarter.owner
		self.week = replacedStarter.week
		self.replacedStarter = replacedStarter.playerName
		self.benchPlayer = benchPlayer.playerName
		self.pointsLost = round(Decimal(benchPlayer.points - replacedStarter.points),2)

# One week's performance for a single player
class PlayerBoxScore(RowData):
	def __init__(self):
		self.values = [0, "", "", "", "", "", "", "", "", 0.0, "", "", False]
		self.attrs = ["week", "owner", "team", "opponent", "slot", "playerName", "playerTeam", "pos", "playerOpp", "points", "draftOwner", "draftAmount", "isBench"]

class Standing:
	def __init__(self):
		self.points = 0
		self.wins = 0
		self.losses = 0
		self.ties = 0

	def toList(self, owner):
		return [owner,self.wins,self.losses,self.ties,round(Decimal(self.points),2)]

class Results:
	def __init__(self):

		# owner -> Standing
		self.standings = {}

		# Standings if every owner set optimal starting lineup
		self.standingsOptimal = {}

		# owner -> {owner -> Standing}
		# Map of standings for each owner
		# if just that owner made optimal starting lineup
		self.standingsIndividualOptimal = {}
		
		# Player -> [owner who drafted player, draft cost]
		self.playerDraftMap = {}
		
		# Every wrong decision
		# list of WrongDecisions
		self.wrongDecisionsAll = []
		
		# Every unique wrong decision that would have resulted in optimal lineup
		# list of WrongDecisions
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
	 		standing = standings[owner].toList(owner)
	 		standingsList.append(standing)

	 	with open(filename, "w") as f:
	 		w = csv.writer(f)
	 		w.writerows(standingsList)

	def Output(self):
	 	self.outputRows("results/wrongDecisionsAll.csv", self.wrongDecisionsAll)
	 	self.outputRows("results/wrongDecisionsOptimal.csv", self.wrongDecisionsOptimal)
	 	self.outputRows("results/playerData.csv", self.playerData)
	 	self.outputStandings("results/standings.csv", self.standings)
	 	self.outputStandings("results/standingsOptimal.csv", self.standingsOptimal)

	 	for index,owner in enumerate(self.standingsIndividualOptimal):
	 		standings = self.standingsIndividualOptimal[owner]
	 		filename = "results/standingsOptimal-"+owner+".csv"
	 		self.outputStandings(filename,standings)

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

#
# Fantasy Team Name
# Player Name
# Player Team
# Player Position
# Amount
#
def LoadDraft():
	rows = []

	html = open("draft/draft.html", "r").read()
	soup = BeautifulSoup(html, 'html.parser')

	# player -> [draft owner, auction value]
	playerDraftMap = {}
	
	for team in soup.find_all('tr', class_='tableHead'):
		
		for player in team.find_next_siblings('tr'):

			rowData = []
			
			# Need to grab the owner name because
			# We have one too many 'Butt Stuffs' in our league
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
def RunOptimalLinupAlgo(startingScoreRowData, benchScoreRowData, optimalWrongDecisions, allWrongDecisions):
	
	startingPlayers = startingScoreRowData[:]
	
	playersToInsert = benchScoreRowData[:]
	startersRemovedFromLineup = []

	# Gather all possible wrong decisions
	# This is list of any bench player that out scored any starter
	for benchPlayer in benchScoreRowData:
		for starter in startingScoreRowData:
			if  not DoesPosFitInSlot(benchPlayer.pos, starter.slot):
				continue

			if benchPlayer.points > starter.points:
				allWrongDecisions.append(WrongDecision(starter, benchPlayer))

	# Attempts to set the optimal lineup
	# by placing bench players into lineup where they
	# get biggest points gain.
	# The removed starter is then placed back into the queue
	# to see if there is another spot for him
	while len(playersToInsert) > 0:

		player = playersToInsert.pop(0)

		if player.points <= 0:
			continue

		# newSlot[0] is the index of starter
		# newSlot[1] is the point difference
		newSlot = [-1,0]

		for index,starter in enumerate(startingPlayers):
			if not DoesPosFitInSlot(player.pos, starter.slot):
				continue

			# Find the biggest point gain for our new player
			pointDiff = player.points - starter.points
			if round(pointDiff,2) > round(newSlot[1],2):
				newSlot[0] = index
				newSlot[1] = pointDiff

		if newSlot[0] > -1:

			# Try to reinsert the now benched player back
			# into starting lineup. Maybe there is still hope
			playerToRemove = startingPlayers[newSlot[0]]
			playersToInsert.append(playerToRemove)

			if not playerToRemove.isBench:
				startersRemovedFromLineup.append(startingPlayers[newSlot[0]])

			# set player's slot and place into the starting lineup!
			player.slot = playerToRemove.slot
			startingPlayers[newSlot[0]] = player
			
	# get list of actual swaps and add to wrong decisions list
	# There should be one swap (bench player) per removed starter
	# it doesn't really matter which one
	replacedPlayers = []
	for removedStarter in startersRemovedFromLineup:
		for starter in startingPlayers:
			if starter.isBench and DoesPosFitInSlot(removedStarter.pos, starter.slot) and starter not in replacedPlayers:
				wrongDecision = WrongDecision(removedStarter, starter)
				optimalWrongDecisions.append(wrongDecision)
				replacedPlayers.append(starter)
				break

	return startingPlayers

#
# Return list of PlayerBoxScore row data from the given playerTable
#
def LoadStatsForTeam(playerTable, index, week, owners, teamNames, playerDraftMap):

	scoreRowData = []

	playerRows = playerTable.find_all('tr', class_='pncPlayerRow')
		
	for row in playerRows:
		playerData = PlayerBoxScore()
		playerData.week = week
		playerData.owner = owners[index]
		playerData.team = teamNames[index]
		playerData.opponent = teamNames[(index+1)%2]

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

		playerData.slot = slot

		playerInfo = row.find('td', class_='playertablePlayerName')

		# Some terrible human forgot to start anyone at all
		if playerInfo is None:
			scoreRowData.append(playerData)
			continue

		playerName = playerInfo.a.text.strip()
		playerData.playerName = playerName

		if isDefense:
			playerData.pos = "Defense"
		else:
			playerInfoString = playerInfo.text.strip()
			if isBench and playerInfoString.find(",") == -1:
				# Defenses on the bench have no commas
				playerData.pos = "Defense"
			else:
				details = playerInfoString.split(",")[1].strip().split()
				playerData.playerTeam = details[0]
				playerData.pos = details[1]

		playerData.playerOpp = row.find('td', class_='').text

		playerPoints = row.find('td', class_='playertableStat').text
		try:
			points = float(playerPoints)
			playerData.points = points
		except ValueError:
			pass

		draftInfo = ["", ""]

		try:
			draftInfo = playerDraftMap[playerName]
		except KeyError:
			pass

		playerData.draftOwner = draftInfo[0]
		playerData.draftAmount = draftInfo[1]
		playerData.isBench = isBench

		scoreRowData.append(playerData)

	return scoreRowData


def UpdateStandings(owners, standings, totalWeekPoints):
	for index,owner in enumerate(owners):
		ownerStandings = None
		try:
			ownerStandings = standings[owner]
		except KeyError:
			standings[owner] = Standing()
			ownerStandings = standings[owner]

		ownerStandings.points += totalWeekPoints[index]

		oppOwnerIndex = (index+1) % 2

		if round(totalWeekPoints[index],2) == round(totalWeekPoints[oppOwnerIndex],2):
			ownerStandings.ties += 1
		elif totalWeekPoints[index] > totalWeekPoints[oppOwnerIndex]:
			ownerStandings.wins += 1
		else:
			ownerStandings.losses += 1


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
	# totalWeekPoints[1]  total week points for optimal lineups
	# totalWeekPoints[2]  total week points for owner[0] optimal standings
	# totalWeekPoints[3]  total week points for owner[1] optimal standings
	totalWeekPoints = [[0,0],[0,0],[0,0],[0,0]]

	for index,playerTable in enumerate(players):

		startingScoreRowData = LoadStatsForTeam(playerTable, index, week, owners, teamNames, results.playerDraftMap)
		benchScoreRowData = LoadStatsForTeam(benches[index], index, week, owners, teamNames, results.playerDraftMap)

		# Add all starting and bench players to player data
		for row in startingScoreRowData:
			results.playerData.append(row)

		for row in benchScoreRowData:
			results.playerData.append(row)

		# Get the optimal staring lineup
		optimalScoringPlayers = RunOptimalLinupAlgo(startingScoreRowData, benchScoreRowData, results.wrongDecisionsOptimal, results.wrongDecisionsAll) 

		# Calculate total week points for both starting lineup
		# and the optimal starting lineup
		for player in startingScoreRowData:
			totalWeekPoints[0][index] += player.points

			# update points to other owner's optimal standings
			oppOwnerOptimalIndex = ((index+1)%2) + 2
			totalWeekPoints[oppOwnerOptimalIndex][index] += player.points

		for player in optimalScoringPlayers:
			totalWeekPoints[1][index] += player.points
			totalWeekPoints[index+2][index] += player.points

	# update both standings maps from totalWeekPoints
	UpdateStandings(owners, results.standings, totalWeekPoints[0])
	UpdateStandings(owners, results.standingsOptimal, totalWeekPoints[1])

	# update standings for each owner optimal standings
	for index,owner in enumerate(owners):
		standings = None
		try:
			standings = results.standingsIndividualOptimal[owner]
		except KeyError:
			results.standingsIndividualOptimal[owner] = {}
			standings = results.standingsIndividualOptimal[owner]

		UpdateStandings(owners, standings, totalWeekPoints[index+2])

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

