from itertools import chain
from bs4 import BeautifulSoup
import csv
from time import sleep
import sys
import os
import getopt


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



def RunWrongDecisionsAlgo(startingScoreRowData, benchScoreRowData, wrongDecisions):
	
	startingPlayers = startingScoreRowData[:]
	
	playersToInsert = benchScoreRowData[:]
	startersRemovedFromLineup = []

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
	for removedStarter in startersRemovedFromLineup:
		for starter in startingPlayers:
			if starter[12] and DoesPosFitInSlot(removedStarter[7], starter[4]):
				wrongDecision = []
				wrongDecision.append(starter[1])
				wrongDecision.append(starter[0])
				wrongDecision.append(removedStarter[5])
				wrongDecision.append(starter[5])
				wrongDecision.append(starter[9] - removedStarter[9])
				wrongDecisions.append(wrongDecision)

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


def LoadStatsForPage(htmlFile, rows, playerDraftMap, standings, loadWrongDecisions, wrongDecisions):

	html = open(htmlFile, "r").read()
	soup = BeautifulSoup(html, 'html.parser')
  
  	# get week
  	week = soup.find('div', class_='games-pageheader').em.text[5:].strip()

	players = soup.find_all('table', class_='playerTableTable tableBody')

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
	totalWeekPoints = [0,0]

	for index,playerTable in enumerate(players):

		startingScoreRowData = LoadStatsForTeam(playerTable, index, week, owners, teamNames, playerDraftMap)

		playersToCount = []

		if loadWrongDecisions:
			benchScoreRowData = LoadStatsForTeam(benches[index], index, week, owners, teamNames, playerDraftMap)
			playersToCount = RunWrongDecisionsAlgo(startingScoreRowData, benchScoreRowData, wrongDecisions)
		else:
			playersToCount = startingScoreRowData

		for player in playersToCount:
			totalWeekPoints[index] += player[9]

		for row in startingScoreRowData:
			rows.append(row)


	# update standings map from totalWeekPoints
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


def LoadStats(playerDraftMap, useTestDir, loadWrongDecisions):

	rows = []

	# owner -> [wins, losses, totalpoints]
	standings = {}

	# list of wrong decisions [owner, week, starter nane, bench name, points lost]
	wrongDecisions = []

	dirname = 'boxscores'
	if useTestDir:
		dirname = 'test'

	for item in os.listdir(dirname):
		print(item)
		LoadStatsForPage(dirname + '/'+item, rows, playerDraftMap, standings, loadWrongDecisions, wrongDecisions)

	with open("boxscoredatanew.csv", "w") as f:
		writer = csv.writer(f)
		writer.writerows(rows)

	# Convert standings owner map to a list of standings
 	standingsList = []
 	for index,owner in enumerate(standings):
 		standing = []
 		standing.append(owner)
 		for val in standings[owner]:
 			standing.append(val)
 		standingsList.append(standing)

 	with open("standings.csv", "w") as f:
 		w = csv.writer(f)
 		w.writerows(standingsList)

 	with open("wrongdecisions.csv", "w") as f:
 		w = csv.writer(f)
 		w.writerows(wrongDecisions)

def main(argv):

	try:
		opts, args = getopt.getopt(argv,"tdw")
	except getopt.GetoptError:
		print("scrape.py -t [use test dir] -d [parse draft] -w [wrong decisions]")
		sys.exit(2)

	loadDraft = False
	useTestDir = False
	loadWrongDecisions = False

	for opt, arg in opts:
		if opt == '-t':
			useTestDir = True
		elif opt == '-d':
			loadDraft = True
		elif opt == '-w':
			loadWrongDecisions = True

	playerDraftMap = {} 
	if loadDraft:
		playerDraftMap = LoadDraft()

	LoadStats(playerDraftMap, useTestDir, loadWrongDecisions)
	
                             
if __name__ == '__main__':
    main(sys.argv[1:])
