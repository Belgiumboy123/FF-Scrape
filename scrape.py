from bs4 import BeautifulSoup
from decimal import Decimal
from itertools import chain
import csv
import getopt
import glob
import os
import requests
import subprocess
import sys

# List of urls used to download files
DraftUrl = "http://games.espn.com/ffl/tools/draftrecap?leagueId=524258&year=2016"
StandingsUrl = "http://games.espn.go.com/ffl/standings?leagueId=524258&seasonId=2016"
ScheduleUrl = "http://games.espn.com/ffl/schedule?leagueId=524258"
BoxScoreQuickUrl = "http://games.espn.com/ffl/boxscorequick?leagueId=524258&teamId={}&scoringPeriodId={}&seasonId=2016&view=scoringperiod&version=quick"

def GetBoxScoreQuickUrl(teamId, scoringPeriodId):
	return BoxScoreQuickUrl.format(teamId, scoringPeriodId)


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

# Individual auction draft result
class PlayerDraftInfo(RowData):
	def __init__(self):
		self.values = ["","","","", 0]
		self.attrs = ["owner", "playerName", "playerTeam", "pos", "draftAmount"]

class Standing:
	def __init__(self):
		self.points = 0
		self.wins = 0
		self.losses = 0
		self.ties = 0
		self.madePlayoffs = False

	def toList(self, owner):
		return [owner,self.wins,self.losses,self.ties,round(Decimal(self.points),2),self.madePlayoffs]

	# Compare two separate team standings
	# The higher placed standing comes first
	def __cmp__(self, other):
		if self.wins > other.wins:
			return -1 
		elif self.wins == other.wins:
			# should check ties/losses here first
			# TODO This will break when comparing ties
			if self.points > other.points:
				return -1
			else:
				return 0
		else:
			return 1

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

		# list of [owner, player name, player team, pos, draft cost]
		self.allDraftData = []
		
		# Every wrong decision
		# list of WrongDecisions
		self.wrongDecisionsAll = []
		
		# Every unique wrong decision that would have resulted in optimal lineup
		# list of WrongDecisions
		self.wrongDecisionsOptimal = []

		# Every individual player game data
		# See comment at LoadStatsForTeam
		self.playerData = []

		# The two divisions.
		# Division -> list of owners
		self.divisions = { "east" : [], "west" : [] }

	def InitializeWithOwners(self):
		for owner in self.divisions["east"] + self.divisions["west"]:
			self.standings[owner] = Standing()
			self.standingsOptimal[owner] = Standing()

			# initialize individual optimal standings here
			self.standingsIndividualOptimal[owner] = {}
			for ownerOpt in self.divisions["east"] + self.divisions["west"]:
				self.standingsIndividualOptimal[owner][ownerOpt] = Standing()

	def CalculatePlayoffTeams(self):
		# figure out top 4 playoff teams for each standings
		CalculatePlayoffTeams(self.divisions, self.standings)
		CalculatePlayoffTeams(self.divisions, self.standingsOptimal)
		for index,owner in enumerate(self.standingsIndividualOptimal):
			CalculatePlayoffTeams(self.divisions, self.standingsIndividualOptimal[owner])

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
	 	self.outputRows("results/draft.csv", self.allDraftData)
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


def LoadContent(url, directory, proposedFileName):

	filepath = directory+ "/" + proposedFileName
	content = None

	if not os.path.exists(filepath):
		content = requests.get(url).content
		with open(filepath, 'wb') as f:
			f.write(content)
	else:
		content = open(filepath, "r").read()

	return content

# Given a link element parse out owner name from title.
# Format is 'team name (owner name)'
def ParseOwner(linkTag):
	title = linkTag['title']
	idxStart = title.index('(')
	idxEnd = title.index(')')
	owner = title[idxStart+1:idxEnd]
	return owner

def LoadDraft(results):

	content = LoadContent(DraftUrl, "draft", "draft.html")

	soup = BeautifulSoup(content, 'html.parser')

	for team in soup.find_all('tr', class_='tableHead'):
		
		for player in team.find_next_siblings('tr'):

			playerDraftInfo = PlayerDraftInfo()
			
			# Need to grab the owner name because
			# We have one too many 'Butt Stuffs' in our league
			owner = ParseOwner(team.a)
			playerDraftInfo.owner = owner

			data = player.find_all('td')
			playerName = data[1].a.text.strip()
			playerDraftInfo.playerName = playerName

			playerData = data[1].text.strip()
			if 'D/ST' in playerData:
				playerDraftInfo.playerTeam = ""
				playerDraftInfo.pos = "Defense"
			else:
				playerDetails = playerData.split(',')[1].strip().split()
				playerDraftInfo.playerTeam = playerDetails[0]
				playerDraftInfo.pos = playerDetails[1]

			amount = data[2].text.strip()[1:]
			playerDraftInfo.draftAmount = amount

			results.playerDraftMap[str(playerName)] = [str(owner), str(amount)]
			results.allDraftData.append(playerDraftInfo)

def CalculatePlayoffTeams(divisions, standings):

	eastTeams = []
	westTeams = []

	for index,owner in enumerate(standings):
		if owner in divisions["east"]:
			eastTeams.append(standings[owner])
		else:
			westTeams.append(standings[owner])

	eastTeams.sort()
	westTeams.sort()

	# Don't bother with playoff teams with less than
	# 5 teams in either division
	if len(eastTeams) < 5 or len(westTeams) < 5:
		return

	eastTeams[0].madePlayoffs = True
	westTeams[0].madePlayoffs = True

	eastIndex = 1
	westIndex = 1
	for i in range(0,2):
		if eastTeams[eastIndex].__cmp__(westTeams[westIndex]) == -1:
			eastTeams[eastIndex].madePlayoffs = True
			eastIndex += 1
		else:
			westTeams[westIndex].madePlayoffs = True
			westIndex += 1

#
# First get divisions webpage
# Save division into results
# Calulate all playoff teams based on final standings
# This assumes all standings in results have been calculated
#
def LoadDivisions(results):

	content = LoadContent(StandingsUrl, "divisions", "divisions.html")
	soup = BeautifulSoup(content, 'html.parser')

	mainDiv = soup.find('div', class_='games-fullcol')
	tables = mainDiv.find_all('table', class_='tableBody')

	for index,table in enumerate(tables):
		teams = table.find_all('tr', class_="tableBody")
		if len(teams) is 0:
			continue

		division = "east"
		if index is 1:
			division = "west"

		for team in teams:
			owner = ParseOwner(team.find('a'))
			results.divisions[division].append(owner)


	# initialize all maps relient on existing owners in results.
	results.InitializeWithOwners()

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
			if not DoesPosFitInSlot(benchPlayer.pos, starter.slot):
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


#
# For optimal owner update with optimal week points for that owner
# Otherwise update with regular scored points
#
def UpdateIndividualOptimalStandings(owners, totalWeekPointsRegular, totalWeekPointsOptimal1, totalWeekPointsOptimal2, results):
	for index,owner in enumerate(results.standingsIndividualOptimal):
		if owner == owners[0]:
			UpdateStandings(owners, results.standingsIndividualOptimal[owner], totalWeekPointsOptimal1)
		elif owner == owners[1]:
			UpdateStandings(owners, results.standingsIndividualOptimal[owner], totalWeekPointsOptimal2)
		else:
			UpdateStandings(owners, results.standingsIndividualOptimal[owner], totalWeekPointsRegular)


def UpdateStandings(owners, standings, totalWeekPoints):
	for index,owner in enumerate(owners):
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
	UpdateIndividualOptimalStandings(owners, totalWeekPoints[0], totalWeekPoints[2], totalWeekPoints[3], results)

def DownloadBoxscores():
	schedulesContent = LoadContent(ScheduleUrl, "schedules", "schedules.html")
	soup = BeautifulSoup(schedulesContent, 'html.parser')

	tables = soup.find_all('table', class_='tableBody')

	# Remove league settings tables
	# there should only be one table left after this
	tables = [table for table in tables if "leagueSettingsTable" not in table["class"] ]
	table = tables[0]

	# Filter out all non matchup rows from table
	tableRows = table.find_all('tr')
	matchupRows = [row for row in tableRows if 'class' not in row.attrs]

	matches = 0

	for index,matchup in enumerate(matchupRows):

		# There should be at least 5 table cells
		cells = matchup.find_all('td')
		if len(cells) < 5:
			continue

		scoringPeriodId = matches/5 + 1
		matches += 1

		# We only care about the regular season
		if scoringPeriodId > 13:
			break;

		# Parse out the teamId
		link = cells[0].a["href"]
		teamIdIndex = link.index("teamId=")
		link = link[teamIdIndex+7:]
		teamId = link[:link.index('&')]

		# Get Url and name the file
		url = GetBoxScoreQuickUrl(teamId, scoringPeriodId)
		filename = "week_" + str(scoringPeriodId) + ":_" + cells[1].text + "_vs_" + cells[4].text + ".html"

		print("Downloading boxscore to file: " + filename)
		print(url)

		LoadContent(url, 'boxscores', filename)

'''
Load stats for every single page found in directory
'''
def LoadStats(results, useTestDir):

	dirname = 'boxscores'
	if useTestDir:
		dirname = 'test'
	else:
		# if there are no files in boxscores directory
		# download all boxscores from espn
		if len(glob.glob(dirname +"/*.html")) == 0:
			DownloadBoxscores()

	for item in os.listdir(dirname):
		if not item.endswith(".html"):
			continue

		print(item)
		LoadStatsForPage(dirname+'/'+item, results)

def main(argv):
	try:
		opts, args = getopt.getopt(argv,"tr")
	except getopt.GetoptError:
		print("scrape.py -t [use test dir] -r [cleans all files]")
		sys.exit(2)

	useTestDir = False
	for opt, arg in opts:
		if opt == '-t':
			useTestDir = True
		elif opt == '-r':
			# This option will terminate program after cleaning
			# This option removes all files from the results folder.
			subprocess.Popen('rm results/*.*', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			sys.exit(0)

	results = Results()

	# Load all divisions and owners
	LoadDivisions(results)

	# Load all draft information
	LoadDraft(results)

	# Get all boxscore data and store in results
	LoadStats(results, useTestDir)

	# calculate playoff teams for all standings
	results.CalculatePlayoffTeams()

	# Write all of the results out to csv files
	results.Output()
                             
if __name__ == '__main__':
    main(sys.argv[1:])

